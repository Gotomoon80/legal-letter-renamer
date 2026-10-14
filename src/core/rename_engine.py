# -*- coding: utf-8 -*-
"""重命名引擎：生成计划、冲突检测、执行、撤销。

安全策略：
1. 先生成"重命名计划"供用户预览，绝不直接改动文件；
2. 执行采用"两段式"改名（原名 -> 临时名 -> 目标名），避免互相覆盖；
3. 每次执行都写入一份撤销记录（JSON），支持一键回滚。
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from . import config, template as tpl
from .logger import get_logger
from .matcher import MatchItem, STATUS_OK

log = get_logger("renamer")

# 计划行状态
R_OK = "ok"              # 可执行
R_SAME = "same"          # 新名与原名相同，跳过
R_CONFLICT = "conflict"  # 目标名重复
R_EXISTS = "exists"      # 目标文件已存在
R_INVALID = "invalid"    # 非法 / 保留名
R_NONAME = "noname"      # 模板需要姓名但未匹配到

STATUS_TEXT = {
    R_OK: "可执行",
    R_SAME: "名称未变",
    R_CONFLICT: "目标重名",
    R_EXISTS: "目标已存在",
    R_INVALID: "非法名称",
    R_NONAME: "缺少姓名",
}


@dataclass
class PlanRow:
    """重命名计划中的一行。"""
    index: int          # 序号（界面显示用，从 1 起）
    src: str            # 原文件绝对路径
    src_name: str       # 原文件名
    dst: str            # 目标绝对路径
    new_name: str       # 目标文件名
    seq: int            # 使用的序号
    name: str           # 匹配到的姓名
    status: str = R_OK
    note: str = ""


def build_plan(items: List[MatchItem],
               template: str,
               seq_width: int = config.DEFAULT_SEQ_WIDTH,
               replace_in_orig: bool = False,
               seq_style: str = config.DEFAULT_SEQ_STYLE) -> List[PlanRow]:
    """根据匹配结果与模板，生成重命名计划（含冲突检测）。"""
    rows: List[PlanRow] = []
    for i, item in enumerate(items):
        parsed = item.parsed
        seq_text = tpl.format_seq(item.seq, seq_width, seq_style)

        orig_value = parsed.stem
        body_value = parsed.body
        if replace_in_orig and item.name and parsed.name_candidate:
            orig_value = parsed.stem.replace(parsed.name_candidate, item.name)
            body_value = parsed.body.replace(parsed.name_candidate, item.name)

        ctx = {
            "序号": seq_text,
            "姓名": item.name or "",
            "原名": orig_value,
            "主体": body_value,
            "扩展名": parsed.ext,
        }
        rendered = tpl.render(template, ctx)
        if "{扩展名}" in template:
            new_name = rendered
        else:
            new_name = rendered + parsed.ext

        folder = os.path.dirname(item.file.path)
        dst = os.path.join(folder, new_name)

        status = R_OK
        note = ""
        if not new_name or new_name == parsed.ext:
            status = R_INVALID
            note = "生成的名称为空"
        elif tpl.is_reserved(new_name):
            status = R_INVALID
            note = "Windows 保留名称"
        elif "{姓名}" in template and not item.name:
            status = R_NONAME
            note = "模板含 {姓名} 但未匹配到姓名"
        elif new_name == item.file.name:
            status = R_SAME
            note = "名称无变化"
        elif os.path.exists(dst) and os.path.normcase(dst) != os.path.normcase(item.file.path):
            src_set = {os.path.normcase(x.file.path) for x in items}
            if os.path.normcase(dst) not in src_set:
                status = R_EXISTS
                note = "目标文件已存在"

        rows.append(PlanRow(index=i + 1, src=item.file.path, src_name=item.file.name,
                            dst=dst, new_name=new_name, seq=item.seq, name=item.name,
                            status=status, note=note))

    _mark_conflicts(rows)
    return rows


def _mark_conflicts(rows: List[PlanRow]) -> None:
    """标记目标名重复的行。"""
    seen: Dict[str, List[PlanRow]] = {}
    for r in rows:
        if r.status in (R_OK,):
            key = os.path.normcase(r.new_name)
            seen.setdefault(key, []).append(r)
    for key, group in seen.items():
        if len(group) > 1:
            names = "、".join("第%d行" % r.index for r in group)
            for r in group:
                r.status = R_CONFLICT
                r.note = "目标名称重复：%s" % names


def summarize(rows: List[PlanRow]) -> Dict[str, int]:
    """统计各状态数量。"""
    result = {k: 0 for k in STATUS_TEXT}
    for r in rows:
        result[r.status] = result.get(r.status, 0) + 1
    return result


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def _temp_name(folder: str, ext: str, n: int) -> str:
    return os.path.join(folder, ".__renaming_tmp_%d_%d%s" % (int(time.time() * 1000) % 100000, n, ext))


def execute(rows: List[PlanRow],
            progress_cb: Optional[Callable[[int, int, str], None]] = None,
            dry_run: bool = False) -> Dict:
    """执行重命名。

    返回 {'ok':int, 'fail':int, 'skipped':int, 'errors':[...], 'undo':path}
    """
    todo = [r for r in rows if r.status == R_OK]
    skipped = len(rows) - len(todo)
    result = {"ok": 0, "fail": 0, "skipped": skipped, "errors": [], "undo": "", "total": len(todo)}

    if dry_run:
        result["ok"] = len(todo)
        log.info("[预演] 计划重命名 %d 个文件，跳过 %d 个", len(todo), skipped)
        return result

    if not todo:
        log.info("没有需要执行的重命名")
        return result

    operations: List[Dict[str, str]] = []   # 成功的 src->dst
    temp_map: List[Tuple[PlanRow, str]] = []

    # 阶段一：原名 -> 临时名
    total = len(todo)
    for i, r in enumerate(todo):
        if progress_cb:
            progress_cb(i, total, "正在预备：%s" % r.src_name)
        folder = os.path.dirname(r.src)
        ext = os.path.splitext(r.src)[1]
        tmp = _temp_name(folder, ext, i)
        try:
            os.rename(r.src, tmp)
            temp_map.append((r, tmp))
        except OSError as exc:
            log.error("预备改名失败 %s: %s", r.src, exc)
            result["fail"] += 1
            result["errors"].append({"file": r.src, "error": str(exc)})

    # 阶段二：临时名 -> 目标名
    for i, (r, tmp) in enumerate(temp_map):
        if progress_cb:
            progress_cb(len(todo) + i, total * 2, "正在改名：%s -> %s" % (r.src_name, r.new_name))
        try:
            if os.path.exists(r.dst):
                raise OSError("目标文件已存在：%s" % r.new_name)
            os.rename(tmp, r.dst)
            result["ok"] += 1
            operations.append({"src": r.src, "dst": r.dst, "name": r.name})
            log.info("重命名成功：%s -> %s", r.src_name, r.new_name)
        except OSError as exc:
            log.error("改名失败 %s -> %s : %s", tmp, r.dst, exc)
            result["fail"] += 1
            result["errors"].append({"file": r.src, "error": str(exc)})
            # 尽力还原
            try:
                os.rename(tmp, r.src)
            except OSError:
                pass

    # 写入撤销记录
    if operations:
        result["undo"] = _save_undo(operations)
        log.info("本次成功 %d 个，失败 %d 个，撤销记录：%s",
                 result["ok"], result["fail"], result["undo"])
    if progress_cb:
        progress_cb(total * 2, total * 2, "完成")
    return result


def _save_undo(operations: List[Dict[str, str]]) -> str:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    path = os.path.join(config.LOG_DIR,
                        "undo_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    payload = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "operations": operations}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# 撤销
# ---------------------------------------------------------------------------
def latest_undo_file() -> Optional[str]:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    files = [os.path.join(config.LOG_DIR, f) for f in os.listdir(config.LOG_DIR)
             if f.startswith("undo_") and f.endswith(".json")]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def undo(undo_path: str,
         progress_cb: Optional[Callable[[int, int, str], None]] = None) -> Dict:
    """根据撤销记录回滚。"""
    result = {"ok": 0, "fail": 0, "errors": []}
    if not undo_path or not os.path.exists(undo_path):
        result["errors"].append("撤销记录不存在")
        return result

    with open(undo_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    ops = list(reversed(payload.get("operations", [])))
    total = len(ops)
    log.info("开始撤销，共 %d 条，来源 %s", total, undo_path)

    for i, op in enumerate(ops):
        if progress_cb:
            progress_cb(i, total, "正在撤销：%s" % os.path.basename(op["dst"]))
        dst, src = op["dst"], op["src"]
        try:
            if not os.path.exists(dst):
                raise OSError("文件不存在：%s" % dst)
            if os.path.exists(src):
                raise OSError("原名称已被占用：%s" % src)
            os.rename(dst, src)
            result["ok"] += 1
        except OSError as exc:
            log.error("撤销失败 %s: %s", dst, exc)
            result["fail"] += 1
            result["errors"].append({"file": dst, "error": str(exc)})

    log.info("撤销完成：成功 %d，失败 %d", result["ok"], result["fail"])
    return result