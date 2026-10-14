# -*- coding: utf-8 -*-
"""纯函数式 API 层：输入/输出全部为 JSON 友好的 dict。

这是"核心逻辑"与"界面/平台"之间的唯一契约层：
- 桌面版 Tkinter 界面直接调用这些函数；
- 未来的 HarmonyOS(ArkTS) 前端，无论是调用本地服务还是移植核心逻辑，
  都可以对照本文件的输入/输出契约实现或对接，保证行为一致。

约定：
- 所有函数都不 import 任何 GUI 库，可在无界面环境（服务器/移动端）运行；
- 返回值统一为 dict，且一定可 JSON 序列化。
"""
import os
import re
from typing import Dict, List, Optional

from . import config, matcher, rename_engine, scanner
from .logger import get_logger
from .roster import RosterEntry, load_roster
from . import template as tpl
from .serializer import plan_rows_to_view, plan_row_from_dict

log = get_logger("api")


# ---------------------------------------------------------------------------
# 名单
# ---------------------------------------------------------------------------
def parse_roster_text(text: str) -> List[Dict]:
    """把"每行一个姓名"的文本解析成名单列表（供前端直接粘贴）。"""
    entries: List[RosterEntry] = []
    idx = 0
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        line = re.sub(r"^[（(\[【]\s*\d+\s*[)）\]】]\s*", "", line)
        line = re.sub(r"^\d+\s*[.、,，:：)\]]\s*", "", line)
        line = re.sub(r"^[①-⑳]\s*", "", line)
        line = line.strip()
        if not line:
            continue
        idx += 1
        entries.append(RosterEntry(name=line, row_index=idx))
    from .serializer import to_dict
    return to_dict(entries)


def load_roster_entries(payload: Dict) -> List[RosterEntry]:
    """从 payload 解析名单：优先 roster_path，其次 roster_text。"""
    path = (payload.get("roster_path") or "").strip()
    if path:
        return load_roster(path)
    text = payload.get("roster_text") or ""
    if text.strip():
        return [RosterEntry(name=e["name"], row_index=e.get("row_index", i + 1))
                for i, e in enumerate(parse_roster_text(text))]
    return []


# ---------------------------------------------------------------------------
# 一站式流程：扫描 -> 匹配 -> 生成计划
# ---------------------------------------------------------------------------
def pipeline(payload: Dict) -> Dict:
    """执行 扫描→匹配→生成计划，返回完整结果（含前端可展示的行数据）。

    输入 payload 字段：
      folder(str)          目标文件夹
      roster_path(str)     名单文件路径（可选）
      roster_text(str)     名单文本，每行一个姓名（可选）
      mode(str)            by_name | by_order
      sort(str)            name_asc/name_desc/size_asc/size_desc/mtime_asc/mtime_desc
      groups(list[str])    Word/Excel/PDF/图片
      all_types(bool)      不限类型
      recursive(bool)      包含子文件夹
      fallback(bool)       姓名匹配不上时按顺序补齐
      template(str)        命名模板
      seq_start(int)       序号起始
      seq_width(int)       序号位数
      replace_in_orig(bool) 在原名中替换识别到的姓名
      exclude_paths(list[str]) 额外排除的文件
    """
    folder = (payload.get("folder") or "").strip()
    if not folder or not os.path.isdir(folder):
        return {"ok": False, "error": "目标文件夹无效: %s" % folder}

    template = (payload.get("template") or config.DEFAULT_TEMPLATE).strip() \
        or config.DEFAULT_TEMPLATE
    ok, msg = tpl.validate_template(template)
    if not ok:
        return {"ok": False, "error": msg}

    roster = load_roster_entries(payload)

    if payload.get("all_types"):
        exts = None
    else:
        exts = scanner.resolve_extensions(payload.get("groups") or ["Word", "Excel"])

    exclude = set(payload.get("exclude_paths") or [])
    rp = (payload.get("roster_path") or "").strip()
    if rp:
        exclude.add(rp)

    files = scanner.scan_folder(folder, exts=exts,
                                recursive=bool(payload.get("recursive")),
                                exclude_paths=exclude)

    mode = payload.get("mode", "by_name")

    # 从文档正文内容识别姓名时，先逐个读取文件内容提取候选
    content_names = None
    if mode == "by_content":
        from . import content_reader
        content_names = {}
        for f in files:
            try:
                cands = content_reader.extract_names_from_file(f.path)
            except Exception as exc:  # 单个文件失败不影响整体
                log.warning("读取内容失败 %s: %s", f.path, exc)
                cands = []
            if cands:
                content_names[f.path] = cands
        log.info("内容识别：%d/%d 个文件提取到姓名候选", len(content_names), len(files))

    items, stats = matcher.match(
        files, roster,
        mode=mode,
        sort_key=payload.get("sort", "name_asc"),
        seq_start=int(payload.get("seq_start", config.DEFAULT_SEQ_START)),
        fallback_by_order=bool(payload.get("fallback", True)),
        content_names=content_names,
    )

    rows = rename_engine.build_plan(
        items, template,
        seq_width=int(payload.get("seq_width", config.DEFAULT_SEQ_WIDTH)),
        replace_in_orig=bool(payload.get("replace_in_orig")),
        seq_style=payload.get("seq_style", config.DEFAULT_SEQ_STYLE))

    summary = rename_engine.summarize(rows)
    return {
        "ok": True,
        "folder": folder,
        "template": template,
        "mode": mode,
        "roster_count": len(roster),
        "file_count": len(files),
        "content_hit": len(content_names) if content_names is not None else 0,
        "summary": summary,
        "stats": {
            "matched": stats.matched,
            "unmatched": stats.unmatched,
            "roster_used": stats.roster_used,
            "filled_by_order": stats.filled_by_order,
            "duplicate_new_names": stats.duplicate_new_names,
        },
        "rows": plan_rows_to_view(rows),
    }


# ---------------------------------------------------------------------------
# 执行 / 撤销
# ---------------------------------------------------------------------------
def execute_plan(rows: List[Dict], dry_run: bool = False) -> Dict:
    """执行重命名计划（rows 为 pipeline 返回的 rows，或手工构造的同结构数据）。"""
    plan = [plan_row_from_dict(r) for r in (rows or [])]
    res = rename_engine.execute(plan, dry_run=dry_run)
    res["ok_flag"] = res["fail"] == 0
    return res


def undo_last() -> Dict:
    """撤销最近一次重命名。"""
    path = rename_engine.latest_undo_file()
    if not path:
        return {"ok": False, "error": "没有找到撤销记录"}
    res = rename_engine.undo(path)
    res["undo"] = path
    res["ok_flag"] = res["fail"] == 0
    return res