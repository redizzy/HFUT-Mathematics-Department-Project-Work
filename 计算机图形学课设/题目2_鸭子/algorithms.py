# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目一
基本图元的底层生成算法

实现：
1. Bresenham 直线生成算法
2. 中点画圆算法（含空心 / 实心两种）
3. 扫描线多边形填充算法
4. 星形多边形顶点生成

这些算法只返回像素点坐标，不依赖任何图形库，
由上层渲染器（pygame Surface）负责把像素写到屏幕。
"""

import math


# ---------------------------------------------------------------------------
# 1. Bresenham 直线算法
# ---------------------------------------------------------------------------
def bresenham_line(x0, y0, x1, y1):
    """Bresenham 直线生成算法

    通过整数运算逐步逼近理想直线，在每一步根据误差累积量
    决定 x 或 y 方向前进，避免浮点计算。

    参数：
        x0, y0: 起点
        x1, y1: 终点
    返回：
        [(x, y), ...] 直线上所有像素点
    """
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


# ---------------------------------------------------------------------------
# 2. 中点画圆算法（八对称性）
# ---------------------------------------------------------------------------
def midpoint_circle(cx, cy, r):
    """中点画圆算法（生成圆周像素）

    利用圆的八对称性，只需计算 1/8 圆弧（0~45°），
    通过中点判别式 d 决定下一像素位置。

    参数：
        cx, cy: 圆心
        r: 半径
    返回：
        [(x, y), ...] 圆周上所有像素点
    """
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


def midpoint_circle_fill(cx, cy, r):
    """实心圆填充（基于中点画圆 + 水平扫描）

    每一对镜像扫描线 (cy ± y) 之间填充水平直线，
    再叠加 (cy ± x) 一对，覆盖整个圆面。
    """
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


# ---------------------------------------------------------------------------
# 3. 扫描线多边形填充算法
# ---------------------------------------------------------------------------
def scanline_fill_polygon(vertices):
    """扫描线多边形填充算法

    对每一条扫描线 y：
      1) 求出它与所有非水平边的交点 x 坐标；
      2) 按 x 排序，成对取出 [x_i, x_{i+1}] 区段填充。
    端点处理约定：包含下端点(y0)，不含上端点(y1)，避免角点重复计入。

    参数：
        vertices: [(x, y), ...] 多边形顶点（按顺序，自动闭合）
    返回：
        [(x, y), ...] 多边形内部所有像素点
    """
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


# ---------------------------------------------------------------------------
# 4. 星形顶点生成（用于五角星等正多角星）
# ---------------------------------------------------------------------------
def star_vertices(cx, cy, r_outer, r_inner=None, num_points=5, rotation=0.0):
    """生成 n 角星顶点（外/内顶点交替）

    参数：
        cx, cy: 中心
        r_outer: 外接圆半径
        r_inner: 内接圆半径，默认 r_outer × 0.382（接近黄金分割）
        num_points: 角数
        rotation: 旋转弧度（顶点初始指向正上方）
    返回：
        [(x, y), ...] 2*num_points 个顶点（外、内交替）
    """
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
