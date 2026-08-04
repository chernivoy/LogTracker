import os
import queue
import tkinter as tk
from tkinter import font as tkfont

import customtkinter as ctk
from watchdog.observers import Observer

from config_manager import ConfigManager
from constants import CONFIG_PATH
from file_change_handler import FileChangeHandler
from file_handler import FileHandler
from theme_manager import ThemeManager
from tray_manager import TrayManager
from ui.error_window import ErrorWindow
from ui.image_manager import ImageManager
from ui.window_handler import WindowHandler
from utils import rdp
from utils.tray_promote import promote_tray_icon
import sys
import ctypes

# Логування в проєкті тримається на print(), а повідомлення часто містять
# кирилицю. Консоль Windows зазвичай працює в cp1252/cp866, тож print()
# падав з UnicodeEncodeError — найчастіше саме всередині except-гілки,
# через що обробник помилки сам ставав помилкою і ховав початкову причину.
# errors='replace' робить вивід ущербним (нелатиниця стає '?'), але ніколи
# не аварійним. Кодування не чіпаємо: підміна на utf-8 дала б кракозябри
# в консолях зі старою кодовою сторінкою.
for _stream in (sys.stdout, sys.stderr):
    # sys.stdout дорівнює None у windowed-збірці — там вивід перехоплює
    # rthook_logfile.py, який пише у файл в utf-8 без втрат.
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except (OSError, ValueError):
            pass

if sys.platform == "win32":
    # DPI-awareness критичний для RDP з Retina-клієнта. Виставляємо ДО
    # створення CTk (яке саме намагається викликати SetProcessDpiAwareness(2)):
    # рівень awareness ставиться один раз на процес, тож перемагає перший
    # виклик. Раніше тут стояв SetProcessDpiAwareness(1) — це SYSTEM-aware
    # (а не PER_MONITOR, попри старий лог), і CTk-івський виклик мовчки
    # провалювався. Наслідок: процес «замерзав» на DPI входу, а при реконекті
    # RDP з іншим DPI Windows віртуалізував координати (звідси від'ємні X/Y і
    # зникле вікно), тоді як GetDpiForMonitor у CTk бачив реальний новий DPI —
    # неузгодженість, що ламала і розмір, і позицію.
    #
    # PER_MONITOR_AWARE_V2 коректно реагує на зміну DPI сесії (WM_DPICHANGED),
    # координати лишаються реальними, а масштаб CTk узгоджений з ними.
    try:
        # -4 == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        if not ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            raise OSError("SetProcessDpiAwarenessContext(-4) failed")
        print("INFO: DPI awareness = PER_MONITOR_AWARE_V2")
    except (AttributeError, OSError):
        try:
            # Windows 8.1 / 10 до 1607: per-monitor без v2.
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            print("INFO: DPI awareness = PER_MONITOR_DPI_AWARE")
        except (AttributeError, OSError):
            # Зовсім старі версії Windows.
            ctypes.windll.user32.SetProcessDPIAware()
            print("INFO: DPI awareness = SYSTEM (legacy)")


