import os
import shutil
import subprocess
import time


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

    @staticmethod
    def create_directory_if_not_exists(directory):
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Создана директория: {directory}")
            except Exception as e:
                print(f"Ошибка при создании директории {directory}: {e}")

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
    def wait_for_file(file_path, timeout=2, poll_interval=0.1):
        """Чекає, доки файл звільниться. Викликається з головного потоку Tk."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if FileHandler.is_file_closed(file_path):
                return True
            # Пауза принципова: без неї цикл крутив open() безперервно і
            # з'їдав ядро на 100%. А оскільки викликається він із
            # periodic_sync (root.after -> головний потік Tk), кожна секунда
            # очікування — це секунда повністю замороженого вікна.
            time.sleep(poll_interval)

        # Таймаут малий навмисно: periodic_sync повторює спробу щосекунди,
        # тож блокувати UI на 30 с у надії дочекатися сенсу не мало.
        print(f"File still locked after {timeout}s: {file_path}")
        return False

    @staticmethod
    def can_read_file(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8'):
                pass
            return True
        except Exception as e:
            print(f"Не удалось прочитать файл {file_path}: {e}")
            return False

    @staticmethod
    def copy_files_from_source_dir(source_directory, dest_directory, managed_files=None):
        """Синхронізує .log з джерела в теку призначення.

        managed_files — множина імен, які скопіював саме цей застосунок.
        Прибирання застарілих копій обмежене цією множиною: тека
        призначення задається користувачем через UI, і раніше сюди
        потрапляв будь-який сторонній .log, який просто видалявся.
        """
        try:
            FileHandler().create_directory_if_not_exists(dest_directory)
            copied = False
            for filename in os.listdir(source_directory):
                if filename.endswith('.log'):
                    source_file = os.path.join(source_directory, filename)
                    dest_file = os.path.join(dest_directory, filename)

                    if FileHandler.wait_for_file(source_file):
                        if not os.path.exists(dest_file):
                            FileHandler.copy_file_without_waiting(source_file, dest_file)
                            print(f'File {filename} copied from {source_directory} to {dest_directory}')
                            copied = True
                        else:

                            if os.path.getmtime(source_file) > os.path.getmtime(dest_file):
                                FileHandler.copy_file_without_waiting(source_file, dest_file)
                                print(f'File {filename} updated in {dest_directory}')
                                copied = True

                        if managed_files is not None:
                            managed_files.add(filename)

            for filename in os.listdir(dest_directory):
                if filename.endswith('.log'):
                    dest_file = os.path.join(dest_directory, filename)
                    source_file = os.path.join(source_directory, filename)
                    if os.path.exists(source_file):
                        continue

                    # Чужий файл — не ми його сюди поклали, не нам і прибирати.
                    if managed_files is not None and filename not in managed_files:
                        print(f'File {filename} left alone: not copied by this app')
                        continue

                    os.remove(dest_file)
                    if managed_files is not None:
                        managed_files.discard(filename)
                    print(
                        f'File {filename} removed from {dest_directory},  because it does not exist in {source_directory}')
                    copied = True
            if copied:
                print(f'Finished copying from {source_directory} to {dest_directory}.')
            # Явний return: раніше при copied=False функція просто добігала
            # до кінця і віддавала None. Працювало випадково — обидва
            # значення хибні — але тип, що залежить від гілки, це пастка.
            return copied
        except Exception as e:
            print(f" Error when copying file from {source_directory} to {dest_directory}: {e}")
            return False

    @staticmethod
    def copy_file_path_to_clipboard(file_path):
        """
        Копіює шлях до файлу в системний буфер обміну.
        Використовує підхід, що залежить від операційної системи.
        """
        try:
            if os.name == 'nt':  # Для Windows
                subprocess.run(['clip'], input=file_path.encode('utf-8'), check=True, shell=True)
                print(f"Шлях до файлу '{file_path}' скопійовано в буфер обміну.")
            elif os.name == 'posix':  # Для macOS і Linux
                try:
                    subprocess.run(['xclip', '-selection', 'clipboard'], input=file_path.encode('utf-8'), check=True)
                    print(f"Шлях до файлу '{file_path}' скопійовано в буфер обміну (Linux).")
                except FileNotFoundError:
                    try:
                        subprocess.run(['pbcopy'], input=file_path.encode('utf-8'), check=True)
                        print(f"Шлях до файлу '{file_path}' скопійовано в буфер обміну (macOS).")
                    except FileNotFoundError:
                        print("Інструмент для роботи з буфером обміну (xclip/pbcopy) не знайдено.")
            else:
                print("Копіювання в буфер обміну не підтримується на цій операційній системі.")
        except subprocess.CalledProcessError as e:
            print(f"Помилка виконання команди для буфера обміну: {e}")
        except Exception as e:
            print(f"Не вдалося скопіювати шлях до файлу в буфер обміну: {e}")

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
                print(f"Файл '{file_path}' відкрито у Провіднику Windows.")

            elif os.name == 'posix':
                # macOS та Linux використовують різні команди
                if subprocess.run(['uname'], capture_output=True, text=True).stdout.strip() == 'Darwin':
                    # macOS: `open -R`
                    subprocess.run(['open', '-R', abs_path], check=True)
                    print(f"Файл '{file_path}' відкрито у Finder.")
                else:  # Linux
                    # Спроба використання стандартних команд для різних DE
                    # xdg-open зазвичай відкриває папку, але не виділяє файл
                    # nautilus, dolphin - це специфічні менеджери файлів

                    # Спочатку спробуємо nautilus (GNOME)
                    try:
                        subprocess.run(['nautilus', '--select', abs_path], check=True)
                        print(f"Файл '{file_path}' відкрито у Nautilus.")
                    except FileNotFoundError:
                        # Якщо nautilus не знайдено, спробуємо dolphin (KDE)
                        try:
                            subprocess.run(['dolphin', '--select', abs_path], check=True)
                            print(f"Файл '{file_path}' відкрито у Dolphin.")
                        except FileNotFoundError:
                            # Якщо нічого не підходить, просто відкриємо папку
                            subprocess.run(['xdg-open', os.path.dirname(abs_path)], check=True)
                            print(f"Папку з файлом '{file_path}' відкрито.")
            else:
                print("Операція не підтримується на поточній системі.")

        except FileNotFoundError:
            print(f"Помилка: Команда для відкриття провідника не знайдена.")
        except subprocess.CalledProcessError as e:
            print(f"Помилка при виконанні команди: {e}")
        except Exception as e:
            print(f"Не вдалося відкрити файл у провіднику: {e}")
