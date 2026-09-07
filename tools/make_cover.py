"""Generate Eufisky hackathon cover images with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    (1920, 1080, ROOT / "docs" / "cover.png"),
    (1200, 630, ROOT / "docs" / "cover-1200x630.png"),
)

NIGHT = "#0B172A"
NAVY = "#172A46"
PAPER = "#F7F2E8"
ICE = "#D9E8F4"
BLUE = "#74B5E4"
GOLD = "#F2C763"


def font(size: int, *, display: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf"]
        if display
        else ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def gradient(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), NIGHT)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            glow = max(0.0, 1.0 - (((x - width * 0.13) / width) ** 2 + ((y - height * 0.2) / height) ** 2) ** 0.5 * 2.1)
            base = (11, 23, 42)
            lift = (19, 30, 46)
            pixels[x, y] = tuple(min(255, round(base[i] + lift[i] * glow)) for i in range(3))
    return image


def draw_shield(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int) -> None:
    cx, cy = center
    w = size
    h = round(size * 1.15)
    outer = [
        (cx, cy - h // 2),
        (cx + w // 2, cy - h // 3),
        (cx + w * 46 // 100, cy + h // 10),
        (cx + w * 34 // 100, cy + h * 34 // 100),
        (cx, cy + h // 2),
        (cx - w * 34 // 100, cy + h * 34 // 100),
        (cx - w * 46 // 100, cy + h // 10),
        (cx - w // 2, cy - h // 3),
    ]
    draw.polygon(outer, fill=GOLD)
    inset = round(w * 0.13)
    inner = [
        (cx, cy - h // 2 + inset),
        (cx + w // 2 - inset, cy - h // 3 + inset // 2),
        (cx + w * 38 // 100, cy + h // 12),
        (cx + w * 28 // 100, cy + h * 28 // 100),
        (cx, cy + h // 2 - inset),
        (cx - w * 28 // 100, cy + h * 28 // 100),
        (cx - w * 38 // 100, cy + h // 12),
        (cx - w // 2 + inset, cy - h // 3 + inset // 2),
    ]
    draw.polygon(inner, fill=NAVY)

    # A simple handset inside the shield.
    stroke = max(12, size // 18)
    points = [
        (cx - w * 0.22, cy - h * 0.15),
        (cx - w * 0.14, cy + h * 0.05),
        (cx + w * 0.02, cy + h * 0.18),
        (cx + w * 0.20, cy + h * 0.23),
    ]
    draw.line(points, fill=ICE, width=stroke, joint="curve")
    cap = stroke * 2
    draw.rounded_rectangle(
        (points[0][0] - cap // 2, points[0][1] - cap, points[0][0] + cap // 2, points[0][1] + cap // 2),
        radius=stroke,
        fill=ICE,
    )
    draw.rounded_rectangle(
        (points[-1][0] - cap // 2, points[-1][1] - cap // 2, points[-1][0] + cap // 2, points[-1][1] + cap),
        radius=stroke,
        fill=ICE,
    )


def make_cover(width: int, height: int, destination: Path) -> None:
    image = gradient(width, height)
    draw = ImageDraw.Draw(image)
    scale = width / 1920

    # Phone-line motif.
    line_y = round(height * 0.84)
    draw.line((0, line_y, width, line_y), fill="#27415F", width=max(2, round(3 * scale)))
    pulse = [
        (round(width * 0.70), line_y),
        (round(width * 0.75), line_y),
        (round(width * 0.765), line_y - round(50 * scale)),
        (round(width * 0.785), line_y + round(62 * scale)),
        (round(width * 0.805), line_y - round(42 * scale)),
        (round(width * 0.825), line_y),
        (width, line_y),
    ]
    draw.line(pulse, fill=GOLD, width=max(4, round(7 * scale)), joint="curve")

    draw_shield(draw, (round(width * 0.25), round(height * 0.48)), round(410 * scale))

    x = round(width * 0.45)
    title_font = font(round(168 * scale), display=True)
    subtitle_font = font(round(49 * scale), display=True)
    badge_font = font(round(25 * scale))
    draw.text((x, round(height * 0.28)), "Eufisky", font=title_font, fill=PAPER, anchor="lm")
    draw.multiline_text(
        (x, round(height * 0.55)),
        "A voice agent that guards\nMom's phone line",
        font=subtitle_font,
        fill=ICE,
        spacing=round(12 * scale),
        anchor="lm",
    )
    badge = "Built on AssemblyAI"
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    pad_x, pad_y = round(25 * scale), round(15 * scale)
    badge_box = (
        x,
        round(height * 0.71),
        x + bbox[2] - bbox[0] + pad_x * 2,
        round(height * 0.71) + bbox[3] - bbox[1] + pad_y * 2,
    )
    draw.rounded_rectangle(badge_box, radius=100, fill=GOLD)
    draw.text(
        (badge_box[0] + pad_x, badge_box[1] + pad_y),
        badge,
        font=badge_font,
        fill=NIGHT,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    print(f"wrote {destination} ({width}x{height})")


if __name__ == "__main__":
    for output_width, output_height, output_path in OUTPUTS:
        make_cover(output_width, output_height, output_path)
