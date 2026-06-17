# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目四
松树模型 —— 多层枝叶 + 风力摇摆

坐标系：树根在原点 (0, 0)，+x 右、+y 下（pygame 习惯）。
树体向上生长 = 顶点 y 递减。

结构：
  · 一根中央树干（4 顶点梯形）
  · 若干层"枝叶"（tier）从下到上堆叠
       - 每层是一个底边为 Bezier 曲线的多边形（树叶状）
       - 每层有 N 个"枝头"用于挂松果
  · 每层独立做正弦旋转摇摆，振幅随高度递增

渲染：
  · 树干：扫描线填充
  · 每层枝叶：先用 Bezier 曲线生成底边采样点，与左右斜边 + 顶点拼成多边形，扫描线填充
  · 描边：Bresenham 直线沿轮廓画一遍深色
"""

import math
from algorithms import (
    bezier_curve,
    bresenham_line,
    scanline_fill_polygon,
)
from transforms import compose, translate, rotate, apply_point, apply_points


# 配色
COLOR_TRUNK       = (95, 60, 35)
COLOR_TRUNK_DARK  = (60, 38, 22)
COLOR_LEAF_TIERS  = [
    (35, 110, 55),    # 最底层（最深的绿）
    (45, 130, 65),
    (55, 150, 75),
    (70, 170, 90),
    (90, 195, 110),   # 顶层（最浅的绿）
]
COLOR_OUTLINE_LEAF = (15, 60, 30)


class TreeTier:
    """单层枝叶。所有顶点定义在\textit{树局部坐标系}中。

    一个 tier 由：左下角 (-w, base_y)、右下角 (w, base_y)、
    顶点 (0, base_y - h) 三个关键点定义；底边用一条二次 Bezier
    采样得到向下凸出的曲线（仿真叶层下垂感）。
    """

    def __init__(self, base_y, half_width, height,
                 sway_amp_deg, sway_phase, color):
        self.base_y = base_y           # 该层底部在树坐标系的 y
        self.w = half_width             # 底边半宽
        self.h = height                  # 该层高度
        self.sway_amp_deg = sway_amp_deg  # 摇摆幅度（度）
        self.sway_phase = sway_phase      # 相位偏移
        self.color = color

        # 预生成静态轮廓（局部坐标系，未旋转）：
        # 起点 (-w, base_y) → 底边 Bezier 弧线 → 终点 (w, base_y) → 顶点 (0, base_y - h)
        # Bezier 控制点放在 (0, base_y + 0.4*h)，让底边向下凸（垂坠）
        bottom = bezier_curve(
            control_points=[(-self.w, self.base_y),
                            (0.0, self.base_y + 0.4 * self.h),
                            (self.w, self.base_y)],
            segments=18
        )
        apex = (0.0, self.base_y - self.h)
        # 多边形顶点（顺时针/逆时针都可，扫描线填充无所谓）
        self.local_polygon = bottom + [apex]

        # 枝头：底边采样里挑 4 个点作为松果挂载位置
        bottom_samples = bottom
        n = len(bottom_samples)
        idxs = [int(n * 0.15), int(n * 0.4), int(n * 0.6), int(n * 0.85)]
        self.branch_tips_local = [bottom_samples[i] for i in idxs]

    def sway_matrix(self, t):
        """返回该 tier 当前的摇摆矩阵（绕自己 base_y 旋转）。

        旋转中心 = (0, base_y)，旋转角随时间正弦变化：
            θ = sway_amp · sin(ω·t + phase)
        """
        theta = math.radians(self.sway_amp_deg) * math.sin(t + self.sway_phase)
        return compose(
            translate(0, self.base_y),
            rotate(theta),
            translate(0, -self.base_y),
        )


class PineTree:
    """松树模型：树干 + 多层 tier"""

    def __init__(self, trunk_height=120, trunk_w_top=14, trunk_w_bot=22,
                 num_tiers=5, max_width=130, top_width=20,
                 total_leaf_height=320):
        self.trunk_height = trunk_height
        self.trunk_w_top = trunk_w_top
        self.trunk_w_bot = trunk_w_bot

        # 树干多边形（梯形）：底中心在 (0, 0)，向上延伸
        self.trunk_polygon = [
            (-trunk_w_bot, 0),
            ( trunk_w_bot, 0),
            ( trunk_w_top, -trunk_height),
            (-trunk_w_top, -trunk_height),
        ]

        # 各 tier 由低到高排列
        self.tiers = []
        trunk_top_y = -trunk_height
        # 每层在树叶总高度上占的位置：bottom 层 base_y = trunk_top_y
        # 顶层 base_y = trunk_top_y - total_leaf_height + tier_h_top
        for i in range(num_tiers):
            # 0 = 最底层；num_tiers-1 = 顶层
            ratio = i / max(1, num_tiers - 1)
            # 宽度从底到顶线性收窄
            half_w = max_width - (max_width - top_width) * ratio
            # 每层高度
            tier_h = 80
            # base_y：每层底部位置（从 trunk_top_y 向上累加，每层有 0.65 * tier_h 重叠）
            base_y = trunk_top_y - i * (tier_h * 0.65)
            # 越往上摇摆越大
            sway_amp = 1.5 + 4.5 * ratio
            phase = i * 0.7
            color = COLOR_LEAF_TIERS[min(i, len(COLOR_LEAF_TIERS) - 1)]
            self.tiers.append(TreeTier(
                base_y=base_y,
                half_width=half_w,
                height=tier_h * 1.4,  # 高一点以盖住下层
                sway_amp_deg=sway_amp,
                sway_phase=phase,
                color=color,
            ))

    # ----------------------------------------------------------------
    # 当前帧每个 tier 的世界变换（含父变换 base_M 与 tier 自身摇摆）
    # ----------------------------------------------------------------
    def tier_world_matrices(self, base_M, t, wind_strength=1.0):
        """返回 [(tier, M_world), ...]，每层叠加自身摇摆 + 父变换"""
        result = []
        for tier in self.tiers:
            # 风强度作用于摇摆幅度
            theta = (math.radians(tier.sway_amp_deg) * wind_strength
                     * math.sin(t + tier.sway_phase))
            M_sway = compose(
                translate(0, tier.base_y),
                rotate(theta),
                translate(0, -tier.base_y),
            )
            result.append((tier, compose(base_M, M_sway)))
        return result

    # ----------------------------------------------------------------
    # 渲染
    # ----------------------------------------------------------------
    def render(self, surface, base_M, t, wind_strength, put_fn):
        # 1) 树干（无摇摆，固定）
        trunk_world = [(int(round(x)), int(round(y)))
                       for x, y in apply_points(base_M, self.trunk_polygon)]
        put_fn(surface, scanline_fill_polygon(trunk_world), COLOR_TRUNK)
        # 高光线（左侧偏暗模拟阴影）
        n = len(trunk_world)
        for i in range(n):
            put_fn(surface,
                   bresenham_line(*trunk_world[i],
                                  *trunk_world[(i + 1) % n]),
                   COLOR_TRUNK_DARK)

        # 2) 每层枝叶（从底到顶画——底层先画，顶层最后画在前面）
        for tier, M_world in self.tier_world_matrices(base_M, t, wind_strength):
            world_verts = [(int(round(x)), int(round(y)))
                           for x, y in apply_points(M_world, tier.local_polygon)]
            put_fn(surface, scanline_fill_polygon(world_verts), tier.color)
            # 描边
            n = len(world_verts)
            for i in range(n):
                put_fn(surface,
                       bresenham_line(*world_verts[i],
                                      *world_verts[(i + 1) % n]),
                       COLOR_OUTLINE_LEAF)

    # ----------------------------------------------------------------
    # 获取所有枝头当前世界坐标（用于松果挂载）
    # ----------------------------------------------------------------
    def branch_tip_world_positions(self, base_M, t, wind_strength=1.0):
        """返回 [(tier_idx, tip_idx, (x, y)), ...]"""
        out = []
        for ti, (tier, M_world) in enumerate(
                self.tier_world_matrices(base_M, t, wind_strength)):
            for ki, tip in enumerate(tier.branch_tips_local):
                wx, wy = apply_point(M_world, *tip)
                out.append((ti, ki, (wx, wy)))
        return out
