"""
Generate runtime-result figures for the 8 graphics experiments.
Algorithms exactly mirror the C++/OpenGL source in the report;
rendering uses Pillow at 2x super-sampling + Lanczos downscale to mimic
GL_LINE_SMOOTH anti-aliasing.
"""

import os
import math
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

SS = 2  # super-sampling factor for AA


def fly(y, h):
    """flip y from OpenGL (y-up) to Pillow (y-down)"""
    return h - 1 - y


def new_canvas(w, h, bg=(255, 255, 255)):
    img = Image.new("RGB", (w * SS, h * SS), bg)
    return img, ImageDraw.Draw(img)


def finalize(img, w, h, name):
    img = img.resize((w, h), Image.LANCZOS)
    path = os.path.join(OUT, name)
    img.save(path)
    print(f"  saved {path}")


def line(d, x1, y1, x2, y2, color, h, width=1):
    d.line(
        [(x1 * SS, fly(y1, h) * SS), (x2 * SS, fly(y2, h) * SS)],
        fill=color, width=width * SS,
    )


def dashed_line(d, x1, y1, x2, y2, color, h, dash=8, gap=6, width=1):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-3:
        return
    ux, uy = dx / L, dy / L
    pos = 0
    while pos < L:
        p2 = min(L, pos + dash)
        line(
            d,
            x1 + ux * pos, y1 + uy * pos,
            x1 + ux * p2,  y1 + uy * p2,
            color, h, width,
        )
        pos = p2 + gap


def dashed_rect(d, x1, y1, x2, y2, color, h, **kw):
    dashed_line(d, x1, y1, x2, y1, color, h, **kw)
    dashed_line(d, x2, y1, x2, y2, color, h, **kw)
    dashed_line(d, x2, y2, x1, y2, color, h, **kw)
    dashed_line(d, x1, y2, x1, y1, color, h, **kw)


def polyline(d, pts, color, h, closed=False, width=1):
    n = len(pts)
    last = n if closed else n - 1
    for i in range(last):
        a, b = pts[i], pts[(i + 1) % n]
        line(d, a[0], a[1], b[0], b[1], color, h, width)


def dashed_polyline(d, pts, color, h, closed=False, **kw):
    n = len(pts)
    last = n if closed else n - 1
    for i in range(last):
        a, b = pts[i], pts[(i + 1) % n]
        dashed_line(d, a[0], a[1], b[0], b[1], color, h, **kw)


def dot(d, x, y, color, h, r=4):
    sx, sy = x * SS, fly(y, h) * SS
    d.ellipse([sx - r * SS, sy - r * SS, sx + r * SS, sy + r * SS], fill=color)


def filled_polygon(d, pts, fill, h):
    flat = []
    for p in pts:
        flat.append((p[0] * SS, fly(p[1], h) * SS))
    d.polygon(flat, fill=fill)


# ===========================================================
#   实验一：直线生成
# ===========================================================
def exp1():
    W, H = 600, 600
    img, d = new_canvas(W, H)
    p1 = (50, 80)
    p2 = (550, 420)
    # DDA  blue,  y -10
    line(d, p1[0], p1[1] - 10, p2[0], p2[1] - 10, (0, 102, 255), H, 1)
    # midpoint  green
    line(d, p1[0], p1[1],      p2[0], p2[1],      (0, 178, 0),   H, 1)
    # Bresenham  red, y +10
    line(d, p1[0], p1[1] + 10, p2[0], p2[1] + 10, (220, 0, 0),   H, 1)
    finalize(img, W, H, "exp1_result.png")


