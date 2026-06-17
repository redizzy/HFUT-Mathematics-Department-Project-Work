# -*- coding: utf-8 -*-

import os
import math
import random
import pygame

from algorithms import (
    bresenham_line,
    midpoint_circle,
    midpoint_circle_fill,
    scanline_fill_polygon,
    star_vertices,
)
from widgets import Button, Toggle, Slider


WINDOW_W = 1180
WINDOW_H = 740
TOOLBAR_H = 50
SIDEBAR_W = 260

CANVAS_LEFT = 10
CANVAS_TOP = TOOLBAR_H + 10
CANVAS_W = WINDOW_W - SIDEBAR_W - 30
CANVAS_H = WINDOW_H - TOOLBAR_H - 20


THEMES = {
    "深夜": {
        "bg_top":      (5, 10, 30),
        "bg_bot":      (15, 25, 60),
        "mountain":    (8, 14, 28),
        "big_star":    (255, 230, 120),
        "small_star":  (255, 255, 240),
        "moon":        (240, 240, 230),
        "comet":       (180, 220, 255),
    },
    "黄昏": {
        "bg_top":      (40, 20, 60),
        "bg_bot":      (220, 120, 90),
        "mountain":    (30, 18, 35),
        "big_star":    (255, 255, 200),
        "small_star":  (255, 240, 220),
        "moon":        (255, 230, 200),
        "comet":       (255, 200, 180),
    },
    "极光": {
        "bg_top":      (8, 22, 38),
        "bg_bot":      (40, 110, 95),
        "mountain":    (10, 25, 30),
        "big_star":    (220, 255, 230),
        "small_star":  (220, 255, 240),
        "moon":        (210, 240, 220),
        "comet":       (160, 255, 200),
    },
}


