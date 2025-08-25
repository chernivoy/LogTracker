import customtkinter as ctk
from ui.image_manager import ImageManager
from utils import rdp
from tkinter import font as tkFont
import tkinter as tk
import os

from ui.settings_window import SettingsWindow


class ContextMenu:
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
            context_menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(app),
                                     image=root._settings_icon_photo, compound="left")
            context_menu.add_separator()
            context_menu.add_command(label="Exit", command=app.on_closing,
                                     image=root._exit_icon_photo, compound="left")

        else:
            context_menu.add_command(label="Path settings", command=lambda: SettingsWindow.open_settings_window(app))
            context_menu.add_separator()
            context_menu.add_command(label="Exit", command=app.on_closing)  # Без іконки, якщо не завантажилась
            # Без іконки, якщо не завантажилась
        context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