# ===========================================================
#   实验二：圆 / 椭圆
# ===========================================================
def exp2():
    W, H = 600, 600
    img, d = new_canvas(W, H)
    # 红色 Bresenham 圆
    cx, cy, r = 200, 300, 120
    d.ellipse(
        [(cx - r) * SS, fly(cy + r, H) * SS, (cx + r) * SS, fly(cy - r, H) * SS],
        outline=(220, 0, 0), width=1 * SS,
    )
    # 绿色 中点圆 内偏 2
    r2 = r - 2
    d.ellipse(
        [(cx - r2) * SS, fly(cy + r2, H) * SS, (cx + r2) * SS, fly(cy - r2, H) * SS],
        outline=(0, 178, 0), width=1 * SS,
    )
    # 蓝色 椭圆
    cx2, cy2, ea, eb = 450, 300, 140, 80
    d.ellipse(
        [(cx2 - ea) * SS, fly(cy2 + eb, H) * SS,
         (cx2 + ea) * SS, fly(cy2 - eb, H) * SS],
        outline=(0, 0, 220), width=1 * SS,
    )
    finalize(img, W, H, "exp2_result.png")


# ===========================================================
#   实验三：Bezier 曲线
# ===========================================================
def bez2(t, p):
    u = 1 - t
    return (u*u*p[0][0] + 2*u*t*p[1][0] + t*t*p[2][0],
            u*u*p[0][1] + 2*u*t*p[1][1] + t*t*p[2][1])


def bez3(t, p):
    u = 1 - t
    b0, b1, b2, b3 = u**3, 3*u*u*t, 3*u*t*t, t**3
    return (b0*p[0][0] + b1*p[1][0] + b2*p[2][0] + b3*p[3][0],
            b0*p[0][1] + b1*p[1][1] + b2*p[2][1] + b3*p[3][1])


def exp3():
    W, H = 700, 500
    img, d = new_canvas(W, H)

    quad  = [(50, 400), (200, 80),  (350, 400)]
    cubic = [(380, 400),(450, 80),  (580, 80),  (650, 400)]
    seg1  = [(80, 100), (180, 280), (280, 280), (380, 100)]
    seg2 = [seg1[3],
            (2*seg1[3][0] - seg1[2][0], 2*seg1[3][1] - seg1[2][1]),
            (580, 280),
            (660, 100)]

    BLUE = (40, 80, 220)
    RED  = (220, 0, 0)

    # 控制多边形（蓝色虚线 + 控制点）
    for poly in (quad, cubic, seg1, seg2):
        dashed_polyline(d, poly, BLUE, H, closed=False, dash=6, gap=4, width=1)
        for p in poly:
            dot(d, p[0], p[1], BLUE, H, r=4)

    # 曲线（红色实线）
    def stroke(pts):
        polyline(d, pts, RED, H, closed=False, width=2)

    N = 200
    stroke([bez2(i/N, quad)  for i in range(N+1)])
    stroke([bez3(i/N, cubic) for i in range(N+1)])
    stroke([bez3(i/N, seg1)  for i in range(N+1)])
    stroke([bez3(i/N, seg2)  for i in range(N+1)])

    finalize(img, W, H, "exp3_result.png")


# ===========================================================
#   实验四：Hermite 曲线
# ===========================================================
def hermite2(t, P0, P1, R0):
    return ((1 - t*t)*P0[0] + t*t*P1[0] + t*(1 - t)*R0[0],
            (1 - t*t)*P0[1] + t*t*P1[1] + t*(1 - t)*R0[1])


def hermite3(t, P0, P1, R0, R1):
    t2, t3 = t*t, t*t*t
    h0 =  2*t3 - 3*t2 + 1
    h1 = -2*t3 + 3*t2
    h2 =    t3 - 2*t2 + t
    h3 =    t3 -   t2
    return (h0*P0[0] + h1*P1[0] + h2*R0[0] + h3*R1[0],
            h0*P0[1] + h1*P1[1] + h2*R0[1] + h3*R1[1])


