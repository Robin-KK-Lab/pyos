"""PyOS 桌面环境：窗口 / 桌面 / Dock / 顶栏 / 浮层 / 多用户。"""
import asyncio
import json
import math
import os
import random
import re
import subprocess
import time

import flet as ft
import psutil

from src.core.fs import VirtualFS
from src.core.shell import Shell
from src.ui.apps import AboutApp, FileManagerApp, NotepadApp, TerminalApp

try:
    from src.ui.apps_extra import CalculatorApp
except Exception:
    CalculatorApp = None
try:
    from src.ui.spotlight import Spotlight
except Exception:
    Spotlight = None
try:
    from src.ui.dynamic_island import DynamicIsland
except Exception:
    DynamicIsland = None
try:
    from src.ui.system_actions import LockScreen, PowerOverlay
except Exception:
    LockScreen = None
    PowerOverlay = None
try:
    from src.ui.control_center import ControlCenter
except Exception:
    ControlCenter = None
try:
    from src.ui.notification_center import NotificationCenter
except Exception:
    NotificationCenter = None

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(os.path.dirname(_DATA_DIR))
_DATA_PATH = os.path.join(_ROOT_DIR, "pyos_data.json")

DOCK_CONF = "/etc/pyos/dock.json"
MENUBAR_H = 28

DESKTOP_APPS = [a for a in [TerminalApp, FileManagerApp, NotepadApp,
                            CalculatorApp, AboutApp] if a is not None]

ICON_W = 100
ICON_H = 108
GRID_X0 = 20
GRID_Y0 = 20
GRID_GAP_X = 8
GRID_GAP_Y = 4
ROWS_PER_COL = 4


# ============================================================ Window
class Window(ft.Container):
    def __init__(self, os_ctx, app, body, width=680, height=460):
        super().__init__()
        self.os = os_ctx
        self.app = app
        self.maximized = False
        self._restore = None

        idx = len(os_ctx.windows) % 6
        self.left = 130 + idx * 34
        self.top = MENUBAR_H + 46 + idx * 28
        self.width = width
        self.height = height
        self.bgcolor = "#0f172a"
        self.border_radius = ft.BorderRadius.all(12)
        self.border = ft.Border.all(1, "#334155")
        self.clip_behavior = ft.ClipBehavior.ANTI_ALIAS
        self.shadow = ft.BoxShadow(blur_radius=30, color="#00000099",
                                   offset=ft.Offset(0, 12))

        self.opacity = 0
        self.scale = 0.92
        self.animate_opacity = ft.Animation(180, ft.AnimationCurve.EASE_OUT)
        self.animate_scale = ft.Animation(220, ft.AnimationCurve.EASE_OUT)

        title_bar = ft.Container(
            height=40, bgcolor="#1e293b",
            padding=ft.Padding.only(left=12, right=8),
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            content=ft.Row(
                controls=[
                    ft.Icon(app.icon, size=16, color="#60a5fa"),
                    ft.Text(app.name, size=13, color="#e2e8f0",
                            weight=ft.FontWeight.W_600),
                    ft.Container(expand=True),
                    self._dot(ft.Icons.REMOVE, "#fbbf24", self.minimize),
                    self._dot(ft.Icons.CROP_SQUARE, "#34d399",
                              self.toggle_max),
                    self._dot(ft.Icons.CLOSE, "#f87171", self.close)],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER))

        title_drag = ft.GestureDetector(
            content=title_bar,
            on_pan_update=self._on_drag,
            on_double_tap=lambda e: self.toggle_max(),
            on_tap_down=lambda e: self.bring_to_front())

        body_box = ft.Container(content=body, expand=True, padding=0)
        inner = ft.Column(controls=[title_drag, body_box],
                          spacing=0, expand=True)

        E, C = 5, 14
        inv = lambda: ft.Container(bgcolor="#01000000", expand=True)
        edges = [
            ft.GestureDetector(left=C, right=C, top=0, height=E,
                on_pan_update=lambda ev: self._resize("top", ev),
                content=inv()),
            ft.GestureDetector(left=C, right=C, bottom=0, height=E,
                on_pan_update=lambda ev: self._resize("bottom", ev),
                content=inv()),
            ft.GestureDetector(left=0, top=C, bottom=C, width=E,
                on_pan_update=lambda ev: self._resize("left", ev),
                content=inv()),
            ft.GestureDetector(right=0, top=C, bottom=C, width=E,
                on_pan_update=lambda ev: self._resize("right", ev),
                content=inv()),
            ft.GestureDetector(left=0, top=0, width=C, height=C,
                on_pan_update=lambda ev: self._resize("tl", ev),
                content=inv()),
            ft.GestureDetector(right=0, top=0, width=C, height=C,
                on_pan_update=lambda ev: self._resize("tr", ev),
                content=inv()),
            ft.GestureDetector(left=0, bottom=0, width=C, height=C,
                on_pan_update=lambda ev: self._resize("bl", ev),
                content=inv()),
            ft.GestureDetector(right=0, bottom=0, width=C, height=C,
                on_pan_update=lambda ev: self._resize("br", ev),
                content=inv()),
        ]
        self.content = ft.Stack(
            controls=[ft.Container(content=inner, left=0, top=0,
                                   right=0, bottom=0)] + edges,
            expand=True, clip_behavior=ft.ClipBehavior.NONE)

    def _dot(self, icon, color, handler):
        return ft.Container(
            width=22, height=22, border_radius=11, bgcolor=color,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e: handler(),
            content=ft.Icon(icon, size=12, color="#0f172a"))

    @staticmethod
    def _delta(e):
        for name in ("primary_delta", "local_delta", "global_delta"):
            d = getattr(e, name, None)
            if d is not None:
                dx = getattr(d, "x", 0) or 0
                dy = getattr(d, "y", 0) or 0
                if dx or dy:
                    return dx, dy
        return (getattr(e, "delta_x", 0) or 0,
                getattr(e, "delta_y", 0) or 0)

    def _on_drag(self, e):
        if self.maximized:
            return
        dx, dy = self._delta(e)
        self.left = (self.left or 0) + dx
        t = (self.top or 0) + dy
        if t < MENUBAR_H:
            t = MENUBAR_H
        self.top = t
        try:
            self.update()
        except Exception:
            pass

    def _resize(self, direction, e):
        if self.maximized:
            return
        dx, dy = self._delta(e)
        if not dx and not dy:
            return
        is_top = direction in ("top", "tl", "tr")
        is_bottom = direction in ("bottom", "bl", "br")
        is_left = direction in ("left", "tl", "bl")
        is_right = direction in ("right", "tr", "br")
        L, T, W, H = self.left, self.top, self.width, self.height
        if is_top:
            nt = T + dy
            nh = H - dy
            if nh >= 200 and nt >= MENUBAR_H:
                self.top = nt
                self.height = nh
        if is_bottom:
            nh = H + dy
            if nh >= 200:
                self.height = nh
        if is_left:
            nl = L + dx
            nw = W - dx
            if nw >= 320:
                self.left = nl
                self.width = nw
        if is_right:
            nw = W + dx
            if nw >= 320:
                self.width = nw
        try:
            self.update()
        except Exception:
            pass

    def minimize(self):
        if not self.visible:
            return
        L0, T0 = self.left or 0, self.top or 0
        try:
            self.animate_scale = ft.Animation(320, ft.AnimationCurve.EASE_IN)
            self.animate_opacity = ft.Animation(320, ft.AnimationCurve.EASE_IN)
            try:
                self.animate_blur = ft.Animation(
                    320, ft.AnimationCurve.EASE_IN)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.scale = ft.Scale(0.01, alignment=ft.Alignment.CENTER)
        except Exception:
            self.scale = 0.01
        self.opacity = 0.0
        try:
            self.blur = ft.Blur(20, 20)
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass

        async def _finish():
            try:
                await asyncio.sleep(0.34)
            except Exception:
                pass
            try:
                self.visible = False
                self.left = L0
                self.top = T0
                try:
                    self.scale = ft.Scale(1.0,
                                          alignment=ft.Alignment.CENTER)
                except Exception:
                    self.scale = 1.0
                self.opacity = 1.0
                self.blur = ft.Blur(0, 0)
                self.update()
            except Exception:
                pass
            try:
                self.os.refresh_dock()
            except Exception:
                pass

        try:
            self.os.page.run_task(_finish)
        except Exception:
            self.visible = False

    def toggle_max(self):
        if self.maximized:
            if self._restore:
                self.left, self.top, self.width, self.height = self._restore
            self.border_radius = ft.BorderRadius.all(12)
            self.maximized = False
        else:
            self._restore = (self.left, self.top, self.width, self.height)
            self.left = 0
            self.top = MENUBAR_H
            self.width = self.os.page.width or 1180
            self.height = max(320, (self.os.page.height or 760) - MENUBAR_H)
            self.border_radius = ft.BorderRadius.all(0)
            self.maximized = True
        try:
            self.update()
        except Exception:
            pass
        self.os.refresh_dock()

    def close(self):
        try:
            self.animate_scale = ft.Animation(180, ft.AnimationCurve.EASE_IN)
            self.animate_opacity = ft.Animation(160, ft.AnimationCurve.EASE_IN)
            self.scale = 0.88
            self.opacity = 0.0
            self.update()
        except Exception:
            pass

        async def _finish():
            try:
                await asyncio.sleep(0.19)
            except Exception:
                pass
            try:
                self.os.close_window(self)
            except Exception:
                pass

        try:
            self.os.page.run_task(_finish)
        except Exception:
            try:
                self.os.close_window(self)
            except Exception:
                pass

    def bring_to_front(self):
        try:
            self.os.win_layer.controls.remove(self)
            self.os.win_layer.controls.append(self)
            self.os.win_layer.update()
        except Exception:
            pass
        try:
            self.os.set_active_app(self.app.name)
        except Exception:
            pass
        if self.scale != 1.0 or self.opacity != 1.0:
            self.scale = 1.0
            self.opacity = 1.0
            try:
                self.update()
            except Exception:
                pass


