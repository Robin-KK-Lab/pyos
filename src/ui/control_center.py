"""控制中心：点图标 toggle，无手势。"""
import asyncio
import subprocess

import flet as ft

try:
    from pycaw.pycaw import AudioUtilities
except Exception:
    AudioUtilities = None


class ControlCenter:
    PANEL_W = 360
    PANEL_H = 460
    MENUBAR_H = 28

    def __init__(self, desktop):
        self.d = desktop
        self.page = desktop.page
        self.progress = 0.0
        self._anim_gen = 0
        self._wifi_on = True
        self._bt_on = False
        self._dark = True
        self._dnd = False
        self._brightness = self._get_brightness() or 80
        self._volume = self._get_volume() or 40

        self.panel = ft.Container(
            top=self.MENUBAR_H,
            right=12,
            width=self.PANEL_W,
            height=self.PANEL_H,
            bgcolor="#1e293bf5",
            border_radius=ft.BorderRadius.only(
                bottom_left=18, bottom_right=18),
            border=ft.Border.all(1, "#475569"),
            padding=ft.Padding.all(14),
            visible=False,
            offset=ft.Offset(0, -1.0),
            shadow=ft.BoxShadow(blur_radius=36, color="#000000cc",
                                offset=ft.Offset(0, 12)),
            content=ft.Column(
                controls=[
                    self._toggles_grid(),
                    ft.Container(height=10),
                    self._slider_block("亮度", ft.Icons.BRIGHTNESS_6,
                                       self._brightness, self._on_brightness),
                    ft.Container(height=8),
                    self._slider_block("音量", ft.Icons.VOLUME_UP,
                                       self._volume, self._on_volume),
                    ft.Container(expand=True),
                    self._quick_actions()],
                spacing=0, expand=True))

        self.backdrop = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#01000000",
            content=ft.Container(expand=True),
            visible=False,
            on_click=self.hide)

        self.wrapper = self.panel  # 兼容旧引用

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
            # 展开
            async def _do():
                try:
                    self.panel.animate_offset = ft.Animation(
                        340, ft.AnimationCurve.EASE_OUT)
                    self.panel.offset = ft.Offset(0, -1.0)
                    self.panel.visible = True
                    self.backdrop.visible = True
                    self.panel.update()
                    self.backdrop.update()
                    # 等一帧，Flutter 建立基准状态
                    await asyncio.sleep(0.03)
                    if self._anim_gen != gen:
                        return
                    self.panel.offset = ft.Offset(0, 0)
                    self.panel.update()
                    await asyncio.sleep(0.42)
                except Exception:
                    pass
            try:
                self.page.run_task(_do)
            except Exception:
                self.panel.offset = ft.Offset(0, 0)
        else:
            # 收起
            async def _do():
                try:
                    self.panel.animate_offset = ft.Animation(
                        340, ft.AnimationCurve.EASE_OUT)
                    self.panel.offset = ft.Offset(0, -1.0)
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


    def _toggles_grid(self):
        wifi = self._toggle_card("WiFi", ft.Icons.WIFI,
                                 self._wifi_on, "#3b82f6", self._toggle_wifi)
        bt = self._toggle_card("蓝牙", ft.Icons.BLUETOOTH,
                               self._bt_on, "#3b82f6", self._toggle_bt)
        dark = self._toggle_card("深色模式", ft.Icons.DARK_MODE,
                                 self._dark, "#8b5cf6", self._toggle_dark)
        dnd = self._toggle_card("勿扰", ft.Icons.DO_NOT_DISTURB,
                                self._dnd, "#ef4444", self._toggle_dnd)
        return ft.Row(
            controls=[
                ft.Column([wifi, ft.Container(height=8), dark],
                          spacing=0, expand=True),
                ft.Container(width=8),
                ft.Column([bt, ft.Container(height=8), dnd],
                          spacing=0, expand=True)],
            spacing=0)

    def _toggle_card(self, label, icon, active, active_color, handler):
        bg = active_color if active else "#334155cc"
        fg = "#ffffff" if active else "#94a3b8"
        icon_box = ft.Container(
            width=32, height=32,
            border_radius=ft.BorderRadius.all(16),
            bgcolor="#ffffff22",
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(icon, size=18, color=fg))
        lbl = ft.Text(label, size=12,
                      color="#f1f5f9" if active else "#cbd5e1",
                      weight=ft.FontWeight.W_500)
        state = ft.Text("开" if active else "关", size=10, color=fg)
        card = ft.Container(
            padding=ft.Padding.all(10),
            bgcolor=bg,
            border_radius=ft.BorderRadius.all(12),
            on_click=lambda e: handler(card, icon_box, lbl, state),
            content=ft.Column(
                controls=[
                    ft.Row([icon_box], alignment=ft.MainAxisAlignment.START),
                    ft.Container(height=6),
                    lbl, state],
                spacing=2, tight=True))

        def on_hover(e):
            card.opacity = (0.85 if str(e.data).lower() == "true" else 1.0)
            try:
                card.update()
            except Exception:
                pass
        card.on_hover = on_hover
        return card

    def _slider_block(self, label, icon, value, on_change):
        slider = ft.Slider(min=0, max=100, value=value, expand=True,
                           active_color="#3b82f6", on_change=on_change)
        val_text = ft.Text("{}%".format(int(value)), size=11,
                           color="#94a3b8")
        box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            bgcolor="#0f1b30",
            border_radius=ft.BorderRadius.all(12),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(icon, size=14, color="#94a3b8"),
                            ft.Text(label, size=12, color="#cbd5e1"),
                            ft.Container(expand=True), val_text],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    slider],
                spacing=2, tight=True))

        def _wrap(e):
            try:
                val_text.value = "{}%".format(int(slider.value))
                val_text.update()
            except Exception:
                pass
            on_change(e)
        slider.on_change = _wrap
        return box

    def _quick_actions(self):
        def mk(label, icon, handler, danger=False, expand=True):
            color = "#f87171" if danger else "#e2e8f0"

            def on_click(e):
                self.hide()
                try:
                    handler()
                except Exception as ex:
                    self.d.toast("failed: " + repr(ex))
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius.all(10),
                bgcolor="#0f1b30",
                expand=expand,
                on_click=on_click,
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16, color=color),
                        ft.Text(label, size=12, color=color)],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER))
        return ft.Row(
            controls=[
                mk("锁屏", ft.Icons.LOCK_OUTLINE,
                   (self.d.lock_screen.show if self.d.lock_screen
                    else lambda: self.d.toast("锁屏未加载"))),
                ft.Container(width=8),
                mk("睡眠", ft.Icons.BEDTIME_OUTLINED,
                   (self.d.power_overlay.sleep if self.d.power_overlay
                    else lambda: self.d.toast("电源未加载")))],
            spacing=0)

    # ------------------------------------------------------
    def _set_toggle(self, card, icon_box, lbl, state, active, active_color):
        card.bgcolor = active_color if active else "#334155cc"
        icon_box.content.color = "#ffffff" if active else "#94a3b8"
        lbl.color = "#f1f5f9" if active else "#cbd5e1"
        state.value = "开" if active else "关"
        state.color = "#ffffff" if active else "#94a3b8"
        try:
            card.update()
            icon_box.update()
            lbl.update()
            state.update()
        except Exception:
            pass

    def _toggle_wifi(self, card, icon_box, lbl, state):
        self._wifi_on = not self._wifi_on
        self._set_toggle(card, icon_box, lbl, state,
                         self._wifi_on, "#3b82f6")
        self.d.toast("WiFi 已" + ("开启" if self._wifi_on else "关闭"))

    def _toggle_bt(self, card, icon_box, lbl, state):
        self._bt_on = not self._bt_on
        self._set_toggle(card, icon_box, lbl, state,
                         self._bt_on, "#3b82f6")
        self.d.toast("蓝牙已" + ("开启" if self._bt_on else "关闭"))

    def _toggle_dark(self, card, icon_box, lbl, state):
        self._dark = not self._dark
        self._set_toggle(card, icon_box, lbl, state,
                         self._dark, "#8b5cf6")
        try:
            self.page.theme_mode = (ft.ThemeMode.DARK if self._dark
                                    else ft.ThemeMode.LIGHT)
            self.page.update()
        except Exception:
            pass
        self.d.toast("已切换到" + ("深色" if self._dark else "浅色") + "模式")

    def _toggle_dnd(self, card, icon_box, lbl, state):
        self._dnd = not self._dnd
        self._set_toggle(card, icon_box, lbl, state,
                         self._dnd, "#ef4444")
        self.d.toast("勿扰已" + ("开启" if self._dnd else "关闭"))

    # ------------------------------------------------------
    @staticmethod
    def _get_brightness():
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance -Namespace root/wmi "
                 "-ClassName WmiMonitorBrightness).CurrentBrightness"],
                capture_output=True, text=True, timeout=4)
            v = (out.stdout or "").strip()
            if v.isdigit():
                return int(v)
        except Exception:
            pass
        return None

    def _on_brightness(self, e):
        v = int(e.control.value)
        self._brightness = v
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance -Namespace root/wmi "
                 "-ClassName WmiMonitorBrightnessMethods)"
                 ".WmiSetBrightness(1, {})".format(v)],
                creationflags=0x08000000)
        except Exception:
            pass

    @staticmethod
    def _get_volume():
        try:
            if AudioUtilities is None:
                return None
            sp = AudioUtilities.GetSpeakers()
            if hasattr(sp, "EndpointVolume"):
                return int(sp.EndpointVolume.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            pass
        return None

    def _on_volume(self, e):
        v = int(e.control.value)
        self._volume = v
        try:
            if AudioUtilities is None:
                return
            sp = AudioUtilities.GetSpeakers()
            if hasattr(sp, "EndpointVolume"):
                sp.EndpointVolume.SetMasterVolumeLevelScalar(v / 100.0, None)
        except Exception:
            pass