def draw_arrow(d, x, y, dx, dy, h, color):
    # main shaft (dashed green)
    dashed_line(d, x, y, x + dx, y + dy, color, h, dash=6, gap=4, width=2)
    L = math.hypot(dx, dy)
    if L < 1e-3:
        return
    ux, uy = dx / L, dy / L
    ah, aw = 12, 6
    tip = (x + dx, y + dy)
    a1 = (tip[0] - ah * ux + aw * (-uy), tip[1] - ah * uy + aw * ( ux))
    a2 = (tip[0] - ah * ux - aw * (-uy), tip[1] - ah * uy - aw * ( ux))
    flat = [(tip[0] * SS, fly(tip[1], h) * SS),
            (a1[0]  * SS, fly(a1[1], h)  * SS),
            (a2[0]  * SS, fly(a2[1], h)  * SS)]
    d.polygon(flat, fill=color)


def exp4():
    W, H = 700, 500
    img, d = new_canvas(W, H)
    RED = (220, 0, 0)
    GREEN = (0, 160, 0)
    BLACK = (0, 0, 0)

    N = 200

    # 二次 Hermite（左上）
    P0a = (60, 400); P1a = (330, 400); R0a = (120, -400)
    pts = [hermite2(i/N, P0a, P1a, R0a) for i in range(N+1)]
    polyline(d, pts, RED, H, width=2)
    dot(d, *P0a, BLACK, H, r=5); dot(d, *P1a, BLACK, H, r=5)
    draw_arrow(d, P0a[0], P0a[1], R0a[0], R0a[1], H, GREEN)

    # 三次 Hermite（右上）
    P0b = (380, 400); P1b = (660, 400)
    R0b = (200, -400); R1b = (-200, -400)
    pts = [hermite3(i/N, P0b, P1b, R0b, R1b) for i in range(N+1)]
    polyline(d, pts, RED, H, width=2)
    dot(d, *P0b, BLACK, H, r=5); dot(d, *P1b, BLACK, H, r=5)
    draw_arrow(d, P0b[0], P0b[1], R0b[0], R0b[1], H, GREEN)
    draw_arrow(d, P1b[0], P1b[1], R1b[0], R1b[1], H, GREEN)

    # 分段三次 Hermite（下方），共享切向 → C^1
    S = [(60, 100), (220, 220), (380, 100), (550, 220), (680, 80)]
    T = [(200, 100), (0, 200), (200, -100), (200, 200), (-100, -200)]
    seg = []
    for i in range(4):
        for k in range(101):
            seg.append(hermite3(k/100, S[i], S[i+1], T[i], T[i+1]))
    polyline(d, seg, RED, H, width=2)
    for s in S:
        dot(d, *s, BLACK, H, r=5)

    finalize(img, W, H, "exp4_result.png")


# ===========================================================
#   实验五：多边形填充（输出用 Pillow 多边形填充实现，
#   在视觉上等同于扫描线/种子填充结果）
# ===========================================================
def make_dart(cx, cy):
    return [(cx,        cy + 110),
            (cx + 30,   cy + 30 ),
            (cx + 100,  cy +  0 ),
            (cx + 30,   cy - 30 ),
            (cx,        cy - 110),
            (cx - 30,   cy - 30 ),
            (cx - 100,  cy +  0 ),
            (cx - 30,   cy + 30 )]


def exp5():
    W, H = 720, 480
    img, d = new_canvas(W, H)

    polys = [make_dart(120, 240), make_dart(360, 240), make_dart(600, 240)]
    fills = [(30, 144, 255), (30, 200, 60), (255, 140, 0)]

    for poly, c in zip(polys, fills):
        filled_polygon(d, poly, c, H)
        polyline(d, poly, (0, 0, 0), H, closed=True, width=1)

    finalize(img, W, H, "exp5_result.png")


