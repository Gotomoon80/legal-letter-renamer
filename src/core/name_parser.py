# -*- coding: utf-8 -*-
"""文件名解析：提取序号、主体、姓名候选、扩展名。"""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from . import config

# ---- 序号字符集 -----------------------------------------------------------
# ①..⑳
_CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)}
_CIRCLED[chr(0x24EA)] = 0  # ⓪
# ⑴..⒇
_PAREN_DIGIT = {chr(0x2474 + i): i + 1 for i in range(20)}
# 中文数字
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "壹": 1, "贰": 2, "叁": 3, "肆": 4,
           "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9, "拾": 10}
# 中文数字（支持 十一..九十九 这类）
_CN_NUM_RE = re.compile(r"^([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾]{1,3})")

# 需要从"序号"后面剥离的分隔符/装饰符
_SEP_CHARS = " \t.、,，。:：;；_-—~～()（）[]【】<>《》「」『』〔〕〈〉\"'’“”"
_SEP_SET = set(_SEP_CHARS)
# 文件名开头的装饰性包裹符号（《》等），解析序号前先跳过
_LEAD_DECOR = "《「『【〔〈（(［[｛{ \t"
# 序号类字符（圈号/带括号数字），不应残留在姓名候选里
_NUM_CHARS = set(_CIRCLED) | set(_PAREN_DIGIT)


def _cn_to_int(s: str) -> Optional[int]:
    """中文数字转整数（支持 十、十一、二十、二十三 等）。"""
    if not s:
        return None
    if s == "十":
        return 10
    if len(s) == 1:
        return _CN_NUM.get(s)
    # 形如 十一 / 二十 / 二十三
    if s[0] == "十":
        rest = _CN_NUM.get(s[1:], 0)
        return 10 + rest
    if len(s) >= 2 and s[1] == "十":
        tens = _CN_NUM.get(s[0], 0) * 10
        ones = _CN_NUM.get(s[2], 0) if len(s) > 2 else 0
        return tens + ones
    return None


@dataclass
class ParsedName:
    """文件名解析结果。"""
    original: str                      # 原始完整文件名
    stem: str                          # 去扩展名后的名字
    ext: str                           # 扩展名（含点，小写）
    seq: Optional[int] = None          # 解析出的序号
    seq_raw: str = ""                  # 序号的原始字符串
    body: str = ""                     # 去掉序号后的主体
    has_placeholder: bool = False      # 是否含"待填姓名"占位符
    name_candidate: str = ""           # 姓名候选（剥离噪声词后的结果）
    content_name: str = ""             # 从文档正文内容提取到的姓名
    tokens: List[str] = field(default_factory=list)  # 候选片段（按分隔符/噪声词切分）

    @property
    def seq_text(self) -> str:
        return self.seq_raw or ""


def _try_extract_seq(s: str):
    """在字符串开头尝试各种序号样式，返回 (seq, raw, rest)。"""
    # 1) 圈号 ① ② …
    if s and s[0] in _CIRCLED:
        return _CIRCLED[s[0]], s[0], s[1:].lstrip(_SEP_CHARS)
    # 2) 全角括号数字 ⑴ ⑵ …
    if s and s[0] in _PAREN_DIGIT:
        return _PAREN_DIGIT[s[0]], s[0], s[1:].lstrip(_SEP_CHARS)
    # 3) 【1】 / (1) / [1] / （1）
    m = re.match(r"^[（(\[【]\s*(\d{1,4})\s*[)）\]】]", s)
    if m:
        return int(m.group(1)), m.group(0), s[m.end():].lstrip(_SEP_CHARS)
    # 4) 第1号 / 第1 / 第1份
    m = re.match(r"^第\s*(\d{1,4})\s*[号份个]?", s)
    if m:
        return int(m.group(1)), m.group(0), s[m.end():].lstrip(_SEP_CHARS)
    # 5) 开头纯数字：1、01、001，后跟分隔符或直接接文字
    m = re.match(r"^(\d{1,4})(?=[\s.、,，。:：;；_\-—()（）\[\]【】]|$)", s)
    if m:
        raw = m.group(1)
        rest = s[m.end():].lstrip(_SEP_CHARS)
        return int(raw), raw, rest
    # 6) 中文数字序号：一、二、三…（后面需有分隔符，避免误伤"张三"）
    m = _CN_NUM_RE.match(s)
    if m and len(s) > m.end() and s[m.end()] in _SEP_SET:
        num = _cn_to_int(m.group(1))
        if num is not None:
            return num, m.group(1), s[m.end():].lstrip(_SEP_CHARS)
    return None, "", s


