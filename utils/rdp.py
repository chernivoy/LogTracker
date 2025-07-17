import ctypes


def check_rdp_status():
    """Повертає True, якщо програма запущена в сесії RDP."""
    SM_REMOTESESSION = 0x1000
    return ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION) != 0
