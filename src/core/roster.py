# -*- coding: utf-8 -*-
"""名单加载：支持 Excel(.xlsx/.xls)、CSV、纯文本(.txt)。"""
import csv
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .logger import get_logger

log = get_logger("roster")

# 疑似表头的关键字（用于自动跳表头、自动选列）
_NAME_HEADER_KEYS = ["姓名", "名字", "客户", "当事人", "名称", "name", "姓 名"]
_SKIP_HEADER_KEYS = ["序号", "编号", "no", "index", "id"]


@dataclass
class RosterEntry:
    """名单中的一行。"""
    name: str                                   # 姓名（主字段）
    row_index: int = 0                          # 原始行号（从 1 开始，含表头则从 2）
    extra: Dict[str, str] = field(default_factory=dict)  # 其它列

    def __str__(self) -> str:
        return self.name


def _looks_like_header(row: List[str]) -> bool:
    joined = "".join(str(c) for c in row if c is not None).lower()
    return any(k.lower() in joined for k in _NAME_HEADER_KEYS)


def _pick_name_column(rows: List[List[str]], header: Optional[List[str]]) -> int:
    """自动挑选最像"姓名列"的列索引。"""
    if header:
        for i, h in enumerate(header):
            h = (h or "").lower()
            if any(k.lower() in h for k in _NAME_HEADER_KEYS):
                return i
    # 没有表头：选非空单元格最多、且"看起来像姓名"比例最高的列
    if not rows:
        return 0
    ncol = max(len(r) for r in rows)
    best_idx, best_score = 0, -1.0
    for c in range(ncol):
        vals = [(r[c] if c < len(r) else "") for r in rows]
        non_empty = [v for v in vals if v and v.strip()]
        if not non_empty:
            continue
        # 像姓名的：长度 2~6 且不含太多数字
        good = sum(1 for v in non_empty
                   if 2 <= len(v.strip()) <= 6 and not any(ch.isdigit() for ch in v))
        score = good / len(non_empty)
        if score > best_score:
            best_score, best_idx = score, c
    return best_idx


def _is_skip_header_cell(v: str) -> bool:
    v = (v or "").strip().lower()
    return any(k.lower() == v or (k.lower() in v and len(v) <= 6)
               for k in _SKIP_HEADER_KEYS)


def load_roster(path: str, name_column: Optional[int] = None) -> List[RosterEntry]:
    """加载名单文件，返回 RosterEntry 列表。

    name_column: 指定姓名列索引（0 起），None 则自动识别。
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError("名单文件不存在: %s" % path)

    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        rows = _read_xlsx(path)
    elif ext == ".xls":
        rows = _read_xls(path)
    elif ext == ".csv":
        rows = _read_csv(path)
    elif ext in (".txt", ".text"):
        return _read_txt(path)
    else:
        # 兜底：按文本读
        log.warning("未知名单格式 %s，按文本解析", ext)
        return _read_txt(path)

    return _rows_to_entries(rows, name_column)


def _read_xlsx(path: str) -> List[List[str]]:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows: List[List[str]] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(["" if c is None else str(c).strip() for c in row])
        return rows
    finally:
        wb.close()


def _read_xls(path: str) -> List[List[str]]:
    import xlrd
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    rows: List[List[str]] = []
    for r in range(sheet.nrows):
        rows.append([str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)])
    return rows


def _read_csv(path: str) -> List[List[str]]:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return [[("" if c is None else str(c).strip()) for c in row]
                        for row in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return [[c.strip() for c in row] for row in csv.reader(f)]


def _read_txt(path: str) -> List[RosterEntry]:
    content = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    import re
    entries: List[RosterEntry] = []
    idx = 0
    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        # 去掉行首序号：1. / 1、/ ① / 第1号
        line = re.sub(r"^[（(\[【]\s*\d+\s*[)）\]】]\s*", "", line)
        line = re.sub(r"^\d+\s*[.、,，:：)\]]\s*", "", line)
        line = re.sub(r"^[①-⑳]\s*", "", line)
        line = re.sub(r"^第\s*\d+\s*[号份个]?\s*[.、,，:：]?\s*", "", line)
        line = line.strip()
        if not line:
            continue
        idx += 1
        entries.append(RosterEntry(name=line, row_index=idx))
    log.info("从 txt 加载名单 %d 条", len(entries))
    return entries


def _rows_to_entries(rows: List[List[str]], name_column: Optional[int]) -> List[RosterEntry]:
    if not rows:
        return []

    header = None
    data = rows
    if _looks_like_header(rows[0]):
        header = rows[0]
        data = rows[1:]

    col = name_column if name_column is not None else _pick_name_column(data, header)
    headers = header or []
    log.info("名单解析：识别姓名列=%s（表头=%s），数据行=%d", col, headers, len(data))

    entries: List[RosterEntry] = []
    for i, row in enumerate(data):
        val = row[col].strip() if col < len(row) else ""
        if not val:
            continue
        # 跳过疑似表头残留
        if _looks_like_header([val]):
            continue
        extra = {}
        for j, v in enumerate(row):
            if j == col:
                continue
            key = headers[j] if j < len(headers) and headers[j] else "列%d" % (j + 1)
            if v:
                extra[key] = v
        entries.append(RosterEntry(name=val, row_index=i + (2 if header else 1), extra=extra))
    log.info("名单加载完成，共 %d 条", len(entries))
    return entries