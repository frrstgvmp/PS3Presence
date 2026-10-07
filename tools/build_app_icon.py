from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_DIR / "design" / "images.png"
OUTPUT_PNG = PROJECT_DIR / "design" / "ps3-presence.png"
OUTPUT_ICO = PROJECT_DIR / "assets" / "ps3-presence.ico"
CROP = (120, 105, 230, 230)
ICON_SIZE = 512


def is_checkerboard_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return alpha > 0 and red >= 220 and abs(red - green) <= 3 and abs(green - blue) <= 3


def remove_connected_checkerboard(image: Image.Image) -> Image.Image:
    """Remove only the white/gray checkerboard connected to the crop border."""
    pixels = image.load()
    width, height = image.size
    queued: deque[tuple[int, int]] = deque()
    visited: set[tuple[int, int]] = set()

    for x in range(width):
        queued.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queued.extend(((0, y), (width - 1, y)))

    while queued:
        x, y = queued.popleft()
        if (x, y) in visited or not is_checkerboard_pixel(pixels[x, y]):
            continue
        visited.add((x, y))
        red, green, blue, _alpha = pixels[x, y]
        pixels[x, y] = (red, green, blue, 0)
        for neighbor_x, neighbor_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= neighbor_x < width and 0 <= neighbor_y < height:
                queued.append((neighbor_x, neighbor_y))
    return image


def build_icon() -> None:
    source = Image.open(SOURCE).convert("RGBA").crop(CROP)
    cutout = remove_connected_checkerboard(source)
    alpha = cutout.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise RuntimeError("No visible icon pixels were found in the source image.")

    character = cutout.crop(bounds)
    scale = min(420 / character.width, 420 / character.height)
    character = character.resize(
        (round(character.width * scale), round(character.height * scale)),
        Image.Resampling.LANCZOS,
    )
    icon = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    offset = ((ICON_SIZE - character.width) // 2, (ICON_SIZE - character.height) // 2)
    icon.alpha_composite(character, offset)
    icon.save(OUTPUT_PNG)
    icon.save(OUTPUT_ICO, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    build_icon()
