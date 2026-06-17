# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目四
松果模型 —— 两种状态 + 物理仿真

状态机：
  ATTACHED  -- 挂在某根枝头，世界位置由树体摇摆决定（每帧同步）。
  FALLING   -- 已脱离，按物理更新：
                 vy ← vy + g
                 vx ← vx + wind · k_wind
                 vx, vy 乘阻力系数 ≤ 1
                 旋转 angle ← angle + va
                 落到地面 (y ≥ ground_y) 时进入 LANDED。
  LANDED    -- 停在地面，停止旋转，仅渲染。

形状：
  局部坐标系：尖端朝下 (+y)。
  外轮廓 12 顶点近似橄榄形多边形，扫描线填充棕色，
  叠加 4 条水平 / 斜向 Bresenham 直线模拟松果鳞片纹理。
"""

import math
import random

from algorithms import (
    bresenham_line,
    scanline_fill_polygon,
    midpoint_circle_fill,
)
from transforms import compose, translate, rotate, scale, apply_points


# 颜色
COLOR_CONE      = (130, 75, 35)
COLOR_CONE_DARK = (75, 45, 20)
COLOR_TIP       = (95, 55, 25)
GRAVITY         = 0.35     # 像素 / 帧²
DRAG            = 0.992    # 速度阻尼
WIND_COEF       = 0.05     # 风力对水平速度的影响系数


# 松果外形（局部坐标，原点 = 挂点，尖端朝下 +y）
PINECONE_LOCAL = [
    ( 0,  -2),
    ( 5,   0),
    ( 8,   5),
    ( 9,  12),
    ( 7,  18),
    ( 4,  22),
    ( 0,  24),
    (-4,  22),
    (-7,  18),
    (-9,  12),
    (-8,   5),
    (-5,   0),
]

# 鳞片纹理：每条用一对端点（局部坐标）
PINECONE_SCALES = [
    ((-7,  4), ( 7,  4)),
    ((-8,  9), ( 8,  9)),
    ((-7, 14), ( 7, 14)),
    ((-5, 19), ( 5, 19)),
    ((-4,  4), ( 4, 14)),
    (( 4,  4), (-4, 14)),
]


class Pinecone:
    STATE_ATTACHED = 0
    STATE_FALLING  = 1
    STATE_LANDED   = 2

    def __init__(self, tier_idx, tip_idx, size=1.0):
        self.tier_idx = tier_idx
        self.tip_idx = tip_idx
        self.state = self.STATE_ATTACHED
        self.x = 0.0
        self.y = 0.0
        self.angle = 0.0
        self.size = size
        # 物理
        self.vx = 0.0
        self.vy = 0.0
        self.va = 0.0
        # 落地后是否已记录（不再做计算）
        self.land_timer = 0

    # ----------------------------------------------------------------
    def attach_to(self, world_xy):
        """ATTACHED 状态下：每帧同步世界位置"""
        if self.state == self.STATE_ATTACHED:
            self.x, self.y = world_xy
            # 默认松果尖端朝下，挂点对应顶部
            # 没有旋转——后续可叠加微小摇摆，此处先不加

    def release(self, wind_x=0.0):
        """脱离枝头，进入自由落体"""
        if self.state != self.STATE_ATTACHED:
            return
        self.state = self.STATE_FALLING
        self.vx = random.uniform(-1.0, 1.0) + wind_x * 0.3
        self.vy = random.uniform(0.0, 0.8)
        self.va = random.uniform(-0.08, 0.08)

    def step(self, wind_x, ground_y):
        if self.state != self.STATE_FALLING:
            if self.state == self.STATE_LANDED:
                self.land_timer += 1
            return
        # 重力
        self.vy += GRAVITY
        # 风力
        self.vx += wind_x * WIND_COEF
        # 空气阻力
        self.vx *= DRAG
        self.vy *= DRAG
        # 积分
        self.x += self.vx
        self.y += self.vy
        self.angle += self.va
        # 落地判定
        if self.y >= ground_y:
            self.y = ground_y
            self.state = self.STATE_LANDED
            self.vx = self.vy = self.va = 0.0

    def reset(self):
        self.state = self.STATE_ATTACHED
        self.vx = self.vy = self.va = 0.0
        self.angle = 0.0
        self.land_timer = 0

    # ----------------------------------------------------------------
    def render(self, surface, put_fn):
        """画松果：先把局部多边形按 (size·R(angle)·T(x, y)) 变到世界"""
        M = compose(
            translate(self.x, self.y),
            rotate(self.angle),
            scale(self.size, self.size),
        )
        # 主体
        world = [(int(round(x)), int(round(y)))
                 for x, y in apply_points(M, PINECONE_LOCAL)]
        put_fn(surface, scanline_fill_polygon(world), COLOR_CONE)

        # 描边
        n = len(world)
        for i in range(n):
            put_fn(surface,
                   bresenham_line(*world[i], *world[(i + 1) % n]),
                   COLOR_CONE_DARK)

        # 鳞片纹理
        for a, b in PINECONE_SCALES:
            pa, pb = apply_points(M, [a, b])
            ax, ay = int(round(pa[0])), int(round(pa[1]))
            bx, by = int(round(pb[0])), int(round(pb[1]))
            put_fn(surface, bresenham_line(ax, ay, bx, by), COLOR_CONE_DARK)

        # 尖端高光小圆
        tip_world = apply_points(M, [(0, 24)])[0]
        put_fn(surface,
               midpoint_circle_fill(int(tip_world[0]), int(tip_world[1]), 1),
               COLOR_TIP)
