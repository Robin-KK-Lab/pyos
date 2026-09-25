"""桌面环境：网格图标 + 拖拽重排 + 单击打开/双击重命名 + Dock + 多用户。"""
import asyncio
import math
import os
import random
import time

import flet as ft

from src.core.fs import VirtualFS
from src.core.shell import Shell
from src.ui.apps import AboutApp, FileManagerApp, NotepadApp, TerminalApp

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(os.path.dirname(_DATA_DIR))
_DATA_PATH = os.path.join(_ROOT_DIR, "pyos_data.json")

DESKTOP_APPS = [TerminalApp, FileManagerApp, NotepadApp, AboutApp]

# 桌面网格
ICON_W = 100
ICON_H = 108
GRID_X0 = 20
GRID_Y0 = 20
GRID_GAP_X = 8
GRID_GAP_Y = 4
ROWS_PER_COL = 4


# ======================================================================
class Window(ft.Container):
    def __init__(self, os_ctx, app, body, width=680, height=460):
        super().__init__()
        self.os = os_ctx
        self.app = app
        self.maximized = False
        self._restore = None

        idx = len(os_ctx.windows) % 6
        self.left = 130 + idx * 34
        self.top = 70 + idx * 28
        self.width = width
        self.height = height
        self.bgcolor = "#0f172a"
        self.border_radius = ft.BorderRadius.all(12)
        self.border = ft.Border.all(1, "#334155")
        self.clip_behavior = ft.ClipBehavior.ANTI_ALIAS
        self.shadow = ft.BoxShadow(
            blur_radius=30, color="#00000099", offset=ft.Offset(0, 12))

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
                    self._dot(ft.Icons.CROP_SQUARE, "#34d399", self.toggle_max),
                    self._dot(ft.Icons.CLOSE, "#f87171", self.close),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER))

        self.content = ft.Column(
            controls=[
                ft.GestureDetector(content=title_bar,
                                   on_pan_update=self._on_drag),
                ft.Container(content=body, expand=True, padding=0),
            ], spacing=0, expand=True)

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
        self.top = (self.top or 0) + dy
        try:
            self.update()
        except Exception:
            pass

    def minimize(self):
        self.visible = False
        try:
            self.update()
        except Exception:
            pass
        self.os.refresh_dock()

    def toggle_max(self):
        if self.maximized:
            if self._restore:
                self.left, self.top, self.width, self.height = self._restore
            self.border_radius = ft.BorderRadius.all(12)
            self.maximized = False
        else:
            self._restore = (self.left, self.top, self.width, self.height)
            self.left = 0
            self.top = 0
            self.width = self.os.page.width or 1180
            self.height = max(320, self.os.page.height or 760)
            self.border_radius = ft.BorderRadius.all(0)
            self.maximized = True
        try:
            self.update()
        except Exception:
            pass
        self.os.refresh_dock()

    def close(self):
        self.os.close_window(self)

    def bring_to_front(self):
        try:
            self.os.win_layer.controls.remove(self)
            self.os.win_layer.controls.append(self)
            self.os.win_layer.update()
        except ValueError:
            pass
        except Exception:
            pass


