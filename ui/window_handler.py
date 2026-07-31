import ctypes
import os
import time
import tkinter as tk

import customtkinter as ctk

from config_manager import ConfigManager
from utils.path import PathUtils
from utils import rdp

CONFIG_FILE_WINDOW = PathUtils.resource_path(os.path.join("src", "window_config.ini"))

# --- ctypes: типи Win32-викликів округлення кутів -------------------------
# Без явних restype 64-бітні HWND/HRGN зрізаються до 32 біт (типовий restype
# ctypes — c_int), і зіпсований дескриптор регіону міг би піти далі в
# SetWindowRgn. Ці функції кличе лише window_handler (і мертвий pin.py), тож
# налаштування на кешованому windll стороннього коду не зачіпає. RedrawWindow
# теж типізуємо — інакше передача 64-бітного hwnd у нетипізовану функцію дала б
# OverflowError на великому вказівнику.
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_user32.GetParent.restype = ctypes.c_void_p
_user32.GetParent.argtypes = (ctypes.c_void_p,)
_gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
_gdi32.CreateRoundRectRgn.argtypes = (ctypes.c_int,) * 6
_user32.SetWindowRgn.restype = ctypes.c_int
_user32.SetWindowRgn.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
_gdi32.DeleteObject.restype = ctypes.c_int
_gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
_user32.RedrawWindow.restype = ctypes.c_int
_user32.RedrawWindow.argtypes = (
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
)


