import os
import ctypes
import pystray
from PIL import Image, ImageDraw
from ctypes import windll
from config_manager import ConfigManager
from utils.rdp import check_rdp_status
from utils.path import PathUtils
from ui.window_handler import WindowHandler


class TrayManager:
    @staticmethod
    def create_image(width, height, color1, color2):
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle(
            (width // 2, 0, width, height // 2),
            fill=color2)
        dc.rectangle(
            (0, height // 2, width // 2, height),
            fill=color2)
        return image

    @staticmethod
    def on_exit(root, app):
        root.after(0, app.on_closing)  # Вызываем on_closing в основном потоке

    @staticmethod
    def minimize_to_tray(root, app):
        app.is_window_open = False

        WindowHandler.save_window_size('Window', root)

        def on_open(icon, item):
            root.after(0, icon.stop)
            TrayManager.restore_window(root, app)

        menu = (
            pystray.MenuItem('Open', on_open),
            # pystray.MenuItem('Exit', lambda icon, item: TrayManager.on_exit(icon, item, root, app))
            pystray.MenuItem('Exit', lambda icon, item: TrayManager.on_exit(root, app))

        )

        icon_file_path = PathUtils.resource_path(os.path.join("src", "bug2.png"))
        try:
            icon_image = Image.open(icon_file_path)
        except FileNotFoundError:
            print(f"Помилка: Файл іконки не знайдено за шляхом: {icon_file_path}. Використовуємо стандартну іконку.")
            icon_image = TrayManager.create_image(64, 64, 'black', 'blue')

        app.tray_icon = pystray.Icon("test", icon_image, "LogTracker for ADAICA", menu)

        root.withdraw()
        app.tray_icon.run_detached()

    @staticmethod
    def restore_window(root, app):

        WindowHandler.load_window_size('Window', root)  # Перечитываем размеры окна из файла конфигурации
        root.deiconify()
        app.is_window_open = True  # Обновляем состояние окна
        root.lift()
        if app.tray_icon:
            app.tray_icon.visible = False

    @staticmethod
    def toggle_pin(root):
        current = root.attributes('-topmost')
        root.attributes('-topmost', not current)
