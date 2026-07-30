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
        width = root.winfo_width()
        height = root.winfo_height()
        x = root.winfo_x()
        y = root.winfo_y()

        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['width'] = str(width)
        config[section]['height'] = str(height)
        config[section]['x'] = str(x)  # Зберігаємо ЛОГІЧНІ X
        config[section]['y'] = str(y)  # Зберігаємо ЛОГІЧНІ Y

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
    def load_window_size(section, root):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            return None

        dpi_scale = WindowHandler._window_scale(root)

        # У INI лежать ФІЗИЧНІ пікселі (winfo_*). Ширину/висоту ділимо на
        # масштаб CTk — усередині CTk.geometry() їх множить назад, тож у Win32
        # доходить рівно збережений фізичний розмір. X/Y CTk не масштабує,
        # вони передаються як фізичні координати без ділення.
        width = config.getint(section, 'width', fallback=800)
        height = config.getint(section, 'height', fallback=600)
        x = config.getint(section, 'x', fallback=100)
        y = config.getint(section, 'y', fallback=100)

        # Захист від зниклого вікна: якщо збережена позиція поза екраном
        # (типово після реконекту RDP з іншою роздільною здатністю чи
        # розкладкою моніторів) — повертаємо її у видиму область.
        x, y = rdp.clamp_to_visible(x, y, width, height)

        width_for_geometry = int(width / dpi_scale)
        height_for_geometry = int(height / dpi_scale)

        return f'{width_for_geometry}x{height_for_geometry}+{x}+{y}'

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

        # Над кнопками (згорнути/бургер) у куті не показуємо resize-курсор:
        # зона краю масштабується за DPI і перекриває їх, а клік має лишатись
        # кліком, а не ресайзом. Шлях Tk-віджета кнопки містить "ctkbutton".
        if "ctkbutton" in str(event.widget):
            root.configure(cursor="")
            root._resize_dir = None
            return

        # Координати курсора відносно ВІКНА (у фізичних пікселях, як і winfo_*).
        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        # Зона краю ~20 логічних px: множимо на масштаб, інакше при DPI 200%
        # смуга захоплення була б лише ~10 фізичних px — важко влучити,
        # надто трекпадом через RDP. _window_scale читає кеш CTk, без Win32.
        border = int(20 * WindowHandler._window_scale(root))

        cursor = ""
        root._resize_dir = None  # Скидаємо напрямок ресайзу

        # Визначаємо, в якій зоні знаходиться курсор, щоб змінити його вигляд
        if x_logical <= border and y_logical <= border:
            cursor = "sizing northwest"
            root._resize_dir = "nw"
        elif x_logical >= width_logical - border and y_logical <= border:
            cursor = "sizing northeast"
            root._resize_dir = "ne"
        elif x_logical <= border and y_logical >= height_logical - border:
            cursor = "sizing southwest"
            root._resize_dir = "sw"
        elif x_logical >= width_logical - border and y_logical >= height_logical - border:
            cursor = "sizing southeast"
            root._resize_dir = "se"
        elif x_logical <= border:
            cursor = "sizing west"
            root._resize_dir = "w"
        elif x_logical >= width_logical - border:
            cursor = "sizing east"
            root._resize_dir = "e"
        elif y_logical <= border:
            cursor = "sizing north"
            root._resize_dir = "n"
        elif y_logical >= height_logical - border:
            cursor = "sizing south"
            root._resize_dir = "s"

        root.configure(cursor=cursor or "")

    @staticmethod
    def start_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        # Клік по кнопці в куті — це клік, а не початок ресайзу (зона краю
        # масштабується за DPI і перекриває кнопки). Не чіпаємо _resize_dir і
        # регіон заокруглення, щоб кнопка спрацювала чисто.
        if "ctkbutton" in str(event.widget):
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
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        # Повертаємо округлення після завершення ресайзу
        if root.overrideredirect():
            WindowHandler.round_corners(root, 30)
