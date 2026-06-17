# -*- coding: utf-8 -*-

import os
import math
import random
import pygame

from algorithms import (
    bresenham_line, midpoint_circle, midpoint_circle_fill,
    scanline_fill_polygon, bezier_curve,
)
from widgets import Button, Toggle, Slider
from transforms import compose, translate, rotate, scale, apply_point, apply_points
from tree import PineTree
from pinecone import Pinecone


WINDOW_W = 1180
WINDOW_H = 740
TOOLBAR_H = 50
SIDEBAR_W = 280

CANVAS_LEFT = 10
CANVAS_TOP = TOOLBAR_H + 10
CANVAS_W = WINDOW_W - SIDEBAR_W - 30
CANVAS_H = WINDOW_H - TOOLBAR_H - 20

# 配色主题
THEMES = {
    "春日": {
        "sky_top":     (160, 215, 245),
        "sky_bot":     (235, 245, 230),
        "ground_top":  (130, 175, 90),
        "ground_bot":  (75, 110, 50),
        "mountain":    (110, 130, 150),
        "sun":         (255, 235, 170),
    },
    "黄昏": {
        "sky_top":     (255, 175, 115),
        "sky_bot":     (255, 220, 170),
        "ground_top":  (130, 95, 60),
        "ground_bot":  (75, 50, 35),
        "mountain":    (105, 65, 75),
        "sun":         (255, 200, 100),
    },
    "雪夜": {
        "sky_top":     (20, 30, 65),
        "sky_bot":     (60, 80, 130),
        "ground_top":  (220, 230, 245),
        "ground_bot":  (170, 185, 210),
        "mountain":    (50, 65, 95),
        "sun":         (235, 235, 220),  # 月亮
    },
}



