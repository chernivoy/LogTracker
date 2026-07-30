import os
import queue
import tkinter as tk

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
        self._geometry_save_job = None

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
        self.root.bind("<Configure>", self.on_window_resize)

        # Геометрію вже застосував ErrorWindow.setup_window() → _load_window_geometry().
        # Тут повторний виклик був би зайвим (результат усе одно ігнорувався).

    def run(self):
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.destination_directory, recursive=False)
        self.observer.start()

        # Спершу синхронізація, щоб у теці призначення вже лежали свіжі
        # копії, і лише потім пошук найсвіжішої відомої помилки.
        self.event_handler.sync_files_and_check(self.source_directory)
        self.show_latest_known_error()

        self.process_queue()
        self.periodic_sync()
        self._ensure_on_screen()

        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, self))
        self.root.mainloop()

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
                    print(f"[on-screen guard] вікно було поза екраном ({x},{y}) → ({nx},{ny})")

                target_alpha = self.theme_manager.current_theme_data.get("window_alpha")
                if target_alpha is not None:
                    try:
                        current_alpha = float(self.root.attributes('-alpha'))
                        if abs(current_alpha - float(target_alpha)) > 0.01:
                            self.root.attributes('-alpha', target_alpha)
                            print(f"[on-screen guard] відновлено alpha теми {current_alpha} → {target_alpha}")
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

    def on_file_label_double_click(self, event):
        """Копіює шлях до файлу в буфер обміну, якщо подія сталася на мітці."""
        if self.event_handler.last_error_file:
            FileHandler.reveal_in_file_explorer(self.event_handler.last_error_file)

    def on_window_resize(self, event):
        """Зберігає геометрію з дебаунсом.

        <Configure> сипле десятками подій за секунду під час перетягування
        чи ресайзу, а save_window_size щоразу робить повний цикл
        читання-модифікації-запису ini. Відкладаємо запис до моменту, коли
        рух припинився.
        """
        if self._geometry_save_job is not None:
            self.root.after_cancel(self._geometry_save_job)

        self._geometry_save_job = self.root.after(500, self._save_geometry_now)

    def _save_geometry_now(self):
        self._geometry_save_job = None
        WindowHandler.save_window_size('Window', self.root)

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
        вікно з трею не піднімаємо.
        """
        latest = self.event_handler.find_latest_existing_error()
        if latest is None:
            print("No existing errors found in tracked files")
            return

        _, file_path, error_line = latest
        self.event_handler.last_error_file = file_path
        self.on_error_found(file_path, error_line, alert=False)

    def on_error_found(self, file_path, error_line, alert=True):
        """Показує найсвіжішу помилку тіку — одну, з будь-якого файлу.

        Вибір робить FileChangeHandler: він читає всі нові рядки всіх
        файлів і порівнює мітки часу, тож сюди приходить уже переможець.

        alert=False — показ уже відомої помилки при старті: вміст той
        самий, але вікно не має вискакувати з трею через стару подію.
        """
        file_name = os.path.basename(file_path)

        header_label_font = self.theme_manager.current_theme_data.get("header_label_font")
        error_textbox_font = self.theme_manager.current_theme_data.get("error_textbox_font")

        self.file_label.configure(font=header_label_font or ("Inter", 13),
                                  text=f" File: {file_name}")
        self.error_text_widget.configure(font=error_textbox_font or ("Inter", 13),
                                         state=tk.NORMAL)

        self.error_text_widget.delete(1.0, tk.END)
        self.error_text_widget.insert(tk.END, error_line + "\n")
        self.error_text_widget.configure(state=tk.DISABLED)

        if alert and not self.is_window_open:
            TrayManager.restore_window(self.root, self)


if __name__ == "__main__":
    app = LogTrackerApp()
    app.run()
