"""PyInstaller runtime hook: перенаправляє stdout/stderr у файл.

Спрацьовує лише в замороженій windowed-збірці (console=False), де sys.stdout
дорівнює None і весь вивід print() інакше зникає безслідно. При запуску з
сирців (python logger.py) та в console=True збірці нічого не змінює.

Лог: %LOCALAPPDATA%\\LogTracker\\logger.log (попередній запуск → logger.log.1).
"""

import os
import sys
import threading

MAX_BYTES = 5 * 1024 * 1024


class _CappedWriter:
    """Файловий враппер із лімітом розміру.

    Потрібен, бо WindowHandler.do_resize друкує ~6 рядків на кожну подію руху
    миші — без обмеження лог росте необмежено. Після ліміту запис тихо
    припиняється, застосунок продовжує працювати.

    Захищений блокуванням: print() кличуть і головний потік Tk, і потік
    watchdog (див. FileChangeHandler). Без замка їхні write() перемежовували б
    байти в одному рядку, а self._written += ... (не атомарний) міг би
    недорахувати ліміт. Замок робить кожен write/flush цілісним.
    """

    def __init__(self, stream):
        self._stream = stream
        self._written = 0
        self._stopped = False
        self._lock = threading.Lock()

    def write(self, text):
        with self._lock:
            if not self._stopped:
                try:
                    self._stream.write(text)
                    self._written += len(text)
                    if self._written >= MAX_BYTES:
                        self._stream.write(f"\n--- reached limit of {MAX_BYTES} B, log writing stopped ---\n")
                        self._stream.flush()
                        self._stopped = True
                except Exception:
                    self._stopped = True
        return len(text)

    def flush(self):
        with self._lock:
            try:
                self._stream.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    def fileno(self):
        return self._stream.fileno()

    def close(self):
        self.flush()


def _setup():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or os.path.expanduser("~")
    log_dir = os.path.join(base, "LogTracker")
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "logger.log")
    prev_path = log_path + ".1"

    # Зберігаємо лог попереднього запуску на одне покоління.
    try:
        if os.path.exists(log_path):
            if os.path.exists(prev_path):
                os.remove(prev_path)
            os.replace(log_path, prev_path)
    except OSError:
        pass

    # line_buffering=True критичний: LogTrackerApp.on_closing завершується через
    # os._exit(0), який не скидає буфери Python — інакше хвіст лога губиться.
    stream = open(log_path, "w", encoding="utf-8", buffering=1, errors="replace")
    writer = _CappedWriter(stream)
    sys.stdout = writer
    sys.stderr = writer


# Тільки заморожена збірка без консолі: саме там sys.stdout is None.
if getattr(sys, "frozen", False) and sys.stdout is None:
    try:
        _setup()
    except Exception:
        pass  # не даємо збою логування завалити старт застосунку