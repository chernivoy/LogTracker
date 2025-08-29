import os
import time
import shutil
import queue
import tkinter as tk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import configparser
import subprocess
import ctypes
import customtkinter as ctk
from ctypes import windll

from config_manager import ConfigManager
from tray_manager import TrayManager
from file_handler import FileHandler
from file_change_handler import FileChangeHandler
from theme_manager import ThemeManager

from utils.path import PathUtils
from ui.image_manager import ImageManager
from ui.window_handler import WindowHandler
from ui.error_window import ErrorWindow

config_path = PathUtils.resource_path(os.path.join("src", "config.ini"))

config = configparser.ConfigParser()
config.read(config_path)


class LogTrackerApp:
    def __init__(self):
        # Загрузка конфигурации
        self.theme_manager = ThemeManager()
        self.config = ConfigManager.load_config(config_path)

        # 1. Спочатку створюємо головне вікно
        self.root = ctk.CTk()

        # 2. Потім створюємо ImageManager, передаючи йому root
        self.image_manager = ImageManager(self.root)

        # Инициализация директорий из конфигурации или установка значений по умолчанию, если их нет
        self.directory = self.config.get('Settings', 'directory', fallback='')
        self.source_directory = self.config.get('Settings', 'source_directory', fallback='')
        self.word = self.config.get('Settings', 'word', fallback='')

        # Инициализация других атрибутов
        self.observer = None
        self.error_window = ErrorWindow(self, self.root, self.image_manager)

        self.error_text_widget = self.error_window.error_text_widget
        self.file_label = self.error_window.file_label
        self.widgets_to_update = self.error_window.widgets_to_update

        self.event_queue = queue.Queue()
        self.event_handler = FileChangeHandler(self, self.directory, self.word, self.event_queue)

        # Привязка событий
        self.error_text_widget.bind("<Double-Button-1>", self.on_error_double_click)
        self.root.bind("<Configure>", self.on_window_resize)
        self.is_window_open = True
        self.tray_icon = None

        WindowHandler.load_window_size('Window', self.root)

    def run(self):
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.directory, recursive=False)
        self.observer.start()

        self.process_queue()
        self.periodic_sync()

        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, self))
        self.root.mainloop()

    def process_queue(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                event()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Exception in process_queue: {e}")
        self.root.after(100, self.process_queue)

    def periodic_sync(self):
        self.event_handler.sync_files_and_check(self.config.get('Settings', 'source_directory'))
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

    def on_window_resize(self, event):
        WindowHandler.save_window_size('Window', self.root)

    def toggle_theme(self, theme_name: str):
        self.theme_manager.load_theme(theme_name)

        current_theme = self.theme_manager.current_theme_data
        ctk.set_default_color_theme(current_theme["default_color_theme"])
        self.root.attributes('-alpha', current_theme["window_alpha"])

        ThemeManager.update_widgets_theme(self, self.widgets_to_update)
        ConfigManager.save_config("Theme", "current", theme_name)

    def on_error_found(self, file_path, error_line):
        """Метод, який викликається при виявленні помилки в файлі."""
        file_name = os.path.basename(file_path)

        # Оновлення віджетів UI
        self.file_label.configure(font=("Inter", 13), text=f" File: {file_name}")
        self.error_text_widget.configure(state=tk.NORMAL)
        self.error_text_widget.delete(1.0, tk.END)
        self.error_text_widget.insert(tk.END, error_line + "\n")
        self.error_text_widget.configure(state=tk.DISABLED)

        # Вирішуємо, чи потрібно показати вікно
        if not self.is_window_open:
            TrayManager.restore_window(self.root, self)


if __name__ == "__main__":
    app = LogTrackerApp()
    app.run()
