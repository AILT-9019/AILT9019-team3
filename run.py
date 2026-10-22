from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from app.config import get_settings


def _open_browser(port: int) -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    port = get_settings().port
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
