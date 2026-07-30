# Файл: ui/context_menu.py

import tkinter as tk
import tkinter.font as tkFont

from ui.settings_window import SettingsWindow
from ui.ui_assets import (
    EXIT_ICON_PATH, SETTINGS_ICON_PATH, THEME_ICON_PATH,
    DARK_THEME_ICON_PATH, LIGHT_THEME_ICON_PATH, CUSTOM_THEME_ICON_PATH
)
from ui.window_handler import WindowHandler


class ContextMenu:
    def __init__(self, root, app, image_manager):
        self.root = root
        self.app = app
        self.image_manager = image_manager
        self.menu = None
        self._icons = {}
        self._has_icons = False

    def show_menu(self, button):
        current_theme = self.app.theme_manager.current_theme_data

        # DPI: беремо той самий канонічний масштаб, що й решта застосунку —
        # кешоване _get_window_scaling() CTk через WindowHandler._window_scale, а
        # не сирий rdp.get_windows_dpi_scale. Нативний tk.Menu сам за DPI не
        # масштабується (Tk не бачить per-monitor DPI при awareness V2), тож
        # базовий кегль множимо вручну — узгоджено з масштабом вікна.
        scale = WindowHandler._window_scale(self.root)
        menu_font = tkFont.Font(family="Inter", size=max(1, int(6 * scale)))

        self._load_icons()

        # Кольори меню беремо з теми (context_menu_*). Фон навмисно збігається з
        # фоном вікна теми (main_frame_fg_color) — див. значення в themes/*.
        menu_colors = {
            "bg": current_theme["context_menu_bg"],
            "fg": current_theme["context_menu_fg"],
            "activebackground": current_theme["context_menu_active_bg"],
            "activeforeground": current_theme["context_menu_active_fg"],
        }
        self.menu = tk.Menu(self.root, tearoff=0, font=menu_font,
                            borderwidth=0, relief="flat", **menu_colors)

        self._populate_menu(menu_font, menu_colors)

        # Позиція під кнопкою. winfo_* — фізичні пікселі (при DPI-awareness), саме
        # їх чекає tk_popup; якщо меню не влазить у екран — Tk сам підправить.
        x = button.winfo_rootx() + button.winfo_width() // 2
        y = button.winfo_rooty() + button.winfo_height()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _populate_menu(self, menu_font, menu_colors):
        # Одна побудова замість двох гілок: коли всіх іконок нема
        # (_has_icons=False), _img повертає порожній dict і пункти будуються лише
        # з текстом. get_tk_photo_image повертає None на відсутній файл, тож без
        # цієї перевірки в меню потрапив би image=None замість текстового фолбеку.
        icons = self._icons if self._has_icons else {}

        def _img(key):
            return {"image": icons[key], "compound": "left"} if icons else {}

        theme_menu = tk.Menu(self.menu, tearoff=0, font=menu_font,
                             borderwidth=0, relief="flat", **menu_colors)
        theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"), **_img("dark_theme"))
        theme_menu.add_separator()
        theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"), **_img("light_theme"))
        theme_menu.add_separator()
        theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"), **_img("custom_theme"))
        theme_menu.add_separator()
        theme_menu.add_command(label="ADAICA Light", command=lambda: self.app.toggle_theme("adaica_light"),
                               **_img("light_theme"))

        self.menu.add_cascade(label="Theme", menu=theme_menu, **_img("theme"))
        self.menu.add_separator()
        self.menu.add_command(label="Path settings",
                              command=lambda: SettingsWindow.open_settings_window(self.app), **_img("settings"))
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.app.on_closing, **_img("exit"))

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

        self._icons = {}
        try:
            # Кеш ImageManager (за шляхом+розміром+DPI) переживає повторні
            # відкриття меню, тож force_reload не потрібен — PNG читається один раз.
            for name, path in icon_paths.items():
                self._icons[name] = self.image_manager.get_tk_photo_image(
                    path, base_icon_size)
        except Exception as e:
            print(f"Error when loading menu icons: {e}")

        # get_tk_photo_image повертає None на відсутній файл (не кидає виняток),
        # тож меню з іконками показуємо лише коли завантажились УСІ. Часткова
        # невдача → чистимо словник і йдемо на текстовий фолбек у _populate_menu.
        self._has_icons = bool(self._icons) and all(
            img is not None for img in self._icons.values())
        if not self._has_icons:
            self._icons = {}
            print("WARNING: not all menu icons loaded, falling back to text labels.")
