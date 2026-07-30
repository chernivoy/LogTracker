import pystray
from PIL import Image, ImageDraw

from ui.ui_assets import BUG_ICON_PATH
from ui.window_handler import WindowHandler
from utils import rdp
from utils.path import PathUtils


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
        root.after(0, app.on_closing)

    @staticmethod
    def minimize_to_tray(root, app):
        app.is_window_open = False

        WindowHandler.save_window_size('Window', root)

        def on_open(icon, item):
            root.after(0, icon.stop)
            TrayManager.restore_window(root, app)

        # Визначаємо локальний словник з дефолтними значеннями (логічними)
        defaults = {
            'x': 100,
            'y': 100,
            'width': 300,
            'height': 300
        }

        def on_restore_defaults(icon, item):
            # Цей колбек виконується в потоці pystray. Файловий запис і чисті
            # ctypes-обчислення тут безпечні, але всі операції з Tk-вікном
            # маршалимо в головний цикл через root.after (правило потоків).
            WindowHandler.save_window_params(
                'Window',
                x=defaults['x'],
                y=defaults['y'],
                width=defaults['width'],
                height=defaults['height']
            )

            # Масштаб CTk (кешований, той самий, що CTk застосує в geometry()).
            dpi_scale = WindowHandler._window_scale(root)

            # Розміри ділимо на масштаб (CTk множить назад). X/Y — фізичні.
            w_geo = int(defaults['width'] / dpi_scale)
            h_geo = int(defaults['height'] / dpi_scale)

            # Про всяк випадок підганяємо дефолтну позицію у видиму область
            # (напр. якщо первинний монітор має від'ємний origin).
            x_geo, y_geo = rdp.clamp_to_visible(
                defaults['x'], defaults['y'], defaults['width'], defaults['height']
            )

            def _apply():
                root.geometry(f"{w_geo}x{h_geo}+{x_geo}+{y_geo}")
                # Одразу показуємо вікно, а не лишаємо в треї до окремого кліку
                # «Open»: сенс пункту — витягнути зникле вікно в один крок.
                root.deiconify()
                app.is_window_open = True
                root.lift()
                root.attributes('-topmost', True)
                if root.overrideredirect():
                    root.update_idletasks()
                    WindowHandler.round_corners(root, 30)

            root.after(0, icon.stop)
            root.after(0, _apply)
            if app.tray_icon:
                app.tray_icon.visible = False

        menu = (
            pystray.MenuItem('Open', on_open, default=True),
            # Записуємо дефолтні значення (просто викликаємо без x, y)
            pystray.MenuItem('Restore Defaults window size', on_restore_defaults),
            pystray.MenuItem('Exit', lambda icon, item: TrayManager.on_exit(root, app))

        )

        icon_file_path = PathUtils.resource_path(BUG_ICON_PATH)
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
        # load_window_size ПОВЕРТАЄ рядок геометрії (з уже підігнаною у видиму
        # область позицією) — його треба ЗАСТОСУВАТИ. Раніше результат
        # ігнорувався, тож відновлення не перепозиціонувало вікно, і зникле за
        # межами екрана вікно так і лишалось невидимим.
        geometry_string = WindowHandler.load_window_size('Window', root)
        if geometry_string:
            root.geometry(geometry_string)

        root.deiconify()
        app.is_window_open = True  # Обновляем состояние окна
        root.lift()
        root.attributes('-topmost', True)  # overrideredirect-вікно легко втрачає topmost
        if app.tray_icon:
            app.tray_icon.visible = False

    @staticmethod
    def toggle_pin(root):
        current = root.attributes('-topmost')
        root.attributes('-topmost', not current)
