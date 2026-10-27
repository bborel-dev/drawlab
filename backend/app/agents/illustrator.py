from dataclasses import dataclass
from typing import Iterator

import numpy as np
from PIL import Image

from app.agents.art_director import ArtDirection
from app.agents.cutter import Cut
from app.id_map import covering_id_map, path_centroids, path_fill_colors
from app.ink import UNOWNED, erase_ink, find_ink, front_ink_owners, ink_path_colors, overlapping_ink_region
from app.seams import find_gaps, seal_seams, trace_gap_patch
from app.tracing import (
    downscale_for_tracing,
    recolor_binary_path,
    svg_document,
    trace_binary_paths,
    trace_paths,
)

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
    ink = find_ink(trace_image)
    color_image = erase_ink(trace_image, ink)
    paths = trace_paths(color_image, hierarchical="cutout")
    ids = covering_id_map(paths, color_image.size)
    names = layer_names(direction)
    owners = paint_object_owners(cuts, names, color_image.size)
    path_owner = assign_paths(ids, owners, len(paths), len(names))
    fill_unowned_paths(path_owner, paths, ids, direction, names)
    pixel_owner = path_owner[ids]
    ink_owner = front_ink_owners(ink, pixel_owner, color_image.width)
    color_paths = group_color_paths(paths, path_owner, len(names))
    gaps, rendered = find_gaps([path for layer_paths in color_paths for path in layer_paths], color_image.size)
    for index, name in enumerate(names):
        color = color_part(color_paths[index], trace_gap_patch(rendered, gaps & (pixel_owner == index)))
        line = trace_ink_part(trace_image, overlapping_ink_region(ink, ink_owner, index))
        layer = assemble_layer(name, color, line)
        if layer:
            yield layer


def assemble_svg(size: tuple[int, int], layers: list[Layer]) -> str:
    return svg_document(size, "".join(layer.svg for layer in layers))


def layer_names(direction: ArtDirection) -> list[str]:
    names = [element.name for element in direction.elements]
    has_surface = any(element.kind == "surface" for element in direction.elements)
    return names if has_surface else [BACKGROUND_LAYER, *names]


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


def group_color_paths(paths: list[str], path_owner: np.ndarray, layer_count: int) -> list[list[str]]:
    grouped: list[list[str]] = [[] for _ in range(layer_count)]
    for path_index, path in enumerate(paths, start=1):
        grouped[path_owner[path_index]].append(seal_seams(path))
    return grouped


def color_part(paths: list[str], gap_patch: str | None) -> LayerPart | None:
    patched = [*paths, gap_patch] if gap_patch else paths
    return LayerPart(paths=patched, offset=(0, 0)) if patched else None


def trace_ink_part(image: Image.Image, region: np.ndarray) -> LayerPart | None:
    box = Image.fromarray(region.astype(np.uint8) * 255).getbbox()
    if box is None:
        return None
    left, top, right, bottom = box
    region_crop = region[top:bottom, left:right]
    paths = trace_binary_paths(region_crop)
    if not paths:
        return None
    colors = ink_path_colors(paths, np.asarray(image)[top:bottom, left:right], region_crop)
    return LayerPart(paths=[recolor_binary_path(path, color) for path, color in zip(paths, colors)], offset=(left, top))


def assemble_layer(name: str, color: LayerPart | None, line: LayerPart | None) -> Layer | None:
    parts = [(f"{name}-color", "color", color), (f"{name}-ink", "ink", line)]
    groups = [part_group(group_id, kind, part) for group_id, kind, part in parts if part]
    if not groups:
        return None
    path_count = sum(len(part.paths) for _, _, part in parts if part)
    return Layer(name=name, svg=f'<g id="{name}">{"".join(groups)}</g>', path_count=path_count)


def part_group(group_id: str, kind: str, part: LayerPart) -> str:
    x, y = part.offset
    transform = f' transform="translate({x},{y})"' if (x, y) != (0, 0) else ""
    return f'<g id="{group_id}" data-pass="{kind}"{transform}>{"".join(part.paths)}</g>'
