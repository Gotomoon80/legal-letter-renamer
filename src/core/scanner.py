# -*- coding: utf-8 -*-
"""文件夹扫描：收集待处理文件及其属性。"""
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from . import config
from .logger import get_logger

log = get_logger("scanner")


@dataclass
class FileItem:
    """单个待处理文件。"""
    name: str          # 文件名（含扩展名）
    path: str          # 绝对路径
    ext: str           # 扩展名（小写，含点）
    size: int          # 字节
    mtime: float       # 修改时间戳
    ctime: float       # 创建时间戳

    @property
    def mtime_str(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")

    @property
    def size_str(self) -> str:
        n = float(self.size)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % self.size
            n /= 1024
        return "%d B" % self.size


def resolve_extensions(groups: Sequence[str], include_all: bool = False) -> Optional[set]:
    """把界面上的类型分组名转换成扩展名集合；include_all=True 表示不限类型。"""
    if include_all:
        return None
    exts = set()
    for g in groups:
        for e in config.EXT_GROUPS.get(g, []):
            exts.add(e.lower())
    return exts


def scan_folder(folder: str, exts: Optional[set] = None, recursive: bool = False,
                exclude_paths: Optional[set] = None) -> List[FileItem]:
    """扫描文件夹，返回文件列表。

    exts 为 None 表示不限类型；recursive 为 True 时递归子目录；
    exclude_paths 中的文件会被跳过（例如名单文件本身）。
    """
    if not folder or not os.path.isdir(folder):
        raise NotADirectoryError("文件夹不存在: %s" % folder)

    excluded = {os.path.normcase(os.path.abspath(p)) for p in (exclude_paths or set())}
    items: List[FileItem] = []
    if recursive:
        walker = os.walk(folder)
        for root, dirs, files in walker:
            for fn in files:
                _add_item(items, root, fn, exts, excluded)
    else:
        for fn in os.listdir(folder):
            _add_item(items, folder, fn, exts, excluded)

    log.info("扫描目录 %s：命中 %d 个文件（类型=%s，递归=%s，排除=%d）",
             folder, len(items), "全部" if exts is None else sorted(exts),
             recursive, len(excluded))
    return items


def _add_item(items: List[FileItem], folder: str, fn: str, exts: Optional[set],
              excluded: Optional[set] = None) -> None:
    # 跳过 Office 临时文件（~$xxx.docx）与本工具自身的临时文件
    if fn.startswith("~$") or fn.startswith(".__renaming_tmp_"):
        return
    path = os.path.join(folder, fn)
    if not os.path.isfile(path):
        return
    if excluded and os.path.normcase(os.path.abspath(path)) in excluded:
        return
    ext = os.path.splitext(fn)[1].lower()
    if exts is not None and ext not in exts:
        return
    try:
        st = os.stat(path)
    except OSError as exc:
        log.warning("无法读取文件属性 %s: %s", path, exc)
        return
    items.append(FileItem(
        name=fn, path=path, ext=ext,
        size=st.st_size, mtime=st.st_mtime, ctime=st.st_ctime,
    ))


def sort_files(items: List[FileItem], sort_key: str) -> List[FileItem]:
    """按指定方式排序。"""
    if sort_key == "name_asc":
        return sorted(items, key=lambda x: _natural_key(x.name))
    if sort_key == "name_desc":
        return sorted(items, key=lambda x: _natural_key(x.name), reverse=True)
    if sort_key == "size_asc":
        return sorted(items, key=lambda x: (x.size, _natural_key(x.name)))
    if sort_key == "size_desc":
        return sorted(items, key=lambda x: (-x.size, _natural_key(x.name)))
    if sort_key == "mtime_asc":
        return sorted(items, key=lambda x: x.mtime)
    if sort_key == "mtime_desc":
        return sorted(items, key=lambda x: x.mtime, reverse=True)
    return sorted(items, key=lambda x: _natural_key(x.name))


def _natural_key(s: str):
    """自然排序：让 2 排在 10 前面。"""
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]