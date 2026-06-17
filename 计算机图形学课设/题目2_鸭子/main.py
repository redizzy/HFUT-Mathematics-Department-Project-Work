# -*- coding: utf-8 -*-


import os
import math
import pygame

from algorithms import bresenham_line
from widgets import Button, Toggle, Slider
from transforms import (
    identity, translate, rotate, scale, compose, multiply,
    apply_point, matrix_to_str,
)
from duck import Duck


WINDOW_W = 1180
WINDOW_H = 740
TOOLBAR_H = 50
SIDEBAR_W = 280

CANVAS_LEFT = 10
CANVAS_TOP = TOOLBAR_H + 10
CANVAS_W = WINDOW_W - SIDEBAR_W - 30
CANVAS_H = WINDOW_H - TOOLBAR_H - 20

CANVAS_CX = CANVAS_W // 2
CANVAS_CY = CANVAS_H // 2

# 颜色
BG_TOP    = (170, 220, 240)   # 浅蓝（天空）
BG_BOT    = (230, 245, 250)   # 接近白
GRID_LIGHT = (200, 220, 235)
GRID_DARK  = (170, 195, 215)
AXIS_X     = (220, 70, 70)
AXIS_Y     = (60, 170, 90)
TEXT_DIM   = (60, 75, 100)


