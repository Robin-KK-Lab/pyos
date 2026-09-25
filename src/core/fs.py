"""虚拟文件系统：目录树 + JSON 持久化 + 回收站 + 多用户 + 快捷方式。"""
import json
import os
import time


class Node:
    def __init__(self, name, is_dir=False):
        self.name = name
        self.is_dir = is_dir
        self.children = {} if is_dir else None
        self.content = None if is_dir else ""
        self.created = time.time()
        self.modified = time.time()
        self.origin = None

    def to_dict(self):
        d = {"name": self.name, "is_dir": self.is_dir,
             "created": self.created, "modified": self.modified,
             "origin": self.origin}
        if self.is_dir:
            d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        else:
            d["content"] = self.content or ""
        return d

    @classmethod
    def from_dict(cls, d):
        node = cls(d["name"], bool(d.get("is_dir")))
        node.created = d.get("created", time.time())
        node.modified = d.get("modified", time.time())
        node.origin = d.get("origin")
        if node.is_dir:
            for k, v in (d.get("children") or {}).items():
                node.children[k] = cls.from_dict(v)
        else:
            node.content = d.get("content", "")
        return node


class VirtualFS:
    def __init__(self, data_path=None):
        self.data_path = data_path
        self.root = Node("/", is_dir=True)
        self.cwd = "/home/user"
        self.current_user = "user"
        self.users = {}
        loaded = False
        if data_path and os.path.exists(data_path):
            try:
                self._load()
                loaded = True
            except Exception:
                loaded = False
        if not loaded:
            self._build_default()
            self._save()

    # ---------- 持久化 ----------
    def _save(self):
        if not self.data_path:
            return
        try:
            data = {"cwd": self.cwd, "current_user": self.current_user,
                    "users": self.users, "root": self.root.to_dict()}
            tmp = self.data_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.data_path)
        except Exception:
            pass

    def _load(self):
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.root = Node.from_dict(data["root"])
        self.cwd = data.get("cwd", "/home/user")
        self.current_user = data.get("current_user", "user")
        self.users = data.get("users") or {}
        if not self.users:
            self.users = {"user": {"home": "/home/user",
                                   "full_name": "普通用户"}}
            if not self.exists("/home/user/Desktop"):
                self.mkdir("/home/user/Desktop")

    def reset(self):
        self.root = Node("/", is_dir=True)
        self.cwd = "/home/user"
        self.current_user = "user"
        self.users = {}
        self._build_default()
        self._save()

    # ---------- 默认目录 ----------
    def _build_default(self):
        self.mkdir("/home")
        self.mkdir("/etc")
        self.mkdir("/tmp")
        self.mkdir("/var")
        self.mkdir("/trash")
        self.add_user("user", "普通用户")
        self.add_user("guest", "访客")
        self.current_user = "user"
        self.cwd = self.home_of("user")
        self.write("/etc/hostname", "pyos\n")
        self.write("/etc/os-release", 'NAME="PyOS"\nVERSION="1.0"\nID=pyos\n')
        self.write("/home/user/readme.txt",
                   "欢迎使用 PyOS！\n=================\n\n"
                   "· 拖动文件到桌面，可创建桌面快捷方式\n"
                   "· 桌面文件夹：~/Desktop\n"
                   "· 快捷方式后缀 .lnk，双击可打开目标\n"
                   "· 删除的文件进入回收站 /trash\n")

    # ---------- 用户系统 ----------
    def add_user(self, username, full_name=""):
        username = (username or "").strip()
        if not username or "/" in username or username in (".", ".."):
            raise ValueError("非法用户名")
        home = "/home/" + username
        if username not in self.users:
            self.users[username] = {"home": home,
                                     "full_name": full_name or username}
        for d in (home, home + "/Desktop", home + "/Documents",
                  home + "/Downloads"):
            if not self.exists(d):
                self.mkdir(d)
        self._save()
        return self.users[username]

    def remove_user(self, username):
        if username == "user":
            raise PermissionError("不能删除主用户")
        if username not in self.users:
            raise KeyError(username)
        home = self.users[username]["home"]
        if self.exists(home):
            self.rm(home)
        del self.users[username]
        if self.current_user == username:
            self.current_user = "user"
            self.cwd = self.home_of("user")
        self._save()

    def home_of(self, username=None):
        username = username or self.current_user
        info = self.users.get(username)
        if not info:
            return "/home/" + username
        return info["home"]

    def desktop_of(self, username=None):
        return self.home_of(username).rstrip("/") + "/Desktop"

    def switch_user(self, username):
        if username not in self.users:
            raise KeyError("用户不存在: " + username)
        self.current_user = username
        self.cwd = self.home_of(username)
        if not self.exists(self.desktop_of()):
            self.mkdir(self.desktop_of())
        self._save()
        return username

    def list_users(self):
        return [(name, self.users[name].get("full_name", name))
                for name in sorted(self.users.keys())]

    # ---------- 快捷方式 ----------
    @staticmethod
    def is_shortcut(path):
        return str(path).lower().endswith(".lnk")

    def shortcut_target(self, path):
        if not self.is_shortcut(path):
            return None
        try:
            content = self.read(path).strip()
            return content or None
        except Exception:
            return None

    def make_shortcut(self, target_path, dest_dir, name=None):
        target = self._norm(target_path)
        if not self.exists(target):
            raise FileNotFoundError(target_path)
        dest = self._norm(dest_dir)
        if not self.exists(dest):
            self.mkdir(dest)
        if not self.is_dir(dest):
            raise NotADirectoryError(dest_dir)
        base = (name or target.rstrip("/").split("/")[-1]).strip()
        if not base:
            raise ValueError("非法名称")
        if base.lower().endswith(".lnk"):
            base = base[:-4]
        link_name = base + ".lnk"
        link_path = dest.rstrip("/") + "/" + link_name
        if self.exists(link_path):
            for i in range(1, 1000):
                cand = "{0} ({1}).lnk".format(base, i)
                cand_path = dest.rstrip("/") + "/" + cand
                if not self.exists(cand_path):
                    link_path = cand_path
                    break
        self.write(link_path, target)
        return link_path

    # ---------- 路径处理 ----------
    def _norm(self, path):
        if path is None:
            path = "."
        path = str(path).strip()
        if path == "~":
            path = self.home_of()
        elif path.startswith("~/"):
            path = self.home_of() + path[1:]
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
        parts = []
        for seg in path.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(seg)
        return "/" + "/".join(parts)

    def _get(self, path):
        p = self._norm(path)
        if p == "/":
            return self.root
        node = self.root
        for seg in p.strip("/").split("/"):
            if not node.is_dir or seg not in node.children:
                return None
            node = node.children[seg]
        return node

    @staticmethod
    def _parent_of(p):
        return "/".join(p.split("/")[:-1]) or "/"

    @staticmethod
    def _unique_name(parent, name):
        if name not in parent.children:
            return name
        stem, ext = os.path.splitext(name)
        for i in range(1, 1000):
            c = "{0} ({1}){2}".format(stem, i, ext)
            if c not in parent.children:
                return c
        return "{0}_{1}{2}".format(stem, int(time.time()), ext)

    # ---------- 基础操作 ----------
    def exists(self, path):
        return self._get(path) is not None

    def is_dir(self, path):
        node = self._get(path)
        return node is not None and node.is_dir

    def mkdir(self, path, parents=True):
        p = self._norm(path)
        node = self.root
        for i, seg in enumerate([s for s in p.strip("/").split("/") if s]):
            if seg not in node.children:
                if not parents and i != len(p.strip("/").split("/")) - 1:
                    raise FileNotFoundError(p)
                node.children[seg] = Node(seg, is_dir=True)
            child = node.children[seg]
            if not child.is_dir:
                raise NotADirectoryError(p)
            node = child
        node.modified = time.time()
        self._save()
        return p

    def write(self, path, content):
        p = self._norm(path)
        if p == "/":
            raise IsADirectoryError(path)
        parent_path = self._parent_of(p)
        parent = self._get(parent_path)
        if parent is None:
            self.mkdir(parent_path)
            parent = self._get(parent_path)
        if not parent.is_dir:
            raise NotADirectoryError(parent_path)
        name = p.split("/")[-1]
        if name in parent.children and parent.children[name].is_dir:
            raise IsADirectoryError(p)
        if name in parent.children:
            parent.children[name].content = content
            parent.children[name].modified = time.time()
        else:
            node = Node(name, is_dir=False)
            node.content = content
            parent.children[name] = node
        self._save()
        return p

    def read(self, path):
        node = self._get(path)
        if node is None:
            raise FileNotFoundError(path)
        if node.is_dir:
            raise IsADirectoryError(path)
        return node.content or ""

    def ls(self, path="."):
        node = self._get(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            return [node.name]
        return sorted(node.children.keys())

    def rm(self, path):
        p = self._norm(path)
        if p == "/":
            raise PermissionError("不能删除根目录")
        parent = self._get(self._parent_of(p))
        name = p.split("/")[-1]
        if parent is None or name not in parent.children:
            raise FileNotFoundError(path)
        del parent.children[name]
        parent.modified = time.time()
        self._save()

    def cd(self, path):
        node = self._get(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            raise NotADirectoryError(path)
        self.cwd = self._norm(path)
        self._save()
        return self.cwd

    def stat(self, path):
        node = self._get(path)
        if node is None:
            raise FileNotFoundError(path)
        return {"name": node.name, "is_dir": node.is_dir,
                "size": 0 if node.is_dir else len(node.content or ""),
                "modified": node.modified}

    def rename(self, path, new_name):
        p = self._norm(path)
        if p == "/":
            raise PermissionError("不能重命名根目录")
        new_name = (new_name or "").strip()
        if not new_name or "/" in new_name or new_name in (".", ".."):
            raise ValueError("非法名称")
        parent = self._get(self._parent_of(p))
        old_name = p.split("/")[-1]
        if parent is None or old_name not in parent.children:
            raise FileNotFoundError(path)
        if new_name != old_name and new_name in parent.children:
            raise FileExistsError("同名已存在: " + new_name)
        node = parent.children.pop(old_name)
        node.name = new_name
        node.modified = time.time()
        parent.children[new_name] = node
        self._save()
        return self._parent_of(p).rstrip("/") + "/" + new_name

    def move(self, src, dst_dir):
        src_p = self._norm(src)
        dst_p = self._norm(dst_dir)
        if src_p == "/":
            raise PermissionError("不能移动根目录")
        dst_node = self._get(dst_p)
        if dst_node is None:
            raise FileNotFoundError(dst_dir)
        if not dst_node.is_dir:
            raise NotADirectoryError(dst_dir)
        if dst_p == src_p or dst_p.startswith(src_p.rstrip("/") + "/"):
            raise ValueError("不能移动到自身或子目录")
        src_parent = self._get(self._parent_of(src_p))
        old_name = src_p.split("/")[-1]
        if src_parent is None or old_name not in src_parent.children:
            raise FileNotFoundError(src)
        final_name = self._unique_name(dst_node, old_name)
        node = src_parent.children.pop(old_name)
        node.name = final_name
        node.modified = time.time()
        dst_node.children[final_name] = node
        self._save()
        return dst_p.rstrip("/") + "/" + final_name

    # ---------- 回收站 ----------
    def trash(self, path):
        p = self._norm(path)
        if p == "/" or p == "/trash" or p.startswith("/trash/"):
            raise PermissionError("不能删除该路径")
        if not self.exists("/trash"):
            self.mkdir("/trash")
        trash_root = self._get("/trash")
        src_parent = self._get(self._parent_of(p))
        name = p.split("/")[-1]
        if src_parent is None or name not in src_parent.children:
            raise FileNotFoundError(path)
        final_name = self._unique_name(trash_root, name)
        node = src_parent.children.pop(name)
        node.origin = p
        node.name = final_name
        node.modified = time.time()
        trash_root.children[final_name] = node
        self._save()
        return "/trash/" + final_name

    def restore(self, name_or_path):
        trash_root = self._get("/trash")
        if trash_root is None:
            raise FileNotFoundError("/trash")
        name = name_or_path
        if "/" in name_or_path:
            name = name_or_path.rstrip("/").split("/")[-1]
        if name not in trash_root.children:
            raise FileNotFoundError(name)
        node = trash_root.children.pop(name)
        origin = node.origin or ("/home/user/" + node.name)
        parent_path = self._parent_of(origin)
        if not self.exists(parent_path):
            self.mkdir(parent_path)
        parent = self._get(parent_path)
        final_name = self._unique_name(parent, node.name)
        node.name = final_name
        node.origin = None
        node.modified = time.time()
        parent.children[final_name] = node
        self._save()
        return parent_path.rstrip("/") + "/" + final_name

    def empty_trash(self):
        trash_root = self._get("/trash")
        if trash_root is None:
            return 0
        n = len(trash_root.children)
        trash_root.children.clear()
        trash_root.modified = time.time()
        self._save()
        return n

    def list_trash(self):
        trash_root = self._get("/trash")
        if trash_root is None:
            return []
        return [(name, trash_root.children[name].origin)
                for name in sorted(trash_root.children.keys())]