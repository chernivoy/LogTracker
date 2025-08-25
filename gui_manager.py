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
from utils import path as Path
from ui.image_manager import ImageManager
from ui.window_handler import WindowHandler


class GUIManager:

    @staticmethod
    def create_error_window(root: ctk.CTk, app, image_manager: ImageManager):

        theme_manager = app.theme_manager
        current_theme = theme_manager.current_theme_data

        # Шляхи до іконок
        header_icon_path = os.path.join("src", "Header.ico")
        bug_icon_path = os.path.join("src", "bug2.png")

        # Встановлення теми CTk
        ctk.set_appearance_mode(current_theme["ctk_appearance_mode"])
        ctk.set_default_color_theme(current_theme["default_color_theme"])

        TRANSPARENT_COLOR = "#000001"

        root.overrideredirect(True)
        root.configure(bg=TRANSPARENT_COLOR)
        root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        root.attributes('-alpha', 0.9)

        root.title("LogTracker")
        root.minsize(300, 100)

        # Завантаження та встановлення геометрії
        geometry_string = ConfigManager.load_window_size('Window', root)
        if geometry_string:
            root.geometry(geometry_string)
        else:
            root.geometry('400x200+100+100')

        header_icon = Path.PathUtils.resource_path(header_icon_path)

        app.app_icon = image_manager.get_ctk_image(path=bug_icon_path, size=(16, 16))

        if os.path.exists(header_icon):
            root.iconbitmap(header_icon)
        else:
            print(f"Error: The icon file is not found by: {header_icon}")

        root.attributes('-topmost', True)
        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))
        root.update_idletasks()
        root.update()

        WindowHandler.round_corners(root, 30)

        main_frame = ctk.CTkFrame(root, fg_color=current_theme["main_frame_fg_color"])
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        file_label = ctk.CTkLabel(
            main_frame,
            text=" LogTracker",
            anchor="w",
            text_color=current_theme["header_label_text_color"],
            font=current_theme["header_label_font"],
            image=app.app_icon,
            compound="left"
        )
        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        to_tray_button = ctk.CTkButton(
            main_frame,
            text="x",
            height=20,
            width=20,
            fg_color=current_theme["to_tray_button_fg_color"],
            text_color=current_theme["to_tray_button_text_color"],
            font=current_theme["to_tray_button_font"],
            hover_color=current_theme["to_tray_button_hover_color"],
            command=lambda: TrayManager.minimize_to_tray(root, app)
        )
        to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        burger_button = ctk.CTkButton(
            main_frame,
            text="...",
            height=20,
            width=20,
            fg_color=current_theme["burger_button_fg_color"],
            text_color=current_theme["burger_button_text_color"],
            font=current_theme["burger_button_font"],
            hover_color=current_theme["burger_button_hover_color"],
            command=lambda: GUIManager.show_context_menu(root, app, image_manager)
        )
        burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

        error_frame = ctk.CTkFrame(
            main_frame,
            fg_color=current_theme["error_frame_fg_color"],
            border_color=current_theme["error_frame_border_color"],
            border_width=current_theme["error_frame_border_width"]
        )
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame, fg_color="transparent")
        error_text_widget_frame.pack(fill="both", expand=True)

        error_text_widget = ctk.CTkTextbox(
            error_text_widget_frame,
            height=20,
            corner_radius=current_theme["error_textbox_corner_radius"],
            border_width=current_theme["error_textbox_border_width"],
            fg_color=current_theme["error_textbox_fg_color"],
            wrap="word",
            state="disabled",
            text_color=current_theme["error_textbox_text_color"],
            font=current_theme["error_textbox_font"],
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
        WindowHandler.bind_resize_events(root)
        file_label.bind("<ButtonPress-1>", lambda event: WindowHandler.start_move(event, root))
        file_label.bind("<B1-Motion>", lambda event: WindowHandler.do_move(event, root))

        # ЗБЕРІГАЄМО ВІДЖЕТИ, ЯКІ ПОТРІБНО ОНОВЛЮВАТИ, У СЛОВНИК
        # Це ключовий крок для надійної зміни теми
        widgets_to_update = {
            "main_frame": main_frame,
            "file_label": file_label,
            "to_tray_button": to_tray_button,
            "burger_button": burger_button,
            "error_frame": error_frame,
            "error_text_widget_frame": error_text_widget_frame,
            "error_text_widget": error_text_widget
        }

        return root, error_text_widget, file_label, widgets_to_update

    @staticmethod
    def update_widgets_theme(app, widgets_to_update):
        """
        Оновлює кольори та шрифти всіх віджетів відповідно до поточної теми.
        Використовує словник віджетів для прямого оновлення.
        """
        theme_data = app.theme_manager.current_theme_data

        # Встановлюємо кольорову схему CTk
        ctk.set_default_color_theme(theme_data["default_color_theme"])

        # ПРЯМЕ ОНОВЛЕННЯ СТИЛІВ ДЛЯ КОЖНОГО ВІДЖЕТА ЗІ СЛОВНИКА
        widgets_to_update["main_frame"].configure(fg_color=theme_data["main_frame_fg_color"])

        widgets_to_update["file_label"].configure(
            text_color=theme_data["header_label_text_color"],
            font=theme_data["header_label_font"]
        )

        widgets_to_update["to_tray_button"].configure(
            text_color=theme_data["to_tray_button_text_color"],
            font=theme_data["to_tray_button_font"],
            fg_color=theme_data["to_tray_button_fg_color"],
            hover_color=theme_data["to_tray_button_hover_color"]
        )

        widgets_to_update["burger_button"].configure(
            text_color=theme_data["burger_button_text_color"],
            font=theme_data["burger_button_font"],
            fg_color=theme_data["burger_button_fg_color"],
            hover_color=theme_data["burger_button_hover_color"]
        )

        widgets_to_update["error_frame"].configure(
            fg_color=theme_data["error_frame_fg_color"],
            border_color=theme_data["error_frame_border_color"],
            border_width=theme_data["error_frame_border_width"]
        )

        widgets_to_update["error_text_widget"].configure(
            fg_color=theme_data["error_textbox_fg_color"],
            text_color=theme_data["error_textbox_text_color"],
            font=theme_data["error_textbox_font"],
            border_width=theme_data["error_textbox_border_width"],
            corner_radius=theme_data["error_textbox_corner_radius"]
        )

        # Після оновлення всіх стилів викличте метод update_idletasks()
        # Це гарантує, що зміни будуть застосовані негайно
        app.root.update_idletasks()

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
    def show_context_menu(root: ctk.CTk, app, image_manager: ImageManager):
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

        settings_icon_path = os.path.join("src", "settings_icon.png")

        dark_theme_icon_path = os.path.join("src", "settings_icon.png")

        light_theme_icon_path = os.path.join("src", "settings_icon.png")

        # Важливо: зберігати посилання на PhotoImage, інакше воно буде видалено з пам'яті
        root._settings_icon_photo = image_manager.get_tk_photo_image(settings_icon_path, (12, 12))
        root._exit_icon_photo = image_manager.get_tk_photo_image(exit_icon_path, (12, 12))

        root._dark_theme_icon_photo = image_manager.get_tk_photo_image(dark_theme_icon_path,
                                                                       (12, 12))
        root._light_theme_icon_photo = image_manager.get_tk_photo_image(light_theme_icon_path,
                                                                        (12, 12))

        # Створюємо підменю "Тема"
        theme_menu = tk.Menu(context_menu, tearoff=0,
                             bg=current_theme["context_menu_bg"], fg=current_theme["context_menu_fg"],
                             activebackground=current_theme["context_menu_active_bg"],
                             activeforeground=current_theme["context_menu_active_fg"],
                             font=menu_font, borderwidth=0, relief="flat")

        # Додаємо елементи в підменю
        theme_menu.add_command(
            label="Dark",
            command=lambda: app.toggle_theme("dark"),
            image=root._dark_theme_icon_photo, compound="left"
        )

        theme_menu.add_command(
            label="Light",
            command=lambda: app.toggle_theme("light"),
            image=root._light_theme_icon_photo, compound="left"
        )

        # Додаємо підменю в головне меню
        context_menu.add_cascade(label="Theme", menu=theme_menu)
        context_menu.add_separator()

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
