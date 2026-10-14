# -*- coding: utf-8 -*-
"""文档内容读取与"称谓姓名"提取。

设计要点：
- **只用 Python 标准库**（zipfile + xml.etree）直接解析 Office 文档，
  不引入 python-docx / lxml 等含 C 扩展的依赖，保证：
    1) 打包出的 exe 体积小、绿色免安装；
    2) 核心逻辑保持纯 Python，便于将来移植到鸿蒙（ArkTS）。
- .docx / .xlsx 本质都是 zip 包：解压后读取里面的 XML，收集文本节点即可。
- .doc / .xls 为旧二进制格式，标准库难以可靠解析，做"尽力而为"并注明。
"""
import os
import re
import zipfile
from typing import List, Optional

from .logger import get_logger

log = get_logger("content")

# OOXML 命名空间
_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# 称谓提取模式（按优先级排列），均返回姓名候选
# 说明：中文姓名一般 2~6 字，允许中间带"·"（少数民族姓名）
_NAME = r"[A-Za-z\u4e00-\u9fa5·]{1,8}"

NAME_PATTERNS = [
    # 尊敬的张三 / 敬爱的张三
    r"(?:尊敬的|敬爱的|亲爱的|致)\s*(" + _NAME + r")(?:先生|女士|同学|同志|律师|经理|总监)?",
    # 张三先生 / 李四女士（无称谓前缀，靠后缀识别）
    r"(" + _NAME + r")(?:先生|女士|同学|同志)",
    # 收件人：张三
    r"收件人[:：]\s*(" + _NAME + r")",
]

# 明显不是姓名的常见词（避免把"客户/先生"等当姓名）
_STOP_WORDS = {
    "先生", "女士", "同学", "同志", "律师", "经理", "总监", "客户",
    "尊敬的", "敬爱的", "亲爱的", "您好", "你好", "收件人",
}


# ---------------------------------------------------------------------------
# 文本提取
# ---------------------------------------------------------------------------
def extract_docx_text(path: str) -> str:
    """从 .docx 提取正文文本（含页眉页脚）。"""
    parts: List[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            targets = [n for n in ("word/document.xml",) if n in names]
            # 页眉页脚里也可能写姓名
            targets += [n for n in names
                        if n.startswith("word/header") or n.startswith("word/footer")]
            for n in targets:
                try:
                    xml = zf.read(n)
                except KeyError:
                    continue
                parts.append(_xml_text(xml, _NS_W + "t"))
    except (zipfile.BadZipFile, OSError) as exc:
        log.warning("读取 docx 失败 %s: %s", path, exc)
    return "\n".join(p for p in parts if p)


def extract_xlsx_text(path: str) -> str:
    """从 .xlsx 提取单元格文本（主要取共享字符串表）。"""
    parts: List[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "xl/sharedStrings.xml" in names:
                parts.append(_xml_text(zf.read("xl/sharedStrings.xml"),
                                       "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
            for n in names:
                if n.startswith("xl/worksheets/") and n.endswith(".xml"):
                    parts.append(_xml_text(zf.read(n),
                                           "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
    except (zipfile.BadZipFile, OSError) as exc:
        log.warning("读取 xlsx 失败 %s: %s", path, exc)
    return "\n".join(p for p in parts if p)


def extract_plain_text(path: str) -> str:
    """读取纯文本文件（自动尝试常见编码）。"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError:
            return ""
    return ""


def extract_doc_text(path: str) -> str:
    """旧版 .doc（OLE 复合文档）尽力提取：在字节流中查找 GBK/UTF-16 文本片段。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return ""
    # 提取连续的 GBK 中文/ASCII 片段
    chunks = re.findall(rb"[\x20-\x7e\xa1-\xfe]{4,}", raw)
    out = []
    for c in chunks:
        for enc in ("gbk", "utf-8"):
            try:
                out.append(c.decode(enc))
                break
            except UnicodeDecodeError:
                continue
    return "\n".join(out)


def extract_text(path: str) -> str:
    """按扩展名分派文本提取。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return extract_docx_text(path)
    if ext == ".doc":
        return extract_doc_text(path)
    if ext in (".xlsx", ".xlsm"):
        return extract_xlsx_text(path)
    if ext == ".xls":
        return extract_doc_text(path)  # 二进制，尽力而为
    if ext in (".txt", ".csv", ".rtf"):
        return extract_plain_text(path)
    return ""


def _xml_text(xml_bytes: bytes, tag: str) -> str:
    """从 XML 字节流中收集指定标签的文本。"""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        log.warning("XML 解析失败: %s", exc)
        return ""
    return "".join(node.text or "" for node in root.iter(tag))


# ---------------------------------------------------------------------------
# 姓名提取
# ---------------------------------------------------------------------------
def extract_names(text: str) -> List[str]:
    """从文本中提取姓名候选（按出现顺序、去重）。"""
    found: List[str] = []
    seen = set()
    for pat in NAME_PATTERNS:
        for m in re.finditer(pat, text or ""):
            name = (m.group(1) or "").strip()
            name = name.strip("·").strip()
            if not name or name in _STOP_WORDS:
                continue
            if len(name) < 2 or len(name) > 8:
                continue
            if name not in seen:
                seen.add(name)
                found.append(name)
    return found


def extract_names_from_file(path: str) -> List[str]:
    """读取文件内容并提取姓名候选。"""
    text = extract_text(path)
    return extract_names(text)