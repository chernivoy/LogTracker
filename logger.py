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
from PIL import Image, ImageDraw, ImageFont, ImageTk
from tkinter import PhotoImage
import customtkinter as ctk
from ctypes import windll

import config_manager
from config_manager import ConfigManager
from tray_manager import TrayManager


# tray_icon = None
# root = None
# is_window_open = False

# Установка DPI-осведомленности
windll.shcore.SetProcessDpiAwareness(2)

# Получить абсолютный путь к ресурсу, работает для разработки и для PyInstaller
def resource_path(relative_path):
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


config_path = resource_path('src/config.ini')
# config_path = resource_path(r'C:\ChernivoyPersonaldata\log\src\config.ini')
# window_config_path = resource_path(r'C:\ChernivoyPersonaldata\log\src\window_config.ini')
# window_config_path = resource_path('src/window_config.ini')

# window_config_path = config_manager.CONFIG_FILE_WINDOW

config = configparser.ConfigParser()
config.read(config_path)


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
    def __init__(self, _app, directory, word, error_text_widget, file_label, event_queue, _config):
        self.app = _app  # Сохраняем экземпляр приложения
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
        self.track_files()
        self.create_directory_if_not_exists(directory)

    def track_files(self):
        print("Tracking .log files in the directory:", self.directory)
        try:
            for file_name in os.listdir(self.directory):
                file_path = os.path.join(self.directory, file_name)
                if file_name.endswith(".log") and self.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
                    self.last_update_time[file_path] = -1
                    print(f"File added for tracking: {file_path}")
        except PermissionError as e:
            print(f"Ошибка доступа: {e}")
        except FileNotFoundError as e:
            print(f"Файл не найден: {e}")
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

    def copy_files_from_source_dir(self):

        source_directory = self.config.get('Settings', 'source_directory')
        try:
            self.create_directory_if_not_exists(self.directory)

            copied = False

            for filename in os.listdir(source_directory):
                if filename.endswith('.log'):
                    source_file = os.path.join(source_directory, filename)
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
                    source_file = os.path.join(source_directory, filename)
                    if not os.path.exists(source_file):
                        os.remove(dest_file)
                        print(f'Удален файл {filename} из {self.directory}, так как он не существует в {source_directory}')
                        copied = True

            if copied:
                print(f'Завершено копирование из {source_directory} в {self.directory}.')
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
            self.event_queue.put(lambda: self.file_label.configure(font=("Inter", 13), text=f"File: {file_name}"))
            print(f"Новая строка с ошибкой: {last_error_line}")
            self.error_text_widget.configure(state=tk.NORMAL)
            self.error_text_widget.delete(1.0, tk.END)
            self.error_text_widget.insert(tk.END, last_error_line + "\n")
            self.error_text_widget.configure(state=tk.DISABLED)
            if not self.app.is_window_open:  # Используем атрибут из LogTrackerApp
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
        if not self.app.is_window_open:
            self.app.root.after(0, lambda: TrayManager.restore_window(self.app.root, self.app))
            self.app.is_window_open = True


