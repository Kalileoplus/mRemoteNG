"""
Genera icon.ico per PyMRemoteNG.
Design: hub di rete - nodo centrale bianco connesso a 4 nodi ciano su sfondo navy.
"""
from PIL import Image, ImageDraw, ImageFilter
import os, math

SIZES = [16, 24, 32, 48, 64, 128, 256]

BG       = (22,  27,  44,  255)   # navy scuro
CYAN     = (0,   210, 255, 255)   # ciano brillante
CYAN_DIM = (0,   150, 200, 170)   # ciano per le linee
WHITE    = (230, 240, 255, 255)   # bianco freddo


def draw_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # Sfondo arrotondato
    pad = max(1, size // 10)
    rad = max(3, size // 5)
    d.rounded_rectangle([pad, pad, size - pad - 1, size - pad - 1],
                        radius=rad, fill=BG)

    cx, cy  = size / 2.0, size / 2.0
    lw      = max(1, size // 20)
    nr      = max(2, size // 7)    # raggio nodo centrale
    sr      = max(1, size // 13)   # raggio nodi satelliti
    offset  = size * 0.29          # distanza nodi dal centro

    # Posizioni dei 4 nodi satelliti (rombo, non quadrato)
    angle_step = math.pi / 2
    start_angle = math.pi / 4      # 45 gradi -> rombo
    satellites = [
        (cx + offset * math.cos(start_angle + i * angle_step),
         cy + offset * math.sin(start_angle + i * angle_step))
        for i in range(4)
    ]

    # Linee di connessione (dietro ai nodi)
    for sx, sy in satellites:
        d.line([(cx, cy), (sx, sy)], fill=CYAN_DIM, width=lw)

    # Nodi satelliti (ciano, bordo bianco sottile)
    bw = max(1, lw // 2)
    for sx, sy in satellites:
        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr],
                  fill=CYAN, outline=WHITE, width=bw)

    # Nodo centrale (bianco, bordo ciano)
    d.ellipse([cx - nr, cy - nr, cx + nr, cy + nr],
              fill=WHITE, outline=CYAN, width=lw)

    # Alone sfumato sul nodo centrale (solo per size >= 64)
    if size >= 64:
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd   = ImageDraw.Draw(glow)
        gr   = int(nr * 1.8)
        gd.ellipse([cx - gr, cy - gr, cx + gr, cy + gr],
                   fill=(0, 210, 255, 60))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=nr * 0.6))
        img  = Image.alpha_composite(img, glow)

    return img


def main():
    frames = [draw_frame(s) for s in SIZES]
    out    = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "PyMRemoteNG", "icon.ico")
    frames[0].save(
        out,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    print(f"[OK] Icona salvata in: {out}")


if __name__ == "__main__":
    main()
