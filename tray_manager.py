import os
import ctypes
import pystray
from PIL import Image, ImageDraw
from ctypes import windll
from config_manager import ConfigManager
from utils.rdp import check_rdp_status


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
    def on_exit(icon, item, root, app):
        print("Quitting application from tray...")
        if app.observer:
            print("Stopping observer from tray...")
            app.observer.stop()
            app.observer.join(timeout=5)  # Ждем 5 секунд для завершения
            if app.observer.is_alive():
                print("Observer is still running. Force stopping from tray...")
                app.observer = None  # Принудительно освобождаем объект наблюдателя
            else:
                print("Observer stopped successfully from tray.")
        icon.stop()
        root.after(0, app.on_closing)  # Вызываем on_closing в основном потоке

    @staticmethod
    def minimize_to_tray(root, app):
        app.is_window_open = False

        ConfigManager.save_window_size('Window', root)

        def on_open(icon, item):
            root.after(0, icon.stop)
            TrayManager.restore_window(root, app)

        menu = (
            pystray.MenuItem('Open', on_open),
            pystray.MenuItem('Exit', lambda icon, item: TrayManager.on_exit(icon, item, root, app))
        )
        icon_image = TrayManager.create_image(64, 64, 'black', 'blue')
        app.tray_icon = pystray.Icon("test", icon_image, "LogTracker for ADAICA", menu)

        root.withdraw()
        app.tray_icon.run_detached()

    @staticmethod
    def restore_window(root, app):
        if check_rdp_status():
            windll.shcore.SetProcessDpiAwareness(2)  # Установите DPI-осведомленность при восстановлении окна
        else:
            windll.shcore.SetProcessDpiAwareness(1)  # Установите DPI-осведомленность по умолчанию

        ConfigManager.load_window_size('Window', root)  # Перечитываем размеры окна из файла конфигурации
        root.deiconify()
        app.is_window_open = True  # Обновляем состояние окна
        root.lift()
        if app.tray_icon:
            app.tray_icon.visible = False

    # @staticmethod
    # def toggle_pin(root):
    #     if root.attributes('-topmost'):
    #         root.attributes('-topmost', False)
    #     else:
    #         root.attributes('-topmost', True)

    @staticmethod
    def toggle_pin(root):
        current = root.attributes('-topmost')
        root.attributes('-topmost', not current)
