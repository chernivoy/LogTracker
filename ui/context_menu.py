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
        self._load_icons()

    def show_menu(self, button):

        theme_manager = self.app.theme_manager
        current_theme = theme_manager.current_theme_data

        base_font_size = 10
        dpi_scale_factor = rdp.get_windows_dpi_scale(self.root)
        scaled_font_size = int(base_font_size * dpi_scale_factor)
        menu_font = tkFont.Font(family="Inter", size=scaled_font_size)

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

        self._load_icons()

        theme_menu = tk.Menu(
            self.menu, tearoff=0,
            bg=current_theme["context_menu_bg"], fg=current_theme["context_menu_fg"],
            activebackground=current_theme["context_menu_active_bg"],
            activeforeground=current_theme["context_menu_active_fg"],
            font=menu_font, borderwidth=0, relief="flat"
        )

        if self._has_icons:
            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"),
                                   image=self._dark_theme_icon, compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"),
                                   image=self._light_theme_icon, compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"),
                                   image=self._custom_theme_icon, compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="ADAICA Light", command=lambda: self.app.toggle_theme("adaica_light"),
                                   image=self._custom_theme_icon, compound="left")

        else:
            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"))
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"))
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"))
            theme_menu.add_command(label="ADAICA Light", command=lambda: self.app.toggle_theme("adaica_light"))

        if self._has_icons:
            self.menu.add_cascade(label="Theme", menu=theme_menu, image=self._theme_icon, compound="left")
        else:
            self.menu.add_cascade(label="Theme", menu=theme_menu)

        self.menu.add_separator()

        if self._has_icons:
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app),
                                  image=self._settings_icon, compound="left")
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing, image=self._exit_icon, compound="left")
        else:
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app))
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing)

        x = int(button.winfo_rootx() + int(button.winfo_width()) / 2)
        y = button.winfo_rooty() + button.winfo_width()

        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _load_icons(self):
        try:
            base_icon_size = (16, 16)

            self._settings_icon = self.image_manager.get_tk_photo_image(SETTINGS_ICON_PATH, base_icon_size)
            self._exit_icon = self.image_manager.get_tk_photo_image(EXIT_ICON_PATH, base_icon_size)
            self._theme_icon = self.image_manager.get_tk_photo_image(THEME_ICON_PATH, base_icon_size)
            self._dark_theme_icon = self.image_manager.get_tk_photo_image(DARK_THEME_ICON_PATH, base_icon_size)
            self._light_theme_icon = self.image_manager.get_tk_photo_image(LIGHT_THEME_ICON_PATH, base_icon_size)
            self._custom_theme_icon = self.image_manager.get_tk_photo_image(CUSTOM_THEME_ICON_PATH, base_icon_size)

            self._has_icons = True
        except Exception as e:
            print(f"Error when loading icons: {e}")
            self._has_icons = False
