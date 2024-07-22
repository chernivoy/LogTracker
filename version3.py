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


def toggle_overrideredirect(root):
    current_state = root.overrideredirect()
    root.overrideredirect(not current_state)




def create_text_window():
    ctk.set_appearance_mode("dark")
    global root
    root = ctk.CTk()
    root.title("Logs")


    root.attributes('-topmost', True)
    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    load_window_size(root)

    # Убираем кнопки минимизации и максимизации


    main_frame = ctk.CTkFrame(root)
    main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    burger_button = ctk.CTkButton(main_frame, text="...", height=20, width=20, fg_color="blue", command=lambda: show_context_menu(root))
    burger_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

    # pin_button = ctk.CTkButton(main_frame, text="Unpin", height=20, width=20, fg_color="blue", command=lambda: toggle_pin(root, pin_button))
    # pin_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")
    #
    # minimize_button = ctk.CTkButton(main_frame, text="To Tray", height=20, width=20,command=lambda: minimize_to_tray(root))
    # minimize_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")

    file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
    file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    error_frame = ctk.CTkFrame(main_frame)
    error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

    # error_label = ctk.CTkLabel(error_frame, text="ERR:", anchor="w")
    # error_label.pack(side="left", padx=(10, 0))

    error_text_widget_frame = ctk.CTkFrame(error_frame)
    error_text_widget_frame.pack(fill="both", expand=True)

    error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=80, corner_radius=20, border_width=1, border_color="blue", wrap="word", state="disabled")
    error_text_widget.pack(fill="both", expand=True, padx=5)

    text_widget_frame = ctk.CTkFrame(main_frame)
    text_widget_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)
    text_widget_frame.grid_remove()  # Скрываем frame сразу после создания

    text_widget = ctk.CTkTextbox(text_widget_frame, wrap="none")
    text_widget.pack(fill="both", expand=True)

    # Настройка растягивания для окна и фреймов
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    main_frame.grid_rowconfigure(0, weight=0)
    main_frame.grid_rowconfigure(1, weight=1)
    main_frame.grid_rowconfigure(2, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)

    error_frame.grid_rowconfigure(0, weight=1)
    error_frame.grid_columnconfigure(0, weight=1)

    text_widget_frame.grid_rowconfigure(0, weight=1)
    text_widget_frame.grid_columnconfigure(0, weight=1)

    icon_image = PhotoImage(file="err_pic4.png")
    # icon_image = ImageTk.
    icon_width = icon_image.width()  # Ширина иконки
    icon_height = icon_image.height()  # Высота иконки

    # toggle_button = ctk.CTkButton(main_frame, image=icon_image, text="", height=icon_height, width=icon_width,
    #                               fg_color="#1a1a1a", corner_radius=40, border_width=1, border_color="blue", command=lambda: show_context_menu(root))
    # toggle_button.image = icon_image
    # toggle_button.grid(row=1, column=2, padx=(5, 0), pady=5, sticky="ne")

    # icon_image2 = PhotoImage(file="err_pic4.png")
    # toggle_button2 = ctk.CTkButton(main_frame, image= icon_image2,  text="", height=32, width=32,
    #                               fg_color="#1a1a1a", corner_radius=40, command=lambda: show_context_menu(root))
    #
    # toggle_button2.grid(row=3, column=3, padx=(5, 0), pady=5, sticky="ne")
    #
    # error_button = ctk.CTkButton(main_frame, height=16, width=16, image=icon_image2, text="", command=lambda: show_context_menu(root))
    # error_button.grid(row=3, column=1, padx=(5, 0), pady=5, sticky="ne")
    # text_widget_frame.grid()

    return root, text_widget, error_text_widget, file_label









def on_closing():
    save_window_size(root)
    observer.stop()
    observer.join()
    root.quit()


