import os
import shutil
import sys


class PathUtils:
    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    @staticmethod
    def user_config_path(filename):
        """Шлях до ЗАПИСУВАНОГО конфігу (config.ini / window_config.ini).

        У зібраному вигляді ресурси лежать усередині теки встановлення
        (sys._MEIPASS = dist/logger/_internal). Писати туди під C:\\Program
        Files не можна без адмін-прав, а перевстановлення затирає налаштування
        користувача. Тому записувані конфіги виносимо в
        %LOCALAPPDATA%\\LogTracker\\ — поряд із логом (rthook_logfile). При
        першій появі туди сідується bundled-копія з ресурсів, щоб дефолти
        (word, file_extension, теми) не загубилися.

        У dev (python logger.py, sys.frozen відсутній) поведінка стара: пишемо
        в ./src, який лежить у git — щоб локальна розробка не роз'їжджалася з
        репозиторієм.
        """
        if not getattr(sys, "frozen", False):
            return PathUtils.resource_path(os.path.join("src", filename))

        base = (os.environ.get("LOCALAPPDATA")
                or os.environ.get("TEMP")
                or os.path.expanduser("~"))
        target_dir = os.path.join(base, "LogTracker")
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError:
            # Не змогли створити теку — відкочуємось на bundled-ресурс, щоб
            # застосунок бодай прочитав дефолти (записи все одно впадуть, але
            # це краще за крах на імпорті).
            return PathUtils.resource_path(os.path.join("src", filename))

        target = os.path.join(target_dir, filename)
        if not os.path.exists(target):
            seed = PathUtils.resource_path(os.path.join("src", filename))
            try:
                if os.path.exists(seed):
                    shutil.copyfile(seed, target)
            except OSError:
                pass  # немає сіду — load_config створить дефолтний файл
        return target