class WindowHandler:
    """
    Відповідає за налаштування та поведінку вікна:
    зміна розміру, переміщення та округлення кутів.
    """

    CORNER_RADIUS = 30  # радіус округлення у ЛОГІЧНИХ px (масштабується за DPI)

    @staticmethod
    def save_window_size(section, root):
        # Симетрично до load_window_size: зберігаємо ЛОГІЧНІ width/height
        # (як їх бачить CTk) і ФІЗИЧНІ x/y. Round-trip save↔load іде через
        # рідну модель масштабування CTk, без ручного множника: load віддає
        # логічні w/h у geometry(), а CTk сам домножує їх до фізичних.
        #
        # x/y лишаємо фізичними через winfo_x()/winfo_y(): це надійні цілі
        # (можуть бути від'ємними на моніторі ліворуч/вгорі), а розбір рядка
        # geometry() для позиції неоднозначний — Tk трактує "-100" як «100 px
        # від правого краю», а не x=-100.
        width = WindowHandler._to_logical(root, root.winfo_width())
        height = WindowHandler._to_logical(root, root.winfo_height())
        x = root.winfo_x()
        y = root.winfo_y()

        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['width'] = str(width)   # ЛОГІЧНА ширина
        config[section]['height'] = str(height)  # ЛОГІЧНА висота
        config[section]['x'] = str(x)  # ФІЗИЧНИЙ X
        config[section]['y'] = str(y)  # ФІЗИЧНИЙ Y

        ConfigManager.save_atomic(config, CONFIG_FILE_WINDOW)

    @staticmethod
    def save_window_params(section, x=None, y=None, width=None, height=None):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['x'] = str(x) if x is not None else "100"
        config[section]['y'] = str(y) if y is not None else "100"
        config[section]['width'] = str(width) if width is not None else "300"
        config[section]['height'] = str(height) if height is not None else "300"

        ConfigManager.save_atomic(config, CONFIG_FILE_WINDOW)

    @staticmethod
    def _window_scale(root):
        """Масштаб, який CTk застосовує до geometry() (== DPI монітора / 96).

        Беремо його з самого CustomTkinter — це кешоване значення, без
        Win32-викликів на кожну подію. Тоді ділення розмірів тут і множення
        всередині CTk.geometry() скорочуються ТОЧНО (включно з можливим
        користувацьким window_scaling), а не приблизно, як при окремому
        запиті GetDpiForMonitor. Запасний варіант — прямий запит DPI монітора.
        """
        getter = getattr(root, "_get_window_scaling", None)
        if callable(getter):
            try:
                scale = getter()
                if scale and scale > 0:
                    return scale
            except Exception:
                pass
        try:
            scale = rdp.get_windows_dpi_scale(root)
            if scale and scale > 0:
                return scale
        except Exception:
            pass
        return 2.0

    @staticmethod
    def _to_logical(root, physical_value):
        """Фізичні пікселі → логічні (як їх зберігає CTk), тим самим
        реверсом масштабу, який CTk застосовує в geometry(). Пара до того,
        як geometry() домножує назад. Запасний варіант — ділення на
        _window_scale()."""
        rev = getattr(root, "_reverse_window_scaling", None)
        if callable(rev):
            try:
                return int(rev(physical_value))
            except Exception:
                pass
        scale = WindowHandler._window_scale(root)
        return int(physical_value / scale) if scale else int(physical_value)

    @staticmethod
    def load_window_size(section, root):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            return None

        # У INI лежать ЛОГІЧНІ width/height і ФІЗИЧНІ x/y. Логічні w/h
        # передаємо в geometry() як є — CTk домножить їх до фізичних сам
        # (симетрично до save_window_size). Жодного ручного множника тут
        # більше немає: round-trip повністю на рідній моделі масштабування
        # CTk, тож при зміні DPI (реконект) зберігається ЛОГІЧНИЙ розмір
        # вікна, а не фіксований піксельний.
        width = config.getint(section, 'width', fallback=800)
        height = config.getint(section, 'height', fallback=600)
        x = config.getint(section, 'x', fallback=100)
        y = config.getint(section, 'y', fallback=100)

        # Захист від зниклого вікна: clamp у фізичному просторі екрана, тож
        # логічні w/h переводимо в фізичну оцінку розміру через масштаб CTk.
        scale = WindowHandler._window_scale(root)
        phys_w = int(width * scale)
        phys_h = int(height * scale)
        x, y = rdp.clamp_to_visible(x, y, phys_w, phys_h)

        return f'{width}x{height}+{x}+{y}'

    @staticmethod
    def _set_corner_region(hwnd, width, height, radius, redraw=True):
        """Створює округлий регіон width×height (ФІЗИЧНІ px) і віддає його
        вікну hwnd. Повертає True на успіх.

        SetWindowRgn ПЕРЕБИРАЄ володіння регіоном і сам видаляє попередній,
        тож на успіху окремий DeleteObject не потрібен. На ЗБОЇ ОС регіон НЕ
        приймає — володіння лишається за нами, тому звільняємо його вручну,
        інакше кожен збій = витік GDI-об'єкта.
        """
        hrgn = _gdi32.CreateRoundRectRgn(0, 0, width, height, radius, radius)
        if not hrgn:
            return False
        if _user32.SetWindowRgn(hwnd, hrgn, redraw) == 0:
            _gdi32.DeleteObject(hrgn)
            return False
        return True

    @staticmethod
    def round_corners(window, radius):
        """Накладає округлий регіон на все вікно. `radius` — у ЛОГІЧНИХ px:
        множимо на масштаб CTk, бо winfo_width/height повертають ФІЗИЧНІ px, і
        без масштабу при DPI 200% кути виглядали б удвічі гострішими за задум
        (border і minsize масштабуються так само).

        Викликається в кінці КОЖНОГО ресайзу і при відновленні з трея, тож
        друкуємо лише на збої — інакше success-рядок спамив би logger.log
        (у windowed-збірці файл має ліміт MAX_BYTES).
        """
        hwnd = _user32.GetParent(window.winfo_id())
        radius = int(radius * WindowHandler._window_scale(window))
        if not WindowHandler._set_corner_region(
            hwnd, window.winfo_width(), window.winfo_height(), radius
        ):
            print("[round_corners] SetWindowRgn failed")

    @staticmethod
    def start_move(event: tk.Event, root: ctk.CTk):
        """
        Зберігає початкову позицію курсора відносно вікна
        для подальшого переміщення.
        """
        root._start_move_x = event.x_root - root.winfo_x()
        root._start_move_y = event.y_root - root.winfo_y()

    @staticmethod
    def do_move(event: tk.Event, root: ctk.CTk):
        """
        Переміщує вікно відповідно до руху курсора.
        """
        if not root.overrideredirect():
            return

        # Якщо активний ресайз краю — не рухаємо вікно. Обробники move (на
        # заголовку/фреймі) і resize (на root) прив'язані обидва, і в зоні
        # краю спрацьовували б разом, даючи дрож «рух + зміна розміру».
        if getattr(root, "_resize_dir", None):
            return

        new_x_logical = event.x_root - root._start_move_x
        new_y_logical = event.y_root - root._start_move_y

        root.geometry(f"+{new_x_logical}+{new_y_logical}")

    @staticmethod
    def bind_resize_events(root: ctk.CTk):
        """
        Прив'язує події ресайзу (зміна розміру вікна) до кореневого вікна.

        Move-прив'язки (перетягування за заголовок) тут НЕ ставляться: їх вішає
        ErrorWindow.bind_events напряму на file_label і main_frame, де є прямі
        посилання на віджети. Раніше цей метод ще й дублював їх, шукаючи заголовок
        за жорстко зашитим Tk-шляхом ".!ctkframe.!ctklabel" — крихким до зміни
        ієрархії віджетів; ті самі хендлери одразу перезаписувались у bind_events,
        тож lookup був зайвий і лише створював точку мовчазної деградації.
        """
        # Події для ресайзу (зміна розміру вікна)
        resize_handlers = [
            ("<Motion>", WindowHandler.change_cursor),  # Зміна курсора при наведенні на край
            ("<ButtonPress-1>", WindowHandler.start_resize),  # Початок ресайзу
            ("<B1-Motion>", WindowHandler.do_resize),  # Виконання ресайзу
            ("<ButtonRelease-1>", WindowHandler.stop_resize),  # Завершення ресайзу
        ]

        # Прив'язуємо події ресайзу безпосередньо до кореневого вікна.
        for event_type, handler_func in resize_handlers:
            root.bind(event_type, handler_func)

    @staticmethod
    def _header_bottom(root):
        """Нижня Y-межа заголовка у координатах вікна (фізичні px) = верх
        контент-фрейму. Уся смуга над нею — зона ПЕРЕМІЩЕННЯ вікна, а не
        ресайзу. Якщо межу не визначити — 0 (зони заголовка нема, поведінка
        як раніше)."""
        content = getattr(root, "_content_frame", None)
        if content is not None:
            try:
                return content.winfo_rooty() - root.winfo_rooty()
            except Exception:
                pass
        return 0

    @staticmethod
    def change_cursor(event: tk.Event):
        """
        Змінює вигляд курсора на краю вікна для вказівки на можливість ресайзу.
        """
        root = event.widget.winfo_toplevel()
        # Якщо вікно має рамку (не overrideredirect), ОС сама керує курсором.
        if not root.overrideredirect():
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Кнопки згорнути/бургер — клік має лишатись кліком, не ресайзом і не
        # переміщенням. Шлях Tk-віджета кнопки містить "ctkbutton" (в т.ч. для
        # внутрішніх canvas/label). Перевіряємо ДО зони заголовка, бо кнопки
        # теж у ній лежать.
        widget_path = str(event.widget)
        if "ctkbutton" in widget_path:
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Координати курсора відносно ВІКНА (у фізичних пікселях, як і winfo_*).
        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()

        # Уся смуга заголовка (над контентом) — зона ПЕРЕМІЩЕННЯ: і текст
        # заголовка, і порожній фон рухають вікно (move-прив'язки заголовка та
        # main_frame самі це роблять), тож resize-курсор тут не показуємо й
        # напрямок не ставимо. Ресайз лишається на нижньому/бічних краях.
        if y_logical < WindowHandler._header_bottom(root):
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Зона краю ~20 логічних px: множимо на масштаб, інакше при DPI 200%
        # смуга захоплення була б лише ~10 фізичних px — важко влучити,
        # надто трекпадом через RDP. _window_scale читає кеш CTk, без Win32.
        border = int(20 * WindowHandler._window_scale(root))

        cursor = ""
        root._resize_dir = None  # Скидаємо напрямок ресайзу

        # Визначаємо зону й ставимо СТАНДАРТНИЙ віндовсний курсор ресайзу.
        # Ці Tk-імена мапляться на нативні курсори Windows:
        #   size_nw_se -> IDC_SIZENWSE (⤡), size_ne_sw -> IDC_SIZENESW (⤢),
        #   size_we    -> IDC_SIZEWE   (↔), size_ns    -> IDC_SIZENS   (↕).
        # Раніше стояло "sizing <напрямок>": друге слово Tk ігнорує, тож усі
        # зони показували один 4-стрілковий IDC_SIZEALL, а не напрямкові.
        if x_logical <= border and y_logical <= border:
            cursor = "size_nw_se"
            root._resize_dir = "nw"
        elif x_logical >= width_logical - border and y_logical <= border:
            cursor = "size_ne_sw"
            root._resize_dir = "ne"
        elif x_logical <= border and y_logical >= height_logical - border:
            cursor = "size_ne_sw"
            root._resize_dir = "sw"
        elif x_logical >= width_logical - border and y_logical >= height_logical - border:
            cursor = "size_nw_se"
            root._resize_dir = "se"
        elif x_logical <= border:
            cursor = "size_we"
            root._resize_dir = "w"
        elif x_logical >= width_logical - border:
            cursor = "size_we"
            root._resize_dir = "e"
        elif y_logical <= border:
            cursor = "size_ns"
            root._resize_dir = "n"
        elif y_logical >= height_logical - border:
            cursor = "size_ns"
            root._resize_dir = "s"

        root.configure(cursor=cursor or "")

    @staticmethod
    def start_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        # Клік по кнопці в куті — це клік, а не початок ресайзу чи переміщення.
        # Перевіряємо ДО зони заголовка, бо кнопки теж у ній. Шлях віджета
        # кнопки містить "ctkbutton" (в т.ч. для внутрішніх canvas/label).
        widget_path = str(event.widget)
        if "ctkbutton" in widget_path:
            root._resize_dir = None
            return

        # Кешуємо масштаб на весь жест: DPI монітора під час одного
        # перетягування не змінюється, тож не смикаємо Win32 на кожну подію.
        scale = WindowHandler._window_scale(root)

        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        border = int(20 * scale)

        # Уся смуга заголовка (над контентом) — зона ПЕРЕМІЩЕННЯ, не ресайзу:
        # move-прив'язки заголовка/main_frame самі рухатимуть вікно, а ми лише
        # не вмикаємо тут ресайз. Ресайз лишається на нижньому/бічних краях.
        if y_logical < WindowHandler._header_bottom(root):
            root._resize_dir = None
            return

        # Визначаємо напрямок ресайзу на основі позиції курсора в момент кліка
        root._resize_dir = None
        if x_logical <= border and y_logical <= border:
            root._resize_dir = "nw"
        elif x_logical >= width_logical - border and y_logical <= border:
            root._resize_dir = "ne"
        elif x_logical <= border and y_logical >= height_logical - border:
            root._resize_dir = "sw"
        elif x_logical >= width_logical - border and y_logical >= height_logical - border:
            root._resize_dir = "se"
        elif x_logical <= border:
            root._resize_dir = "w"
        elif x_logical >= width_logical - border:
            root._resize_dir = "e"
        elif y_logical <= border:
            root._resize_dir = "n"
        elif y_logical >= height_logical - border:
            root._resize_dir = "s"

        # Якщо ми не в зоні ресайзу, виходимо
        if not root.overrideredirect() or not root._resize_dir:
            root._resize_dir = None  # Впевнюємося, що напрямок скинуто
            return
        # --- КІНЕЦЬ НОВОЇ ЛОГІКИ ---

        # Округлення НЕ скидаємо: регіон тепер тримається живим і
        # перераховується щокадру в _apply_resize_frame під новий розмір, тож
        # кути лишаються скругленими протягом усього жесту. (Раніше тут стояв
        # SetWindowRgn(hwnd, 0) — квадратні кути аж до stop_resize.)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())

        root._resize_hwnd = hwnd     # кешуємо hwnd на весь жест (для перемальовки)
        root._resize_scale = scale  # масштаб зафіксовано на весь жест ресайзу
        root._resize_pending = None      # остання відкладена геометрія (тротлінг)
        root._resize_trail_job = None    # трейлінг-таймер фінального кадру
        root._resize_last_paint = 0.0    # час останнього застосованого кадру
        root._start_cursor_x_logical = event.x_root
        root._start_cursor_y_logical = event.y_root
        root._start_width_logical = root.winfo_width()
        root._start_height_logical = root.winfo_height()
        root._start_win_x_logical = root.winfo_x()
        root._start_win_y_logical = root.winfo_y()

    @staticmethod
    def do_resize(event: tk.Event):
        """
        Виконує зміну розміру вікна відповідно до руху курсора.
        """
        root = event.widget.winfo_toplevel()

        if not hasattr(root, "_resize_dir") or not root._resize_dir:
            return
        if not root.overrideredirect():
            return

        current_cursor_x_logical = event.x_root
        current_cursor_y_logical = event.y_root

        dx_logical = current_cursor_x_logical - root._start_cursor_x_logical
        dy_logical = current_cursor_y_logical - root._start_cursor_y_logical

        dir = root._resize_dir

        # Масштаб зафіксовано в start_resize — не смикаємо Win32 на кожну подію.
        scale = getattr(root, "_resize_scale", None) or WindowHandler._window_scale(root)

        # Мінімум у ФІЗИЧНИХ пікселях, узгоджений з root.minsize(...): CTk
        # застосовує до minsize той самий масштаб, тож OS-мінімум теж
        # (min_logical * scale). Якби межі не збігалися, при ресайзі з заходу/
        # півночі OS клампив би розмір, а x/y усе одно зсувалися б — вікно
        # «повзло» б убік. Висота — динамічна (заголовок + запас під текст),
        # її рахує ErrorWindow і кладе в root._min_height_logical.
        min_width = int(300 * scale)
        min_height = int(getattr(root, "_min_height_logical", 100) * scale)

        new_width_logical = root._start_width_logical
        new_height_logical = root._start_height_logical
        new_x_logical = root._start_win_x_logical
        new_y_logical = root._start_win_y_logical

        if "e" in dir:  # East (right)
            new_width_logical = max(root._start_width_logical + dx_logical, min_width)
        if "s" in dir:  # South (bottom)
            new_height_logical = max(root._start_height_logical + dy_logical, min_height)

        if "w" in dir:  # West (left)
            potential_new_width = root._start_width_logical - dx_logical
            if potential_new_width >= min_width:
                new_width_logical = potential_new_width
                new_x_logical = root._start_win_x_logical + dx_logical
            else:
                new_width_logical = min_width
                new_x_logical = root._start_win_x_logical + root._start_width_logical - min_width

        if "n" in dir:  # North (top)
            potential_new_height = root._start_height_logical - dy_logical
            if potential_new_height >= min_height:
                new_height_logical = potential_new_height
                new_y_logical = root._start_win_y_logical + dy_logical
            else:
                new_height_logical = min_height
                new_y_logical = root._start_win_y_logical + root._start_height_logical - min_height

        # Компенсуємо фізичні розміри, ділячи на масштаб CTk перед geometry()
        # (усередині CTk множить назад). X/Y — фізичні, без ділення.
        final_width_for_geometry = int(new_width_logical / scale)
        final_height_for_geometry = int(new_height_logical / scale)

        # Зберігаємо цільову геометрію й малюємо з ТРОТЛІНГОМ ~60 к/с. Кожен
        # застосований кадр — це `geometry()` + синхронна перемальовка дітей
        # (див. _apply_resize_frame), що недешево, надто по RDP. Миша ж сипле
        # ~100–125 подій/с; без тротлінгу кожна робила б повний erase+repaint
        # шаруватого вікна, і кадри не встигали б — звідси ривки.
        root._resize_pending = (
            f"{final_width_for_geometry}x{final_height_for_geometry}+{int(new_x_logical)}+{int(new_y_logical)}",
            dir,
        )
        now = time.perf_counter()
        if now - getattr(root, "_resize_last_paint", 0.0) >= 0.016:  # leading edge, ~60 к/с
            root._resize_last_paint = now
            WindowHandler._apply_resize_frame(root)
        # Трейлінг: гарантуємо, що остання позиція (можливо, «пропущена»
        # тротлінгом) таки відмалюється, коли рух зупиниться.
        trail = getattr(root, "_resize_trail_job", None)
        if trail is not None:
            root.after_cancel(trail)
        root._resize_trail_job = root.after(24, lambda: WindowHandler._apply_resize_frame(root))

    @staticmethod
    def _apply_resize_frame(root):
        """Застосовує останню відкладену геометрію ресайзу і синхронно
        перемальовує дітей.

        Синхронна перемальовка потрібна, бо кнопки праворуч угорі закріплені
        за правим краєм (grid `sticky "ne"`, колонка з `weight 0`), тож при
        ресайзі змінюється лише їхня ПОЗИЦІЯ, а не розмір. CTk перемальовує
        віджет тільки на зміні РОЗМІРУ (`_update_dimensions_event`), тож
        пересунуті кнопки самі не перемальовуються — на шаруватому вікні вони
        зникають/стрибають. `update_idletasks` спершу застосовує відкладений
        re-layout (пересуває HWND кнопок), але не обробляє `WM_PAINT`, тому далі
        явно кличемо `RedrawWindow(...UPDATENOW)` — синхронний `WM_PAINT` усім
        дочірнім HWND на вже коректних позиціях.
        """
        pending = getattr(root, "_resize_pending", None)
        if not pending:
            return
        geometry_string, dir = pending

        root.geometry(geometry_string)
        root.update_idletasks()

        hwnd = getattr(root, "_resize_hwnd", None)
        if hwnd:
            # Тримаємо округлення ЖИВИМ під час ресайзу: регіон перераховуємо
            # під новий ФІЗИЧНИЙ розмір щокадру (після update_idletasks winfo_*
            # уже оновлені), тож він завжди збігається з вікном і кутів не
            # обрізає. bRedraw=False — тут не малюємо, це зробить наступний
            # RedrawWindow (одна перемальовка на кадр, без подвійної).
            scale = getattr(root, "_resize_scale", None) or 1.0
            WindowHandler._set_corner_region(
                hwnd, root.winfo_width(), root.winfo_height(),
                int(WindowHandler.CORNER_RADIUS * scale), redraw=False,
            )

            RDW_INVALIDATE, RDW_ERASE, RDW_ALLCHILDREN, RDW_UPDATENOW = 0x1, 0x4, 0x80, 0x100
            flags = RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW
            # ERASE — лише для заходу/півночі, де рухається початок вікна:
            # там контент їде екраном і майже-чорні згладжені краї тексту хедера
            # (не keyʼяться в прозорість ключем "#000001") лишають слід на
            # старому місці; стирання фону його прибирає. На сході/півдні
            # початок не рухається — зайвий erase лише додав би мерехтіння.
            if "w" in dir or "n" in dir:
                flags |= RDW_ERASE
            ctypes.windll.user32.RedrawWindow(hwnd, None, None, flags)

    @staticmethod
    def stop_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        # Ресайзу не було (звичайний клік у не-крайовій зоні) — не пишемо ini
        # на кожен клік і не перемальовуємо кути, лише скидаємо курсор.
        if not getattr(root, "_resize_dir", None):
            root.configure(cursor="")
            return

        # Скасовуємо трейлінг-таймер і застосовуємо ФІНАЛЬНИЙ кадр: остання
        # подія руху могла бути «пропущена» тротлінгом, тож без цього вікно
        # завмерло б на передостанній позиції до кінця жесту.
        trail = getattr(root, "_resize_trail_job", None)
        if trail is not None:
            root.after_cancel(trail)
            root._resize_trail_job = None
        WindowHandler._apply_resize_frame(root)

        # Оновлюємо реальні розміри перед clamp/заокругленням: після geometry()
        # у do_resize winfo_* могли ще не оновитися.
        root.update_idletasks()

        # Підстраховка: якщо вікно якось опинилося фактично поза екраном —
        # повертаємо його всередину. Перевіряємо саме видимість (а не «цілком
        # уміщається»), щоб звичайний ресайз за правий/нижній край не смикав
        # протилежну межу.
        cur_x, cur_y = root.winfo_x(), root.winfo_y()
        cur_w, cur_h = root.winfo_width(), root.winfo_height()
        if not rdp.is_rect_visible(cur_x, cur_y, cur_w, cur_h):
            nx, ny = rdp.clamp_to_visible(cur_x, cur_y, cur_w, cur_h)
            root.geometry(f"+{nx}+{ny}")
            root.update_idletasks()

        WindowHandler.save_window_size('Window', root)
        root._resize_dir = None
        root._resize_scale = None
        root._resize_hwnd = None
        root._resize_pending = None
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        # Повертаємо округлення після завершення ресайзу (фінальний чистий
        # регіон під точний кінцевий розмір; під час жесту воно вже було живе)
        if root.overrideredirect():
            WindowHandler.round_corners(root, WindowHandler.CORNER_RADIUS)
