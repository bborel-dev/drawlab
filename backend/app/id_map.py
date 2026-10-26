import io
import re

import numpy as np
import resvg_py
from PIL import Image

from app.tracing import svg_document

FILL_PATTERN = re.compile(r'fill="#[0-9A-Fa-f]{6}"')


def render_id_map(paths: list[str], size: tuple[int, int]) -> np.ndarray:
    id_paths = [FILL_PATTERN.sub(f'fill="#{index + 1:06X}"', path) for index, path in enumerate(paths)]
    png = resvg_py.svg_to_bytes(
        svg_string=svg_document(size, "".join(id_paths)), background="#000000", shape_rendering="crisp_edges"
    )
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.int64)
    return (pixels[..., 0] << 16) | (pixels[..., 1] << 8) | pixels[..., 2]


def path_centroids(ids: np.ndarray, path_count: int) -> np.ndarray:
    rows, columns = np.indices(ids.shape)
    flat_ids = ids.ravel()
    areas = np.bincount(flat_ids, minlength=path_count + 1).astype(float)
    sum_x = np.bincount(flat_ids, weights=columns.ravel(), minlength=path_count + 1)
    sum_y = np.bincount(flat_ids, weights=rows.ravel(), minlength=path_count + 1)
    safe_areas = np.maximum(areas, 1.0)
    return np.stack([sum_x / safe_areas, sum_y / safe_areas], axis=1)