class ForestScene:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.surface = pygame.Surface((w, h))

        self.theme_name = "春日"
        self.wind = 0.0          # -3 ~ +3
        self.sway_speed = 1.0    # 摇摆角频率乘数
        self.pinecone_count = 12

        self.paused = False
        self.frame = 0

        # 树和地面
        self.ground_y = int(h * 0.78)
        self.tree = PineTree(
            trunk_height=140, trunk_w_top=14, trunk_w_bot=24,
            num_tiers=5, max_width=140, top_width=22,
        )
        self.tree_base_x = w // 2
        self.tree_base_y = self.ground_y

        # 松果
        self.pinecones = []
        self._spawn_pinecones()

        # 自动掉落计数
        self.auto_drop_cd = 240

        # 雪花粒子
        self.snowflakes = []

        # 显示开关
        self.show_wind_arrow = True
        self.show_bezier_controls = False

        # 静态背景缓存
        self._bg_cache = None
        self._bg_sig = None

    @property
    def theme(self):
        return THEMES[self.theme_name]

    # ---------- 参数 setter ----------
    def set_wind(self, v):
        self.wind = float(v)

    def set_sway_speed(self, v):
        self.sway_speed = float(v)

    def set_pinecone_count(self, v):
        target = int(v)
        if target != self.pinecone_count:
            self.pinecone_count = target
            self._spawn_pinecones()

    def set_theme(self, name):
        self.theme_name = name
        self._bg_sig = None
        # 重生成雪花
        if name == "雪夜":
            self._init_snow()
        else:
            self.snowflakes = []

    def reset(self):
        self._spawn_pinecones()
        self.frame = 0

    def shake(self):
        """摇晃树：让一部分挂着的松果脱落"""
        attached = [pc for pc in self.pinecones
                    if pc.state == Pinecone.STATE_ATTACHED]
        random.shuffle(attached)
        n_drop = max(1, len(attached) // 3)
        for pc in attached[:n_drop]:
            pc.release(wind_x=self.wind)

    def drop_all(self):
        for pc in self.pinecones:
            if pc.state == Pinecone.STATE_ATTACHED:
                pc.release(wind_x=self.wind)

    # ---------- 内部 ----------
    def _spawn_pinecones(self):
        """生成 n 个松果，均分挂到枝头"""
        self.pinecones = []
        base_M = self._tree_base_matrix()
        tips = self.tree.branch_tip_world_positions(
            base_M, 0.0, wind_strength=1.0)
        if not tips:
            return
        random.seed()
        # 给每个 tier 至少 1 个
        chosen = []
        per_tier = {}
        for ti, ki, _ in tips:
            per_tier.setdefault(ti, []).append((ti, ki))
        n_assigned = 0
        for ti in sorted(per_tier.keys()):
            if n_assigned >= self.pinecone_count:
                break
            ti_ki = random.choice(per_tier[ti])
            chosen.append(ti_ki)
            n_assigned += 1
        # 剩余随机挂
        remaining = [(ti, ki) for ti, ki, _ in tips if (ti, ki) not in chosen]
        random.shuffle(remaining)
        while n_assigned < self.pinecone_count and remaining:
            chosen.append(remaining.pop())
            n_assigned += 1

        for ti, ki in chosen:
            size = random.uniform(0.85, 1.15)
            self.pinecones.append(Pinecone(ti, ki, size=size))

    def _init_snow(self):
        self.snowflakes = []
        for _ in range(60):
            self.snowflakes.append({
                "x": random.uniform(0, self.w),
                "y": random.uniform(-self.h, 0),
                "vy": random.uniform(0.5, 1.6),
                "vx": random.uniform(-0.3, 0.3),
                "r": random.choice([1, 1, 2, 2, 3]),
            })

    def _tree_base_matrix(self):
        """从树局部坐标系到世界坐标系的基变换"""
        return translate(self.tree_base_x, self.tree_base_y)

    def _put(self, surf, pixels, color):
        w, h = surf.get_size()
        for x, y in pixels:
            if 0 <= x < w and 0 <= y < h:
                surf.set_at((x, y), color)

    # ---------- 静态背景：天空 + 远山 + 地面 + 太阳/月亮 ----------
    def _render_background(self):
        sig = (self.theme_name, self.w, self.h)
        if self._bg_sig == sig and self._bg_cache is not None:
            return
        cache = pygame.Surface((self.w, self.h))
        t = self.theme

        # 天空（地面以上）
        gy = self.ground_y
        for y in range(0, gy):
            r = y / max(1, gy)
            c = (
                int(t["sky_top"][0] + r * (t["sky_bot"][0] - t["sky_top"][0])),
                int(t["sky_top"][1] + r * (t["sky_bot"][1] - t["sky_top"][1])),
                int(t["sky_top"][2] + r * (t["sky_bot"][2] - t["sky_top"][2])),
            )
            pygame.draw.line(cache, c, (0, y), (self.w, y))

        # 太阳 / 月亮
        sun_x, sun_y, sun_r = int(self.w * 0.84), int(gy * 0.25), 36
        self._put(cache, midpoint_circle_fill(sun_x, sun_y, sun_r), t["sun"])
        halo = tuple(int(c * 0.55) for c in t["sun"])
        for hr in (sun_r + 7, sun_r + 14):
            self._put(cache, midpoint_circle(sun_x, sun_y, hr), halo)

        # 远山
        rng = random.Random(20260525)
        verts = [(0, gy)]
        x = 0
        while x < self.w:
            x += rng.randint(70, 160)
            verts.append((x, gy - rng.randint(50, 130)))
        verts.append((self.w, gy))
        self._put(cache, scanline_fill_polygon(verts), t["mountain"])

        # 地面（渐变）
        gh = self.h - gy
        for y in range(gy, self.h):
            r = (y - gy) / max(1, gh)
            c = (
                int(t["ground_top"][0] + r * (t["ground_bot"][0] - t["ground_top"][0])),
                int(t["ground_top"][1] + r * (t["ground_bot"][1] - t["ground_top"][1])),
                int(t["ground_top"][2] + r * (t["ground_bot"][2] - t["ground_top"][2])),
            )
            pygame.draw.line(cache, c, (0, y), (self.w, y))

        # 地面线（高光）
        pygame.draw.line(cache, tuple(min(255, c + 30) for c in t["ground_top"]),
                         (0, gy), (self.w, gy))

        self._bg_cache = cache
        self._bg_sig = sig

    # ---------- 雪花 ----------
    def _update_snow(self):
        if self.theme_name != "雪夜":
            return
        for s in self.snowflakes:
            s["y"] += s["vy"]
            s["x"] += s["vx"] + self.wind * 0.2
            if s["y"] > self.h:
                s["y"] = -random.uniform(0, 50)
                s["x"] = random.uniform(0, self.w)

    def _draw_snow(self):
        if self.theme_name != "雪夜":
            return
        for s in self.snowflakes:
            self._put(self.surface,
                      midpoint_circle_fill(int(s["x"]), int(s["y"]), s["r"]),
                      (240, 245, 255))

    # ---------- 风向指示 ----------
    def _draw_wind_arrow(self):
        if not self.show_wind_arrow or abs(self.wind) < 0.05:
            return
        # 在画布左上角画一个表示风向的箭头
        cx, cy = 50, 35
        # 长度与风强度成正比，max ±40
        L = int(self.wind * 13)
        if L == 0:
            return
        x_end = cx + L
        c = (255, 240, 120)
        self._put(self.surface, bresenham_line(cx, cy, x_end, cy), c)
        # 箭头头部
        if L > 0:
            self._put(self.surface, bresenham_line(x_end, cy, x_end - 8, cy - 4), c)
            self._put(self.surface, bresenham_line(x_end, cy, x_end - 8, cy + 4), c)
        else:
            self._put(self.surface, bresenham_line(x_end, cy, x_end + 8, cy - 4), c)
            self._put(self.surface, bresenham_line(x_end, cy, x_end + 8, cy + 4), c)

    # ---------- Bezier 控制点显示 ----------
    def _draw_bezier_debug(self):
        if not self.show_bezier_controls:
            return
        # 显示底层 tier 的 Bezier 控制点和原始曲线
        base_M = self._tree_base_matrix()
        # 第一层 tier
        tier = self.tree.tiers[0]
        theta = (math.radians(tier.sway_amp_deg) *
                 math.sin(self.frame * 0.05 * self.sway_speed + tier.sway_phase))
        M = compose(base_M,
                    translate(0, tier.base_y),
                    rotate(theta),
                    translate(0, -tier.base_y))
        ctrl = [(-tier.w, tier.base_y),
                (0.0, tier.base_y + 0.4 * tier.h),
                (tier.w, tier.base_y)]
        ctrl_world = apply_points(M, ctrl)
        # 控制点
        for cx, cy in ctrl_world:
            self._put(self.surface,
                      midpoint_circle_fill(int(cx), int(cy), 4),
                      (255, 100, 100))
        # 控制点连线
        for i in range(len(ctrl_world) - 1):
            a = ctrl_world[i]
            b = ctrl_world[i + 1]
            self._put(self.surface,
                      bresenham_line(int(a[0]), int(a[1]),
                                     int(b[0]), int(b[1])),
                      (255, 200, 200))

    # ---------- 步进 ----------
    def _step(self):
        if self.paused:
            return
        self.frame += 1

        # 自动掉落
        self.auto_drop_cd -= 1
        if self.auto_drop_cd <= 0:
            attached = [pc for pc in self.pinecones
                        if pc.state == Pinecone.STATE_ATTACHED]
            if attached:
                random.choice(attached).release(wind_x=self.wind)
            self.auto_drop_cd = random.randint(150, 280)

        # 同步挂着的松果
        base_M = self._tree_base_matrix()
        t = self.frame * 0.05 * self.sway_speed
        tips = self.tree.branch_tip_world_positions(base_M, t,
                                                    wind_strength=1.0)
        tips_map = {(ti, ki): pos for ti, ki, pos in tips}
        for pc in self.pinecones:
            if pc.state == Pinecone.STATE_ATTACHED:
                pos = tips_map.get((pc.tier_idx, pc.tip_idx))
                if pos is not None:
                    pc.attach_to(pos)
            else:
                pc.step(self.wind, self.ground_y - 2)

        self._update_snow()

    # ---------- 主渲染 ----------
    def render(self):
        self._step()
        self._render_background()
        self.surface.blit(self._bg_cache, (0, 0))
        self._draw_snow()

        base_M = self._tree_base_matrix()
        t = self.frame * 0.05 * self.sway_speed
        self.tree.render(self.surface, base_M, t,
                         wind_strength=1.0, put_fn=self._put)

        # Bezier 调试 (在 tree 上方画一层)
        self._draw_bezier_debug()

        # 松果（按 y 排序，让后面的先画）
        for pc in sorted(self.pinecones, key=lambda p: p.y):
            pc.render(self.surface, self._put)

        # 风向指示
        self._draw_wind_arrow()


# =============================================================================
# 主应用
# =============================================================================
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("计算机图形学课程设计 · 题目四：松树与松果")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        font_path = self._find_font()
        self.font_title  = self._load_font(font_path, 18, bold=True)
        self.font_normal = self._load_font(font_path, 14)
        self.font_small  = self._load_font(font_path, 12)

        self.scene = ForestScene(CANVAS_W, CANVAS_H)
        self.theme_names = list(THEMES.keys())
        self.theme_idx = 0
        self.show_about = False
        self.status_msg = ""
        self.status_timer = 0

        self._build_ui()
        self.running = True

    @staticmethod
    def _find_font():
        for p in [r"C:\Windows\Fonts\msyh.ttc",
                  r"C:\Windows\Fonts\simhei.ttf"]:
            if os.path.exists(p):
                return p
        return None

    @staticmethod
    def _load_font(path, size, bold=False):
        try:
            if path:
                f = pygame.font.Font(path, size)
                f.set_bold(bold)
                return f
        except Exception:
            pass
        f = pygame.font.Font(None, size + 4)
        f.set_bold(bold)
        return f

    # ---------- UI ----------
    def _build_ui(self):
        self.buttons = []
        self.toggles = []
        self.sliders = []

        x = 10
        for label, cb in [
            ("摇晃", self._on_shake),
            ("全部掉落", self._on_drop_all),
            ("重置", self._on_reset),
            ("暂停/继续", self._on_pause),
            ("切换主题", self._on_theme),
            ("保存图片", self._on_save),
            ("关于", self._on_about),
        ]:
            self.buttons.append(Button((x, 10, 84, 30), label, cb, self.font_normal))
            x += 92

        for label, attr, cb in [
            ("风向", "show_wind_arrow",
                lambda v: setattr(self.scene, "show_wind_arrow", v)),
            ("Bezier 控制点", "show_bezier_controls",
                lambda v: setattr(self.scene, "show_bezier_controls", v)),
        ]:
            init = getattr(self.scene, attr)
            self.toggles.append(Toggle((x, 10, 110, 30), label,
                                       self.font_small, init, cb))
            x += 118

        sx = CANVAS_W + 30
        sy = TOOLBAR_H + 60
        self.sliders.append(Slider((sx, sy, 240, 20), "风力",
            self.font_normal, -3.0, 3.0, self.scene.wind, self.scene.set_wind))
        self.sliders.append(Slider((sx, sy + 60, 240, 20), "摇摆速度",
            self.font_normal, 0.3, 3.0, self.scene.sway_speed,
            self.scene.set_sway_speed))
        self.sliders.append(Slider((sx, sy + 120, 240, 20), "松果数量",
            self.font_normal, 4, 24, self.scene.pinecone_count,
            self.scene.set_pinecone_count))

    # ---------- 回调 ----------
    def _on_shake(self):
        self.scene.shake()
        self._toast("摇下一些松果")

    def _on_drop_all(self):
        self.scene.drop_all()
        self._toast("全部掉落")

    def _on_reset(self):
        self.scene.reset()
        self._toast("已重置松果")

    def _on_pause(self):
        self.scene.paused = not self.scene.paused
        self._toast("已暂停" if self.scene.paused else "继续")

    def _on_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(self.theme_names)
        self.scene.set_theme(self.theme_names[self.theme_idx])
        self._toast(f"主题：{self.theme_names[self.theme_idx]}")

    def _on_save(self):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        i = 0
        while True:
            p = os.path.join(out_dir, f"pinetree_{i:03d}.png")
            if not os.path.exists(p):
                break
            i += 1
        pygame.image.save(self.scene.surface, p)
        self._toast(f"已保存：{os.path.basename(p)}")

    def _on_about(self):
        self.show_about = not self.show_about

    def _toast(self, msg, frames=110):
        self.status_msg = msg
        self.status_timer = frames

    # ---------- 事件 ----------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.show_about:
                        self.show_about = False
                    else:
                        self.running = False
                elif event.key == pygame.K_r:
                    self._on_reset()
                elif event.key == pygame.K_SPACE:
                    self._on_pause()
                elif event.key == pygame.K_s:
                    self._on_shake()
                continue

            if self.show_about:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.show_about = False
                continue

            # 点击画布：摇落点击附近的挂着松果
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if (CANVAS_LEFT <= mx <= CANVAS_LEFT + CANVAS_W
                    and CANVAS_TOP <= my <= CANVAS_TOP + CANVAS_H):
                    on_widget = any(s.rect.inflate(0, 24).collidepoint(event.pos)
                                    for s in self.sliders)
                    if not on_widget:
                        # 画布坐标
                        scx = mx - CANVAS_LEFT
                        scy = my - CANVAS_TOP
                        # 找最近的挂着松果
                        attached = [pc for pc in self.scene.pinecones
                                    if pc.state == Pinecone.STATE_ATTACHED]
                        if attached:
                            attached.sort(
                                key=lambda pc: (pc.x - scx)**2 + (pc.y - scy)**2)
                            # 如距离小于阈值就摇下
                            d2 = (attached[0].x - scx)**2 + (attached[0].y - scy)**2
                            if d2 < 80**2:
                                attached[0].release(wind_x=self.scene.wind)
                                self._toast("摇下了 1 颗")

            for b in self.buttons: b.handle_event(event)
            for t in self.toggles: t.handle_event(event)
            for s in self.sliders: s.handle_event(event)

    # ---------- 画 UI ----------
    def _draw_toolbar(self):
        pygame.draw.rect(self.screen, (30, 38, 65), (0, 0, WINDOW_W, TOOLBAR_H))
        pygame.draw.line(self.screen, (80, 100, 160),
                         (0, TOOLBAR_H), (WINDOW_W, TOOLBAR_H))
        for b in self.buttons: b.draw(self.screen)
        for t in self.toggles: t.draw(self.screen)

    def _draw_sidebar(self):
        sx = CANVAS_W + 20
        sw = WINDOW_W - sx - 10
        sy = TOOLBAR_H + 10
        sh = CANVAS_H
        pygame.draw.rect(self.screen, (25, 32, 55), (sx, sy, sw, sh))
        pygame.draw.rect(self.screen, (80, 100, 160), (sx, sy, sw, sh), 1)

        title = self.font_title.render("参数控制面板", True, (220, 230, 255))
        self.screen.blit(title, (sx + 12, sy + 14))
        pygame.draw.line(self.screen, (80, 100, 160),
                         (sx + 12, sy + 42), (sx + sw - 12, sy + 42), 1)

        for s in self.sliders: s.draw(self.screen)

        # 统计
        info_y = sy + 260
        att = sum(1 for p in self.scene.pinecones if p.state == Pinecone.STATE_ATTACHED)
        fall = sum(1 for p in self.scene.pinecones if p.state == Pinecone.STATE_FALLING)
        land = sum(1 for p in self.scene.pinecones if p.state == Pinecone.STATE_LANDED)
        lines = [
            "—— 松果状态 ——",
            f"   挂着：{att}",
            f"   下落：{fall}",
            f"   落地：{land}",
            "",
            "—— 当前主题 ——",
            f"   {self.scene.theme_name}",
            "",
            "—— 快捷键 ——",
            "S    摇晃",
            "R    重置",
            "Space 暂停 / 继续",
            "ESC  退出",
            "",
            "—— 算法演示 ——",
            "● Bresenham 直线",
            "● 中点画圆 / 实心填充",
            "● 扫描线多边形填充",
            "● 2D 齐次坐标变换",
            "● De Casteljau Bezier 曲线",
            "● 层级化变换 + 物理仿真",
        ]
        for i, line in enumerate(lines):
            if line.startswith("——"):
                c = (255, 220, 180); f = self.font_small
            else:
                c = (210, 225, 255); f = self.font_small
            ts = f.render(line, True, c)
            self.screen.blit(ts, (sx + 14, info_y + i * 18))

    def _draw_status_bar(self):
        if self.status_timer <= 0 or not self.status_msg:
            return
        self.status_timer -= 1
        bar = pygame.Rect(CANVAS_LEFT, CANVAS_TOP + CANVAS_H - 34,
                          CANVAS_W, 26)
        s = pygame.Surface((bar.w, bar.h), pygame.SRCALPHA)
        s.fill((20, 30, 60, 200))
        self.screen.blit(s, bar.topleft)
        ts = self.font_normal.render(self.status_msg, True, (255, 255, 220))
        self.screen.blit(ts, (bar.x + 12, bar.y + 4))

    def _draw_about(self):
        if not self.show_about:
            return
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        dw, dh = 580, 380
        dx = (WINDOW_W - dw) // 2
        dy = (WINDOW_H - dh) // 2
        pygame.draw.rect(self.screen, (40, 50, 80), (dx, dy, dw, dh), border_radius=10)
        pygame.draw.rect(self.screen, (200, 220, 255), (dx, dy, dw, dh), 2, border_radius=10)
        lines = [
            ("计算机图形学课程设计 · 题目四（难题）", self.font_title, (255, 230, 180)),
            ("", None, None),
            ("枝叶摇动的松树与掉落的松果", self.font_title, (255, 255, 255)),
            ("", None, None),
            ("综合算法：", self.font_normal, (220, 230, 255)),
            ("    · Bresenham 直线 / 中点画圆 / 扫描线填充", self.font_normal, (200, 220, 255)),
            ("    · 2D 齐次坐标变换（含层级化变换）", self.font_normal, (200, 220, 255)),
            ("    · De Casteljau 任意阶 Bezier 曲线", self.font_normal, (200, 220, 255)),
            ("    · 基于矩阵的层级骨架动画 + 物理仿真", self.font_normal, (200, 220, 255)),
            ("", None, None),
            ("合肥工业大学 · 计算机图形学课程", self.font_normal, (220, 230, 255)),
            ("", None, None),
            ("点击任意处或按 ESC 关闭", self.font_small, (170, 190, 230)),
        ]
        y = dy + 24
        for text, font, color in lines:
            if not text:
                y += 12
                continue
            ts = font.render(text, True, color)
            tr = ts.get_rect(centerx=dx + dw // 2, y=y)
            self.screen.blit(ts, tr)
            y += font.get_linesize() + 2

    # ---------- 主循环 ----------
    def run(self):
        while self.running:
            self.handle_events()
            self.scene.render()

            self.screen.fill((15, 20, 40))
            self._draw_toolbar()
            self.screen.blit(self.scene.surface, (CANVAS_LEFT, CANVAS_TOP))
            pygame.draw.rect(self.screen, (80, 100, 160),
                             (CANVAS_LEFT - 1, CANVAS_TOP - 1,
                              CANVAS_W + 2, CANVAS_H + 2), 1)
            self._draw_sidebar()
            self._draw_status_bar()
            self._draw_about()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()
