"""PyInstaller 入口：启动 Streamlit 服务并自动打开浏览器。"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_root() -> Path:
    # PyInstaller 解包目录
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = _resource_root()
    app_file = root / "streamlit_app.py"
    os.chdir(str(root))

    def _open_browser():
        time.sleep(2.5)
        try:
            webbrowser.open("http://localhost:8501")
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web.cli import main as st_main
    sys.argv = [
        "streamlit", "run", str(app_file),
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
        "--server.headless=true",
    ]
    sys.exit(st_main())


if __name__ == "__main__":
    main()
