from pathlib import Path

import pytest

import mosaic

LIBRARY_1_PATH = Path("tests/sample_data/library/")
NIXOS_IMAGE_PATH = LIBRARY_1_PATH / "nixos_logo.png"


@pytest.mark.parametrize("target_image, tile_dir", [(NIXOS_IMAGE_PATH, LIBRARY_1_PATH)])
def test_main(target_image, tile_dir, tmp_path):
    output_image = tmp_path / "output.jpg"
    mosaic.mosaic(img_path=target_image, tiles_path=tile_dir, output_image=output_image)
    assert output_image.exists()
