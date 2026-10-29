from dataclasses import dataclass
from typing import Iterator

import numpy as np
from PIL import Image

from app.agents.art_director import ArtDirection
from app.agents.cutter import Cut
from app.edge_blends import snap_edge_blends
from app.id_map import (
    covering_id_map,
    path_centroids,
    path_fill_colors,
    recolor_from_pixels,
    split_regions_at_ink,
)
from app.ink_colors import split_ink_by_tone
from app.outlines import (
    DETAILED,
    SMOOTH,
    Edges,
    Smoothing,
    absorb_slivers,
    box_image_edges,
    context_box,
    ink_outline_paths,
    smooth_region_paths,
)
from app.ink import (
    UNOWNED,
    erase_ink,
    find_ink,
    front_ink_owners,
    ink_path_colors,
    ink_reach,
    ink_clip_region,
    keep_ink_on_top,
)
from app.region_merging import merge_similar_regions, snap_region_boundaries
from app.seams import find_gaps, seal_seams, trace_gap_patch
from app.svg_compaction import compact_markup
from app.tracing import (
    downscale_for_tracing,
    recolor_binary_path,
    svg_document,
    trace_paths,
)
from app.underpaint import trace_underpaint, underpaint_regions
from app.unknown_objects import color_name, find_unknown_objects, surface_tone_map

BACKGROUND_LAYER = "background"
SURFACE_COLOR_TIE = 30


@dataclass(frozen=True)
class Layer:
    name: str
    svg: str
    path_count: int


@dataclass(frozen=True)
class LayerPart:
    paths: list[str]
    offset: tuple[int, int]


def draw_layers(image: Image.Image, direction: ArtDirection, cuts: list[Cut]) -> Iterator[Layer]:
    trace_image = downscale_for_tracing(image)
    reach = ink_reach(trace_image)
    ink = find_ink(trace_image, reach)
    color_image = snap_edge_blends(erase_ink(trace_image, ink))
    paths = trace_paths(color_image, hierarchical="cutout")
    paths, ids = split_regions_at_ink(paths, covering_id_map(paths, color_image.size), ink)
    names = layer_names(direction)
    owners = paint_object_owners(cuts, names, color_image.size)
    color_pixels = np.asarray(color_image)
    ids = merge_similar_regions(ids, color_pixels, owners)
    ids = absorb_slivers(snap_region_boundaries(ids, color_pixels))
    paths = recolor_from_pixels(paths, ids, color_pixels)
    path_owner = assign_paths(ids, owners, len(paths), len(names))
    unowned = path_owner == UNOWNED
    fill_unowned_paths(path_owner, paths, ids, direction, names)
    region_detailed = detailed_layers(direction, names)[path_owner]
    names = adopt_unknown_objects(path_owner, unowned, paths, ids, direction, cuts, names)
    ink_owner = front_ink_owners(ink, path_owner[ids], reach)
    detailed = inherited_details(direction, names, path_owner, region_detailed)
    paths, ids = smooth_region_paths(paths, keep_ink_on_top(ids, path_owner, ink, ink_owner), region_detailed)
    pixel_owner = path_owner[ids]
    color_paths = group_color_paths(paths, path_owner, np.bincount(ids.ravel(), minlength=len(paths) + 1), len(names))
    gaps, rendered = find_gaps([path for layer_paths in color_paths for path in layer_paths], color_image.size)
    underpaints = trace_underpaints(rendered, pixel_owner, path_owner, paths, ids, surface_indexes(direction, names))
    for index, name in enumerate(names):
        gap_patch = trace_gap_patch(rendered, gaps & (pixel_owner == index))
        color = color_part(color_paths[index], gap_patch, underpaints.get(index))
        smoothing = DETAILED if detailed[index] else SMOOTH
        line = trace_ink_part(trace_image, ink, ink_clip_region(ink, ink_owner, index), smoothing)
        layer = assemble_layer(name, color, line)
        if layer:
            yield layer


def assemble_svg(size: tuple[int, int], layers: list[Layer]) -> str:
    return svg_document(size, "".join(layer.svg for layer in layers))


def layer_names(direction: ArtDirection) -> list[str]:
    names = [element.name for element in direction.elements]
    has_surface = any(element.kind == "surface" for element in direction.elements)
    return names if has_surface else [BACKGROUND_LAYER, *names]


def detailed_layers(direction: ArtDirection, names: list[str]) -> np.ndarray:
    detailed = {element.name for element in direction.elements if element.outline == "detailed"}
    return np.array([name in detailed for name in names])