class DuckScene:
    """画布场景：背景 + 网格 + 坐标轴 + 鸭子 + 轨迹"""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.surface = pygame.Surface((w, h))
        self.duck = Duck()

        # 变换状态（鸭子相对画布中心）
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.angle_deg = 0.0
        self.scale_factor = 1.0

        # 切换项
        self.show_grid = True
        self.show_axes = True
        self.show_matrix = True
        self.show_trail = False
        self.animate_circle = False

        # 动画状态
        self.anim_t = 0.0

        # 轨迹点缓存
        self.trail = []
        self.max_trail = 80

        # 静态背景缓存
        self._bg_cache = None
        self._bg_sig = None

    # ---------- 状态变更 ----------
    def reset(self):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.angle_deg = 0.0
        self.scale_factor = 1.0
        self.trail.clear()

    def set_offset_x(self, v):
        self.offset_x = float(v)

    def set_offset_y(self, v):
        self.offset_y = float(v)

    def set_angle_deg(self, v):
        self.angle_deg = float(v)

    def set_scale(self, v):
        self.scale_factor = float(v)

    # ---------- 主变换矩阵 ----------
    def transform_matrix(self):
        """M = T(画布中心 + 偏移) · R(角度) · S(缩放)
        含义：先在原点缩放鸭子，再绕原点旋转，最后平移到世界位置。"""
        return compose(
            translate(CANVAS_CX + self.offset_x, CANVAS_CY + self.offset_y),
            rotate(math.radians(self.angle_deg)),
            scale(self.scale_factor),
        )

    # ---------- 像素辅助 ----------
    def _put(self, surf, pixels, color):
        w, h = surf.get_size()
        for x, y in pixels:
            if 0 <= x < w and 0 <= y < h:
                surf.set_at((x, y), color)

    # ---------- 背景 ----------
    def _render_bg(self):
        sig = (self.w, self.h, self.show_grid)
        if self._bg_sig == sig and self._bg_cache is not None:
            return
        cache = pygame.Surface((self.w, self.h))
        # 渐变天空
        for y in range(self.h):
            t = y / self.h
            c = (
                int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0])),
                int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1])),
                int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2])),
            )
            pygame.draw.line(cache, c, (0, y), (self.w, y))
        # 网格
        if self.show_grid:
            for x in range(0, self.w, 25):
                c = GRID_DARK if x % 100 == 0 else GRID_LIGHT
                pygame.draw.line(cache, c, (x, 0), (x, self.h))
            for y in range(0, self.h, 25):
                c = GRID_DARK if y % 100 == 0 else GRID_LIGHT
                pygame.draw.line(cache, c, (0, y), (self.w, y))
        self._bg_cache = cache
        self._bg_sig = sig

    # ---------- 坐标轴（鸭子本地坐标系经变换后的方向）----------
    def _draw_axes(self, M):
        ox, oy = apply_point(M, 0, 0)          # 局部原点
        xx, xy = apply_point(M, 80, 0)          # 局部 +x 方向终点
        yx, yy = apply_point(M, 0, 80)          # 局部 +y 方向终点
        ox, oy = int(round(ox)), int(round(oy))
        xx, xy = int(round(xx)), int(round(xy))
        yx, yy = int(round(yx)), int(round(yy))
        # 三像素加粗的"轴"
        for off in (-1, 0, 1):
            self._put(self.surface, bresenham_line(ox + off, oy, xx + off, xy), AXIS_X)
            self._put(self.surface, bresenham_line(ox, oy + off, xx, xy + off), AXIS_X)
            self._put(self.surface, bresenham_line(ox + off, oy, yx + off, yy), AXIS_Y)
            self._put(self.surface, bresenham_line(ox, oy + off, yx, yy + off), AXIS_Y)
        # 箭头三角（手画三角顶点）
        def arrow_head(tip, tail, color):
            tx, ty = tip
            dx, dy = tx - tail[0], ty - tail[1]
            L = math.hypot(dx, dy)
            if L < 1: return
            ux, uy = dx / L, dy / L
            # 法向
            nx, ny = -uy, ux
            p1 = (tx - 10 * ux + 5 * nx, ty - 10 * uy + 5 * ny)
            p2 = (tx - 10 * ux - 5 * nx, ty - 10 * uy - 5 * ny)
            from algorithms import scanline_fill_polygon
            verts = [(int(round(tx)), int(round(ty))),
                     (int(round(p1[0])), int(round(p1[1]))),
                     (int(round(p2[0])), int(round(p2[1])))]
            self._put(self.surface, scanline_fill_polygon(verts), color)
        arrow_head((xx, xy), (ox, oy), AXIS_X)
        arrow_head((yx, yy), (ox, oy), AXIS_Y)

    # ---------- 轨迹 ----------
    def _update_trail(self, M):
        cx, cy = apply_point(M, 0, 0)
        self.trail.append((int(cx), int(cy)))
        if len(self.trail) > self.max_trail:
            self.trail.pop(0)

    def _draw_trail(self):
        if len(self.trail) < 2:
            return
        for i in range(1, len(self.trail)):
            alpha = i / len(self.trail)
            c = (int(80 + 60 * alpha), int(120 + 80 * alpha), int(180 + 50 * alpha))
            self._put(self.surface,
                      bresenham_line(*self.trail[i - 1], *self.trail[i]), c)

    # ---------- 动画 ----------
    def _step_animation(self):
        if not self.animate_circle:
            return
        self.anim_t += 0.012
        R = 180
        self.offset_x = math.cos(self.anim_t) * R
        self.offset_y = math.sin(self.anim_t) * R
        # 让鸭子始终面向运动方向：切线 = (-sin, cos)，转成角度
        self.angle_deg = math.degrees(self.anim_t) + 90.0

    # ---------- 主渲染 ----------
    def render(self):
        self._step_animation()
        self._render_bg()
        self.surface.blit(self._bg_cache, (0, 0))

        M = self.transform_matrix()

        if self.show_trail:
            self._update_trail(M)
            self._draw_trail()

        self.duck.render(self.surface, M, self._put)

        if self.show_axes:
            self._draw_axes(M)


