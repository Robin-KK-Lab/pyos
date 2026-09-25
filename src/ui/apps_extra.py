"""PyOS 附加应用：计算器。"""
import flet as ft

from src.ui.apps import BaseApp


class CalculatorApp(BaseApp):
    name = "计算器"
    icon = ft.Icons.CALCULATE
    color = "#64748b"
    width = 340
    height = 520

    def __init__(self, os_ctx, **kwargs):
        super().__init__(os_ctx, **kwargs)
        self.current = "0"
        self.pending = None
        self.op = None
        self.just_calculated = False
        self.op_pressed = False

    def build(self):
        self.expr_text = ft.Text("", size=13, color="#64748b",
                                 text_align=ft.TextAlign.RIGHT)
        self.result_text = ft.Text("0", size=42, color="#f1f5f9",
                                   weight=ft.FontWeight.W_300,
                                   text_align=ft.TextAlign.RIGHT)

        display = ft.Container(
            padding=ft.Padding.only(left=20, right=20, top=20, bottom=16),
            alignment=ft.Alignment.BOTTOM_RIGHT,
            content=ft.Column(
                controls=[self.expr_text, self.result_text],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.END,
                alignment=ft.MainAxisAlignment.END))

        layout = [
            [("AC", "fn"), ("±", "fn"), ("%", "fn"), ("÷", "op")],
            [("7", "num"), ("8", "num"), ("9", "num"), ("×", "op")],
            [("4", "num"), ("5", "num"), ("6", "num"), ("-", "op")],
            [("1", "num"), ("2", "num"), ("3", "num"), ("+", "op")],
            [("0", "wide"), (".", "num"), ("=", "op")],
        ]

        rows = []
        for r in layout:
            cells = [self._make_key(lb, kind) for lb, kind in r]
            rows.append(ft.Row(controls=cells, spacing=8, expand=True))

        return ft.Container(
            bgcolor="#0b1220",
            padding=ft.Padding.all(12),
            expand=True,
            content=ft.Column(
                controls=[display,
                          ft.Column(controls=rows, spacing=8, expand=True)],
                spacing=0, expand=True))

    def _make_key(self, label, kind):
        if kind == "fn":
            bg, fg = "#334155", "#f1f5f9"
        elif kind == "op":
            bg, fg = "#f59e0b", "#ffffff"
        else:
            bg, fg = "#1e293b", "#f1f5f9"

        key = ft.Container(
            bgcolor=bg,
            border_radius=ft.BorderRadius.all(24),
            alignment=ft.Alignment.CENTER,
            expand=2 if kind == "wide" else 1,
            height=64,
            on_click=lambda e, lb=label: self._on_key(lb),
            content=ft.Text(label, size=20, color=fg))

        def on_hover(e, k=key, base=bg):
            try:
                if str(e.data).lower() == "true":
                    if base == "#1e293b":
                        k.bgcolor = "#334155"
                    elif base == "#f59e0b":
                        k.bgcolor = "#fbbf24"
                    else:
                        k.bgcolor = "#475569"
                else:
                    k.bgcolor = base
                k.update()
            except Exception:
                pass
        key.on_hover = on_hover
        return key

    def _on_key(self, label):
        if label == "AC":
            self.current = "0"
            self.pending = None
            self.op = None
            self.just_calculated = False
            self.op_pressed = False

        elif label == "±":
            if self.current.startswith("-"):
                self.current = self.current[1:]
            elif self.current not in ("0", "0."):
                self.current = "-" + self.current

        elif label == "%":
            try:
                self.current = self._fmt(float(self.current) / 100)
                self.op_pressed = False
            except Exception:
                pass

        elif label in ("+", "-", "×", "÷"):
            # 连按运算符：只更新运算符，不重复计算
            if self.op and self.pending is not None and not self.op_pressed:
                self._compute()
            self.pending = self.current
            self.op = label
            self.just_calculated = False
            self.current = ""
            self.op_pressed = True

        elif label == "=":
            if self.op and self.pending is not None:
                if self.op_pressed:
                    # ???????? =?? pending ????
                    self.current = self.pending
                    self.op = None
                    self.pending = None
                else:
                    self._compute()
                    self.op = None
                    self.pending = None
                self.just_calculated = True
                self.op_pressed = False

        elif label == ".":
            if self.op_pressed or self.just_calculated or not self.current:
                self.current = "0."
                self.op_pressed = False
                self.just_calculated = False
            elif "." not in self.current:
                self.current += "."

        else:
            if self.op_pressed or self.just_calculated:
                self.current = label
                self.op_pressed = False
                self.just_calculated = False
            elif self.current == "0":
                self.current = label
            else:
                self.current += label

        self._refresh()

    def _compute(self):
        try:
            a = float(self.pending)
            b = float(self.current or "0")
        except Exception:
            return
        if self.op == "+":
            r = a + b
        elif self.op == "-":
            r = a - b
        elif self.op == "×":
            r = a * b
        elif self.op == "÷":
            if b == 0:
                self.current = "错误"
                self.pending = None
                self.op = None
                return
            r = a / b
        else:
            return
        self.current = self._fmt(r)

    @staticmethod
    def _fmt(v):
        if v == int(v):
            return str(int(v))
        return "{:.10g}".format(v)

    def _refresh(self):
        self.result_text.value = self.current if self.current else ""
        if self.op and self.pending is not None:
            self.expr_text.value = "{} {}".format(self.pending, self.op)
        else:
            self.expr_text.value = ""
        try:
            self.result_text.update()
            self.expr_text.update()
        except Exception:
            pass