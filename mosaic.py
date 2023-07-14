import logging
import sys
from multiprocessing import Process, Queue, cpu_count
from pathlib import Path

import typer
from PIL import Image, ImageOps
from rich import print
from rich.progress import Progress, track

# Change these 3 config parameters to suit your needs...
DEFAULT_TILE_SIZE = 50  # height/width of mosaic tiles in pixels
DEFAULT_TILE_MATCH_RES = 5  # tile matching resolution (higher values give better fit but require more processing)
DEFAULT_ENLARGEMENT = (
    2  # the mosaic image will be this many times wider and taller than the original
)

# TILE_BLOCK_SIZE = TILE_SIZE / max(min(TILE_MATCH_RES, TILE_SIZE), 1)
WORKER_COUNT = max(cpu_count() - 1, 1)
EOQ_VALUE = None

APP = typer.Typer()


def _tile_block_size(tile_size, tile_match_res):
    return tile_size / max(min(tile_match_res, tile_size), 1)


class TileProcessor:
    def __init__(self, tiles_directory, tile_size, tile_match_res):
        self.tiles_directory = str(Path(tiles_directory).resolve())
        self.tile_size = tile_size
        self.tile_match_res = tile_match_res

    @property
    def tile_block_size(self):
        return _tile_block_size(
            tile_size=self.tile_size, tile_match_res=self.tile_match_res
        )

    def __process_tile(self, tile_path):
        try:
            img = Image.open(tile_path)
            img = ImageOps.exif_transpose(img)

            # tiles must be square, so get the largest square that fits inside the image
            w = img.size[0]
            h = img.size[1]
            min_dimension = min(w, h)
            w_crop = (w - min_dimension) / 2
            h_crop = (h - min_dimension) / 2
            img = img.crop((w_crop, h_crop, w - w_crop, h - h_crop))

            large_tile_img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
            small_tile_img = img.resize(
                (
                    int(self.tile_size / self.tile_block_size),
                    int(self.tile_size / self.tile_block_size),
                ),
                Image.LANCZOS,
            )

            return (large_tile_img.convert("RGB"), small_tile_img.convert("RGB"))
        except Exception:
            logging.error("Failed to read or convert image.", exc_info=True)
            return (None, None)

    def get_tiles(self):
        large_tiles = []
        small_tiles = []

        print("Reading tiles from {}...".format(self.tiles_directory))

        # search the tiles directory recursively
        def _process_image(image_path: Path):
            assert image_path.exists()
            large_tile, small_tile = self.__process_tile(image_path)
            return large_tile, small_tile

        with Progress() as progress:
            task = progress.add_task("Reading tiles", total=None)
            for image_path_unresolved in Path(self.tiles_directory).iterdir():
                image_path = image_path_unresolved.resolve()
                assert image_path.exists(), image_path
                large_tile, small_tile = _process_image(image_path=image_path)
                if all(tile is not None for tile in (large_tile, small_tile)):
                    large_tiles.append(large_tile)
                    small_tiles.append(small_tile)
                progress.update(task, description=image_path.name)

        print("Processed {} tiles.".format(len(large_tiles)))

        return (large_tiles, small_tiles)


class TargetImage:
    def __init__(self, image_path, enlargement, tile_size, tile_match_res):
        self.image_path = image_path
        self.enlargement = enlargement
        self.tile_size = tile_size
        self.tile_match_res = tile_match_res

    @property
    def tile_block_size(self):
        return _tile_block_size(
            tile_size=self.tile_size, tile_match_res=self.tile_match_res
        )

    def get_data(self):
        print("Processing main image...")
        img = Image.open(self.image_path)
        w = img.size[0] * self.enlargement
        h = img.size[1] * self.enlargement
        large_img = img.resize((w, h), Image.LANCZOS)
        w_diff = (w % self.tile_size) / 2
        h_diff = (h % self.tile_size) / 2

        # if necessary, crop the image slightly so we use a whole number of tiles horizontally and vertically
        if w_diff or h_diff:
            large_img = large_img.crop((w_diff, h_diff, w - w_diff, h - h_diff))

        small_img = large_img.resize(
            (int(w / self.tile_block_size), int(h / self.tile_block_size)),
            Image.LANCZOS,
        )

        image_data = (large_img.convert("RGB"), small_img.convert("RGB"))

        print("Main image processed.")

        return image_data


class TileFitter:
    def __init__(self, tiles_data):
        self.tiles_data = tiles_data

    def __get_tile_diff(self, t1, t2, bail_out_value):
        diff = 0
        for i in range(len(t1)):
            # diff += (abs(t1[i][0] - t2[i][0]) + abs(t1[i][1] - t2[i][1]) + abs(t1[i][2] - t2[i][2]))
            diff += (
                (t1[i][0] - t2[i][0]) ** 2
                + (t1[i][1] - t2[i][1]) ** 2
                + (t1[i][2] - t2[i][2]) ** 2
            )
            if diff > bail_out_value:
                # we know already that this isn't going to be the best fit, so no point continuing with this tile
                return diff
        return diff

    def get_best_fit_tile(self, img_data):
        best_fit_tile_index = None
        min_diff = sys.maxsize
        tile_index = 0

        # go through each tile in turn looking for the best match for the part of the image represented by 'img_data'
        for tile_data in self.tiles_data:
            diff = self.__get_tile_diff(img_data, tile_data, min_diff)
            if diff < min_diff:
                min_diff = diff
                best_fit_tile_index = tile_index
            tile_index += 1

        return best_fit_tile_index


