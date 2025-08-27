# Файл: ui/context_menu.py

import tkinter as tk
import tkinter.font as tkFont
import customtkinter as ctk

from ui.ui_assets import (
    EXIT_ICON_PATH, BUG_ICON_PATH, SETTINGS_ICON_PATH, THEME_ICON_PATH,
    DARK_THEME_ICON_PATH, LIGHT_THEME_ICON_PATH, CUSTOM_THEME_ICON_PATH
)
from utils import rdp
from ui.settings_window import SettingsWindow


class ContextMenu:
    def __init__(self, root, app, image_manager):
        """
        Ініціалізує контекстне меню та завантажує іконки.
        """
        self.root = root
        self.app = app
        self.image_manager = image_manager
        self.menu = None
        self._load_icons()

    def _load_icons(self):
        """
        Завантажує іконки меню та зберігає їх у класі.
        """
        try:
            self._settings_icon = self.image_manager.get_tk_photo_image(SETTINGS_ICON_PATH, (16, 16))
            self._exit_icon = self.image_manager.get_tk_photo_image(EXIT_ICON_PATH, (16, 16))
            self._theme_icon = self.image_manager.get_tk_photo_image(THEME_ICON_PATH, (16, 16))
            self._dark_theme_icon = self.image_manager.get_tk_photo_image(DARK_THEME_ICON_PATH, (16, 16))
            self._light_theme_icon = self.image_manager.get_tk_photo_image(LIGHT_THEME_ICON_PATH, (16, 16))
            self._custom_theme_icon = self.image_manager.get_tk_photo_image(CUSTOM_THEME_ICON_PATH, (16, 16))
            self._has_icons = True
        except Exception as e:
            print(f"Error loading menu icons: {e}")
            self._has_icons = False

    def show_menu(self, button):
        """
        Відображає контекстне меню.
        """
        theme_manager = self.app.theme_manager
        current_theme = theme_manager.current_theme_data

        base_font_size = 10
        dpi_scale_factor = rdp.get_windows_dpi_scale(self.root)
        scaled_font_size = int(base_font_size * dpi_scale_factor)
        menu_font = tkFont.Font(family="Inter", size=scaled_font_size)

        # Створюємо меню, якщо воно не існує
        if self.menu is None:
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
        else:
            # Якщо існує, очищаємо його
            self.menu.delete(0, 'end')

        self.menu.configure(
            bg=current_theme["context_menu_bg"],
            fg=current_theme["context_menu_fg"],
            activebackground=current_theme["context_menu_active_bg"],
            activeforeground=current_theme["context_menu_active_fg"],
            font=menu_font
        )

        # Створюємо підменю "Тема"
        theme_menu = tk.Menu(
            self.menu, tearoff=0,
            bg=current_theme["context_menu_bg"], fg=current_theme["context_menu_fg"],
            activebackground=current_theme["context_menu_active_bg"],
            activeforeground=current_theme["context_menu_active_fg"],
            font=menu_font, borderwidth=0, relief="flat"
        )

        # Додаємо елементи в підменю "Тема"
        if self._has_icons:
            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"),
                                   image=self._dark_theme_icon, compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"),
                                   image=self._light_theme_icon, compound="left")
            theme_menu.add_separator()
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"),
                                   image=self._custom_theme_icon, compound="left")
        else:
            theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"))
            theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"))
            theme_menu.add_command(label="Custom", command=lambda: self.app.toggle_theme("custom"))

        # Додаємо підменю в головне меню
        if self._has_icons:
            self.menu.add_cascade(label="Theme", menu=theme_menu, image=self._theme_icon, compound="left")
        else:
            self.menu.add_cascade(label="Theme", menu=theme_menu)

        self.menu.add_separator()

        # Додаємо основні пункти
        if self._has_icons:
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app),
                                  image=self._settings_icon, compound="left")
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing, image=self._exit_icon, compound="left")
        else:
            self.menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(self.app))
            self.menu.add_separator()
            self.menu.add_command(label="Exit", command=self.app.on_closing)

        x = button.winfo_rootx() + button.winfo_width()
        y = button.winfo_rooty()

        try:
            # Відображаємо меню в правильній позиції
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

