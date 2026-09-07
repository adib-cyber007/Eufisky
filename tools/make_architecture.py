"""Generate the README architecture diagram with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "architecture.png"
WIDTH, HEIGHT = 1600, 900
NIGHT = "#0B172A"
NAVY = "#172A46"
NAVY_2 = "#21385B"
PAPER = "#F7F2E8"
ICE = "#D9E8F4"
MUTED = "#A9B8CA"
BLUE = "#74B5E4"
GOLD = "#F2C763"
CORAL = "#F0795C"
MINT = "#8BD5B2"


def font(size: int, *, bold: bool = False, display: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if display:
        candidates = ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf"]
    elif bold:
        candidates = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    else:
        candidates = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, size: int, color: str, *, bold: bool = False) -> None:
    draw.multiline_text(
        ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
        text,
        fill=color,
        font=font(size, bold=bold),
        anchor="mm",
        align="center",
        spacing=6,
    )


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, body: str, accent: str) -> None:
    draw.rounded_rectangle(box, radius=20, fill=NAVY, outline="#385171", width=2)
    draw.rounded_rectangle((box[0], box[1], box[2], box[1] + 10), radius=10, fill=accent)
    draw.text((box[0] + 24, box[1] + 30), title, fill=PAPER, font=font(28, bold=True))
    draw.multiline_text(
        (box[0] + 24, box[1] + 78),
        body,
        fill=ICE,
        font=font(20),
        spacing=8,
    )


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = GOLD) -> None:
    draw.line((*start, *end), fill=color, width=5)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 16, ey - 10), (ex - 16, ey + 10)], fill=color)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), NIGHT)
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), "How Eufisky protects a call", fill=PAPER, font=font(58, display=True))
    draw.text((73, 122), "Trusted callers stay private. Unknown callers enter an explainable safety path.", fill=MUTED, font=font(24))

    phone_boxes = [
        (70, 235, 300, 345, "Caller"),
        (70, 380, 300, 490, "Margaret"),
        (70, 525, 300, 635, "Sarah"),
    ]
    for x1, y1, x2, y2, label in phone_boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=NAVY_2, outline=BLUE, width=2)
        centered_text(draw, (x1, y1, x2, y2), f"{label}\nbrowser phone", 23, PAPER, bold=True)

    draw.line((300, 290, 360, 290), fill=BLUE, width=4)
    draw.line((300, 435, 360, 435), fill=BLUE, width=4)
    draw.line((300, 580, 360, 580), fill=BLUE, width=4)
    draw.line((360, 290, 360, 580), fill=BLUE, width=4)
    arrow(draw, (360, 435), (420, 435), BLUE)
    draw.text((315, 654), "Secure WebSockets\nJSON + PCM16 audio", fill=MUTED, font=font(18), anchor="ma", align="center")

    router = (420, 300, 700, 570)
    card(draw, router, "FastAPI call router", "Caller-ID routing\nAudio bridge + hold\nRoom isolation\nExplicit tool actions", BLUE)

    trusted_box = (810, 185, 1160, 300)
    draw.rounded_rectangle(trusted_box, radius=18, fill="#16372F", outline=MINT, width=3)
    centered_text(draw, trusted_box, "Trusted contact\nPrivate bridge · no AI", 23, PAPER, bold=True)
    draw.line((700, 350, 760, 245), fill=MINT, width=4)
    arrow(draw, (760, 245), (810, 245), MINT)

    front = (810, 350, 1160, 485)
    card(draw, front, "Front Door voice agent", "Screens unknown callers\nconnect · message · decline", CORAL)
    arrow(draw, (700, 435), (810, 435), CORAL)

    streams = (810, 535, 1160, 705)
    card(draw, streams, "AssemblyAI Streaming", "Caller leg       Senior leg\nKeyterm-boosted transcript\nDeterministic speaker labels", BLUE)
    draw.line((985, 485, 985, 535), fill=BLUE, width=4)
    draw.polygon([(985, 535), (975, 518), (995, 518)], fill=BLUE)

    risk = (1245, 405, 1530, 620)
    card(draw, risk, "Risk + Guardian", "Decaying evidence score\n40: private nudge\n65: caller held\n90: family recommended", GOLD)
    arrow(draw, (1160, 620), (1245, 520), GOLD)

    post = (810, 755, 1530, 845)
    draw.rounded_rectangle(post, radius=18, fill=NAVY_2, outline=CORAL, width=2)
    centered_text(
        draw,
        post,
        "Post-call: batch PII redaction  →  incident summary\n→  Family Dashboard",
        21,
        PAPER,
        bold=True,
    )
    draw.line((1385, 620, 1385, 755), fill=CORAL, width=4)
    draw.polygon([(1385, 755), (1375, 738), (1395, 738)], fill=CORAL)

    draw.text((70, 794), "Privacy boundary", fill=GOLD, font=font(20, bold=True))
    draw.text((70, 827), "Raw recordings are deleted after post-call processing.\nRender demo storage is temporary.", fill=MUTED, font=font(17), spacing=5)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, format="PNG", optimize=True)
    print(f"wrote {OUTPUT} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
