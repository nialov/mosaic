import time
from itertools import count
from pathlib import Path

import pytest

import mosaic

LIBRARY_1_PATH = Path("tests/sample_data/library/")
NIXOS_IMAGE_PATH = LIBRARY_1_PATH / "nixos_logo.png"


@pytest.mark.parametrize("target_image, tile_dir", [(NIXOS_IMAGE_PATH, LIBRARY_1_PATH)])
def test_main(target_image, tile_dir, tmp_path: Path, image_regression):
    output_image = tmp_path / "output.jpg"
    result_queue = mosaic.mosaic(
        img_path=target_image, tiles_path=tile_dir, output_image=output_image
    )
    assert result_queue is not None
    counter = count()
    while not output_image.exists():
        current_count = next(counter)
        print(current_count)
        time.sleep(0.01)
        if current_count > 100:
            raise TimeoutError("Expected image to be compiled in 1 second.")

    assert result_queue.empty(), result_queue
    assert output_image.exists(), output_image
    image_regression.check(output_image.read_bytes())