# ======================================================================
class Desktop:
    def __init__(self, page: ft.Page):
        self.page = page
        self.fs = VirtualFS(data_path=_DATA_PATH)
        self.shell = Shell(self.fs)
        self.shell.user = self.fs.current_user
        self.windows = []

        self.editing_mode = False
        self.shake_items = []

        self.desktop_items = []           # 每项：{kind, col, row, ...}
        self._desktop_snapshot = None
        self._dragging_path = None

        self.win_layer = ft.Stack(expand=True, controls=[])
        self.dock_row = ft.Row(controls=[], spacing=4)
        self.dock_icons = []
        self.clock_text = ft.Text("", size=12, color="#cbd5e1")

        self._build_ui()
        self._rebuild_desktop_items()
        self.refresh_dock()

        try:
            self.page.run_task(self._clock_loop)
            self.page.run_task(self._desktop_sync_loop)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 界面搭建
    # ------------------------------------------------------------------
    def _build_ui(self):
        background = ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=["#0b1120", "#111c34", "#1e1b4b"]))

        self.desktop_layer = ft.Stack(expand=True, controls=[
            ft.Container(expand=True, bgcolor="#00000000",
                         on_click=self._on_desktop_bg_click),
        ])

        desktop_drop = ft.DragTarget(
            group="fm",
            content=self.desktop_layer,
            on_accept=self._on_desktop_drop)

        self.user_avatar = ft.Container(
            width=32, height=32, border_radius=ft.BorderRadius.all(16),
            bgcolor="#3b82f6", alignment=ft.Alignment.CENTER,
            on_click=self._toggle_user_menu, tooltip="当前用户",
            content=ft.Text(self.fs.current_user[0].upper(), size=14,
                            color="#ffffff", weight=ft.FontWeight.BOLD))

        clock_box = ft.Container(
            right=16, top=12,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=ft.BorderRadius.all(12),
            bgcolor="#0b1120aa", border=ft.Border.all(1, "#1e293b"),
            content=ft.Row(
                controls=[
                    self.user_avatar, ft.Container(width=6),
                    ft.Icon(ft.Icons.WIFI, size=14, color="#94a3b8"),
                    ft.Icon(ft.Icons.VOLUME_UP, size=14, color="#94a3b8"),
                    ft.Icon(ft.Icons.BATTERY_FULL, size=14, color="#94a3b8"),
                    self.clock_text],
                spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        self.user_menu = self._build_user_menu()
        dock = self._build_dock()

        self.start_menu = ft.Container(
            left=16, bottom=100, width=280,
            bgcolor="#111c34ee",
            border_radius=ft.BorderRadius.all(14),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(8),
            visible=False,
            shadow=ft.BoxShadow(blur_radius=24, color="#000000aa",
                                offset=ft.Offset(0, 6)),
            content=ft.Column(
                controls=[self._start_item(a) for a in DESKTOP_APPS] + [
                    ft.Divider(height=1, color="#334155"),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=9),
                        border_radius=ft.BorderRadius.all(8),
                        on_click=self._quit,
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.POWER_SETTINGS_NEW, size=16,
                                        color="#f87171"),
                                ft.Text("关机（退出 PyOS）", size=13,
                                        color="#f87171")],
                            spacing=12)),
                ],
                spacing=2, tight=True))

        self.page.add(ft.Stack(expand=True, controls=[
            background,
            desktop_drop,
            self.win_layer,
            clock_box,
            self.user_menu,
            dock,
            self.start_menu,
        ]))

    # ------------------------------------------------------------------
    # 桌面项集合
    # ------------------------------------------------------------------
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
        """构建/刷新项目列表，保留已有位置，新项目找空位。"""
        new_items = []

        # 系统应用
        for app_cls in DESKTOP_APPS:
            new_items.append({
                "kind": "app",
                "app_cls": app_cls,
                "name": app_cls.name,
                "display": app_cls.name,
                "icon": app_cls.icon,
                "color": app_cls.color,
                "path": None,
            })

        # ~/Desktop 内容
        desktop_dir = self.fs.desktop_of()
        try:
            names = self.fs.ls(desktop_dir)
            node = self.fs._get(desktop_dir)
        except Exception:
            names = []
            node = None

        for name in names:
            child = node.children[name] if node else None
            if child is None:
                continue
            is_dir = child.is_dir
            is_lnk = (not is_dir) and name.lower().endswith(".lnk")
            full = desktop_dir.rstrip("/") + "/" + name

            if is_lnk:
                display = name[:-4] if name.lower().endswith(".lnk") else name
                icon = ft.Icons.OPEN_IN_NEW
                color = "#06b6d4"
            elif is_dir:
                display = name
                icon = ft.Icons.FOLDER
                color = "#f59e0b"
            else:
                display = name
                icon = ft.Icons.INSERT_DRIVE_FILE
                color = "#60a5fa"

            new_items.append({
                "kind": "file",
                "path": full,
                "name": name,
                "display": display,
                "icon": icon,
                "color": color,
                "is_dir": is_dir,
                "is_lnk": is_lnk,
            })

        # 继承旧位置
        old_pos = {}
        for item in self.desktop_items:
            old_pos[self._item_key(item)] = (item["col"], item["row"])

        used = set()
        for item in new_items:
            key = self._item_key(item)
            if key in old_pos:
                c, r = old_pos[key]
                item["col"] = c
                item["row"] = r
                used.add((c, r))

        for item in new_items:
            if "col" not in item:
                c, r = self._find_free_slot(used)
                item["col"] = c
                item["row"] = r
                used.add((c, r))

        self.desktop_items = new_items
        self._render_desktop_icons()

    def _grid_pos(self, col, row):
        return (GRID_X0 + col * (ICON_W + GRID_GAP_X),
                GRID_Y0 + row * (ICON_H + GRID_GAP_Y))

    def _render_desktop_icons(self):
        self.shake_items = []
        # 保留底层空白 Container
        controls = list(self.desktop_layer.controls[:1])
        for item in self.desktop_items:
            x, y = self._grid_pos(item["col"], item["row"])
            item["x"] = x
            item["y"] = y
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
                controls=[icon_stack, name_text],
                spacing=2,
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
            target = self.fs.shortcut_target(path)
            if not target or not self.fs.exists(target):
                self.toast("快捷方式无效")
                return
            if self.fs.is_dir(target):
                self._open_in_file_manager(target)
            else:
                self.open_notepad(target)
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
            new_path = (parent.rstrip("/") + "/" + new_full) \
                if parent != "/" else "/" + new_full

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
                self.toast("已重命名为 {0}".format(new_name))
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
            modal=True,
            title=ft.Text("重命名"),
            content=ft.Column([tf, err], tight=True, width=320),
            actions=[
                ft.TextButton("取消", on_click=do_cancel),
                ft.FilledButton("确定", on_click=do_rename)])
        page.show_dialog(dlg)

    def _delete_desktop_item(self, item):
        if item["kind"] != "file":
            self.toast("系统应用不能删除")
            return
        try:
            self.fs.trash(item["path"])
            self.toast("已移到回收站：{0}".format(
                item.get("display", item["name"])))
            self.desktop_items = [it for it in self.desktop_items
                                   if it is not item]
            self._compact_layout()
        except Exception as ex:
            self.toast("删除失败：{0}".format(ex))

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

    # ------------------------------------------------------------------
    # 拖拽重排
    # ------------------------------------------------------------------
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
        # 计算松手后最近的格子
        col = max(0, round((item["x"] - GRID_X0) / (ICON_W + GRID_GAP_X)))
        row = max(0, min(ROWS_PER_COL - 1,
                        round((item["y"] - GRID_Y0) / (ICON_H + GRID_GAP_Y))))

        # 移除自己，其他图标按现有顺序排好
        others = [it for it in self.desktop_items if it is not item]
        others.sort(key=lambda it: (it["col"], it["row"]))

        # 目标线性索引（col,row → 单一序号）
        target_idx = col * ROWS_PER_COL + row
        if target_idx > len(others):
            target_idx = len(others)

        # 插入；后面的自然往后顺移一格（推箱子）
        others.insert(target_idx, item)

        # 重新分配格子：从上到下、从左到右
        for i, it in enumerate(others):
            it["col"] = i // ROWS_PER_COL
            it["row"] = i % ROWS_PER_COL

        self.desktop_items = others
        self._relayout_icons()

    def _relayout_icons(self):
        """按当前 col/row 重新摆放所有图标容器。"""
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

    # ------------------------------------------------------------------
    # 双向同步
    # ------------------------------------------------------------------
    async def _desktop_sync_loop(self):
        while True:
            try:
                if not self.editing_mode:
                    try:
                        snapshot = tuple(self.fs.ls(self.fs.desktop_of()))
                    except Exception:
                        snapshot = ()
                    if snapshot != self._desktop_snapshot:
                        self._desktop_snapshot = snapshot
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

    # ------------------------------------------------------------------
    # 拖拽落桌面 = 创建快捷方式
    # ------------------------------------------------------------------
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
                self.toast("目标不存在：{0}".format(src))
                return
            link = self.fs.make_shortcut(target, self.fs.desktop_of())
            self._refresh_desktop_icons()
            self.toast("已创建快捷方式：{0}".format(
                link.rstrip("/").split("/")[-1]))
        except Exception as ex:
            self.toast("创建快捷方式失败：{0}".format(ex))

    def _open_in_file_manager(self, path):
        self.open_app(FileManagerApp)
        wins = [w for w in self.windows if isinstance(w.app, FileManagerApp)]
        if wins:
            try:
                wins[-1].app._navigate(path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 用户菜单
    # ------------------------------------------------------------------
    def _build_user_menu(self):
        return ft.Container(
            right=16, top=56, width=240,
            bgcolor="#111c34ee",
            border_radius=ft.BorderRadius.all(12),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.all(8), visible=False,
            shadow=ft.BoxShadow(blur_radius=20, color="#000000aa",
                                offset=ft.Offset(0, 6)),
            content=ft.Column(self._user_menu_items(), spacing=2, tight=True))

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
                            bgcolor="#3b82f6" if is_current else "#475569",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(username[0].upper(), size=12,
                                            color="#ffffff",
                                            weight=ft.FontWeight.BOLD)),
                        ft.Column(
                            controls=[
                                ft.Text(full_name, size=13, color="#e2e8f0"),
                                ft.Text(username, size=11, color="#64748b")],
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
                    ft.Icon(ft.Icons.PERSON_ADD, size=16, color="#93c5fd"),
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
            self.toast("已切换到用户 {0}".format(username))
        except Exception as ex:
            self.toast("切换失败：{0}".format(ex))

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
                self.toast("已创建用户 {0}".format(name))
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
            actions=[
                ft.TextButton("取消", on_click=do_cancel),
                ft.FilledButton("创建", on_click=do_create)])
        page.show_dialog(dlg)

    # ------------------------------------------------------------------
    # Dock
    # ------------------------------------------------------------------
    def _build_dock(self):
        self.dock_inner = ft.Container(
            bgcolor="#0b1120dd",
            border_radius=ft.BorderRadius.all(20),
            border=ft.Border.all(1, "#334155"),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            shadow=ft.BoxShadow(blur_radius=28, color="#000000cc",
                                offset=ft.Offset(0, 8)),
            content=self.dock_row, opacity=0.25,
            animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_OUT))
        return ft.Container(
            left=0, right=0, bottom=0, height=110,
            alignment=ft.Alignment.BOTTOM_CENTER,
            padding=ft.Padding.only(bottom=12),
            on_hover=self._on_dock_hover,
            content=self.dock_inner)

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
        try:
            self.dock_inner.update()
        except Exception:
            pass

    def _on_dock_icon_hover(self, index, e):
        if str(e.data).lower() != "true":
            return
        amp, radius = 0.6, 2.6
        for item in self.dock_icons:
            i = item["index"]
            dist = abs(i - index)
            if dist >= radius:
                scale, lift = 1.0, 0.0
            else:
                t = dist / radius
                factor = 1.0 - t * t
                scale = 1.0 + amp * factor
                lift = -0.35 * factor
            item["box"].scale = scale
            item["box"].offset = ft.Offset(0, lift)
            try:
                item["box"].update()
            except Exception:
                pass

    def refresh_dock(self):
        self.dock_icons = []
        items = []
        idx = 0
        items.append(self._dock_start_button(idx)); idx += 1
        items.append(self._dock_separator())
        for app_cls in DESKTOP_APPS:
            items.append(self._dock_app_icon(app_cls, idx)); idx += 1
        items.append(self._dock_separator())
        items.append(self._dock_trash_icon(idx)); idx += 1
        self.dock_row.controls = items
        try:
            self.dock_row.update()
        except Exception:
            pass

    def _dock_separator(self):
        return ft.Container(width=1, height=40, bgcolor="#334155",
                            margin=ft.Margin.symmetric(horizontal=6))

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
            self.start_menu.visible = not self.start_menu.visible
            if self.start_menu.visible:
                self.user_menu.visible = False
                try:
                    self.user_menu.update()
                except Exception:
                    pass
            try:
                self.start_menu.update()
            except Exception:
                pass

        return ft.Container(
            on_click=on_click,
            on_hover=lambda e, i=index: self._on_dock_icon_hover(i, e),
            tooltip="开始", content=icon_box)

    def _dock_app_icon(self, app_cls, index):
        wins = [w for w in self.windows if isinstance(w.app, app_cls)]
        running = len(wins) > 0

        icon_box = ft.Container(
            width=46, height=46,
            border_radius=ft.BorderRadius.all(14),
            bgcolor=app_cls.color, alignment=ft.Alignment.CENTER,
            content=ft.Icon(app_cls.icon, size=24, color="#ffffff"),
            scale=1.0, offset=ft.Offset(0, 0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        self._register_dock_icon(icon_box, index)

        def on_click(e):
            wins_local = [w for w in self.windows
                          if isinstance(w.app, app_cls)]
            if wins_local:
                w = wins_local[-1]
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

        dot = ft.Container(
            width=4, height=4,
            border_radius=ft.BorderRadius.all(2),
            bgcolor="#60a5fa" if running else "#00000000",
            margin=ft.Margin.only(top=3))

        return ft.Container(
            on_click=on_click,
            on_hover=lambda e, i=index: self._on_dock_icon_hover(i, e),
            tooltip=app_cls.name,
            content=ft.Column(
                controls=[icon_box, dot], spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER))

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
                    bgcolor="#f87171", alignment=ft.Alignment.CENTER,
                    visible=count > 0,
                    content=ft.Text(str(count), size=9, color="#ffffff",
                                    weight=ft.FontWeight.BOLD))]),
            scale=1.0, offset=ft.Offset(0, 0),
            animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT))
        self._register_dock_icon(icon_box, index)

        def on_click(e):
            self._open_in_file_manager("/trash")

        return ft.Container(
            on_click=on_click,
            on_hover=lambda e, i=index: self._on_dock_icon_hover(i, e),
            tooltip="回收站", content=icon_box)

    # ------------------------------------------------------------------
    def _start_item(self, app_cls):
        def handler(e):
            self.hide_start()
            self.open_app(app_cls)

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=9),
            border_radius=ft.BorderRadius.all(8),
            on_click=handler,
            content=ft.Row(
                controls=[
                    ft.Icon(app_cls.icon, size=18, color="#93c5fd"),
                    ft.Text(app_cls.name, size=13, color="#e2e8f0")],
                spacing=12))

    def hide_start(self):
        self.start_menu.visible = False
        try:
            self.start_menu.update()
        except Exception:
            pass

    def _quit(self, e=None):
        try:
            if hasattr(self.page, "window_close"):
                self.page.run_task(self.page.window_close)
            else:
                self.page.run_task(self.page.window.close)
        except Exception:
            pass

    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    async def _clock_loop(self):
        while True:
            self.clock_text.value = time.strftime("%Y-%m-%d  %H:%M:%S")
            try:
                self.clock_text.update()
            except Exception:
                return
            await asyncio.sleep(1)

    def toast(self, msg):
        try:
            self.page.run_task(self._toast_task, msg)
        except Exception:
            pass

    async def _toast_task(self, msg):
        bar = ft.SnackBar(
            content=ft.Text(msg, color="#f1f5f9"),
            bgcolor="#1e293b", duration=1600)
        self.page.overlay.append(bar)
        bar.open = True
        try:
            self.page.update()
        except Exception:
            return
        await asyncio.sleep(2.0)
        try:
            self.page.overlay.remove(bar)
            self.page.update()
        except Exception:
            pass