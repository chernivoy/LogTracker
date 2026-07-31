# Файл: ui_assets.py

import os
import sys


def resource_path(relative_path):
    """ Отримує абсолютний шлях до ресурсів для PyInstaller та розробки """
    try:
        # PyInstaller створює тимчасову папку і зберігає шлях у _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Якщо запущено просто як скрипт .py
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# Шляхи до іконок
# HEADER_ICON_PATH = os.path.join("src", "Header.ico")
HEADER_ICON_PATH = resource_path(os.path.join("src", "Header.ico"))
BUG_ICON_PATH = os.path.join("src", "bug2.png")
CLOSE_ICON_PATH = os.path.join("src", "close.png")
BURGER_MENU_ICON_PATH = os.path.join("src", "burger_menu.png")
EXIT_ICON_PATH = os.path.join("src", "exit_icon.png")
SETTINGS_ICON_PATH = os.path.join("src", "settings_icon.png")
DARK_THEME_ICON_PATH = os.path.join("src", "moon2.png")
LIGHT_THEME_ICON_PATH = os.path.join("src", "day2.png")
GRAPHITE_THEME_ICON_PATH = os.path.join("src", "graphite.png")
THEME_ICON_PATH = os.path.join("src", "theme.png")
