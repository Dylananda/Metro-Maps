"""Dibuja los iconos PNG de la app (sin dependencias): fondo oscuro, una «M» blanca y una barra verde de salida."""
import math, struct, zlib

INK = (24, 34, 44)
WHITE = (255, 255, 255)
GREEN = (10, 107, 75)

# Trazo de la «M» en una caja de 100×100 y su grosor
M = [(30, 68), (30, 34), (50, 54), (70, 34), (70, 68)]
STROKE = 9.0
BAR = (30, 76, 70, 82)  # x0, y0, x1, y1

def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def color_at(x, y, scale):
    # x, y en la caja 0..100; scale < 1 encoge el dibujo hacia el centro (iconos «maskable»)
    u = 50 + (x - 50) / scale
    v = 50 + (y - 50) / scale
    if min(seg_dist(u, v, *M[i], *M[i + 1]) for i in range(len(M) - 1)) <= STROKE / 2:
        return WHITE
    if BAR[0] <= u <= BAR[2] and BAR[1] <= v <= BAR[3]:
        return GREEN
    return INK

def png(path, size, scale=1.0, ss=3):
    rows = []
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            acc = [0, 0, 0]
            for a in range(ss):
                for b in range(ss):
                    c = color_at((i + (a + .5) / ss) * 100 / size, (j + (b + .5) / ss) * 100 / size, scale)
                    acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]
            row += bytes(v // (ss * ss) for v in acc)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    open(path, "wb").write(data)

if __name__ == "__main__":
    import os
    os.makedirs("docs/icons", exist_ok=True)
    png("docs/icons/icon-192.png", 192)
    png("docs/icons/icon-512.png", 512, ss=2)
    png("docs/icons/maskable-512.png", 512, scale=0.78, ss=2)
    png("docs/icons/apple-180.png", 180)
    print("iconos listos")
