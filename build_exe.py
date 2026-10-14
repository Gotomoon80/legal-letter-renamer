# -*- coding: utf-8 -*-
"""打包脚本：把项目打包为单文件 exe。

用法（在项目根目录执行）：
    python build_exe.py

产物：dist/批量文档重命名助手.exe
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, "app.py")
APP_NAME = "批量文档重命名助手"
ICON = os.path.join(ROOT, "assets", "icon.ico")


def main():
    if not os.path.exists(ENTRY):
        print("找不到入口文件：%s" % ENTRY)
        sys.exit(1)

    # 清理旧的构建产物
    for d in ("build", "dist"):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--noconsole",
        "--name", APP_NAME,
        "--hidden-import", "openpyxl",
        "--hidden-import", "xlrd",
        # 本项目完全用不到的科学计算/图像库，排除以显著减小体积
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "pytest",
    ]
    if os.path.exists(ICON):
        cmd += ["--icon", ICON]
        # 把图标一并打进 exe，供运行时设置窗口/任务栏图标使用
        cmd += ["--add-data", "%s;assets" % ICON]
    else:
        print("未找到图标文件（%s），将使用默认图标" % ICON)
    cmd.append(ENTRY)
    print("执行打包命令：\n  " + " ".join(cmd))
    ret = subprocess.call(cmd, cwd=ROOT)
    if ret != 0:
        print("打包失败，返回码 %d" % ret)
        sys.exit(ret)

    exe = os.path.join(ROOT, "dist", APP_NAME + ".exe")
    print("\n打包完成：%s" % exe)
    if os.path.exists(exe):
        print("文件大小：%.1f MB" % (os.path.getsize(exe) / 1024 / 1024))


if __name__ == "__main__":
    main()