"""系统功能：锁屏 / 睡眠 / 关机 / 重启。"""
import asyncio
import os
import sys
import time

import flet as ft


class LockScreen:
    """全屏锁屏。点击任意处解锁。带淡入淡出动画。"""

    def __init__(self, desktop):
        self.d = desktop
        self.page = desktop.page

        self._clock = ft.Text("", size=76, weight=ft.FontWeight.W_200,
                              color="#f1f5f9")
        self._date = ft.Text("", size=15, color="#94a3b8")

        avatar = ft.Container(
            width=84, height=84,
            border_radius=ft.BorderRadius.all(42),
            bgcolor="#3b82f6",
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                desktop.fs.current_user[0].upper(),
                size=34, color="#ffffff", weight=ft.FontWeight.BOLD))

        self._user_text = ft.Text(desktop.fs.current_user, size=14,
                                  color="#cbd5e1")
        self._hint = ft.Text("点击任意处解锁", size=12, color="#475569")

        # 内容列：单独做 scale 动画
        self._content = ft.Column(
            controls=[
                self._clock,
                self._date,
                ft.Container(height=28),
                avatar,
                self._user_text,
                ft.Container(height=64),
                self._hint],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            scale=0.94,
            opacity=1,
            animate_scale=ft.Animation(400, ft.AnimationCurve.EASE_OUT))

        # 全屏遮罩：opacity 做淡入淡出
        self.overlay = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#0b1120",
            visible=False,
            opacity=0,
            on_click=self.unlock,
            alignment=ft.Alignment.CENTER,
            content=self._content,
            animate_opacity=ft.Animation(320, ft.AnimationCurve.EASE_OUT))

    def show(self):
        self._update_clock()
        self.overlay.opacity = 0
        self.overlay.visible = True
        self._content.scale = 0.94
        try:
            self.overlay.update()
        except Exception:
            pass

        async def _fade_in():
            try:
                await asyncio.sleep(0.03)
                self.overlay.opacity = 1.0
                self._content.scale = 1.0
                self.overlay.update()
            except Exception:
                pass

        try:
            self.page.run_task(_fade_in)
        except Exception:
            self.overlay.opacity = 1.0
            self._content.scale = 1.0

    def unlock(self, e=None):
        if not self.overlay.visible:
            return
        self.overlay.opacity = 0
        self._content.scale = 0.94
        try:
            self.overlay.update()
        except Exception:
            pass

        async def _fade_out():
            try:
                await asyncio.sleep(0.33)
                self.overlay.visible = False
                self.overlay.update()
            except Exception:
                pass

        try:
            self.page.run_task(_fade_out)
        except Exception:
            self.overlay.visible = False

    def _update_clock(self):
        t = time.localtime()
        self._clock.value = time.strftime("%H:%M", t)
        wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        self._date.value = time.strftime("%Y 年 %m 月 %d 日", t) + \
            "  " + wd[t.tm_wday]
        try:
            self._clock.update()
            self._date.update()
        except Exception:
            pass

    async def clock_loop(self):
        while True:
            try:
                if self.overlay.visible:
                    self._update_clock()
            except Exception:
                pass
            await asyncio.sleep(1)



class PowerOverlay:
    """关机 / 重启 / 睡眠 全屏遮罩。"""

    def __init__(self, desktop):
        self.d = desktop
        self.page = desktop.page

        self._title = ft.Text("", size=22, color="#f1f5f9")
        self._sub = ft.Text("", size=13, color="#64748b")
        self._ring = ft.ProgressRing(width=28, height=28,
                                     stroke_width=3, color="#3b82f6")

        content = ft.Column(
            controls=[
                self._ring,
                ft.Container(height=22),
                self._title,
                self._sub],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER)

        self.overlay = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#000000",
            visible=False,
            opacity=0,
            alignment=ft.Alignment.CENTER,
            content=content,
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN))

    def _show(self, title, sub="", show_ring=True):
        self._title.value = title
        self._sub.value = sub
        self._ring.visible = show_ring
        self.overlay.opacity = 0
        self.overlay.visible = True
        try:
            self.overlay.update()
        except Exception:
            pass

        async def _fade():
            try:
                await asyncio.sleep(0.02)
                self.overlay.opacity = 1.0
                self.overlay.update()
            except Exception:
                pass

        try:
            self.page.run_task(_fade)
        except Exception:
            self.overlay.opacity = 1.0
            try:
                self.overlay.update()
            except Exception:
                pass

    def shutdown(self):
        self._show("正在关机…", "保存工作并退出 PyOS")

        async def _do():
            await asyncio.sleep(2.2)
            try:
                if hasattr(self.page, "window_close"):
                    self.page.run_task(self.page.window_close)
                else:
                    self.page.run_task(self.page.window.close)
            except Exception:
                pass
            await asyncio.sleep(0.5)
            os._exit(0)

        try:
            self.page.run_task(_do)
        except Exception:
            pass

    def restart(self):
        self._show("正在重启…", "PyOS 即将重新启动")

        async def _do():
            await asyncio.sleep(2.0)
            try:
                os.execv(sys.executable,
                         [sys.executable] + sys.argv)
            except Exception:
                self.overlay.visible = False
                try:
                    self.overlay.update()
                except Exception:
                    pass

        try:
            self.page.run_task(_do)
        except Exception:
            pass

    def sleep(self):
        self._show("", "", show_ring=False)
        self.overlay.content.controls[1].visible = False  # 隐藏间隙
        self._title.value = ""
        self._sub.value = ""

        async def _wake():
            await asyncio.sleep(3.0)
            self.overlay.visible = False
            try:
                self.overlay.update()
            except Exception:
                pass
            # 恢复间隙可见，给下次使用
            try:
                self.overlay.content.controls[1].visible = True
            except Exception:
                pass

        try:
            self.page.run_task(_wake)
        except Exception:
            pass