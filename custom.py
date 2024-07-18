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
tray_icon = None
root = None

# Установка DPI-осведомленности
windll.shcore.SetProcessDpiAwareness(2)

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
            file_name = os.path.basename(file_path)
            self.event_queue.put(lambda: self.file_label.configure(text=f"File: {file_name}"))
            print(f"Новая строка с ошибкой: {last_error_line}")
            self.error_text_widget.configure(state=tk.NORMAL)
            self.error_text_widget.delete(1.0, tk.END)
            self.error_text_widget.insert(tk.END, last_error_line + "\n")
            self.error_text_widget.configure(state=tk.DISABLED)
            self.event_queue.put(self.show_window_from_tray)

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
        self.text_widget.delete(1.0, tk.END)
        for file_path in self.file_paths:
            self.text_widget.insert(tk.END, file_path + "\n")

    def show_window_from_tray(self):
        if root.state() == "withdrawn":
            root.deiconify()

class CustomTkinterApp:
    def __init__(self, root):
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.text_widget = ctk.CTkTextbox(root)
        self.text_widget.pack(fill=ctk.BOTH, expand=True)
        self.error_text_widget = ctk.CTkTextbox(root, height=1)
        self.error_text_widget.pack(fill=ctk.BOTH, expand=True)
        self.file_label = ctk.CTkLabel(root, text="File: ")
        self.file_label.pack()
        self.load_window_size()
        self.word = "ERR"
        self.directory = r'C:\ProgramData\ADAICA Schweiz AG\ADAICA\Logs\ichernevoy'
        self.event_queue = queue.Queue()
        self.event_handler = FileChangeHandler(self.directory, self.word, self.text_widget, self.error_text_widget, self.file_label, self.event_queue)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, path=self.directory, recursive=False)
        self.observer.start()
        self.check_files_thread = threading.Thread(target=self.periodically_check_files, daemon=True)
        self.check_files_thread.start()
        self.process_queue()

    def periodically_check_files(self):
        while True:
            try:
                self.event_handler.copy_files_from_A()
                time.sleep(60)
            except Exception as e:
                print(f"Ошибка при периодической проверке файлов: {e}")

    def process_queue(self):
        while not self.event_queue.empty():
            try:
                task = self.event_queue.get_nowait()
                task()
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Ошибка при обработке очереди: {e}")
        self.root.after(1000, self.process_queue)

    def minimize_to_tray(self):
        self.create_tray_icon()
        self.root.withdraw()

    def create_tray_icon(self):
        icon_image = Image.new("RGB", (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(icon_image)
        font = ImageFont.load_default()
        draw.text((14, 22), "App", font=font, fill=(0, 0, 0))
        self.tray_icon = pystray.Icon("test", icon_image, "App", menu=pystray.Menu(
            pystray.MenuItem("Показать", self.show_window),
            pystray.MenuItem("Выход", self.exit_application)
        ))
        self.tray_icon.run_detached()

    def show_window(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        if self.tray_icon:
            self.tray_icon.stop()

    def exit_application(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.observer.stop()
        self.observer.join()
        self.root.destroy()

    def save_window_size(self):
        config = configparser.ConfigParser()
        config['Window'] = {
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y()
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    def load_window_size(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if 'Window' in config:
                width = int(config['Window'].get('width', self.root.winfo_width()))
                height = int(config['Window'].get('height', self.root.winfo_height()))
                x = int(config['Window'].get('x', self.root.winfo_x()))
                y = int(config['Window'].get('y', self.root.winfo_y()))
                self.root.geometry(f'{width}x{height}+{x}+{y}')
                ctk.deactivate_automatic_dpi_awareness()
                ctk.set_window_scaling(self.root)

if __name__ == "__main__":
    root = ctk.CTk()
    app = CustomTkinterApp(root)
    root.mainloop()
    app.save_window_size()
