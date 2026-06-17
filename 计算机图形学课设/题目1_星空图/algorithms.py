
import math

# 1. Bresenham 直线算法
def bresenham_line(x0, y0, x1, y1):
    points = []
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points



# 2. 中点画圆算法（八对称性）
def midpoint_circle(cx, cy, r):
    points = []
    cx, cy, r = int(cx), int(cy), int(r)
    if r <= 0:
        return [(cx, cy)]

    x, y = 0, r
    d = 1 - r  # 中点判别式初值
    while x <= y:
        # 八对称点
        points.extend([
            (cx + x, cy + y), (cx - x, cy + y),
            (cx + x, cy - y), (cx - x, cy - y),
            (cx + y, cy + x), (cx - y, cy + x),
            (cx + y, cy - x), (cx - y, cy - x),
        ])
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1
    return points

# 实心圆填充
def midpoint_circle_fill(cx, cy, r):

    points = []
    cx, cy, r = int(cx), int(cy), int(r)
    if r <= 0:
        return [(cx, cy)]

    x, y = 0, r
    d = 1 - r
    seen = set()

    def hline(x_left, x_right, yy):
        for xi in range(x_left, x_right + 1):
            key = (xi, yy)
            if key not in seen:
                seen.add(key)
                points.append(key)

    while x <= y:
        # 上下两对水平线（高的一对 y=±y，低的一对 y=±x）
        hline(cx - y, cx + y, cy + x)
        hline(cx - y, cx + y, cy - x)
        hline(cx - x, cx + x, cy + y)
        hline(cx - x, cx + x, cy - y)
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1
    return points

# 3. 扫描线多边形填充算法
def scanline_fill_polygon(vertices):

    if len(vertices) < 3:
        return []

    points = []
    ys = [int(v[1]) for v in vertices]
    ymin, ymax = min(ys), max(ys)
    n = len(vertices)

    for y in range(ymin, ymax + 1):
        xs = []
        for i in range(n):
            x0, y0 = vertices[i]
            x1, y1 = vertices[(i + 1) % n]
            # 跳过水平边
            if y0 == y1:
                continue
            # 保证 y0 < y1
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            # 端点处理约定：[y0, y1)
            if y0 <= y < y1:
                # 线性插值求交点 x
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))

        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            x_start = int(round(xs[i]))
            x_end = int(round(xs[i + 1]))
            for xx in range(x_start, x_end + 1):
                points.append((xx, y))
    return points


# 4. 星形顶点生成
def star_vertices(cx, cy, r_outer, r_inner=None, num_points=5, rotation=0.0):

    if r_inner is None:
        r_inner = r_outer * 0.382
    verts = []
    for i in range(num_points * 2):
        # i=0 时指向正上方（-π/2）
        ang = rotation + i * math.pi / num_points - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        verts.append((int(round(x)), int(round(y))))
    return verts
