"""PyOS —— 基于 Python + Flet 的模拟操作系统入口。"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import flet as ft

from src.ui.desktop import Desktop


def main(page: ft.Page):
    page.title = "PyOS 1.0"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#020617"
    page.window_width = 1180
    page.window_height = 760
    page.window_min_width = 860
    page.window_min_height = 560
    Desktop(page)


if __name__ == "__main__":
    ft.run(main)