class GUIManager:
    @staticmethod
    def toggle_overrideredirect(root):
        current_state = root.overrideredirect()
        root.overrideredirect(not current_state)
        if not current_state:
            GUIManager.round_corners(root, 30)

    def round_corners(root, radius=30):
        """Скругляет углы окна."""
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, root.winfo_width(), root.winfo_height(), radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)

    @staticmethod
    def remove_maximize_button(root):
        """
        Убирает кнопку "Развернуть" в окне.
        """
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
    def create_text_window():
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        # global root
        root = ctk.CTk()

        root.attributes('-alpha', 0.95)

        # root.attributes('-toolwindow', True)
        # root.wm_attributes('-transparentcolor', 'grey')

        root.title("LogTracker")
        root.minsize(300, 100)
        # root.iconbitmap('src/Header.ico')
        root.iconbitmap(r'C:\ChernivoyPersonaldata\log\src\Header.ico')
        root.attributes('-topmost', True)

        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))

        ConfigManager.load_window_size('Window', root)
        GUIManager.toggle_overrideredirect(root)


        main_frame = ctk.CTkFrame(root, fg_color="#2a2d30")
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        file_label = ctk.CTkLabel(main_frame, text="File: ", anchor="w", text_color="#5f8dfc", font=("Inter", 13))
        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")


        # close
        to_tray_button = ctk.CTkButton(main_frame,
                                      text="x", height=20, width=20,
                                       fg_color="transparent",
                                       text_color="#ce885f",
                                      command=lambda: TrayManager.minimize_to_tray(root, app))

        to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")


        burger_button = ctk.CTkButton(main_frame,
                                      text="...", height=20, width=20,
                                      fg_color="transparent",
                                      text_color="#ce885f",
                                      command=lambda: GUIManager.show_context_menu(root, app))

        burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

        error_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame, fg_color="transparent")
        error_text_widget_frame.pack(fill="both", expand=True)

        # Настройка виджета CTkTextbox без скроллбара
        error_text_widget = ctk.CTkTextbox(
            error_text_widget_frame,
            height=20,  # Устанавливаем достаточную высоту, чтобы избежать появления скроллбара
            corner_radius=1,
            border_width=0,
            fg_color="transparent",
            wrap="word",
            state="disabled",  # Блокируем виджет для предотвращения появления скроллбара
            text_color="#b4b361",
            font=("Inter", 13),
            yscrollcommand=lambda *args: None  # Отключаем вертикальный скроллбар
        )


        # border_color="blue"
        error_text_widget.pack(fill="both", expand=True, padx=5, pady=5)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        GUIManager.remove_maximize_button(root)

        # Привязка событий для перемещения окна
        file_label.bind("<ButtonPress-1>", lambda event: GUIManager.start_move(event, root))
        file_label.bind("<B1-Motion>", lambda event: GUIManager.do_move(event, root))

        return root, error_text_widget, file_label

    @staticmethod
    def start_move(event, root):
        """Запоминаем начальные координаты курсора и окна."""
        root.start_x = event.x
        root.start_y = event.y

    @staticmethod
    def do_move(event, root):
        """Перемещаем окно в зависимости от движения курсора."""
        x = root.winfo_x() + event.x - root.start_x
        y = root.winfo_y() + event.y - root.start_y
        root.geometry(f"+{x}+{y}")


    @staticmethod
    def open_settings_window(app):
        settings_window = ctk.CTkToplevel(app.root)
        settings_window.title("Path settings")

        ConfigManager.load_window_size('Window_path', settings_window)
        settings_window.minsize(400, 270)

        settings_window.grab_set()  # Окно настроек становится модальным

        # Метки
        label_source_directory = ctk.CTkLabel(settings_window, text="Path to source directory:")
        label_source_directory.pack(pady=10)

        # Текстовые поля
        entry_source_directory = ctk.CTkEntry(settings_window, width=300)
        entry_source_directory.insert(0, app.source_directory)
        entry_source_directory.pack(pady=5)

        label_target_directory = ctk.CTkLabel(settings_window, text="Path to destination directory:")
        label_target_directory.pack(pady=10)

        entry_target_directory = ctk.CTkEntry(settings_window, width=300)
        entry_target_directory.insert(0, app.directory)
        entry_target_directory.pack(pady=5)

        # Кнопка "Сохранить"
        btn_save = ctk.CTkButton(
            settings_window,
            text="Save",
            command=lambda: GUIManager.save_settings(
                app,
                settings_window,
                entry_source_directory.get(),
                entry_target_directory.get()

            )
        )
        btn_save.pack(pady=10)

        # Кнопка "Отмена"
        btn_cancel = ctk.CTkButton(
            settings_window,
            text="Cancel",
            command=settings_window.destroy
        )
        btn_cancel.pack(pady=5)

        settings_window.bind("<Configure>",
                             lambda event: ConfigManager.save_window_size('Window_path', settings_window))

    @staticmethod
    def save_settings(app, settings_window, source_directory, target_directory):
        # Сохраняем пути в конфигурационный файл
        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'directory', target_directory)

        with open(config_path, 'w') as configfile:
            app.config.write(configfile)

        # Обновляем атрибуты в LogTrackerApp
        app.source_directory = source_directory
        app.directory = target_directory

        ConfigManager.save_window_size('Window_path', settings_window)
        settings_window.destroy()

    @staticmethod
    def show_context_menu(root, app):
        context_menu = tk.Menu(root, tearoff=0, bg="#2b2b2b", fg="#dde3ee")
        context_menu.add_command(label="To tray", command=lambda: TrayManager.minimize_to_tray(root, app))
        context_menu.add_command(label=f"Pin/Unpin", command=lambda: TrayManager.toggle_pin(root))
        context_menu.add_command(label="Window border", command=lambda: GUIManager.toggle_overrideredirect(root))
        context_menu.add_command(label="Path settings",
                                 command=app.open_settings_window)  # Добавляем вызов окна настроек
        context_menu.add_command(label="Exit", command=app.on_closing)
        context_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())


class LogTrackerApp:
    def __init__(self):
        # Загрузка конфигурации
        self.config = ConfigManager.load_config(config_path)

        # Инициализация директорий из конфигурации или установка значений по умолчанию, если их нет
        self.directory = self.config.get('Settings', 'directory', fallback='')
        self.source_directory = self.config.get('Settings', 'source_directory', fallback='')
        self.word = self.config.get('Settings', 'word', fallback='')

        # Инициализация других атрибутов
        self.observer = None
        self.root, self.error_text_widget, self.file_label = GUIManager.create_text_window()
        self.event_queue = queue.Queue()
        self.event_handler = FileChangeHandler(self, self.directory, self.word, self.error_text_widget,
                                               self.file_label, self.event_queue, self.config)  # Передаем self в FileChangeHandler

        # Привязка событий
        self.error_text_widget.bind("<Double-Button-1>", self.on_error_double_click)
        self.root.bind("<Configure>", self.on_window_resize)
        self.is_window_open = True
        self.tray_icon = None



        ConfigManager.load_window_size('Window', self.root)

    def open_settings_window(self):
        GUIManager.open_settings_window(self)

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
        self.event_handler.copy_files_from_source_dir()
        self.root.after(2000, self.periodic_sync)

    def on_closing(self):
        def _safe_closing():
            try:
                print("Closing application...")
                ConfigManager.save_window_size('Window', self.root)
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
        ConfigManager.save_window_size('Window', self.root)


if __name__ == "__main__":
    app = LogTrackerApp()
    app.run()