def _extract_seq(stem: str):
    """从名字开头提取序号，返回 (seq:int|None, raw:str, rest:str)。

    会先直接匹配，失败时跳过开头的装饰符号（如《「【）后重试，
    以兼容《①致张三律师函》这类被书名号包裹的文件名。
    """
    seq, raw, rest = _try_extract_seq(stem)
    if seq is not None:
        return seq, raw, rest
    stripped = stem.lstrip(_LEAD_DECOR)
    if stripped and stripped != stem:
        seq, raw, rest = _try_extract_seq(stripped)
        if seq is not None:
            return seq, raw, rest
        return None, "", stripped
    return None, "", stem


def _strip_noise(text: str, noise_words: List[str]) -> str:
    """剥离模板噪声词。"""
    out = text
    for w in sorted(noise_words, key=len, reverse=True):
        if w:
            out = out.replace(w, "")
    return out


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _extract_candidate(body: str, noise_words: List[str]) -> str:
    """从主体中提取姓名候选。"""
    cleaned = _strip_noise(body, noise_words)
    # 去掉分隔符/标点/空格，以及残留的序号类字符（圈号等）
    cleaned = "".join(ch for ch in cleaned if ch not in _SEP_SET and ch not in _NUM_CHARS)
    # 只保留中文/字母数字
    cleaned = "".join(ch for ch in cleaned if _is_cjk(ch) or ch.isalnum())
    return cleaned


def _split_tokens(body: str, noise_words: List[str]) -> List[str]:
    """把主体切成若干候选片段，供匹配阶段逐个尝试。"""
    tokens: List[str] = []
    # 先按分隔符切
    parts = re.split(r"[%s]+" % re.escape(_SEP_CHARS), body)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 再按噪声词切
        sub = _strip_noise(p, noise_words)
        for piece in re.split(r"[%s]+" % re.escape("".join(noise_words)) if noise_words else "", sub):
            piece = piece.strip()
            piece = "".join(ch for ch in piece
                            if ch not in _NUM_CHARS and ch not in _SEP_SET)
            if piece:
                tokens.append(piece)
    # 去重保序
    seen = set()
    uniq = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def parse_filename(filename: str, noise_words: Optional[List[str]] = None,
                   content_name: str = "") -> ParsedName:
    """解析文件名，返回 ParsedName。"""
    if noise_words is None:
        noise_words = config.DEFAULT_NOISE_WORDS

    stem, ext = os.path.splitext(filename)
    ext = ext.lower()

    # 去掉常见的装饰性书名号/括号（仅用于候选提取，序号判断仍基于原串）
    seq, seq_raw, rest = _extract_seq(stem)

    # 主体：优先用 rest，但如果原串带了包裹符号，这里保留原有字符
    body = rest if rest else stem

    # 占位符检测
    low = stem.lower()
    has_ph = any(ph.lower() in low for ph in config.NAME_PLACEHOLDERS)

    candidate = "" if has_ph else _extract_candidate(body, noise_words)
    tokens = _split_tokens(body, noise_words)

    return ParsedName(
        original=filename,
        stem=stem,
        ext=ext,
        seq=seq,
        seq_raw=seq_raw,
        body=body,
        has_placeholder=has_ph,
        name_candidate=candidate,
        content_name=content_name,
        tokens=tokens,
    )