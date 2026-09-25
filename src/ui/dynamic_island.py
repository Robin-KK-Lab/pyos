"""灵动岛：空闲 / 通知 / 详情 三态切换，不阻塞。"""
import asyncio
import time

import flet as ft


IDLE_W, IDLE_H = 150, 26
NOTIFY_W, NOTIFY_H = 360, 56
DETAIL_W, DETAIL_H = 460, 220
TOP_OFFSET = 2


class DynamicIsland:
    def __init__(self, desktop):
        self.d = desktop
        self.page = desktop.page
        self.fs = desktop.fs
        self._gen = 0
        self.state = "idle"
        self._last_close = 0.0
        self.last = None

        # 空闲
        self.clock_txt = ft.Text("", size=12, color="#e2e8f0")
        self.idle_dot = ft.Container(
            width=6, height=6,
            border_radius=ft.BorderRadius.all(3),
            bgcolor="#4ade80")
        self.idle_view = ft.Row(
            controls=[self.idle_dot, self.clock_txt],
            spacing=8, alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # 通知
        self.n_icon = ft.Container(
            width=36, height=36,
            border_radius=ft.BorderRadius.all(10),
            bgcolor="#3b82f6", alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.NOTIFICATIONS, size=18,
                            color="#ffffff"))
        self.n_title = ft.Text("", size=13, color="#f1f5f9",
                               weight=ft.FontWeight.W_600,
                               max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS)
        self.n_sub = ft.Text("", size=11, color="#94a3b8",
                             max_lines=1,
                             overflow=ft.TextOverflow.ELLIPSIS)
        self.notify_view = ft.Row(
            controls=[
                self.n_icon,
                ft.Column(
                    controls=[self.n_title, self.n_sub],
                    spacing=0, tight=True, expand=True)],
            spacing=12, visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # 详情
        self.d_icon = ft.Container(
            width=40, height=40,
            border_radius=ft.BorderRadius.all(11),
            bgcolor="#3b82f6", alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.NOTIFICATIONS, size=20,
                            color="#ffffff"))
        self.d_title = ft.Text("", size=15, color="#f1f5f9",
                               weight=ft.FontWeight.W_600,
                               max_lines=1,
                               overflow=ft.TextOverflow.ELLIPSIS)
        self.d_sub = ft.Text("", size=11, color="#94a3b8",
                             max_lines=1,
                             overflow=ft.TextOverflow.ELLIPSIS)
        self.d_rows = ft.Column([], spacing=6, tight=True,
                                scroll=ft.ScrollMode.AUTO)
        self.d_close = ft.Container(
            width=24, height=24,
            border_radius=ft.BorderRadius.all(12),
            bgcolor="#334155", alignment=ft.Alignment.CENTER,
            on_click=self._on_close_detail,
            content=ft.Icon(ft.Icons.CLOSE, size=14, color="#e2e8f0"))

        self.detail_view = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.d_icon,
                        ft.Column(
                            controls=[self.d_title, self.d_sub],
                            spacing=0, tight=True, expand=True),
                        self.d_close],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=1, bgcolor="#334155",
                             margin=ft.Margin.symmetric(vertical=8)),
                ft.Container(content=self.d_rows, expand=True)],
            spacing=0, expand=True, visible=False)

        # alpha=1 让 Container 参与命中测试；肉眼不可见
        self.backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000",
            content=ft.Container(expand=True),
            visible=False,
            on_click=self._on_close_detail)
        self.pill = ft.Container(
            width=IDLE_W, height=IDLE_H,
            bgcolor="#000000",
            border_radius=ft.BorderRadius.all(16),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=16, vertical=6),
            content=ft.Stack(
                controls=[self.idle_view, self.notify_view, self.detail_view],
                expand=True),
            animate_scale=ft.Animation(320, ft.AnimationCurve.EASE_OUT),
            scale=1.0,
            on_click=self._on_tap)

        # 用 Row 让 pill 自动水平居中，Row 本身不拦截点击
        self.wrapper = ft.Row(
            controls=[self.pill],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.START,
            left=0, right=0, top=TOP_OFFSET,
            height=IDLE_H)

        try:
            self.page.run_task(self._clock_loop)
        except Exception:
            pass

    # ------------------------------------------------------------
    def notify(self, subtitle="", title="", icon=None, color=None,
               duration=2.5, details=None):
        if not subtitle and not title:
            return
        if not title:
            title = subtitle
            subtitle = ""
        self.last = {
            "title": title, "subtitle": subtitle,
            "icon": icon or ft.Icons.NOTIFICATIONS,
            "color": color or "#3b82f6",
            "details": details or [],
        }
        self._gen += 1
        gen = self._gen

        def _apply():
            try:
                self.n_icon.bgcolor = self.last["color"]
                self.n_icon.content = ft.Icon(self.last["icon"], size=18,
                                              color="#ffffff")
                self.n_title.value = title
                self.n_sub.value = subtitle
                self._show_view("notify")
            except Exception:
                pass

        # 短促更新：能立刻执行就立刻，不能就交给 run_task
        try:
            _apply()
        except Exception:
            try:
                self.page.run_task(_apply)
            except Exception:
                pass

        try:
            self.page.run_task(self._auto_collapse, gen, duration)
        except Exception:
            pass

    # ------------------------------------------------------------
    def _show_view(self, name):
        prev = self.state
        same = (name == prev)
        self.state = name

        self.idle_view.visible = (name == "idle")
        self.notify_view.visible = (name == "notify")
        self.detail_view.visible = (name == "detail")

        if same:
            try:
                self.page.update()
            except Exception:
                pass
            return

        if name == "idle":
            w, h = IDLE_W, IDLE_H
            pad = ft.Padding.symmetric(horizontal=16, vertical=6)
            br = ft.BorderRadius.all(16)
        elif name == "notify":
            w, h = NOTIFY_W, NOTIFY_H
            pad = ft.Padding.symmetric(horizontal=16, vertical=10)
            br = ft.BorderRadius.all(18)
        else:
            w, h = DETAIL_W, DETAIL_H
            pad = ft.Padding.all(16)
            br = ft.BorderRadius.all(20)

        # 改尺寸：立刻生效
        self.pill.width = w
        self.pill.height = h
        self.pill.padding = pad
        self.pill.border_radius = br
        self.wrapper.height = h
        self.backdrop.visible = (name == "detail")

        # 从 55% 开始 → 视觉上是"从中心弹出"
        self.pill.scale = 0.55

        try:
            self.page.update()
        except Exception:
            pass

        async def _grow():
            try:
                await asyncio.sleep(0.016)
                self.pill.scale = 1.0
                self.pill.update()
            except Exception:
                pass

        try:
            self.page.run_task(_grow)
        except Exception:
            self.pill.scale = 1.0

    def _on_tap(self, e=None):
        # 刚被 × 或背板关闭过，忽略紧随其后的冒泡事件
        if time.time() - self._last_close < 0.3:
            return
        # 详情状态下点药丸本体不做任何事，由 × 或背板负责收起
        if self.state == "detail":
            return
        self._gen += 1
        self._open_detail()

    def _on_close_detail(self, e=None):
        self._last_close = time.time()
        self._gen += 1
        self._collapse()

    def _open_detail(self):
        info = self.last or self._system_info()
        try:
            self.d_icon.bgcolor = info["color"]
            self.d_icon.content = ft.Icon(info["icon"], size=20,
                                          color="#ffffff")
            self.d_title.value = info["title"]
            self.d_sub.value = info.get("subtitle", "")

            rows = []
            for item in info.get("details", []):
                if isinstance(item, tuple) and len(item) == 2:
                    k, v = item
                    rows.append(ft.Row(
                        controls=[
                            ft.Text(str(k), size=11, color="#64748b",
                                    width=90),
                            ft.Text(str(v), size=12, color="#e2e8f0",
                                    selectable=True, expand=True)],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.START))
                else:
                    rows.append(ft.Text(str(item), size=12,
                                        color="#cbd5e1", selectable=True))
            if not rows:
                rows = [ft.Text("（没有更多信息）", size=11,
                                color="#475569")]
            self.d_rows.controls = rows
        except Exception:
            pass
        self._show_view("detail")

    def _system_info(self):
        try:
            user = self.fs.current_user
        except Exception:
            user = "?"
        try:
            n_apps = len(self.d.windows)
        except Exception:
            n_apps = 0
        now = time.localtime()
        wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return {
            "title": "PyOS",
            "subtitle": user + " 的桌面",
            "icon": ft.Icons.MEMORY,
            "color": "#3b82f6",
            "details": [
                ("日期", time.strftime("%Y-%m-%d", now) + " "
                 + wd[now.tm_wday]),
                ("时间", time.strftime("%H:%M:%S", now)),
                ("用户", user),
                ("打开窗口", str(n_apps)),
                ("提示", "点击药丸收起"),
            ],
        }

    async def _auto_collapse(self, gen, duration):
        try:
            await asyncio.sleep(duration)
        except Exception:
            return
        if gen != self._gen:
            return
        if self.state == "notify":
            self._collapse()

    def _collapse(self):
        self._show_view("idle")

    async def _clock_loop(self):
        while True:
            try:
                self.clock_txt.value = time.strftime("%H:%M")
                if self.state == "idle":
                    self.clock_txt.update()
            except Exception:
                return
            await asyncio.sleep(20)