# =============================================================================
# 场景渲染器
# =============================================================================
class StarScene:
    """星空场景。负责按当前参数把所有图元渲染到内部 Surface。"""

    def __init__(self, canvas_w, canvas_h):
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        self.surface = pygame.Surface((canvas_w, canvas_h))

        # 可调参数
        self.theme_name = "深夜"
        self.star_count = 90
        self.big_star_size = 70
        self.show_moon = True
        self.show_comet = True
        self.animate = True

        # 内部状态
        self.frame = 0
        self.comet_t = 0.0
        self.small_stars = []   # (x, y, r, phase)
        self.mountain_verts = []
        self._static_cache = None  # 静态层缓存（背景 + 山脉 + 月亮）
        self._cache_signature = None

        self._regen_stars()
        self._regen_mountains()

    # ---------------- 主题与参数 ----------------
    @property
    def theme(self):
        return THEMES[self.theme_name]

    def set_star_count(self, n):
        self.star_count = int(n)
        self._regen_stars()

    def set_big_star_size(self, s):
        self.big_star_size = int(s)

    def set_theme(self, name):
        self.theme_name = name
        self._invalidate_cache()

    def set_show_moon(self, v):
        self.show_moon = bool(v)
        self._invalidate_cache()

    def set_show_comet(self, v):
        self.show_comet = bool(v)

    def set_animate(self, v):
        self.animate = bool(v)

    def regenerate(self):
        self._regen_stars()
        self._regen_mountains()
        self._invalidate_cache()

    # ---------------- 内部 ----------------
    def _regen_stars(self):
        random.seed()
        self.small_stars = []
        for _ in range(self.star_count):
            x = random.randint(10, self.canvas_w - 10)
            y = random.randint(10, int(self.canvas_h * 0.78))
            r = random.choices([1, 2, 3, 4], weights=[5, 4, 2, 1])[0]
            phase = random.uniform(0, 2 * math.pi)
            self.small_stars.append((x, y, r, phase))

    def _regen_mountains(self):
        rng = random.Random(random.randint(0, 10**6))
        verts = [(0, self.canvas_h)]
        x = 0
        base = self.canvas_h - 10
        while x < self.canvas_w:
            x += rng.randint(30, 110)
            peak_y = base - rng.randint(50, 140)
            verts.append((x, peak_y))
        verts.append((self.canvas_w, self.canvas_h))
        self.mountain_verts = verts

    def _invalidate_cache(self):
        self._static_cache = None
        self._cache_signature = None

    # ---------------- 像素写入辅助 ----------------
    def _put(self, surf, points, color):
        """批量写像素到指定 Surface（含越界裁剪）"""
        w, h = surf.get_size()
        for x, y in points:
            if 0 <= x < w and 0 <= y < h:
                surf.set_at((x, y), color)

    # ---------------- 各图元绘制 ----------------
    def _draw_gradient_bg(self, target):
        top = self.theme["bg_top"]
        bot = self.theme["bg_bot"]
        for y in range(self.canvas_h):
            t = y / self.canvas_h
            c = (
                int(top[0] + t * (bot[0] - top[0])),
                int(top[1] + t * (bot[1] - top[1])),
                int(top[2] + t * (bot[2] - top[2])),
            )
            pygame.draw.line(target, c, (0, y), (self.canvas_w, y))

    def _draw_moon(self, target):
        color = self.theme["moon"]
        cx, cy, r = 140, 130, 50
        # 主体：实心圆（中点画圆 + 水平扫描）
        self._put(target, midpoint_circle_fill(cx, cy, r), color)
        # 月坑：暗色小圆
        dark = tuple(max(0, c - 50) for c in color)
        for dx, dy, rr in [(-15, -10, 8), (12, 5, 7), (-5, 16, 5), (18, -14, 4)]:
            self._put(target, midpoint_circle_fill(cx + dx, cy + dy, rr), dark)
        # 月晕：两层空心圆
        for halo_r in (r + 8, r + 16):
            halo = tuple(int(c * 0.45) for c in color)
            self._put(target, midpoint_circle(cx, cy, halo_r), halo)

    def _draw_mountains(self, target):
        self._put(target,
                  scanline_fill_polygon(self.mountain_verts),
                  self.theme["mountain"])

    def _draw_small_stars(self, target):
        base_color = self.theme["small_star"]
        for x, y, r, phase in self.small_stars:
            # 闪烁亮度
            if self.animate:
                bright = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(self.frame * 0.06 + phase))
            else:
                bright = 1.0
            c = tuple(min(255, int(ch * bright)) for ch in base_color)
            if r == 1:
                if 0 <= x < self.canvas_w and 0 <= y < self.canvas_h:
                    target.set_at((x, y), c)
            else:
                # 实心圆主体
                self._put(target, midpoint_circle_fill(x, y, r), c)
                # 大一点的加十字光芒（Bresenham 直线）
                if r >= 3:
                    spike = r + 3
                    self._put(target, bresenham_line(x - spike, y, x + spike, y), c)
                    self._put(target, bresenham_line(x, y - spike, x, y + spike), c)

    def _draw_big_star(self, target):
        color = self.theme["big_star"]
        cx = self.canvas_w - 200
        cy = 150
        r = self.big_star_size
        rot = (self.frame * 0.004) if self.animate else 0.0

        verts = star_vertices(cx, cy, r, num_points=5, rotation=rot)

        # 扫描线填充
        self._put(target, scanline_fill_polygon(verts), color)
        # 描边（Bresenham 直线）：更亮的轮廓
        outline = tuple(min(255, c + 30) for c in color)
        n = len(verts)
        for i in range(n):
            self._put(target,
                      bresenham_line(*verts[i], *verts[(i + 1) % n]),
                      outline)
        # 中心高光（小实心圆）
        self._put(target, midpoint_circle_fill(cx, cy, 4), (255, 255, 255))
        # 外发散光芒（12 根短线）
        for ang_deg in range(0, 360, 30):
            ang = math.radians(ang_deg) + rot
            x1 = cx + int((r + 10) * math.cos(ang))
            y1 = cy + int((r + 10) * math.sin(ang))
            x2 = cx + int((r + 30) * math.cos(ang))
            y2 = cy + int((r + 30) * math.sin(ang))
            ray = tuple(int(c * 0.65) for c in color)
            self._put(target, bresenham_line(x1, y1, x2, y2), ray)

    def _draw_comet(self, target):
        color = self.theme["comet"]
        # 路径：从右上方斜射向左下方
        x_a, y_a = self.canvas_w - 60, 60
        x_b, y_b = 60, int(self.canvas_h * 0.55)
        t = self.comet_t
        cx = int(x_a + t * (x_b - x_a))
        cy = int(y_a + t * (y_b - y_a))

        # 尾巴方向向量
        dx, dy = x_a - x_b, y_a - y_b
        norm = math.hypot(dx, dy)
        ux, uy = dx / norm, dy / norm

        # 尾巴：渐隐多段直线
        tail_len = 90
        for i in range(0, tail_len, 2):
            tx = int(cx + ux * i)
            ty = int(cy + uy * i)
            alpha = (1 - i / tail_len) ** 1.5
            tc = tuple(int(c * alpha) for c in color)
            self._put(target, [(tx, ty), (tx, ty + 1)], tc)
        # 彗头实心圆
        self._put(target, midpoint_circle_fill(cx, cy, 4), color)
        # 头部光晕
        halo = tuple(int(c * 0.5) for c in color)
        self._put(target, midpoint_circle(cx, cy, 7), halo)

    # ---------------- 主渲染 ----------------
    def render(self):
        # 静态层（背景 + 山脉 + 月亮）缓存——参数没变就不重画
        sig = (self.theme_name, self.show_moon, tuple(self.mountain_verts))
        if self._cache_signature != sig or self._static_cache is None:
            cache = pygame.Surface((self.canvas_w, self.canvas_h))
            self._draw_gradient_bg(cache)
            self._draw_mountains(cache)
            if self.show_moon:
                self._draw_moon(cache)
            self._static_cache = cache
            self._cache_signature = sig

        # 把缓存层贴到工作 surface 上
        self.surface.blit(self._static_cache, (0, 0))

        # 动态层
        self._draw_small_stars(self.surface)
        self._draw_big_star(self.surface)
        if self.show_comet:
            self._draw_comet(self.surface)

        if self.animate:
            self.frame += 1
            self.comet_t = (self.comet_t + 0.004) % 1.15


