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
            WindowHandler.save_window_params(
                'Window',
                x=defaults['x'],
                y=defaults['y'],
                width=defaults['width'],
                height=defaults['height']
            )

            # 2. Отримуємо DPI scale для коректного розрахунку фізичного розміру
            try:
                dpi_scale = rdp.get_windows_dpi_scale(root)
            except Exception:
                dpi_scale = 2.0

            # 3. Формуємо рядок geometry відповідно до логіки вашого load_window_size
            # Логічні розміри ділимо на DPI
            w_geo = int(defaults['width'] / dpi_scale)
            h_geo = int(defaults['height'] / dpi_scale)

            # Координати X та Y залишаємо логічними (без ділення)
            x_geo = defaults['x']
            y_geo = defaults['y']

            # 4. Фізично оновлюємо вікно, поки воно приховане
            root.geometry(f"{w_geo}x{h_geo}+{x_geo}+{y_geo}")

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
