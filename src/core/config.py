# -*- coding: utf-8 -*-
"""项目全局配置与常量。

包含默认噪声词、文件类型分组、默认命名模板等。
本项目的命名完全由"名单 + 模板"驱动。
"""
import os
import sys

# ---------------------------------------------------------------------------
# 应用信息
# ---------------------------------------------------------------------------
APP_NAME = "批量文档重命名助手"
APP_NAME_EN = "BatchDocRenamer"
APP_VERSION = "1.1.1"

# 数据根目录：
# - 源码运行：项目根目录（src/core/config.py -> 上溯两级）
# - 打包 exe：exe 所在目录（保证日志、对照表与 exe 放在一起，绿色免安装）
# 若该目录不可写（例如放在只读盘/Program Files），自动回退到用户目录，
# 保证"双击即用、无需安装"在任何位置都能工作。
def _is_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
        return True
    except Exception:
        return False


if getattr(sys, "frozen", False):
    _preferred = os.path.dirname(sys.executable)
else:
    _preferred = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if _is_writable(_preferred):
    BASE_DIR = _preferred
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), APP_NAME_EN)

LOG_DIR = os.path.join(BASE_DIR, "logs")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")


def resource_path(*parts: str) -> str:
    """定位随程序分发的只读资源（打包后位于 exe 解压目录 _MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


ICON_PATH = resource_path("assets", "icon.ico")

# ---------------------------------------------------------------------------
# 文件类型分组（用户可多选）
# ---------------------------------------------------------------------------
EXT_GROUPS = {
    "Word": [".doc", ".docx", ".docm", ".dot", ".dotx", ".rtf"],
    "Excel": [".xls", ".xlsx", ".xlsm", ".xlsb", ".csv"],
    "PDF": [".pdf"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"],
}

# ---------------------------------------------------------------------------
# 文件名解析默认配置
# ---------------------------------------------------------------------------
# 默认噪声词/模板词：从文件名中剥离后剩下的通常就是"姓名候选"
DEFAULT_NOISE_WORDS = [
    "律师函", "催款函", "催收函", "账单", "对账单", "通知函", "通知",
    "致", "函", "先生", "女士", "同学", "客户", "尊敬的",
]

# 姓名占位符：文件中出现这些字样时，视为"待填入姓名"
NAME_PLACEHOLDERS = ["xxx", "XXX", "xx", "XX", "某某", "某", "{姓名}", "{name}", "＿＿"]

# 常见序号样式说明（仅在界面上做提示用）
SEQ_STYLE_HINT = "支持：① ② ③、1. 2. 3.、(1)、【1】、第1号、01/001 等"

# ---------------------------------------------------------------------------
# 命名模板
# ---------------------------------------------------------------------------
# 可用占位符：{序号} {姓名} {原名} {主体} {扩展名}
TEMPLATE_PLACEHOLDERS = {
    "{序号}": "序号（按设置补零，如 0001）",
    "{姓名}": "匹配到的名单姓名",
    "{原名}": "原文件名（不含扩展名）",
    "{主体}": "原文件名去掉序号后的主体部分",
    "{扩展名}": "原扩展名（含点，如 .docx）",
}

DEFAULT_TEMPLATE = "{序号}_{姓名}"

# 预设模板
TEMPLATE_PRESETS = [
    ("序号_姓名", "{序号}_{姓名}"),
    ("序号+姓名", "{序号}{姓名}"),
    ("序号+姓名+律师函", "{序号}{姓名}律师函"),
    ("保留原名+姓名", "{原名}_{姓名}"),
    ("姓名_律师函", "{姓名}_律师函"),
    ("序号_姓名_账单", "{序号}_{姓名}_账单"),
    ("《01致姓名缴费通知书》", "《{序号}致{姓名}的缴费通知书》"),
    ("《01致姓名律师函》", "《{序号}致{姓名}律师函》"),
]

# 序号默认设置
DEFAULT_SEQ_START = 1
# 默认 2 位：1~99 个文件产出 01、02…99，整齐一致
# （圈号样式仅 50 个标准字形，超出会回退为数字，故不作为默认）
DEFAULT_SEQ_WIDTH = 2

# 序号样式：(显示名, 值)
SEQ_STYLES = [
    ("阿拉伯数字（0001）", "arabic"),
    ("圈号（①②③）", "circled"),
    ("中文（一二三）", "chinese"),
]
DEFAULT_SEQ_STYLE = "arabic"

# 姓名识别来源：(显示名, 值)
NAME_SOURCES = [
    ("从文件名识别", "by_name"),
    ("从文档内容识别", "by_content"),
    ("按文件夹顺序对应名单", "by_order"),
]
DEFAULT_NAME_SOURCE = "by_content"

# 匹配相似度阈值（0~1）
DEFAULT_SIMILARITY = 0.6

# 排序方式
SORT_OPTIONS = [
    ("文件名 升序", "name_asc"),
    ("文件名 降序", "name_desc"),
    ("大小 升序", "size_asc"),
    ("大小 降序", "size_desc"),
    ("修改时间 升序", "mtime_asc"),
    ("修改时间 降序", "mtime_desc"),
]