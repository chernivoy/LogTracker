import sys
import configparser
import os
import ctypes
from utils.path import PathUtils

# Указываем путь к файлу конфигурации
CONFIG_FILE_WINDOW = PathUtils.user_config_path("window_config.ini")


class ConfigManager:
    @staticmethod
    def save_atomic(config, config_file):
        """Пише конфіг атомарно: у тимчасовий .part і підміняє через os.replace().

        Прямий open(config_file, 'w') одразу обрізає файл до нуля. Краш чи
        os._exit(0), яким завершується on_closing, між truncate і кінцем
        запису лишав би порожній або напівзаписаний ini — той самий клас
        пошкодження, від якого копіювання логів захищено .part-ом. Тут той
        самий прийом (див. file_handler.copy_file_without_waiting): реальний
        конфіг лишається цілим, доки нова версія не запишеться повністю. При
        збої запису прибираємо недороблений .part, щоб він не накопичувався.
        """
        temp_file = config_file + '.part'
        try:
            # encoding='utf-8' явно: без нього береться локальна кодова
            # сторінка (тут cp1251). Шляхи source/destination користувач
            # вводить вручну — вони бувають з кирилицею чи юнікодом, і символ
            # поза кодовою сторінкою кинув би UnicodeEncodeError по кнопці Save
            # або мовчки спотворив шлях. Читання (config.read) — теж utf-8.
            with open(temp_file, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            os.replace(temp_file, config_file)
        except OSError:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
            raise

    @staticmethod
    def load_config(config_file):
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            # Якщо файл не знайдено, створюємо його з дефолтними значеннями
            # Дефолтні X і Y тут мають бути ЛОГІЧНИМИ для початку,
            # оскільки root.geometry() їх компенсує
            config['Window'] = {'width': '800', 'height': '600', 'x': '100', 'y': '100'}
            ConfigManager.save_atomic(config, config_file)
            return config

        try:
            config.read(config_file, encoding='utf-8')
        except (configparser.Error, OSError) as e:
            # Пошкоджений ini (напр. обірваний посеред запису) не має класти
            # застосунок: load_config кличеться на старті, і виняток тут не
            # ловився ніде вище. Повертаємо ПОРОЖНІЙ конфіг — усі читачі йдуть
            # через .get(..., fallback=...) / getint(..., fallback=...), тож
            # підхопляться дефолти, а наступний save_atomic перепише файл
            # коректно. config.read міг лишити config частково заповненим,
            # тому віддаємо свіжий екземпляр, а не цей.
            print(f"Config {config_file} unreadable, falling back to defaults: {e}")
            return configparser.ConfigParser()

        return config

    @staticmethod
    def save_config(section, key, value, config_file=CONFIG_FILE_WINDOW):
        config = ConfigManager.load_config(config_file)

        if section not in config:
            config[section] = {}

        config[section][key] = str(value)

        ConfigManager.save_atomic(config, config_file)
