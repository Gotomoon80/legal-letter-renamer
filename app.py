# -*- coding: utf-8 -*-
"""批量文档重命名助手 - 启动入口（打包 exe 也以此文件为入口）。"""
import os
import sys

# 把项目根目录加入模块搜索路径，使 src 可作为包导入
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main():
    try:
        from src.ui.main_window import run
        run()
    except Exception:
        import traceback
        try:
            from src.core import config
            os.makedirs(config.LOG_DIR, exist_ok=True)
            with open(os.path.join(config.LOG_DIR, "crash.log"), "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 60 + "\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()