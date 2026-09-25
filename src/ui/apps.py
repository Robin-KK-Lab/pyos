"""PyOS 内置应用：终端 / 文件管理器 / 记事本 / 关于本机。"""
import platform

import flet as ft


# ======================================================================
class BaseApp:
    name = "应用"
    icon = ft.Icons.APPS
    color = "#3b82f6"
    width = 680
    height = 460

    def __init__(self, os_ctx, **kwargs):
        self.os = os_ctx
        self.kwargs = kwargs

    def build(self):
        return ft.Container()


# ======================================================================
class TerminalApp(BaseApp):
    name = "终端"
    icon = ft.Icons.TERMINAL
    color = "#0ea5e9"
    width = 740
    height = 460

    def build(self):
        self.lines = ft.ListView(expand=True, spacing=1, auto_scroll=True,
                                 padding=ft.Padding.all(10))
        self._append("PyOS Shell 1.0  ·  输入 help 查看命令列表", "#64748b")
        self._append("", "#e2e8f0")

        self.prompt = ft.Text(self.os.shell.prompt(), size=13, color="#4ade80")
        self.entry = ft.TextField(
            expand=True,
            border=ft.InputBorder.NONE,
            text_size=13,
            color="#e2e8f0",
            autofocus=True,
            on_submit=self._submit,
            content_padding=ft.Padding.symmetric(vertical=6),
        )

        input_row = ft.Container(
            bgcolor="#020617",
            border=ft.Border.only(top=ft.BorderSide(1, "#1e293b")),
            padding=ft.Padding.symmetric(horizontal=12),
            content=ft.Row(
                controls=[self.prompt, self.entry],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        return ft.Container(
            bgcolor="#020617",
            expand=True,
            content=ft.Column([self.lines, input_row], spacing=0, expand=True),
        )

    def _append(self, text, color="#e2e8f0"):
        self.lines.controls.append(
            ft.Text(text, size=13, color=color, selectable=True))

    def _submit(self, e):
        cmd = self.entry.value or ""
        self.entry.value = ""
        old = self.prompt.value
        self._append("{0} {1}".format(old, cmd), "#94a3b8")

        result = self.os.shell.run(cmd)

        if result == "\x0c":
            self.lines.controls.clear()
        elif result:
            for line in str(result).split("\n"):
                self._append(line)

        self.prompt.value = self.os.shell.prompt()
        self.lines.update()
        self.prompt.update()
        self.entry.update()
        try:
            self.os.page.run_task(self.entry.focus)
        except Exception:
            pass


# ======================================================================
class FileManagerApp(BaseApp):
    name = "文件管理器"
    icon = ft.Icons.FOLDER_OPEN
    color = "#f59e0b"
    width = 860
    height = 580

    def build(self):
        self.cwd = "/home/user"
        self.selected = None
        self._dragging = None
        self.history = []
        self.history_idx = -1

        self.crumbs = ft.Row(spacing=2, scroll=ft.ScrollMode.AUTO)
        self.listing = ft.ListView(expand=True, spacing=2,
                                   padding=ft.Padding.all(6))
        self.status = ft.Text("", size=11, color="#64748b")

        self.btn_back = ft.IconButton(
            ft.Icons.ARROW_BACK, icon_size=18, tooltip="后退",
            on_click=self._back, disabled=True)
        self.btn_fwd = ft.IconButton(
            ft.Icons.ARROW_FORWARD, icon_size=18, tooltip="前进",
            on_click=self._forward, disabled=True)

        toolbar = ft.Row(
            controls=[
                self.btn_back,
                self.btn_fwd,
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=18,
                              tooltip="上一级", on_click=self._up),
                ft.IconButton(ft.Icons.REFRESH, icon_size=18, tooltip="刷新",
                              on_click=lambda e: self._reload()),
                self._sep(),
                ft.IconButton(ft.Icons.CREATE_NEW_FOLDER, icon_size=18,
                              tooltip="新建文件夹", on_click=self._new_folder),
                ft.IconButton(ft.Icons.EDIT, icon_size=18, tooltip="重命名",
                              on_click=self._rename),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18,
                              tooltip="删除到回收站", on_click=self._to_trash),
                ft.IconButton(ft.Icons.DELETE_FOREVER, icon_size=18,
                              tooltip="永久删除", on_click=self._delete_forever),
                ft.IconButton(ft.Icons.DRIVE_FILE_MOVE, icon_size=18,
                              tooltip="移动到...", on_click=self._move_to),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.RESTORE_FROM_TRASH, icon_size=18,
                              tooltip="打开回收站",
                              on_click=lambda e: self._navigate("/trash")),
                ft.IconButton(ft.Icons.RESTORE, icon_size=18,
                              tooltip="从回收站恢复选中项",
                              on_click=self._restore_selected),
                ft.IconButton(ft.Icons.DELETE_SWEEP, icon_size=18,
                              tooltip="清空回收站", on_click=self._empty_trash),
            ],
            spacing=2,
        )

        top = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor="#111c34",
            content=ft.Column(
                controls=[
                    toolbar,
                    ft.Container(padding=ft.Padding.only(left=4, top=4),
                                 content=self.crumbs),
                ],
                spacing=2, tight=True,
            ),
        )

        bottom = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor="#111c34",
            content=self.status,
        )

        self._navigate("/home/user", record=True, silent=True)

        return ft.Container(
            bgcolor="#0b1220",
            expand=True,
            content=ft.Column(
                controls=[
                    top,
                    ft.Container(content=self.listing, expand=True),
                    bottom,
                ],
                spacing=0, expand=True,
            ),
        )

    @staticmethod
    def _sep():
        return ft.Container(width=1, height=22, bgcolor="#334155",
                            margin=ft.Margin.symmetric(horizontal=4))

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------
    def _navigate(self, path, record=True, silent=False):
        try:
            norm = self.os.fs._norm(path)
            if not self.os.fs.is_dir(norm):
                if not silent:
                    self.os.toast("不是目录：{0}".format(path))
                return
            self.cwd = norm
            self.selected = None
            if record:
                self.history = self.history[:self.history_idx + 1]
                self.history.append(self.cwd)
                self.history_idx = len(self.history) - 1
            self._reload(silent=silent)
            self._sync_nav_buttons()
        except Exception as ex:
            if not silent:
                self.os.toast("无法打开：{0}".format(ex))

    def _back(self, e=None):
        if self.history_idx > 0:
            self.history_idx -= 1
            self._navigate(self.history[self.history_idx],
                           record=False, silent=True)

    def _forward(self, e=None):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self._navigate(self.history[self.history_idx],
                           record=False, silent=True)

    def _up(self, e=None):
        if self.cwd == "/":
            return
        parent = "/".join(self.cwd.rstrip("/").split("/")[:-1]) or "/"
        self._navigate(parent)

    def _sync_nav_buttons(self):
        self.btn_back.disabled = (self.history_idx <= 0)
        self.btn_fwd.disabled = (self.history_idx >= len(self.history) - 1)
        for b in (self.btn_back, self.btn_fwd):
            try:
                b.update()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 列表渲染
    # ------------------------------------------------------------------
    def _reload(self, silent=False):
        self.listing.controls.clear()
        self.crumbs.controls.clear()

        self.crumbs.controls.append(self._crumb("根目录", "/"))
        if self.cwd != "/":
            acc = ""
            for p in [s for s in self.cwd.split("/") if s]:
                acc += "/" + p
                self.crumbs.controls.append(
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=12, color="#475569"))
                label = "回收站" if acc == "/trash" else p
                self.crumbs.controls.append(self._crumb(label, acc))

        try:
            names = self.os.fs.ls(self.cwd)
            node = self.os.fs._get(self.cwd)
        except Exception as ex:
            self.status.value = "无法打开：{0}".format(ex)
            if not silent:
                self._update_all()
            return

        dirs = sorted([n for n in names if node.children[n].is_dir],
                      key=str.lower)
        files = sorted([n for n in names if not node.children[n].is_dir],
                       key=str.lower)

        if not names:
            self.listing.controls.append(
                ft.Container(
                    padding=ft.Padding.all(28),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("（空目录）", size=12, color="#475569")))
        else:
            for n in dirs + files:
                child = node.children[n]
                full = (self.cwd.rstrip("/") + "/" + n) \
                    if self.cwd != "/" else "/" + n
                self.listing.controls.append(self._row(n, full, child))

        self.status.value = "{0} 个项目   ·   {1}".format(len(names), self.cwd)
        if not silent:
            self._update_all()

    def _crumb(self, label, path):
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=ft.BorderRadius.all(4),
            on_click=lambda e, p=path: self._navigate(p),
            content=ft.Text(label, size=12, color="#93c5fd"))

    def _row(self, name, full, node):
        is_dir = node.is_dir
        is_sel = (full == self.selected)
        size = "" if is_dir else self._fmt_size(len(node.content or ""))
        in_trash = self.cwd == "/trash" or self.cwd.startswith("/trash/")

        subtitle = None
        if in_trash and node.origin:
            subtitle = ft.Text("原位置: {0}".format(node.origin),
                               size=10, color="#475569")

        tile = ft.ListTile(
            dense=True,
            leading=ft.Icon(
                ft.Icons.FOLDER if is_dir else ft.Icons.INSERT_DRIVE_FILE,
                size=20, color="#fbbf24" if is_dir else "#60a5fa"),
            title=ft.Text(name, size=13, color="#e2e8f0"),
            subtitle=subtitle,
            trailing=ft.Text(size, size=11, color="#64748b") if size else None)

        box = ft.Container(
            bgcolor="#1e3a5f" if is_sel else None,
            border=ft.Border.all(1, "#3b82f6" if is_sel else "#00000000"),
            border_radius=ft.BorderRadius.all(6),
            content=tile)

        gesture = ft.GestureDetector(
            content=box,
            on_tap=lambda e, p=full: self._select(p),
            on_double_tap=lambda e, p=full, d=is_dir: self._open(p, d))

        draggable = ft.Draggable(
            group="fm",
            data=full,
            content=gesture,
            on_drag_start=lambda e, p=full: self._on_drag_start(p),
            content_feedback=ft.Container(
                width=220, height=36,
                bgcolor="#1e293b",
                border_radius=ft.BorderRadius.all(6),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                content=ft.Text(name, size=12, color="#e2e8f0")))

        if is_dir:
            return ft.DragTarget(
                group="fm",
                content=draggable,
                on_accept=lambda e, t=full: self._drop(e, t))
        return draggable

    @staticmethod
    def _fmt_size(n):
        try:
            n = float(n)
        except Exception:
            return ""
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return "{0} {1}".format(
                    int(n) if unit == "B" else round(n, 1), unit)
            n /= 1024
        return "{0:.1f} TB".format(n)

    def _update_all(self):
        for c in (self.listing, self.crumbs, self.status):
            try:
                c.update()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 选中 / 打开
    # ------------------------------------------------------------------
    def _select(self, path):
        self.selected = None if self.selected == path else path
        self._reload()

    def _open(self, path, is_dir):
        if is_dir:
            self._navigate(path)
            return

        # 回收站里双击 = 恢复
        if self.cwd == "/trash" or self.cwd.startswith("/trash/"):
            name = path.rstrip("/").split("/")[-1]
            try:
                restored = self.os.fs.restore(name)
                self._reload()
                self.os.toast("已恢复到 {0}".format(restored))
            except Exception as ex:
                self.os.toast("恢复失败：{0}".format(ex))
            return

        # 双击 .lnk = 打开快捷方式指向的目标
        if path.lower().endswith(".lnk"):
            target = self.os.fs.shortcut_target(path)
            if not target:
                self.os.toast("快捷方式无效（无目标）")
                return
            if not self.os.fs.exists(target):
                self.os.toast("快捷方式目标不存在：{0}".format(target))
                return
            if self.os.fs.is_dir(target):
                self._navigate(target)
            else:
                try:
                    self.os.open_notepad(target)
                except Exception as ex:
                    self.os.toast("无法打开：{0}".format(ex))
            return

        # 普通文件 → 记事本
        try:
            self.os.open_notepad(path)
        except Exception as ex:
            self.os.toast("无法打开：{0}".format(ex))

    # ------------------------------------------------------------------
    # 拖拽
    # ------------------------------------------------------------------
    def _on_drag_start(self, path):
        self._dragging = path; self.os._dragging_path = path

    def _drop(self, e, target_dir):
        src = getattr(self, "_dragging", None)
        self._dragging = None
        if not src:
            return
        try:
            src_norm = self.os.fs._norm(src)
            tgt_norm = self.os.fs._norm(target_dir)
            if src_norm == tgt_norm:
                return
            if tgt_norm == src_norm.rstrip("/") + "/" or \
               tgt_norm.startswith(src_norm.rstrip("/") + "/"):
                self.os.toast("不能移动到自身子目录")
                return
            self.os.fs.move(src_norm, tgt_norm)
            self.selected = None
            self._reload()
            self.os.toast("已移动到 {0}".format(tgt_norm))
        except Exception as ex:
            self.os.toast("移动失败：{0}".format(ex))

    # ------------------------------------------------------------------
    # 对话框：完全照 demo 的写法（同步 show_dialog / pop_dialog）
    # ------------------------------------------------------------------
    def _new_folder(self, e=None):
        page = self.os.page
        tf = ft.TextField(label="文件夹名称", autofocus=True,
                          value="新建文件夹")
        err = ft.Text("", size=12, color="#f87171", visible=False)

        def do_create(ev):
            name = (tf.value or "").strip()
            if not name:
                err.value = "请输入名称"
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return

            target = (self.cwd.rstrip("/") + "/" + name) \
                if self.cwd != "/" else "/" + name

            if self.os.fs.exists(target):
                err.value = "同名已存在：{0}".format(name)
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return

            try:
                self.os.fs.mkdir(target)
                self._reload()
                self.os.toast("已创建 {0}".format(name))
                page.pop_dialog()
            except Exception as ex:
                err.value = "创建失败：{0}".format(ex)
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass

        def do_cancel(ev):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("新建文件夹"),
            content=ft.Column([tf, err], tight=True, width=320),
            actions=[
                ft.TextButton("取消", on_click=do_cancel),
                ft.FilledButton("创建", on_click=do_create),
            ],
        )
        page.show_dialog(dlg)


    def _rename(self, e=None):
        if not self.selected:
            self.os.toast("请先选中一个文件或文件夹")
            return
        page = self.os.page
        old = self.selected.rstrip("/").split("/")[-1]
        tf = ft.TextField(label="新名字", autofocus=True, value=old)
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

            if new_name == old:
                page.pop_dialog()
                return

            parent_path = "/".join(self.selected.rstrip("/").split("/")[:-1]) or "/"
            new_path = (parent_path.rstrip("/") + "/" + new_name) \
                if parent_path != "/" else "/" + new_name

            if self.os.fs.exists(new_path):
                err.value = "同名已存在：{0}".format(new_name)
                err.visible = True
                try:
                    err.update()
                except Exception:
                    pass
                return

            try:
                self.os.fs.rename(self.selected, new_name)
                self.selected = None
                self._reload()
                self.os.toast("已重命名为 {0}".format(new_name))
                page.pop_dialog()
            except Exception as ex:
                err.value = "重命名失败：{0}".format(ex)
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
                ft.FilledButton("确定", on_click=do_rename),
            ],
        )
        page.show_dialog(dlg)


    def _to_trash(self, e=None):
        if not self.selected:
            self.os.toast("请先选中一个文件或文件夹")
            return
        try:
            target = self.os.fs.trash(self.selected)
            self.selected = None
            self._reload()
            self.os.toast("已移到回收站：{0}".format(target))
        except Exception as ex:
            self.os.toast("删除失败：{0}".format(ex))

    def _restore_selected(self, e=None):
        if not self.selected:
            self.os.toast("请先选中一个文件或文件夹")
            return
        if not (self.cwd == "/trash" or self.cwd.startswith("/trash/")):
            self.os.toast("请先进入回收站 /trash")
            return
        name = self.selected.rstrip("/").split("/")[-1]
        try:
            restored = self.os.fs.restore(name)
            self.selected = None
            self._reload()
            self.os.toast("已恢复到 {0}".format(restored))
        except Exception as ex:
            self.os.toast("恢复失败：{0}".format(ex))
    def _delete_forever(self, e=None):
        if not self.selected:
            self.os.toast("请先选中一个文件或文件夹")
            return
        page = self.os.page
        name = self.selected.rstrip("/").split("/")[-1]

        def do_delete(ev):
            try:
                self.os.fs.rm(self.selected)
                self.selected = None
                self._reload()
                self.os.toast("已永久删除 {0}".format(name))
            except Exception as ex:
                self.os.toast("删除失败：{0}".format(ex))
            page.pop_dialog()

        def do_cancel(ev):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("永久删除"),
            content=ft.Text("确定要永久删除 “{0}” 吗？此操作不可恢复。".format(name)),
            actions=[
                ft.TextButton("取消", on_click=do_cancel),
                ft.FilledButton("永久删除", on_click=do_delete),
            ],
        )
        page.show_dialog(dlg)

    def _move_to(self, e=None):
        if not self.selected:
            self.os.toast("请先选中一个文件或文件夹")
            return
        page = self.os.page
        tf = ft.TextField(label="目标目录", autofocus=True,
                          value="/home/user/Documents")

        def do_move(ev):
            target = (tf.value or "").strip()
            if target:
                try:
                    dst = self.os.fs._norm(target)
                    if not self.os.fs.is_dir(dst):
                        raise NotADirectoryError(target)
                    self.os.fs.move(self.selected, dst)
                    self.selected = None
                    self._reload()
                    self.os.toast("已移动到 {0}".format(dst))
                except Exception as ex:
                    self.os.toast("移动失败：{0}".format(ex))
            page.pop_dialog()

        def do_cancel(ev):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("移动到..."),
            content=ft.Column([tf], tight=True, width=360),
            actions=[
                ft.TextButton("取消", on_click=do_cancel),
                ft.FilledButton("移动", on_click=do_move),
            ],
        )
        page.show_dialog(dlg)

    def _empty_trash(self, e=None):
        try:
            n = self.os.fs.empty_trash()
            self.selected = None
            self._reload()
            self.os.toast("已清空回收站（{0} 项）".format(n))
        except Exception as ex:
            self.os.toast("操作失败：{0}".format(ex))


