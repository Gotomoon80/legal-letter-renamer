# -*- coding: utf-8 -*-
"""匹配引擎：把文件夹中的文件与名单里的姓名"对号入座"。

两种模式：
- by_name ：根据文件名中解析出的姓名候选与名单姓名智能匹配（模糊匹配 + 一对一贪心）；
- by_order：按排序后的文件顺序与名单顺序一一对应。
"""
import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import config
from .name_parser import ParsedName, parse_filename
from .roster import RosterEntry
from .scanner import FileItem, sort_files
from .logger import get_logger

log = get_logger("matcher")

STATUS_OK = "ok"              # 已匹配
STATUS_UNMATCHED = "unmatched"  # 未匹配到姓名
STATUS_EMPTY_NAME = "empty"   # 名单为空


@dataclass
class MatchItem:
    """单个文件的匹配结果。"""
    file: FileItem
    parsed: ParsedName
    seq: int = 0                 # 最终使用的序号
    name: str = ""               # 匹配到的姓名
    roster_index: int = -1       # 对应名单中的行索引（-1 表示无）
    status: str = STATUS_OK
    note: str = ""
    score: float = 0.0


@dataclass
class MatchStats:
    total: int = 0
    matched: int = 0
    unmatched: int = 0
    roster_total: int = 0
    roster_used: int = 0
    filled_by_order: int = 0   # 未识别到姓名、被"按顺序补齐"的文件数（可能名不对人）
    duplicate_new_names: List[str] = field(default_factory=list)


def name_similarity(candidate: str, name: str) -> float:
    """计算姓名候选与名单姓名的相似度（0~1）。"""
    c = (candidate or "").strip()
    n = (name or "").strip()
    if not c or not n:
        return 0.0
    if c == n:
        return 1.0
    # 包含关系：如"张三合同" vs "张三"
    if n in c or c in n:
        shorter, longer = (c, n) if len(c) <= len(n) else (n, c)
        return 0.80 + 0.20 * (len(shorter) / len(longer))
    return difflib.SequenceMatcher(None, c, n).ratio()


def _candidates_of(parsed: ParsedName, extra: Optional[List[str]] = None) -> List[str]:
    """汇总一个文件可用于匹配名单的所有姓名候选（按优先级）。"""
    cands: List[str] = []
    if parsed.content_name:
        cands.append(parsed.content_name)
    if parsed.name_candidate:
        cands.append(parsed.name_candidate)
    cands.extend(t for t in parsed.tokens if t)
    if extra:
        cands.extend(e for e in extra if e)
    # 去重保序
    seen = set()
    out = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _best_name_for(parsed: ParsedName, roster: List[RosterEntry],
                   extra: Optional[List[str]] = None) -> Tuple[Optional[int], float]:
    """为单个文件在所有名单里找最匹配的那条，返回 (名单索引, 分数)。"""
    candidates = _candidates_of(parsed, extra)
    best_idx, best_score = None, 0.0
    for idx, entry in enumerate(roster):
        for c in candidates:
            s = name_similarity(c, entry.name)
            if s > best_score:
                best_score, best_idx = s, idx
    return best_idx, best_score


