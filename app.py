"""Drive Downloader — desktop app entry point."""

import sys
from pathlib import Path

import webview

from backend import Api

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
UI = BASE / "ui" / "index.html"


def main():
    api = Api()
    window = webview.create_window(
        "Drive Downloader",
        url=str(UI),
        js_api=api,
        width=900, height=720, min_size=(640, 520),
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
