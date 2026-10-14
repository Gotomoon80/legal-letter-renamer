# -*- coding: utf-8 -*-
"""序列化工具：核心数据结构 <-> dict <-> JSON。

设计目标（为跨平台/跨语言移植预留）：
- 核心数据全部可无损转成 JSON；
- 未来无论走"HarmonyOS 前端 + 核心服务"还是"核心逻辑移植 TypeScript"，
  都能用同一份 JSON 契约对接。
"""
import json
from dataclasses import fields, is_dataclass
from typing import Any, Dict, List

from .matcher import MatchItem
from .name_parser import ParsedName
from .rename_engine import PlanRow, STATUS_TEXT
from .roster import RosterEntry
from .scanner import FileItem


# ---------------------------------------------------------------------------
# 通用：对象 -> dict
# ---------------------------------------------------------------------------
def to_dict(obj: Any) -> Any:
    """把 dataclass / list / dict 递归转成纯 dict/list。"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def to_json(obj: Any, indent: int = 2) -> str:
    """转成 JSON 字符串（中文不转义）。"""
    return json.dumps(to_dict(obj), ensure_ascii=False, indent=indent)


def from_json(text: str) -> Any:
    return json.loads(text)


# ---------------------------------------------------------------------------
# dict -> 对象
# ---------------------------------------------------------------------------
def _flat(cls, d: Dict[str, Any]):
    """扁平 dataclass 的通用还原。"""
    kwargs = {}
    for f in fields(cls):
        if f.name in d and d[f.name] is not None:
            kwargs[f.name] = d[f.name]
    return cls(**kwargs)


def parsed_name_from_dict(d: Dict[str, Any]) -> ParsedName:
    return _flat(ParsedName, d)


def file_item_from_dict(d: Dict[str, Any]) -> FileItem:
    return _flat(FileItem, d)


def roster_entry_from_dict(d: Dict[str, Any]) -> RosterEntry:
    return _flat(RosterEntry, d)


def match_item_from_dict(d: Dict[str, Any]) -> MatchItem:
    return MatchItem(
        file=file_item_from_dict(d.get("file", {})),
        parsed=parsed_name_from_dict(d.get("parsed", {})),
        seq=d.get("seq", 0),
        name=d.get("name", ""),
        roster_index=d.get("roster_index", -1),
        status=d.get("status", "ok"),
        note=d.get("note", ""),
        score=d.get("score", 0.0),
    )


def plan_row_from_dict(d: Dict[str, Any]) -> PlanRow:
    return _flat(PlanRow, d)


# ---------------------------------------------------------------------------
# 面向界面的便捷转换
# ---------------------------------------------------------------------------
def plan_row_to_view(row: PlanRow) -> Dict[str, Any]:
    """把一行计划转成适合前端直接展示的结构。"""
    return {
        "index": row.index,
        "src": row.src,
        "src_name": row.src_name,
        "dst": row.dst,
        "new_name": row.new_name,
        "seq": row.seq,
        "name": row.name,
        "status": row.status,
        "status_text": STATUS_TEXT.get(row.status, row.status),
        "note": row.note,
    }


def plan_rows_to_view(rows: List[PlanRow]) -> List[Dict[str, Any]]:
    return [plan_row_to_view(r) for r in rows]