# =============================================================================
# 主应用
# =============================================================================
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("计算机图形学课程设计 · 题目一：星空图")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        # 字体：直接按文件路径加载 Windows 中文字体，
        # 避开 pygame.font.SysFont 在某些系统注册表上的崩溃。
        font_path = self._find_chinese_font()
        self.font_title = self._load_font(font_path, 18, bold=True)
        self.font_normal = self._load_font(font_path, 14)
        self.font_small = self._load_font(font_path, 12)

        self.scene = StarScene(CANVAS_W, CANVAS_H)
        self.theme_names = list(THEMES.keys())
        self.theme_idx = 0
        self.show_about_dialog = False
        self.status_msg = ""
        self.status_timer = 0

        self._build_ui()
        self.running = True

    @staticmethod
    def _find_chinese_font():
        """在 Windows 系统字体目录里找一个可用的中文字体文件路径。
        找不到就返回 None，让 pygame 用默认字体（不显示中文，但不会崩）。"""
        candidates = [
            r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑
            r"C:\Windows\Fonts\msyhbd.ttc", # 微软雅黑粗体
            r"C:\Windows\Fonts\simhei.ttf", # 黑体
            r"C:\Windows\Fonts\simsun.ttc", # 宋体
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    @staticmethod
    def _load_font(path, size, bold=False):
        """按文件路径加载字体，失败回退到 pygame 内置默认字体。"""
        try:
            if path:
                f = pygame.font.Font(path, size)
                f.set_bold(bold)
                return f
        except Exception:
            pass
        # 用 None 路径加载 pygame 内置默认字体（不会触发系统字体扫描）
        f = pygame.font.Font(None, size + 4)
        f.set_bold(bold)
        return f

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        self.buttons = []
        self.toggles = []
        self.sliders = []

        # 工具栏按钮
        x = 10
        toolbar_items = [
            ("重新生成", self._on_regen),
            ("切换主题", self._on_cycle_theme),
            ("保存图片", self._on_save),
            ("关于", self._on_about),
        ]
        for label, cb in toolbar_items:
            self.buttons.append(Button((x, 10, 88, 30), label, cb, self.font_normal))
            x += 96

        # 工具栏开关
        toggle_items = [
            ("月亮", self.scene.show_moon, self.scene.set_show_moon),
            ("彗星", self.scene.show_comet, self.scene.set_show_comet),
            ("动画", self.scene.animate, self.scene.set_animate),
        ]
        for label, init, cb in toggle_items:
            self.toggles.append(Toggle((x, 10, 72, 30), label, self.font_small, init, cb))
            x += 80

        # 侧边栏滑块
        sx = CANVAS_W + 30
        sy = TOOLBAR_H + 70
        self.sliders.append(Slider(
            (sx, sy, 220, 20), "星星数量", self.font_normal,
            10, 250, self.scene.star_count, self.scene.set_star_count
        ))
        self.sliders.append(Slider(
            (sx, sy + 70, 220, 20), "大星星尺寸", self.font_normal,
            30, 120, self.scene.big_star_size, self.scene.set_big_star_size
        ))

    # ---------------- 回调 ----------------
    def _on_regen(self):
        self.scene.regenerate()
        self._toast("已重新生成场景")

    def _on_cycle_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(self.theme_names)
        self.scene.set_theme(self.theme_names[self.theme_idx])
        self._toast(f"当前主题：{self.theme_names[self.theme_idx]}")

    def _on_save(self):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        i = 0
        while True:
            path = os.path.join(out_dir, f"starry_sky_{i:03d}.png")
            if not os.path.exists(path):
                break
            i += 1
        pygame.image.save(self.scene.surface, path)
        self._toast(f"已保存：{os.path.basename(path)}")

    def _on_about(self):
        self.show_about_dialog = not self.show_about_dialog

    def _toast(self, msg, frames=120):
        self.status_msg = msg
        self.status_timer = frames

    # ---------------- 事件 ----------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.show_about_dialog:
                        self.show_about_dialog = False
                    else:
                        self.running = False
                elif event.key == pygame.K_r:
                    self._on_regen()
                elif event.key == pygame.K_t:
                    self._on_cycle_theme()
                elif event.key == pygame.K_s:
                    self._on_save()
                elif event.key == pygame.K_SPACE:
                    self.scene.set_animate(not self.scene.animate)
                    for tg in self.toggles:
                        if tg.text == "动画":
                            tg.state = self.scene.animate

            # 弹窗时拦截鼠标事件
            if self.show_about_dialog:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.show_about_dialog = False
                continue

            for b in self.buttons:
                b.handle_event(event)
            for t in self.toggles:
                t.handle_event(event)
            for s in self.sliders:
                s.handle_event(event)

    # ---------------- UI 绘制 ----------------
    def _draw_toolbar(self):
        pygame.draw.rect(self.screen, (30, 38, 65), (0, 0, WINDOW_W, TOOLBAR_H))
        pygame.draw.line(self.screen, (80, 100, 160),
                         (0, TOOLBAR_H), (WINDOW_W, TOOLBAR_H), 1)
        for b in self.buttons:
            b.draw(self.screen)
        for t in self.toggles:
            t.draw(self.screen)

    def _draw_sidebar(self):
        sx = CANVAS_W + 20
        sw = WINDOW_W - sx - 10
        sy = TOOLBAR_H + 10
        sh = CANVAS_H

        pygame.draw.rect(self.screen, (25, 32, 55), (sx, sy, sw, sh))
        pygame.draw.rect(self.screen, (80, 100, 160), (sx, sy, sw, sh), 1)

        # 标题
        title = self.font_title.render("参数控制面板", True, (220, 230, 255))
        self.screen.blit(title, (sx + 12, sy + 14))
        pygame.draw.line(self.screen, (80, 100, 160),
                         (sx + 12, sy + 42), (sx + sw - 12, sy + 42), 1)

        # 滑块
        for s in self.sliders:
            s.draw(self.screen)

        # 状态信息
        info_y = sy + 220
        lines = [
            "—— 快捷键 ——",
            "R   重新生成",
            "T   切换主题",
            "S   保存图片",
            "Space  切换动画",
            "ESC  退出",
            "",
            "—— 当前主题 ——",
            f"   {self.scene.theme_name}",
            "",
            "—— 算法演示 ——",
            "● Bresenham 直线",
            "● 中点画圆",
            "● 扫描线多边形填充",
        ]
        for i, line in enumerate(lines):
            if line.startswith("——"):
                c = (255, 220, 180)
            else:
                c = (210, 225, 255)
            ts = self.font_small.render(line, True, c)
            self.screen.blit(ts, (sx + 14, info_y + i * 20))

    def _draw_status_bar(self):
        if self.status_timer <= 0 or not self.status_msg:
            return
        self.status_timer -= 1
        bar_h = 26
        bar_rect = pygame.Rect(CANVAS_LEFT, CANVAS_TOP + CANVAS_H - bar_h - 8,
                               CANVAS_W, bar_h)
        s = pygame.Surface((bar_rect.w, bar_rect.h), pygame.SRCALPHA)
        s.fill((20, 30, 60, 200))
        self.screen.blit(s, bar_rect.topleft)
        text = self.font_normal.render(self.status_msg, True, (255, 255, 220))
        self.screen.blit(text, (bar_rect.x + 12, bar_rect.y + 4))

    def _draw_about_dialog(self):
        if not self.show_about_dialog:
            return
        # 遮罩
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        dw, dh = 540, 340
        dx = (WINDOW_W - dw) // 2
        dy = (WINDOW_H - dh) // 2
        pygame.draw.rect(self.screen, (40, 50, 80), (dx, dy, dw, dh), border_radius=10)
        pygame.draw.rect(self.screen, (200, 220, 255), (dx, dy, dw, dh), 2, border_radius=10)

        lines = [
            ("计算机图形学课程设计 · 题目一", self.font_title, (255, 230, 180)),
            ("", self.font_normal, None),
            ("星空图绘制系统", self.font_title, (255, 255, 255)),
            ("", self.font_normal, None),
            ("使用底层图元算法绘制：", self.font_normal, (220, 230, 255)),
            ("    · Bresenham 直线生成算法", self.font_normal, (200, 220, 255)),
            ("    · 中点画圆算法（八对称性）", self.font_normal, (200, 220, 255)),
            ("    · 扫描线多边形填充算法", self.font_normal, (200, 220, 255)),
            ("", self.font_normal, None),
            ("合肥工业大学 · 计算机图形学课程", self.font_normal, (220, 230, 255)),
            ("", self.font_normal, None),
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

    # ---------------- 主循环 ----------------
    def run(self):
        while self.running:
            self.handle_events()
            self.scene.render()

            self.screen.fill((15, 20, 40))
            self._draw_toolbar()
            self.screen.blit(self.scene.surface, (CANVAS_LEFT, CANVAS_TOP))
            pygame.draw.rect(
                self.screen, (80, 100, 160),
                (CANVAS_LEFT - 1, CANVAS_TOP - 1, CANVAS_W + 2, CANVAS_H + 2), 1
            )
            self._draw_sidebar()
            self._draw_status_bar()
            self._draw_about_dialog()

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()
