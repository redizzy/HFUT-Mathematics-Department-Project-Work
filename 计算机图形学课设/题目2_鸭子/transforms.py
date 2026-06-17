# -*- coding: utf-8 -*-
"""
计算机图形学课程设计 · 题目二
二维几何变换（齐次坐标 3×3 矩阵）

理论：
  二维点 (x, y) 用齐次坐标表示为 [x, y, 1]^T。所有变换都可表示
  为左乘一个 3×3 矩阵，便于复合（矩阵相乘）：

  平移 T(tx, ty) =   [1  0  tx]
                    [0  1  ty]
                    [0  0   1]

  旋转 R(θ)     =   [cosθ  -sinθ  0]
                    [sinθ   cosθ  0]
                    [ 0      0    1]

  缩放 S(sx, sy)=   [sx  0   0]
                    [0   sy  0]
                    [0   0   1]

  绕任意点 (cx, cy) 旋转：
      R_around(θ, cx, cy) = T(cx, cy) · R(θ) · T(-cx, -cy)

  复合：变换顺序"先 S 后 R 再 T"对应矩阵
      M = T · R · S
  作用到点：[x', y', 1]^T = M · [x, y, 1]^T
"""

import math


# ---------- 基本矩阵 ----------
def identity():
    return [[1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]]


def translate(tx, ty):
    """平移矩阵"""
    return [[1.0, 0.0, tx],
            [0.0, 1.0, ty],
            [0.0, 0.0, 1.0]]


def rotate(theta):
    """绕原点旋转 θ 弧度"""
    c, s = math.cos(theta), math.sin(theta)
    return [[c,  -s, 0.0],
            [s,   c, 0.0],
            [0.0, 0.0, 1.0]]


def scale(sx, sy=None):
    """缩放矩阵（sy 缺省时各向同性）"""
    if sy is None:
        sy = sx
    return [[sx,  0.0, 0.0],
            [0.0, sy,  0.0],
            [0.0, 0.0, 1.0]]


# ---------- 矩阵运算 ----------
def multiply(A, B):
    """3×3 矩阵乘法 A·B"""
    return [
        [sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def compose(*mats):
    """从左到右连乘：compose(M1, M2, M3) = M1 · M2 · M3
    几何含义：变换先作用 M3、再作用 M2、最后 M1"""
    result = identity()
    for M in mats:
        result = multiply(result, M)
    return result


# ---------- 应用变换 ----------
def apply_point(M, x, y):
    """对单点应用变换：[x, y, 1]^T → [x', y', 1]^T"""
    nx = M[0][0] * x + M[0][1] * y + M[0][2]
    ny = M[1][0] * x + M[1][1] * y + M[1][2]
    return nx, ny


def apply_points(M, points):
    """对点列表批量应用变换，返回新的点列表"""
    return [apply_point(M, x, y) for x, y in points]


# ---------- 复合变换便利函数 ----------
def rotate_around(theta, cx, cy):
    """绕任意点 (cx, cy) 旋转 θ"""
    return compose(translate(cx, cy), rotate(theta), translate(-cx, -cy))


def scale_around(sx, sy, cx, cy):
    """绕任意点 (cx, cy) 缩放"""
    return compose(translate(cx, cy), scale(sx, sy), translate(-cx, -cy))


def matrix_to_str(M, precision=2):
    """把矩阵格式化成多行字符串，便于在 UI 中显示"""
    rows = []
    for row in M:
        rows.append("  ".join(f"{v:+.{precision}f}" for v in row))
    return "\n".join(rows)
