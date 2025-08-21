import sys
import configparser
import os
import ctypes
from utils.path import PathUtils

# Указываем путь к файлу конфигурации
CONFIG_FILE_WINDOW = PathUtils.resource_path(os.path.join("src", "window_config.ini"))


class ConfigManager:
    @staticmethod
    def load_config(config_file):
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            # Якщо файл не знайдено, створюємо його з дефолтними значеннями
            # Дефолтні X і Y тут мають бути ЛОГІЧНИМИ для початку,
            # оскільки root.geometry() їх компенсує
            config['Window'] = {'width': '800', 'height': '600', 'x': '100', 'y': '100'}
            with open(config_file, 'w') as configfile:
                config.write(configfile)
            return config

        config.read(config_file)
        return config

    @staticmethod
    def save_window_size(section, root):
        width = root.winfo_width()
        height = root.winfo_height()
        x = root.winfo_x()
        y = root.winfo_y()

        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        if section not in config:
            config[section] = {}

        config[section]['width'] = str(width)
        config[section]['height'] = str(height)
        config[section]['x'] = str(x)  # Зберігаємо ЛОГІЧНІ X
        config[section]['y'] = str(y)  # Зберігаємо ЛОГІЧНІ Y

        with open(CONFIG_FILE_WINDOW, 'w') as configfile:
            config.write(configfile)

    @staticmethod
    def load_window_size(section, root):
        config = ConfigManager.load_config(CONFIG_FILE_WINDOW)

        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            dpi_scale = dpi / 96.0
        except Exception as e:
            print(
                f"Попередження: Не вдалося отримати DPI Scale в load_window_size: {e}. Використовуємо 2.0 за замовчуванням.")
            dpi_scale = 2.0

        if section in config:
            # Зчитуємо ШИРИНУ, ВИСОТУ, X, Y з INI (всі вони тепер ЛОГІЧНІ)
            width = config.getint(section, 'width', fallback=800)
            height = config.getint(section, 'height', fallback=600)
            x = config.getint(section, 'x', fallback=100)
            y = config.getint(section, 'y', fallback=100)

            # Розміри: ділимо логічні розміри на dpi_scale для geometry()
            width_for_geometry = int(width / dpi_scale)
            height_for_geometry = int(height / dpi_scale)

            # ✅ КЛЮЧОВА ЗМІНА: Позиція X та Y: передаємо ЛОГІЧНІ значення без додаткового ділення.
            # geometry() сам скомпенсує їх з урахуванням DPI.
            x_for_geometry = x
            y_for_geometry = y

            return f'{width_for_geometry}x{height_for_geometry}+{x_for_geometry}+{y_for_geometry}'
        else:
            return None

    @staticmethod
    def save_config_value(section, key, value, config_file=CONFIG_FILE_WINDOW):
        config = ConfigManager.load_config(config_file)

        if section not in config:
            config[section] = {}

        config[section][key] = str(value)

        with open(config_file, 'w') as configfile:
            config.write(configfile)