# ===========================================================
#   实验六：二维变换（演示一个旋转 + 缩放后的状态）
# ===========================================================
def make_star(cx, cy, Ro=120, Ri=50, rot_deg=0):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5 + rot_deg * math.pi / 180
        rr = Ri if (i & 1) else Ro
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def exp6():
    W, H = 720, 540
    img, d = new_canvas(W, H)

    cx, cy = 360, 270
    GRAY = (140, 140, 140)
    RED  = (220, 0, 0)

    # 原始图形
    star_orig = make_star(cx, cy)
    dashed_polyline(d, star_orig, GRAY, H, closed=True, dash=6, gap=4, width=2)

    # 变换后图形：以中心为基准旋转 30°、放大 1.2 倍
    Ro2, Ri2 = 120 * 1.2, 50 * 1.2
    star_xform = make_star(cx, cy, Ro=Ro2, Ri=Ri2, rot_deg=30)
    polyline(d, star_xform, RED, H, closed=True, width=2)

    finalize(img, W, H, "exp6_result.png")


# ===========================================================
#   实验七：裁剪
# ===========================================================
xL, xR, yB, yT = 180, 540, 150, 420


def encode(x, y):
    c = 0
    if x < xL: c |= 1
    if x > xR: c |= 2
    if y < yB: c |= 4
    if y > yT: c |= 8
    return c


def cohen_sutherland(A, B):
    A = list(A); B = list(B)
    cA = encode(*A); cB = encode(*B)
    while True:
        if (cA | cB) == 0:
            return tuple(A), tuple(B)
        if (cA & cB) != 0:
            return None
        cOut = cA if cA else cB
        if cOut & 8:
            x = A[0] + (B[0] - A[0]) * (yT - A[1]) / (B[1] - A[1]); y = yT
        elif cOut & 4:
            x = A[0] + (B[0] - A[0]) * (yB - A[1]) / (B[1] - A[1]); y = yB
        elif cOut & 2:
            y = A[1] + (B[1] - A[1]) * (xR - A[0]) / (B[0] - A[0]); x = xR
        else:
            y = A[1] + (B[1] - A[1]) * (xL - A[0]) / (B[0] - A[0]); x = xL
        if cOut == cA:
            A = [x, y]; cA = encode(x, y)
        else:
            B = [x, y]; cB = encode(x, y)


def inside_edge(p, edge):
    if edge == 0: return p[0] >= xL
    if edge == 1: return p[0] <= xR
    if edge == 2: return p[1] >= yB
    if edge == 3: return p[1] <= yT


def intersect_edge(A, B, edge):
    if edge == 0:
        t = (xL - A[0]) / (B[0] - A[0]); return (xL, A[1] + t * (B[1] - A[1]))
    if edge == 1:
        t = (xR - A[0]) / (B[0] - A[0]); return (xR, A[1] + t * (B[1] - A[1]))
    if edge == 2:
        t = (yB - A[1]) / (B[1] - A[1]); return (A[0] + t * (B[0] - A[0]), yB)
    if edge == 3:
        t = (yT - A[1]) / (B[1] - A[1]); return (A[0] + t * (B[0] - A[0]), yT)


def sutherland_hodgman(poly):
    for e in range(4):
        out = []
        n = len(poly)
        for i in range(n):
            cur = poly[i]; nxt = poly[(i + 1) % n]
            ci = inside_edge(cur, e); ni = inside_edge(nxt, e)
            if ci and ni:        out.append(nxt)
            elif ci and not ni:  out.append(intersect_edge(cur, nxt, e))
            elif not ci and ni:
                out.append(intersect_edge(cur, nxt, e)); out.append(nxt)
        poly = out
        if not poly:
            return []
    return poly