# ======================================================================
class NotepadApp(BaseApp):
    name = "记事本"
    icon = ft.Icons.EDIT_NOTE
    color = "#10b981"
    width = 680
    height = 480

    def __init__(self, os_ctx, filepath=None, **kwargs):
        super().__init__(os_ctx, **kwargs)
        self.filepath = filepath
        if filepath:
            self.name = "记事本 - " + filepath.rstrip("/").split("/")[-1]

    def build(self):
        content = ""
        if self.filepath:
            try:
                content = self.os.fs.read(self.filepath)
            except Exception:
                content = ""

        self.editor = ft.TextField(
            value=content,
            multiline=True,
            expand=True,
            border=ft.InputBorder.NONE,
            text_size=14,
            color="#e2e8f0",
            bgcolor="#0b1220",
            content_padding=ft.Padding.all(12),
            on_change=self._on_change,
        )

        self.path_field = ft.TextField(
            value=self.filepath or "/home/user/untitled.txt",
            expand=True, height=34, text_size=12,
            bgcolor="#0b1220", color="#94a3b8",
            content_padding=ft.Padding.symmetric(horizontal=10),
        )

        self.info = ft.Text("就绪", size=11, color="#64748b")

        bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor="#111c34",
            content=ft.Row(
                controls=[
                    ft.ElevatedButton("保存", icon=ft.Icons.SAVE, height=34,
                                      on_click=self._save),
                    self.path_field,
                ],
                spacing=8,
            ),
        )

        return ft.Container(
            bgcolor="#0b1220",
            expand=True,
            content=ft.Column(
                controls=[
                    bar,
                    ft.Container(content=self.editor, expand=True),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        bgcolor="#111c34",
                        content=self.info,
                    ),
                ],
                spacing=0, expand=True,
            ),
        )

    def _on_change(self, e):
        text = self.editor.value or ""
        self.info.value = "{0} 字符   ·   {1} 行".format(
            len(text), len(text.splitlines()))
        try:
            self.info.update()
        except Exception:
            pass

    def _save(self, e):
        path = (self.path_field.value or "").strip()
        if not path:
            self.info.value = "请先填写保存路径"
            self.info.update()
            return
        try:
            self.os.fs.write(path, self.editor.value or "")
            self.filepath = path
            self.info.value = "已保存到 {0}".format(path)
            self.os.toast("已保存：{0}".format(path))
        except Exception as ex:
            self.info.value = "保存失败：{0}".format(ex)
        try:
            self.info.update()
        except Exception:
            pass


