import customtkinter as ctk
import tkinter as tk
import platform
import os
import ctypes
from config_manager import ConfigManager
from utils.path import PathUtils

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
    def load_window_size(section, root):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            dpi_scale = dpi / 96.0
        except Exception as e:
            print(
                f"Попередження: Не вдалося отримати DPI Scale в load_window_size: {e}. Використовуємо 2.0 за замовчуванням.")
            dpi_scale = 2.0

        if section in config:
            # Зчитуємо ШИРИНУ, ВИСОТУ, X, Y з INI (всі вони тепер ЛОГІЧНІ)
            width = config.getint(section, 'width', fallback=800)
            height = config.getint(section, 'height', fallback=600)
            x = config.getint(section, 'x', fallback=100)
            y = config.getint(section, 'y', fallback=100)

            # Розміри: ділимо логічні розміри на dpi_scale для geometry()
            width_for_geometry = int(width / dpi_scale)
            height_for_geometry = int(height / dpi_scale)

            # ✅ КЛЮЧОВА ЗМІНА: Позиція X та Y: передаємо ЛОГІЧНІ значення без додаткового ділення.
            # geometry() сам скомпенсує їх з урахуванням DPI.
            x_for_geometry = x
            y_for_geometry = y

            return f'{width_for_geometry}x{height_for_geometry}+{x_for_geometry}+{y_for_geometry}'
        else:
            return None

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

        # Отримуємо логічні координати курсора відносно ВІКНА
        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        border = 20

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

        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        border = 20

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
        min_width_logical = 300
        min_height_logical = 100

        new_width_logical = root._start_width_logical
        new_height_logical = root._start_height_logical
        new_x_logical = root._start_win_x_logical
        new_y_logical = root._start_win_y_logical

        # Логіка зміни розміру та позиції (БЕЗ ЗМІН в цьому блоці)
        if "e" in dir:  # East (right)
            new_width_logical = max(root._start_width_logical + dx_logical, min_width_logical)
        if "s" in dir:  # South (bottom)
            new_height_logical = max(root._start_height_logical + dy_logical, min_height_logical)

        if "w" in dir:  # West (left)
            potential_new_width = root._start_width_logical - dx_logical
            if potential_new_width >= min_width_logical:
                new_width_logical = potential_new_width
                new_x_logical = root._start_win_x_logical + dx_logical
            else:
                new_width_logical = min_width_logical
                new_x_logical = root._start_win_x_logical + root._start_width_logical - min_width_logical

        if "n" in dir:  # North (top)
            potential_new_height = root._start_height_logical - dy_logical
            if potential_new_height >= min_height_logical:
                new_height_logical = potential_new_height
                new_y_logical = root._start_win_y_logical + dy_logical
            else:
                new_height_logical = min_height_logical
                new_y_logical = root._start_win_y_logical + root._start_height_logical - min_height_logical
        # Кінець логіки зміни розміру

        # Отримуємо поточний DPI Scale для вікна.
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        dpi_scale_for_geometry = dpi / 96.0

        # Компенсуємо ЛОГІЧНІ розміри, ділячи їх на DPI Scale, перед передачею в geometry()
        final_width_for_geometry = int(new_width_logical / dpi_scale_for_geometry)
        final_height_for_geometry = int(new_height_logical / dpi_scale_for_geometry)

        # Для позиції X та Y передаємо ЛОГІЧНІ значення без додаткового ділення.
        final_x_for_geometry = new_x_logical
        final_y_for_geometry = new_y_logical

        print(f"DO RESIZE: Dir='{dir}'")
        print(f"  Cursor (Logical/Screen): X={current_cursor_x_logical}, Y={current_cursor_y_logical}")
        print(f"  Delta (Log): dx={dx_logical:.2f}, dy={dy_logical:.2f}")
        print(
            f"  New Window (Log calculated): X={new_x_logical:.2f}, Y={new_y_logical:.2f}, W={new_width_logical:.2f}, H={new_height_logical:.2f}")
        print(
            f"  Applying (Compensated Logical to geometry): {final_width_for_geometry}x{final_height_for_geometry}+{final_x_for_geometry}+{final_y_for_geometry}")

        # Застосовуємо нові розміри та позицію
        root.geometry(
            f"{final_width_for_geometry}x{final_height_for_geometry}+{final_x_for_geometry}+{final_y_for_geometry}")

    @staticmethod
    def stop_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        WindowHandler.save_window_size('Window', root)
        root._resize_dir = None
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        print("--- STOP RESIZE LOG ---")
        print(
            f"Final Window (Log): X={root.winfo_x()}, Y={root.winfo_y()}, W={root.winfo_width()}, H={root.winfo_height()}")
        print("-----------------------")

        # Повертаємо округлення після завершення ресайзу
        if root.overrideredirect():
            WindowHandler.round_corners(root, 30)

