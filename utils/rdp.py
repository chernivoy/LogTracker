import ctypes
from ctypes import wintypes


def check_rdp_status():
    """Повертає True, якщо програма запущена в сесії RDP."""
    SM_REMOTESESSION = 0x1000
    return ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION) != 0


def get_window_dpi(hwnd):
    try:
        user32 = ctypes.windll.user32
        shcore = ctypes.windll.shcore
        # Установка DPI-awareness, якщо ще не встановлено
        shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        return user32.GetDpiForWindow(hwnd)
    except Exception:
        return 96  # Стандартний DPI


def get_windows_dpi_scale(window_handle):
    """
    Отримує коефіцієнт масштабування DPI для монітора, на якому знаходиться дане вікно.
    Повертає 1.0, якщо не в Windows або якщо DPI-обізнаність не встановлена ​​правильно.
    """
    try:
        shcore = ctypes.windll.shcore
        # Отримуємо дескриптор монітора, на якому зараз знаходиться вікно
        monitor = ctypes.windll.user32.MonitorFromWindow(window_handle.winfo_id(), 2)  # MONITOR_DEFAULTTONEAREST
        if monitor:
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            # Отримуємо ефективний DPI для монітора
            shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))  # MDT_EFFECTIVE_DPI
            # Повертаємо коефіцієнт масштабування відносно 96 DPI (стандарт)
            return dpi_x.value / 96.0
    except Exception:
        # Запасний варіант для не-Windows або якщо API DPI не спрацює
        return 1.0