# import customtkinter as ctk
# from ui.image_manager import ImageManager
# from utils import rdp
# from tkinter import font as tkFont
# import tkinter as tk
# import os
# import ui.ui_assets
# from ui.settings_window import SettingsWindow
#
#
# class ContextMenu:
#     def __init__(self, root: ctk.CTk, app, image_manager: ImageManager):
#         self.root = root
#         self.app = app
#         self.image_manager = image_manager
#         self.menu = None
#
#     def show_context_menu2(self, root: ctk.CTk, app, image_manager: ImageManager):
#         menu = self.get_context_menu()
#
#     def get_context_menu(self):
#         if self.menu is None:
#             theme_manager = self.app.theme_manager
#             current_theme = theme_manager.current_theme_data
#
#             base_font_size = 10
#             dpi_scale_factor = rdp.get_windows_dpi_scale(root)
#             scaled_font_size = int(base_font_size * dpi_scale_factor)
#             menu_font = tkFont.Font(family="Inter", size=scaled_font_size)
#
#             self.menu = tk.Menu(
#                 self.root,
#                 tearoff=0,
#                 bg=current_theme["context_menu_bg"],
#                 fg=current_theme["context_menu_fg"],
#                 activebackground=current_theme["context_menu_active_bg"],
#                 activeforeground=current_theme["context_menu_active_fg"],
#                 font=menu_font,
#                 borderwidth=0,
#                 relief="flat"
#             )
#         else:
#             self.menu.delete(0, 'end')
#
#         return self.menu
#
#
#
#     @staticmethod
#     def show_context_menu(root: ctk.CTk, app, image_manager: ImageManager):
#         """
#         Відображає контекстне меню для вікна.
#         """
#         theme_manager = app.theme_manager
#         current_theme = theme_manager.current_theme_data
#
#         base_font_size = 10
#         dpi_scale_factor = rdp.get_windows_dpi_scale(root)
#         scaled_font_size = int(base_font_size * dpi_scale_factor)
#         menu_font = tkFont.Font(family="Inter", size=scaled_font_size)
#
#         if hasattr(root, '_context_menu'):
#             root._context_menu.delete(0, 'end')
#
#             root._context_menu.configure(
#                 bg=current_theme["context_menu_bg"],
#                 fg=current_theme["context_menu_fg"],
#                 activebackground=current_theme["context_menu_active_bg"],
#                 activeforeground=current_theme["context_menu_active_fg"]
#             )
#         else:
#             root._context_menu = tk.Menu(
#                 root,
#                 tearoff=0,
#                 bg=current_theme["context_menu_bg"],
#                 fg=current_theme["context_menu_fg"],
#                 activebackground=current_theme["context_menu_active_bg"],
#                 activeforeground=current_theme["context_menu_active_fg"],
#                 font=menu_font,
#                 borderwidth=0,
#                 relief="flat"
#             )
#
#         context_menu = root._context_menu
#
#         # Важливо: зберігати посилання на PhotoImage, інакше воно буде видалено з пам'яті
#         root._settings_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.SETTINGS_ICON_PATH,
#                                                                      (16, 16))
#         root._exit_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.EXIT_ICON_PATH,
#                                                                  (16, 16))
#         root._theme_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.THEME_ICON_PATH,
#                                                                   (16, 16))
#         root._dark_theme_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.DARK_THEME_ICON_PATH,
#                                                                        (16, 16))
#         root._light_theme_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.LIGHT_THEME_ICON_PATH,
#                                                                         (16, 16))
#         root._custom_theme_icon_photo = image_manager.get_tk_photo_image(ui.ui_assets.CUSTOM_THEME_ICON_PATH,
#                                                                          (16, 16))
#
#         # Створюємо підменю "Тема"
#         theme_menu = tk.Menu(context_menu, tearoff=0,
#                              bg=current_theme["context_menu_bg"], fg=current_theme["context_menu_fg"],
#                              activebackground=current_theme["context_menu_active_bg"],
#                              activeforeground=current_theme["context_menu_active_fg"],
#                              font=menu_font, borderwidth=0, relief="flat")
#
#         # Додаємо елементи в підменю
#         theme_menu.add_command(
#             label="Dark",
#             command=lambda: app.toggle_theme("dark"),
#             image=root._dark_theme_icon_photo, compound="left"
#         )
#
#         theme_menu.add_command(
#             label="Light",
#             command=lambda: app.toggle_theme("light"),
#             image=root._light_theme_icon_photo, compound="left"
#         )
#
#         theme_menu.add_command(
#             label="Custom",
#             command=lambda: app.toggle_theme("custom"),
#             image=root._custom_theme_icon_photo, compound="left"
#         )
#
#         # Додаємо підменю в головне меню
#         context_menu.add_cascade(
#             label="Theme",
#             menu=theme_menu,
#             image=root._theme_icon_photo,
#             compound="left")
#         context_menu.add_separator()
#
#         if root._exit_icon_photo and root._settings_icon_photo:
#             context_menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(app),
#                                      image=root._settings_icon_photo, compound="left")
#             context_menu.add_separator()
#             context_menu.add_command(label="Exit", command=app.on_closing,
#                                      image=root._exit_icon_photo, compound="left")
#
#         else:
#             context_menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(app))
#             context_menu.add_separator()
#             context_menu.add_command(label="Exit", command=app.on_closing)  # Без іконки, якщо не завантажилась
#             # Без іконки, якщо не завантажилась
#         context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
