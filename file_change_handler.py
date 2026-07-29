import os

from watchdog.events import FileSystemEventHandler

from file_handler import FileHandler

# Логи пишуться з BOM (EF BB BF). Файл читається як 'utf-8', а не
# 'utf-8-sig', щоб офсети лишалися звичайними байтовими зміщеннями, тож
# BOM доходить до зіставлення як символ '﻿'. Пробільним він не
# вважається, і str.strip() його не прибирає.
BOM = '﻿'


def normalize_line(line):
    """Готує рядок до порівняння зі словом-маркером."""
    return line.lstrip(BOM).strip()


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
        # Імена файлів, які саме цей застосунок скопіював у теку призначення.
        # Лише їх дозволено видаляти при синхронізації.
        self.managed_files = set()
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
            copied = FileHandler.copy_files_from_source_dir(
                source_directory, self.destination_directory,
                self.managed_files, self.file_extension
            )
            if copied:
                present = set()
                found = {}

                for filename in os.listdir(self.destination_directory):
                    if filename.endswith(self.file_extension):
                        file_path = os.path.join(self.destination_directory, filename)
                        present.add(file_path)

                        if self._baseline_if_new(file_path):
                            continue

                        errors = self.check_new_errors(file_path)
                        if errors:
                            found[file_path] = errors

                self._forget_missing_files(present)

                # Одне повідомлення на весь тік. Якщо помилки прийшли в
                # кількох файлах одразу, раніше кожен клав свій колбек у
                # чергу і на екрані лишався тільки останній.
                if found:
                    self.last_error_file = list(found)[-1]
                    self.event_queue.put(lambda batch=found: self.app.on_error_found(batch))
        except Exception as e:
            print(f"Error when sync and check files and errors: {e}")

    def _baseline_if_new(self, file_path):
        """Бере новий файл на облік без сповіщень. True — файл щойно взято.

        track_files() на старті ставить офсет на кінець кожного файлу, що
        вже лежить у теці, тож стара історія не показується. А от файл,
        скопійований уже після старту, не мав запису в file_paths і читався
        з нуля — і вся його історія висипалася як свіжі помилки. На першому
        запуску, коли тека призначення порожня, так поводилися геть усі
        файли: у вікні опинялася помилка тижневої давнини.
        """
        if file_path in self.file_paths:
            return False

        try:
            self.file_paths[file_path] = os.path.getsize(file_path)
        except OSError:
            self.file_paths[file_path] = 0

        print(f"Baseline set for new file: {file_path}")
        return True

    def _forget_missing_files(self, present):
        """Прибирає з словників записи про файли, яких уже немає.

        file_paths і last_update_time поповнювалися при кожному новому
        файлі, але ніколи не чистилися — включно з файлами, які видаляла
        сама ж синхронізація. За довгу сесію словники росли необмежено.
        """
        for gone in [p for p in self.file_paths if p not in present]:
            del self.file_paths[gone]
            self.last_update_time.pop(gone, None)

    def check_new_errors(self, file_path):
        """Повертає ВСІ рядки-помилки з нової частини файлу.

        Раніше метод у циклі перезаписував одну змінну, тож із пачки
        виживала лише остання помилка — решта губилася назавжди, бо офсет
        уже зсунуто. Тепер повертається повний список, а рішення про показ
        ухвалює sync_files_and_check, який бачить усі файли тіку разом.
        """
        return [
            line
            for line in (normalize_line(raw) for raw in self.read_new_lines(file_path))
            if line.startswith(self.word)
        ]

    def read_new_lines(self, file_path):
        """Читає «хвіст» файлу від збереженого офсету до кінця."""
        new_lines = []

        try:
            current_size = os.path.getsize(file_path)
        except OSError as e:
            print(f"Cannot stat {file_path}: {e}")
            return new_lines

        previous_offset = self.file_paths.get(file_path, 0)
        # Запасне значення на випадок, коли до tell() справа не дійде.
        next_offset = current_size

        try:
            # errors='replace' обов'язковий: лог може містити не-UTF-8 байти
            # (напр. рядок у cp1251). Раніше readlines() кидав UnicodeDecodeError,
            # офсет лишався незмінним, і кожне наступне читання билося об той
            # самий байт — помилки в цьому файлі не виявлялися вже ніколи.
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                # Файл могли ротувати або обрізати — тоді збережений офсет
                # більший за розмір, і читати треба з початку.
                file.seek(previous_offset if previous_offset <= current_size else 0)
                new_lines = file.readlines()
                # Саме tell(), а не зафіксований до відкриття current_size.
                # Лог дописують безперервно, тож між getsize() і readlines()
                # у файл встигали потрапити нові рядки: readlines() їх читав,
                # а офсет лишався на доростовому розмірі — і наступний тік
                # показував ті самі помилки вдруге.
                next_offset = file.tell()
        except OSError as e:
            print(f"Cannot read {file_path}: {e}")
        finally:
            # Офсет рухаємо завжди, навіть після збою: інакше одна невдача
            # заморожує позицію назавжди і файл випадає зі спостереження.
            self.file_paths[file_path] = next_offset

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