def save_window_size(root):
    # Получаем коэффициент масштабирования DPI
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    dpi_scale = user32.GetDpiForWindow(root.winfo_id()) / 96.0

    # Корректируем ширину и высоту с учетом масштаба DPI
    width = int(root.winfo_width() / dpi_scale)
    height = int(root.winfo_height() / dpi_scale)

    config = configparser.ConfigParser()
    config['Window'] = {
        'width': width,
        'height': height,
        'x': root.winfo_x(),
        'y': root.winfo_y()
    }

    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

def show_context_menu(root):
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="Pin/Unpin", command=lambda: toggle_pin(root, None))
    context_menu.add_command(label="Свернуть в трей", command=lambda: minimize_to_tray(root))
    context_menu.add_command(label="Window border", command=lambda: toggle_overrideredirect(root))
    context_menu.add_command(label="Выйти", command=lambda: on_closing())
    context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())


def load_window_size(root):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if 'Window' in config:
            width = config.getint('Window', 'width', fallback=800)
            height = config.getint('Window', 'height', fallback=600)
            x = config.getint('Window', 'x', fallback=100)
            y = config.getint('Window', 'y', fallback=100)
            root.geometry(f'{width}x{height}+{x}+{y}')

    else:
        root.geometry('800x600+100+100')


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

def on_quit(icon, item):
    global root
    icon.stop()
    root.quit()

def show_context_menu(root):
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="Pin/Unpin", command=lambda: toggle_pin(root, None))
    context_menu.add_command(label="Свернуть в трей", command=lambda: minimize_to_tray(root))
    context_menu.add_command(label="Window border", command=lambda: toggle_overrideredirect(root))
    context_menu.add_command(label="Выйти", command=lambda: on_closing())
    context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())

def open_file(file_path):
    try:
        if os.name == 'nt':  # Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # macOS, Linux
            subprocess.call(('xdg-open', file_path))
    except Exception as e:
        print(f"Не удалось открыть файл {file_path}: {e}")
def minimize_to_tray(root):
    global tray_icon

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

    def on_click(icon, item):
        root.after(0, icon.stop)
        restore_window()

    def on_quit(icon, item):
        save_window_size(root)
        observer.stop()
        observer.join()
        icon.stop()
        root.quit()

    menu = (
        pystray.MenuItem('Открыть', on_click),
        pystray.MenuItem('Выход', on_quit)

    )
    icon_image = create_image(64, 64, 'black', 'white')
    tray_icon = pystray.Icon("test", icon_image, "Файлы в целевой директории", menu)
    root.withdraw()
    tray_icon.run_detached()

def restore_window():
    global tray_icon
    root.deiconify()
    root.lift()
    if tray_icon:
        tray_icon.stop()
        tray_icon = None

def toggle_pin(root, pin_button):
    if root.attributes('-topmost'):
        root.attributes('-topmost', False)
        if pin_button:
            pin_button.configure(text="Pin")
    else:
        root.attributes('-topmost', True)
        if pin_button:
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
            time.sleep(0.2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main(directory, word):
    global observer
    global root
    root, text_widget, error_text_widget, file_label = create_text_window()
    event_queue = queue.Queue()

    event_handler = FileChangeHandler(directory, word, text_widget, error_text_widget, file_label, event_queue)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()

    def process_queue():
        try:
            while True:
                event = event_queue.get_nowait()
                event()
        except queue.Empty:
            pass
        root.after(100, process_queue)

    def periodic_sync():
        event_handler.copy_files_from_A()
        root.after(5000, periodic_sync)

    def on_closing():
        save_window_size(root)
        observer.stop()
        observer.join()
        root.quit()

    def on_error_double_click(event):
        if event_handler.last_error_file:
            open_file(event_handler.last_error_file)

    error_text_widget.bind("<Double-Button-1>", on_error_double_click)

    root.after(100, process_queue)
    root.after(5000, periodic_sync)

    root.protocol("WM_DELETE_WINDOW", lambda: minimize_to_tray(root))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    directory = r"C:\temp\logger"
    word = "ERR"
    main(directory, word)
