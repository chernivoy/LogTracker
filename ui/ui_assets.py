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
# Спільна іконка застосунку («жук») — одне джерело для шапки вікна, трея,
# заголовка/таскбара (iconbitmap) і .exe. Два формати з одного дизайну:
#   app_icon.png — 256×256 майстер, який CTkImage/трей САМІ зменшують під DPI
#                  (тому джерело високороздільне — без розмиття на 150–200%);
#   app_icon.ico — мультирозмірний (16…256), з якого Windows бере потрібний
#                  розмір під DPI для iconbitmap та іконки exe.
# .ico резолвиться через resource_path (потрібен реальний шлях для iconbitmap);
# .png — відносний, його резолвлять уже викликачі (ImageManager / TrayManager).
APP_ICO_PATH = resource_path(os.path.join("src", "app_icon.ico"))
APP_ICON_PATH = os.path.join("src", "app_icon.png")
CLOSE_ICON_PATH = os.path.join("src", "close.png")
BURGER_MENU_ICON_PATH = os.path.join("src", "burger_menu.png")
EXIT_ICON_PATH = os.path.join("src", "exit_icon.png")
SETTINGS_ICON_PATH = os.path.join("src", "settings_icon.png")
DARK_THEME_ICON_PATH = os.path.join("src", "moon2.png")
LIGHT_THEME_ICON_PATH = os.path.join("src", "day2.png")
GRAPHITE_THEME_ICON_PATH = os.path.join("src", "graphite.png")
THEME_ICON_PATH = os.path.join("src", "theme.png")