# ============================================================ Desktop
class Desktop:
    def __init__(self, page: ft.Page):
        self.page = page
        self.fs = VirtualFS(data_path=_DATA_PATH)
        self.shell = Shell(self.fs)
        self.shell.user = self.fs.current_user
        self.windows = []

        self.editing_mode = False
        self.shake_items = []
        self.desktop_items = []
        self._desktop_snapshot = None
        self._dragging_path = None

        self.win_layer = ft.Stack(expand=True, controls=[])
        self.dock_row = ft.Row(controls=[], spacing=4,
                              alignment=ft.MainAxisAlignment.CENTER,
                              vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.dock_preview_row = ft.Row(controls=[], spacing=8)
        self.dock_preview = ft.Container(
            left=0, top=560, width=200, height=120,
            scale=0.9,
            animate_scale=ft.Animation(360, ft.AnimationCurve.BOUNCE_OUT),
            bgcolor="#0b1120ee",
            border_radius=ft.BorderRadius.all(14),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(10),
            shadow=ft.BoxShadow(blur_radius=28, color="#000000cc",
                                offset=ft.Offset(0, 10)),
            visible=False,
            on_hover=self._on_dock_preview_hover,
            content=self.dock_preview_row)
        self.dock_icons = []
        self.pinned = self._load_pinned()
        self._app_icons_ordered = []

        self.clock_text = ft.Text("", size=12, color="#e2e8f0")
        self.active_app_name = "桌面"
        self.app_menu_items = ["文件", "编辑", "显示", "前往", "窗口", "帮助"]

        # 浮层实例
        self.spotlight = Spotlight(self) if Spotlight else None
        self.dynamic_island = DynamicIsland(self) if DynamicIsland else None
        self.lock_screen = LockScreen(self) if LockScreen else None
        self.power_overlay = PowerOverlay(self) if PowerOverlay else None
        self.control_center = ControlCenter(self) if ControlCenter else None
        self.notification_center = (NotificationCenter(self)
                                    if NotificationCenter else None)

        try:
            self.page.on_keyboard_event = self._handle_key
        except Exception:
            pass

        self._build_ui()
        self._rebuild_desktop_items()
        self.refresh_dock()

        try:
            self.page.run_task(self._clock_loop)
            self.page.run_task(self._desktop_sync_loop)
            if self.lock_screen:
                self.page.run_task(self.lock_screen.clock_loop)
        except Exception:
            pass

    # -------------------------------------------------------- 界面
    def _build_ui(self):
        background = ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=["#0b1120", "#111c34", "#1e1b4b"]))

        self.desktop_layer = ft.Stack(expand=True, controls=[
            ft.Container(expand=True, bgcolor="#00000000",
                         on_click=self._on_desktop_bg_click)])
        desktop_drop = ft.DragTarget(
            group="fm", content=self.desktop_layer,
            on_accept=self._on_desktop_drop)

        # 用户头像
        self.user_avatar = ft.Container(
            width=32, height=32, border_radius=ft.BorderRadius.all(16),
            bgcolor="#3b82f6", alignment=ft.Alignment.CENTER,
            on_click=self._toggle_user_menu, tooltip="当前用户",
            content=ft.Text(self.fs.current_user[0].upper(), size=14,
                            color="#ffffff", weight=ft.FontWeight.BOLD))

        # 右键菜单
        self.context_backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000", visible=False,
            content=ft.Container(expand=True),
            on_click=self._hide_context_menu)
        self.context_menu = ft.Container(
            width=200, left=0, bottom=122, height=200, visible=False,
            scale=1.0,
            animate_scale=ft.Animation(360, ft.AnimationCurve.BOUNCE_OUT),
            bgcolor="#1e293bee",
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(1, "#475569"),
            padding=ft.Padding.all(4),
            shadow=ft.BoxShadow(blur_radius=24, color="#000000cc",
                                offset=ft.Offset(0, 10)),
            content=ft.Column([], spacing=1, tight=True))

        # 通用 popup
        self.popup_backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000", visible=False,
            content=ft.Container(expand=True),
            on_click=self._hide_popup)
        self.popup_menu = ft.Container(
            left=0, top=MENUBAR_H + 4, width=220, visible=False,
            scale=1.0,
            animate_scale=ft.Animation(360, ft.AnimationCurve.BOUNCE_OUT),
            bgcolor="#1e293bf5",
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(1, "#475569"),
            padding=ft.Padding.all(4),
            shadow=ft.BoxShadow(blur_radius=24, color="#000000cc",
                                offset=ft.Offset(0, 10)),
            content=ft.Column([], spacing=1, tight=True))

        # 开始菜单背板
        self.start_backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000", content=ft.Container(expand=True),
            visible=False, on_click=self._on_start_backdrop_click)

        # 开始菜单
        self.start_menu = ft.Container(
            left=16, bottom=100, width=280,
            bgcolor="#0f1b30",
            border_radius=ft.BorderRadius.all(14),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(8), visible=False,
            opacity=0, scale=0.94,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT),
            shadow=ft.BoxShadow(blur_radius=40, color="#000000ff",
                                offset=ft.Offset(0, 12), spread_radius=2),
            content=ft.Column(
                controls=[self._start_item(a) for a in DESKTOP_APPS] + [
                    ft.Divider(height=1, color="#334155"),
                    self._start_power_row()],
                spacing=2, tight=True))

        # 电源二级菜单
        self.power_submenu = ft.Container(
            left=16 + 280 + 8, bottom=140, width=170,
            bgcolor="#0f1b30",
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(6), visible=False,
            opacity=0, scale=1.0,
            animate_scale=ft.Animation(360, ft.AnimationCurve.BOUNCE_OUT),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(blur_radius=24, color="#000000cc",
                                offset=ft.Offset(0, 8)),
            on_hover=self._on_power_submenu_hover,
            content=ft.Column(
                controls=[
                    self._power_sub_item("锁屏", ft.Icons.LOCK_OUTLINE,
                                         self._do_lock),
                    self._power_sub_item("睡眠", ft.Icons.BEDTIME_OUTLINED,
                                         self._do_sleep),
                    ft.Divider(height=1, color="#334155"),
                    self._power_sub_item("重启", ft.Icons.RESTART_ALT,
                                         self._do_restart),
                    self._power_sub_item("关机",
                                         ft.Icons.POWER_SETTINGS_NEW,
                                         self._do_shutdown, danger=True)],
                spacing=2, tight=True))

        # 用户菜单
        self.user_menu = self._build_user_menu()

        # 顶栏
        menubar = self._build_menubar()

        # Dock
        dock = self._build_dock()

        # Stack 组装
        stack_controls = [
            background,
            desktop_drop,
            self.win_layer,
            self.user_menu,
            dock,
            self.dock_preview,
            menubar,
            self.context_backdrop,
            self.context_menu,
            self.popup_backdrop,
            self.popup_menu,
            self.start_backdrop,
            self.start_menu,
            self.power_submenu,
        ]

        if self.spotlight:
            stack_controls.append(self.spotlight.overlay)
        if self.dynamic_island:
            stack_controls.append(self.dynamic_island.backdrop)
            stack_controls.append(self.dynamic_island.wrapper)
        if self.lock_screen:
            stack_controls.append(self.lock_screen.overlay)
        if self.power_overlay:
            stack_controls.append(self.power_overlay.overlay)
        if self.control_center:
            stack_controls.append(self.control_center.backdrop)
            stack_controls.append(self.control_center.panel)
        if self.notification_center:
            stack_controls.append(self.notification_center.backdrop)
            stack_controls.append(self.notification_center.panel)

        self.page.add(ft.Stack(expand=True, controls=stack_controls))

    # -------------------------------------------------------- 顶栏
    def _build_menubar(self):
        self.menubar_left = ft.Row(controls=[], spacing=0)
        self._render_menubar_left()

        right_items = []
        right_items.append(self._wifi_widget())
        right_items.append(self._status_icon(ft.Icons.VOLUME_UP,
                                             self._on_status_volume))
        right_items.append(self._battery_widget())
        right_items.append(self._status_clock_icon())
        right_items.append(ft.Container(width=4))
        if self.control_center:
            right_items.append(self._control_center_icon())
        right_items.append(self.user_avatar)
        right_items.append(ft.Container(width=8))

        right = ft.Row(
            controls=right_items, spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

        return ft.Container(
            left=0, right=0, top=0, height=MENUBAR_H,
            bgcolor="#0b1120f2",
            border=ft.Border.only(bottom=ft.BorderSide(1, "#1e293b")),
            padding=ft.Padding.symmetric(horizontal=10),
            content=ft.Row(
                controls=[self.menubar_left,
                          ft.Container(expand=True), right],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def _render_menubar_left(self):
        items = []
        items.append(ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3),
            border_radius=ft.BorderRadius.all(4),
            on_click=lambda e: self.toast("PyOS 1.0"),
            content=ft.Icon(ft.Icons.MEMORY, size=14, color="#e2e8f0")))
        items.append(ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            content=ft.Text(self.active_app_name, size=13,
                            color="#f1f5f9", weight=ft.FontWeight.W_600)))
        for name in self.app_menu_items:
            items.append(self._menubar_item(name))
        self.menubar_left.controls = items
        try:
            self.menubar_left.update()
        except Exception:
            pass

    def _menubar_item(self, name):
        box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3),
            border_radius=ft.BorderRadius.all(4),
            content=ft.Text(name, size=13, color="#e2e8f0"))

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass

        def on_tap(e):
            self._show_menu_dropdown(name)

        box.on_hover = on_hover
        return ft.GestureDetector(on_tap_down=on_tap, content=box)

    def set_active_app(self, name, menu_items=None):
        self.active_app_name = name or "桌面"
        if menu_items:
            self.app_menu_items = menu_items
        elif name in (None, "桌面"):
            self.app_menu_items = ["文件", "编辑", "显示", "前往",
                                   "窗口", "帮助"]
        else:
            self.app_menu_items = ["文件", "编辑", "显示", "窗口", "帮助"]
        self._render_menubar_left()

    def reset_active_app(self):
        self.set_active_app("桌面")

    # -------------------------------------------------------- 顶栏 - 组件
    def _wifi_widget(self):
        self._wifi_icon = ft.Icon(ft.Icons.WIFI, size=13, color="#cbd5e1")
        box = ft.Container(width=26, height=20,
                           border_radius=ft.BorderRadius.all(4),
                           alignment=ft.Alignment.CENTER,
                           content=self._wifi_icon)

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass

        def on_tap(e):
            x = self._extract_anchor_x(e) or 0
            self._on_status_wifi(x)

        box.on_hover = on_hover
        try:
            self.page.run_task(self._wifi_loop)
        except Exception:
            pass
        return ft.GestureDetector(on_tap_down=on_tap, content=box)

    async def _wifi_loop(self):
        while True:
            try:
                self._refresh_wifi()
            except Exception:
                pass
            await asyncio.sleep(8)

    def _refresh_wifi(self):
        try:
            stats = psutil.net_if_stats()
            skip = ("Loopback", "lo", "vEthernet", "VMware",
                    "VirtualBox", "Bluetooth", "veth", "docker")
            active = False
            for name, s in stats.items():
                if any(name.startswith(p) for p in skip):
                    continue
                if getattr(s, "isup", False):
                    active = True
                    break
        except Exception:
            active = True
        self._wifi_icon.name = (ft.Icons.WIFI if active
                                else ft.Icons.WIFI_OFF)
        self._wifi_icon.color = "#cbd5e1" if active else "#64748b"
        try:
            self._wifi_icon.update()
        except Exception:
            pass

    def _battery_widget(self):
        self._battery_text = ft.Text("", size=11, color="#cbd5e1")
        self._battery_icon = ft.Icon(ft.Icons.BATTERY_FULL, size=13,
                                     color="#cbd5e1")
        box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
            border_radius=ft.BorderRadius.all(4),
            content=ft.Row(controls=[self._battery_icon, self._battery_text],
                           spacing=4,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass

        def on_tap(e):
            x = self._extract_anchor_x(e) or 0
            self._on_status_battery(x)

        box.on_hover = on_hover
        try:
            self.page.run_task(self._battery_loop)
        except Exception:
            pass
        return ft.GestureDetector(on_tap_down=on_tap, content=box)

    async def _battery_loop(self):
        while True:
            try:
                self._refresh_battery()
            except Exception:
                pass
            await asyncio.sleep(5)

    def _refresh_battery(self):
        sysp = self._system_power_status()
        if sysp is not None:
            pct = int(sysp["percent"])
            plugged = bool(sysp["plugged"])
            self._battery_text.value = "{}%".format(pct)
            if plugged:
                self._battery_icon.name = ft.Icons.BATTERY_CHARGING_FULL
                self._battery_icon.color = "#4ade80"
            elif pct >= 80:
                self._battery_icon.name = ft.Icons.BATTERY_FULL
                self._battery_icon.color = "#cbd5e1"
            elif pct >= 30:
                self._battery_icon.name = ft.Icons.BATTERY_5_BAR
                self._battery_icon.color = "#cbd5e1"
            elif pct >= 10:
                self._battery_icon.name = ft.Icons.BATTERY_2_BAR
                self._battery_icon.color = "#fbbf24"
            else:
                self._battery_icon.name = ft.Icons.BATTERY_ALERT
                self._battery_icon.color = "#f87171"
            try:
                self._battery_icon.update()
                self._battery_text.update()
            except Exception:
                pass
            return

        try:
            bat = psutil.sensors_battery()
        except Exception:
            bat = None
        if bat is None:
            self._battery_icon.name = ft.Icons.POWER
            self._battery_icon.color = "#cbd5e1"
            self._battery_text.value = ""
        else:
            pct = int(bat.percent)
            self._battery_text.value = "{}%".format(pct)
            if bat.power_plugged:
                self._battery_icon.name = ft.Icons.BATTERY_CHARGING_FULL
                self._battery_icon.color = "#4ade80"
            elif pct >= 80:
                self._battery_icon.name = ft.Icons.BATTERY_FULL
                self._battery_icon.color = "#cbd5e1"
            elif pct >= 30:
                self._battery_icon.name = ft.Icons.BATTERY_5_BAR
                self._battery_icon.color = "#cbd5e1"
            elif pct >= 10:
                self._battery_icon.name = ft.Icons.BATTERY_2_BAR
                self._battery_icon.color = "#fbbf24"
            else:
                self._battery_icon.name = ft.Icons.BATTERY_ALERT
                self._battery_icon.color = "#f87171"
        try:
            self._battery_icon.update()
            self._battery_text.update()
        except Exception:
            pass

    @staticmethod
    def _system_power_status():
        try:
            import ctypes
            from ctypes import wintypes

            class SPS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", wintypes.BYTE),
                    ("BatteryFlag", wintypes.BYTE),
                    ("BatteryLifePercent", wintypes.BYTE),
                    ("SystemStatusFlag", wintypes.BYTE),
                    ("BatteryLifeTime", wintypes.DWORD),
                    ("BatteryFullLifeTime", wintypes.DWORD)]

            s = SPS()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(
                    ctypes.byref(s)):
                return None
            pct = s.BatteryLifePercent
            if pct == 255:
                return None
            life = s.BatteryLifeTime
            life_secs = None
            if life not in (0xFFFFFFFF, 0):
                life_secs = int(life)
            return {
                "percent": int(pct),
                "plugged": s.ACLineStatus == 1,
                "life_secs": life_secs}
        except Exception:
            return None

    def _status_icon(self, icon, handler):
        box = ft.Container(
            width=26, height=20,
            border_radius=ft.BorderRadius.all(4),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=13, color="#cbd5e1"))

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass

        def on_tap(e):
            x = self._extract_anchor_x(e) or 0
            handler(x)

        box.on_hover = on_hover
        return ft.GestureDetector(on_tap_down=on_tap, content=box)

    def _status_clock_icon(self):
        box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(4),
            content=self.clock_text)

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass

        def on_tap(e):
            if self.notification_center:
                self.notification_center.toggle()

        box.on_hover = on_hover
        return ft.GestureDetector(on_tap=on_tap, content=box)


    def _control_center_icon(self):
        box = ft.Container(
            width=26, height=20,
            border_radius=ft.BorderRadius.all(4),
            alignment=ft.Alignment.CENTER,
            on_click=lambda e: self.control_center.toggle()
            if self.control_center else None,
            content=ft.Icon(ft.Icons.TUNE, size=13, color="#cbd5e1"))

        def on_hover(e):
            try:
                box.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                box.update()
            except Exception:
                pass
        box.on_hover = on_hover
        return box

    @staticmethod
    def _extract_anchor_x(e):
        if e is None:
            return None
        pos = getattr(e, "global_position", None)
        if pos is not None:
            return getattr(pos, "x", None)
        pos = getattr(e, "local_position", None)
        if pos is not None:
            return getattr(pos, "x", None)
        return None

    # -------------------------------------------------------- 顶栏面板
    def _on_status_wifi(self, anchor_x):
        out = self._run_netsh(["wlan", "show", "interfaces"])
        current = None
        for line in (out or "").splitlines():
            s = line.strip()
            if s.startswith("SSID") and not s.startswith("BSSID") and ":" in s:
                v = s.split(":", 1)[1].strip()
                if v:
                    current = v
                    break

        items = []
        if current:
            items.append((current + "  (已连接)", ft.Icons.WIFI,
                          lambda: self.toast("已是当前网络"),
                          "已连接", True))
        else:
            items.append(("未连接", ft.Icons.WIFI_OFF, None, None, False))
        items.append(("---", None, None))
        items.append(("刷新", ft.Icons.REFRESH,
                      lambda: self._on_status_wifi(anchor_x)))
        self._show_popup(items, anchor_x, align="right", width=260)

    @staticmethod
    def _run_netsh(args):
        try:
            r = subprocess.run(["netsh"] + args, capture_output=True,
                               text=True, encoding="gbk",
                               errors="ignore", timeout=4)
            return r.stdout or ""
        except Exception:
            return ""

    def _on_status_volume(self, anchor_x):
        vol = self._get_volume_interface()
        if vol is None:
            content = ft.Container(
                padding=ft.Padding.all(14),
                content=ft.Column(
                    controls=[
                        ft.Text("音量 (pycaw 未安装)", size=12,
                                color="#94a3b8"),
                        ft.Slider(min=0, max=100, value=50, width=180,
                                  active_color="#3b82f6")],
                    spacing=10, tight=True))
            self._show_popup(content, anchor_x, align="right", width=260)
            return

        try:
            cur = int(vol.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            cur = 50
        level_text = ft.Text("{}%".format(cur), size=20,
                             weight=ft.FontWeight.BOLD, color="#e2e8f0")
        slider = ft.Slider(min=0, max=100, value=cur, width=180,
                           active_color="#3b82f6")

        def on_change(e):
            try:
                v = int(slider.value)
                vol.SetMasterVolumeLevelScalar(v / 100.0, None)
                level_text.value = "{}%".format(v)
                level_text.update()
            except Exception:
                pass
        slider.on_change = on_change

        content = ft.Container(
            padding=ft.Padding.all(14),
            content=ft.Column(
                controls=[
                    ft.Row([ft.Text("音量", size=12, color="#94a3b8"),
                            ft.Container(expand=True), level_text]),
                    slider],
                spacing=10, tight=True))
        self._show_popup(content, anchor_x, align="right", width=260)

    def _get_volume_interface(self):
        try:
            from pycaw.pycaw import AudioUtilities
            sp = AudioUtilities.GetSpeakers()
            if sp is None:
                return None
            if hasattr(sp, "EndpointVolume"):
                v = sp.EndpointVolume
                _ = v.GetMasterVolumeLevelScalar()
                return v
        except Exception:
            pass
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            d = AudioUtilities.GetSpeakers()
            if hasattr(d, "Activate"):
                itf = d.Activate(IAudioEndpointVolume._iid_,
                                 CLSCTX_ALL, None)
                v = cast(itf, POINTER(IAudioEndpointVolume))
                _ = v.GetMasterVolumeLevelScalar()
                return v
        except Exception:
            pass
        return None

    @staticmethod
    def _fmt_duration(seconds):
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        if h > 0 and m > 0:
            return "{} 小时 {} 分钟".format(h, m)
        if h > 0:
            return "{} 小时".format(h)
        if m > 0:
            return "{} 分钟".format(m)
        return "不到 1 分钟"

    def _on_status_battery(self, anchor_x):
        sysp = self._system_power_status()
        try:
            bat = psutil.sensors_battery()
        except Exception:
            bat = None

        if sysp is not None:
            pct = int(sysp["percent"])
            plugged = bool(sysp["plugged"])
            life = sysp["life_secs"]
            color = "#4ade80" if plugged else (
                "#f87171" if pct < 10 else (
                    "#fbbf24" if pct < 30 else "#e2e8f0"))
            if plugged:
                time_label, time_value = "状态", "充电中"
                power_text = "已接通电源"
            else:
                time_label = "剩余使用时间"
                time_value = (self._fmt_duration(life)
                              if life else "系统未提供")
                power_text = "使用电池"
            content = ft.Container(
                padding=ft.Padding.all(16),
                content=ft.Column(
                    controls=[
                        ft.Text("电池", size=12, color="#94a3b8"),
                        ft.Text("{}%".format(pct), size=32,
                                weight=ft.FontWeight.BOLD, color=color),
                        ft.Container(height=6),
                        ft.Text(time_label, size=11, color="#94a3b8"),
                        ft.Text(time_value, size=14, color="#e2e8f0"),
                        ft.Container(height=6),
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.POWER if plugged
                                    else ft.Icons.BATTERY_5_BAR,
                                    size=14, color="#64748b"),
                                ft.Text(power_text, size=11,
                                        color="#94a3b8")],
                            spacing=6)],
                    spacing=4, tight=True))
            self._show_popup(content, anchor_x, align="right", width=240)
            return

        if bat is None:
            content = ft.Container(
                padding=ft.Padding.all(16),
                content=ft.Column(
                    controls=[
                        ft.Text("电源", size=12, color="#94a3b8"),
                        ft.Text("此设备未检测到电池", size=11,
                                color="#64748b")],
                    spacing=6, tight=True))
        else:
            pct = int(bat.percent)
            color = "#4ade80" if bat.power_plugged else (
                "#f87171" if pct < 10 else (
                    "#fbbf24" if pct < 30 else "#e2e8f0"))
            content = ft.Container(
                padding=ft.Padding.all(16),
                content=ft.Column(
                    controls=[
                        ft.Text("电池", size=12, color="#94a3b8"),
                        ft.Text("{}%".format(pct), size=32,
                                weight=ft.FontWeight.BOLD, color=color)],
                    spacing=4, tight=True))
        self._show_popup(content, anchor_x, align="right", width=240)

    def _on_status_clock(self, anchor_x):
        now = time.localtime()
        wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        content = ft.Container(
            padding=ft.Padding.all(16),
            content=ft.Column(
                controls=[
                    ft.Text(time.strftime("%Y 年 %m 月 %d 日", now),
                            size=16, color="#e2e8f0"),
                    ft.Text(wd[now.tm_wday], size=12, color="#94a3b8"),
                    ft.Divider(height=14, color="#334155"),
                    ft.Text(time.strftime("%H:%M:%S", now), size=28,
                            weight=ft.FontWeight.BOLD, color="#e2e8f0")],
                spacing=6, tight=True))
        self._show_popup(content, anchor_x, align="right", width=220)

    # -------------------------------------------------------- popup / 菜单
    def _show_popup(self, content, anchor_x, align="left", width=220,
                    top=None):
        if isinstance(content, list):
            rows = []
            for item in content:
                if item[0] == "---":
                    rows.append(ft.Container(
                        height=1, bgcolor="#334155",
                        margin=ft.Margin.symmetric(vertical=4)))
                    continue
                label, icon, cb = item[0], item[1], item[2]
                shortcut = item[3] if len(item) > 3 else None
                enabled = item[4] if len(item) > 4 else True

                def mk(lb=label, ic=icon, fn=cb, sc=shortcut, en=enabled):
                    r = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12,
                                                     vertical=7),
                        border_radius=ft.BorderRadius.all(6),
                        content=ft.Row(
                            controls=[
                                ft.Icon(ic, size=14,
                                        color="#e2e8f0" if en else "#475569"),
                                ft.Text(lb, size=12,
                                        color="#e2e8f0" if en else "#475569"),
                                ft.Container(expand=True),
                                ft.Text(sc or "", size=10, color="#64748b")],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER))
                    if en and fn is not None:
                        r.on_click = lambda e, f=fn: self._popup_action(f)

                        def on_hover(e, rw=r):
                            try:
                                rw.bgcolor = ("#334155"
                                              if str(e.data).lower() == "true"
                                              else None)
                                rw.update()
                            except Exception:
                                pass
                        r.on_hover = on_hover
                    return r
                rows.append(mk())
            content = ft.Column(rows, spacing=1, tight=True)

        self.popup_menu.content = content
        self.popup_menu.width = width
        page_w = self.page.width or 1180
        left = (anchor_x - width if align == "right" else anchor_x)
        left = max(10, min(left, page_w - width - 10))
        self.popup_menu.left = left
        self.popup_menu.top = top if top is not None else MENUBAR_H + 4
        self.popup_menu.scale = 0.94
        self.popup_menu.visible = True
        self.popup_backdrop.visible = True
        try:
            self.popup_backdrop.update()
            self.popup_menu.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                self.popup_menu.scale = 1.0
                self.popup_menu.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            self.popup_menu.scale = 1.0

    def _hide_popup(self, e=None):
        self.popup_menu.visible = False
        self.popup_backdrop.visible = False
        try:
            self.popup_backdrop.update()
            self.popup_menu.update()
        except Exception:
            pass

    def _popup_action(self, cb):
        self._hide_popup()
        if cb:
            try:
                cb()
            except Exception as ex:
                self.toast("操作失败：{}".format(ex))

    def _show_menu_dropdown(self, name):
        items = self._get_menu_items(name)
        if items:
            self._show_popup(items, anchor_x=0, align="left",
                             width=240, top=MENUBAR_H + 4)

    def _get_menu_items(self, name):
        if name == "文件":
            return [("新建窗口", ft.Icons.ADD,
                     lambda: self.open_app(TerminalApp), "Ctrl+N"),
                    ("新建文件夹", ft.Icons.CREATE_NEW_FOLDER,
                     lambda: self._open_in_file_manager(
                         self.fs.desktop_of()), "Ctrl+Shift+N"),
                    ("---", None, None),
                    ("关闭窗口", ft.Icons.CLOSE,
                     self._menu_close_window, "Ctrl+W")]
        if name == "编辑":
            return [("撤销", ft.Icons.UNDO, None, "Ctrl+Z", False),
                    ("重做", ft.Icons.REDO, None, "Ctrl+Y", False),
                    ("---", None, None),
                    ("剪切", ft.Icons.CONTENT_CUT, None, "Ctrl+X", False),
                    ("复制", ft.Icons.CONTENT_COPY, None, "Ctrl+C", False),
                    ("粘贴", ft.Icons.CONTENT_PASTE, None, "Ctrl+V", False),
                    ("全选", ft.Icons.SELECT_ALL, None, "Ctrl+A", False)]
        if name == "显示":
            return [("缩放窗口", ft.Icons.CROP_SQUARE,
                     self._menu_toggle_max, None),
                    ("---", None, None),
                    ("显示隐藏文件", ft.Icons.VISIBILITY,
                     lambda: self.toast("已切换隐藏文件显示"))]
        if name == "前往":
            home = self.fs.home_of()
            return [("主目录", ft.Icons.HOME,
                     lambda: self._open_in_file_manager(home)),
                    ("桌面", ft.Icons.DESKTOP_WINDOWS,
                     lambda: self._open_in_file_manager(
                         self.fs.desktop_of())),
                    ("文稿", ft.Icons.DESCRIPTION,
                     lambda: self._open_in_file_manager(
                         home + "/Documents")),
                    ("下载", ft.Icons.DOWNLOAD,
                     lambda: self._open_in_file_manager(
                         home + "/Downloads")),
                    ("---", None, None),
                    ("回收站", ft.Icons.DELETE_OUTLINE,
                     lambda: self._open_in_file_manager("/trash"))]
        if name == "窗口":
            items = [("最小化", ft.Icons.REMOVE, self._menu_minimize),
                     ("缩放", ft.Icons.CROP_SQUARE, self._menu_toggle_max),
                     ("---", None, None)]
            if not self.windows:
                items.append(("（无窗口）", ft.Icons.CIRCLE,
                              None, None, False))
            else:
                for w in self.windows:
                    items.append((w.app.name, w.app.icon,
                                  (lambda _w=w: self._focus_window(_w))))
            return items
        if name == "帮助":
            return [("PyOS 帮助", ft.Icons.HELP, self._menu_help),
                    ("---", None, None),
                    ("关于 PyOS", ft.Icons.INFO,
                     lambda: self.open_app(AboutApp))]
        return []

    def _menu_close_window(self):
        if self.windows:
            self.close_window(self.windows[-1])

    def _menu_minimize(self):
        if self.windows:
            self.windows[-1].minimize()

    def _menu_toggle_max(self):
        if self.windows:
            self.windows[-1].toggle_max()

    def _focus_window(self, w):
        w.visible = True
        w.bring_to_front()
        try:
            w.update()
        except Exception:
            pass
        self.refresh_dock()

    def _menu_help(self):
        self.open_app(TerminalApp)

    # -------------------------------------------------------- 右键菜单
    def _show_context_menu(self, items, anchor_x=None, index=None):
        rows = []
        for label, icon, cb in items:
            if label == "---":
                rows.append(ft.Container(
                    height=1, bgcolor="#334155",
                    margin=ft.Margin.symmetric(vertical=4)))
                continue
            row = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                border_radius=ft.BorderRadius.all(6),
                on_click=lambda e, f=cb: self._menu_action(f),
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=14, color="#e2e8f0"),
                        ft.Text(label, size=12, color="#e2e8f0")],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER))

            def on_hover(e, r=row):
                try:
                    r.bgcolor = ("#334155"
                                 if str(e.data).lower() == "true" else None)
                    r.update()
                except Exception:
                    pass
            row.on_hover = on_hover
            rows.append(row)

        self.context_menu.content.controls = rows
        page_w = self.page.width or 1180
        menu_w = 200
        menu_h = 16
        for it in items:
            menu_h += 8 if it[0] == "---" else 36
        if anchor_x is None:
            left = (page_w - menu_w) / 2
        else:
            left = anchor_x
        left = max(10, min(left, page_w - menu_w - 10))
        self.context_menu.left = left
        self.context_menu.width = menu_w
        self.context_menu.height = menu_h
        self.context_menu.scale = 0.9
        self.context_menu.visible = True
        self.context_backdrop.visible = True
        try:
            self.context_backdrop.update()
            self.context_menu.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                self.context_menu.scale = 1.0
                self.context_menu.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            self.context_menu.scale = 1.0

    def _hide_context_menu(self, e=None):
        self.context_menu.visible = False
        self.context_backdrop.visible = False
        try:
            self.context_backdrop.update()
            self.context_menu.update()
        except Exception:
            pass

    def _menu_action(self, cb):
        self._hide_context_menu()
        if cb:
            try:
                cb()
            except Exception as ex:
                self.toast("菜单动作失败：{}".format(ex))

    # -------------------------------------------------------- Dock
    def _load_pinned(self):
        default = []
        for a in DESKTOP_APPS:
            default.append({"type": "system", "ref": a.__name__})
        try:
            if self.fs.exists(DOCK_CONF):
                data = json.loads(self.fs.read(DOCK_CONF))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return list(default)

    def _save_pinned(self):
        try:
            if not self.fs.exists("/etc/pyos"):
                self.fs.mkdir("/etc/pyos")
            self.fs.write(DOCK_CONF,
                          json.dumps(self.pinned, ensure_ascii=False))
        except Exception:
            pass

    def _pin_item(self, entry):
        key = entry.get("ref") or entry.get("path")
        for it in self.pinned:
            if (it.get("ref") or it.get("path")) == key:
                return False
        self.pinned.append(entry)
        self._save_pinned()
        self.refresh_dock()
        return True

    def _unpin_item(self, entry):
        key = entry.get("ref") or entry.get("path")
        self.pinned = [it for it in self.pinned
                       if (it.get("ref") or it.get("path")) != key]
        self._save_pinned()
        self.refresh_dock()

    def _resolve_pinned_entry(self, entry):
        if entry.get("type") == "system":
            ref = entry.get("ref", "")
            for a in DESKTOP_APPS:
                if a.__name__ == ref:
                    return {"kind": "app", "app_cls": a,
                            "label": a.name, "icon": a.icon,
                            "color": a.color, "entry": entry}
            return None
        path = entry.get("path", "")
        try:
            if not self.fs.exists(path):
                return None
            node = self.fs._get(path)
            name = path.rstrip("/").split("/")[-1]
            is_lnk = name.lower().endswith(".lnk")
            if node.is_dir:
                label, icon, color = name, ft.Icons.FOLDER, "#f59e0b"
            elif is_lnk:
                label, icon, color = (name[:-4], ft.Icons.OPEN_IN_NEW,
                                      "#06b6d4")
            else:
                label, icon, color = (name, ft.Icons.INSERT_DRIVE_FILE,
                                      "#60a5fa")
            return {"kind": "file", "path": path, "label": label,
                    "icon": icon, "color": color,
                    "is_dir": node.is_dir, "is_lnk": is_lnk,
                    "entry": entry}
        except Exception:
            return None

    def _build_dock(self):
        self.dock_inner = ft.Container(
            bgcolor="#0b1120dd",
            border_radius=ft.BorderRadius.all(20),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            shadow=ft.BoxShadow(blur_radius=28, color="#000000cc",
                                offset=ft.Offset(0, 8)),
            content=self.dock_row, opacity=0.25,
            clip_behavior=ft.ClipBehavior.NONE,        # 允许图标溢出
            animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_OUT))

        # Row 撑满宽度，dock_inner 居中
        dock_row_wrap = ft.Row(
            controls=[self.dock_inner],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.END,
            expand=True)

        # Container 承接 on_hover
        dock_box = ft.Container(
            alignment=ft.Alignment.BOTTOM_CENTER,
            padding=ft.Padding.only(bottom=12),
            on_hover=self._on_dock_hover,
            clip_behavior=ft.ClipBehavior.NONE,        # 允许溢出
            content=dock_row_wrap)

        drop = ft.DragTarget(
            group="fm", content=dock_box,
            on_accept=self._on_dock_drop)

        return ft.Container(
            left=0, right=0, bottom=0, height=110,
            clip_behavior=ft.ClipBehavior.NONE,        # 允许溢出
            content=drop)



    def _update_dock_width(self, scales=None):
        """根据 scales 更新 dock_inner 宽度。"""
        n = len(self.dock_icons)
        if n == 0:
            return
        ICON_W = 46
        SEP_W = 13
        GAP = 4
        PAD = 10
        total = 0
        for i in range(n):
            s = scales[i] if scales else 1.0
            total += ICON_W * s
        total += SEP_W * 2
        total += (n + 1) * GAP
        total += PAD * 2
        try:
            self.dock_inner.width = total
            self.dock_inner.update()
        except Exception:
            pass

    def _on_dock_hover(self, e):
        shown = str(e.data).lower() == "true"
        self.dock_inner.opacity = 1.0 if shown else 0.25
        if not shown:
            for item in self.dock_icons:
                item["box"].scale = 1.0
                item["box"].offset = ft.Offset(0, 0)
                try:
                    item["box"].update()
                except Exception:
                    pass
            self._update_dock_width(None)
        try:
            self.dock_inner.update()
        except Exception:
            pass

    def _on_dock_icon_hover(self, index, e):
        if str(e.data).lower() != "true":
            return
        n = len(self.dock_icons)
        if n == 0:
            return

        ICON_W = 46
        GAP = 4
        amp = 0.6
        radius = 2.6
        margin = 12
        page_w = self.page.width or 1180

        # Dock 原始总宽 + 左边缘（居中时）
        dock_orig_w = n * ICON_W + (n - 1) * GAP
        dock_left = (page_w - dock_orig_w) / 2
        hover_center = dock_left + index * (ICON_W + GAP) + ICON_W / 2

        # 初始缩放（抛物线）
        scales = []
        for i in range(n):
            dist = abs(i - index)
            if dist >= radius:
                scales.append(1.0)
            else:
                t = dist / radius
                scales.append(1.0 + amp * (1.0 - t * t))

        # 计算每个图标的实际中心（考虑缩放后的宽度 + 间距）
        def compute_centers(scales):
            centers = [0.0] * n
            centers[index] = hover_center
            for i in range(index + 1, n):
                prev_w = ICON_W * scales[i - 1]
                cur_w = ICON_W * scales[i]
                centers[i] = centers[i - 1] + prev_w / 2 + GAP + cur_w / 2
            for i in range(index - 1, -1, -1):
                next_w = ICON_W * scales[i + 1]
                cur_w = ICON_W * scales[i]
                centers[i] = centers[i + 1] - next_w / 2 - GAP - cur_w / 2
            return centers

        # 迭代压缩，直到左右都不超出屏幕
        for _ in range(8):
            centers = compute_centers(scales)
            min_edge = min(centers[i] - ICON_W * scales[i] / 2
                           for i in range(n))
            max_edge = max(centers[i] + ICON_W * scales[i] / 2
                           for i in range(n))

            ok_left = min_edge >= margin
            ok_right = max_edge <= page_w - margin
            if ok_left and ok_right:
                break

            ratio = 1.0
            if max_edge > page_w - margin:
                denom = max_edge - hover_center
                if denom > 0:
                    ratio = min(ratio,
                                (page_w - margin - hover_center) / denom)
            if min_edge < margin:
                denom = hover_center - min_edge
                if denom > 0:
                    ratio = min(ratio,
                                (hover_center - margin) / denom)
            ratio = max(0.15, min(1.0, ratio))
            scales = [1.0 + (s - 1.0) * ratio for s in scales]

        # 应用：算每个图标的偏移
        centers = compute_centers(scales)
        for i, item in enumerate(self.dock_icons):
            orig_center = dock_left + i * (ICON_W + GAP) + ICON_W / 2
            dx_px = centers[i] - orig_center
            dx = dx_px / ICON_W
            scale = scales[i]
            dy = -(scale - 1.0) * 0.55
            item["box"].scale = scale
            item["box"].offset = ft.Offset(dx, dy)
            try:
                item["box"].update()
            except Exception:
                pass
        # 同步 Dock 药丸宽度
        self._update_dock_width(scales)
    def refresh_dock(self):
        self.dock_icons = []
        self._dock_index_by_app = {}
        self._app_icons_ordered = []
        items = []
        idx = 0
        items.append(self._dock_start_button(idx)); idx += 1
        items.append(self._dock_separator())
        pinned_apps = set()
        for entry in list(self.pinned):
            item = self._resolve_pinned_entry(entry)
            if item is None:
                continue
            if item["kind"] == "app":
                pinned_apps.add(item["app_cls"])
                self._dock_index_by_app[item["app_cls"]] = idx
                self._app_icons_ordered.append(item["app_cls"])
            items.append(self._dock_item_icon(item, idx)); idx += 1
        for app_cls in DESKTOP_APPS:
            if app_cls in pinned_apps:
                continue
            has_win = any(isinstance(w.app, app_cls) for w in self.windows)
            if not has_win:
                continue
            temp_item = {
                "kind": "app", "app_cls": app_cls,
                "label": app_cls.name, "icon": app_cls.icon,
                "color": app_cls.color,
                "entry": {"type": "temp", "ref": app_cls.__name__},
                "temp": True}
            self._dock_index_by_app[app_cls] = idx
            self._app_icons_ordered.append(app_cls)
            items.append(self._dock_item_icon(temp_item, idx)); idx += 1
        items.append(self._dock_separator())
        items.append(self._dock_trash_icon(idx)); idx += 1
        self.dock_row.controls = items

        # 手动计算总宽：start(46) + sep(13) + N*icon(46) + sep(13) + trash(46)
        #                + gap(4) * (元素数 - 1)
        N = max(0, idx - 3)  # 中间图标数量
        total_w = 46 + 13 + N * 46 + 13 + 46 + (N + 3) * 4
        self.dock_row.width = total_w

        try:
            self.dock_row.update()
        except Exception:
            pass

    def _dock_separator(self):
        return ft.Container(
            width=13, height=40,
            alignment=ft.Alignment.CENTER,
            content=ft.Container(width=1, height=40, bgcolor="#334155"))

    def _register_dock_icon(self, box, index):
        self.dock_icons.append({"box": box, "index": index})

    def _dock_start_button(self, index):
        icon_box = ft.Container(
            width=46, height=46,
            border_radius=ft.BorderRadius.all(14),
            bgcolor="#1d4ed8", alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.GRID_VIEW, size=24, color="#ffffff"),
            scale=1.0, offset=ft.Offset(0, 0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        self._register_dock_icon(icon_box, index)

        def on_click(e):
            self._toggle_start()

        return ft.Container(
            width=46, height=54,
            on_click=on_click,
            on_hover=lambda e, i=index: self._on_dock_icon_hover(i, e),
            tooltip="开始", content=icon_box)

    def _dock_item_icon(self, item, index):
        if item["kind"] == "app":
            ws = [w for w in self.windows
                  if isinstance(w.app, item["app_cls"])]
        else:
            ws = []
        running = len(ws) > 0

        icon_box = ft.Container(
            width=46, height=46,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=item["color"], alignment=ft.Alignment.CENTER,
            content=ft.Icon(item["icon"], size=24, color="#ffffff"),
            scale=1.0, offset=ft.Offset(0, 0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        self._register_dock_icon(icon_box, index)

        def on_click(e):
            if item["kind"] == "app":
                app_cls = item["app_cls"]
                ws2 = [w for w in self.windows
                       if isinstance(w.app, app_cls)]
                if ws2:
                    w = ws2[-1]
                    if w.visible:
                        w.minimize()
                    else:
                        w.visible = True
                        w.bring_to_front()
                        try:
                            w.update()
                        except Exception:
                            pass
                        self.refresh_dock()
                else:
                    self.open_app(app_cls)
            else:
                self._open_dock_file(item)

        def on_right(e):
            self._on_dock_item_right(item, e, index)

        dot = ft.Container(
            width=4, height=4,
            border_radius=ft.BorderRadius.all(2),
            bgcolor="#60a5fa" if running else "#00000000",
            margin=ft.Margin.only(top=3))

        inner = ft.Container(
            width=46, height=54,
            on_click=on_click,
            on_hover=lambda e, i=index, it=item:
                self._on_dock_hover_all(i, e, it),
            tooltip=item.get("label", ""),
            content=ft.Column(
                controls=[icon_box, dot], spacing=0, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER))

        return ft.GestureDetector(
            on_secondary_tap_down=on_right,
            content=inner,
            width=46, height=54)

    def _open_dock_file(self, item):
        path = item["path"]
        if item.get("is_lnk"):
            t = self.fs.shortcut_target(path)
            if not t or not self.fs.exists(t):
                self.toast("快捷方式无效")
                return
            if self.fs.is_dir(t):
                self._open_in_file_manager(t)
            else:
                self.open_notepad(t)
        elif item.get("is_dir"):
            self._open_in_file_manager(path)
        else:
            self.open_notepad(path)

    def _on_dock_item_right(self, item, e=None, index=None):
        anchor_x = None
        if e is not None:
            pos = getattr(e, "global_position", None)
            if pos is not None:
                anchor_x = getattr(pos, "x", None)
            if anchor_x is None:
                pos = getattr(e, "local_position", None)
                if pos is not None:
                    anchor_x = getattr(pos, "x", None)

        items = []
        if item["kind"] == "app":
            app_cls = item["app_cls"]
            ws = [w for w in self.windows if isinstance(w.app, app_cls)]
            if ws:
                w = ws[-1]
                if w.visible:
                    items.append(("隐藏窗口", ft.Icons.VISIBILITY_OFF,
                                  w.minimize))
                else:
                    def show_w():
                        w.visible = True
                        w.bring_to_front()
                        try:
                            w.update()
                        except Exception:
                            pass
                        self.refresh_dock()
                    items.append(("显示窗口", ft.Icons.VISIBILITY, show_w))
                items.append(("退出", ft.Icons.CLOSE,
                              lambda: self.close_window(w)))
            else:
                items.append(("打开", ft.Icons.OPEN_IN_NEW,
                              lambda: self.open_app(app_cls)))
        else:
            items.append(("打开", ft.Icons.OPEN_IN_NEW,
                          lambda: self._open_dock_file(item)))

        items.append(("---", None, None))
        if item.get("temp"):
            items.append(("固定到 Dock", ft.Icons.PUSH_PIN,
                          lambda: self._pin_item(
                              {"type": "system",
                               "ref": item["app_cls"].__name__})))
        else:
            items.append(("从 Dock 移除", ft.Icons.CLOSE,
                          lambda: self._unpin_item(item["entry"])))
        self._show_context_menu(items, anchor_x=anchor_x, index=index)

    def _on_dock_drop(self, e):
        path = self._dragging_path
        self._dragging_path = None
        if not path:
            return
        try:
            norm = self.fs._norm(path)
            if not self.fs.exists(norm):
                self.toast("目标不存在")
                return
            ok = self._pin_item({"type": "file", "path": norm})
            self.toast(("已固定到 Dock：" if ok else "已在 Dock 中：")
                       + norm.rstrip("/").split("/")[-1])
        except Exception as ex:
            self.toast("固定失败：{}".format(ex))

    def _dock_trash_icon(self, index):
        count = 0
        try:
            if self.fs.exists("/trash"):
                count = len(self.fs.ls("/trash"))
        except Exception:
            count = 0
        icon_box = ft.Container(
            width=46, height=46,
            border_radius=ft.BorderRadius.all(14),
            bgcolor="#334155", alignment=ft.Alignment.CENTER,
            content=ft.Stack(controls=[
                ft.Icon(ft.Icons.DELETE_OUTLINE, size=24, color="#e2e8f0"),
                ft.Container(
                    right=2, top=2, width=16, height=16,
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor="#f87171",
                    alignment=ft.Alignment.CENTER,
                    visible=count > 0,
                    content=ft.Text(str(count), size=9, color="#ffffff",
                                    weight=ft.FontWeight.BOLD))]),
            scale=1.0, offset=ft.Offset(0, 0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        self._register_dock_icon(icon_box, index)

        def on_click(e):
            self._open_in_file_manager("/trash")

        def on_right(e):
            pos = getattr(e, "global_position", None)
            anchor_x = getattr(pos, "x", 0) if pos else 0
            items = [
                ("打开回收站", ft.Icons.FOLDER_OPEN,
                 lambda: self._open_in_file_manager("/trash")),
                ("---", None, None),
                ("清空回收站", ft.Icons.DELETE_SWEEP,
                 self._empty_trash_from_dock)]
            self._show_context_menu(items, anchor_x=anchor_x, index=index)

        inner = ft.Container(
            on_click=on_click,
            on_hover=lambda e, i=index: self._on_dock_icon_hover(i, e),
            tooltip="回收站", content=icon_box)
        return ft.GestureDetector(
            on_secondary_tap_down=on_right,
            content=inner,
            width=46, height=54)

    def _empty_trash_from_dock(self):
        try:
            n = self.fs.empty_trash()
            self.refresh_dock()
            self.toast("已清空回收站（{} 项）".format(n))
        except Exception as ex:
            self.toast("清空失败：{}".format(ex))

    # -------------------------------------------------------- Dock 预览
    def _on_dock_hover_all(self, index, e, item):
        try:
            self._on_dock_icon_hover(index, e)
        except Exception:
            pass
        try:
            self._on_dock_preview(index, e, item)
        except Exception:
            pass

    def _on_dock_preview(self, index, e, item):
        if str(e.data).lower() != "true":
            self._schedule_hide_dock_preview()
            return
        # 从 hover 事件里取鼠标位置
        mouse_x = None
        for attr in ("global_position", "local_position"):
            pos = getattr(e, attr, None)
            if pos is not None:
                mx = getattr(pos, "x", None)
                if mx is not None:
                    mouse_x = mx
                    break
        self._show_dock_preview(index, item, mouse_x)


    def _show_dock_preview(self, index, item, mouse_x=None):
        if item["kind"] != "app":
            self._hide_dock_preview_now()
            return
        app_cls = item["app_cls"]
        wins = [w for w in self.windows if isinstance(w.app, app_cls)]
        if not wins:
            self._hide_dock_preview_now()
            return
        cards = [self._make_preview_card(w, app_cls) for w in wins]
        self.dock_preview_row.controls = cards

        page_w = self.page.width or 1180
        n = len(cards)
        card_w = 140
        gap = 8
        pad = 10
        total_w = n * card_w + max(0, n - 1) * gap + 2 * pad

        # 优先用鼠标 x 做中心；否则用数学计算
        # 用精确公式算图标中心
        center_x = self._dock_icon_screen_x(index)

        left = center_x - total_w / 2
        left = max(10, min(left, page_w - total_w - 10))

        self._preview_hide_gen = getattr(self, "_preview_hide_gen", 0) + 1
        self.dock_preview.width = total_w
        self.dock_preview.height = 108
        self.dock_preview.left = left

        # 用 top 从顶部算（不用 bottom，避免被覆盖）
        page_h = self.page.height or 760
        preview_h = 108
        dock_h = 110
        top_y = page_h - dock_h - preview_h - 8
        if top_y < MENUBAR_H + 4:
            top_y = MENUBAR_H + 4
        self.dock_preview.top = top_y
        self.dock_preview.bottom = None

        self.dock_preview.scale = 0.9
        self.dock_preview.visible = True
        try:
            self.dock_preview.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                self.dock_preview.scale = 1.0
                self.dock_preview.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            self.dock_preview.scale = 1.0


    def _dock_icon_screen_x(self, index):
        """精确计算第 index 个 dock_icon 在屏幕上的中心 x。
        Dock 布局（从 dock_row 左边缘算）：
          start(46) gap(4) sep(13) gap(4)
          icon[0](46) gap(4) icon[1](46) gap(4) ... icon[N-1](46) gap(4)
          sep(13) gap(4) trash(46)
        """
        page_w = self.page.width or 1180
        n_icons = len(self.dock_icons)
        if n_icons == 0:
            return page_w / 2

        # 中间图标数量
        N = max(0, n_icons - 2)

        # dock_row 内容总宽
        # 46 (start) + 13 (sep) + N*46 (icons) + (N-1)*4 (icon 间距)
        # + 13 (sep) + 46 (trash) + (N+3)*4 (所有 gap)
        # 简化：50*N + 130
        total_w = 50 * N + 130

        # dock_inner padding 左右各 10
        inner_w = total_w + 20
        dock_inner_left = (page_w - inner_w) / 2
        dock_row_left = dock_inner_left + 10

        # 每个 dock_icon 的中心相对 dock_row 左边缘的偏移
        if index == 0:
            # start button
            return dock_row_left + 23

        if index == n_icons - 1:
            # trash（最后一个）
            # 位置 = start(46) gap(4) sep(13) gap(4)
            #      + N 个 icon + (N-1) 个 gap + gap(4) + sep(13) + gap(4)
            #      + 23
            offset = 46 + 4 + 13 + 4 + N * 46 + (N - 1) * 4 + 4 + 13 + 4 + 23
            return dock_row_left + offset

        # 中间图标 (index=1..N)
        k = index - 1
        offset = 46 + 4 + 13 + 4 + k * (46 + 4) + 23
        return dock_row_left + offset


    def _schedule_hide_dock_preview(self):
        gen = getattr(self, "_preview_hide_gen", 0) + 1
        self._preview_hide_gen = gen

        async def _later():
            try:
                await asyncio.sleep(0.2)
            except Exception:
                return
            if getattr(self, "_preview_hide_gen", 0) != gen:
                return
            self.dock_preview.visible = False
            try:
                self.dock_preview.update()
            except Exception:
                pass
        try:
            self.page.run_task(_later)
        except Exception:
            pass

    def _hide_dock_preview_now(self):
        self._preview_hide_gen = getattr(self, "_preview_hide_gen", 0) + 1
        if not self.dock_preview.visible:
            return
        self.dock_preview.visible = False
        try:
            self.dock_preview.update()
        except Exception:
            pass

    def _on_dock_preview_hover(self, e):
        if str(e.data).lower() == "true":
            self._preview_hide_gen = getattr(self, "_preview_hide_gen", 0) + 1
        else:
            self._schedule_hide_dock_preview()

    def _make_preview_card(self, win, app_cls):
        def on_click(e, w=win):
            try:
                self._hide_dock_preview_now()
                w.visible = True
                w.bring_to_front()
                w.update()
                self.refresh_dock()
            except Exception:
                pass

        preview_area = ft.Container(
            width=120, height=60,
            bgcolor="#0f172a",
            border_radius=ft.BorderRadius.all(6),
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=20, height=20,
                        border_radius=ft.BorderRadius.all(5),
                        bgcolor=app_cls.color,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(app_cls.icon, size=11,
                                        color="#ffffff")),
                    ft.Text(win.app.name, size=10, color="#94a3b8")],
                spacing=6, alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER))
        title = ft.Text(win.app.name, size=11, color="#e2e8f0",
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        text_align=ft.TextAlign.CENTER, width=120)
        card = ft.Container(
            width=140, height=88,
            padding=ft.Padding.all(6),
            border_radius=ft.BorderRadius.all(10),
            bgcolor="#1e293bcc",
            border=ft.Border.all(1, "#334155"),
            on_click=on_click,
            content=ft.Column(
                controls=[preview_area, title], spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER))

        def on_hover(e, c=card):
            try:
                if str(e.data).lower() == "true":
                    c.bgcolor = "#334155"
                    c.border = ft.Border.all(2, "#3b82f6")
                    self._preview_hide_gen = getattr(
                        self, "_preview_hide_gen", 0) + 1
                else:
                    c.bgcolor = "#1e293bcc"
                    c.border = ft.Border.all(1, "#334155")
                c.update()
            except Exception:
                pass
        card.on_hover = on_hover
        return card

    # -------------------------------------------------------- 开始菜单
    def _start_item(self, app_cls):
        def handler(e):
            self.hide_start()
            self.open_app(app_cls)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=9),
            border_radius=ft.BorderRadius.all(8),
            on_click=handler,
            content=ft.Row(
                controls=[ft.Icon(app_cls.icon, size=18, color="#93c5fd"),
                          ft.Text(app_cls.name, size=13, color="#e2e8f0")],
                spacing=12))

    def _start_power_row(self):
        def on_hover(e):
            if str(e.data).lower() == "true":
                self._show_power_submenu()
            else:
                self._schedule_hide_power_submenu()
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=9),
            border_radius=ft.BorderRadius.all(8),
            on_hover=on_hover,
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.POWER_SETTINGS_NEW, size=16,
                            color="#e2e8f0"),
                    ft.Text("电源", size=13, color="#e2e8f0"),
                    ft.Container(expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=14,
                            color="#64748b")],
                spacing=12))

    def _power_sub_item(self, label, icon, handler, danger=False):
        color = "#f87171" if danger else "#e2e8f0"

        def on_click(e):
            self._hide_power_submenu_now()
            try:
                self.hide_start()
            except Exception:
                pass
            try:
                handler()
            except Exception as ex:
                try:
                    self.toast("失败：{}".format(ex))
                except Exception:
                    pass

        row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=ft.BorderRadius.all(6),
            on_click=on_click,
            content=ft.Row(
                controls=[ft.Icon(icon, size=14, color=color),
                          ft.Text(label, size=12, color=color)],
                spacing=10))

        def on_hover(e):
            try:
                row.bgcolor = ("#1e293b"
                               if str(e.data).lower() == "true" else None)
                row.update()
            except Exception:
                pass
        row.on_hover = on_hover
        return row

    def _do_lock(self):
        if self.lock_screen:
            self.lock_screen.show()
        else:
            self.toast("锁屏模块未加载")

    def _do_sleep(self):
        if self.power_overlay:
            self.power_overlay.sleep()
        else:
            self.toast("电源模块未加载")

    def _do_restart(self):
        if self.power_overlay:
            self.power_overlay.restart()
        else:
            self.toast("电源模块未加载")

    def _do_shutdown(self):
        if self.power_overlay:
            self.power_overlay.shutdown()
        else:
            try:
                self.page.run_task(self.page.window_close)
            except Exception:
                pass

    def _show_power_submenu(self):
        self._power_hide_gen = getattr(self, "_power_hide_gen", 0) + 1
        self.power_submenu.scale = 0.9
        self.power_submenu.opacity = 0
        self.power_submenu.visible = True
        try:
            self.power_submenu.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                self.power_submenu.scale = 1.0
                self.power_submenu.opacity = 1.0
                self.power_submenu.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            self.power_submenu.scale = 1.0
            self.power_submenu.opacity = 1.0

    def _hide_power_submenu_now(self):
        self._power_hide_gen = getattr(self, "_power_hide_gen", 0) + 1
        if not self.power_submenu.visible:
            return
        self.power_submenu.visible = False
        try:
            self.power_submenu.update()
        except Exception:
            pass

    def _schedule_hide_power_submenu(self):
        gen = getattr(self, "_power_hide_gen", 0) + 1
        self._power_hide_gen = gen

        async def _later():
            try:
                await asyncio.sleep(0.15)
            except Exception:
                return
            if getattr(self, "_power_hide_gen", 0) != gen:
                return
            self._hide_power_submenu_now()
        try:
            self.page.run_task(_later)
        except Exception:
            pass

    def _on_power_submenu_hover(self, e):
        if str(e.data).lower() == "true":
            self._power_hide_gen = getattr(self, "_power_hide_gen", 0) + 1
        else:
            self._schedule_hide_power_submenu()

    def _show_start(self):
        self.start_menu.opacity = 0
        self.start_menu.scale = 0.94
        self.start_menu.visible = True
        self.start_backdrop.visible = True
        try:
            self.user_menu.visible = False
            self.user_menu.update()
        except Exception:
            pass
        try:
            self.start_backdrop.update()
            self.start_menu.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                self.start_menu.opacity = 1.0
                self.start_menu.scale = 1.0
                self.start_menu.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            self.start_menu.opacity = 1.0
            self.start_menu.scale = 1.0

    def _hide_start_animated(self):
        if not self.start_menu.visible:
            return
        self.start_backdrop.visible = False
        self.start_menu.opacity = 0
        self.start_menu.scale = 0.94
        try:
            self.start_backdrop.update()
            self.start_menu.update()
        except Exception:
            pass
        try:
            self._hide_power_submenu_now()
        except Exception:
            pass

        async def _finish():
            try:
                await asyncio.sleep(0.22)
                self.start_menu.visible = False
                self.start_menu.update()
            except Exception:
                pass
        try:
            self.page.run_task(_finish)
        except Exception:
            self.start_menu.visible = False

    def _toggle_start(self):
        if self.start_menu.visible and self.start_menu.opacity >= 0.5:
            self._hide_start_animated()
        else:
            self._show_start()

    def hide_start(self):
        self._hide_start_animated()

    def _on_start_backdrop_click(self, e=None):
        self._hide_start_animated()

    # -------------------------------------------------------- 通用 popup hover 辅助
    def _show_menu_dropdown(self, name):
        items = self._get_menu_items(name)
        if items:
            self._show_popup(items, anchor_x=0, align="left",
                             width=240, top=MENUBAR_H + 4)

    # -------------------------------------------------------- 用户菜单
    def _build_user_menu(self):
        return ft.Container(
            right=16, top=56, width=240,
            bgcolor="#111c34ee",
            border_radius=ft.BorderRadius.all(12),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(8), visible=False,
            shadow=ft.BoxShadow(blur_radius=20, color="#000000aa",
                                offset=ft.Offset(0, 6)),
            content=ft.Column(self._user_menu_items(),
                              spacing=2, tight=True))

    def _user_menu_items(self):
        items = []
        for username, full_name in self.fs.list_users():
            is_current = (username == self.fs.current_user)
            items.append(ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border_radius=ft.BorderRadius.all(8),
                on_click=lambda e, u=username: self._switch_user(u),
                content=ft.Row(
                    controls=[
                        ft.Container(
                            width=28, height=28,
                            border_radius=ft.BorderRadius.all(14),
                            bgcolor=("#3b82f6" if is_current
                                     else "#475569"),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(
                                username[0].upper(), size=12,
                                color="#ffffff",
                                weight=ft.FontWeight.BOLD)),
                        ft.Column(
                            controls=[
                                ft.Text(full_name, size=13,
                                        color="#e2e8f0"),
                                ft.Text(username, size=11,
                                        color="#64748b")],
                            spacing=0, tight=True),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.CHECK, size=16, color="#4ade80",
                                visible=is_current)],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER)))
        items.append(ft.Divider(height=1, color="#334155"))
        items.append(ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=ft.BorderRadius.all(8),
            on_click=self._add_user_dialog,
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PERSON_ADD, size=16,
                            color="#93c5fd"),
                    ft.Text("新建用户", size=13, color="#e2e8f0")],
                spacing=10)))
        return items

    def _refresh_user_menu(self):
        try:
            self.user_avatar.content = ft.Text(
                self.fs.current_user[0].upper(), size=14, color="#ffffff",
                weight=ft.FontWeight.BOLD)
            self.user_avatar.update()
        except Exception:
            pass
        try:
            self.user_menu.content.controls = self._user_menu_items()
            self.user_menu.update()
        except Exception:
            pass

    def _toggle_user_menu(self, e=None):
        self.user_menu.visible = not self.user_menu.visible
        if self.user_menu.visible:
            self.start_menu.visible = False
            try:
                self.start_menu.update()
            except Exception:
                pass
        try:
            self.user_menu.update()
        except Exception:
            pass

    def _switch_user(self, username):
        if username == self.fs.current_user:
            self.user_menu.visible = False
            try:
                self.user_menu.update()
            except Exception:
                pass
            return
        try:
            self.editing_mode = False
            for w in list(self.windows):
                self.close_window(w)
            self.fs.switch_user(username)
            self.shell.user = username
            self.user_menu.visible = False
            self._refresh_user_menu()
            self._desktop_snapshot = None
            self.desktop_items = []
            self._refresh_desktop_icons()
            self.refresh_dock()
            self.toast("已切换到用户 {}".format(username))
        except Exception as ex:
            self.toast("切换失败：{}".format(ex))

    def _add_user_dialog(self, e=None):
        self.user_menu.visible = False
        try:
            self.user_menu.update()
        except Exception:
            pass
        page = self.page
        tf = ft.TextField(label="用户名", autofocus=True,
                          hint_text="只能字母数字下划线")
        err = ft.Text("", size=12, color="#f87171", visible=False)

        def do_create(ev):
            name = (tf.value or "").strip()
            if not name:
                err.value = "请输入用户名"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return
            if not name.replace("_", "").isalnum():
                err.value = "只允许字母、数字和下划线"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return
            existing = [u for u, _ in self.fs.list_users()]
            if name in existing:
                err.value = "用户已存在"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return
            try:
                self.fs.add_user(name)
                self._refresh_user_menu()
                self.toast("已创建用户 {}".format(name))
                page.pop_dialog()
            except Exception as ex:
                err.value = str(ex)
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass

        def do_cancel(ev):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("新建用户"),
            content=ft.Column([tf, err], tight=True, width=300),
            actions=[ft.TextButton("取消", on_click=do_cancel),
                     ft.FilledButton("创建", on_click=do_create)])
        page.show_dialog(dlg)

    # -------------------------------------------------------- 桌面图标
    def _item_key(self, item):
        if item["kind"] == "app":
            return "app:" + item["app_cls"].__name__
        return "file:" + item["path"]

    def _find_free_slot(self, used):
        col = 0
        while True:
            for row in range(ROWS_PER_COL):
                if (col, row) not in used:
                    return col, row
            col += 1

    def _rebuild_desktop_items(self):
        new_items = []
        for app_cls in DESKTOP_APPS:
            new_items.append({
                "kind": "app", "app_cls": app_cls,
                "name": app_cls.name, "display": app_cls.name,
                "icon": app_cls.icon, "color": app_cls.color,
                "path": None})
        desktop_dir = self.fs.desktop_of()
        try:
            names = self.fs.ls(desktop_dir)
            node = self.fs._get(desktop_dir)
        except Exception:
            names, node = [], None
        for name in names:
            child = node.children[name] if node else None
            if child is None:
                continue
            is_dir = child.is_dir
            is_lnk = (not is_dir) and name.lower().endswith(".lnk")
            full = desktop_dir.rstrip("/") + "/" + name
            if is_lnk:
                display = name[:-4] if name.lower().endswith(".lnk") else name
                icon, color = ft.Icons.OPEN_IN_NEW, "#06b6d4"
            elif is_dir:
                display = name
                icon, color = ft.Icons.FOLDER, "#f59e0b"
            else:
                display = name
                icon, color = ft.Icons.INSERT_DRIVE_FILE, "#60a5fa"
            new_items.append({
                "kind": "file", "path": full, "name": name,
                "display": display, "icon": icon, "color": color,
                "is_dir": is_dir, "is_lnk": is_lnk})
        old_pos = {}
        for item in self.desktop_items:
            old_pos[self._item_key(item)] = (item["col"], item["row"])
        used = set()
        for item in new_items:
            key = self._item_key(item)
            if key in old_pos:
                c, r = old_pos[key]
                item["col"], item["row"] = c, r
                used.add((c, r))
        for item in new_items:
            if "col" not in item:
                c, r = self._find_free_slot(used)
                item["col"], item["row"] = c, r
                used.add((c, r))
        self.desktop_items = new_items
        self._render_desktop_icons()

    def _grid_pos(self, col, row):
        return (GRID_X0 + col * (ICON_W + GRID_GAP_X),
                MENUBAR_H + GRID_Y0 + row * (ICON_H + GRID_GAP_Y))

    def _render_desktop_icons(self):
        self.shake_items = []
        controls = list(self.desktop_layer.controls[:1])
        for item in self.desktop_items:
            x, y = self._grid_pos(item["col"], item["row"])
            item["x"], item["y"] = x, y
            controls.append(self._build_icon_control(item))
        self.desktop_layer.controls = controls
        try:
            self.desktop_layer.update()
        except Exception:
            pass

    def _refresh_desktop_icons(self):
        self._rebuild_desktop_items()

    def _build_icon_control(self, item):
        icon_box = ft.Container(
            width=52, height=52,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=item["color"],
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(item["icon"], size=26, color="#ffffff"))
        delete_btn = ft.Container(
            width=22, height=22,
            border_radius=ft.BorderRadius.all(11),
            bgcolor="#ef4444",
            border=ft.Border.all(2, "#0b1120"),
            alignment=ft.Alignment.CENTER,
            visible=self.editing_mode and item["kind"] == "file",
            on_click=lambda e, it=item: self._delete_desktop_item(it),
            content=ft.Icon(ft.Icons.CLOSE, size=12, color="#ffffff"))
        icon_stack = ft.Stack(
            controls=[
                ft.Container(left=8, top=8, content=icon_box),
                ft.Container(right=0, top=0, content=delete_btn)],
            width=68, height=64)
        name_text = ft.Text(
            item.get("display", item["name"]),
            size=11, color="#e2e8f0",
            text_align=ft.TextAlign.CENTER,
            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
            width=ICON_W - 8)
        inner = ft.Container(
            width=ICON_W, height=ICON_H,
            alignment=ft.Alignment.CENTER,
            offset=ft.Offset(0, 0),
            content=ft.Column(
                controls=[icon_stack, name_text], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER))

        def on_tap(e):
            if self.editing_mode:
                return
            self._open_item(item)

        def on_double(e):
            if self.editing_mode:
                return
            self._rename_item(item)

        def on_pan_start(e):
            if self.editing_mode:
                return
            self._drag_start(item)

        def on_pan_update(e):
            if self.editing_mode:
                return
            self._drag_update(item, e)

        def on_pan_end(e):
            if self.editing_mode:
                return
            self._drag_end(item)

        def on_long(e):
            if self.editing_mode:
                self._exit_edit_mode()
            else:
                self._enter_edit_mode()

        gesture = ft.GestureDetector(
            left=item["x"], top=item["y"],
            width=ICON_W, height=ICON_H,
            content=inner,
            on_tap=on_tap,
            on_double_tap=on_double,
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
            on_long_press=on_long)
        item["container"] = gesture
        item["icon_box"] = icon_box
        self.shake_items.append({"box": inner, "icon_box": icon_box})
        return gesture

    def _open_item(self, item):
        if item["kind"] == "app":
            self.open_app(item["app_cls"])
            return
        path = item["path"]
        if item.get("is_lnk"):
            t = self.fs.shortcut_target(path)
            if not t or not self.fs.exists(t):
                self.toast("快捷方式无效")
                return
            if self.fs.is_dir(t):
                self._open_in_file_manager(t)
            else:
                self.open_notepad(t)
            return
        if item.get("is_dir"):
            self._open_in_file_manager(path)
            return
        self.open_notepad(path)

    def _rename_item(self, item):
        if item["kind"] == "app":
            self.toast("系统应用不能重命名")
            return
        page = self.page
        old_display = item.get("display", item["name"])
        tf = ft.TextField(label="新名字", autofocus=True, value=old_display)
        err = ft.Text("", size=12, color="#f87171", visible=False)

        def do_rename(ev):
            new_name = (tf.value or "").strip()
            if not new_name:
                err.value = "请输入名称"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return
            if new_name == old_display:
                page.pop_dialog()
                return
            if item.get("is_lnk") and not new_name.lower().endswith(".lnk"):
                new_full = new_name + ".lnk"
            else:
                new_full = new_name
            old_path = item["path"]
            parent = "/".join(old_path.rstrip("/").split("/")[:-1]) or "/"
            new_path = (parent.rstrip("/") + "/" + new_full
                        if parent != "/" else "/" + new_full)
            if self.fs.exists(new_path):
                err.value = "同名已存在"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return
            try:
                self.fs.rename(old_path, new_full)
                self._refresh_desktop_icons()
                self.toast("已重命名为 {}".format(new_name))
                page.pop_dialog()
            except Exception as ex:
                err.value = str(ex)
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass

        def do_cancel(ev):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text("重命名"),
            content=ft.Column([tf, err], tight=True, width=320),
            actions=[ft.TextButton("取消", on_click=do_cancel),
                     ft.FilledButton("确定", on_click=do_rename)])
        page.show_dialog(dlg)

    def _delete_desktop_item(self, item):
        if item["kind"] != "file":
            self.toast("系统应用不能删除")
            return
        try:
            self.fs.trash(item["path"])
            self.toast("已移到回收站：{}".format(
                item.get("display", item["name"])))
            self.desktop_items = [it for it in self.desktop_items
                                   if it is not item]
            self._compact_layout()
        except Exception as ex:
            self.toast("删除失败：{}".format(ex))

    def _compact_layout(self):
        self.desktop_items.sort(key=lambda it: (it["col"], it["row"]))
        col, row = 0, 0
        for item in self.desktop_items:
            item["col"], item["row"] = col, row
            row += 1
            if row >= ROWS_PER_COL:
                row = 0
                col += 1
        self._render_desktop_icons()

    def _drag_start(self, item):
        try:
            c = item["container"]
            self.desktop_layer.controls.remove(c)
            self.desktop_layer.controls.append(c)
            self.desktop_layer.update()
        except Exception:
            pass

    def _drag_update(self, item, e):
        dx, dy = Window._delta(e)
        item["x"] = (item.get("x", 0) or 0) + dx
        item["y"] = (item.get("y", 0) or 0) + dy
        c = item["container"]
        c.left = item["x"]
        c.top = item["y"]
        try:
            c.update()
        except Exception:
            pass

    def _drag_end(self, item):
        col = max(0, round((item["x"] - GRID_X0) / (ICON_W + GRID_GAP_X)))
        row = max(0, min(ROWS_PER_COL - 1,
                        round((item["y"] - MENUBAR_H - GRID_Y0)
                              / (ICON_H + GRID_GAP_Y))))
        others = [it for it in self.desktop_items if it is not item]
        others.sort(key=lambda it: (it["col"], it["row"]))
        target_idx = col * ROWS_PER_COL + row
        if target_idx > len(others):
            target_idx = len(others)
        others.insert(target_idx, item)
        for i, it in enumerate(others):
            it["col"] = i // ROWS_PER_COL
            it["row"] = i % ROWS_PER_COL
        self.desktop_items = others
        self._relayout_icons()

    def _relayout_icons(self):
        for item in self.desktop_items:
            x, y = self._grid_pos(item["col"], item["row"])
            item["x"], item["y"] = x, y
            c = item.get("container")
            if c is None:
                continue
            c.left = x
            c.top = y
            try:
                c.update()
            except Exception:
                pass

    # -------------------------------------------------------- 编辑模式
    def _enter_edit_mode(self):
        if self.editing_mode:
            return
        self.editing_mode = True
        self._refresh_desktop_icons()
        for item in self.shake_items:
            item["seed"] = random.uniform(0, math.pi * 2)
            f = random.uniform(6.0, 10.0)
            item["freq"] = f
            item["freq2"] = f * random.uniform(1.5, 2.6)
            item["amp_x"] = random.uniform(0.018, 0.035)
            item["amp_y"] = random.uniform(0.010, 0.022)
            item["amp_rot"] = random.uniform(0.05, 0.14)
        try:
            self.page.run_task(self._shake_loop)
        except Exception:
            pass
        self.toast("编辑模式：点右上角 × 删除，点空白处退出")

    def _exit_edit_mode(self):
        if not self.editing_mode:
            return
        self.editing_mode = False
        self._refresh_desktop_icons()

    def _on_desktop_bg_click(self, e=None):
        self._hide_context_menu()
        self._hide_popup()
        if self.editing_mode:
            self._exit_edit_mode()

    async def _shake_loop(self):
        while self.editing_mode:
            t = time.time()
            for item in list(self.shake_items):
                box = item["box"]
                icon_box = item["icon_box"]
                seed = item.get("seed", 0.0)
                f1 = item.get("freq", 8.0)
                f2 = item.get("freq2", 16.0)
                ax = item.get("amp_x", 0.025)
                ay = item.get("amp_y", 0.018)
                ar = item.get("amp_rot", 0.1)
                x = math.sin(t * f1 + seed) * ax
                y = math.sin(t * f2 + seed * 1.7) * ay
                angle = math.sin(t * f1 + seed * 0.9) * ar
                try:
                    box.offset = ft.Offset(x, y)
                    box.update()
                except Exception:
                    pass
                try:
                    icon_box.rotate.angle = angle
                    icon_box.update()
                except Exception:
                    pass
            await asyncio.sleep(0.05)

    async def _desktop_sync_loop(self):
        while True:
            try:
                if not self.editing_mode:
                    try:
                        snap = tuple(self.fs.ls(self.fs.desktop_of()))
                    except Exception:
                        snap = ()
                    if snap != self._desktop_snapshot:
                        self._desktop_snapshot = snap
                        self._refresh_desktop_icons()
                else:
                    try:
                        self._desktop_snapshot = tuple(
                            self.fs.ls(self.fs.desktop_of()))
                    except Exception:
                        self._desktop_snapshot = ()
            except Exception:
                pass
            await asyncio.sleep(1.2)

    def _on_desktop_drop(self, e):
        if self.editing_mode:
            self._exit_edit_mode()
        src = self._dragging_path
        self._dragging_path = None
        if not src:
            return
        try:
            target = self.fs._norm(src)
            if not self.fs.exists(target):
                self.toast("目标不存在：{}".format(src))
                return
            link = self.fs.make_shortcut(target, self.fs.desktop_of())
            self._refresh_desktop_icons()
            self.toast("已创建快捷方式：{}".format(
                link.rstrip("/").split("/")[-1]))
        except Exception as ex:
            self.toast("创建快捷方式失败：{}".format(ex))

    def _open_in_file_manager(self, path):
        self.open_app(FileManagerApp)
        wins = [w for w in self.windows
                if isinstance(w.app, FileManagerApp)]
        if wins:
            try:
                wins[-1].app._navigate(path)
            except Exception:
                pass

    # -------------------------------------------------------- 键盘
    def _handle_key(self, e):
        try:
            k = (e.key or "").lower()
        except Exception:
            return
        if k == " " and (getattr(e, "ctrl", False)
                         or getattr(e, "meta", False)):
            if self.spotlight:
                self.spotlight.toggle()
            return
        if k == "escape":
            if self.spotlight:
                self.spotlight.close()
            self._hide_popup()
            self._hide_context_menu()
            if self.control_center:
                self.control_center.hide()
            if self.notification_center:
                self.notification_center.hide()
            return
        if self.spotlight and self.spotlight.overlay.visible:
            if k in ("arrow down", "down", "arrowdown"):
                self.spotlight.move(1)
            elif k in ("arrow up", "up", "arrowup"):
                self.spotlight.move(-1)
            elif k in ("enter", "return"):
                self.spotlight.open_selected()

    # -------------------------------------------------------- 窗口
    def open_app(self, app_cls, **kwargs):
        app = app_cls(self, **kwargs)
        body = app.build()
        win = Window(self, app, body, app.width, app.height)
        self.win_layer.controls.append(win)
        self.windows.append(win)
        try:
            self.win_layer.update()
        except Exception:
            pass
        self.refresh_dock()
        self.set_active_app(app.name)

        async def _grow():
            try:
                await asyncio.sleep(0.02)
                win.opacity = 1.0
                win.scale = 1.0
                win.update()
            except Exception:
                pass
        try:
            self.page.run_task(_grow)
        except Exception:
            win.opacity = 1.0
            win.scale = 1.0
        return win

    def open_notepad(self, path):
        return self.open_app(NotepadApp, filepath=path)

    def close_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
        if win in self.win_layer.controls:
            self.win_layer.controls.remove(win)
        try:
            self.win_layer.update()
        except Exception:
            pass
        self.refresh_dock()
        if not self.windows:
            self.reset_active_app()
        else:
            self.set_active_app(self.windows[-1].app.name)

    # -------------------------------------------------------- 时钟/通知
    async def _clock_loop(self):
        while True:
            self.clock_text.value = time.strftime("%Y-%m-%d  %H:%M:%S")
            try:
                self.clock_text.update()
            except Exception:
                return
            await asyncio.sleep(1)

    def toast(self, msg, details=None, title=None, icon=None):
        if self.dynamic_island:
            try:
                self.dynamic_island.notify(
                    subtitle=msg, title=title, icon=icon, details=details)
            except Exception:
                pass
        if self.notification_center:
            try:
                self.notification_center.push(
                    subtitle=msg, title=title, icon=icon, details=details)
            except Exception:
                pass