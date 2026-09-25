"""Spotlight 全局搜索：Ctrl+Space / Win+Space 唤出，搜索应用和文件。"""
import flet as ft

from src.ui.apps import AboutApp, FileManagerApp, NotepadApp, TerminalApp
from src.ui.apps_extra import CalculatorApp

APPS = [TerminalApp, FileManagerApp, NotepadApp, CalculatorApp, AboutApp]

APP_ALIASES = {
    TerminalApp: ["terminal", "term", "shell", "console", "cmd", "命令行"],
    FileManagerApp: ["finder", "files", "file", "fm", "explorer",
                     "文件管理器", "访达"],
    NotepadApp: ["notepad", "note", "editor", "text", "txt",
                 "记事本", "编辑器"],
    CalculatorApp: ["calc", "calculator", "???", "jsq"],
    AboutApp: ["about", "info", "system", "version",
               "关于本机", "系统信息"],
}



class Spotlight:
    def __init__(self, desktop):
        self.d = desktop
        self.fs = desktop.fs
        self.page = desktop.page
        self.results = []
        self.selected = 0

        self.field = ft.TextField(
            hint_text="Spotlight 搜索",
            border=ft.InputBorder.NONE,
            text_size=20,
            color="#e2e8f0",
            autofocus=False,
            on_change=self._on_change,
            on_submit=lambda e: self.open_selected(),
            content_padding=ft.Padding.symmetric(vertical=6))

        self.results_list = ft.ListView(
            spacing=0, padding=ft.Padding.symmetric(vertical=6))

        self.results_box = ft.Container(
            bgcolor="#0b1220",
            border=ft.Border.only(top=ft.BorderSide(1, "#1e293b")),
            border_radius=ft.BorderRadius.only(
                bottom_left=14, bottom_right=14),
            padding=ft.Padding.symmetric(horizontal=4),
            content=self.results_list,
            visible=True, height=60)

        panel = ft.Container(
            width=560,
            bgcolor="#111c34f5",
            border_radius=ft.BorderRadius.all(14),
            border=ft.Border.all(1, "#334155"),
            shadow=ft.BoxShadow(blur_radius=40, color="#000000cc",
                                offset=ft.Offset(0, 12)),
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=ft.Padding.symmetric(
                            horizontal=18, vertical=14),
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SEARCH, size=22,
                                        color="#94a3b8"),
                                self.field],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER)),
                    self.results_box],
                spacing=0, tight=True))

        self.overlay = ft.Container(
            left=0, right=0, top=0, bottom=0,
            bgcolor="#00000066",
            visible=False,
            on_click=self.close,
            padding=ft.Padding.only(top=140),
            alignment=ft.Alignment.TOP_CENTER,
            content=panel)

    # ----------------------------------------------------------
    def toggle(self):
        if self.overlay.visible:
            self.close()
        else:
            self.open()

    def open(self, e=None):
        self.field.value = ""
        self.results = []
        self.selected = 0
        self._render_results()
        self.overlay.visible = True
        try:
            self.overlay.update()
        except Exception:
            pass
        try:
            self.page.run_task(self.field.focus)
        except Exception:
            pass

    def close(self, e=None):
        self.overlay.visible = False
        try:
            self.overlay.update()
        except Exception:
            pass

    # ----------------------------------------------------------
    def _on_change(self, e):
        self._search(self.field.value or "")

    def _search(self, query):
        q = query.lower().strip()
        self.results = []
        self.selected = 0
        if not q:
            self._render_results()
            return

        # 1) 应用（中英文名 + 别名）
        for app_cls in APPS:
            hit = False
            if q in app_cls.name.lower():
                hit = True
            else:
                for alias in APP_ALIASES.get(app_cls, []):
                    if q in alias.lower():
                        hit = True
                        break
            if hit:
                self.results.append({
                    "kind": "app", "app_cls": app_cls,
                    "label": app_cls.name,
                    "icon": app_cls.icon, "color": app_cls.color,
                    "sub": "应用程序"})

        # 2) 文件（当前用户 home 下递归，深度 ≤ 4，最多 15 条）
        home = self.fs.home_of()
        self._walk(home, q, 0)

        self._render_results()

    def _walk(self, path, q, depth):
        if len(self.results) >= 15 or depth > 4:
            return
        try:
            names = self.fs.ls(path)
        except Exception:
            return
        for name in names:
            if len(self.results) >= 15:
                return
            full = (path.rstrip("/") + "/" + name) if path != "/" \
                else "/" + name
            is_dir = self.fs.is_dir(full)
            is_lnk = (not is_dir) and name.lower().endswith(".lnk")
            if q in name.lower():
                if is_dir:
                    icon, color = ft.Icons.FOLDER, "#f59e0b"
                elif is_lnk:
                    icon, color = ft.Icons.OPEN_IN_NEW, "#06b6d4"
                else:
                    icon, color = ft.Icons.INSERT_DRIVE_FILE, "#60a5fa"
                self.results.append({
                    "kind": "file", "path": full, "label": name,
                    "icon": icon, "color": color, "sub": full,
                    "is_dir": is_dir, "is_lnk": is_lnk})
            if is_dir:
                self._walk(full, q, depth + 1)

    # ----------------------------------------------------------
    def _render_results(self):
        rows = []
        q = (self.field.value or "").strip()
        if not self.results:
            msg = "无结果" if q else "输入以搜索应用和文件"
            rows.append(ft.Container(
                padding=ft.Padding.all(20),
                alignment=ft.Alignment.CENTER,
                content=ft.Text(msg, size=13, color="#475569")))
            self.results_box.height = 60
        else:
            for i, r in enumerate(self.results):
                rows.append(self._row(r, i, i == self.selected))
            self.results_box.height = min(len(self.results) * 44 + 12, 320)

        self.results_list.controls = rows
        try:
            self.results_box.update()
            self.results_list.update()
        except Exception:
            pass

    def _row(self, r, idx, selected):
        def on_click(e, i=idx):
            self.selected = i
            self.open_selected()

        row = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=ft.BorderRadius.all(6),
            bgcolor="#1e3a5f" if selected else None,
            on_click=on_click,
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=28, height=28,
                        border_radius=ft.BorderRadius.all(7),
                        bgcolor=r["color"],
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(r["icon"], size=15,
                                        color="#ffffff")),
                    ft.Column(
                        controls=[
                            ft.Text(r["label"], size=13, color="#e2e8f0"),
                            ft.Text(r["sub"], size=10, color="#64748b",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    width=400)],
                        spacing=0, tight=True)],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def on_hover(e, rr=row, i=idx):
            if str(e.data).lower() == "true":
                self.selected = i
                rr.bgcolor = "#1e3a5f"
            else:
                rr.bgcolor = None
            try:
                rr.update()
            except Exception:
                pass
        row.on_hover = on_hover
        return row

    def move(self, delta):
        if not self.results:
            return
        self.selected = (self.selected + delta) % len(self.results)
        self._render_results()

    def open_selected(self):
        if not self.results:
            return
        r = self.results[self.selected]
        self.close()
        if r["kind"] == "app":
            self.d.open_app(r["app_cls"])
            return
        path = r["path"]
        if r["is_lnk"]:
            target = self.fs.shortcut_target(path)
            if target and self.fs.exists(target):
                if self.fs.is_dir(target):
                    self.d._open_in_file_manager(target)
                else:
                    self.d.open_notepad(target)
            else:
                self.d.toast("快捷方式无效")
        elif r["is_dir"]:
            self.d._open_in_file_manager(path)
        else:
            self.d.open_notepad(path)