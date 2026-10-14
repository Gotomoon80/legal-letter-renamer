# -*- coding: utf-8 -*-
"""统一日志模块。

- 同时输出到控制台与文件；
- 日志文件按日期滚动，存放于项目 logs/ 目录；
- 提供便捷函数，供各模块直接调用。
"""
import logging
import os
import sys
from datetime import datetime

from . import config

_LOGGER_NAME = config.APP_NAME_EN
_initialized = False
_log_file_path = None


def _ensure_dir(path: str) -> None:
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """初始化并返回全局 logger（幂等，多次调用只初始化一次）。"""
    global _initialized, _log_file_path
    logger = logging.getLogger(_LOGGER_NAME)
    if _initialized:
        return logger

    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件处理器
    try:
        _ensure_dir(config.LOG_DIR)
        _log_file_path = os.path.join(
            config.LOG_DIR, "app_%s.log" % datetime.now().strftime("%Y%m%d")
        )
        fh = logging.FileHandler(_log_file_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as exc:  # 日志初始化失败也不能影响主流程
        print("日志文件初始化失败: %s" % exc, file=sys.stderr)

    # 控制台处理器（打包为窗口程序时可能没有 stdout，需容错）
    try:
        if sys.stdout is not None:
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(fmt)
            logger.addHandler(sh)
    except Exception:
        pass

    _initialized = True
    logger.info("=" * 60)
    logger.info("%s v%s 启动", config.APP_NAME, config.APP_VERSION)
    logger.info("日志文件: %s", _log_file_path)
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """获取子 logger。"""
    setup_logger()
    if name:
        return logging.getLogger("%s.%s" % (_LOGGER_NAME, name))
    return logging.getLogger(_LOGGER_NAME)


def get_log_file() -> str:
    """返回当前日志文件路径。"""
    setup_logger()
    return _log_file_path or ""


def get_log_dir() -> str:
    return config.LOG_DIR