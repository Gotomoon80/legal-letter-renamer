# -*- coding: utf-8 -*-
"""主窗口：批量文档重命名助手（Tkinter / ttk）。"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import List, Optional

from ..core import config, logger
from ..core import content_reader, matcher, rename_engine, report, scanner, template as tpl
from ..core.matcher import MatchItem
from ..core.rename_engine import PlanRow, STATUS_TEXT
from ..core.roster import RosterEntry, load_roster

log = logger.get_logger("ui")

COLUMNS = [
    ("idx", "序号", 64),
    ("src", "原文件名", 300),
    ("pseq", "识别序号", 90),
    ("cand", "识别姓名", 130),
    ("name", "匹配姓名", 130),
    ("new", "新文件名", 320),
    ("status", "状态", 100),
    ("note", "备注", 220),
]

# ---------------------------------------------------------------------------
# 外观：仿 Trae 暗色主题 + 版权信息
# ---------------------------------------------------------------------------
PALETTE = {
    "bg": "#1e1e1e",        # 主背景
    "panel": "#252526",     # 面板
    "field": "#2d2d30",     # 输入框/表格
    "border": "#3c3c3c",
    "fg": "#d4d4d4",        # 主文字
    "muted": "#9d9d9d",     # 次要文字
    "accent": "#4a9eff",    # 强调色
    "sel_bg": "#094771",
    "sel_fg": "#ffffff",
    "ok": "#4ec9b0",
    "warn": "#ce9178",
    "err": "#f48771",
}

SPLASH_MS = 1900            # 权利声明页停留时长（毫秒）
AUTHOR_NAME = "田野"
AUTHOR_ID = "麦田律 / mikelawyer"
AUTHOR_TITLE = "北京执业律师"
COPYRIGHT = "免费软件(freeware) · © 2026 %s（%s）· %s" % (AUTHOR_NAME, AUTHOR_ID, AUTHOR_TITLE)

_FONT_FAMILY = "Microsoft YaHei UI"


def _font(size: int = 11, bold: bool = False):
    return (_FONT_FAMILY, size, "bold" if bold else "normal")


def setup_fonts(root: tk.Tk) -> None:
    """把全局字体统一调大一点，并保证控件内部留白足够、文字不被边框裁切。"""
    global _FONT_FAMILY
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for fam in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"):
        if fam in families:
            _FONT_FAMILY = fam
            break
    for name, size, weight in (("TkDefaultFont", 11, "normal"),
                               ("TkTextFont", 11, "normal"),
                               ("TkMenuFont", 11, "normal"),
                               ("TkHeadingFont", 11, "bold"),
                               ("TkTooltipFont", 11, "normal")):
        try:
            tkfont.nametofont(name).configure(family=_FONT_FAMILY, size=size, weight=weight)
        except Exception:
            pass


def apply_dark_theme(root: tk.Tk) -> None:
    """应用仿 Trae 的暗色主题。"""
    p = PALETTE
    root.configure(bg=p["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=p["bg"], foreground=p["fg"],
                    fieldbackground=p["field"], bordercolor=p["border"],
                    lightcolor=p["panel"], darkcolor=p["bg"],
                    troughcolor=p["bg"], focuscolor=p["bg"])
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("Status.TLabel", background=p["panel"],
                    foreground=p["muted"], padding=(8, 5))
    style.configure("TCheckbutton", background=p["bg"], foreground=p["fg"],
                    focuscolor=p["bg"], padding=(2, 3))
    style.map("TCheckbutton",
              background=[("active", p["bg"])],
              foreground=[("disabled", p["muted"])])
    style.configure("TLabelframe", background=p["bg"], bordercolor=p["border"],
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["accent"],
                    font=_font(11, True), padding=(4, 2))
    style.configure("TButton", background=p["panel"], foreground=p["fg"],
                    bordercolor=p["border"], padding=(12, 6), relief="flat",
                    focuscolor=p["bg"])
    style.map("TButton",
              background=[("active", p["field"]), ("pressed", p["field"]),
                          ("disabled", p["panel"])],
              foreground=[("disabled", p["muted"])])
    style.configure("TEntry", fieldbackground=p["field"], foreground=p["fg"],
                    insertcolor=p["fg"], bordercolor=p["border"], padding=5,
                    selectbackground=p["sel_bg"], selectforeground=p["sel_fg"])
    style.configure("TCombobox", fieldbackground=p["field"], background=p["field"],
                    foreground=p["fg"], arrowcolor=p["fg"], bordercolor=p["border"],
                    padding=5, selectbackground=p["sel_bg"], selectforeground=p["sel_fg"])
    style.map("TCombobox",
              fieldbackground=[("readonly", p["field"]), ("disabled", p["panel"])],
              foreground=[("readonly", p["fg"]), ("disabled", p["muted"])],
              background=[("readonly", p["field"]), ("active", p["field"])])
    style.configure("TSpinbox", fieldbackground=p["field"], background=p["field"],
                    foreground=p["fg"], arrowcolor=p["fg"], bordercolor=p["border"],
                    padding=5, selectbackground=p["sel_bg"], selectforeground=p["sel_fg"])
    style.map("TSpinbox",
              fieldbackground=[("disabled", p["panel"])],
              foreground=[("disabled", p["muted"])])
    style.configure("Treeview", background=p["panel"], fieldbackground=p["panel"],
                    foreground=p["fg"], bordercolor=p["border"], borderwidth=1,
                    rowheight=28, font=_font(11))
    style.map("Treeview",
              background=[("selected", p["sel_bg"])],
              foreground=[("selected", p["sel_fg"])])
    style.configure("Treeview.Heading", background=p["field"], foreground=p["fg"],
                    relief="flat", font=_font(11, True), padding=(4, 6))
    style.map("Treeview.Heading", background=[("active", p["border"])])
    style.configure("TScrollbar", background=p["panel"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["muted"])
    style.map("TScrollbar", background=[("active", p["border"])])
    style.configure("TProgressbar", background=p["accent"], troughcolor=p["field"],
                    bordercolor=p["field"], lightcolor=p["accent"], darkcolor=p["accent"])
    # 下拉列表用的是原生 Listbox，只能通过 option 改配色
    root.option_add("*TCombobox*Listbox.background", p["field"])
    root.option_add("*TCombobox*Listbox.foreground", p["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["sel_bg"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["sel_fg"])


def build_splash(root: tk.Tk) -> tk.Toplevel:
    """启动时的"权利声明页"，约 1.9 秒后自动关闭。"""
    p = PALETTE
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=p["border"])
    w, h = 600, 340
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 2))
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass

    body = tk.Frame(win, bg=p["panel"])
    body.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(body, text=config.APP_NAME, bg=p["panel"], fg=p["fg"],
             font=_font(20, True)).pack(pady=(30, 2))
    tk.Label(body, text="权 利 声 明", bg=p["panel"], fg=p["accent"],
             font=_font(13, True)).pack(pady=(0, 14))
    for text in ("本程序为免费软件（freeware），可自由使用与传播，禁止用于商业销售。",
                 "制作人：%s（%s）· %s" % (AUTHOR_NAME, AUTHOR_ID, AUTHOR_TITLE),
                 "由 IDE 中指导 LLM 制作",
                 "版权所有 © 2026 %s" % AUTHOR_NAME):
        tk.Label(body, text=text, bg=p["panel"], fg=p["muted"],
                 font=_font(11)).pack(pady=3)
    tk.Label(body, text="v%s" % config.APP_VERSION, bg=p["panel"], fg=p["border"],
             font=_font(10)).pack(side="bottom", pady=12)
    return win


# ---------------------------------------------------------------------------
# 悬停说明：鼠标停在控件上时浮现的提示文字
# ---------------------------------------------------------------------------
TIPS = {
    "folder": "目标文件夹：要批量处理的文件所在的文件夹。\n点「浏览…」选择；勾选「包含子文件夹」可连子目录一起处理。",
    "roster": "名单文件：导入客户名单，程序据此「对号入座」。\n"
              "支持 Excel（.xlsx / .xls / .xlsm）、CSV 和纯文本（.txt，每行一个姓名）。\n"
              "程序会自动识别姓名列（表头写「序号 / 姓名 / 备注」均可）。\n"
              "名单文件本身不会被重命名。",
    "roster_btns": "查看名单：预览已导入的姓名。\n清空名单：移除当前名单，不影响磁盘上的文件。",
    "mode": "姓名来源：决定从哪里取姓名来对号入座。\n"
            "· 从文件名识别：从文件名里解析姓名。\n"
            "· 从文档内容识别（推荐）：逐个读文档正文，从称谓里取姓名，\n"
            "  例如正文写「尊敬的张三」就取「张三」——文件名再乱也能对上。\n"
            "· 按文件夹顺序对应名单：不看名字，按排序后的文件顺序与名单一一对应。",
    "sort": "排序方式：决定文件参与匹配与编号的先后。\n可按文件名、文件大小、修改时间升序或降序。\n在「从文档内容识别」模式下，顺序不影响结果。",
    "fallback": "姓名匹配不上时按顺序补齐：\n"
                "勾选后，没识别出姓名的文件会用名单中剩余的姓名按顺序补上。\n"
                "注意：这会造成「名不对人」，预览时会弹窗提醒；\n"
                "若文档正文里写了姓名，请改用「从文档内容识别」。",
    "recursive": "包含子文件夹：勾选后连子文件夹里的文件一起处理。",
    "types": "文件类型：只处理勾选的类型（Word / Excel / PDF / 图片…）。\n勾选「全部类型」则不限制类型。",
    "template": "命名模板：决定新文件名长什么样。\n"
                "可用占位符：{序号} {姓名} {原名} {主体} {扩展名}\n"
                "例如：《{序号}致{姓名}的缴费通知书》",
    "preset": "模板预设：常用模板，选中后会自动填入上面的模板框。",
    "seq_start": "序号起始：第一个文件的序号从几开始，默认 1。",
    "seq_width": "序号位数：序号补零的位数。例如位数=2 时是 01、02…99。",
    "seq_style": "序号样式：序号怎么写。\n"
                 "· 阿拉伯数字（0001）\n"
                 "· 圈号（①②③…，Unicode 只到 ㊿ 共 50 个，超出会自动退回数字）\n"
                 "· 中文（一二三…）",
    "replace_orig": "在原文件名中替换识别到的姓名：配合模板里的 {原名} 使用，\n"
                    "把原文件名里与姓名有关的字样换成识别出的姓名。",
    "preview": "刷新预览：扫描文件夹并按当前设置生成重命名计划，显示在下方表格。\n这一步只做展示，不会改动任何文件。",
    "run": "执行重命名：按表格中的计划真正改名（只执行状态为「可执行」的行）。\n"
           "改名前建议先「导出对照表」留档；改错了可用「撤销上次」还原。",
    "undo": "撤销上次：把最近一次重命名还原回去（依据改名时自动保存的撤销记录）。",
    "export": "导出对照表：把本次的「原名 → 新名」导出成 Excel，便于核对与存档。",
    "log": "打开日志：查看每一步操作记录。\n若程序出错，把日志文件夹里的 crash.log 发给开发者即可。",
    "tree": "预览表格：\n"
            "· 识别姓名：从文件名或文档内容里认出来的名字。\n"
            "· 匹配姓名：与名单对上的那个人（最终采用）。\n"
            "· 状态：可执行 / 未变 / 重名 / 缺姓名 / 文件已存在。\n"
            "绿色=可执行，橙色=需留意，红色=有问题。",
}


class Tooltip:
    """鼠标悬停在控件上时，浮现说明气泡。"""

    def __init__(self, widget, text: str, delay: int = 400, wraplength: int = 420):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._tip = None
        self._after_id = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip or not self.text:
            return
        p = PALETTE
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.configure(bg=p["border"])
        tk.Label(tip, text=self.text, justify="left", bg=p["field"], fg=p["fg"],
                 font=_font(10), wraplength=self.wraplength, padx=10, pady=8,
                 relief="flat", anchor="w").pack(padx=1, pady=1)
        tip.wm_geometry("+%d+%d" % (x, y))
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass
        self._tip = tip

    def _hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: List[scanner.FileItem] = []
        self.roster: List[RosterEntry] = []
        self.items: List[MatchItem] = []
        self.rows: List[PlanRow] = []
        self._busy = False
        self._queue: "queue.Queue" = queue.Queue()

        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_banner(self):
        """顶部横幅：程序名 + 版本 + 免费软件与版权信息。"""
        p = PALETTE
        banner = tk.Frame(self.root, bg=p["panel"], highlightthickness=1,
                          highlightbackground=p["border"])
        banner.pack(fill="x", side="top")
        tk.Label(banner, text=config.APP_NAME, bg=p["panel"], fg=p["fg"],
                 font=_font(15, True)).pack(side="left", padx=(14, 8), pady=10)
        tk.Label(banner, text="v%s" % config.APP_VERSION, bg=p["panel"],
                 fg=p["muted"], font=_font(10)).pack(side="left", pady=(18, 10))
        tk.Label(banner, text=COPYRIGHT, bg=p["panel"], fg=p["accent"],
                 font=_font(10)).pack(side="right", padx=14, pady=12)

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.root.title("%s v%s" % (config.APP_NAME, config.APP_VERSION))
        self.root.geometry("1320x840")
        self.root.minsize(1160, 720)

        self._build_banner()

        pad = {"padx": 8, "pady": 5}

        def tip(widget, key):
            """给控件挂上悬停说明。"""
            return Tooltip(widget, TIPS.get(key, ""))

        # --- 1. 数据选择 ---
        f1 = ttk.LabelFrame(self.root, text="1. 选择数据")
        f1.pack(fill="x", **pad)

        lb_folder = ttk.Label(f1, text="目标文件夹：")
        lb_folder.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.folder_var = tk.StringVar()
        w_folder = ttk.Entry(f1, textvariable=self.folder_var)
        w_folder.grid(row=0, column=1, sticky="ew", padx=4)
        w_browse = ttk.Button(f1, text="浏览…", command=self.choose_folder, width=8)
        w_browse.grid(row=0, column=2, padx=4)
        for w in (lb_folder, w_folder, w_browse):
            tip(w, "folder")

        lb_roster = ttk.Label(f1, text="名单文件：")
        lb_roster.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.roster_var = tk.StringVar()
        w_roster = ttk.Entry(f1, textvariable=self.roster_var)
        w_roster.grid(row=1, column=1, sticky="ew", padx=4)
        w_import = ttk.Button(f1, text="导入名单…", command=self.import_roster, width=10)
        w_import.grid(row=1, column=2, padx=4)
        for w in (lb_roster, w_roster, w_import):
            tip(w, "roster")

        ttk.Label(f1, text="已加载名单：").grid(row=1, column=3, sticky="e", padx=(20, 4))
        self.roster_count_var = tk.StringVar(value="0 条")
        ttk.Label(f1, textvariable=self.roster_count_var, foreground=PALETTE["accent"]).grid(row=1, column=4, sticky="w")
        w_show = ttk.Button(f1, text="查看名单", command=self.show_roster, width=9)
        w_show.grid(row=1, column=5, padx=4)
        w_clear = ttk.Button(f1, text="清空名单", command=self.clear_roster, width=9)
        w_clear.grid(row=1, column=6, padx=4)
        for w in (w_show, w_clear):
            tip(w, "roster_btns")

        f1.columnconfigure(1, weight=1)

        # --- 2. 匹配与排序 ---
        f2 = ttk.LabelFrame(self.root, text="2. 匹配方式")
        f2.pack(fill="x", **pad)

        lb_mode = ttk.Label(f2, text="姓名来源：")
        lb_mode.grid(row=0, column=0, sticky="w", padx=4)
        _default_mode = next((d for d, v in config.NAME_SOURCES
                              if v == config.DEFAULT_NAME_SOURCE), config.NAME_SOURCES[0][0])
        self.mode_var = tk.StringVar(value=_default_mode)
        self.mode_combo = ttk.Combobox(f2, textvariable=self.mode_var, state="readonly", width=24,
                                       values=[s[0] for s in config.NAME_SOURCES])
        self.mode_combo.grid(row=0, column=1, padx=4)
        tip(lb_mode, "mode")
        tip(self.mode_combo, "mode")

        lb_sort = ttk.Label(f2, text="排序方式：")
        lb_sort.grid(row=0, column=2, sticky="w", padx=(20, 4))
        self.sort_var = tk.StringVar(value=config.SORT_OPTIONS[0][0])
        w_sort = ttk.Combobox(f2, textvariable=self.sort_var, state="readonly", width=18,
                              values=[s[0] for s in config.SORT_OPTIONS])
        w_sort.grid(row=0, column=3, padx=4)
        tip(lb_sort, "sort")
        tip(w_sort, "sort")

        self.fallback_var = tk.BooleanVar(value=True)
        w_fallback = ttk.Checkbutton(f2, text="姓名匹配不上时按顺序补齐", variable=self.fallback_var)
        w_fallback.grid(row=0, column=4, padx=(20, 4))
        tip(w_fallback, "fallback")

        self.recursive_var = tk.BooleanVar(value=False)
        w_recursive = ttk.Checkbutton(f2, text="包含子文件夹", variable=self.recursive_var)
        w_recursive.grid(row=0, column=5, padx=4)
        tip(w_recursive, "recursive")

        ttk.Label(f2, text="文件类型：").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.type_vars = {}
        col = 1
        for g in config.EXT_GROUPS:
            v = tk.BooleanVar(value=(g in ("Word", "Excel")))
            self.type_vars[g] = v
            w_type = ttk.Checkbutton(f2, text=g, variable=v)
            w_type.grid(row=1, column=col, sticky="w", padx=4)
            tip(w_type, "types")
            col += 1
        self.all_type_var = tk.BooleanVar(value=False)
        w_all = ttk.Checkbutton(f2, text="全部类型", variable=self.all_type_var)
        w_all.grid(row=1, column=col, sticky="w", padx=4)
        tip(w_all, "types")

        # --- 3. 命名规则 ---
        f3 = ttk.LabelFrame(self.root, text="3. 命名规则（模板）")
        f3.pack(fill="x", **pad)

        lb_tpl = ttk.Label(f3, text="模板：")
        lb_tpl.grid(row=0, column=0, sticky="w", padx=4)
        self.template_var = tk.StringVar(value=config.DEFAULT_TEMPLATE)
        w_tpl = ttk.Entry(f3, textvariable=self.template_var)
        w_tpl.grid(row=0, column=1, sticky="ew", padx=4)
        tip(lb_tpl, "template")
        tip(w_tpl, "template")

        lb_preset = ttk.Label(f3, text="预设：")
        lb_preset.grid(row=0, column=2, sticky="e", padx=(12, 4))
        self.preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(f3, textvariable=self.preset_var, state="readonly", width=20,
                                    values=[p[0] for p in config.TEMPLATE_PRESETS])
        preset_combo.grid(row=0, column=3, padx=4)
        preset_combo.bind("<<ComboboxSelected>>", self._on_preset)
        tip(lb_preset, "preset")
        tip(preset_combo, "preset")

        lb_seqstart = ttk.Label(f3, text="序号起始：")
        lb_seqstart.grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.seq_start_var = tk.IntVar(value=config.DEFAULT_SEQ_START)
        w_seqstart = ttk.Spinbox(f3, from_=0, to=99999, textvariable=self.seq_start_var, width=8)
        w_seqstart.grid(row=1, column=1, sticky="w", padx=4)
        tip(lb_seqstart, "seq_start")
        tip(w_seqstart, "seq_start")

        lb_seqwidth = ttk.Label(f3, text="序号位数：")
        lb_seqwidth.grid(row=1, column=2, sticky="e", padx=(12, 4))
        self.seq_width_var = tk.IntVar(value=config.DEFAULT_SEQ_WIDTH)
        w_seqwidth = ttk.Spinbox(f3, from_=1, to=8, textvariable=self.seq_width_var, width=6)
        w_seqwidth.grid(row=1, column=3, sticky="w", padx=4)
        tip(lb_seqwidth, "seq_width")
        tip(w_seqwidth, "seq_width")

        lb_seqstyle = ttk.Label(f3, text="序号样式：")
        lb_seqstyle.grid(row=1, column=4, sticky="e", padx=(12, 4))
        self.seq_style_var = tk.StringVar(value=config.SEQ_STYLES[0][0])
        w_seqstyle = ttk.Combobox(f3, textvariable=self.seq_style_var, state="readonly", width=18,
                                  values=[s[0] for s in config.SEQ_STYLES])
        w_seqstyle.grid(row=1, column=5, sticky="w", padx=4)
        tip(lb_seqstyle, "seq_style")
        tip(w_seqstyle, "seq_style")

        self.replace_orig_var = tk.BooleanVar(value=False)
        w_replace = ttk.Checkbutton(f3, text="在原文件名中替换识别到的姓名（配合 {原名} 使用）",
                                    variable=self.replace_orig_var)
        w_replace.grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=2)
        tip(w_replace, "replace_orig")

        hint = "可用占位符：" + "  ".join("%s=%s" % (k, v) for k, v in config.TEMPLATE_PLACEHOLDERS.items())
        ttk.Label(f3, text=hint, foreground=PALETTE["muted"]).grid(row=3, column=0, columnspan=4, sticky="w", padx=4)

        f3.columnconfigure(1, weight=1)

        # --- 4. 预览表格 ---
        f4 = ttk.LabelFrame(self.root, text="4. 预览（确认无误后再执行）")
        f4.pack(fill="both", expand=True, **pad)

        self.tree = ttk.Treeview(f4, columns=[c[0] for c in COLUMNS], show="headings", height=14)
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w", stretch=(key in ("src", "new")))
        vsb = ttk.Scrollbar(f4, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(f4, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        f4.rowconfigure(0, weight=1)
        f4.columnconfigure(0, weight=1)
        tip(self.tree, "tree")

        self.tree.tag_configure("ok", foreground=PALETTE["ok"])
        self.tree.tag_configure("warn", foreground=PALETTE["warn"])
        self.tree.tag_configure("err", foreground=PALETTE["err"])

        # --- 5. 底部操作 ---
        f5 = ttk.Frame(self.root)
        f5.pack(fill="x", **pad)

        self.btn_preview = ttk.Button(f5, text="刷新预览", command=self.refresh_preview, width=12)
        self.btn_preview.pack(side="left", padx=4)
        self.btn_run = ttk.Button(f5, text="执行重命名", command=self.do_rename, width=12)
        self.btn_run.pack(side="left", padx=4)
        self.btn_undo = ttk.Button(f5, text="撤销上次", command=self.do_undo, width=12)
        self.btn_undo.pack(side="left", padx=4)
        self.btn_export = ttk.Button(f5, text="导出对照表", command=self.export_report, width=12)
        self.btn_export.pack(side="left", padx=4)
        self.btn_log = ttk.Button(f5, text="打开日志", command=self.open_log, width=10)
        self.btn_log.pack(side="left", padx=4)

        tip(self.btn_preview, "preview")
        tip(self.btn_run, "run")
        tip(self.btn_undo, "undo")
        tip(self.btn_export, "export")
        tip(self.btn_log, "log")

        self.progress = ttk.Progressbar(f5, mode="determinate")
        self.progress.pack(side="right", fill="x", expand=True, padx=6)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                  style="Status.TLabel").pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def _on_preset(self, _event=None):
        name = self.preset_var.get()
        for key, val in config.TEMPLATE_PRESETS:
            if key == name:
                self.template_var.set(val)
                break

    def choose_folder(self):
        d = filedialog.askdirectory(title="选择要处理的目标文件夹")
        if d:
            self.folder_var.set(os.path.normpath(d))
            log.info("选择文件夹：%s", d)

    def import_roster(self):
        path = filedialog.askopenfilename(
            title="选择名单文件",
            filetypes=[("表格/文本", "*.xlsx *.xls *.xlsm *.csv *.txt"),
                       ("Excel", "*.xlsx *.xls *.xlsm"),
                       ("文本", "*.txt *.csv"),
                       ("所有文件", "*.*")])
        if not path:
            return
        try:
            entries = load_roster(path)
        except Exception as exc:
            log.exception("导入名单失败")
            messagebox.showerror("导入失败", "无法读取名单：\n%s" % exc)
            return
        if not entries:
            messagebox.showwarning("名单为空", "没有从文件中解析到姓名，请检查文件内容。")
            return
        self.roster = entries
        self.roster_var.set(path)
        self.roster_count_var.set("%d 条" % len(entries))
        log.info("导入名单 %s，共 %d 条", path, len(entries))
        messagebox.showinfo("导入成功", "已导入名单 %d 条。" % len(entries))
        self.refresh_preview()

    def clear_roster(self):
        self.roster = []
        self.roster_var.set("")
        self.roster_count_var.set("0 条")
        log.info("已清空名单")

    def show_roster(self):
        if not self.roster:
            messagebox.showinfo("名单", "尚未导入名单。")
            return
        win = tk.Toplevel(self.root)
        win.title("名单预览（共 %d 条）" % len(self.roster))
        win.geometry("360x520")
        lb = tk.Listbox(win, font=("Microsoft YaHei", 10))
        sb = ttk.Scrollbar(win, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for i, e in enumerate(self.roster, start=1):
            extra = ("  " + str(e.extra)) if e.extra else ""
            lb.insert("end", "%d. %s%s" % (i, e.name, extra))

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------
    def _collect_exts(self) -> Optional[set]:
        if self.all_type_var.get():
            return None
        groups = [g for g, v in self.type_vars.items() if v.get()]
        return scanner.resolve_extensions(groups)

    def _sort_key(self) -> str:
        label = self.sort_var.get()
        for name, key in config.SORT_OPTIONS:
            if name == label:
                return key
        return "name_asc"

    def refresh_preview(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择有效的目标文件夹。")
            return

        # 校验收到的名单
        try:
            entries = load_roster(self.roster_var.get()) if self.roster_var.get().strip() else self.roster
        except Exception:
            entries = self.roster
        self.roster = entries

        exts = self._collect_exts()
        exclude = None
        rp = self.roster_var.get().strip()
        if rp:
            exclude = {rp}
        try:
            self.files = scanner.scan_folder(folder, exts=exts,
                                             recursive=self.recursive_var.get(),
                                             exclude_paths=exclude)
        except Exception as exc:
            log.exception("扫描失败")
            messagebox.showerror("扫描失败", str(exc))
            return

        if not self.files:
            self._clear_tree()
            self.status_var.set("未找到符合条件的文件")
            return

        # 姓名来源（把界面显示名映射成内部值）
        mode = "by_name"
        for disp, val in config.NAME_SOURCES:
            if disp == self.mode_var.get():
                mode = val
                break

        tmpl_text = self.template_var.get().strip() or config.DEFAULT_TEMPLATE
        ok, msg = tpl.validate_template(tmpl_text)
        if not ok:
            messagebox.showerror("模板错误", msg)
            return

        # 从文档内容识别姓名时，先逐个读取正文
        content_names = None
        if mode == "by_content":
            self.status_var.set("正在读取 %d 个文档的正文内容…" % len(self.files))
            self.root.update_idletasks()
            content_names = {}
            for f in self.files:
                try:
                    cands = content_reader.extract_names_from_file(f.path)
                except Exception as exc:
                    log.warning("读取内容失败 %s: %s", f.path, exc)
                    cands = []
                if cands:
                    content_names[f.path] = cands
            log.info("内容识别：%d/%d 个文件提取到姓名候选",
                     len(content_names), len(self.files))

        seq_style = config.DEFAULT_SEQ_STYLE
        for disp, val in config.SEQ_STYLES:
            if disp == self.seq_style_var.get():
                seq_style = val
                break

        self.items, stats = matcher.match(
            self.files, self.roster, mode=mode, sort_key=self._sort_key(),
            seq_start=int(self.seq_start_var.get()),
            fallback_by_order=self.fallback_var.get(),
            content_names=content_names)

        self.rows = rename_engine.build_plan(
            self.items, tmpl_text, int(self.seq_width_var.get()),
            replace_in_orig=self.replace_orig_var.get(),
            seq_style=seq_style)

        self._fill_tree(self.rows)

        s = rename_engine.summarize(self.rows)
        self.status_var.set(
            "文件 %d 个 | 可执行 %d | 未变 %d | 重名 %d | 已存在 %d | 缺姓名 %d | 名单 %d 条（已用 %d）"
            % (len(self.rows), s.get("ok", 0), s.get("same", 0), s.get("conflict", 0),
               s.get("exists", 0), s.get("noname", 0), len(self.roster), stats.roster_used))
        log.info("预览完成：%s", self.status_var.get())

        # 安全提醒：若大量文件其实是"按顺序补齐"的，姓名很可能与文件内容不对应
        filled = getattr(stats, "filled_by_order", 0)
        if filled > 0:
            self.status_var.set(self.status_var.get() + "  ⚠ %d 个为顺序补齐" % filled)
            messagebox.showwarning(
                "注意：可能名不对人",
                "有 %d 个文件没能识别到姓名，程序已按名单顺序依次补齐。\n"
                "这样得到的姓名可能与文件内容不对应。\n\n"
                "如果文件里（文档正文）写了收件人姓名，请把「姓名来源」\n"
                "改为「从文档内容识别」，再点「刷新预览」。" % filled)

    def _clear_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    def _fill_tree(self, rows: List[PlanRow]):
        self._clear_tree()
        for r in rows:
            tag = "ok"
            if r.status in ("conflict", "exists", "invalid", "noname"):
                tag = "err"
            elif r.status == "same":
                tag = "warn"
            pseq = ""
            # 从匹配结果里取解析序号
            if r.index - 1 < len(self.items):
                ps = self.items[r.index - 1].parsed.seq
                pseq = "" if ps is None else str(ps)
            cand = ""
            if r.index - 1 < len(self.items):
                p = self.items[r.index - 1].parsed
                cand = p.content_name or p.name_candidate
            self.tree.insert("", "end", values=(
                r.index, r.src_name, pseq, cand, r.name, r.new_name,
                STATUS_TEXT.get(r.status, r.status), r.note), tags=(tag,))

    # ------------------------------------------------------------------
    # 执行 / 撤销
    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_preview, self.btn_run, self.btn_undo, self.btn_export):
            b.configure(state=state)

    def do_rename(self):
        if self._busy:
            return
        if not self.rows:
            messagebox.showwarning("提示", "请先点击「刷新预览」生成计划。")
            return
        runnable = [r for r in self.rows if r.status == "ok"]
        if not runnable:
            messagebox.showinfo("提示", "没有可执行的重命名（请检查状态列）。")
            return
        if not messagebox.askyesno("确认", "即将重命名 %d 个文件，是否继续？" % len(runnable)):
            return

        self._set_busy(True)
        self.progress.configure(value=0, maximum=max(1, len(runnable) * 2))
        threading.Thread(target=self._run_rename, args=(self.rows,), daemon=True).start()

    def _run_rename(self, rows):
        def cb(done, total, text):
            self._queue.put(("progress", (done, total, text)))
        try:
            res = rename_engine.execute(rows, progress_cb=cb)
            self._queue.put(("rename_done", res))
        except Exception as exc:
            log.exception("执行重命名异常")
            self._queue.put(("error", str(exc)))

    def do_undo(self):
        if self._busy:
            return
        path = rename_engine.latest_undo_file()
        if not path:
            messagebox.showinfo("提示", "没有找到撤销记录。")
            return
        if not messagebox.askyesno("确认", "将撤销最近一次重命名操作：\n%s\n是否继续？" % os.path.basename(path)):
            return
        self._set_busy(True)
        threading.Thread(target=self._run_undo, args=(path,), daemon=True).start()

    def _run_undo(self, path):
        def cb(done, total, text):
            self._queue.put(("progress", (done, total, text)))
        try:
            res = rename_engine.undo(path, progress_cb=cb)
            self._queue.put(("undo_done", res))
        except Exception as exc:
            log.exception("撤销异常")
            self._queue.put(("error", str(exc)))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    done, total, text = payload
                    self.progress.configure(maximum=max(1, total), value=done)
                    self.status_var.set(text)
                elif kind == "rename_done":
                    self._on_rename_done(payload)
                elif kind == "undo_done":
                    self._on_undo_done(payload)
                elif kind == "error":
                    self._set_busy(False)
                    messagebox.showerror("出错", payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _on_rename_done(self, res):
        self._set_busy(False)
        msg = "成功 %d 个，失败 %d 个，跳过 %d 个。" % (res["ok"], res["fail"], res["skipped"])
        if res.get("undo"):
            msg += "\n撤销记录：%s" % os.path.basename(res["undo"])
        if res["errors"]:
            msg += "\n\n失败明细（前 5 条）：\n" + "\n".join(
                "%s: %s" % (e["file"], e["error"]) for e in res["errors"][:5])
        messagebox.showinfo("重命名完成", msg)
        self.status_var.set("重命名完成：" + msg.splitlines()[0])
        self.refresh_preview()

    def _on_undo_done(self, res):
        self._set_busy(False)
        messagebox.showinfo("撤销完成", "成功 %d 个，失败 %d 个。" % (res["ok"], res["fail"]))
        self.refresh_preview()

    # ------------------------------------------------------------------
    # 其它
    # ------------------------------------------------------------------
    def export_report(self):
        if not self.rows:
            messagebox.showwarning("提示", "请先刷新预览。")
            return
        try:
            path = report.export_report(self.rows)
        except Exception as exc:
            log.exception("导出失败")
            messagebox.showerror("导出失败", str(exc))
            return
        messagebox.showinfo("导出成功", "对照表已生成：\n%s" % path)

    def open_log(self):
        d = logger.get_log_dir()
        if os.path.isdir(d):
            os.startfile(d)  # noqa: S606 (Windows)
        else:
            messagebox.showinfo("日志", "日志目录尚未创建。")


def _set_window_icon(win: tk.Misc) -> None:
    """设置窗口/任务栏图标（椎拳崇头像）。"""
    path = getattr(config, "ICON_PATH", "")
    if not path or not os.path.exists(path):
        return
    try:
        win.iconbitmap(default=path)
    except Exception:
        try:
            win.iconbitmap(path)
        except Exception:
            pass


def run():
    logger.setup_logger()
    root = tk.Tk()
    _set_window_icon(root)
    setup_fonts(root)
    apply_dark_theme(root)
    root.withdraw()

    # 启动时先显示"权利声明页"，约 1.9 秒后再显示主界面
    splash = build_splash(root)
    _set_window_icon(splash)

    def _close_splash():
        try:
            splash.destroy()
        except Exception:
            pass
        root.deiconify()
        root.lift()
        try:
            root.focus_force()
        except Exception:
            pass

    root.after(SPLASH_MS, _close_splash)
    MainWindow(root)
    root.mainloop()