import os

from watchdog.events import FileSystemEventHandler

from file_handler import FileHandler


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, _app, destination_directory, word, file_extension, event_queue):
        self.app = _app
        self.destination_directory = destination_directory
        self.word = word
        self.file_extension = file_extension
        self.event_queue = event_queue
        self.file_paths = {}
        self.last_error_file = None
        self.last_update_time = {}
        FileHandler().create_directory_if_not_exists(self.destination_directory)
        self.track_files()

    def track_files(self):
        print(f"Tracking files with {self.file_extension} extension in the directory:", self.destination_directory)
        try:
            for file_name in os.listdir(self.destination_directory):
                file_path = os.path.join(self.destination_directory, file_name)
                if file_name.endswith(self.file_extension) and FileHandler.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
                    self.last_update_time[file_path] = -1
                    print(f"File added for tracking: {file_path}")
        except Exception as e:
            print(f"Error when tracking files: {e}")

    def sync_files_and_check(self, source_directory):
        try:
            copied = FileHandler.copy_files_from_source_dir(source_directory, self.destination_directory)
            if copied:
                for filename in os.listdir(self.destination_directory):
                    if filename.endswith(self.file_extension):
                        self.check_new_errors(os.path.join(self.destination_directory, filename))
        except Exception as e:
            print(f"Error when sync and check files and errors: {e}")

    def check_new_errors(self, file_path):
        new_lines = self.read_new_lines(file_path)
        last_error_line = None
        for line in new_lines:
            if line.strip().startswith(self.word):
                last_error_line = line.strip()

        if new_lines:
            self.last_update_time[file_path] = os.path.getmtime(file_path)

        if last_error_line:
            self.last_error_file = file_path
            self.event_queue.put(
                lambda: self.app.on_error_found(file_path, last_error_line)
            )

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
        if event.src_path.endswith(self.file_extension):
            if event.event_type == 'deleted':
                self.stop_tracking(event.src_path)
                print(f"Файл {event.src_path} был удален. Остановлено отслеживание.")
            else:
                print(f"Изменен файл: {event.src_path}")

    def on_deleted(self, event):
        if event.src_path in self.file_paths:
            del self.file_paths[event.src_path]
            print(f"Файл {event.src_path} был удален.")

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]
