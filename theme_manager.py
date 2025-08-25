import importlib
import os
import customtkinter as ctk
from config_manager import ConfigManager
from utils.path import PathUtils
import configparser

config_path = PathUtils.resource_path(os.path.join("src", "window_config.ini"))

# config = configparser.ConfigParser()
# config.read(config_path)


class ThemeManager:

    config = ConfigManager.load_config(config_path)
    theme = config.get('Theme', 'current', fallback='dark')

    def __init__(self, initial_theme: str = theme):
        self.current_theme_name = initial_theme
        self.current_theme_data = {}
        self.load_theme(self.current_theme_name)

    def load_theme(self, theme_name: str):
        """
        Завантажує та застосовує нову тему за її назвою.
        """
        try:
            # Динамічно імпортуємо модуль теми, наприклад, 'themes.dark_theme'
            theme_module = importlib.import_module(f"themes.{theme_name}_theme")
            self.current_theme_name = theme_name
            self.current_theme_data = theme_module.THEME_SETTINGS
            # Застосовуємо CTkAppearanceMode
            # ctk.set_appearance_mode(self.current_theme_data["ctk_appearance_mode"])
            print(f"Theme changed to: {self.current_theme_name}")
        except ModuleNotFoundError:
            print(f"Помилка: Файл теми для '{theme_name}' не знайдено.")
        except KeyError as e:
            print(f"Помилка: Відсутній ключ '{e}' в налаштуваннях теми.")

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


