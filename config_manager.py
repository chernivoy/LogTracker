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
    def save_config(section, key, value, config_file=CONFIG_FILE_WINDOW):
        config = ConfigManager.load_config(config_file)

        if section not in config:
            config[section] = {}

        config[section][key] = str(value)

        with open(config_file, 'w') as configfile:
            config.write(configfile)
