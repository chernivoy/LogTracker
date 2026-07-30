import ctypes
import os
import tkinter as tk

import customtkinter as ctk

from config_manager import ConfigManager
from utils.path import PathUtils
from utils import rdp

CONFIG_FILE_WINDOW = PathUtils.resource_path(os.path.join("src", "window_config.ini"))


class WindowHandler:
    """
    Відповідає за налаштування та поведінку вікна:
    зміна розміру, переміщення та округлення кутів.
    """

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

        with open(CONFIG_FILE_WINDOW, 'w') as configfile:
            config.write(configfile)

    @staticmethod
    def save_window_params_2(section, x=None, y=None, width=None, height=None):
        """
        Зберігає параметри вікна у конфіг.
        Використовує передані значення або дефолтні, без розрахунку поточних координат.
        """
        DEFAULT_PARAMS = {
            'width': '300',
            'height': '300',
            'x': '100',
            'y': '100'
        }

        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        # Словник значень, які потрібно записати
        provided_params = {
            'width': width,
            'height': height,
            'x': x,
            'y': y
        }

        for key, val in provided_params.items():
            # Якщо аргумент передано — пишемо його, інакше беремо з DEFAULT_PARAMS
            config[section][key] = str(val) if val is not None else DEFAULT_PARAMS[key]

        try:
            with open(CONFIG_FILE_WINDOW, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Помилка запису конфігурації: {e}")

    @staticmethod
    def save_window_params(section, x=None, y=None, width=None, height=None):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['x'] = str(x) if x is not None else "100"
        config[section]['y'] = str(y) if y is not None else "100"
        config[section]['width'] = str(width) if width is not None else "300"
        config[section]['height'] = str(height) if height is not None else "300"

        with open(CONFIG_FILE_WINDOW, 'w') as configfile:
            config.write(configfile)

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
    def round_corners(window, radius):
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        # Використовуємо розміри вікна напряму, без ручного масштабування
        width = window.winfo_width()
        height = window.winfo_height()

        hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
            0, 0, width, height, radius, radius
        )

        result = ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        if result == 0:
            print("[round_corners] SetWindowRgn failed")
        else:
            print("[round_corners] SetWindowRgn applied successfully")

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
        Прив'язує всі необхідні події до вікна для ресайзу та переміщення.
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

        # Окремі прив'язки для переміщення вікна (заголовок/file_label).
        try:
            file_label = root.nametowidget(".!ctkframe.!ctklabel")
            file_label.bind("<ButtonPress-1>", lambda event: WindowHandler.start_move(event, root))
            file_label.bind("<B1-Motion>", lambda event: WindowHandler.do_move(event, root))
        except KeyError:
            print(
                "Помилка: Не вдалося знайти віджет 'file_label' для прив'язки переміщення. Переміщення буде недоступне.")

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

        # Тимчасово скасовуємо округлення (щоб не обрізало кути під час ресайзу)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)

        root._resize_hwnd = hwnd     # кешуємо hwnd на весь жест (для перемальовки)
        root._resize_scale = scale  # масштаб зафіксовано на весь жест ресайзу
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

        # Мінімум у ФІЗИЧНИХ пікселях, узгоджений з root.minsize(300, 100):
        # CTk застосовує до minsize той самий масштаб, тож OS-мінімум теж
        # 300x100 * scale. Якби тут мінімум лишався 300x100 фізичних, при
        # ресайзі з заходу/півночі на межі OS клампив би ширину, а x усе одно
        # зсувався б — вікно «повзло» б убік. Тепер межі збігаються.
        min_width = int(300 * scale)
        min_height = int(100 * scale)

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

        # Застосовуємо нові розміри та позицію
        root.geometry(
            f"{final_width_for_geometry}x{final_height_for_geometry}+{int(new_x_logical)}+{int(new_y_logical)}")

        # Спершу застосовуємо відкладений re-layout (пересунути HWND кнопок до
        # нового правого краю), потім ФОРСУЄМО синхронну перемальовку дітей.
        #
        # Чому це потрібно: кнопки праворуч угорі закріплені за правим краєм
        # (sticky "ne", колонка з weight 0), тож при ресайзі змінюється лише
        # їхня ПОЗИЦІЯ, а не розмір. CTk перемальовує віджет тільки на зміні
        # РОЗМІРУ (`_update_dimensions_event`), тож пересунуті кнопки не
        # перемальовуються — на шаруватому вікні вони зникають/стрибають до
        # наступної повної перемальовки (аж на stop_resize). `update_idletasks`
        # не рятує: він не обробляє `WM_PAINT`. Тому явно кличемо
        # RedrawWindow(...UPDATENOW) — синхронний WM_PAINT усім дочірнім HWND.
        root.update_idletasks()
        hwnd = getattr(root, "_resize_hwnd", None)
        if hwnd:
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
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        # Повертаємо округлення після завершення ресайзу
        if root.overrideredirect():
            WindowHandler.round_corners(root, 30)
