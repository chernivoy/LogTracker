import importlib

import customtkinter as ctk

from config_manager import ConfigManager
from utils.path import PathUtils

config_path = PathUtils.user_config_path("window_config.ini")


DEFAULT_THEME = 'dark'


class ThemeManager:
    config = ConfigManager.load_config(config_path)
    theme = config.get('Theme', 'current', fallback=DEFAULT_THEME)

    def __init__(self, initial_theme: str = theme):
        self.current_theme_name = initial_theme
        self.current_theme_data = {}
        self.load_theme(self.current_theme_name)

    def load_theme(self, theme_name: str):
        """
        Завантажує та застосовує нову тему за її назвою.

        Якщо тему завантажити не вдалося — відкочується на DEFAULT_THEME.
        Раніше помилка лише друкувалася, current_theme_data лишався порожнім,
        і застосунок падав значно пізніше з KeyError у ErrorWindow.setup_window.
        """
        try:
            # Динамічно імпортуємо модуль теми, наприклад, 'themes.dark_theme'
            theme_module = importlib.import_module(f"themes.{theme_name}_theme")
            theme_data = theme_module.THEME_SETTINGS
            # Застосовуємо CTkAppearanceMode
            ctk.set_appearance_mode(theme_data["ctk_appearance_mode"])
        except (ModuleNotFoundError, AttributeError, KeyError) as e:
            # Текст навмисно ASCII: у console-збірці stdout буває в cp1252,
            # і кирилиця тут падала з UnicodeEncodeError, ховаючи справжню причину.
            print(f"ERROR: cannot load theme '{theme_name}': {type(e).__name__}: {e}")

            if theme_name != DEFAULT_THEME:
                print(f"ERROR: falling back to '{DEFAULT_THEME}'")
                self.load_theme(DEFAULT_THEME)
                return

            raise RuntimeError(
                f"Default theme '{DEFAULT_THEME}' is unavailable, cannot continue"
            ) from e

        # Стан оновлюємо лише після успішного застосування — щоб не лишити
        # напівзастосовану тему при збої на будь-якому з кроків вище.
        self.current_theme_name = theme_name
        self.current_theme_data = theme_data
        print(f"Theme changed to: {self.current_theme_name}")

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
