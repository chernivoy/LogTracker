import os
import time

from watchdog.events import FileSystemEventHandler

from file_handler import FileHandler

# Свіжість визначається ВИКЛЮЧНО за mtime файлу.
#
# Мітка часу всередині рядка ("ERR █ 2026.07.30 05.32.40.1515517 █ ...")
# для цього непридатна: застосунок пише її в UTC, а файлова система живе
# за місцевим часом. Різниця стала і мовчазна — на цій машині 2 години.
# Порівняння такої мітки з datetime.now() оголошувало щойно записану
# помилку «старішою за запуск трекера», і вона не показувалась.
#
# Копії зберігають mtime джерела (див. copy_file_without_waiting), тож
# mtime — це реальний час останнього запису в лог, в одному годиннику
# з усім іншим.

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
        # Межа «історія / свіже» для файлів, що з'являються під час роботи.
        # time.time(), бо порівнюється з os.path.getmtime().
        self.started_at = time.time()
        # Імена файлів, які саме цей застосунок скопіював у теку призначення.
        # Лише їх дозволено видаляти при синхронізації.
        self.managed_files = set()
        FileHandler().create_directory_if_not_exists(self.destination_directory)
        self.track_files()

    def track_files(self):
        # Перший запуск без налаштувань: теки призначення ще нема (порожній або
        # неіснуючий шлях). Тихо пропускаємо — os.listdir на такому шляху лише
        # кинув би виняток. track_files повторять при зміні налаштувань.
        if not self.destination_directory or not os.path.isdir(self.destination_directory):
            print(f"Destination not available yet, tracking skipped: {self.destination_directory!r}")
            return
        print(f"Tracking files with {self.file_extension} extension in the directory:", self.destination_directory)
        try:
            for file_name in os.listdir(self.destination_directory):
                file_path = os.path.join(self.destination_directory, file_name)
                if file_name.endswith(self.file_extension) and FileHandler.can_read_file(file_path):
                    self.file_paths[file_path] = os.path.getsize(file_path)
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
                newest = None  # (мітка_часу, шлях, рядок)

                for filename in os.listdir(self.destination_directory):
                    if filename.endswith(self.file_extension):
                        file_path = os.path.join(self.destination_directory, filename)
                        present.add(file_path)

                        adopted = self._adopt_if_new(file_path)
                        if adopted is not None:
                            # Файл побачено вперше: офсет уже на кінці,
                            # показати можна лише свіжу частину його вмісту.
                            newest = self._pick_newest(file_path, adopted, newest)
                        else:
                            newest = self._newest_error(file_path, newest)

                self._forget_missing_files(present)

                # На екран іде рівно одна помилка — найсвіжіша з усіх файлів
                # тіку. Читаємо при цьому всі нові рядки кожного файлу, тож
                # порівняння йде за реальними мітками часу, а не за порядком,
                # у якому os.listdir() віддав імена.
                if newest is not None:
                    _, file_path, error_line = newest
                    self.last_error_file = file_path
                    self.event_queue.put(
                        lambda p=file_path, line=error_line: self.app.on_error_found(p, line)
                    )
        except Exception as e:
            print(f"Error when sync and check files and errors: {e}")

    def _newest_error(self, file_path, current_newest):
        """Порівнює НОВІ помилки файлу з лідером і повертає найсвіжішу."""
        return self._pick_newest(file_path, self.check_new_errors(file_path), current_newest)

    def _pick_newest(self, file_path, errors, current_newest):
        """Обирає найсвіжішу помилку між списком і поточним лідером.

        Кандидат від файлу — його ОСТАННЯ помилка: лог дописується в
        кінець, тож порядок читання збігається з порядком запису.
        Між файлами виграє той, у якого новіший mtime.
        """
        if not errors:
            return current_newest

        try:
            stamp = os.path.getmtime(file_path)
        except OSError:
            return current_newest

        # >= : за однакового mtime перемагає пізніше оброблений файл.
        if current_newest is None or stamp >= current_newest[0]:
            return (stamp, file_path, errors[-1])

        return current_newest

    def find_latest_existing_error(self):
        """Найсвіжіша помилка серед уже наявного вмісту всіх файлів.

        Потрібна, щоб заповнити вікно на старті. track_files() ставить
        офсети на кінець наявних файлів — усе, що вже записано, вважається
        переглянутим, тож звичайний прохід не побачить нічого і поле
        лишається порожнім, доки не станеться нова помилка. Тут навпаки:
        файли читаються цілком, але офсети не чіпаються.
        """
        newest = None

        try:
            file_names = os.listdir(self.destination_directory)
        except OSError as e:
            print(f"Cannot list {self.destination_directory}: {e}")
            return None

        for file_name in file_names:
            if not file_name.endswith(self.file_extension):
                continue

            file_path = os.path.join(self.destination_directory, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                    errors = [
                        line
                        for line in (normalize_line(raw) for raw in file)
                        if line.startswith(self.word)
                    ]
            except OSError as e:
                print(f"Cannot scan {file_path}: {e}")
                continue

            newest = self._pick_newest(file_path, errors, newest)

        return newest

    def _adopt_if_new(self, file_path):
        """Бере файл на облік при першій появі.

        None — файл не новий. Інакше список помилок з наявного вмісту,
        які варто показати.

        Офсет ставиться на кінець: читати такий файл з нуля не можна, бо
        тоді вся його історія висипалася б як свіжі помилки (на першому
        запуску, коли тека призначення порожня, так поводилися геть усі
        файли — у вікні опинявся запис тижневої давнини).

        Але просто змовчати теж не можна: застосунок, за яким стежимо,
        заводить НОВИЙ лог на кожну сесію, і помилки, записані туди до
        першого погляду трекера, зникли б безслідно.

        Ознака «файл живий» — mtime не старіший за момент запуску
        трекера. Саме mtime, а не мітка в рядку: та йде в UTC і на дві
        години відстає від місцевого часу, тому щойно записана помилка
        завжди виглядала давнішою за старт і мовчки відкидалась.
        """
        if file_path in self.file_paths:
            return None

        errors = []
        offset = 0
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                errors = [
                    line
                    for line in (normalize_line(raw) for raw in file)
                    if line.startswith(self.word)
                ]
                offset = file.tell()
        except OSError as e:
            print(f"Cannot adopt {file_path}: {e}")
            try:
                offset = os.path.getsize(file_path)
            except OSError:
                offset = 0

        self.file_paths[file_path] = offset

        try:
            active = os.path.getmtime(file_path) >= self.started_at
        except OSError:
            active = False

        print(f"Adopted {file_path}: {len(errors)} errors, active={active}")
        return errors if active else []

    def _forget_missing_files(self, present):
        """Прибирає з словників записи про файли, яких уже немає.

        file_paths поповнювався при кожному новому файлі, але ніколи не
        чистився — включно з файлами, які видаляла сама ж синхронізація.
        За довгу сесію словник ріс необмежено.
        """
        for gone in [p for p in self.file_paths if p not in present]:
            del self.file_paths[gone]

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

    # --- watchdog ---
    # Обробники нижче лише логують і чистять стан. Виявлення помилок
    # тримається на periodic_sync, а не на цих подіях (див. CLAUDE.md).

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(self.file_extension):
            # Тут була гілка `if event.event_type == 'deleted'`, недосяжна
            # за визначенням: watchdog викликає on_modified лише для
            # FileModifiedEvent. Через неї stop_tracking() не викликався
            # ніколи, а видалення обробляє on_deleted.
            print(f"Modified: {event.src_path}")

    def on_deleted(self, event):
        if event.is_directory:
            return
        # os.replace() у copy_file_without_waiting (атомарна підміна копії)
        # породжує на Windows подію 'deleted' для цільового файлу, одразу за
        # якою йде 'moved' (.part -> ціль). Файл при цьому НЕ зникає. Якщо тут
        # беззастережно зняти його з обліку, наступний тік sync_files_and_check
        # «усиновить» його заново через _adopt_if_new, а усиновлення повертає
        # ВСІ наявні помилки файлу (офсет скидається на кінець аж після
        # читання) — тож стара, вже показана помилка знову йде в on_error_found,
        # і згорнуте вікно вискакує з трея, хоча нової помилки не було.
        #
        # Реальне видалення лишає файл відсутнім — перевіряємо саме це. os.replace
        # атомарний: ціль завжди існує (стара або нова версія), тож exists()
        # надійно відрізняє підміну від справжнього видалення. Осиротілі копії
        # й без цього прибирає _forget_missing_files на тіку синхронізації.
        if not os.path.exists(event.src_path):
            self.stop_tracking(event.src_path)

    def stop_tracking(self, file_path):
        if file_path in self.file_paths:
            del self.file_paths[file_path]
            print(f"Stopped tracking deleted file: {file_path}")
