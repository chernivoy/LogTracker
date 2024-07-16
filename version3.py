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

CONFIG_FILE = "window_config.ini"
tray_icon = None
root = None

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
        root.after(0, restore_window)





def create_text_window():
    ctk.set_appearance_mode("dark")
    global root
    root = ctk.CTk()
    root.title("Logs")
    root.attributes('-topmost', True)
    # root.geometry("800x600")
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    pin_button = ctk.CTkButton(main_frame, text="Pin", command=lambda: toggle_pin(root, pin_button))
    pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

    error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=4, wrap="word", state="disabled")
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)
    error_text_widget_frame.grid_columnconfigure(0, weight=1)
    error_text_widget_frame.grid_rowconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic.png")

    toggle_button = ctk.CTkButton(main_frame, image=icon_image, command=lambda: show_context_menu(root))
    toggle_button.image = icon_image
    toggle_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")

    return root, text_widget, error_text_widget, file_label


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
    config.read(CONFIG_FILE)
    if 'Window' in config:
        width = config.getint('Window', 'width', fallback=800)
        height = config.getint('Window', 'height', fallback=600)
        x = config.getint('Window', 'x', fallback=100)
        y = config.getint('Window', 'y', fallback=100)
        root.geometry(f'{width}x{height}+{x}+{y}')

def create_image_with_text(text, width=64, height=64, font_size=40):
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('arial.ttf', font_size)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2
    draw.text((text_x, text_y), text, font=font, fill=(0, 0, 0, 255))
    return image

def on_quit(icon, item):
    global root
    icon.stop()
    root.quit()

def show_context_menu(event):
    context_menu.post(event.x_root, event.y_root)

def minimize_to_tray(window):
    global tray_icon
    window.withdraw()
    if not tray_icon:
        tray_icon = pystray.Icon("test")
        tray_icon.icon = create_image_with_text("E")
        tray_icon.menu = pystray.Menu(pystray.MenuItem("Open", lambda: restore_window()),
                                      pystray.MenuItem("Exit", on_quit))
        tray_icon.run()

def restore_window():
    global root
    root.after(0, root.deiconify)

def toggle_pin(root, pin_button):
    if root.attributes('-topmost'):
        root.attributes('-topmost', False)
        pin_button.configure(text="Pin")
    else:
        root.attributes('-topmost', True)
        pin_button.configure(text="Unpin")


def monitor_directory(directory, word, text_widget, error_text_widget, file_label):
    event_queue = queue.Queue()
    handler = FileChangeHandler(directory, word, text_widget, error_text_widget, file_label, event_queue)
    observer = Observer()
    observer.schedule(handler, directory, recursive=True)
    observer.start()

    def process_events():
        while True:
            try:
                event = event_queue.get_nowait()
                event()
            except queue.Empty:
                break
        root.after(1000, process_events)

    root.after(1000, process_events)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main(directory, word):
    global root
    root, text_widget, error_text_widget, file_label = create_text_window()
    monitor_thread = threading.Thread(target=monitor_directory, args=(directory, word, text_widget, error_text_widget, file_label))
    monitor_thread.daemon = True
    monitor_thread.start()
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))
    root.mainloop()

if __name__ == "__main__":
    directory = r"C:\temp\logger"
    word = "ERR"
    main(directory, word)
