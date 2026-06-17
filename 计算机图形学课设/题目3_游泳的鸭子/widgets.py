# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目一
Pygame 自定义 UI 控件：按钮、开关、滑块

Pygame 本身没有原生的菜单栏/工具栏控件，
这里实现一套轻量级 immediate-mode 风格的小部件，
用来组装顶部工具栏和右侧参数面板。
"""

import pygame


# ---------- 调色板 ----------
COLOR_BTN_BG = (70, 90, 160)
COLOR_BTN_HOVER = (110, 140, 230)
COLOR_BTN_BORDER = (200, 220, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_TOGGLE_ON = (80, 160, 100)
COLOR_TOGGLE_OFF = (90, 90, 110)
COLOR_TRACK = (60, 70, 100)
COLOR_FILL = (110, 140, 230)
COLOR_HANDLE = (220, 235, 255)
COLOR_HANDLE_RING = (90, 110, 180)
COLOR_LABEL = (220, 230, 255)


class Button:
    """一个矩形按钮，点击时调用 callback。"""

    def __init__(self, rect, text, callback, font):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.font = font
        self.hovered = False

    def draw(self, surface):
        c = COLOR_BTN_HOVER if self.hovered else COLOR_BTN_BG
        pygame.draw.rect(surface, c, self.rect, border_radius=5)
        pygame.draw.rect(surface, COLOR_BTN_BORDER, self.rect, width=1, border_radius=5)
        text_surf = self.font.render(self.text, True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()


class Toggle:
    """带 On/Off 状态的切换开关。"""

    def __init__(self, rect, text, font, initial=True, callback=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.state = initial
        self.callback = callback

    def draw(self, surface):
        c = COLOR_TOGGLE_ON if self.state else COLOR_TOGGLE_OFF
        pygame.draw.rect(surface, c, self.rect, border_radius=5)
        pygame.draw.rect(surface, COLOR_BTN_BORDER, self.rect, width=1, border_radius=5)
        prefix = "● " if self.state else "○ "
        text_surf = self.font.render(prefix + self.text, True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.state = not self.state
                if self.callback:
                    self.callback(self.state)


class Slider:
    """水平滑块。整数最小/最大值时输出整数，否则输出浮点。"""

    def __init__(self, rect, label, font, min_val, max_val, initial, callback=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial
        self.callback = callback
        self.dragging = False
        self._int_mode = isinstance(min_val, int) and isinstance(max_val, int)

    def _value_to_x(self):
        t = (self.value - self.min_val) / (self.max_val - self.min_val)
        return self.rect.x + int(t * self.rect.width)

    def _x_to_value(self, x):
        t = (x - self.rect.x) / max(1, self.rect.width)
        t = max(0.0, min(1.0, t))
        v = self.min_val + t * (self.max_val - self.min_val)
        return int(round(v)) if self._int_mode else v

    def _format_value(self):
        return f"{int(self.value)}" if self._int_mode else f"{self.value:.2f}"

    def draw(self, surface):
        # 上方标签
        label_text = f"{self.label}：{self._format_value()}"
        text_surf = self.font.render(label_text, True, COLOR_LABEL)
        surface.blit(text_surf, (self.rect.x, self.rect.y - 22))

        # 轨道
        track = pygame.Rect(self.rect.x, self.rect.centery - 3, self.rect.width, 6)
        pygame.draw.rect(surface, COLOR_TRACK, track, border_radius=3)

        # 已填充部分
        handle_x = self._value_to_x()
        filled_w = handle_x - self.rect.x
        if filled_w > 0:
            filled = pygame.Rect(self.rect.x, self.rect.centery - 3, filled_w, 6)
            pygame.draw.rect(surface, COLOR_FILL, filled, border_radius=3)

        # 滑块手柄
        pygame.draw.circle(surface, COLOR_HANDLE, (handle_x, self.rect.centery), 9)
        pygame.draw.circle(surface, COLOR_HANDLE_RING, (handle_x, self.rect.centery), 9, width=2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 扩大点击命中区域（包含手柄上下各 10px）
            hit = self.rect.inflate(0, 24)
            if hit.collidepoint(event.pos):
                self.dragging = True
                old = self.value
                self.value = self._x_to_value(event.pos[0])
                if self.callback and self.value != old:
                    self.callback(self.value)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            old = self.value
            self.value = self._x_to_value(event.pos[0])
            if self.callback and self.value != old:
                self.callback(self.value)
