"""Генератор спільної іконки застосунку LogTracker.

Малює один дизайн («жук» в акцентному синьому на прозорому) і зберігає його
у двох форматах у `src/`:
    src/app_icon.png  — 256×256 RGBA майстер (шапка вікна + трей; вони самі
                        зменшують його під DPI, тож джерело високороздільне);
    src/app_icon.ico  — мультирозмірний (16…256) для iconbitmap і .exe
                        (Windows бере потрібний розмір під DPI).

Це НЕ рантайм-код застосунку — запускати вручну, коли треба перемалювати
іконку. Малюється з 8× супер-семплом і зменшується LANCZOS, тож кожен розмір
лишається чітким.

    python tools/generate_app_icon.py
"""
import os

from PIL import Image, ImageDraw

# ---- палітра -------------------------------------------------------------
MAIN = (95, 141, 252, 255)    # #5f8dfc  акцентний синій
DARK = (45, 67, 110, 255)     # #2d436e  шов / деталізація
LIGHT = (183, 205, 255, 255)  # світліший синій — плямки на спинці

SS = 8      # супер-семплінг
L = 256     # логічний розмір іконки
C = L * SS  # розмір полотна малювання

ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def render():
    """Малює жука на супер-семпльованому полотні (C×C) і повертає його."""
    img = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def s(v):
        return v * SS

    def ellipse(cx, cy, rx, ry, fill):
        d.ellipse([s(cx - rx), s(cy - ry), s(cx + rx), s(cy + ry)], fill=fill)

    def stroke(pts, width, fill):
        p = [(s(x), s(y)) for x, y in pts]
        d.line(p, fill=fill, width=int(s(width)), joint="curve")
        r = s(width) / 2
        for (x, y) in (p[0], p[-1]):  # круглі кінці
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def dot(cx, cy, r, fill):
        ellipse(cx, cy, r, r, fill)

    cx = 128
    body_cy, body_rx, body_ry = 150, 56, 80

    # ноги (малюємо першими, тіло їх перекриває всередині)
    leg_w = 11
    for ay, mdy, fdx, fdy in [(108, -18, 62, -34), (150, 0, 66, 4), (192, 18, 60, 40)]:
        stroke([(cx - body_rx + 6, ay), (cx - body_rx - 20, ay + mdy),
                (cx - body_rx - fdx + 8, ay + fdy)], leg_w, MAIN)
        stroke([(cx + body_rx - 6, ay), (cx + body_rx + 20, ay + mdy),
                (cx + body_rx + fdx - 8, ay + fdy)], leg_w, MAIN)

    # вусики
    stroke([(cx - 12, 60), (cx - 30, 34), (cx - 30, 16)], 8, MAIN)
    stroke([(cx + 12, 60), (cx + 30, 34), (cx + 30, 16)], 8, MAIN)
    dot(cx - 30, 13, 8, MAIN)
    dot(cx + 30, 13, 8, MAIN)

    ellipse(cx, 66, 27, 23, MAIN)                 # голова
    ellipse(cx, body_cy, body_rx, body_ry, MAIN)  # надкрила
    ellipse(cx, 92, 40, 24, MAIN)                 # передньоспинка

    # деталізація спинки
    stroke([(cx, 82), (cx, body_cy + body_ry - 12)], 7, DARK)   # центральний шов
    d.arc([s(cx - 40), s(74), s(cx + 40), s(118)], start=20, end=160,
          fill=DARK, width=int(s(6)))
    for sx, sy in [(-26, 132), (26, 132), (-30, 178), (30, 178), (0, 205)]:
        dot(cx + sx, sy, 9, LIGHT)

    return img


def main():
    big = render()

    png_path = os.path.join(SRC, "app_icon.png")
    big.resize((L, L), Image.LANCZOS).save(png_path)
    print("wrote", png_path)

    # Кожен кадр — окреме LANCZOS-зменшення з супер-семплу (чіткіше, ніж дати
    # ICO-кодеру зменшувати 256-майстер). PIL складе стандартний .ico.
    frames = [big.resize((n, n), Image.LANCZOS) for n in ICO_SIZES]
    ico_path = os.path.join(SRC, "app_icon.ico")
    frames[-1].save(ico_path, format="ICO", sizes=[(n, n) for n in ICO_SIZES],
                    append_images=frames[:-1])
    print("wrote", ico_path, "sizes", ICO_SIZES)


if __name__ == "__main__":
    main()
