"""把 Streamlit 应用打包成 Windows exe（也适用于 macOS / Linux）。

用法：
    pip install pyinstaller
    python scripts/build_exe.py

打包完成后在 `dist/StockAssistant/` 下找到可执行文件。双击即会启动本地服务并
自动打开浏览器到 http://localhost:8501

实现方式：
    PyInstaller 把 `scripts/launcher.py` 打包为单可执行；该脚本会内嵌 streamlit run。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    launcher = ROOT / "scripts" / "launcher.py"
    if not launcher.exists():
        raise FileNotFoundError(launcher)

    # Streamlit 静态资源需要打入
    streamlit_dir = Path(sys.executable).parent.parent / "lib"  # 占位提示
    add_data = [
        ("streamlit_app.py", "."),
        ("app", "app"),
        (".streamlit", ".streamlit"),
    ]
    sep = ";" if os.name == "nt" else ":"
    add_data_args = []
    for src, dest in add_data:
        add_data_args += ["--add-data", f"{ROOT/src}{sep}{dest}"]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "StockAssistant",
        "--noconfirm",
        "--clean",
        "--onedir",                       # 单目录更稳，启动更快
        "--collect-all", "streamlit",
        "--collect-all", "akshare",
        "--collect-all", "yfinance",
        "--collect-all", "feedparser",
        "--collect-all", "plotly",
        "--collect-submodules", "apscheduler",
        *add_data_args,
        str(launcher),
    ]
    print("[build_exe] running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))
    print("[build_exe] done. See dist/StockAssistant/")


if __name__ == "__main__":
    main()
