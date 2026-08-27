import pystray
from PIL import Image, ImageDraw

from ui.ui_assets import APP_ICON_PATH
from ui.window_handler import WindowHandler
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
    def _stop_icon(root, app):
        """Зупиняє поточну detached-іконку трея і прибирає посилання.

        Ідемпотентний: якщо іконки нема — no-op. Посилання `app.tray_icon`
        обнуляємо ОДРАЗУ, щоб паралельний шлях відновлення (напр. нова
        помилка під час згортання) не спробував зупинити той самий об'єкт
        двічі й не побачив «живу» іконку, якої вже нема.

        `icon.stop()` маршалимо в головний цикл через root.after — так само,
        як це робив увесь тутешній код: метод викликається і з головного
        потоку (minimize/on_error_found), і з потоку pystray (on_open),
        а відкладення уникає зупинки циклу pystray зсередини його ж callback.
        """
        icon = app.tray_icon
        if icon is None:
            return
        app.tray_icon = None

        def _stop():
            try:
                icon.stop()
            except Exception as e:
                print(f"Error stopping tray icon: {e}")

        root.after(0, _stop)

    @staticmethod
    def minimize_to_tray(root, app):
        # Захист від повторного входу. Кнопка «в трей», WM_DELETE і їхня гонка
        # можуть викликати цей метод повторно, коли вікно вже згорнуте. Без
        # guard кожен виклик створював би НОВУ pystray.Icon + run_detached-потік
        # і перезаписував app.tray_icon — попередня іконка ставала осиротілою
        # (посилання втрачене, зупинити неможливо), а потоки накопичувались.
        if not app.is_window_open:
            return

        app.is_window_open = False

        # Підстрахування від витоку: якщо з якоїсь причини лишилась стара
        # detached-іконка (напр. відновлення через нову помилку лише ховало її,
        # не зупиняючи), прибираємо її перед створенням нової.
        TrayManager._stop_icon(root, app)

        WindowHandler.save_window_size('Window', root)

        def on_open(icon, item):
            # Уся Tk-робота + зупинка іконки — усередині потокобезпечного
            # restore_window (маршалить через root.after). Тут нічого з Tk
            # напряму не чіпаємо: колбек виконується в потоці pystray.
            TrayManager.restore_window(root, app)

        # Дефолтні значення — ЛОГІЧНІ (симетрично з load/save window size).
        defaults = {
            'x': 100,
            'y': 100,
            'width': 300,
            'height': 300
        }

        def on_restore_defaults(icon, item):
            # Колбек у потоці pystray. Файловий запис дефолтів тут безпечний;
            # усе, що стосується Tk-вікна, робить restore_window (маршалить у
            # головний цикл). Пишемо дефолти в ini, а тоді відновлюємо звичайним
            # шляхом — load_window_size прочитає саме ці значення й піджене
            # позицію у видиму область. Так уся Tk-логіка живе в одному місці.
            WindowHandler.save_window_params(
                'Window',
                x=defaults['x'],
                y=defaults['y'],
                width=defaults['width'],
                height=defaults['height']
            )
            TrayManager.restore_window(root, app)

        menu = (
            pystray.MenuItem('Open', on_open, default=True),
            # Записуємо дефолтні значення (просто викликаємо без x, y)
            pystray.MenuItem('Restore Defaults window size', on_restore_defaults),
            pystray.MenuItem('Exit', lambda icon, item: TrayManager.on_exit(root, app))

        )

        icon_file_path = PathUtils.resource_path(APP_ICON_PATH)
        try:
            icon_image = Image.open(icon_file_path)
        except Exception as e:
            # Не лише FileNotFoundError: побитий/не-картинка файл кине
            # UnidentifiedImageError/OSError, і без фолбеку впав би весь
            # minimize_to_tray — вікно вже withdraw, іконки нема, застосунок
            # фактично зник з очей. Будь-який збій → згенерована заглушка.
            print(f"Error: could not load tray icon at {icon_file_path}: {e}. Using default icon.")
            icon_image = TrayManager.create_image(64, 64, 'black', 'blue')

        app.tray_icon = pystray.Icon("LogTracker", icon_image, "LogTracker for ADAICA", menu)

        # Бургер-меню — ОКРЕМИЙ Toplevel, і root.withdraw() його НЕ ховає:
        # withdraw діє лише на своє вікно, а попап не transient. Сам себе він
        # теж не закриє: клік по кнопці «в трей» дає йому FocusOut, але
        # рішення ContextMenu відкладає на 60 мс і звіряє з focus_displayof()
        # (бо FocusOut приходить і від кліку по власному підменю) — а на той
        # момент вікно вже withdraw, і Tk повертає фокус самому попапу як
        # єдиному видимому вікну застосунку. Меню бачить фокус «у себе» й
        # лишається відкритим: картка висить поверх усіх вікон, коли самого
        # застосунку на екрані вже нема (виміряно: popup viewable=1 після
        # withdraw, focus_displayof() — знову попап). Тож закриваємо явно.
        app.close_context_menu()

        root.withdraw()
        app.tray_icon.run_detached()

    @staticmethod
    def restore_window(root, app):
        """Показує вікно з трея й зупиняє detached-потік іконки.

        Потокобезпечний: викликається і з головного потоку (on_error_found),
        і з потоку pystray (on_open/on_restore_defaults), тож усі Tk-операції
        маршаляться в головний цикл через root.after (правило потоків).

        Іконку саме ЗУПИНЯЄМО (stop), а не лише ховаємо (visible=False):
        інакше detached-потік pystray лишався б живим, а наступний
        minimize_to_tray створював би ще один — витік потоків за цикл
        «згорнув ↔ прийшла помилка ↔ згорнув».
        """
        TrayManager._stop_icon(root, app)

        def _apply():
            # load_window_size ПОВЕРТАЄ рядок геометрії (з уже підігнаною у
            # видиму область позицією) — його треба ЗАСТОСУВАТИ. Раніше результат
            # ігнорувався, тож відновлення не перепозиціонувало вікно, і зникле за
            # межами екрана вікно так і лишалось невидимим.
            geometry_string = WindowHandler.load_window_size('Window', root)
            if geometry_string:
                root.geometry(geometry_string)

            root.deiconify()
            app.is_window_open = True  # Обновляем состояние окна
            root.lift()
            root.attributes('-topmost', True)  # overrideredirect-вікно легко втрачає topmost
            # Перебудовуємо округлий регіон під фактичний фізичний розмір: якщо
            # DPI змінився, поки вікно було в треї (реконект RDP), регіон від
            # старого масштабу обрізав би кути. update_idletasks спершу застосує
            # geometry, щоб winfo_* були актуальні.
            if root.overrideredirect():
                root.update_idletasks()
                WindowHandler.round_corners(root)

        root.after(0, _apply)

    @staticmethod
    def toggle_pin(root):
        current = root.attributes('-topmost')
        root.attributes('-topmost', not current)
