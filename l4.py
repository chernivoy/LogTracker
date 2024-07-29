import os
import time
import shutil
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import configparser
import subprocess
import ctypes
from ctypes import wintypes
import pystray
from PIL import Image, ImageDraw, ImageFont
from tkinter import PhotoImage
import customtkinter as ctk
from ctypes import windll

CONFIG_FILE = "window_config.ini"

class ConfigManager:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)

    @staticmethod
    def load_config(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        return config

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, config, error_text_widget, file_label, event_queue):
        self.directory = config.get('Settings', 'directory')
        self.directory_A = config.get('Settings', 'directory_A')
        self.word = config.get('Settings', 'word')
        self.error_text_widget = error_text_widget
        self.file_label = file_label
        self.event_queue = event_queue
        self.file_paths = {}
        self.last_error_file = None
        self.last_error_line = {}
        self.last_update_time = {}
        self.track_files()
        self.create_directory_if_not_exists(self.directory)

    def track_files(self):
        print("Отслеживание .log файлов в директории:", self.directory)
        try:
            for file_name in os.listdir(self.directory):
                file_path = os.path.join(self.directory, file_name)
                if file_name.endswith(".log") and self.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
                    self.last_update_time[file_path] = -1
                    print(f"Файл добавлен для отслеживания: {file_path}")
        except PermissionError as e:
            print(f"Ошибка доступа: {e}")
        except FileNotFoundError as e:
            print(f"Файл не найден: {e}")
        except Exception as e:
            print(f"Ошибка при перечислении файлов в директории: {e}")

    def create_directory_if_not_exists(self, directory):
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Создана директория: {directory}")
            except Exception as e:
                print(f"Ошибка при создании директории {directory}: {e}")

    def is_file_closed(self, file_path):
        try:
            with open(file_path, 'rb') as file:
                file.seek(0, os.SEEK_END)
            return True
        except IOError as e:
            print(f"Файл {file_path} в данный момент используется: {e}")
            return False

    def wait_for_file(self, file_path, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_file_closed(file_path):
                return True
        print(f"Файл {file_path} все еще используется после {timeout} секунд.")
        return False

    def copy_files_from_A(self):
        try:
            self.create_directory_if_not_exists(self.directory)
            copied = False
            for filename in os.listdir(self.directory_A):
                if filename.endswith('.log'):
                    source_file = os.path.join(self.directory_A, filename)
                    dest_file = os.path.join(self.directory, filename)
                    if self.wait_for_file(source_file):
                        if not os.path.exists(dest_file):
                            self.copy_file_without_waiting(source_file, dest_file)
                            print(f'Скопирован файл {filename} из директории A в {self.directory}')
                            copied = True
                            self.check_new_errors(dest_file)
                        else:
                            if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                                self.copy_file_without_waiting(source_file, dest_file)
                                print(f'Обновлен файл {filename} в {self.directory}')
                                copied = True
                                self.check_new_errors(dest_file)
            for filename in os.listdir(self.directory):
                if filename.endswith('.log'):
                    dest_file = os.path.join(self.directory, filename)
                    source_file = os.path.join(self.directory_A, filename)
                    if not os.path.exists(source_file):
                        os.remove(dest_file)
                        print(f'Удален файл {filename} из {self.directory}, так как он не существует в {self.directory_A}')
                        copied = True
            if copied:
                print(f'Завершено копирование из {self.directory_A} в {self.directory}.')
                self.event_queue.put(self.update_text_widget)
        except Exception as e:
            print(f"Ошибка при копировании файлов из директории A: {e}")

    def copy_file_without_waiting(self, source_file, dest_file):
        try:
            with open(source_file, 'rb') as src, open(dest_file, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            print(f"Файл {source_file} успешно скопирован в {dest_file}")
        except PermissionError as e:
            print(f"Ошибка доступа при копировании файла {source_file}: {e}")
        except FileNotFoundError as e:
            print(f"Файл {source_file} не найден: {e}")
        except Exception as e:
            print(f"Не удалось скопировать файл {source_file}: {e}")

    def check_new_errors(self, file_path):
        new_lines = self.read_new_lines(file_path)
        current_time = os.path.getmtime(file_path)
        last_error_line = None
        for line in new_lines:
            if line.strip().startswith(self.word) and current_time > self.last_update_time.get(file_path, -1):
                last_error_line = line.strip()
        self.last_update_time[file_path] = current_time
        if last_error_line:
            self.last_error_file = file_path
            file_name = os.path.basename(file_path)
            self.event_queue.put(lambda: self.file_label.configure(text=f"File: {file_name}"))
            print(f"Новая строка с ошибкой: {last_error_line}")
            self.error_text_widget.configure(state=tk.NORMAL)
            self.error_text_widget.delete(1.0, tk.END)
            self.error_text_widget.insert(tk.END, last_error_line + "\n")
            self.error_text_widget.configure(state=tk.DISABLED)
            if not LogTrackerApp.is_window_open:
                self.event_queue.put(LogTrackerApp.show_window_from_tray)

    def can_read_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8'):
                pass
            return True
        except Exception as e:
            print(f"Не удалось прочитать файл {file_path}: {e}")
            return False

    def read_new_lines(self, file_path):
        new_lines = []
        current_size = os.path.getsize(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file.seek(self.file_paths.get(file_path, 0))
                new_lines = file.readlines()
                self.file_paths[file_path] = current_size
        except PermissionError as e:
            print(f"Ошибка доступа: {e}")
        except FileNotFoundError as e:
            print(f"Файл не найден: {e}")
        except Exception as e:
            print(f"Ошибка при чтении файла {file_path}: {e}")
        return new_lines

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".log"):
            if event.event_type == 'deleted':
                self.stop_tracking(event.src_path)
                print(f"Файл {event.src_path} был удален. Остановлено отслеживание.")
            else:
                print(f"Изменен файл: {event.src_path}")
                self.check_new_errors(event.src_path)

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]

class TrayManager:
    def __init__(self, app):
        self.app = app
        self.tray_icon = None

    def create_image(self, width, height, color1, color2):
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
        dc.rectangle((0, height // 2, width // 2, height), fill=color2)
        return image

    def minimize_to_tray(self):
        self.app.save_window_size()
        menu = (pystray.MenuItem('Открыть', self.restore_window), pystray.MenuItem('Выход', self.quit_app))
        icon_image = self.create_image(64, 64,        'blue', 'white')
        self.tray_icon = pystray.Icon("name", icon_image, "Log Tracker", menu)
        self.tray_icon.run_detached()

    def restore_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.app.deiconify()

    def quit_app(self):
        self.app.quit()
        if self.tray_icon:
            self.tray_icon.stop()

class LogTrackerApp(ctk.CTk):
    is_window_open = True

    def __init__(self, config_file):
        super().__init__()
        self.config_manager = ConfigManager(config_file)
        self.init_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tray_manager = TrayManager(self)
        self.event_queue = queue.Queue()
        self.setup_observer()
        self.check_event_queue()

    def init_ui(self):
        self.title("Log Tracker")
        self.geometry("500x300")
        self.configure_grid()
        self.create_widgets()

    def configure_grid(self):
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.columnconfigure(0, weight=1)

    def create_widgets(self):
        self.file_label = ctk.CTkLabel(self, text="File: None")
        self.file_label.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        self.error_text = ctk.CTkTextbox(self, width=500, height=250)
        self.error_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.error_text.configure(state=tk.DISABLED)

    def setup_observer(self):
        directory = self.config_manager.get('Settings', 'directory')
        self.event_handler = FileChangeHandler(
            self.config_manager.config,
            self.error_text,
            self.file_label,
            self.event_queue
        )
        self.observer = Observer()
        self.observer.schedule(self.event_handler, directory, recursive=False)
        self.observer.start()
        self.update_observer()

    def check_event_queue(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                event()
        except queue.Empty:
            pass
        self.after(100, self.check_event_queue)

    def update_observer(self):
        self.event_handler.copy_files_from_A()
        self.after(60000, self.update_observer)

    def on_close(self):
        self.withdraw()
        self.tray_manager.minimize_to_tray()
        LogTrackerApp.is_window_open = False

    @staticmethod
    def show_window_from_tray():
        LogTrackerApp.is_window_open = True
        LogTrackerApp().deiconify()

    def save_window_size(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        if 'window_size' not in config:
            config['window_size'] = {}
        config['window_size']['width'] = str(self.winfo_width())
        config['window_size']['height'] = str(self.winfo_height())
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    def quit(self):
        self.observer.stop()
        self.observer.join()
        self.destroy()

if __name__ == "__main__":
    app = LogTrackerApp(CONFIG_FILE)
    app.mainloop()