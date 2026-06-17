# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目二
鸭子模型

鸭子由若干部件构成，每个部件在\textit{局部坐标系}中定义：
   原点在身体中心，鸭子朝向 +x 方向，y 向下（pygame 习惯）。

部件类型：
  · 多边形（body / belly / wing / tail / beak）—— 顶点列表
  · 圆（head / eye_white / pupil）—— 中心 + 半径

渲染时，调用者传入 3×3 变换矩阵 M：
  · 多边形：所有顶点先经 M 变换，再 scanline 填充；
  · 圆：圆心经 M 变换，半径乘以 M 的均匀尺度因子（再用中点画圆填充）；
    这样圆在旋转下保持为圆，在均匀缩放下半径同步缩放。
"""

import math
from algorithms import (
    scanline_fill_polygon,
    midpoint_circle,
    midpoint_circle_fill,
    bresenham_line,
)
from transforms import apply_point, apply_points


# ---------- 颜色 ----------
COLOR_BODY     = (250, 211, 70)
COLOR_BELLY    = (255, 235, 150)
COLOR_WING     = (220, 178, 45)
COLOR_HEAD     = (250, 211, 70)
COLOR_BEAK     = (240, 134, 48)
COLOR_BEAK_DK  = (200, 100, 30)
COLOR_EYE      = (255, 255, 255)
COLOR_PUPIL    = (25, 25, 30)
COLOR_OUTLINE  = (90, 60, 20)
COLOR_CHEEK    = (255, 170, 170)   # 腮红


# ---------- 工具：椭圆 → 多边形 ----------
def ellipse_polygon(cx, cy, a, b, n=40):
    """把椭圆离散成 n 个顶点"""
    return [
        (cx + a * math.cos(2 * math.pi * i / n),
         cy + b * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


# ---------- 工具：从变换矩阵提取均匀尺度 ----------
def uniform_scale_of(M):
    """假定 M 由 T·R·S 组成（无切变），均匀尺度 = 第一列向量的模"""
    return math.hypot(M[0][0], M[1][0])


class Duck:
    """鸭子模型——所有部件几何定义在局部坐标系中"""

    def __init__(self):
        # 身体：椭圆
        self.body = ellipse_polygon(0, 0, 95, 58, n=42)

        # 腹部（更亮，偏下偏后）
        self.belly = ellipse_polygon(-8, 20, 75, 32, n=32)

        # 翅膀（折叠在身体侧）
        self.wing = [
            (-38, -28), (-18, -42), (8, -42), (28, -32),
            (42, -18), (40, 2),     (26, 14), (4, 20),
            (-20, 16), (-36, 4),    (-42, -12),
        ]

        # 尾巴（向后上方翘起的三角形）
        self.tail = [
            (-82, -8), (-110, -38), (-95, -35),
            (-88, -22), (-78, -18),
        ]

        # 头部（圆形）
        self.head_c = (72, -58)
        self.head_r = 35

        # 嘴（扁菱形）
        self.beak_upper = [
            (98, -68), (138, -58), (98, -55), (90, -60),
        ]
        self.beak_lower = [
            (98, -55), (138, -58), (98, -50), (95, -53),
        ]

        # 眼白 + 瞳孔
        self.eye_c = (84, -70)
        self.eye_r = 8
        self.pupil_c = (86, -69)
        self.pupil_r = 4

        # 腮红（小圆）
        self.cheek_c = (62, -45)
        self.cheek_r = 7

    # ---------------------------------------------------------------
    def render(self, surface, M, put_fn):
        """渲染整只鸭子。

        surface  —— pygame Surface
        M        —— 3×3 变换矩阵
        put_fn(surface, pixels, color) —— 写像素回调（含越界裁剪）
        """
        s = uniform_scale_of(M)

        def tx_poly(verts):
            return [(int(round(x)), int(round(y)))
                    for x, y in apply_points(M, verts)]

        def tx_circle(center, radius):
            cx, cy = apply_point(M, *center)
            return int(round(cx)), int(round(cy)), max(1, int(round(radius * s)))

        def fill_poly(verts, color):
            put_fn(surface, scanline_fill_polygon(verts), color)

        def outline_poly(verts, color, step=1):
            n = len(verts)
            for i in range(n):
                put_fn(surface,
                       bresenham_line(*verts[i], *verts[(i + 1) % n]),
                       color)

        def fill_circle(c, r, color):
            put_fn(surface, midpoint_circle_fill(c[0], c[1], r), color)

        def outline_circle(c, r, color):
            put_fn(surface, midpoint_circle(c[0], c[1], r), color)

        # ---------- 后→前 渲染顺序 ----------
        # 1. 尾巴
        tail = tx_poly(self.tail)
        fill_poly(tail, COLOR_WING)
        outline_poly(tail, COLOR_OUTLINE)

        # 2. 身体
        body = tx_poly(self.body)
        fill_poly(body, COLOR_BODY)

        # 3. 腹部（叠加在身体上）
        belly = tx_poly(self.belly)
        fill_poly(belly, COLOR_BELLY)

        # 4. 身体描边（放在腹部之后画轮廓清晰）
        outline_poly(body, COLOR_OUTLINE)

        # 5. 翅膀
        wing = tx_poly(self.wing)
        fill_poly(wing, COLOR_WING)
        outline_poly(wing, COLOR_OUTLINE)

        # 6. 头
        head = tx_circle(self.head_c, self.head_r)
        fill_circle(head[:2], head[2], COLOR_HEAD)
        outline_circle(head[:2], head[2], COLOR_OUTLINE)

        # 7. 腮红
        cheek = tx_circle(self.cheek_c, self.cheek_r)
        fill_circle(cheek[:2], cheek[2], COLOR_CHEEK)

        # 8. 嘴
        beak_u = tx_poly(self.beak_upper)
        fill_poly(beak_u, COLOR_BEAK)
        outline_poly(beak_u, COLOR_OUTLINE)
        beak_l = tx_poly(self.beak_lower)
        fill_poly(beak_l, COLOR_BEAK_DK)
        outline_poly(beak_l, COLOR_OUTLINE)

        # 9. 眼白
        eye = tx_circle(self.eye_c, self.eye_r)
        fill_circle(eye[:2], eye[2], COLOR_EYE)
        outline_circle(eye[:2], eye[2], COLOR_OUTLINE)

        # 10. 瞳孔
        pup = tx_circle(self.pupil_c, self.pupil_r)
        fill_circle(pup[:2], pup[2], COLOR_PUPIL)
