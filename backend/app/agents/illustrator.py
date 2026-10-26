from dataclasses import dataclass
from typing import Iterator

import numpy as np
from PIL import Image, ImageFilter

from app.agents.art_director import ArtDirection
from app.agents.cutter import Cut
from app.id_map import path_centroids, render_id_map
from app.tracing import downscale_for_tracing, svg_document, trace_paths

BACKGROUND_LAYER = "background"
SEAM_DILATION_SIZE = 5
UNOWNED = -1


@dataclass(frozen=True)
class Layer:
    name: str
    svg: str
    path_count: int


def draw_layers(image: Image.Image, direction: ArtDirection, cuts: list[Cut]) -> Iterator[Layer]:
    trace_image = downscale_for_tracing(image)
    paths = trace_paths(trace_image)
    ids = render_id_map(paths, trace_image.size)
    names = layer_names(direction)
    owners = paint_object_owners(cuts, names, trace_image.size)
    path_owner = assign_paths(ids, owners, len(paths), len(names))
    fill_unowned_paths(path_owner, path_centroids(ids, len(paths)), direction, names, trace_image.size)
    pixel_owner = path_owner[ids]
    rgba = trace_image.convert("RGBA")
    for index, name in enumerate(names):
        layer = trace_layer(rgba, seam_safe_region(pixel_owner, index), name)
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
    path_owner: np.ndarray, centroids: np.ndarray, direction: ArtDirection, names: list[str], size: tuple[int, int]
) -> None:
    surfaces = [
        (names.index(element.name), (element.center[0] * size[0], element.center[1] * size[1]))
        for element in direction.elements
        if element.kind == "surface"
    ]
    for path_index in np.flatnonzero(path_owner == UNOWNED):
        path_owner[path_index] = nearest_surface(surfaces, centroids[path_index]) if surfaces else 0


def nearest_surface(surfaces: list[tuple[int, tuple[float, float]]], point: np.ndarray) -> int:
    return min(surfaces, key=lambda surface: (surface[1][0] - point[0]) ** 2 + (surface[1][1] - point[1]) ** 2)[0]


def seam_safe_region(pixel_owner: np.ndarray, index: int) -> np.ndarray:
    own = pixel_owner == index
    grown = np.asarray(Image.fromarray(own).filter(ImageFilter.MaxFilter(SEAM_DILATION_SIZE)))
    return own | (grown & (pixel_owner > index))


def trace_layer(rgba: Image.Image, region: np.ndarray, name: str) -> Layer | None:
    mask = Image.fromarray(region.astype(np.uint8) * 255)
    box = mask.getbbox()
    if box is None:
        return None
    cut = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    cut.paste(rgba, mask=mask)
    paths = trace_paths(cut.crop(box))
    group = f'<g id="{name}" transform="translate({box[0]},{box[1]})">{"".join(paths)}</g>'
    return Layer(name=name, svg=group, path_count=len(paths))
