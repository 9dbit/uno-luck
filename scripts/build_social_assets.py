"""Build pinned UNO LUCK social and PWA artwork from the existing branded
boot-banner. Output is deterministic, local, and contains no user data.
This runs at Docker build time because binary assets live outside source.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

BANNER = "boot-uno-banner.webp"


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    ratio = max(width / image.width, height / image.height)
    w, h = round(image.width * ratio), round(image.height * ratio)
    scaled = image.resize((w, h), Image.Resampling.LANCZOS)
    x = (w - width) // 2
    y = (h - height) // 2
    return scaled.crop((x, y, x + width, y + height))


def artwork(source: Image.Image, width: int, height: int, icon: bool = False):
    src_w, src_h = source.size
    # Logo and its three stars occupy the upper part of the original vertical
    # game banner. The lower figure/character is intentionally excluded.
    crop_h = min(src_h, round(src_h * 0.405))
    emblem = source.crop((0, 0, src_w, crop_h)).convert("RGBA")
    # Fade the lower edge into the dark-red setting, removing a hard crop seam.
    fade_from = int(crop_h * 0.87)
    alpha = Image.new("L", (src_w, crop_h), 255)
    a = ImageDraw.Draw(alpha)
    if fade_from < crop_h:
        for y in range(fade_from, crop_h):
            strength = max(0, 255 - round((y - fade_from) * 255 / (crop_h - fade_from)))
            a.line(((0, y), (src_w, y)), fill=strength)
    emblem.putalpha(alpha)

    # Background is the same artwork softly defocused, not an unrelated photo.
    background = cover(source.convert("RGB"), width, height)
    background = ImageEnhance.Brightness(
        background.filter(ImageFilter.GaussianBlur(radius=max(16, round(width * .023))))
    ).enhance(.25)
    canvas = Image.new("RGBA", (width, height), (14, 0, 3, 255))
    canvas.alpha_composite(background.convert("RGBA"))
    shade = Image.new("RGBA", (width, height), (16, 0, 2, 90))
    canvas.alpha_composite(shade)

    # Keep the entire emblem in the safe center crop for messaging apps.
    scale = min((width * (.94 if icon else .84)) / src_w,
                (height * (.90 if icon else .93)) / crop_h)
    size = max(1, round(src_w * scale)), max(1, round(crop_h * scale))
    foreground = emblem.resize(size, Image.Resampling.LANCZOS)
    x = (width - size[0]) // 2
    y = (height - size[1]) // 2
    if not icon:
        y -= max(0, round(height * .018))
    canvas.alpha_composite(foreground, (x, y))
    return canvas.convert("RGB")


def build(root: Path):
    banner = root / BANNER
    if not banner.exists():
        raise FileNotFoundError(f"Missing source image: {banner}")
    src = Image.open(banner).convert("RGB")
    out = root / "branding"
    out.mkdir(parents=True, exist_ok=True)

    og = artwork(src, 1200, 630)
    og.save(out / "uno-luck-og-1200x630.jpg", format="JPEG",
            quality=83, optimize=True, progressive=True, subsampling=0)
    for size in (512, 192, 180, 48, 32):
        icon = artwork(src, size, size, icon=True)
        icon.save(out / f"uno-luck-icon-{size}.png", "PNG", optimize=True)
    for name, dims in [
        ("uno-luck-og-1200x630.jpg", (1200, 630)),
        ("uno-luck-icon-512.png", (512, 512)),
        ("uno-luck-icon-192.png", (192, 192)),
        ("uno-luck-icon-180.png", (180, 180)),
        ("uno-luck-icon-48.png", (48, 48)),
        ("uno-luck-icon-32.png", (32, 32)),
    ]:
        with Image.open(out / name) as img:
            assert img.size == dims
    print("UNO_LUCK_SOCIAL_ASSETS_READY: 1200x630 OG + 512/192/180/48/32 PWA/Apple icons")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "app" / "static")
    args = parser.parse_args()
    build(args.root)
