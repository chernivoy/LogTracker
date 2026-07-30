import ctypes
from ctypes import wintypes


def check_rdp_status():
    """Повертає True, якщо програма запущена в сесії RDP."""
    SM_REMOTESESSION = 0x1000
    return ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION) != 0


def get_windows_dpi_scale(window_handle):
    """
    Коефіцієнт масштабування DPI монітора, на якому лежить вікно (1.0 == 96 DPI).

    Для геометрії використовуйте це лише як запасний варіант: у гарячих
    шляхах беріть WindowHandler._window_scale(), який читає вже закешований
    масштаб CustomTkinter без Win32-викликів на кожну подію і точно збігається
    з тим, що CTk застосовує всередині geometry().
    """
    try:
        shcore = ctypes.windll.shcore
        # Дескриптор монітора, на якому зараз перебуває вікно.
        monitor = ctypes.windll.user32.MonitorFromWindow(window_handle.winfo_id(), 2)  # MONITOR_DEFAULTTONEAREST
        if monitor:
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))  # MDT_EFFECTIVE_DPI
            # Усереднюємо X і Y так само, як CustomTkinter, щоб множник тут і
            # множник, який CTk застосовує до geometry(), збігалися.
            return (dpi_x.value + dpi_y.value) / (2 * 96.0)
    except Exception:
        pass
    # Запасний варіант для не-Windows або якщо API DPI не спрацює.
    return 1.0


def get_virtual_screen_rect():
    """Межі віртуального екрана (усіх моніторів разом) у фізичних пікселях:
    (x, y, width, height).

    Враховує монітори з від'ємним origin (додаткові екрани ліворуч/вгорі).
    При збої повертає первинний монітор, а в найгіршому разі — 1920x1080.
    """
    try:
        user32 = ctypes.windll.user32
        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
        x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if w > 0 and h > 0:
            return x, y, w, h
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 0, 0, 1920, 1080


def clamp_to_visible(x, y, width, height):
    """Підганяє (x, y) так, щоб вікно цілком лишалося в межах віртуального
    екрана.

    Головний запобіжник від «зниклого» вікна після реконекту RDP, коли
    збережені координати опиняються поза екраном або стають від'ємними.
    Легітимні позиції на додаткових моніторах (зокрема з від'ємним origin)
    зберігаються, бо межі беруться саме з віртуального екрана, а не з
    первинного монітора. Обчислення у фізичних пікселях — тих самих, у яких
    працюють winfo_* і GetSystemMetrics при DPI-awareness.
    """
    vx, vy, vw, vh = get_virtual_screen_rect()

    # Якщо вікно ширше/вище за весь віртуальний екран — притискаємо до кута.
    max_x = vx + vw - min(int(width), vw)
    max_y = vy + vh - min(int(height), vh)

    x = max(vx, min(int(x), max_x))
    y = max(vy, min(int(y), max_y))
    return x, y


def is_rect_visible(x, y, width, height, min_visible=48):
    """True, якщо з віртуальним екраном перетинається щонайменше min_visible
    пікселів вікна по кожній осі.

    Периметричний вартовий (logger._ensure_on_screen) вважає вікно «зниклим»
    лише коли ця умова НЕ виконується, тож звичайне часткове заповзання за
    край, зроблене користувачем свідомо, його не турбує.
    """
    vx, vy, vw, vh = get_virtual_screen_rect()
    inter_w = min(int(x) + int(width), vx + vw) - max(int(x), vx)
    inter_h = min(int(y) + int(height), vy + vh) - max(int(y), vy)
    return inter_w >= min_visible and inter_h >= min_visible
