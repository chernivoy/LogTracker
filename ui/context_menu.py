# Файл: ui/context_menu.py

import tkinter as tk
import tkinter.font as tkFont

from ui.settings_window import SettingsWindow
from ui.ui_assets import (
    EXIT_ICON_PATH, SETTINGS_ICON_PATH, THEME_ICON_PATH,
    DARK_THEME_ICON_PATH, LIGHT_THEME_ICON_PATH, CUSTOM_THEME_ICON_PATH
)
from utils import rdp


class ContextMenu:
    def __init__(self, root, app, image_manager):
        self.root = root
        self.app = app
        self.image_manager = image_manager
        self.menu = None
        self._icons = {}
        self._has_icons = False

    def show_menu(self, button):
        print("INFO: Attempting to show context menu.")

        theme_manager = self.app.theme_manager
        current_theme = theme_manager.current_theme_data

        base_font_size = 6
        dpi_scale_factor = rdp.get_windows_dpi_scale(self.root)
        print(f"INFO: DPI scale factor detected: {dpi_scale_factor}")
        scaled_font_size = int(base_font_size * dpi_scale_factor)
        print(f"INFO: Scaled font size for menu: {scaled_font_size}")
        menu_font = tkFont.Font(family="Inter", size=scaled_font_size)

        self._load_icons()

        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=current_theme["context_menu_bg"],
            fg=current_theme["context_menu_fg"],
            activebackground=current_theme["context_menu_active_bg"],
            activeforeground=current_theme["context_menu_active_fg"],
            font=menu_font,
            borderwidth=0,
            relief="flat"
        )

        self._populate_menu()

        x = int(button.winfo_rootx() + int(button.winfo_width()) / 2)
        y = button.winfo_rooty() + button.winfo_width()

        try:
            print(f"INFO: Displaying menu at coordinates: ({x}, {y})")
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _populate_menu(self):
        # Логіка наповнення меню, яка використовує self._icons.
        # Перевіряємо саме _has_icons, а не truthiness self._icons: get_tk_photo_image
        # повертає None на відсутній файл, тож словник міг бути непорожнім, але з
        # None-значеннями — і гілка «з іконками» ставила image=None замість фолбеку.
        if self._has_icons:
            # Створення підменю Theme
            theme_menu = tk.Menu(self.menu, tearoff=0,
                                 bg=self.menu['bg'], fg=self.menu['fg'],
                                 activebackground=self.menu['activebackground'],
                                 activeforeground=self.menu['activeforeground'],
                                 font=self.menu['font'], borderwidth=0, relief="flat")

            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"),
                                   image=self._icons['dark_theme'], compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"),
                                   image=self._icons['light_theme'], compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"),
                                   image=self._icons['custom_theme'], compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="ADAICA Light", command=lambda: self.app.toggle_theme("adaica_light"),
                                   image=self._icons['custom_theme'], compound="left")
            print("INFO: Icons loaded and added to theme menu.")

            self.menu.add_cascade(label="Theme", menu=theme_menu, image=self._icons['theme'], compound="left")
            self.menu.add_separator()
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app),
                                  image=self._icons['settings'], compound="left")
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing, image=self._icons['exit'], compound="left")
        else:
            print("WARNING: Icons could not be loaded, using text labels only.")
            theme_menu = tk.Menu(self.menu, tearoff=0,
                                 bg=self.menu['bg'], fg=self.menu['fg'],
                                 activebackground=self.menu['activebackground'],
                                 activeforeground=self.menu['activeforeground'],
                                 font=self.menu['font'], borderwidth=0, relief="flat")
            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"))
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"))
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"))
            theme_menu.add_command(label="ADAICA Light", command=lambda: self.app.toggle_theme("adaica_light"))
            self.menu.add_cascade(label="Theme", menu=theme_menu)
            self.menu.add_separator()
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app))
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing)

    def _load_icons(self):
        base_icon_size = (16, 16)
        icon_paths = {
            'settings': SETTINGS_ICON_PATH,
            'exit': EXIT_ICON_PATH,
            'theme': THEME_ICON_PATH,
            'dark_theme': DARK_THEME_ICON_PATH,
            'light_theme': LIGHT_THEME_ICON_PATH,
            'custom_theme': CUSTOM_THEME_ICON_PATH,
        }
        print(f"INFO: Loading icons with base size: {base_icon_size}")

        self._icons = {}
        try:
            # Примусово створюємо нові іконки, не використовуючи кеш
            for name, path in icon_paths.items():
                self._icons[name] = self.image_manager.get_tk_photo_image(
                    path, base_icon_size, force_reload=True)
        except Exception as e:
            print(f"Error when loading icons: {e}")

        # get_tk_photo_image повертає None на відсутній файл (не кидає виняток),
        # тож меню з іконками показуємо лише коли завантажились УСІ. Часткова
        # невдача → чистимо словник і йдемо на текстовий фолбек у _populate_menu.
        self._has_icons = bool(self._icons) and all(
            img is not None for img in self._icons.values())
        if self._has_icons:
            print("INFO: Icons loaded successfully.")
        else:
            self._icons = {}
            print("WARNING: not all menu icons loaded, falling back to text labels.")
