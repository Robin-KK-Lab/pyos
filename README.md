\# PyOS



一个用 \*\*Python + Flet\*\* 写的模拟操作系统。桌面、Dock、窗口管理、终端、文件管理器、多用户、虚拟文件系统一应俱全。



!\[screenshot](docs/screenshot.png)



\## 特性



\- \*\*桌面环境\*\*：图标网格、拖拽重排（推箱子排列）、单击打开 / 双击重命名

\- \*\*Dock 栏\*\*：自动隐藏、悬停抛物线放大、运行中应用指示点

\- \*\*窗口管理\*\*：拖动、最小化、最大化、关闭、多窗口叠放

\- \*\*终端\*\*：`ls` `cd` `cat` `echo` `mkdir` `mv` `trash` `restore` `tree` `stat` 等 20+ 命令，支持 `>` 重定向

\- \*\*文件管理器\*\*：单击选中、双击打开、拖拽移动、重命名、新建文件夹、删除到回收站 / 永久删除 / 恢复

\- \*\*虚拟文件系统\*\*：JSON 持久化到 `pyos\_data.json`，文件内容全内存操作，重启保留

\- \*\*多用户\*\*：右上角切换用户，每个用户独立 home / Desktop / Documents / Downloads

\- \*\*快捷方式\*\*：拖文件到桌面自动生成 `.lnk`，双击打开目标

\- \*\*编辑模式\*\*：长按桌面图标触发八字抖动 + 旋转，右上角 × 删除快捷方式



\## 快速开始



```bash

git clone https://github.com/<你的用户名>/pyos.git

cd pyos

python -m venv .venv

.venv\\Scripts\\activate           # Windows

\# source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt

python main.py

```



需要 \*\*Python 3.9+\*\* 和 \*\*Flet 0.86 \~ 0.89\*\*。



\## 目录结构



```

PyOS/

├── main.py                 # 入口

├── requirements.txt

├── src/

│   ├── core/

│   │   ├── fs.py           # 虚拟文件系统 + 持久化 + 回收站 + 多用户

│   │   └── shell.py        # Shell 命令解析

│   └── ui/

│       ├── desktop.py      # 桌面 / Dock / 窗口管理器 / 用户切换

│       └── apps.py         # 终端 / 文件管理器 / 记事本 / 关于本机

└── pyos\_data.json          # 运行时生成（不提交）

```



\## 操作速查



| 位置 | 操作 | 效果 |

|---|---|---|

| 桌面图标 | 单击 | 打开应用 / 文件 / 目录 |

| 桌面图标 | 双击 | 重命名 |

| 桌面图标 | 拖动 | 重排位置（其他图标顺移） |

| 桌面图标 | 长按 | 进入编辑模式（抖动 + × 删除） |

| 桌面空白 | 从文件管理器拖文件进来 | 创建快捷方式 |

| Dock 图标 | 悬停 | 抛物线放大邻近图标 |

| Dock 图标 | 单击 | 打开 / 切换窗口 |

| 右上角头像 | 单击 | 切换用户 / 新建用户 |

| 终端 | `help` | 列出所有命令 |



\## 数据持久化



所有文件、目录、回收站、用户信息都会保存到项目根目录的 `pyos\_data.json`。



想恢复出厂设置：删除 `pyos\_data.json` 再启动即可。



\## 已知限制



\- 依赖 Flet 0.86+ 的 API（`ft.Icons` / `ft.Padding` / `page.show\_dialog` 等），旧版本不兼容

\- 拖拽重排只在松手时生效，拖动过程中不实时让位（Flet 事件频率限制）

\- 文件大小、内容都是内存模拟，不适合存大文件



\## License



MIT

