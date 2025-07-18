import os
import time
import queue
import tkinter as tk
import subprocess

from watchdog.events import FileSystemEventHandler

from file_handler import FileHandler
from tray_manager import TrayManager


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, _app, directory, word, error_text_widget, file_label, event_queue, _config):
        self.app = _app
        self.directory = directory
        self.word = word
        self.error_text_widget = error_text_widget
        self.file_label = file_label
        self.event_queue = event_queue
        self.config = _config
        self.file_paths = {}
        self.last_error_file = None
        self.last_error_line = {}
        self.last_update_time = {}
        self.create_directory_if_not_exists(directory)
        self.track_files()

    def track_files(self):
        print("Tracking .log files in the directory:", self.directory)
        try:
            for file_name in os.listdir(self.directory):
                file_path = os.path.join(self.directory, file_name)
                if file_name.endswith(".log") and FileChangeHandler.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
                    self.last_update_time[file_path] = -1
                    print(f"File added for tracking: {file_path}")
        except Exception as e:
            print(f"Ошибка при перечислении файлов в директории: {e}")

    @staticmethod
    def create_directory_if_not_exists(directory):
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Создана директория: {directory}")
            except Exception as e:
                print(f"Ошибка при создании директории {directory}: {e}")

    @staticmethod
    def is_file_closed(file_path):
        try:
            with open(file_path, 'rb') as file:
                file.seek(0, os.SEEK_END)
            return True
        except IOError as e:
            print(f"Файл {file_path} в данный момент используется: {e}")
            return False

    @staticmethod
    def wait_for_file(file_path, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if FileChangeHandler.is_file_closed(file_path):
                return True
        print(f"Файл {file_path} все еще используется после {timeout} секунд.")
        return False

    def copy_files_from_source_dir(self):
        source_directory = self.config.get('Settings', 'source_directory')
        try:
            self.create_directory_if_not_exists(self.directory)
            copied = False
            for filename in os.listdir(source_directory):
                if filename.endswith('.log'):
                    source_file = os.path.join(source_directory, filename)
                    dest_file = os.path.join(self.directory, filename)

                    if FileChangeHandler.wait_for_file(source_file):
                        if not os.path.exists(dest_file):
                            FileHandler.copy_file_without_waiting(source_file, dest_file)
                            print(f'Скопирован файл {filename} из директории A в {self.directory}')
                            copied = True
                            self.check_new_errors(dest_file)
                        else:

                            if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                                FileHandler.copy_file_without_waiting(source_file, dest_file)
                                print(f'Обновлен файл {filename} в {self.directory}')
                                copied = True
                                self.check_new_errors(dest_file)
            for filename in os.listdir(self.directory):
                if filename.endswith('.log'):
                    dest_file = os.path.join(self.directory, filename)
                    source_file = os.path.join(source_directory, filename)
                    if not os.path.exists(source_file):
                        os.remove(dest_file)
                        print(
                            f'Удален файл {filename} из {self.directory}, так как он не существует в {source_directory}')
                        copied = True
            if copied:
                print(f'Завершено копирование из {source_directory} в {self.directory}.')
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
            self.event_queue.put(lambda: self.file_label.configure(font=("Inter", 13), text=f"File: {file_name}"))
            print(f"Новая строка с ошибкой: {last_error_line}")
            self.error_text_widget.configure(state=tk.NORMAL)
            self.error_text_widget.delete(1.0, tk.END)
            self.error_text_widget.insert(tk.END, last_error_line + "\n")
            self.error_text_widget.configure(state=tk.DISABLED)
            if not self.app.is_window_open:
                self.event_queue.put(self.show_window_from_tray)

    @staticmethod
    def can_read_file(file_path):
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

    def on_deleted(self, event):
        if event.src_path in self.file_paths:
            del self.file_paths[event.src_path]
            print(f"Файл {event.src_path} был удален.")

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]

    def show_window_from_tray(self):
        if not self.app.is_window_open:
            self.app.root.after(0, lambda: TrayManager.restore_window(self.app.root, self.app))
            self.app.is_window_open = True