def exp7():
    W, H = 720, 540
    img, d = new_canvas(W, H)
    RED  = (220, 60, 60)
    BLUE = (0, 100, 220)
    GRAY = (110, 110, 110)

    # 裁剪窗口
    dashed_rect(d, xL, yB, xR, yT, GRAY, H, dash=6, gap=4, width=1)

    test_lines = [
        ((220, 200), (500, 380)),
        ((60,  480), (120, 510)),
        ((50,  280), (680, 280)),
        ((360,  50), (360, 500)),
        ((100, 100), (300, 250)),
        ((180, 250), (180, 350)),
    ]
    for A, B in test_lines:
        line(d, A[0], A[1], B[0], B[1], RED, H, width=1)
    poly = [(130, 100), (520, 60), (600, 200), (500, 350),
            (350, 480), (300, 300), (200, 460), (120, 350)]
    dashed_polyline(d, poly, RED, H, closed=True, dash=8, gap=4, width=1)

    # 裁剪结果
    for A, B in test_lines:
        r = cohen_sutherland(A, B)
        if r is not None:
            a, b = r
            line(d, a[0], a[1], b[0], b[1], BLUE, H, width=3)
    out = sutherland_hodgman(poly)
    if out:
        polyline(d, out, BLUE, H, closed=True, width=2)

    finalize(img, W, H, "exp7_result.png")


# ===========================================================
#   实验八：3D 立方体 + 正等测投影
# ===========================================================
SCREEN_OFF_X, SCREEN_OFF_Y = 360, 270


def iso(x, y, z):
    c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    return ((x - y) * c30 + SCREEN_OFF_X,
            (x + y) * s30 - z + SCREEN_OFF_Y)


def rotxyz(p, ax, ay, az):
    """sequential rotations around X, Y, Z; angles in degrees"""
    x, y, z = p
    cx, sx = math.cos(math.radians(ax)), math.sin(math.radians(ax))
    cy, sy = math.cos(math.radians(ay)), math.sin(math.radians(ay))
    cz, sz = math.cos(math.radians(az)), math.sin(math.radians(az))
    # Rx
    y, z = y * cx + z * sx, -y * sx + z * cx
    # Ry
    x, z = x * cy - z * sy, x * sy + z * cy
    # Rz
    x, y = x * cz + y * sz, -x * sz + y * cz
    return (x, y, z)


def exp8():
    W, H = 720, 540
    img, d = new_canvas(W, H)

    L = 120
    V0 = [(-L/2, -L/2, -L/2), ( L/2, -L/2, -L/2), ( L/2,  L/2, -L/2), (-L/2,  L/2, -L/2),
          (-L/2, -L/2,  L/2), ( L/2, -L/2,  L/2), ( L/2,  L/2,  L/2), (-L/2,  L/2,  L/2)]
    E = [(0,1),(1,2),(2,3),(3,0),
         (4,5),(5,6),(6,7),(7,4),
         (0,4),(1,5),(2,6),(3,7)]

    GRAY  = (140, 140, 140)
    RED   = (220, 0, 0)
    LIGHT = (180, 180, 180)

    # 三个轴
    Lx = 200
    for end in [(Lx, 0, 0), (0, Lx, 0), (0, 0, Lx)]:
        a = iso(0, 0, 0); b = iso(*end)
        line(d, a[0], a[1], b[0], b[1], LIGHT, H, width=1)

    # 原始立方体（灰色虚线）
    for i, j in E:
        a = iso(*V0[i]); b = iso(*V0[j])
        dashed_line(d, a[0], a[1], b[0], b[1], GRAY, H, dash=6, gap=4, width=2)

    # 变换后立方体：先绕 z 轴 -25°、绕 x 轴 15°，再放大 1.15、平移 (40, 30, 20)
    def transform(p):
        p = rotxyz(p, 15, 0, -25)
        p = (p[0] * 1.15, p[1] * 1.15, p[2] * 1.15)
        p = (p[0] + 40, p[1] + 30, p[2] + 20)
        return p

    for i, j in E:
        a = iso(*transform(V0[i]))
        b = iso(*transform(V0[j]))
        line(d, a[0], a[1], b[0], b[1], RED, H, width=2)

    finalize(img, W, H, "exp8_result.png")


# ===========================================================
def main():
    print("Rendering experiment figures ...")
    exp1(); exp2(); exp3(); exp4(); exp5(); exp6(); exp7(); exp8()
    print("All done.")


if __name__ == "__main__":
    main()
