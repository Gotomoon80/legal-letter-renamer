# -*- coding: utf-8 -*-
"""命名模板引擎。"""
import re
from typing import Dict

from . import config

# 非法文件名字符（Windows）：\ / : * ? " < > | 以及控制字符
_ILLEGAL_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
# Windows 保留设备名
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
             "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}


def format_seq(seq: int, width: int, style: str = "arabic") -> str:
    """把序号格式化。

    style:
      arabic  - 阿拉伯数字，按 width 补零（0001）
      circled - 圈号 ①②③…
      chinese - 中文数字 一二三…
    """
    if style == "circled":
        return to_circled(seq)
    if style == "chinese":
        return to_chinese(seq)
    if width and width > 0:
        return str(seq).zfill(width)
    return str(seq)


def to_circled(n: int) -> str:
    """把整数转成圈号：1->① … 20->⑳，21->㉑ … 35->㉟，36->㊱ … 50->㊿。"""
    if n == 0:
        return "⓪"
    if 1 <= n <= 20:
        return chr(0x2460 + n - 1)
    if 21 <= n <= 35:
        return chr(0x3251 + n - 21)
    if 36 <= n <= 50:
        return chr(0x32B1 + n - 36)
    return str(n)  # 超出范围回退为数字


_CN_DIGITS = "零一二三四五六七八九"


def to_chinese(n: int) -> str:
    """把整数转成中文数字（支持 1~9999）。"""
    if n <= 0:
        return str(n)
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return "十" + (_CN_DIGITS[n - 10] if n > 10 else "")
    if n < 100:
        return _CN_DIGITS[n // 10] + "十" + (_CN_DIGITS[n % 10] if n % 10 else "")
    if n < 1000:
        s = _CN_DIGITS[n // 100] + "百"
        rem = n % 100
        if rem == 0:
            return s
        if rem < 10:
            return s + "零" + _CN_DIGITS[rem]
        return s + to_chinese(rem)
    if n < 10000:
        s = _CN_DIGITS[n // 1000] + "千"
        rem = n % 1000
        if rem == 0:
            return s
        if rem < 100:
            return s + "零" + to_chinese(rem)
        return s + to_chinese(rem)
    return str(n)


def sanitize(name: str) -> str:
    """清理文件名中的非法字符。"""
    out = _ILLEGAL_RE.sub("", name)
    out = out.strip().rstrip(".")
    return out


def is_reserved(name: str) -> bool:
    stem = name.split(".")[0].upper()
    return stem in _RESERVED


def render(template: str, ctx: Dict[str, str]) -> str:
    """根据上下文渲染模板。

    ctx 键：seq(已格式化) name orig body ext qianziwen
    """
    out = template
    for key, val in ctx.items():
        out = out.replace("{%s}" % key, val if val is not None else "")
    # 容错：把未识别的 {xxx} 原样保留（便于用户发现拼写错误）
    return sanitize(out)


def validate_template(template: str):
    """校验模板，返回 (合法, 提示信息)。"""
    if not template or not template.strip():
        return False, "模板不能为空"
    known = {k.strip("{}") for k in config.TEMPLATE_PLACEHOLDERS}
    found = set(re.findall(r"\{([^{}]+)\}", template))
    unknown = found - known
    if unknown:
        return False, "存在未知占位符: %s" % "、".join("{%s}" % u for u in sorted(unknown))
    if not any(k in template for k in ("{姓名}", "{原名}", "{主体}", "{千字文}")) \
            and "{序号}" not in template:
        return True, "模板未使用任何占位符，将生成同名文件"
    return True, ""