class LogTrackerApp:
    def __init__(self):
        # Загрузка конфигурации
        self.theme_manager = ThemeManager()
        self.config = ConfigManager.load_config(CONFIG_PATH)

        # 1. Спочатку створюємо головне вікно
        self.root = ctk.CTk()

        # 2. Потім створюємо ImageManager, передаючи йому root
        self.image_manager = ImageManager(self.root)

        # Инициализация директорий из конфигурации или установка значений по умолчанию, если их нет
        self.source_directory = self.config.get('Settings', 'source_directory', fallback='')
        self.destination_directory = self.config.get('Settings', 'destination_directory', fallback=r'C:\temp\logger')
        self.word = self.config.get('Settings', 'word', fallback='')
        self.file_extension = self.config.get('Settings', 'file_extension', fallback='')

        # Инициализация других атрибутов
        self.observer = None
        self.is_window_open = True
        self.tray_icon = None
        self._settings_window = None  # відкрите вікно налаштувань (guard від дублювання)
        self._geometry_save_job = None
        self._header_file_path = None  # поточний файл у заголовку (для вписування імені)

        self.error_window = ErrorWindow(self, self.root, self.image_manager)
        self.event_queue = queue.Queue()
        self.event_handler = FileChangeHandler(self, self.destination_directory, self.word, self.file_extension,
                                               self.event_queue)

        self.error_text_widget, self.file_label, self.widgets_to_update = (
            self.error_window.error_text_widget,
            self.error_window.file_label,
            self.error_window.widgets_to_update
        )

        # Привязка событий
        self.error_text_widget.bind("<Double-Button-1>", self.on_error_double_click)
        self.file_label.bind("<Double-Button-1>", self.on_file_label_double_click)
        # Ctrl+клік специфічніший за <ButtonPress-1> (перетягування вікна) з
        # ErrorWindow.bind_events, тож Tk обирає саме його і вікно не «їде».
        self.file_label.bind("<Control-Button-1>", self.on_file_label_ctrl_click)
        self.root.bind("<Configure>", self.on_window_resize)

        # Геометрію вже застосував ErrorWindow.setup_window() → _load_window_geometry().
        # Тут повторний виклик був би зайвим (результат усе одно ігнорувався).

    def run(self):
        # Win11: підвищуємо іконку трея до «always show», поки її ще не додали
        # (перший minimize_to_tray). Недокументований механізм, best-effort —
        # див. utils/tray_promote. No-op у dev і на Win10.
        promote_tray_icon()

        # observer стартує навіть без жодного watch — це коректно. Watch на
        # теку призначення додає _watch_destination, і лише якщо тека валідна:
        # на першому запуску без налаштувань (порожній/неіснуючий шлях) планувати
        # watchdog не можна — емітер ReadDirectoryChangesW впав би на CreateFileW.
        self.observer = Observer()
        self.observer.start()
        self._watch_destination()

        # Перший запуск на новій машині: шляхи можуть бути не налаштовані
        # (порожні) або вказувати на теки, яких тут нема. _refresh_startup_view
        # сам вибере, що показати — підказку про налаштування чи найсвіжішу
        # відому помилку, — і не полізе копіювати з неіснуючого джерела.
        self._refresh_startup_view()

        self.process_queue()
        self.periodic_sync()
        self._ensure_on_screen()

        # Після повного мапінгу вікна (на старті winfo_* ще неточні) повторюємо
        # ре-фіт заголовка й перерахунок мінімальної висоти.
        self.root.after(200, self._fit_header_text)
        self.root.after(200, self.error_window.apply_dynamic_min_height)
        # Запобіжник від «замалого вікна» на старті: перший check_dpi_scaling у
        # CTk (~100 мс після mainloop) уточнює масштаб монітора, тож повторно
        # застосовуємо збережену геометрію вже з коректним DPI — інакше на
        # моніторі з іншим DPI, ніж первинний, вікно лишалось би зменшеним.
        self.root.after(250, self._reapply_saved_geometry)

        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, self))
        self.root.mainloop()

    def _reapply_saved_geometry(self):
        """Повторно застосовує збережену геометрію після того, як CTk визначив
        правильний DPI-масштаб монітора (перший check_dpi_scaling ~100 мс після
        mainloop). На старті геометрія спершу застосовується з масштабом
        первинного монітора; якщо вікно відкривається на моніторі з іншим DPI,
        логічний розмір домножувався не на той масштаб і вікно з'являлося
        замалим. Повторне застосування вже з коректним масштабом дає правильний
        фізичний розмір без ручного ресайзу. Якщо розмір уже коректний —
        геометрія та сама, тож повтор нічого не смикає."""
        geometry_string = WindowHandler.load_window_size('Window', self.root)
        if geometry_string:
            self.root.geometry(geometry_string)

    def _ensure_on_screen(self):
        """Періодичний вартовий стану вікна після реконекту RDP.

        Реконект (особливо з Retina-клієнта зі зміною DPI) лишає по собі два
        сліди, які треба лікувати на таймері, бо події від користувача нема:

        1. **Позиція.** Windows може віддати вікну некоректні/від'ємні
           координати, і воно зникає з екрана. Якщо ВІДКРИТЕ вікно повністю
           поза видимою областю — повертаємо його всередину і піднімаємо.
           Спрацьовує лише коли вікно фактично невидиме (див. is_rect_visible),
           тож свідоме заповзання за край не зачіпає.
        2. **Прозорість.** CustomTkinter (ScalingTracker.check_dpi_scaling) при
           зміні DPI жорстко ставить `-alpha=1` **після** свого перемасштабу,
           затираючи прозорість із теми; перекрити це в `_set_scaling` не можна
           (alpha ставиться пізніше). Відновлюємо alpha теми тут — і лише коли
           він реально «поплив», щоб не мигати вікном щотіку.
        """
        try:
            if self.is_window_open and self.root.winfo_exists():
                x, y = self.root.winfo_x(), self.root.winfo_y()
                w, h = self.root.winfo_width(), self.root.winfo_height()
                if not rdp.is_rect_visible(x, y, w, h):
                    nx, ny = rdp.clamp_to_visible(x, y, w, h)
                    self.root.geometry(f"+{nx}+{ny}")
                    self.root.lift()
                    self.root.attributes('-topmost', True)
                    print(f"[on-screen guard] window was off-screen ({x},{y}) -> ({nx},{ny})")

                target_alpha = self.theme_manager.current_theme_data.get("window_alpha")
                if target_alpha is not None:
                    try:
                        current_alpha = float(self.root.attributes('-alpha'))
                        if abs(current_alpha - float(target_alpha)) > 0.01:
                            self.root.attributes('-alpha', target_alpha)
                            print(f"[on-screen guard] restored theme alpha {current_alpha} -> {target_alpha}")
                    except (tk.TclError, ValueError):
                        pass
        except Exception as e:
            print(f"[on-screen guard] {e}")
        finally:
            self.root.after(2000, self._ensure_on_screen)

    def process_queue(self):
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            # try всередині циклу, а не навколо нього: раніше один збійний
            # колбек обривав розбір усієї черги на цей тік, і решта подій
            # чекала наступного проходу.
            try:
                event()
            except Exception as e:
                print(f"Exception in queued event: {e}")
        self.root.after(100, self.process_queue)

    def periodic_sync(self):
        self.event_handler.sync_files_and_check(self.source_directory)
        self.root.after(1000, self.periodic_sync)

    def apply_directory_settings(self, source_directory, destination_directory):
        """Застосовує нові шляхи з вікна налаштувань БЕЗ перезапуску.

        source_directory підхоплюється сам: periodic_sync щотіка читає
        self.source_directory, тож досить оновити атрибут. А от теку
        призначення тримають закешованою ДВА місця — FileChangeHandler
        (передана в конструкторі) і watchdog-observer, запланований на стару
        теку. Тож зміну призначення проводимо вручну, інакше застосунок далі
        копіює і стежить за старою текою.

        Викликається з головного потоку Tk (кнопка Save), тож звертатися до
        обробника й черги тут безпечно — той самий потік, що й periodic_sync.
        Шляхи вже провалідовані у SettingsWindow (джерело існує, призначення
        непорожнє й не файл).
        """
        self.source_directory = source_directory

        if destination_directory != self.destination_directory:
            self.destination_directory = destination_directory
            handler = self.event_handler
            handler.destination_directory = destination_directory
            FileHandler().create_directory_if_not_exists(destination_directory)

            # Стан трекінгу прив'язаний до СТАРОЇ теки — скидаємо повністю.
            # managed_files стартує порожнім свідомо (як на старті застосунку):
            # чужі .log у новій теці видаляти не можна, лише власні майбутні копії.
            handler.file_paths = {}
            handler.managed_files = set()
            handler.last_error_file = None
            handler.track_files()

            self._watch_destination()

        # Оновити вміст вікна під нові шляхи: найсвіжіша помилка з нової теки
        # або (якщо помилок ще нема) чисте поле замість старого вмісту/підказки.
        self._refresh_startup_view()

    def _watch_destination(self):
        """(Пере)планує watchdog на поточну теку призначення, якщо вона придатна.

        Порожній або неіснуючий шлях (перший запуск без налаштувань) НЕ
        плануємо: емітер ReadDirectoryChangesW відкрив би CreateFileW на
        порожньому шляху і впав. observer стартує в run() навіть без жодного
        watch — це коректно, а watch додається/замінюється тут, коли тека вже
        валідна. unschedule_all на щойно стартованому observer — безпечний no-op.
        """
        if not self.observer:
            return
        try:
            self.observer.unschedule_all()
            if self.destination_directory and os.path.isdir(self.destination_directory):
                self.observer.schedule(
                    self.event_handler, self.destination_directory, recursive=False)
        except Exception as e:
            print(f"Could not watch {self.destination_directory!r}: {e}")

    def _paths_configured(self):
        """Чи задані шляхи настільки, щоб застосунку було що робити.

        Джерело мусить існувати — з нього копіюємо; порожнє або неіснуюче
        (напр. шлях з чужої машини у зашитому config.ini) означає «не
        налаштовано». Теку призначення досить мати непорожньою: якщо її ще
        нема, застосунок її створить.
        """
        return (bool(self.source_directory) and os.path.isdir(self.source_directory)
                and bool(self.destination_directory))

    def _refresh_startup_view(self):
        """Вирішує, що показати у вікні, коли власної нової помилки ще нема:
        підказку про налаштування (шляхи не задані/недоступні) або найсвіжішу
        вже відому помилку. Викликається на старті і після зміни налаштувань.
        """
        if not self._paths_configured():
            self._show_setup_hint()
            return

        # Спершу синхронізація, щоб у теці призначення вже лежали свіжі копії,
        # і лише потім пошук найсвіжішої відомої помилки (alert=False — вікно
        # з трею не спливає, це відновлення стану, а не нова подія).
        self.event_handler.sync_files_and_check(self.source_directory)
        if not self.show_latest_known_error():
            # Налаштовано, але помилок ще нема — прибираємо стару підказку/вміст.
            self._set_error_text("")

    def _show_setup_hint(self):
        """Підказка для першого запуску на новій машині, коли теки не задані.
        Без неї вікно лишалося б порожнім і незрозуміло, що робити далі."""
        self._set_error_text(
            'Paths are not set. Open "Path settings" from the menu (top-right) '
            'and choose the source and destination folders.')

    def _set_error_text(self, text):
        """Ставить текст у поле помилки (порожній рядок — очистити поле)."""
        self.error_text_widget.configure(state=tk.NORMAL)
        self.error_text_widget.delete(1.0, tk.END)
        if text:
            self.error_text_widget.insert(tk.END, text + "\n")
        self.error_text_widget.configure(state=tk.DISABLED)

    def on_closing(self):
        def _safe_closing():
            try:
                print("Closing application...")
                WindowHandler.save_window_size('Window', self.root)
                if self.observer:
                    print("Stopping observer...")
                    self.observer.stop()
                    self.observer.join(timeout=5)  # Ждем 5 секунд для завершения
                    if self.observer.is_alive():
                        print("Observer is still running. Force stopping...")
                        self.observer = None  # Принудительно освобождаем объект наблюдателя
                    else:
                        print("Observer stopped successfully.")
                print("Destroying root window...")
                self.root.quit()  # Используем quit() для завершения главного цикла Tkinter
            except Exception as e:
                print(f"Error during closing: {e}")
            finally:
                self.root.destroy()  # Уничтожаем окно только после завершения всех операций
                print("Application closed.")
                os._exit(0)  # Принудительно завершаем процесс

        if self.tray_icon:
            self.tray_icon.stop()  # Останавливаем иконку в трее

        self.root.after(0, _safe_closing)  # Выполняем _safe_closing в основном потоке

    def on_error_double_click(self, event):
        if self.event_handler.last_error_file:
            FileHandler.open_file(self.event_handler.last_error_file)

    def _source_log_path(self):
        """Шлях до ОРИГІНАЛУ поточного лога в теці джерела ('' якщо недоступний).

        У заголовку стоїть ім'я файла з теки призначення (там працює трекер),
        але користувачу в обох діях із заголовком потрібен оригінал: копія
        службова, її перезаписує кожен тік синхронізації. Ім'я при копіюванні
        не змінюється, тож оригінал знаходимо за basename у source_directory.
        """
        error_file = self.event_handler.last_error_file
        if not error_file or not self.source_directory:
            return ''

        candidate = os.path.join(self.source_directory, os.path.basename(error_file))
        return candidate if os.path.exists(candidate) else ''

    def on_file_label_double_click(self, event):
        """Подвійний клік по заголовку — показати лог у Провіднику, саме в
        теці ДЖЕРЕЛА (див. _source_log_path), а не в копії.

        Фолбеки, щоб подвійний клік не лишався без реакції: якщо оригінал
        зник (лог могли прибрати з джерела) — відкриваємо саму теку джерела;
        якщо й вона недоступна (шляхи ще не задані, мережа відвалилась) —
        показуємо копію, як було раніше.
        """
        error_file = self.event_handler.last_error_file
        if not error_file:
            return

        source_file = self._source_log_path()
        if source_file:
            FileHandler.reveal_in_file_explorer(source_file)
        elif self.source_directory and os.path.isdir(self.source_directory):
            FileHandler.open_file(self.source_directory)
        else:
            FileHandler.reveal_in_file_explorer(error_file)

    def on_file_label_ctrl_click(self, event):
        """Ctrl+клік по заголовку — кладе САМ ФАЙЛ лога в буфер обміну
        (CF_HDROP: Ctrl+V у Провіднику/пошті дасть файл) і підтверджує це
        плашкою над заголовком.

        Копіюємо оригінал із джерела — узгоджено з подвійним кліком; на копію
        з теки призначення падаємо лише коли оригінал недоступний, щоб дія
        взагалі спрацювала.
        """
        # Заголовок — зона переміщення вікна: під Ctrl спрацьовує саме цей
        # обробник (Tk обирає прив'язку з модифікатором як специфічнішу), тож
        # <ButtonPress-1> з WindowHandler.start_move НЕ виконується. Але
        # <B1-Motion> лишається прив'язаним, і якщо користувач посуне мишу, не
        # відпустивши кнопку, do_move порахував би зсув від СТАРОЇ точки й
        # смикнув вікно. Тому опорну точку виставляємо самі.
        WindowHandler.start_move(event, self.root)

        target = self._source_log_path() or self.event_handler.last_error_file
        if not target:
            return

        copied = FileHandler.copy_file_to_clipboard(target)
        self.error_window.toast.show("Copied!" if copied else "Copy failed")

    def on_window_resize(self, event):
        """Зберігає геометрію з дебаунсом.

        <Configure> сипле десятками подій за секунду під час перетягування
        чи ресайзу, а save_window_size щоразу робить повний цикл
        читання-модифікації-запису ini. Відкладаємо запис до моменту, коли
        рух припинився.
        """
        # Перевписуємо ім'я файла в заголовку під нову ширину (лише на подіях
        # самого вікна, а не кожного дочірнього віджета).
        if event.widget is self.root:
            self._fit_header_text()

        if self._geometry_save_job is not None:
            self.root.after_cancel(self._geometry_save_job)

        self._geometry_save_job = self.root.after(500, self._save_geometry_now)

    def _save_geometry_now(self):
        self._geometry_save_job = None
        # Best-effort: os.replace у save_atomic зрідка падає на перехідному
        # локі конфіга (антивірус/індексатор), а це лише дебаунсний тік у
        # Tk-колбеку. Ретраї в save_atomic покривають майже все, але навіть
        # стійкий лок не має роняти UI необробленим винятком Tkinter —
        # наступний рух вікна чи вихід збереже геометрію знову.
        try:
            WindowHandler.save_window_size('Window', self.root)
        except OSError as e:
            print(f"WARNING: could not save window geometry: {e}")

    def toggle_theme(self, theme_name: str):
        self.theme_manager.load_theme(theme_name)

        current_theme = self.theme_manager.current_theme_data
        ctk.set_default_color_theme(current_theme["default_color_theme"])
        self.root.attributes('-alpha', current_theme["window_alpha"])

        ThemeManager.update_widgets_theme(self, self.widgets_to_update)
        ConfigManager.save_config("Theme", "current", theme_name)

    def show_latest_known_error(self):
        """Заповнює вікно найсвіжішою вже відомою помилкою при старті.

        Без цього поле лишається порожнім аж до першої нової помилки:
        офсети на старті стоять на кінці файлів, тож усе вже записане
        вважається переглянутим. alert=False — це стан, а не подія, тож
        вікно з трею не піднімаємо. Повертає True, якщо було що показати.
        """
        latest = self.event_handler.find_latest_existing_error()
        if latest is None:
            print("No existing errors found in tracked files")
            return False

        _, file_path, error_line = latest
        self.event_handler.last_error_file = file_path
        self.on_error_found(file_path, error_line, alert=False)
        return True

    def on_error_found(self, file_path, error_line, alert=True):
        """Показує найсвіжішу помилку тіку — одну, з будь-якого файлу.

        Вибір робить FileChangeHandler: він читає всі нові рядки всіх
        файлів і порівнює мітки часу, тож сюди приходить уже переможець.

        alert=False — показ уже відомої помилки при старті: вміст той
        самий, але вікно не має вискакувати з трею через стару подію.
        """
        self._header_file_path = file_path

        # Шрифти тут НЕ чіпаємо: їх виставляє ErrorWindow.create_widgets при
        # створенні й ThemeManager.update_widgets_theme при зміні теми. Раніше на
        # КОЖНУ помилку робився зайвий configure(font=...) із захисним фолбеком
        # ("Inter", 13), що суперечив контракту «всі теми мають однакові ключі».
        self._fit_header_text()

        self.error_text_widget.configure(state=tk.NORMAL)
        self.error_text_widget.delete(1.0, tk.END)
        self.error_text_widget.insert(tk.END, error_line + "\n")
        self.error_text_widget.configure(state=tk.DISABLED)

        if alert and not self.is_window_open:
            TrayManager.restore_window(self.root, self)

    def _fit_header_text(self, event=None):
        """Вписує ' File: <ім'я>' у доступну ширину заголовка, зберігаючи
        розширення (`.log`).

        Заголовок стоїть sticky="nw" (натуральна ширина), тож при малій ширині
        вікна довге ім'я виходило за колонку й лізло під кнопки праворуч —
        кінець (`.log`) перекривався. Тут, якщо повний текст не влазить у
        відстань до кнопок, обрізаємо хвіст ІМЕНІ й ставимо '…' перед
        розширенням, щоб `.log` завжди було видно. Викликається при показі
        помилки та на зміні розміру вікна.
        """
        file_path = self._header_file_path or self.event_handler.last_error_file
        if not file_path:
            return

        filename = os.path.basename(file_path)
        prefix = " File: "
        full = prefix + filename

        try:
            # Міряємо РЕАЛЬНИМ (масштабованим CTk) шрифтом внутрішнього label,
            # щоб збігалося з фізичними пікселями winfo_*.
            inner = getattr(self.file_label, "_label", None)
            font_spec = inner.cget("font") if inner is not None else self.file_label.cget("font")
            measurer = tkfont.Font(font=font_spec)

            # Доступну ширину беремо з РЕАЛЬНОЇ комірки колонки заголовка
            # (grid_bbox), а не з ширини вікна чи позиції кнопок. Колонка з
            # weight=1 при нестачі місця ЗВУЖУЄТЬСЯ першою (кнопки лишаються),
            # тож мітка обрізається саме своєю коміркою — від вікна/кнопок
            # оцінка виходила завеликою і обрізання не спрацьовувало.
            #   avail = ширина_комірки - padx(обидва боки) - chrome
            # chrome = іконка + внутрішні відступи мітки (reqwidth поверх тексту).
            mf = self.error_window.main_frame
            cell = mf.grid_bbox(0, 0)  # (x, y, w, h) комірки заголовка
            cell_w = cell[2] if cell and cell[2] > 0 else self.root.winfo_width()
            info = self.file_label.grid_info()
            padx = info.get("padx", 0)
            padx_total = (padx[0] + padx[1]) if isinstance(padx, (tuple, list)) else 2 * int(padx)
            current_text = self.file_label.cget("text")
            chrome = max(0, self.file_label.winfo_reqwidth() - measurer.measure(current_text))
            avail = cell_w - padx_total - chrome - 4  # -4 невеликий запас
        except Exception:
            if self.file_label.cget("text") != full:
                self.file_label.configure(text=full)
            return

        if avail <= 0 or measurer.measure(full) <= avail:
            text = full
        else:
            name, ext = os.path.splitext(filename)  # ext = ".log"
            text = prefix + "…" + ext
            for k in range(len(name), 0, -1):
                candidate = prefix + name[:k] + "…" + ext
                if measurer.measure(candidate) <= avail:
                    text = candidate
                    break

        if self.file_label.cget("text") != text:
            self.file_label.configure(text=text)


if __name__ == "__main__":
    app = LogTrackerApp()
    app.run()
