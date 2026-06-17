
import os
import math
import random
import pygame

from algorithms import (
    bresenham_line, midpoint_circle, midpoint_circle_fill,
    scanline_fill_polygon, clip_polygon_horizontal,
)
from widgets import Button, Toggle, Slider
from transforms import compose, translate, rotate, scale, apply_point, apply_points
from duck import Duck


WINDOW_W = 1180
WINDOW_H = 740
TOOLBAR_H = 50
SIDEBAR_W = 280

CANVAS_LEFT = 10
CANVAS_TOP = TOOLBAR_H + 10
CANVAS_W = WINDOW_W - SIDEBAR_W - 30
CANVAS_H = WINDOW_H - TOOLBAR_H - 20


THEMES = {
    "白昼": {
        "sky_top":    (140, 200, 240),
        "sky_bot":    (220, 240, 250),
        "water_top":  (90, 160, 200),
        "water_bot":  (30, 70, 120),
        "foam":       (240, 250, 255),
        "ripple":     (235, 250, 255),
        "underwater": (50, 120, 170),  # 鸭子水下部分的染色
        "sun":        (255, 235, 160),
    },
    "黄昏": {
        "sky_top":    (220, 130, 100),
        "sky_bot":    (255, 200, 150),
        "water_top":  (180, 100, 120),
        "water_bot":  (60, 30, 80),
        "foam":       (255, 230, 200),
        "ripple":     (255, 220, 200),
        "underwater": (140, 70, 120),
        "sun":        (255, 200, 120),
    },
    "月夜": {
        "sky_top":    (15, 25, 60),
        "sky_bot":    (35, 50, 100),
        "water_top":  (40, 70, 110),
        "water_bot":  (8, 18, 45),
        "foam":       (200, 220, 240),
        "ripple":     (180, 210, 240),
        "underwater": (40, 60, 100),
        "sun":        (240, 240, 220),  # 月亮
    },
}