def inherited_details(
    direction: ArtDirection, names: list[str], path_owner: np.ndarray, region_detailed: np.ndarray
) -> np.ndarray:
    planned = {element.name for element in direction.elements}
    named = detailed_layers(direction, names)
    return np.array(
        [
            named[index] if name in planned else bool(region_detailed[path_owner == index].any())
            for index, name in enumerate(names)
        ]
    )


def paint_object_owners(cuts: list[Cut], names: list[str], size: tuple[int, int]) -> np.ndarray:
    masks = {cut.element_name: cut.mask for cut in cuts if cut.mask}
    owners = np.full((size[1], size[0]), UNOWNED, dtype=np.int64)
    for index, name in enumerate(names):
        mask = masks.get(name)
        if mask:
            owners[np.asarray(mask.resize(size, Image.Resampling.NEAREST)) > 127] = index
    return owners


def assign_paths(ids: np.ndarray, owners: np.ndarray, path_count: int, layer_count: int) -> np.ndarray:
    columns = layer_count + 1
    pairs = ids * columns + (owners + 1)
    counts = np.bincount(pairs.ravel(), minlength=(path_count + 1) * columns).reshape(path_count + 1, columns)
    return counts.argmax(axis=1) - 1


def fill_unowned_paths(
    path_owner: np.ndarray, paths: list[str], ids: np.ndarray, direction: ArtDirection, names: list[str]
) -> None:
    unowned = np.flatnonzero(path_owner == UNOWNED)
    surfaces = surface_centers(direction, names, (ids.shape[1], ids.shape[0]))
    if not surfaces:
        path_owner[unowned] = 0
        return
    centroids = path_centroids(ids, len(paths))
    for path_index in unowned:
        path_owner[path_index] = nearest_surface(surfaces, centroids[path_index])
    colors = path_fill_colors(paths)
    dominant = dominant_surface_colors(path_owner, colors, np.bincount(ids.ravel(), minlength=len(paths) + 1), surfaces)
    for path_index in unowned:
        path_owner[path_index] = closest_color_surface(colors[path_index], centroids[path_index], surfaces, dominant)


def adopt_unknown_objects(
    path_owner: np.ndarray,
    unowned: np.ndarray,
    paths: list[str],
    ids: np.ndarray,
    direction: ArtDirection,
    cuts: list[Cut],
    names: list[str],
) -> list[str]:
    surfaces = surface_indexes(direction, names)
    missed = missed_object_center_paths(direction, cuts, names, ids)
    adopted = list(names)
    for unknown in find_unknown_objects(path_owner, unowned, path_fill_colors(paths), ids, surfaces):
        owner = next((index for index, center_path in missed.items() if center_path in unknown.paths), None)
        if owner is None:
            adopted.append(unique_name(f"{color_name(unknown.color)}-shape", adopted))
            owner = len(adopted) - 1
        else:
            del missed[owner]
        path_owner[unknown.paths] = owner
    return adopted


def missed_object_center_paths(
    direction: ArtDirection, cuts: list[Cut], names: list[str], ids: np.ndarray
) -> dict[int, int]:
    cut_names = {cut.element_name for cut in cuts if cut.mask}
    height, width = ids.shape
    return {
        names.index(element.name): int(
            ids[min(int(element.center[1] * height), height - 1), min(int(element.center[0] * width), width - 1)]
        )
        for element in direction.elements
        if element.kind == "object" and element.name not in cut_names
    }


def trace_underpaints(
    rendered: np.ndarray,
    pixel_owner: np.ndarray,
    path_owner: np.ndarray,
    paths: list[str],
    ids: np.ndarray,
    surfaces: list[int],
) -> dict[int, str | None]:
    areas = np.bincount(ids.ravel(), minlength=len(paths) + 1)
    tones = surface_tone_map(path_owner, path_fill_colors(paths), areas, surfaces)
    return {
        surface: trace_underpaint(rendered, pixel_owner, surface, region, tones.get(surface))
        for surface, region in underpaint_regions(pixel_owner, surfaces).items()
    }


def surface_indexes(direction: ArtDirection, names: list[str]) -> list[int]:
    surfaces = [names.index(element.name) for element in direction.elements if element.kind == "surface"]
    return surfaces or [names.index(BACKGROUND_LAYER)]


