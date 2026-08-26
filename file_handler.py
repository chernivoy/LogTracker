import ctypes
import os
import shutil
import subprocess
from collections import namedtuple


# Формати буфера обміну Windows (winuser.h): сам файл і текст у UTF-16.
CF_UNICODETEXT = 13
CF_HDROP = 15


# Результат одного тіку синхронізації.
#
# copied — повні шляхи в теці призначення, які цей тік справді оновив.
# Раніше тут був bool, і будь-яке копіювання запускало перечитування ВСІХ
# файлів теки призначення (при 470 логах — 81,5 мс щосекунди), хоча нові
# байти можуть бути лише в тому, що щойно скопійовано: файл без зміни
# mtime не копіюється, а без копіювання його вміст у теці призначення не
# міняється.
#
# present — усі файли теки призначення, які лишились після прибирання
# осиротілих; звідси FileChangeHandler дізнається, чиї офсети ще актуальні.
# None означає «синхронізація не відбулася» (шляхи не задані, джерело
# зникло, виняток). Порожня множина і None тут РІЗНІ речі: сплутавши їх,
# ми зняли б з обліку геть усе на першому ж тіку з недоступним джерелом, а
# наступний тік «усиновив» би файли заново — і вікно вискочило б з трея зі
# старою, вже показаною помилкою.
SyncResult = namedtuple('SyncResult', 'copied present')

_SYNC_NOT_RUN = SyncResult(frozenset(), None)


class _DROPFILES(ctypes.Structure):
    """Заголовок блоку CF_HDROP — формату, яким Windows передає в буфері
    обміну САМІ ФАЙЛИ (те, що вставляється в Провідник, пошту, чат), а не
    текст їхніх шляхів.

    Розкладка задана Win32 (shlobj.h): DWORD + POINT + BOOL + BOOL = 20 байт.
    Типи беремо явні фіксованої ширини (а не ctypes.wintypes), щоб модуль
    лишався імпортовним поза Windows — тут є posix-гілки, а wintypes на
    не-Windows не імпортується.

    Одразу за цим заголовком у тому самому блоці пам'яті лежить список імен
    (UTF-16), розділених '\\0' і завершених ще одним '\\0'.
    """
    _fields_ = [
        ("pFiles", ctypes.c_uint32),  # зсув від початку блоку до списку імен
        ("pt_x", ctypes.c_int32),     # POINT точки «кидання» — для вставки
        ("pt_y", ctypes.c_int32),     # з буфера не використовується
        ("fNC", ctypes.c_int32),      # BOOL: координати в неклієнтській зоні
        ("fWide", ctypes.c_int32),    # BOOL: імена в UTF-16, а не ANSI
    ]


