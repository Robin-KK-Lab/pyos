"""命令解释器：解析并执行终端里输入的命令。"""
import time


class Shell:
    def __init__(self, fs):
        self.fs = fs
        self.history = []
        self.user = "user"
        self.host = "pyos"

    def prompt(self):
        cwd = self.fs.cwd
        if cwd == "/home/user":
            cwd = "~"
        elif cwd.startswith("/home/user/"):
            cwd = "~" + cwd[len("/home/user"):]
        return "{0}@{1}:{2}$".format(self.user, self.host, cwd)

    @staticmethod
    def _split(line):
        out, cur, quote = [], "", None
        for ch in line:
            if quote:
                if ch == quote:
                    quote = None
                else:
                    cur += ch
            elif ch in "\"'":
                quote = ch
            elif ch.isspace():
                if cur:
                    out.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur:
            out.append(cur)
        return out

    def run(self, line):
        line = (line or "").strip()
        if not line:
            return ""
        self.history.append(line)

        redirect = None
        if ">" in line:
            head, _, tail = line.partition(">")
            line = head.strip()
            redirect = tail.strip().strip('"').strip("'")
        if not line:
            return ""

        parts = self._split(line)
        cmd, args = parts[0], parts[1:]
        handler = getattr(self, "cmd_" + cmd, None)
        if handler is None:
            return "{0}: command not found（试试 help）".format(cmd)

        try:
            out = handler(args)
        except Exception as ex:
            return "{0}: {1}".format(cmd, ex)

        if redirect:
            try:
                payload = (out or "") + ("\n" if out else "")
                self.fs.write(redirect, payload)
            except Exception as ex:
                return "{0}: {1}".format(cmd, ex)
            return ""
        return out

    # ------------------------------------------------------------------
    def cmd_help(self, args):
        return "\n".join([
            "PyOS Shell 内置命令",
            "--------------------------------------------------",
            "  help                    显示本帮助",
            "  ls [路径]               列出目录内容",
            "  cd [路径]               切换目录",
            "  pwd                     显示当前目录",
            "  mkdir <目录...>         创建目录",
            "  touch <文件...>         创建空文件",
            "  cat <文件...>           查看文件内容",
            "  echo <文本>             输出文本，支持 > 重定向",
            "  rm <路径...>            永久删除",
            "  rename <路径> <新名>    重命名",
            "  mv <源> <目标目录>      移动",
            "  trash <路径...>         删除到回收站",
            "  restore <名字...>       从回收站恢复",
            "  trashlist               列出回收站",
            "  emptytrash              清空回收站",
            "  tree [路径]             树形展示目录",
            "  stat <路径>             查看文件信息",
            "  date / whoami / uname   系统信息",
            "  history                 命令历史",
            "  clear                   清屏",
        ])

    def cmd_ls(self, args):
        path = args[0] if args else "."
        node = self.fs._get(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            return node.name
        names = self.fs.ls(path)
        if not names:
            return ""
        cells = []
        for n in names:
            child = node.children[n]
            cells.append(n + "/" if child.is_dir else n)
        return "  ".join(cells)

    def cmd_cd(self, args):
        self.fs.cd(args[0] if args else "/home/user")
        return ""

    def cmd_pwd(self, args):
        return self.fs.cwd

    def cmd_mkdir(self, args):
        if not args:
            return "mkdir: 缺少操作数"
        for a in args:
            self.fs.mkdir(a)
        return ""

    def cmd_touch(self, args):
        if not args:
            return "touch: 缺少操作数"
        for a in args:
            if not self.fs.exists(a):
                self.fs.write(a, "")
        return ""

    def cmd_cat(self, args):
        if not args:
            return "cat: 缺少操作数"
        return "\n".join(self.fs.read(a).rstrip("\n") for a in args)

    def cmd_echo(self, args):
        return " ".join(args)

    def cmd_rm(self, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            return "rm: 缺少操作数"
        for a in targets:
            self.fs.rm(a)
        return ""

    def cmd_rename(self, args):
        if len(args) != 2:
            return "用法：rename <路径> <新名字>"
        return self.fs.rename(args[0], args[1])

    def cmd_mv(self, args):
        if len(args) != 2:
            return "用法：mv <源> <目标目录>"
        return self.fs.move(args[0], args[1])

    def cmd_trash(self, args):
        if not args:
            return "trash: 缺少操作数"
        out = []
        for a in args:
            out.append(self.fs.trash(a))
        return "\n".join(out)

    def cmd_restore(self, args):
        if not args:
            return "restore: 缺少操作数"
        out = []
        for a in args:
            out.append(self.fs.restore(a))
        return "\n".join(out)

    def cmd_trashlist(self, args):
        rows = self.fs.list_trash()
        if not rows:
            return "（回收站为空）"
        return "\n".join("{0:<24} <- {1}".format(n, o or "?") for n, o in rows)

    def cmd_emptytrash(self, args):
        n = self.fs.empty_trash()
        return "已清空 {0} 项".format(n)

    def cmd_tree(self, args):
        path = args[0] if args else "."
        node = self.fs._get(path)
        if node is None:
            return "tree: {0}: 没有那个文件或目录".format(path)
        if not node.is_dir:
            return node.name
        lines = [self.fs._norm(path)]
        self._walk(node, "", lines)
        return "\n".join(lines)

    def _walk(self, node, prefix, lines):
        items = sorted(node.children.items())
        for i, (name, child) in enumerate(items):
            last = (i == len(items) - 1)
            lines.append(prefix + ("└── " if last else "├── ") + name +
                         ("/" if child.is_dir else ""))
            if child.is_dir:
                self._walk(child, prefix + ("    " if last else "│   "), lines)

    def cmd_stat(self, args):
        if not args:
            return "stat: 缺少操作数"
        info = self.fs.stat(args[0])
        kind = "目录" if info["is_dir"] else "文件"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info["modified"]))
        return "名称: {0}\n类型: {1}\n大小: {2} 字节\n修改: {3}".format(
            info["name"], kind, info["size"], stamp)

    def cmd_date(self, args):
        return time.strftime("%Y-%m-%d %H:%M:%S  %A")

    def cmd_whoami(self, args):
        return self.user

    def cmd_uname(self, args):
        return "PyOS 1.0 pyos x86_64 (Flet Edition)"

    def cmd_history(self, args):
        return "\n".join("{0:4d}  {1}".format(i + 1, c)
                         for i, c in enumerate(self.history))

    def cmd_clear(self, args):
        return "\x0c"