import os
import tkinter as tk
import customtkinter as ctk
import ctypes

from config_manager import ConfigManager
from tray_manager import TrayManager


class GUIManager:

    @staticmethod
    def create_error_window(app):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        root = ctk.CTk()
        root.attributes('-alpha', 0.95)
        root.wm_attributes('-transparentcolor', 'grey')
        root.title("LogTracker")
        root.minsize(300, 100)
        root.iconbitmap(r'C:\ChernivoyPersonaldata\log\src\Header.ico')
        root.attributes('-topmost', True)
        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))

        ConfigManager.load_window_size('Window', root)
        GUIManager.toggle_overrideredirect(root)

        main_frame = ctk.CTkFrame(root, fg_color="#2a2d30")
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        file_label = ctk.CTkLabel(main_frame, text="LogTracker", anchor="w", text_color="#5f8dfc", font=("Inter", 13))
        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        to_tray_button = ctk.CTkButton(main_frame,
                                       text="x", height=20, width=20,
                                       fg_color="transparent",
                                       text_color="#ce885f",
                                       command=lambda: TrayManager.minimize_to_tray(root, app))
        to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        burger_button = ctk.CTkButton(main_frame,
                                      text="...", height=20, width=20,
                                      fg_color="transparent",
                                      text_color="#ce885f",
                                      command=lambda: GUIManager.show_context_menu(root, app))
        burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

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

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        GUIManager.remove_maximize_button(root)
        file_label.bind("<ButtonPress-1>", lambda event: GUIManager.start_move(event, root))
        file_label.bind("<B1-Motion>", lambda event: GUIManager.do_move(event, root))

        return root, error_text_widget, file_label

    @staticmethod
    def toggle_overrideredirect(root):
        current_state = root.overrideredirect()
        root.overrideredirect(not current_state)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        if not current_state:
            GUIManager.round_corners(root, 30)

    def round_corners(root: ctk, radius=30):
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, root.winfo_width(), root.winfo_height(), radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)

    @staticmethod
    def remove_maximize_button(root):
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        styles = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
        styles &= ~0x00020000  # WS_MINIMIZEBOX
        styles &= ~0x00010000  # WS_MAXIMIZEBOX
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, styles)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0040 | 0x0100)

    @staticmethod
    def start_move(event, root: ctk):
        root.start_x = event.x
        root.start_y = event.y

    @staticmethod
    def do_move(event, root: ctk):
        x = root.winfo_x() + event.x - root.start_x
        y = root.winfo_y() + event.y - root.start_y
        root.geometry(f"+{x}+{y}")

    @staticmethod
    def open_settings_window(app):
        settings_window = ctk.CTkToplevel(app.root)
        settings_window.title("Path settings")
        ConfigManager.load_window_size('Window_path', settings_window)
        settings_window.minsize(400, 270)
        settings_window.grab_set()

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

        settings_window.bind("<Configure>",
                             lambda event: ConfigManager.save_window_size('Window_path', settings_window))

    @staticmethod
    def save_settings(app, settings_window, source_directory, target_directory):
        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'directory', target_directory)

        from logger import config_path  # уникаємо циклічний імпорт
        with open(config_path, 'w') as configfile:
            app.config.write(configfile)

        app.source_directory = source_directory
        app.directory = target_directory

        ConfigManager.save_window_size('Window_path', settings_window)
        settings_window.destroy()

    @staticmethod
    def show_context_menu(root, app):
        context_menu = tk.Menu(root, tearoff=0, bg="#2a2d30", fg="#e2e0e6", activebackground="#2d436e")
        context_menu.add_command(label="To tray", command=lambda: TrayManager.minimize_to_tray(root, app))
        context_menu.add_command(label="Pin/Unpin", command=lambda: TrayManager.toggle_pin(root))
        context_menu.add_command(label="Window border", command=lambda: GUIManager.toggle_overrideredirect(root))
        context_menu.add_command(label="Path settings", command=lambda: GUIManager.open_settings_window(app))
        context_menu.add_command(label="Exit", command=app.on_closing)
        context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