class SwimmingScene:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.surface = pygame.Surface((w, h))
        self.duck = Duck()

        # 主题
        self.theme_name = "白昼"

        # 游泳参数
        self.swim_speed = 1.2     # 水平速度（像素/帧）
        self.bob_amp = 6.0        # 上下浮沉幅度（像素）
        self.rock_amp_deg = 4.0   # 左右摇摆幅度（度）
        self.water_y_ratio = 0.62 # 水面位置（占画布高度）
        self.paused = False
        self.swim_dir = 1         # +1 向右、-1 向左

        # 状态
        self.duck_x = w * 0.3
        self.frame = 0
        self.ripples = []         # [(cx, cy, r, age, max_age)]
        self.ripple_cd = 0        # 涟漪冷却计数

        # 开关
        self.show_ripples = True
        self.show_clipping = True   # 渲染水下部分（多边形裁剪演示）
        self.show_clip_debug = False  # 调试模式：高亮裁剪线 & 交点
        self.dragging = False     # 用于暂停 auto-swim

        # 背景缓存
        self._bg_cache = None
        self._bg_sig = None

    @property
    def theme(self):
        return THEMES[self.theme_name]

    @property
    def water_y(self):
        return int(self.h * self.water_y_ratio)

    # ---------- 状态控制 ----------
    def reset(self):
        self.duck_x = self.w * 0.3
        self.frame = 0
        self.ripples.clear()
        self.swim_dir = 1
        self.paused = False

    def set_speed(self, v):       self.swim_speed = float(v)
    def set_bob(self, v):         self.bob_amp = float(v)
    def set_rock(self, v):        self.rock_amp_deg = float(v)
    def set_water_y(self, v):
        self.water_y_ratio = float(v)
        self._bg_sig = None  # 水位变了，背景要重画

    def set_theme(self, name):
        self.theme_name = name
        self._bg_sig = None

    # ---------- 像素写入 ----------
    def _put(self, surf, pixels, color):
        w, h = surf.get_size()
        for x, y in pixels:
            if 0 <= x < w and 0 <= y < h:
                surf.set_at((x, y), color)

    # ---------- 背景：天空 + 水 + 太阳 ----------
    def _render_background(self):
        sig = (self.theme_name, self.water_y_ratio, self.w, self.h)
        if self._bg_sig == sig and self._bg_cache is not None:
            return
        cache = pygame.Surface((self.w, self.h))
        wy = self.water_y
        t = self.theme

        # 天空
        for y in range(0, wy):
            r = y / max(1, wy)
            c = (
                int(t["sky_top"][0] + r * (t["sky_bot"][0] - t["sky_top"][0])),
                int(t["sky_top"][1] + r * (t["sky_bot"][1] - t["sky_top"][1])),
                int(t["sky_top"][2] + r * (t["sky_bot"][2] - t["sky_top"][2])),
            )
            pygame.draw.line(cache, c, (0, y), (self.w, y))
        # 水（深色渐变）
        wh = self.h - wy
        for y in range(wy, self.h):
            r = (y - wy) / max(1, wh)
            c = (
                int(t["water_top"][0] + r * (t["water_bot"][0] - t["water_top"][0])),
                int(t["water_top"][1] + r * (t["water_bot"][1] - t["water_top"][1])),
                int(t["water_top"][2] + r * (t["water_bot"][2] - t["water_top"][2])),
            )
            pygame.draw.line(cache, c, (0, y), (self.w, y))

        # 太阳/月亮
        sun_x = int(self.w * 0.78)
        sun_y = int(wy * 0.35)
        sun_r = 35
        self._put(cache, midpoint_circle_fill(sun_x, sun_y, sun_r), t["sun"])
        # 光晕
        halo = tuple(int(c * 0.55) for c in t["sun"])
        for hr in (sun_r + 6, sun_r + 12):
            self._put(cache, midpoint_circle(sun_x, sun_y, hr), halo)

        # 远山剪影
        mountain_color = (
            max(0, t["sky_bot"][0] - 50),
            max(0, t["sky_bot"][1] - 50),
            max(0, t["sky_bot"][2] - 40),
        )
        rng = random.Random(2026)
        verts = [(0, wy)]
        x = 0
        while x < self.w:
            x += rng.randint(60, 140)
            verts.append((x, wy - rng.randint(30, 90)))
        verts.append((self.w, wy))
        self._put(cache, scanline_fill_polygon(verts), mountain_color)

        self._bg_cache = cache
        self._bg_sig = sig

    # ---------- 水面波纹（每帧重画——它会动）----------
    def _draw_water_surface(self):
        wy = self.water_y
        foam = self.theme["foam"]
        # 波动水平线：y(x) = wy + amp * sin(x * freq + t)
        for x in range(self.w):
            y_off = 2.5 * math.sin(x * 0.025 + self.frame * 0.05)
            y = int(wy + y_off)
            self.surface.set_at((x, y), foam)
            # 上方再加一像素淡色，营造细线感
            if 0 <= y - 1 < self.h:
                self.surface.set_at((x, y - 1),
                                    tuple(min(255, c + 15) for c in foam))

    # ---------- 涟漪 ----------
    def _emit_ripple(self):
        wy = self.water_y
        # 从鸭子尾部后方发出涟漪
        bx = int(self.duck_x - 80 * self.swim_dir)
        self.ripples.append({"cx": bx, "cy": wy, "r": 2.0,
                             "age": 0, "max_age": 70})

    def _update_ripples(self):
        for rp in self.ripples:
            rp["r"] += 1.4
            rp["age"] += 1
        self.ripples = [r for r in self.ripples if r["age"] < r["max_age"]]

    def _draw_ripples(self):
        wy = self.water_y
        base = self.theme["ripple"]
        for rp in self.ripples:
            alpha = 1.0 - rp["age"] / rp["max_age"]
            c = tuple(int(b * alpha) for b in base)
            # 涟漪在水面上的表现：扁椭圆——这里用近似的水平圆（中点画圆 + 只画上半）
            pts = midpoint_circle(rp["cx"], rp["cy"], int(rp["r"]))
            # 只画接近水面的部分（|y - wy| <= 3）
            for x, y in pts:
                if abs(y - wy) <= 2:
                    if 0 <= x < self.w and 0 <= y < self.h:
                        self.surface.set_at((x, y), c)

    # ---------- 鸭子 ----------
    def _duck_transform(self):
        """根据当前帧数计算复合变换 M"""
        t = self.frame * 0.05
        bob_y = self.bob_amp * math.sin(t)
        rock = math.radians(self.rock_amp_deg) * math.sin(t * 1.3)
        # 沿 swim_dir 决定鸭子是否水平翻转
        sx = -1.0 if self.swim_dir < 0 else 1.0
        wy = self.water_y
        cy = wy - 28 + bob_y     # 鸭子身体中心略高于水面，腹部入水
        return compose(
            translate(self.duck_x, cy),
            rotate(rock),
            scale(sx, 1.0),
        )

    def _draw_duck(self):
        M = self._duck_transform()
        # 1. 整只鸭子按常规渲染
        self.duck.render(self.surface, M, self._put)

        # 2. 水下染色：把身体 / 腹部多边形分别裁剪到水线下方，
        #    重新填充成蓝色调，覆盖在已渲染的鸭子之上
        if self.show_clipping:
            wy = self.water_y
            uw_color = self.theme["underwater"]

            for part in (self.duck.body, self.duck.belly):
                world_verts = apply_points(M, part)
                world_verts = [(int(round(x)), int(round(y)))
                               for x, y in world_verts]
                below = clip_polygon_horizontal(world_verts, wy, keep="below")
                below = [(int(round(x)), int(round(y))) for x, y in below]
                if len(below) >= 3:
                    self._put(self.surface,
                              scanline_fill_polygon(below), uw_color)
                    # 调试模式：高亮裁剪后多边形的轮廓和交点
                    if self.show_clip_debug:
                        n = len(below)
                        for i in range(n):
                            self._put(self.surface,
                                      bresenham_line(*below[i],
                                                     *below[(i + 1) % n]),
                                      (255, 240, 90))
                        for v in below:
                            if abs(v[1] - wy) <= 1:
                                self._put(self.surface,
                                          midpoint_circle_fill(v[0], v[1], 4),
                                          (255, 100, 100))

    # ---------- 步进 ----------
    def _step(self):
        if self.paused or self.dragging:
            return
        self.frame += 1
        self.duck_x += self.swim_speed * self.swim_dir
        # 到边界自动反向
        margin = 100
        if self.duck_x < margin:
            self.duck_x = margin
            self.swim_dir = 1
        elif self.duck_x > self.w - margin:
            self.duck_x = self.w - margin
            self.swim_dir = -1
        # 涟漪发射
        self.ripple_cd -= 1
        if self.ripple_cd <= 0:
            self._emit_ripple()
            self.ripple_cd = max(8, int(28 - self.swim_speed * 8))
        self._update_ripples()

    # ---------- 主渲染 ----------
    def render(self):
        self._step()
        self._render_background()
        self.surface.blit(self._bg_cache, (0, 0))
        if self.show_ripples:
            self._draw_ripples()
        self._draw_water_surface()
        self._draw_duck()

        # 调试模式：画水线
        if self.show_clip_debug:
            wy = self.water_y
            line = bresenham_line(0, wy, self.w - 1, wy)
            self._put(self.surface, line, (255, 100, 100))


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("计算机图形学课程设计 · 题目三：游泳的鸭子")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        font_path = self._find_font()
        self.font_title  = self._load_font(font_path, 18, bold=True)
        self.font_normal = self._load_font(font_path, 14)
        self.font_small  = self._load_font(font_path, 12)

        self.scene = SwimmingScene(CANVAS_W, CANVAS_H)
        self.theme_names = list(THEMES.keys())
        self.theme_idx = 0
        self.show_about = False
        self.status_msg = ""
        self.status_timer = 0
        self.drag_start_mx = 0
        self.drag_start_dx = 0

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
            ("重置", self._on_reset),
            ("暂停/继续", self._on_pause),
            ("反向", self._on_reverse),
            ("切换主题", self._on_theme),
            ("保存图片", self._on_save),
            ("关于", self._on_about),
        ]:
            self.buttons.append(Button((x, 10, 90, 30), label, cb, self.font_normal))
            x += 96

        for label, attr, cb in [
            ("涟漪",   "show_ripples",
                lambda v: setattr(self.scene, "show_ripples", v)),
            ("裁剪",   "show_clipping",
                lambda v: setattr(self.scene, "show_clipping", v)),
            ("裁剪调试", "show_clip_debug",
                lambda v: setattr(self.scene, "show_clip_debug", v)),
        ]:
            init = getattr(self.scene, attr)
            self.toggles.append(Toggle((x, 10, 80, 30), label, self.font_small, init, cb))
            x += 88

        sx = CANVAS_W + 30
        sy = TOOLBAR_H + 60
        self.sliders.append(Slider((sx, sy, 240, 20), "游泳速度",
            self.font_normal, 0.2, 3.5, self.scene.swim_speed, self.scene.set_speed))
        self.sliders.append(Slider((sx, sy + 60, 240, 20), "浮沉幅度",
            self.font_normal, 0.0, 15.0, self.scene.bob_amp, self.scene.set_bob))
        self.sliders.append(Slider((sx, sy + 120, 240, 20), "摇摆幅度 (°)",
            self.font_normal, 0.0, 12.0, self.scene.rock_amp_deg, self.scene.set_rock))
        self.sliders.append(Slider((sx, sy + 180, 240, 20), "水位",
            self.font_normal, 0.35, 0.85, self.scene.water_y_ratio, self.scene.set_water_y))

    # ---------- 回调 ----------
    def _on_reset(self):
        self.scene.reset()
        self._toast("已重置")

    def _on_pause(self):
        self.scene.paused = not self.scene.paused
        self._toast("已暂停" if self.scene.paused else "继续游")

    def _on_reverse(self):
        self.scene.swim_dir *= -1
        self._toast("掉头")

    def _on_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(self.theme_names)
        self.scene.set_theme(self.theme_names[self.theme_idx])
        self._toast(f"主题：{self.theme_names[self.theme_idx]}")

    def _on_save(self):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        i = 0
        while True:
            p = os.path.join(out_dir, f"swim_duck_{i:03d}.png")
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
                elif event.key == pygame.K_LEFT:
                    self.scene.duck_x = max(60, self.scene.duck_x - 30)
                elif event.key == pygame.K_RIGHT:
                    self.scene.duck_x = min(CANVAS_W - 60, self.scene.duck_x + 30)
                continue

            if self.show_about:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.show_about = False
                continue

            # 拖拽
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if (CANVAS_LEFT <= mx <= CANVAS_LEFT + CANVAS_W
                    and CANVAS_TOP <= my <= CANVAS_TOP + CANVAS_H):
                    on_widget = any(s.rect.inflate(0, 24).collidepoint(event.pos)
                                    for s in self.sliders)
                    if not on_widget:
                        self.scene.dragging = True
                        self.drag_start_mx = mx
                        self.drag_start_dx = self.scene.duck_x
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.scene.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.scene.dragging:
                dx = event.pos[0] - self.drag_start_mx
                self.scene.duck_x = max(60, min(CANVAS_W - 60,
                                                self.drag_start_dx + dx))

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

        info_y = sy + 320
        lines = [
            "—— 当前主题 ——",
            f"   {self.scene.theme_name}",
            "",
            "—— 快捷键 ——",
            "Space  暂停/继续",
            "← →   微调位置",
            "R      重置",
            "ESC    退出",
            "",
            "—— 算法演示 ——",
            "● Bresenham 直线",
            "● 中点画圆 / 实心填充",
            "● 扫描线多边形填充",
            "● 2D 齐次变换矩阵",
            "● Sutherland-Hodgman 裁剪",
        ]
        for i, line in enumerate(lines):
            if line.startswith("——"):
                c = (255, 220, 180); f = self.font_small
            else:
                c = (210, 225, 255); f = self.font_small
            ts = f.render(line, True, c)
            self.screen.blit(ts, (sx + 14, info_y + i * 19))

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
        dw, dh = 560, 360
        dx = (WINDOW_W - dw) // 2
        dy = (WINDOW_H - dh) // 2
        pygame.draw.rect(self.screen, (40, 50, 80), (dx, dy, dw, dh), border_radius=10)
        pygame.draw.rect(self.screen, (200, 220, 255), (dx, dy, dw, dh), 2, border_radius=10)
        lines = [
            ("计算机图形学课程设计 · 题目三（提高题）", self.font_title, (255, 230, 180)),
            ("", None, None),
            ("游泳的鸭子", self.font_title, (255, 255, 255)),
            ("", None, None),
            ("综合算法：", self.font_normal, (220, 230, 255)),
            ("    · Bresenham 直线 / 中点画圆 / 扫描线填充", self.font_normal, (200, 220, 255)),
            ("    · 2D 齐次坐标变换（平移+旋转+缩放复合）", self.font_normal, (200, 220, 255)),
            ("    · Sutherland-Hodgman 多边形裁剪（水下染色演示）", self.font_normal, (200, 220, 255)),
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
