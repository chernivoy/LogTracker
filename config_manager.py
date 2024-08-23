import sys
import configparser
import os
import ctypes

def resource_path(relative_path):
    """ Получает путь к ресурсу (файлу), который упакован PyInstaller. """
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Указываем путь к файлу конфигурации
CONFIG_FILE_WINDOW = resource_path('src/window_config.ini')

print(f'Path to config: {CONFIG_FILE_WINDOW}')  # Вывод пути для отладки

class ConfigManager:
    @staticmethod
    def load_config(config_file):
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Конфигурационный файл не найден: {config_file}")

        config.read(config_file)

        if 'Settings' not in config:
            raise configparser.NoSectionError('Settings')

        return config

    @staticmethod
    def save_window_size(root):
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        dpi_scale = user32.GetDpiForWindow(root.winfo_id()) / 96.0

        width = int(root.winfo_width() / dpi_scale)
        height = int(root.winfo_height() / dpi_scale)

        config = configparser.ConfigParser()
        config['Window'] = {
            'width': width,
            'height': height,
            'x': root.winfo_x(),
            'y': root.winfo_y()
        }

        with open(CONFIG_FILE_WINDOW, 'w') as configfile:
            config.write(configfile)

    @staticmethod
    def load_window_size(root):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE_WINDOW):
            config.read(CONFIG_FILE_WINDOW)
            if 'Window' in config:
                width = config.getint('Window', 'width', fallback=800)
                height = config.getint('Window', 'height', fallback=600)
                x = config.getint('Window', 'x', fallback=100)
                y = config.getint('Window', 'y', fallback=100)
                root.geometry(f'{width}x{height}+{x}+{y}')
        else:
            root.geometry('800x600+100+100')