class FileHandler:
    @staticmethod
    def copy_file_without_waiting(source_file, dest_file):
        """Копіює файл атомарно. Повертає True лише при повному успіху.

        Пишемо в тимчасовий файл і підміняємо через os.replace(), бо
        відкриття призначення в 'wb' одразу обрізало його: зрив копіювання
        на середині лишав обрізаний файл із mtime «зараз». Умова
        getmtime(source) > getmtime(dest) після цього ніколи не
        спрацьовувала, тож копія лишалася скаліченою доти, доки джерело не
        запишуть знову — для завершеного лога назавжди.
        """
        temp_file = dest_file + '.part'
        try:
            with open(source_file, 'rb') as src, open(temp_file, 'wb') as dst:
                shutil.copyfileobj(src, dst)

            # Переносимо час зміни джерела на копію. Інакше mtime копії
            # дорівнює моменту копіювання, і за ним неможливо судити, коли
            # застосунок насправді щось записав. А мітка часу всередині
            # рядка для цього не годиться: лог пише UTC, файлова система —
            # місцевий час, різниця стала (тут 2 год) і мовчазна.
            source_stat = os.stat(source_file)
            os.utime(temp_file, (source_stat.st_atime, source_stat.st_mtime))

            os.replace(temp_file, dest_file)
            print(f"Copied {source_file} -> {dest_file}")
            return True
        except OSError as e:
            print(f"Cannot copy {source_file}: {e}")
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
            return False

    @staticmethod
    def open_file(file_path):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS, Linux
                subprocess.call(('xdg-open', file_path))
        except Exception as e:
            print(f"Cannot open file {file_path}: {e}")

    @staticmethod
    def create_directory_if_not_exists(directory):
        # Порожній шлях (перший запуск без налаштувань) — не тека: os.makedirs('')
        # лише кинув би FileNotFoundError і засмітив би лог на старті.
        if not directory:
            return
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Error creating directory {directory}: {e}")

    @staticmethod
    def is_file_closed(file_path):
        """Предикат: чи можна зараз відкрити файл на читання.

        Свідомо мовчазний — викликається в циклі опитування, і будь-який
        print() тут перетворював очікування на потік однакових рядків.
        """
        try:
            with open(file_path, 'rb') as file:
                file.seek(0, os.SEEK_END)
            return True
        except OSError:
            return False

    @staticmethod
    def can_read_file(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8'):
                pass
            return True
        except Exception as e:
            print(f"Cannot read file {file_path}: {e}")
            return False

    @staticmethod
    def _scan_log_dir(directory, file_extension, remove_stale_part=False):
        """{ім'я: mtime} для логів теки — одним перелічуванням.

        os.scandir віддає mtime з тих даних, які файлова система вже
        повернула під час обходу теки, тож окремий stat на кожен файл не
        потрібен. Раніше тут стояли os.listdir + os.path.getmtime, тобто
        два системні виклики на файл: при 470 логах саме лише порівняння
        часів коштувало 11,6 мс щосекунди.
        """
        result = {}
        with os.scandir(directory) as entries:
            for entry in entries:
                filename = entry.name

                # Осиротілі .part від копіювань, обірваних крашем. os.replace у
                # copy_file_without_waiting атомарний, тож у нормальному потоці
                # .part не лишається — усе, що тут є, це слід аварійного виходу.
                # Прибирати їх більше нікому: нижче все фільтрується за
                # file_extension (.log), тож .part проскакував і копився вічно.
                if remove_stale_part and filename.endswith('.part'):
                    try:
                        os.remove(entry.path)
                        print(f"Removed stale temp file: {filename}")
                    except OSError:
                        pass
                    continue

                if not filename.endswith(file_extension):
                    continue

                # Файл міг зникнути між обходом теки і зверненням до нього
                # (гонка з застосунком, що ротує логи). Пропускаємо саме
                # проблемний файл, а не весь прохід — наступний тік повторить.
                try:
                    if entry.is_file():
                        result[filename] = entry.stat().st_mtime
                except OSError as e:
                    print(f"Skip {filename}: {e}")
                    continue

        return result

    @staticmethod
    def copy_files_from_source_dir(source_directory, dest_directory, managed_files=None,
                                   file_extension='.log'):
        """Синхронізує логи з джерела в теку призначення.

        Повертає SyncResult (див. опис угорі файлу): що саме оновлено цим
        тіком і що лишилось у теці призначення.

        managed_files — множина імен, які скопіював саме цей застосунок.
        Прибирання застарілих копій обмежене цією множиною: тека
        призначення задається користувачем через UI, і раніше сюди
        потрапляв будь-який сторонній лог, який просто видалявся.

        file_extension приходить з конфігу. Раніше тут стояв жорсткий
        '.log', тож зміна file_extension давала розбіжність: застосунок
        стежив за одним розширенням, а копіював інше.
        """
        # Перший запуск без налаштувань: порожнє/неіснуюче джерело — нема що
        # копіювати. Без цього os.scandir(source) на порожньому шляху кидає
        # (Windows) або мовчки лістить робочу теку (POSIX), а порожнє
        # призначення обернуло б os.path.join на відносний шлях — копіювання
        # опинилося б у поточній робочій теці процесу.
        if not source_directory or not os.path.isdir(source_directory):
            return _SYNC_NOT_RUN
        if not dest_directory:
            return _SYNC_NOT_RUN
        try:
            FileHandler().create_directory_if_not_exists(dest_directory)

            source_mtimes = FileHandler._scan_log_dir(source_directory, file_extension)
            dest_mtimes = FileHandler._scan_log_dir(dest_directory, file_extension,
                                                    remove_stale_part=True)

            copied = set()
            for filename, source_mtime in source_mtimes.items():
                dest_mtime = dest_mtimes.get(filename)

                # Копія зберігає mtime джерела, тож будь-яка РІЗНИЦЯ означає
                # розсинхрон — і в той, і в інший бік. Порівняння через '>'
                # лишало б застарілими копії, зроблені до введення переносу
                # mtime: у них стоїть час копіювання, тобто завідомо новіший
                # за джерело, і оновитись вони не могли б ніколи.
                # Допуск 1 мс — на похибку представлення float.
                if dest_mtime is not None and abs(source_mtime - dest_mtime) <= 0.001:
                    continue

                source_file = os.path.join(source_directory, filename)
                dest_file = os.path.join(dest_directory, filename)
                try:
                    # Заблокований файл просто пропускаємо. Раніше тут стояв
                    # wait_for_file(), який блокував головний потік Tk до 2 с
                    # на файл — при 56 файлах тік, розрахований на секунду,
                    # міг розтягтися на хвилини. Наступний тік через секунду
                    # повторить спробу, чекати немає сенсу.
                    #
                    # Перевірка стоїть ПІСЛЯ порівняння mtime і не дарма:
                    # is_file_closed відкриває файл, а відкривати треба лише
                    # той, який зараз копіюємо. Раніше вона стояла першою, тож
                    # щосекунди відкривалися геть усі файли джерела — при 470
                    # логах це 57,7 мс на тік, тобто левова частка постійних
                    # 9 % ядра, і зростало воно лінійно з кожним новим логом.
                    if not FileHandler.is_file_closed(source_file):
                        continue

                    # copied відображає лише реальний успіх: раніше
                    # прапорець ставився беззастережно, а помилку
                    # копіювання проковтували — у лог ішло «File copied»
                    # навіть коли файл не скопіювався.
                    if FileHandler.copy_file_without_waiting(source_file, dest_file):
                        copied.add(dest_file)

                        if managed_files is not None:
                            managed_files.add(filename)
                except OSError as e:
                    print(f"Skip source {filename}: {e}")
                    continue

            present = {os.path.join(dest_directory, name) for name in dest_mtimes}

            for filename in dest_mtimes.keys() - source_mtimes.keys():
                dest_file = os.path.join(dest_directory, filename)
                source_file = os.path.join(source_directory, filename)

                # Так само ізолюємо видалення: os.remove/os.path.exists можуть
                # спіткнутися об файл, який зник під ногами, а зривати через це
                # весь прохід синхронізації не можна.
                try:
                    # Знімок джерела зроблено кількома мілісекундами раніше, і
                    # файл міг з'явитися вже після нього. Питаємо диск наживо,
                    # щоб не видалити щойно створений лог. Кандидатів тут
                    # одиниці (зазвичай нуль), тож зайвий stat нічого не варт.
                    if os.path.exists(source_file):
                        continue

                    # Чужий файл — не ми його сюди поклали, не нам і прибирати.
                    if managed_files is not None and filename not in managed_files:
                        print(f'File {filename} left alone: not copied by this app')
                        continue

                    os.remove(dest_file)
                    present.discard(dest_file)
                    if managed_files is not None:
                        managed_files.discard(filename)
                    print(
                        f'File {filename} removed from {dest_directory},  because it does not exist in {source_directory}')
                except OSError as e:
                    print(f"Skip dest {filename}: {e}")
                    continue

            if copied:
                print(f'Finished copying from {source_directory} to {dest_directory}.')
            # Знімок теки призначення зроблено ДО копіювання, тож щойно
            # створені копії до нього не потрапили — додаємо їх явно,
            # інакше _forget_missing_files зняв би з обліку файл, який
            # цей же тік і завів.
            return SyncResult(frozenset(copied), frozenset(present) | frozenset(copied))
        except Exception as e:
            print(f" Error when copying file from {source_directory} to {dest_directory}: {e}")
            return _SYNC_NOT_RUN

    @staticmethod
    def _put_on_clipboard(clip_format, payload):
        """Кладе готовий блок байтів у буфер обміну у форматі `clip_format`.

        Спільна Win32-частина обох способів копіювання — файлом (CF_HDROP) і
        текстом (CF_UNICODETEXT); різниця між ними тільки в тому, ЩО лежить у
        payload, тож сам обмін із буфером описаний один раз.

        Робимо через ctypes, а не pywin32: зайва залежність у requirements і
        в hiddenimports збірки заради кількох викликів не потрібна. `clip.exe`
        не годиться подвійно — він уміє лише текст, та ще й у windowed-збірці
        блимає вікном консолі.

        Володіння пам'яттю: після успішного SetClipboardData блок належить
        БУФЕРУ (система звільнить його сама, і вміст переживає вихід із
        застосунку), тож звільняти його нам не можна. А на будь-якому збої
        володіння лишається за нами — тоді GlobalFree обов'язковий, інакше
        кожна невдала спроба тече.
        """
        GMEM_MOVEABLE = 0x0002

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # Явні типи обов'язкові: типовий restype ctypes — c_int, тож 64-бітні
        # дескриптори (HGLOBAL, вказівник із GlobalLock) зрізалися б до 32 біт
        # і пішли б у буфер зіпсованими.
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
        kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
        kernel32.GlobalFree.restype = ctypes.c_void_p
        kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
        user32.OpenClipboard.argtypes = (ctypes.c_void_p,)
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)

        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not h_mem:
            print("Clipboard: GlobalAlloc failed")
            return False

        pointer = kernel32.GlobalLock(h_mem)
        if not pointer:
            kernel32.GlobalFree(h_mem)
            print("Clipboard: GlobalLock failed")
            return False
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            kernel32.GlobalUnlock(h_mem)

        # Буфер обміну — глобальний ресурс: ним у цей момент може володіти
        # інший процес, і тоді OpenClipboard просто не вдасться. Не чекаємо
        # і не крутимо ретраї — це головний потік Tk, підвисати в ньому не
        # можна; користувач повторить кліком.
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_mem)
            print("Clipboard: OpenClipboard failed (busy?)")
            return False
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(clip_format, ctypes.c_void_p(h_mem)):
                kernel32.GlobalFree(h_mem)
                print("Clipboard: SetClipboardData failed")
                return False
        finally:
            user32.CloseClipboard()
        return True

    @staticmethod
    def copy_file_to_clipboard(file_path):
        """Кладе в буфер обміну САМ ФАЙЛ (Windows, формат CF_HDROP).

        Тобто після Ctrl+V у Провіднику/пошті/чаті з'явиться файл, а не рядок
        зі шляхом (для тексту є copy_text_to_clipboard). Повертає True лише
        при повному успіху — викликач за цим вирішує, чи показувати
        підтвердження користувачу.
        """
        if os.name != 'nt':
            # CF_HDROP — суто Windows. На posix найближчий аналог (uri-list у
            # X11) залежить від DE й буферної утиліти, тож чесніше не вдавати
            # підтримку: викликач отримає False і не покаже підтвердження.
            print("Copying a file object to clipboard is supported on Windows only.")
            return False

        try:
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                print(f"Cannot copy to clipboard, file is gone: {abs_path}")
                return False

            # Блок CF_HDROP — це заголовок, а одразу за ним, у тій самій
            # пам'яті, список імен. Подвійний '\0' у кінці: один завершує
            # ім'я, другий — увесь список.
            header = _DROPFILES(pFiles=ctypes.sizeof(_DROPFILES), fWide=1)
            payload = bytes(header) + (abs_path + "\0\0").encode("utf-16-le")

            if not FileHandler._put_on_clipboard(CF_HDROP, payload):
                return False
            print(f"File '{abs_path}' copied to clipboard.")
            return True
        except Exception as e:
            print(f"Cannot copy file to clipboard: {e}")
            return False

    @staticmethod
    def copy_text_to_clipboard(text):
        """Копіює ТЕКСТ у системний буфер обміну. Повертає True на успіх.

        На Windows пишемо в буфер напряму (CF_UNICODETEXT), а не через
        `clip.exe`: підпроцес у windowed-збірці блимає вікном консолі, ламає
        не-ASCII на старій кодовій сторінці й коштує запуску процесу на
        кожен клік. Tk-івський clipboard_append теж не годиться — Tk віддає
        вміст ЗА ЗАПИТОМ, а застосунок завершується через os._exit(0), тож
        скопійоване зникало б із буфера разом із процесом.
        """
        try:
            if os.name == 'nt':
                # Рядок у буфері мусить бути нуль-термінований.
                if not FileHandler._put_on_clipboard(
                        CF_UNICODETEXT, (text + "\0").encode("utf-16-le")):
                    return False
                print(f"Copied {len(text)} chars to clipboard.")
                return True

            if os.name == 'posix':  # macOS і Linux
                try:
                    subprocess.run(['xclip', '-selection', 'clipboard'],
                                   input=text.encode('utf-8'), check=True)
                    return True
                except FileNotFoundError:
                    try:
                        subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
                        return True
                    except FileNotFoundError:
                        print("Clipboard tool (xclip/pbcopy) not found.")
                        return False

            print("Clipboard copy is not supported on this operating system.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Clipboard command failed: {e}")
            return False
        except Exception as e:
            print(f"Cannot copy text to clipboard: {e}")
            return False

    @staticmethod
    def reveal_in_file_explorer(file_path):
        """
        Відкриває папку, де знаходиться файл, і виділяє його.
        Працює на Windows, macOS та більшості дистрибутивів Linux.
        """
        try:
            # Перетворюємо шлях на абсолютний, щоб уникнути помилок
            abs_path = os.path.abspath(file_path)

            if os.name == 'nt':  # Windows
                # Команда `explorer.exe /select,` відкриває Провідник і виділяє файл.
                # Без check=True навмисно: explorer повертає ненульовий код
                # навіть коли вікно успішно відкрилося, тож перевірка коду
                # породжувала CalledProcessError і фальшиве повідомлення про
                # помилку при кожному вдалому виклику.
                subprocess.run(['explorer', '/select,', abs_path])
                print(f"File '{file_path}' revealed in Windows Explorer.")

            elif os.name == 'posix':
                # macOS та Linux використовують різні команди
                if subprocess.run(['uname'], capture_output=True, text=True).stdout.strip() == 'Darwin':
                    # macOS: `open -R`
                    subprocess.run(['open', '-R', abs_path], check=True)
                    print(f"File '{file_path}' revealed in Finder.")
                else:  # Linux
                    # Спроба використання стандартних команд для різних DE
                    # xdg-open зазвичай відкриває папку, але не виділяє файл
                    # nautilus, dolphin - це специфічні менеджери файлів

                    # Спочатку спробуємо nautilus (GNOME)
                    try:
                        subprocess.run(['nautilus', '--select', abs_path], check=True)
                        print(f"File '{file_path}' revealed in Nautilus.")
                    except FileNotFoundError:
                        # Якщо nautilus не знайдено, спробуємо dolphin (KDE)
                        try:
                            subprocess.run(['dolphin', '--select', abs_path], check=True)
                            print(f"File '{file_path}' revealed in Dolphin.")
                        except FileNotFoundError:
                            # Якщо нічого не підходить, просто відкриємо папку
                            subprocess.run(['xdg-open', os.path.dirname(abs_path)], check=True)
                            print(f"Opened folder containing '{file_path}'.")
            else:
                print("Operation is not supported on this system.")

        except FileNotFoundError:
            print("Error: file explorer command not found.")
        except subprocess.CalledProcessError as e:
            print(f"Command execution error: {e}")
        except Exception as e:
            print(f"Cannot open file in explorer: {e}")
