from __future__ import annotations

import os
import socket
import threading
import time

import uvicorn
import webview

from backend.app import app
from backend.config import settings


class DesktopApi:
    """JS-callable desktop API exposed to the frontend as window.pywebview.api.

    Wave 18: choose_save_folder() opens a native folder picker so the
    export menu's "Choose folder each time" option works inside the
    desktop shell (a plain browser blob-download does not).
    """

    def __init__(self) -> None:
        self._window = None

    def bind(self, window) -> None:
        self._window = window

    def choose_save_folder(self) -> str | None:
        """Open a native folder-selection dialog. Returns the chosen
        absolute path, or None if the user cancelled."""
        if self._window is None:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        # create_file_dialog returns a tuple/list of paths.
        return result[0] if isinstance(result, (list, tuple)) else result


def run_backend() -> None:
    uvicorn.run(
        app,
        host=settings.backend_host,
        port=settings.backend_port,
        log_level="info" if settings.debug else "warning",
    )


def wait_for_backend(timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((settings.backend_host, settings.backend_port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError("FastAPI backend did not become ready in time.")


def main() -> None:
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    wait_for_backend()
    url = f"http://{settings.backend_host}:{settings.backend_port}/"
    if os.getenv("DEPOPRO_LAUNCHER_SMOKE_TEST") == "1":
        return
    desktop_api = DesktopApi()
    window = webview.create_window(
        title=settings.app_name,
        url=url,
        width=1600,
        height=1000,
        min_size=(1200, 780),
        js_api=desktop_api,
    )
    desktop_api.bind(window)
    webview.start(debug=settings.debug)


if __name__ == "__main__":
    main()
