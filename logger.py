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
is_window_open = False

# Установка DPI-осведомленности
windll.shcore.SetProcessDpiAwareness(2)


class ConfigManager:
    @staticmethod
    def load_config(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        return config

    @staticmethod
    def save_window_size(root):
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        dpi_scale = user32.GetDpiForWindow(root.winfo_id()) / 96.0

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

    @staticmethod
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


class FileHandler:
    @staticmethod
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

    @staticmethod
    def open_file(file_path):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS, Linux
                subprocess.call(('xdg-open', file_path))
        except Exception as e:
            print(f"Не удалось открыть файл {file_path}: {e}")


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, directory, word, error_text_widget, file_label, event_queue, config):
        self.directory = directory
        self.word = word
        self.error_text_widget = error_text_widget
        self.file_label = file_label
        self.event_queue = event_queue
        self.config = config  # Сохраните объект конфигурации
        self.file_paths = {}
        self.last_error_file = None
        self.last_error_line = {}
        self.last_update_time = {}
        self.track_files()
        self.create_directory_if_not_exists(directory)

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

        directory_A = self.config.get('Settings', 'directory_A')
        try:
            self.create_directory_if_not_exists(self.directory)

            copied = False

            for filename in os.listdir(directory_A):
                if filename.endswith('.log'):
                    source_file = os.path.join(directory_A, filename)
                    dest_file = os.path.join(self.directory, filename)
                    if self.wait_for_file(source_file):
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
                    source_file = os.path.join(directory_A, filename)
                    if not os.path.exists(source_file):
                        os.remove(dest_file)
                        print(f'Удален файл {filename} из {self.directory}, так как он не существует в {directory_A}')
                        copied = True

            if copied:
                print(f'Завершено копирование из {directory_A} в {self.directory}.')
                # self.event_queue.put(self.update_text_widget)
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
            if not is_window_open:  # Проверка состояния окна
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
                # self.event_queue.put(self.update_text_widget)

    def on_deleted(self, event):
        if event.src_path in self.file_paths:
            del self.file_paths[event.src_path]
            print(f"Файл {event.src_path} был удален.")
            #self.event_queue.put(self.update_text_widget)

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]

    def show_window_from_tray(self):
        global is_window_open
        if not is_window_open:
            root.after(0, TrayManager.restore_window)
            is_window_open = True


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
    def on_quit(icon, item):
        global root
        print("Quitting application from tray...")
        if app.observer:
            print("Stopping observer from tray...")
            app.observer.stop()
            app.observer.join(timeout=5)  # Ждем 5 секунд для завершения
            if app.observer.is_alive():
                print("Observer is still running. Force stopping from tray...")
                app.observer = None  # Принудительно освобождаем объект наблюдателя
            else:
                print("Observer stopped successfully from tray.")
        icon.stop()
        root.after(0, app.on_closing)  # Вызываем on_closing в основном потоке

    @staticmethod
    def show_context_menu(root, app):
        context_menu = tk.Menu(root, tearoff=0, bg="#2b2b2b", fg="#dde3ee")
        context_menu.add_command(label="Pin/Unpin", command=lambda: TrayManager.toggle_pin(root, None))
        context_menu.add_command(label="Свернуть в трей", command=lambda: TrayManager.minimize_to_tray(root, app))
        context_menu.add_command(label="Window border", command=lambda: GUIManager.toggle_overrideredirect(root))
        context_menu.add_command(label="Выйти", command=app.on_closing)
        context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())

    @staticmethod
    def minimize_to_tray(root, app):
        global is_window_open
        global tray_icon
        is_window_open = False

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

        def on_open(icon, item):
            root.after(0, icon.stop)
            TrayManager.restore_window()

        menu = (
            pystray.MenuItem('Открыть', on_open),
            pystray.MenuItem('Выход', TrayManager.on_quit)
        )
        icon_image = create_image(64, 64, 'black', 'blue')
        tray_icon = pystray.Icon("test", icon_image, "LogTracker for ADAICA", menu)
        root.withdraw()
        tray_icon.run_detached()

    @staticmethod
    def restore_window():
        global root
        global is_window_open
        if TrayManager.check_rdp_status():
            windll.shcore.SetProcessDpiAwareness(2)  # Установите DPI-осведомленность при восстановлении окна
        else:
            windll.shcore.SetProcessDpiAwareness(1)  # Установите DPI-осведомленность по умолчанию

        ConfigManager.load_window_size(root)  # Перечитываем размеры окна из файла конфигурации
        root.deiconify()
        is_window_open = True  # Обновляем состояние окна
        root.lift()
        if tray_icon:
            tray_icon.visible = False

    @staticmethod
    def check_rdp_status():
        SM_REMOTESESSION = 0x1000
        return ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION) != 0

    @staticmethod
    def toggle_pin(root, pin_button):
        if root.attributes('-topmost'):
            root.attributes('-topmost', False)
            if pin_button:
                pin_button.configure(text="Pin")
        else:
            root.attributes('-topmost', True)
            if pin_button:
                pin_button.configure(text="Unpin")


