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
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import pystray
from PIL import Image, ImageDraw

CONFIG_FILE = "window_config.ini"


def copy_file_without_waiting(source_file, dest_file):
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


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, directory, word, text_widget, error_text_widget, file_label, event_queue):
        self.directory = directory
        self.word = word
        self.text_widget = text_widget
        self.error_text_widget = error_text_widget
        self.file_label = file_label
        self.event_queue = event_queue
        self.file_paths = {}
        self.last_error_file = None
        self.last_error_line = {}
        self.last_update_time = {}
        self.track_files()
        self.create_directory_if_not_exists(directory)
        self.update_text_widget()

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
            time.sleep(1)
        print(f"Файл {file_path} все еще используется после {timeout} секунд.")
        return False

    def copy_files_from_A(self):
        directory_A = r'C:\ProgramData\ADAICA Schweiz AG\ADAICA\Logs\ichernevoy'
        try:
            self.create_directory_if_not_exists(self.directory)

            copied = False

            for filename in os.listdir(directory_A):
                if filename.endswith('.log'):
                    source_file = os.path.join(directory_A, filename)
                    dest_file = os.path.join(self.directory, filename)
                    if self.wait_for_file(source_file):
                        if not os.path.exists(dest_file):
                            copy_file_without_waiting(source_file, dest_file)
                            print(f'Скопирован файл {filename} из директории A в {self.directory}')
                            copied = True
                            self.check_new_errors(dest_file)
                        else:
                            if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                                copy_file_without_waiting(source_file, dest_file)
                                print(f'Обновлен файл {filename} в {self.directory}')
                                copied = True
                                self.check_new_errors(dest_file)

            for filename in os.listdir(self.directory):
                if filename.endswith('.log'):
                    dest_file = os.path.join(self.directory, filename)
                    source_file = os.path.join(directory_A, filename)
                    if not os.path.exists(source_file):
                        os.remove(dest_file)
                        print(f'Удален файл {filename} из {self.directory}, так как он не существует в {directory_A}')
                        copied = True

            if copied:
                print(f'Завершено копирование из {directory_A} в {self.directory}.')
                self.event_queue.put(self.update_text_widget)
        except Exception as e:
            print(f"Ошибка при копировании файлов из директории A: {e}")

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
            self.file_label.config(text=f"Последняя ошибка в файле: {os.path.basename(file_path)}")
            print(f"Новая строка с ошибкой: {last_error_line}")
            self.error_text_widget.config(state=tk.NORMAL)
            self.error_text_widget.delete(1.0, tk.END)
            self.error_text_widget.insert(tk.END, last_error_line + "\n")
            self.error_text_widget.config(state=tk.DISABLED)
            self.show_window_from_tray()

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
                self.event_queue.put(self.update_text_widget)

    def on_deleted(self, event):
        if event.src_path in self.file_paths:
            del self.file_paths[event.src_path]
            print(f"Файл {event.src_path} был удален.")
            self.event_queue.put(self.update_text_widget)

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]

    def update_text_widget(self):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        for file_path in self.file_paths:
            self.text_widget.insert(tk.END, file_path + "\n")
        self.text_widget.config(state=tk.DISABLED)

    def show_window_from_tray(self):
        root.deiconify()
        root.attributes('-topmost', True)
        root.attributes('-topmost', False)


def create_text_window():
    root = ttk.Window(themename="litera")
    root.title("Файлы в целевой директории")
    root.attributes('-topmost', True)
    load_window_size(root)

    main_frame = ttk.Frame(root)
    main_frame.pack(fill="both", expand=True, padx=20, pady=20)

    pin_button = ttk.Button(main_frame, text="Unpin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    minimize_button = ttk.Button(main_frame, text="Свернуть в трей", command=lambda: minimize_to_tray(root))
    minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")

    file_label = ttk.Label(main_frame, text="Последняя ошибка в файле:")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    text_widget_frame = ttk.Frame(main_frame)
    text_widget_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=5)

    text_widget = tk.Text(text_widget_frame, wrap="word", state=tk.DISABLED)
    text_widget.pack(side="left", fill="both", expand=True)

    text_scrollbar = ttk.Scrollbar(text_widget_frame, command=text_widget.yview)
    text_scrollbar.pack(side="right", fill="y")
    text_widget.config(yscrollcommand=text_scrollbar.set)

    error_text_widget_frame = ttk.Frame(main_frame)
    error_text_widget_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=5)

    error_text_widget = tk.Text(error_text_widget_frame, wrap="word", state=tk.DISABLED)
    error_text_widget.pack(side="left", fill="both", expand=True)

    error_text_scrollbar = ttk.Scrollbar(error_text_widget_frame, command=error_text_widget.yview)
    error_text_scrollbar.pack(side="right", fill="y")
    error_text_widget.config(yscrollcommand=error_text_scrollbar.set)

    main_frame.columnconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=0)
    main_frame.columnconfigure(2, weight=0)
    main_frame.rowconfigure(1, weight=1)
    main_frame.rowconfigure(2, weight=1)

    return root, text_widget, error_text_widget, file_label, pin_button


def save_window_size(root):
    config = configparser.ConfigParser()
    config['Window'] = {
        'width': root.winfo_width(),
        'height': root.winfo_height(),
        'x': root.winfo_x(),
        'y': root.winfo_y()
    }
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


def load_window_size(root):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if 'Window' in config:
            width = config.getint('Window', 'width', fallback=600)
            height = config.getint('Window', 'height', fallback=400)
            x = config.getint('Window', 'x', fallback=100)
            y = config.getint('Window', 'y', fallback=100)
            root.geometry(f'{width}x{height}+{x}+{y}')


def toggle_pin(root, pin_button):
    if root.attributes('-topmost'):
        root.attributes('-topmost', False)
        pin_button.config(text="Pin")
    else:
        root.attributes('-topmost', True)
        pin_button.config(text="Unpin")


def minimize_to_tray(root):
    root.withdraw()
    show_tray_icon(root)


def show_window_from_tray(root, pin_button):
    root.deiconify()
    root.attributes('-topmost', True)
    root.attributes('-topmost', False)
    pin_button.config(text="Unpin" if root.attributes('-topmost') else "Pin")


def on_quit(root):
    save_window_size(root)
    root.destroy()


def show_tray_icon(root):
    def on_exit(icon, item):
        icon.stop()
        root.quit()

    def show_window(icon, item):
        icon.stop()
        show_window_from_tray(root, pin_button)

    menu = (pystray.MenuItem('Открыть', show_window), pystray.MenuItem('Выход', on_exit))
    image = Image.new('RGB', (64, 64), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 64, 64), fill=(255, 0, 0))

    icon = pystray.Icon("test_icon", image, "Test", menu)
    icon.run_detached()


def monitor_directory(directory, word, text_widget, error_text_widget, file_label, event_queue):
    event_handler = FileChangeHandler(directory, word, text_widget, error_text_widget, file_label, event_queue)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()

    try:
        while True:
            event_handler.copy_files_from_A()
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    root, text_widget, error_text_widget, file_label, pin_button = create_text_window()

    event_queue = queue.Queue()
    directory = r'C:\TestLogs'
    word = 'ERR'

    threading.Thread(target=monitor_directory,
                     args=(directory, word, text_widget, error_text_widget, file_label, event_queue),
                     daemon=True).start()

    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))
    root.mainloop()
