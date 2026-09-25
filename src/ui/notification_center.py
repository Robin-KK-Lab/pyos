"""通知中心：点时钟按钮切换，无手势。"""
import asyncio
import time

import flet as ft


class NotificationCenter:
    PANEL_H = 560
    MENUBAR_H = 28
    MAX_HISTORY = 60

    def __init__(self, desktop):
        self.d = desktop
        self.page = desktop.page
        self.history = []
        self.progress = 0.0
        self._anim_gen = 0

        self.list_col = ft.ListView(
            controls=[], spacing=8, padding=ft.Padding.all(12))
        self.count_text = ft.Text("", size=11, color="#64748b")

        title_row = ft.Row(
            controls=[
                ft.Text("通知中心", size=13, color="#e2e8f0",
                        weight=ft.FontWeight.W_600),
                self.count_text,
                ft.Container(expand=True),
                ft.Container(
                    width=26, height=26,
                    border_radius=ft.BorderRadius.all(13),
                    bgcolor="#334155",
                    alignment=ft.Alignment.CENTER,
                    on_click=lambda e: self._clear_all(),
                    content=ft.Icon(ft.Icons.CLEAR_ALL, size=14,
                                    color="#e2e8f0"))],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.panel = ft.Container(
            left=0, right=0, top=self.MENUBAR_H,
            height=self.PANEL_H,
            bgcolor="#1e293bf8",
            border=ft.Border.only(bottom=ft.BorderSide(1, "#475569")),
            border_radius=ft.BorderRadius.only(
                bottom_left=16, bottom_right=16),
            padding=ft.Padding.only(top=4, bottom=4),
            offset=ft.Offset(0, -1.0),
            visible=False,
            opacity=1.0,
            shadow=ft.BoxShadow(blur_radius=30, color="#000000cc",
                                offset=ft.Offset(0, 8)),
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(
                            horizontal=14, vertical=8),
                        content=title_row),
                    ft.Container(content=self.list_col, expand=True)],
                spacing=0, expand=True))

        self.backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000",
            content=ft.Container(expand=True),
            visible=False,
            on_click=lambda e: self.hide())

        self._render()

    # ------------------------------------------------------
    def push(self, subtitle="", title="", icon=None, color=None,
             details=None):
        if not title and not subtitle:
            return
        if not title:
            title, subtitle = subtitle, ""
        self.history.insert(0, {
            "title": title, "subtitle": subtitle,
            "icon": icon or ft.Icons.NOTIFICATIONS,
            "color": color or "#3b82f6",
            "details": details or [],
            "ts": time.time()})
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[:self.MAX_HISTORY]
        self._render()

    def _clear_all(self):
        self.history = []
        self._render()
        try:
            self.d.toast("已清空通知")
        except Exception:
            pass

    # ------------------------------------------------------
    def _render(self):
        n = len(self.history)
        self.count_text.value = ("（{} 条）".format(n)) if n else ""

        cards = []
        if not self.history:
            cards.append(ft.Container(
                padding=ft.Padding.all(40),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.NOTIFICATIONS_NONE, size=36,
                                color="#475569"),
                        ft.Text("没有通知", size=13, color="#64748b")],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
        else:
            for it in self.history:
                cards.append(self._make_card(it))

        self.list_col.controls = cards
        try:
            self.list_col.update()
            self.count_text.update()
        except Exception:
            pass

    def _make_card(self, n):
        icon_box = ft.Container(
            width=34, height=34,
            border_radius=ft.BorderRadius.all(9),
            bgcolor=n["color"],
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(n["icon"], size=17, color="#ffffff"))
        title_txt = ft.Text(n["title"], size=13, color="#e2e8f0",
                            weight=ft.FontWeight.W_500,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS)
        sub = n.get("subtitle") or ""
        sub_txt = None
        if sub:
            sub_txt = ft.Text(sub, size=11, color="#94a3b8",
                              max_lines=2,
                              overflow=ft.TextOverflow.ELLIPSIS)
        delta = int(time.time() - n["ts"])
        if delta < 60:
            time_str = "刚刚"
        elif delta < 3600:
            time_str = "{} 分钟前".format(delta // 60)
        elif delta < 86400:
            time_str = "{} 小时前".format(delta // 3600)
        else:
            time_str = "{} 天前".format(delta // 86400)
        time_txt = ft.Text(time_str, size=10, color="#475569")

        detail_rows = []
        for item in (n.get("details") or [])[:6]:
            if isinstance(item, tuple) and len(item) == 2:
                k, v = item
                detail_rows.append(ft.Row(
                    controls=[
                        ft.Text(str(k), size=10, color="#64748b", width=72),
                        ft.Text(str(v), size=11, color="#cbd5e1",
                                selectable=True, expand=True)],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START))

        head = ft.Row(
            controls=[
                icon_box,
                ft.Column(
                    controls=[title_txt] + ([sub_txt] if sub_txt else []),
                    spacing=2, tight=True, expand=True),
                time_txt],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START)
        children = [head]
        if detail_rows:
            children.append(ft.Container(
                padding=ft.Padding.only(left=44, top=8),
                content=ft.Column(detail_rows, spacing=4, tight=True)))
        card = ft.Container(
            padding=ft.Padding.all(10),
            bgcolor="#0f1b30",
            border=ft.Border.all(1, "#334155"),
            border_radius=ft.BorderRadius.all(10),
            content=ft.Column(children, spacing=0, tight=True),
            on_click=lambda e: self.hide())

        def on_hover(e, c=card):
            try:
                c.bgcolor = ("#1a2641"
                             if str(e.data).lower() == "true" else "#0f1b30")
                c.update()
            except Exception:
                pass
        card.on_hover = on_hover
        return card

    # ------------------------------------------------------
    # 对外：按钮切换
    # ------------------------------------------------------
    def toggle(self):
        if self.progress >= 0.5:
            self.hide()
        else:
            self.show()

    def show(self):
        self._animate_to(1.0)

    def hide(self, e=None):
        self._animate_to(0.0)

    # ------------------------------------------------------
    def _animate_to(self, target):
        self._anim_gen += 1
        gen = self._anim_gen
        self.progress = target

        if target > 0.5:
            async def _do():
                import sys
                try:
                    self.panel.animate_offset = ft.Animation(
                        340, ft.AnimationCurve.EASE_OUT)
                    self.panel.offset = ft.Offset(0, -1.0)
                    self.panel.visible = True
                    self.backdrop.visible = True
                    self.panel.update()
                    self.backdrop.update()
                    await asyncio.sleep(0.03)
                    if self._anim_gen != gen:
                        return
                    self.panel.offset = ft.Offset(0, 0)
                    self.panel.opacity = 1.0
                    self.panel.update()
                    await asyncio.sleep(0.42)
                except Exception as _ex:
                    import traceback
                    traceback.print_exc()
            try:
                self.page.run_task(_do)
            except Exception:
                self.panel.offset = ft.Offset(0, 0)
        else:
            async def _do():
                try:
                    self.panel.animate_offset = ft.Animation(
                        340, ft.AnimationCurve.EASE_OUT)
                    self.panel.offset = ft.Offset(0, -1.0)
                    self.panel.opacity = 1.0
                    self.panel.update()
                    await asyncio.sleep(0.42)
                    if self._anim_gen != gen:
                        return
                    self.panel.visible = False
                    self.backdrop.visible = False
                    self.panel.update()
                    self.backdrop.update()
                except Exception:
                    pass
            try:
                self.page.run_task(_do)
            except Exception:
                self.panel.visible = False