class GUIManager:
    @staticmethod
    def toggle_overrideredirect(root):
        current_state = root.overrideredirect()
        root.overrideredirect(not current_state)

    @staticmethod
    def remove_window_buttons(root):
        # Получаем дескриптор окна
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())

        # Получаем текущие стили окна
        styles = ctypes.windll.user32.GetWindowLongW(hwnd, -16)

        # Убираем стили для кнопок Minimize и Maximize
        styles &= ~0x00020000  # WS_MINIMIZEBOX
        styles &= ~0x00010000  # WS_MAXIMIZEBOX

        # Применяем измененные стили
        ctypes.windll.user32.SetWindowLongW(hwnd, -16, styles)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0040 | 0x0100)  # SWP_NOSIZE | SWP_NOMOVE

    @staticmethod
    def create_text_window1():
        ctk.set_appearance_mode("dark")
        global root
        root = ctk.CTk()

        root.title("LogTracker")
        root.minsize(353, 133)

        root.iconbitmap('2.ico')

        root.attributes('-topmost', True)
        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))

        ConfigManager.load_window_size(root)

        main_frame = ctk.CTkFrame(root)
        main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
        file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

        burger_button = ctk.CTkButton(main_frame, text="...", height=20, width=20, fg_color="blue",
                                      command=lambda: TrayManager.show_context_menu(root, app))  # Обновлено

        burger_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        error_frame = ctk.CTkFrame(main_frame)
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame)
        error_text_widget_frame.pack(fill="both", expand=True)

        error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=10, corner_radius=20, border_width=1,
                                           border_color="blue", wrap="word", state="disabled")
        error_text_widget.pack(fill="both", expand=True, padx=1, pady=1)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        return root, error_text_widget, file_label


    def create_text_window():
        ctk.set_appearance_mode("dark")
        global root
        root = ctk.CTk()

        root.title("LogTracker")
        root.minsize(353, 133)

        root.iconbitmap('2.ico')

        root.attributes('-topmost', True)
        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))

        ConfigManager.load_window_size(root)

        main_frame = ctk.CTkFrame(root)
        main_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w")
        file_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

        burger_button = ctk.CTkButton(main_frame,
                                      text="...", height=20, width=20, fg_color="blue",
                                      command=lambda: TrayManager.show_context_menu(root, app))

        burger_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        error_frame = ctk.CTkFrame(main_frame)
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame)
        error_text_widget_frame.pack(fill="both", expand=True)

        error_text_widget = ctk.CTkTextbox(error_text_widget_frame, height=10, corner_radius=20, border_width=1,
                                           border_color="blue", wrap="word", state="disabled")
        error_text_widget.pack(fill="both", expand=True, padx=1, pady=1)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        return root, error_text_widget, file_label


class LogTrackerApp:
    def __init__(self):
        self.config = ConfigManager.load_config("config.ini")
        self.directory = self.config.get('Settings', 'directory')
        self.word = self.config.get('Settings', 'word')
        self.observer = None
        self.root, self.error_text_widget, self.file_label = GUIManager.create_text_window()
        self.event_queue = queue.Queue()
        self.event_handler = FileChangeHandler(self.directory, self.word, self.error_text_widget, self.file_label, self.event_queue, self.config)
        self.error_text_widget.bind("<Double-Button-1>", self.on_error_double_click)

    def run(self):
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.directory, recursive=False)
        self.observer.start()

        self.process_queue()
        self.periodic_sync()

        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, app))
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
        self.event_handler.copy_files_from_A()
        self.root.after(5000, self.periodic_sync)

    def on_closing(self):
        def _safe_closing():
            try:
                print("Closing application...")
                ConfigManager.save_window_size(self.root)
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

        if tray_icon:
            tray_icon.stop()  # Останавливаем иконку в трее

        self.root.after(0, _safe_closing)  # Выполняем _safe_closing в основном потоке

    def on_error_double_click(self, event):
        if self.event_handler.last_error_file:
            FileHandler.open_file(self.event_handler.last_error_file)

    def on_window_resize(self, event):
        ConfigManager.save_window_size(self.root)


if __name__ == "__main__":
    app = LogTrackerApp()
    app.run()