# ======================================================================
class AboutApp(BaseApp):
    name = "关于本机"
    icon = ft.Icons.COMPUTER
    color = "#8b5cf6"
    width = 540
    height = 440

    def build(self):
        flet_ver = "未知"
        try:
            from importlib.metadata import version as _pv
            flet_ver = _pv("flet")
        except Exception:
            pass

        def row(k, v):
            return ft.Row(
                controls=[
                    ft.Text(k, size=13, color="#64748b", width=90),
                    ft.Text(str(v), size=13, color="#e2e8f0"),
                ],
                spacing=12,
            )

        return ft.Container(
            bgcolor="#0b1220",
            padding=ft.Padding.all(24),
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=64, height=64,
                                border_radius=ft.BorderRadius.all(16),
                                bgcolor="#1d4ed8",
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.MEMORY, size=32,
                                                color="#ffffff"),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("PyOS 1.0", size=24,
                                            weight=ft.FontWeight.BOLD,
                                            color="#f1f5f9"),
                                    ft.Text("Python + Flet 模拟操作系统",
                                            size=12, color="#64748b"),
                                ],
                                spacing=2,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=16,
                    ),
                    ft.Divider(height=24, color="#1e293b"),
                    row("内核", "PyOS Kernel 1.0"),
                    row("运行时", "Python " + platform.python_version()),
                    row("UI 框架", "Flet " + flet_ver),
                    row("平台", platform.system() + " " + platform.machine()),
                    row("主机名", "pyos"),
                    row("用户", self.os.shell.user),
                    row("工作目录", self.os.fs.cwd),
                    row("数据文件", self.os.fs.data_path or "（未启用）"),
                    ft.Container(expand=True),
                    ft.Text("© PyOS Project  ·  Powered by Flet",
                            size=11, color="#334155"),
                ],
                spacing=8, expand=True,
            ),
        )