import importlib
import customtkinter as ctk

class ThemeManager:
    """
    Клас для управління темами застосунку.
    Відповідає за динамічне завантаження налаштувань стилів з файлів.
    """
    def __init__(self, initial_theme: str = "dark"):
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
            ctk.set_appearance_mode(self.current_theme_data["ctk_appearance_mode"])
            print(f"Theme changed to: {self.current_theme_name}")
        except ModuleNotFoundError:
            print(f"Помилка: Файл теми для '{theme_name}' не знайдено.")
        except KeyError as e:
            print(f"Помилка: Відсутній ключ '{e}' в налаштуваннях теми.")

    def get_color(self, key: str, default: str = "#000000") -> str:
        """
        Повертає колір за ключем з поточної теми.
        """
        return self.current_theme_data.get(key, default)