def unique_name(base: str, taken: list[str]) -> str:
    name, count = base, 1
    while name in taken:
        count += 1
        name = f"{base}-{count}"
    return name


def surface_centers(
    direction: ArtDirection, names: list[str], size: tuple[int, int]
) -> list[tuple[int, tuple[float, float]]]:
    return [
        (names.index(element.name), (element.center[0] * size[0], element.center[1] * size[1]))
        for element in direction.elements
        if element.kind == "surface"
    ]


def nearest_surface(surfaces: list[tuple[int, tuple[float, float]]], point: np.ndarray) -> int:
    return min(surfaces, key=lambda surface: (surface[1][0] - point[0]) ** 2 + (surface[1][1] - point[1]) ** 2)[0]


def dominant_surface_colors(
    path_owner: np.ndarray, colors: np.ndarray, areas: np.ndarray, surfaces: list[tuple[int, tuple[float, float]]]
) -> dict[int, np.ndarray]:
    dominant: dict[int, np.ndarray] = {}
    for surface_index, _ in surfaces:
        owned = np.flatnonzero(path_owner == surface_index)
        if len(owned):
            dominant[surface_index] = colors[owned[areas[owned].argmax()]]
    return dominant


def closest_color_surface(
    color: np.ndarray,
    point: np.ndarray,
    surfaces: list[tuple[int, tuple[float, float]]],
    dominant: dict[int, np.ndarray],
) -> int:
    distances = {index: float(np.linalg.norm(color - dominant_color)) for index, dominant_color in dominant.items()}
    if not distances:
        return nearest_surface(surfaces, point)
    best = min(distances.values())
    candidates = [surface for surface in surfaces if distances.get(surface[0], np.inf) <= best + SURFACE_COLOR_TIE]
    return nearest_surface(candidates, point)


def group_color_paths(
    paths: list[str], path_owner: np.ndarray, areas: np.ndarray, layer_count: int
) -> list[list[str]]:
    grouped: list[list[str]] = [[] for _ in range(layer_count)]
    for path_index in sorted(range(1, len(paths) + 1), key=lambda index: -areas[index]):
        grouped[path_owner[path_index]].append(seal_seams(paths[path_index - 1]))
    return grouped


def color_part(paths: list[str], gap_patch: str | None, underpaint: str | None) -> LayerPart | None:
    patched = [part for part in (underpaint, *paths, gap_patch) if part]
    return LayerPart(paths=patched, offset=(0, 0)) if patched else None


def trace_ink_part(image: Image.Image, ink: np.ndarray, clip: np.ndarray, smoothing: Smoothing) -> LayerPart | None:
    box = Image.fromarray((ink & clip).astype(np.uint8) * 255).getbbox()
    if box is None:
        return None
    top, bottom, left, right = context_box((box[1], box[3], box[0], box[2]), ink.shape)
    ink_crop, clip_crop = ink[top:bottom, left:right], clip[top:bottom, left:right]
    pixels = np.asarray(image)[top:bottom, left:right]
    edges = box_image_edges((top, bottom, left, right), ink.shape)
    tones = split_ink_by_tone(pixels, ink_crop)
    paths = [path for tone in tones for path in trace_tone_paths(pixels, tone, edges, clip_crop, smoothing)]
    return LayerPart(paths=paths, offset=(left, top)) if paths else None


def trace_tone_paths(
    pixels: np.ndarray, tone: np.ndarray, edges: Edges, clip: np.ndarray, smoothing: Smoothing
) -> list[str]:
    paths = ink_outline_paths(tone, edges, clip, smoothing)
    colors = ink_path_colors(paths, pixels, tone) if paths else []
    return [recolor_binary_path(path, color) for path, color in zip(paths, colors)]


def assemble_layer(name: str, color: LayerPart | None, line: LayerPart | None) -> Layer | None:
    parts = [(f"{name}-color", "color", color), (f"{name}-ink", "ink", line)]
    groups = [part_group(group_id, kind, part) for group_id, kind, part in parts if part]
    if not groups:
        return None
    svg = compact_markup(f'<g id="{name}">{"".join(groups)}</g>')
    return Layer(name=name, svg=svg, path_count=svg.count("<path"))


def part_group(group_id: str, kind: str, part: LayerPart) -> str:
    x, y = part.offset
    transform = f' transform="translate({x},{y})"' if (x, y) != (0, 0) else ""
    return f'<g id="{group_id}" data-pass="{kind}"{transform}>{"".join(part.paths)}</g>'