def match(files: List[FileItem],
          roster: List[RosterEntry],
          mode: str = "by_order",
          sort_key: str = "name_asc",
          similarity: float = config.DEFAULT_SIMILARITY,
          seq_start: int = config.DEFAULT_SEQ_START,
          fallback_by_order: bool = True,
          noise_words: Optional[List[str]] = None,
          content_names: Optional[Dict[str, List[str]]] = None) -> Tuple[List[MatchItem], MatchStats]:
    """执行匹配，返回 (匹配结果列表, 统计)。

    mode:
      by_name    - 从文件名识别姓名
      by_content - 从文档正文内容识别姓名（content_names 提供候选）
      by_order   - 按顺序对应名单
    content_names: {文件绝对路径: [姓名候选...]}，仅 by_content 模式需要。
    """
    ordered = sort_files(files, sort_key)
    items: List[MatchItem] = []
    stats = MatchStats(total=len(ordered), roster_total=len(roster))

    content_names = content_names or {}

    def _parsed_of(f: FileItem) -> ParsedName:
        cands = content_names.get(f.path) or []
        return parse_filename(f.name, noise_words,
                              content_name=(cands[0] if cands else ""))

    if not roster:
        for i, f in enumerate(ordered):
            items.append(MatchItem(file=f, parsed=_parsed_of(f),
                                   seq=seq_start + i, name="",
                                   status=STATUS_EMPTY_NAME, note="名单为空，未匹配姓名"))
        stats.unmatched = len(items)
        log.warning("名单为空，所有文件均未匹配姓名")
        _order_and_number(items, mode, seq_start)
        return items, stats

    if mode == "by_order":
        for i, f in enumerate(ordered):
            parsed = _parsed_of(f)
            if i < len(roster):
                items.append(MatchItem(file=f, parsed=parsed, name=roster[i].name,
                                       roster_index=i, status=STATUS_OK, score=1.0))
            else:
                items.append(MatchItem(file=f, parsed=parsed, name="",
                                       status=STATUS_UNMATCHED,
                                       note="名单数量不足，缺少对应姓名"))
        stats.matched = min(len(ordered), len(roster))
        stats.unmatched = len(ordered) - stats.matched
        stats.roster_used = stats.matched
        log.info("顺序匹配完成：文件 %d / 名单 %d", len(ordered), len(roster))
        _order_and_number(items, mode, seq_start)
        _fill_duplicates(items, stats)
        return items, stats

    # --- 智能匹配（按文件名 或 按文档内容）---
    parsed_list = [_parsed_of(f) for f in ordered]
    # 把所有"文件-名单"可能对算出来，按分数降序贪心一对一分配
    all_pairs: List[Tuple[float, int, int]] = []
    for fi, f in enumerate(ordered):
        if mode == "by_content":
            # 内容模式：以文档正文识别到的姓名为准；
            # 正文里没有姓名时，才退回用文件名里的候选，避免文件名"抢走"别人的姓名。
            cands = list(content_names.get(f.path) or [])
            if not cands:
                cands = _candidates_of(parsed_list[fi])
        else:
            cands = _candidates_of(parsed_list[fi], content_names.get(f.path))
        if not cands:
            continue
        for ri, entry in enumerate(roster):
            best = max((name_similarity(c, entry.name) for c in cands), default=0.0)
            if best >= similarity:
                all_pairs.append((best, fi, ri))
    all_pairs.sort(key=lambda x: (-x[0], x[1], x[2]))

    file_to_roster: Dict[int, Tuple[int, float]] = {}
    used_roster = set()
    for score, fi, ri in all_pairs:
        if fi in file_to_roster or ri in used_roster:
            continue
        file_to_roster[fi] = (ri, score)
        used_roster.add(ri)

    # 生成结果
    for i, f in enumerate(ordered):
        parsed = parsed_list[i]
        if i in file_to_roster:
            ri, score = file_to_roster[i]
            note = ""
            if score < 1.0:
                note = "模糊匹配（相似度 %.0f%%）" % (score * 100)
            items.append(MatchItem(file=f, parsed=parsed, name=roster[ri].name,
                                   roster_index=ri, status=STATUS_OK,
                                   note=note, score=score))
        else:
            if parsed.has_placeholder:
                note = "含姓名占位符，未能按姓名匹配"
            elif mode == "by_content":
                note = "文档内容未识别出名单中的姓名"
            else:
                note = "名单中未找到相似姓名"
            items.append(MatchItem(file=f, parsed=parsed, name="",
                                   status=STATUS_UNMATCHED, note=note))

    stats.matched = len(file_to_roster)
    stats.unmatched = len(ordered) - stats.matched
    stats.roster_used = len(used_roster)

    # 姓名匹配不上时，用剩余名单按顺序补齐（可选）
    if fallback_by_order:
        remaining = [i for i in range(len(roster)) if i not in used_roster]
        it = iter(remaining)
        filled = 0
        for item in items:
            if item.status == STATUS_UNMATCHED and item.name == "":
                try:
                    ri = next(it)
                except StopIteration:
                    break
                item.name = roster[ri].name
                item.roster_index = ri
                item.status = STATUS_OK
                item.score = 0.0
                item.note = "顺序补齐（姓名未匹配）"
                filled += 1
        if filled:
            stats.matched += filled
            stats.unmatched -= filled
            stats.roster_used += filled
            stats.filled_by_order = filled
            log.info("按顺序补齐 %d 个文件", filled)

    log.info("姓名匹配完成：已匹配 %d / 未匹配 %d / 名单使用 %d",
             stats.matched, stats.unmatched, stats.roster_used)
    _order_and_number(items, mode, seq_start)
    _fill_duplicates(items, stats)
    return items, stats


def _order_and_number(items: List[MatchItem], mode: str, seq_start: int) -> None:
    """统一排序并分配序号。

    - by_name 模式：已匹配的按"名单顺序"排前面，未匹配的排在后面，
      这样 {序号} 与名单序号一致（0001 对应名单第 1 人）；
    - by_order 模式：保持文件原有排序。
    """
    if mode in ("by_name", "by_content"):
        matched = [it for it in items if it.status == STATUS_OK and it.roster_index >= 0]
        others = [it for it in items if not (it.status == STATUS_OK and it.roster_index >= 0)]
        matched.sort(key=lambda x: x.roster_index)
        ordered = matched + others
    else:
        ordered = list(items)
    for i, it in enumerate(ordered):
        it.seq = seq_start + i
    items[:] = ordered


def _fill_duplicates(items: List[MatchItem], stats: MatchStats) -> None:
    """统计目标名可能重复的情况（真正重复在渲染新名后再判定）。"""
    names = [it.name for it in items if it.name]
    seen = set()
    dups = set()
    for n in names:
        if n in seen:
            dups.add(n)
        seen.add(n)
    stats.duplicate_new_names = sorted(dups)
    if dups:
        log.warning("名单中存在重复姓名，可能导致目标文件重名: %s", sorted(dups))