def fit_tiles(work_queue, result_queue, tiles_data):
    # this function gets run by the worker processes, one on each CPU core
    tile_fitter = TileFitter(tiles_data)

    while True:
        try:
            img_data, img_coords = work_queue.get(True)
            if img_data == EOQ_VALUE:
                break
            tile_index = tile_fitter.get_best_fit_tile(img_data)
            result_queue.put((img_coords, tile_index))
        except KeyboardInterrupt:
            pass

    # let the result handler know that this worker has finished everything
    result_queue.put((EOQ_VALUE, EOQ_VALUE))


class MosaicImage:
    def __init__(self, original_img, tile_size):
        self.image = Image.new(original_img.mode, original_img.size)
        self.x_tile_count = int(original_img.size[0] / tile_size)
        self.y_tile_count = int(original_img.size[1] / tile_size)
        self.total_tiles = self.x_tile_count * self.y_tile_count
        self.tile_size = tile_size

    def add_tile(self, tile_data, coords):
        img = Image.new("RGB", (self.tile_size, self.tile_size))
        img.putdata(tile_data)
        self.image.paste(img, coords)

    def save(self, path):
        self.image.save(path)


def build_mosaic(
    result_queue, all_tile_data_large, original_img_large, output_image: Path, tile_size
):
    mosaic = MosaicImage(original_img_large, tile_size=tile_size)

    active_workers = WORKER_COUNT
    while True:
        try:
            img_coords, best_fit_tile_index = result_queue.get()

            if img_coords == EOQ_VALUE:
                active_workers -= 1
                if not active_workers:
                    break
            else:
                tile_data = all_tile_data_large[best_fit_tile_index]
                mosaic.add_tile(tile_data, img_coords)

        except KeyboardInterrupt:
            pass

    mosaic.save(output_image)


def compose(original_img, tiles, output_image: Path, tile_size, tile_block_size):
    print("Building mosaic, press Ctrl-C to abort...")
    original_img_large, original_img_small = original_img
    tiles_large, tiles_small = tiles

    mosaic = MosaicImage(original_img_large, tile_size=tile_size)

    all_tile_data_large = [list(tile.getdata()) for tile in tiles_large]
    all_tile_data_small = [list(tile.getdata()) for tile in tiles_small]

    work_queue = Queue(WORKER_COUNT)
    result_queue = Queue()
    build_mosaic_process = Process(
        target=build_mosaic,
        args=(
            result_queue,
            all_tile_data_large,
            original_img_large,
            output_image,
            tile_size,
        ),
    )

    try:
        # start the worker processes that will build the mosaic image
        build_mosaic_process.start()

        # start the worker processes that will perform the tile fitting
        worker_processes = []
        for n in range(WORKER_COUNT):
            worker_process = Process(
                target=fit_tiles, args=(work_queue, result_queue, all_tile_data_small)
            )
            worker_process.start()
            worker_processes.append(worker_process)

        for x in track(range(mosaic.x_tile_count), "Processing..."):
            for y in range(mosaic.y_tile_count):
                large_box = (
                    x * tile_size,
                    y * tile_size,
                    (x + 1) * tile_size,
                    (y + 1) * tile_size,
                )
                small_box = (
                    x * tile_size / tile_block_size,
                    y * tile_size / tile_block_size,
                    (x + 1) * tile_size / tile_block_size,
                    (y + 1) * tile_size / tile_block_size,
                )
                work_queue.put(
                    (list(original_img_small.crop(small_box).getdata()), large_box)
                )

        return build_mosaic_process

    except KeyboardInterrupt:
        print("\nHalting, saving partial image please wait...")

    finally:
        # put these special values onto the queue to let the workers know they can terminate
        for n in range(WORKER_COUNT):
            work_queue.put((EOQ_VALUE, EOQ_VALUE))


def mosaic(
    img_path, tiles_path, output_image: Path, tile_size, tile_match_res, enlargement
):
    target_image = TargetImage(
        img_path,
        enlargement=enlargement,
        tile_size=tile_size,
        tile_match_res=tile_match_res,
    )
    image_data = target_image.get_data()
    tiles_data = TileProcessor(
        tiles_path, tile_size=tile_size, tile_match_res=tile_match_res
    ).get_tiles()
    if tiles_data[0]:
        build_mosaic_process = compose(
            image_data,
            tiles_data,
            output_image=output_image,
            tile_size=tile_size,
            tile_block_size=target_image.tile_block_size,
        )
        return build_mosaic_process
    else:
        raise FileNotFoundError(
            "Expected images in tiles directory {}".format(tiles_path)
        )


@APP.command()
def main(
    target_image: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="The image to compose using provided tiles.",
    ),
    tile_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="The directory with image tiles.",
    ),
    output_image: Path = typer.Option(
        Path("mosaic.jpeg"),
        help="Output image path.",
    ),
    tile_size: int = typer.Option(
        DEFAULT_TILE_SIZE,
        help="Height/width of mosaic tiles in pixels.",
    ),
    tile_match_res: int = typer.Option(
        DEFAULT_TILE_MATCH_RES,
        help="Tile matching resolution (higher values give better fit but require more processing).",
    ),
    enlargement: int = typer.Option(
        DEFAULT_ENLARGEMENT,
        help="The mosaic image will be this many times wider and taller than the original.",
    ),
):
    build_mosaic_process = mosaic(
        img_path=target_image,
        tiles_path=tile_dir,
        output_image=output_image,
        tile_size=tile_size,
        tile_match_res=tile_match_res,
        enlargement=enlargement,
    )
    assert build_mosaic_process is not None
    # Join the mosaic building process
    build_mosaic_process.join()
    print("\nFinished, output is in {}".format(output_image))


if __name__ == "__main__":
    APP()
