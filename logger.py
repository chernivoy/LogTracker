import os
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, directory, word):
        self.directory = directory
        self.word = word
        self.file_paths = {}
        self.track_files()
        self.create_directory_if_not_exists(directory)  # Добавляем проверку и создание директории

    def track_files(self):
        print("Tracking .log files in directory:", self.directory)
        try:
            for file_name in os.listdir(self.directory):
                file_path = os.path.join(self.directory, file_name)
                if file_name.endswith(".log") and self.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
                    print(f"File added for tracking: {file_path}")
        except PermissionError as e:
            print(f"PermissionError: {e}")
        except FileNotFoundError as e:
            print(f"FileNotFoundError: {e}")
        except Exception as e:
            print(f"Error listing files in directory: {e}")

    def create_directory_if_not_exists(self, directory):
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Error creating directory {directory}: {e}")

    def copy_files_from_A(self):
        directory_A = r'C:\temp\loggerA'  # Путь к директории A
        try:
            self.create_directory_if_not_exists(self.directory)  # Проверяем и создаем целевую директорию, если нужно

            copied = False  # Флаг для отслеживания факта копирования файлов
            for filename in os.listdir(directory_A):
                if filename.endswith('.log'):
                    source_file = os.path.join(directory_A, filename)
                    dest_file = os.path.join(self.directory, filename)
                    if not os.path.exists(dest_file):  # Проверяем, что файл не существует в целевой директории
                        shutil.copy2(source_file, dest_file)
                        print(f'Copied {filename} from directory A to {self.directory}')
                        copied = True  # Установка флага при успешном копировании
                    else:
                        # Проверяем, изменился ли файл в директории A по сравнению с целевой директорией
                        if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                            shutil.copy2(source_file, dest_file)
                            print(f'Updated {filename} in {self.directory}')
                            copied = True  # Установка флага при успешном обновлении

            if copied:
                print(f'Copying from {directory_A} to {self.directory} completed.')
        except Exception as e:
            print(f"Error copying files from directory A: {e}")

    def can_read_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8'):
                pass
            return True
        except Exception as e:
            print(f"Cannot read file {file_path}: {e}")
            return False

    def read_new_lines(self, file_path):
        new_lines = []
        current_size = os.path.getsize(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file.seek(self.file_paths[file_path])
                new_lines = file.readlines()
                self.file_paths[file_path] = current_size
        except PermissionError as e:
            print(f"PermissionError: {e}")
        except FileNotFoundError as e:
            print(f"FileNotFoundError: {e}")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
        return new_lines

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".log"):
            if event.event_type == 'deleted':
                self.stop_tracking(event.src_path)
                print(f"File {event.src_path} was deleted. Stopped tracking.")
            else:
                print(f"Modified file: {event.src_path}")
                new_lines = self.read_new_lines(event.src_path)
                for line in new_lines:
                    if line.strip().startswith(self.word):
                        print(f"New ERR line: {line.strip()}")

                # Проверяем, изменился ли файл в директории A и обновляем его в целевой директории при необходимости
                directory_A = r'C:\temp\loggerA'  # Путь к директории A
                filename = os.path.basename(event.src_path)
                source_file = os.path.join(directory_A, filename)
                dest_file = os.path.join(self.directory, filename)
                if os.path.exists(dest_file) and os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                    shutil.copy2(source_file, dest_file)
                    print(f'Updated {filename} in {self.directory}')

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
            # Проверяем наличие новых файлов в директории A и копируем их
            event_handler.copy_files_from_A()
            time.sleep(1)  # Проверяем каждую секунду
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    directory = r"C:\temp\logger"  # Или "C:/path/to/directory"
    word = "ERR"
    main(directory, word)
