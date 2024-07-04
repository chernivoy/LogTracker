import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
    def __init__(self, directory, word):
        self.directory = directory
        self.word = word
        self.file_paths = {}
        self.last_error_lines = set()  # Для отслеживания уже выведенных строк с ошибками
        self.track_files()
        self.create_directory_if_not_exists(directory)

    def track_files(self):
        print("Отслеживание .log файлов в директории:", self.directory)
        try:
            for file_name in os.listdir(self.directory):
                file_path = os.path.join(self.directory, file_name)
                if file_name.endswith(".log") and self.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
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
                file.seek(0, os.SEEK_END)  # Убедимся, что можем перемещаться в конец файла
            return True
        except IOError as e:
            print(f"Файл {file_path} в данный момент используется: {e}")
            return False

    def wait_for_file(self, file_path, timeout=30):
        """Ожидание доступности файла для чтения."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_file_closed(file_path):
                return True
            time.sleep(1)
        print(f"Файл {file_path} все еще используется после {timeout} секунд.")
        return False

    def copy_files_from_A(self):
        directory_A = r'C:\ProgramData\ADAICA Schweiz AG\ADAICA\Logs\ichernevoy'  # Путь к директории A
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
                        else:
                            if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                                copy_file_without_waiting(source_file, dest_file)
                                print(f'Обновлен файл {filename} в {self.directory}')
                                copied = True
                    else:
                        print(f'Файл {source_file} в данный момент используется и не может быть скопирован.')

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
        except Exception as e:
            print(f"Ошибка при копировании файлов из директории A: {e}")

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
            time.sleep(1)
            with open(file_path, 'r', encoding='utf-8') as file:
                file.seek(self.file_paths[file_path])
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
                new_lines = self.read_new_lines(event.src_path)
                for line in new_lines:
                    if line.strip().startswith(self.word) and line not in self.last_error_lines:
                        print(f"Новая строка с ошибкой: {line.strip()}")
                        self.last_error_lines.add(line)  # Добавляем новую строку в множество

                directory_A = r'C:\ProgramData\ADAICA Schweiz AG\ADAICA\Logs\ichernevoy'
                filename = os.path.basename(event.src_path)
                source_file = os.path.join(directory_A, filename)
                dest_file = os.path.join(self.directory, filename)
                if os.path.exists(dest_file) and os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                    copy_file_without_waiting(source_file, dest_file)
                    print(f'Обновлен файл {filename} в {self.directory}')

    def on_deleted(self, event):
        if event.src_path in self.file_paths:
            del self.file_paths[event.src_path]

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]

def main(directory, word):
    event_handler = FileChangeHandler(directory, word)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=False)
    observer.start()

    try:
        while True:
            event_handler.copy_files_from_A()
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    directory = r"C:\temp\logger"
    word = "ERR"
    main(directory, word)
