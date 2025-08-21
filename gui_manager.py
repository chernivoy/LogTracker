import os
import sys
import tkinter as tk
from tkinter import font as tkFont
import customtkinter as ctk
import ctypes
from PIL import Image, ImageTk

from config_manager import ConfigManager
from tray_manager import TrayManager
from utils import rdp


class GUIManager:
    RESIZE_BORDER_WIDTH = 20

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    @staticmethod
    def load_ctk_image(path: str, size: tuple) -> ctk.CTkImage | None:
        """
        Завантажує зображення з файлу і створює об'єкт CTkImage.
        Повертає CTkImage, або None, якщо файл не знайдено.
        """
        # Використовуємо допоміжну функцію для визначення правильного шляху
        full_path = GUIManager.resource_path(path)

        try:
            image = Image.open(full_path)
            ctk_image = ctk.CTkImage(light_image=image,
                                     dark_image=image,
                                     size=size)
            return ctk_image
        except FileNotFoundError:
            print(f"Помилка: Файл іконки не знайдено за шляхом: {full_path}")
            return None

    @staticmethod
    def load_tk_photo_image(path: str, base_size: tuple, dpi_scale_factor: float) -> tk.PhotoImage | None:
        """
        Завантажує зображення, масштабує його відповідно до DPI
        і повертає об'єкт tk.PhotoImage для використання в нативних Tkinter віджетах (наприклад, Menu).
        """
        full_path = GUIManager.resource_path(path)
        try:
            pil_image = Image.open(full_path)
            scaled_width = int(base_size[0] * dpi_scale_factor)
            scaled_height = int(base_size[1] * dpi_scale_factor)

            # Перевірка, щоб розміри не були нульовими або від'ємними
            if scaled_width <= 0: scaled_width = 1
            if scaled_height <= 0: scaled_height = 1

            resized_image = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)
            tk_photo = ImageTk.PhotoImage(resized_image)
            return tk_photo
        except FileNotFoundError:
            print(f"Помилка: Файл іконки Tkinter PhotoImage не знайдено за шляхом: {full_path}")
            return None
        except Exception as e:
            print(f"Помилка завантаження tk.PhotoImage з {full_path}: {e}")
            return None

    @staticmethod
    def create_error_window(app):

        header_icon_path = os.path.join("src", "Header.ico")
        bug_icon_path = os.path.join("src", "bug2.png")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        # TRANSPARENT_COLOR = "#FF00FF"
        # TRANSPARENT_COLOR = "white"
        TRANSPARENT_COLOR = "#000001"

        root = ctk.CTk()
        root.overrideredirect(True)  # УВАГА: ДО geometry
        root.configure(bg=TRANSPARENT_COLOR)
        root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        root.attributes('-alpha', 0.9)  # повністю непрозорий

        root.title("LogTracker")
        root.minsize(300, 100)

        # Завантаження геометрії ДО .update()
        geometry_string = ConfigManager.load_window_size('Window', root)
        if geometry_string:
            root.geometry(geometry_string)
        else:
            root.geometry('400x200+100+100')

        header_icon = GUIManager.resource_path(header_icon_path)

        app_icon = GUIManager.load_ctk_image(path=bug_icon_path, size=(16, 16))

        if os.path.exists(header_icon):
            root.iconbitmap(header_icon)
        else:
            print(f"Error: The icon file is not found by: {header_icon}")

        root.attributes('-topmost', True)

        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))

        root.update_idletasks()
        root.update()

        # Після повного оновлення - округлення
        GUIManager.round_corners(root, 30)

        # Основна рамка
        # main_frame = ctk.CTkFrame(root, fg_color="#2a2d30", corner_radius=30) #383b40
        main_frame = ctk.CTkFrame(root, fg_color="#383b40")
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        # Заголовок
        # file_label = ctk.CTkLabel(main_frame, text="LogTracker", anchor="w",
        #                           text_color="#5f8dfc", font=("Inter", 13))
        file_label = ctk.CTkLabel(main_frame, text=" LogTracker", anchor="w",
                                  text_color="#5f8dfc", font=("Inter", 13),
                                  image=app_icon,
                                  # Додаємо об'єкт іконки
                                  compound="left")

        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        to_tray_button = ctk.CTkButton(main_frame, text="x", height=20, width=20,
                                       fg_color="transparent", text_color="#ce885f",
                                       command=lambda: TrayManager.minimize_to_tray(root, app))
        to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        burger_button = ctk.CTkButton(main_frame, text="...", height=20, width=20,
                                      fg_color="transparent", text_color="#ce885f",
                                      command=lambda: GUIManager.show_context_menu(root, app))
        burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

        # Поле логів
        error_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame, fg_color="transparent")
        error_text_widget_frame.pack(fill="both", expand=True)

        error_text_widget = ctk.CTkTextbox(
            error_text_widget_frame,
            height=20,
            corner_radius=1,
            border_width=0,
            fg_color="transparent",
            wrap="word",
            state="disabled",
            text_color="#b4b361",
            font=("Inter", 13),
            yscrollcommand=lambda *args: None
        )
        error_text_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Grid конфігурація
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Resize + переміщення
        GUIManager.bind_resize_events(root)
        file_label.bind("<ButtonPress-1>", lambda event: GUIManager.start_move(event, root))
        file_label.bind("<B1-Motion>", lambda event: GUIManager.do_move(event, root))

        return root, error_text_widget, file_label

    @staticmethod
    def toggle_overrideredirect(root: ctk.CTk):
        current_state = root.overrideredirect()
        root.overrideredirect(not current_state)


        if not current_state:
            root.update_idletasks()  # Забезпечуємо оновлення внутрішніх віджетів
            root.update()  # Примусово перемальовуємо вікно
        else:  # Якщо повертаємо рамку, скидаємо регіон вікна
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)

    @staticmethod
    def update_widgets_theme(app):
        """
        Оновлює кольори всіх віджетів відповідно до поточної теми.
        Це потрібно викликати після зміни теми.
        """
        root = app.root
        theme_data = app.theme_manager.current_theme_data

        # Оновлення кольорів для всіх віджетів
        for widget in root.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget.winfo_name() == "!ctkframe":
                widget.configure(fg_color=theme_data["main_frame_fg_color"])

            for child in widget.winfo_children():
                # Оновлення CTkLabel
                if isinstance(child, ctk.CTkLabel):
                    child.configure(text_color=theme_data["header_label_text_color"])
                # Оновлення CTkButton
                elif isinstance(child, ctk.CTkButton):
                    child.configure(text_color=theme_data["button_text_color"])
                # Оновлення CTkTextbox
                elif isinstance(child, ctk.CTkTextbox):
                    child.configure(text_color=theme_data["error_text_color"])

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
            print("[round_corners] ⚠️ SetWindowRgn failed")
        else:
            print("[round_corners] ✅ SetWindowRgn applied successfully")

    @staticmethod
    def remove_maximize_button(root: ctk.CTk):
        """
        Видаляє кнопки мінімізації та максимізації з системного меню вікна.
        (Актуально, якщо overrideredirect(False))
        """
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        styles = ctypes.windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
        styles &= ~0x00020000  # WS_MINIMIZEBOX
        styles &= ~0x00010000  # WS_MAXIMIZEBOX
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, styles)
        # Оновлюємо вікно, щоб зміни набули чинності
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                          0x0040 | 0x0100)  # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER

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
    def open_settings_window(app):
        """
        Відкриває вікно налаштувань для шляхів.
        """
        settings_window = ctk.CTkToplevel(app.root)
        settings_window.title("Path settings")

        # Завантаження та застосування геометрії для підвікна
        geometry_string = ConfigManager.load_window_size('Window_path', settings_window)
        if geometry_string:
            settings_window.geometry(geometry_string)
        else:
            settings_window.geometry('400x270+668+661')  # Дефолтні розміри та позиція

        settings_window.minsize(400, 270)
        settings_window.grab_set()  # Заблокувати інші вікна до закриття цього

        # Віджети для налаштувань шляхів
        label_source_directory = ctk.CTkLabel(settings_window, text="Path to source directory:")
        label_source_directory.pack(pady=10)

        entry_source_directory = ctk.CTkEntry(settings_window, width=300)
        entry_source_directory.insert(0, app.source_directory)
        entry_source_directory.pack(pady=5)

        label_target_directory = ctk.CTkLabel(settings_window, text="Path to destination directory:")
        label_target_directory.pack(pady=10)

        entry_target_directory = ctk.CTkEntry(settings_window, width=300)
        entry_target_directory.insert(0, app.directory)
        entry_target_directory.pack(pady=5)

        # Кнопки збереження та відміни
        btn_save = ctk.CTkButton(
            settings_window,
            text="Save",
            command=lambda: GUIManager.save_settings(
                app,
                settings_window,
                entry_source_directory.get(),
                entry_target_directory.get()
            )
        )
        btn_save.pack(pady=10)

        btn_cancel = ctk.CTkButton(
            settings_window,
            text="Cancel",
            command=settings_window.destroy
        )
        btn_cancel.pack(pady=5)

        # Зберігання позиції вікна налаштувань при його зміні
        settings_window.bind("<Configure>",
                             lambda event: ConfigManager.save_window_size('Window_path', settings_window))

    @staticmethod
    def save_settings(app, settings_window, source_directory, target_directory):
        """
        Зберігає налаштування шляхів та закриває вікно налаштувань.
        """
        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'directory', target_directory)

        # Уникаємо циклічного імпорту, імпортуючи config_path тут
        from logger import config_path
        with open(config_path, 'w') as configfile:
            app.config.write(configfile)

        app.source_directory = source_directory
        app.directory = target_directory

        ConfigManager.save_window_size('Window_path', settings_window)
        settings_window.destroy()

    @staticmethod
    def show_context_menu(root: ctk.CTk, app):
        """
        Відображає контекстне меню для вікна.
        """
        theme_manager = app.theme_manager
        current_theme = theme_manager.current_theme_data

        base_font_size = 10
        dpi_scale_factor = rdp.get_windows_dpi_scale(root)
        scaled_font_size = int(base_font_size * dpi_scale_factor)
        menu_font = tkFont.Font(family="Inter", size=scaled_font_size)

        if hasattr(root, '_context_menu'):
            root._context_menu.delete(0, 'end')

            root._context_menu.configure(
                bg=current_theme["context_menu_bg"],
                fg=current_theme["context_menu_fg"],
                activebackground=current_theme["context_menu_active_bg"],
                activeforeground=current_theme["context_menu_active_fg"]
            )
        else:
            root._context_menu = tk.Menu(
                root,
                tearoff=0,
                bg=current_theme["context_menu_bg"],
                fg=current_theme["context_menu_fg"],
                activebackground=current_theme["context_menu_active_bg"],
                activeforeground=current_theme["context_menu_active_fg"],
                font=menu_font,
                borderwidth=0,
                relief="flat"
            )

        context_menu = root._context_menu

        exit_icon_path = os.path.join("src", "exit_icon.png")
        exit_icon_base_size = (12, 12)

        settings_icon_path = os.path.join("src", "settings_icon.png")
        settings_icon_base_size = (12, 12)

        dark_theme_icon_path = os.path.join("src", "settings_icon.png")
        settings_dark_icon_base_size = (12, 12)

        light_theme_icon_path = os.path.join("src", "settings_icon.png")
        settings_light_icon_base_size = (12, 12)

        # Важливо: зберігати посилання на PhotoImage, інакше воно буде видалено з пам'яті
        root._settings_icon_photo = GUIManager.load_tk_photo_image(settings_icon_path, settings_icon_base_size,
                                                                   dpi_scale_factor)
        root._exit_icon_photo = GUIManager.load_tk_photo_image(exit_icon_path, exit_icon_base_size, dpi_scale_factor)
        root._dark_theme_icon_photo = GUIManager.load_tk_photo_image(dark_theme_icon_path, settings_dark_icon_base_size,
                                                                     dpi_scale_factor)
        root._light_theme_icon_photo = GUIManager.load_tk_photo_image(light_theme_icon_path,
                                                                      settings_light_icon_base_size, dpi_scale_factor)

        # Створюємо підменю "Тема"
        theme_menu = tk.Menu(context_menu, tearoff=0,
                             bg=current_theme["context_menu_bg"], fg=current_theme["context_menu_fg"],
                             activebackground=current_theme["context_menu_active_bg"],
                             activeforeground=current_theme["context_menu_active_fg"],
                             font=menu_font, borderwidth=0, relief="flat")

        # Додаємо елементи в підменю
        theme_menu.add_command(
            label="Темна",
            command=lambda: app.toggle_theme("dark"),
            image=root._dark_theme_icon_photo, compound="left"
        )
        theme_menu.add_command(
            label="Світла",
            command=lambda: app.toggle_theme("light"),
            image=root._light_theme_icon_photo, compound="left"
        )

        # Додаємо підменю в головне меню
        context_menu.add_cascade(label="Тема", menu=theme_menu)
        context_menu.add_separator()
        # context_menu.add_command(label="To tray", command=lambda: TrayManager.minimize_to_tray(root, app))
        # context_menu.add_command(label="Pin/Unpin", command=lambda: TrayManager.toggle_pin(root))
        # context_menu.add_command(label="Window border", command=lambda: GUIManager.toggle_overrideredirect(root))
        # context_menu.add_command(label="Path settings", command=lambda: GUIManager.open_settings_window(app))
        # context_menu.add_command(label="Exit", command=app.on_closing)

        if root._exit_icon_photo and root._settings_icon_photo:
            context_menu.add_command(label="Path settings", command=lambda: GUIManager.open_settings_window(app),
                                     image=root._settings_icon_photo, compound="left")
            context_menu.add_separator()
            context_menu.add_command(label="Exit", command=app.on_closing,
                                     image=root._exit_icon_photo, compound="left")

        else:
            context_menu.add_command(label="Path settings", command=lambda: GUIManager.open_settings_window(app))
            context_menu.add_separator()
            context_menu.add_command(label="Exit", command=app.on_closing)  # Без іконки, якщо не завантажилась
            # Без іконки, якщо не завантажилась
        context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())

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
        border = GUIManager.RESIZE_BORDER_WIDTH

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

    # @staticmethod м1
    # def start_resize(event: tk.Event):
    #     root = event.widget.winfo_toplevel()
    #     if not hasattr(root, "_resize_dir") or not root._resize_dir:
    #         return
    #     if not root.overrideredirect():
    #         return
    #
    #     # Тимчасово скасовуємо округлення (щоб не обрізало кути під час ресайзу)
    #     hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    #     ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)
    #
    #     root._start_cursor_x_logical = event.x_root
    #     root._start_cursor_y_logical = event.y_root
    #     root._start_width_logical = root.winfo_width()
    #     root._start_height_logical = root.winfo_height()
    #     root._start_win_x_logical = root.winfo_x()
    #     root._start_win_y_logical = root.winfo_y()
    #
    #     print("--- START RESIZE LOG ---")
    #     print(f"Timestamp: {ctypes.windll.kernel32.GetTickCount64()}")
    #     print(f"Initial Cursor (Logical/Screen): X={root._start_cursor_x_logical}, Y={root._start_cursor_y_logical}")
    #     print(
    #         f"Initial Window (Log): X={root._start_win_x_logical}, Y={root._start_win_y_logical}, W={root._start_width_logical}, H={root._start_height_logical}")
    #     print("------------------------")

    @staticmethod
    def start_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        # --- НОВА ЛОГІКА ДЛЯ ФІКСАЦІЇ НАПРЯМКУ ---
        x_logical = event.x_root - root.winfo_rootx()
        y_logical = event.y_root - root.winfo_rooty()
        width_logical = root.winfo_width()
        height_logical = root.winfo_height()
        border = GUIManager.RESIZE_BORDER_WIDTH

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

        # Оновлюємо округлені кути, якщо вікно без рамки
        # if root.overrideredirect():
        # GUIManager.round_corners(root, 28)

    @staticmethod
    def stop_resize(event: tk.Event):
        root = event.widget.winfo_toplevel()

        ConfigManager.save_window_size('Window', root)
        root._resize_dir = None
        root.configure(cursor="")  # Повертаємо курсор до стандартного вигляду

        print("--- STOP RESIZE LOG ---")
        print(
            f"Final Window (Log): X={root.winfo_x()}, Y={root.winfo_y()}, W={root.winfo_width()}, H={root.winfo_height()}")
        print("-----------------------")

        # Повертаємо округлення після завершення ресайзу
        if root.overrideredirect():
            GUIManager.round_corners(root, 30)

    @staticmethod
    def bind_resize_events(root: ctk.CTk):
        """
        Прив'язує всі необхідні події до вікна для ресайзу та переміщення.
        """
        # Події для ресайзу (зміна розміру вікна)
        resize_handlers = [
            ("<Motion>", GUIManager.change_cursor),  # Зміна курсора при наведенні на край
            ("<ButtonPress-1>", GUIManager.start_resize),  # Початок ресайзу
            ("<B1-Motion>", GUIManager.do_resize),  # Виконання ресайзу
            ("<ButtonRelease-1>", GUIManager.stop_resize),  # Завершення ресайзу
        ]

        # Прив'язуємо події ресайзу безпосередньо до кореневого вікна.
        for event_type, handler_func in resize_handlers:
            root.bind(event_type, handler_func)

        # Окремі прив'язки для переміщення вікна (заголовок/file_label).
        try:
            file_label = root.nametowidget(".!ctkframe.!ctklabel")
            file_label.bind("<ButtonPress-1>", lambda event: GUIManager.start_move(event, root))
            file_label.bind("<B1-Motion>", lambda event: GUIManager.do_move(event, root))
        except KeyError:
            print(
                "Помилка: Не вдалося знайти віджет 'file_label' для прив'язки переміщення. Переміщення буде недоступне.")
