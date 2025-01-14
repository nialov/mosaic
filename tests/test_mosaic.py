import time
from hashlib import sha256
from itertools import count
from pathlib import Path

import pytest

import mosaic

LIBRARY_1_PATH = Path("tests/sample_data/library/")
NIXOS_IMAGE_PATH = LIBRARY_1_PATH / "nixos_logo.png"


@pytest.mark.parametrize("target_image, tile_dir", [(NIXOS_IMAGE_PATH, LIBRARY_1_PATH)])
def test_main(target_image, tile_dir, tmp_path: Path, data_regression):
    output_image = tmp_path / "output.png"
    build_mosaic_process = mosaic.mosaic(
        img_path=target_image,
        tiles_path=tile_dir,
        output_image=output_image,
        tile_size=mosaic.DEFAULT_TILE_SIZE,
        tile_match_res=mosaic.DEFAULT_TILE_MATCH_RES,
        enlargement=mosaic.DEFAULT_ENLARGEMENT,
    )
    assert build_mosaic_process is not None
    # Join the mosaic building process
    build_mosaic_process.join()
    # assert result_queue.empty(), result_queue
    assert output_image.exists(), output_image

    image_bytes = output_image.read_bytes()
    sha256_hash = sha256()
    sha256_hash.update(image_bytes)

    data_regression.check(dict(image_hash=sha256_hash.hexdigest()))