# =============================================================================
# 主应用
# =============================================================================
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("计算机图形学课程设计 · 题目二：鸭子绘制与变换")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        font_path = self._find_font()
        self.font_title  = self._load_font(font_path, 18, bold=True)
        self.font_normal = self._load_font(font_path, 14)
        self.font_small  = self._load_font(font_path, 12)
        self.font_mono   = self._load_font(
            r"C:\Windows\Fonts\consola.ttf" if os.path.exists(r"C:\Windows\Fonts\consola.ttf") else font_path,
            13
        )

        self.scene = DuckScene(CANVAS_W, CANVAS_H)
        self.dragging = False
        self.drag_start_mouse = (0, 0)
        self.drag_start_offset = (0.0, 0.0)
        self.show_about = False
        self.status_msg = ""
        self.status_timer = 0

        self._build_ui()
        self.running = True

    @staticmethod
    def _find_font():
        for p in [r"C:\Windows\Fonts\msyh.ttc",
                  r"C:\Windows\Fonts\msyhbd.ttc",
                  r"C:\Windows\Fonts\simhei.ttf",
                  r"C:\Windows\Fonts\simsun.ttc"]:
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

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        self.buttons = []
        self.toggles = []
        self.sliders = []

        x = 10
        for label, cb in [
            ("重置", self._on_reset),
            ("圆周动画", self._on_anim_toggle),
            ("保存图片", self._on_save),
            ("关于", self._on_about),
        ]:
            self.buttons.append(Button((x, 10, 90, 30), label, cb, self.font_normal))
            x += 98

        for label, attr, cb in [
            ("网格",   "show_grid",   lambda v: setattr(self.scene, "show_grid", v)
                                          or self.scene.__setattr__("_bg_sig", None)),
            ("坐标轴", "show_axes",   lambda v: setattr(self.scene, "show_axes", v)),
            ("轨迹",   "show_trail",  lambda v: setattr(self.scene, "show_trail", v)
                                          or (self.scene.trail.clear() if not v else None)),
            ("矩阵",   "show_matrix", lambda v: setattr(self.scene, "show_matrix", v)),
        ]:
            init = getattr(self.scene, attr)
            self.toggles.append(Toggle((x, 10, 70, 30), label, self.font_small, init, cb))
            x += 78

        # 侧边栏滑块
        sx = CANVAS_W + 30
        sy = TOOLBAR_H + 60
        self.sliders.append(Slider(
            (sx, sy, 240, 20), "旋转角度 (°)", self.font_normal,
            -180.0, 180.0, 0.0, self.scene.set_angle_deg
        ))
        self.sliders.append(Slider(
            (sx, sy + 60, 240, 20), "缩放比例", self.font_normal,
            0.5, 2.5, 1.0, self.scene.set_scale
        ))
        self.sliders.append(Slider(
            (sx, sy + 120, 240, 20), "平移 X", self.font_normal,
            -350.0, 350.0, 0.0, self.scene.set_offset_x
        ))
        self.sliders.append(Slider(
            (sx, sy + 180, 240, 20), "平移 Y", self.font_normal,
            -250.0, 250.0, 0.0, self.scene.set_offset_y
        ))

    def _sync_sliders_from_scene(self):
        """动画或键盘修改场景状态时，让滑块同步显示"""
        labels = ["旋转角度", "缩放", "平移 X", "平移 Y"]
        values = [self.scene.angle_deg, self.scene.scale_factor,
                  self.scene.offset_x, self.scene.offset_y]
        for s, v in zip(self.sliders, values):
            s.value = v

    # ---------------- 回调 ----------------
    def _on_reset(self):
        self.scene.reset()
        self._sync_sliders_from_scene()
        self._toast("已重置")

    def _on_anim_toggle(self):
        self.scene.animate_circle = not self.scene.animate_circle
        if self.scene.animate_circle:
            self.scene.anim_t = 0.0
            self._toast("圆周动画：开")
        else:
            self._toast("圆周动画：关")

    def _on_save(self):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out_dir, exist_ok=True)
        i = 0
        while True:
            p = os.path.join(out_dir, f"duck_{i:03d}.png")
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

    # ---------------- 事件 ----------------
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
                    self._on_anim_toggle()
                elif event.key == pygame.K_q:
                    self.scene.angle_deg = (self.scene.angle_deg - 5) % 360
                    if self.scene.angle_deg > 180:
                        self.scene.angle_deg -= 360
                elif event.key == pygame.K_e:
                    self.scene.angle_deg = (self.scene.angle_deg + 5) % 360
                    if self.scene.angle_deg > 180:
                        self.scene.angle_deg -= 360
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    self.scene.scale_factor = min(2.5, self.scene.scale_factor + 0.1)
                elif event.key == pygame.K_MINUS:
                    self.scene.scale_factor = max(0.5, self.scene.scale_factor - 0.1)
                elif event.key == pygame.K_LEFT:
                    self.scene.offset_x = max(-350, self.scene.offset_x - 20)
                elif event.key == pygame.K_RIGHT:
                    self.scene.offset_x = min(350, self.scene.offset_x + 20)
                elif event.key == pygame.K_UP:
                    self.scene.offset_y = max(-250, self.scene.offset_y - 20)
                elif event.key == pygame.K_DOWN:
                    self.scene.offset_y = min(250, self.scene.offset_y + 20)
                else:
                    continue
                self._sync_sliders_from_scene()
                continue

            # 弹窗时拦截鼠标
            if self.show_about:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.show_about = False
                continue

            # 拖拽（限定在画布范围内开始拖）
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if (CANVAS_LEFT <= mx <= CANVAS_LEFT + CANVAS_W
                    and CANVAS_TOP <= my <= CANVAS_TOP + CANVAS_H
                    and not self.scene.animate_circle):
                    # 看看是不是落在控件上（落在控件就不拖）
                    on_widget = any(s.rect.inflate(0, 24).collidepoint(event.pos)
                                    for s in self.sliders)
                    if not on_widget:
                        self.dragging = True
                        self.drag_start_mouse = (mx, my)
                        self.drag_start_offset = (self.scene.offset_x,
                                                  self.scene.offset_y)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                mx, my = event.pos
                dx = mx - self.drag_start_mouse[0]
                dy = my - self.drag_start_mouse[1]
                self.scene.offset_x = max(-350, min(350, self.drag_start_offset[0] + dx))
                self.scene.offset_y = max(-250, min(250, self.drag_start_offset[1] + dy))
                self._sync_sliders_from_scene()

            for b in self.buttons:
                b.handle_event(event)
            for t in self.toggles:
                t.handle_event(event)
            for s in self.sliders:
                s.handle_event(event)

    # ---------------- 画 UI ----------------
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

        for s in self.sliders:
            s.draw(self.screen)

        info_y = sy + 320
        lines = [
            "—— 当前变换矩阵 M ——",
            "M = T·R·S",
            "",
        ]
        if self.scene.show_matrix:
            mat_str = matrix_to_str(self.scene.transform_matrix(), precision=2)
            mat_lines = mat_str.split("\n")
        else:
            mat_lines = ["（矩阵显示已关）"]
        lines += mat_lines + ["", "—— 快捷键 ——",
                              "↑↓←→ 平移   Q E 旋转",
                              "+/−  缩放   R  重置",
                              "Space 圆周动画   ESC 退出",
                              ]
        for i, line in enumerate(lines):
            if line.startswith("——"):
                c = (255, 220, 180)
                f = self.font_small
            elif line.startswith("M ="):
                c = (220, 230, 255)
                f = self.font_normal
            elif "+" in line or "-" in line[:1] or "0." in line[:3] or any(d.isdigit() for d in line[:5]):
                c = (180, 255, 200)
                f = self.font_mono
            else:
                c = (210, 225, 255)
                f = self.font_small
            ts = f.render(line, True, c)
            self.screen.blit(ts, (sx + 14, info_y + i * 19))

    def _draw_status_bar(self):
        if self.status_timer <= 0 or not self.status_msg:
            return
        self.status_timer -= 1
        bar_h = 26
        bar = pygame.Rect(CANVAS_LEFT, CANVAS_TOP + CANVAS_H - bar_h - 8,
                          CANVAS_W, bar_h)
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

        dw, dh = 540, 320
        dx = (WINDOW_W - dw) // 2
        dy = (WINDOW_H - dh) // 2
        pygame.draw.rect(self.screen, (40, 50, 80), (dx, dy, dw, dh), border_radius=10)
        pygame.draw.rect(self.screen, (200, 220, 255), (dx, dy, dw, dh), 2, border_radius=10)

        lines = [
            ("计算机图形学课程设计 · 题目二", self.font_title, (255, 230, 180)),
            ("", None, None),
            ("鸭子绘制与几何变换", self.font_title, (255, 255, 255)),
            ("", None, None),
            ("亲自实现的算法：", self.font_normal, (220, 230, 255)),
            ("    · 二维齐次坐标变换矩阵（平移 / 旋转 / 缩放 / 复合）", self.font_normal, (200, 220, 255)),
            ("    · Bresenham 直线 / 中点画圆 / 扫描线多边形填充", self.font_normal, (200, 220, 255)),
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

    # ---------------- 主循环 ----------------
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
