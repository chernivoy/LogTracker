# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Про проект

**LogTracker (ADAICA)** — Windows-only десктопний застосунок на CustomTkinter. Копіює `.log` файли з мережевої/системної теки в локальну, стежить за появою нових рядків з помилками і показує останню помилку в невеликому безрамковому вікні поверх усіх вікон, згорнутому в системний трей.

Точка входу: `logger.py` → клас `LogTrackerApp`.

## Команди

Проект без тестів, лінтерів і CI. Все запускається вручну з кореня репозиторію.

```powershell
# Віртуальне середовище (у репо є і .venv, і venv — актуальне .venv)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Запуск
python logger.py

# Збірка через spec-файл
pyinstaller logger.spec        # → dist/logger/logger.exe

# Збірка через GUI (варіант із README, дав поточний output/logger/)
pip install auto-py-to-exe
auto-py-to-exe
```

Python 3.12. `requirements.txt` збережений у UTF-16 — читати/редагувати з урахуванням кодування.

## Архітектура

### Потік даних

```
source_directory (з src/config.ini)
   │  FileHandler.copy_files_from_source_dir  — копіює нові/оновлені .log, видаляє осиротілі
   ▼
destination_directory (типово C:\temp\logger)
   │  FileChangeHandler.check_new_errors      — читає лише «хвіст» файлу з збереженого offset
   ▼
event_queue (queue.Queue з lambda-колбеків)
   │  LogTrackerApp.process_queue             — розбирає чергу в головному потоці Tk
   ▼
LogTrackerApp.on_error_found → ErrorWindow (+ підняття вікна з трею)
```

### Два незалежні таймери в main loop

`logger.py` крутить два `root.after()`-цикли, і це основний рушій застосунку:

- `process_queue()` — кожні **100 мс**, витягує колбеки з `event_queue` і виконує їх у головному потоці Tk.
- `periodic_sync()` — кожну **1000 мс**, викликає `sync_files_and_check()` (копіювання + перевірка на нові помилки).

**Важливо:** `watchdog.Observer` теж запускається (`run()`), але `FileChangeHandler.on_modified` лише друкує в консоль — виявлення помилок фактично тримається на 1-секундному полінгу, а не на watchdog-подіях. Не покладайся на watchdog як на джерело подій, не переписавши логіку.

**Правило потоків:** watchdog виконується в окремому потоці. Віджети Tk чіпати з нього не можна — тільки класти колбек у `event_queue`. Це причина існування черги.

### Позиційна логіка «offset»

`FileChangeHandler.file_paths` — це dict `{шлях: розмір_у_байтах}`, який слугує курсором для `file.seek()`. `read_new_lines()` читає від збереженого offset до кінця. Якщо файл ротується/усікається, offset залишиться завеликим — новий вміст не побачать.

Рядок вважається помилкою, якщо після `strip()` він **починається** зі слова з `word` (типово `ERR`).

### Конфігурація — два різні файли

| Файл | Що містить | Хто читає/пише |
|---|---|---|
| `src/config.ini` | `[Settings]`: `word`, `file_extension`, `source_directory`, `destination_directory` | `constants.CONFIG_PATH`, `SettingsWindow.save_settings` |
| `src/window_config.ini` | `[Window]`, `[Window_path]` (геометрія), `[Theme] current` | `ConfigManager`, `WindowHandler`, `ThemeManager` |

`ConfigManager.save_config()` за замовчуванням пише саме у **window_config.ini** — його дефолтний аргумент `config_file=CONFIG_FILE_WINDOW`. Налаштування шляхів зберігаються окремим кодом у `SettingsWindow.save_settings`, який пише напряму в `CONFIG_PATH`.

Обидва ini перелічені в `.gitignore`, але були закомічені раніше, тому зміни в них далі потрапляють у `git status`.

### DPI-конвенція (легко зламати)

В ini зберігаються **логічні** значення. При відновленні геометрії (`WindowHandler.load_window_size`, `TrayManager.on_restore_defaults`, `WindowHandler.do_resize`):

- **width/height** — діляться на `dpi_scale` перед передачею в `geometry()`;
- **x/y** — передаються **без ділення**, `geometry()` компенсує сам.

`rdp.get_windows_dpi_scale()` повертає `dpi_x / 96.0`; при винятку код навколо підставляє fallback `2.0` (не `1.0`). `logger.py` на старті викликає `SetProcessDpiAwareness(1)`, `rdp.get_window_dpi()` — `SetProcessDpiAwareness(2)`.

### Безрамкове вікно

`ErrorWindow.setup_window()` вмикає `overrideredirect(True)` + `-transparentcolor` + `-alpha` + `-topmost`. Наслідок — усе, що зазвичай робить ОС, реалізовано вручну в `ui/window_handler.py` через Win32-виклики `ctypes`:

- переміщення — `start_move` / `do_move`;
- ресайз за 8 напрямками — `change_cursor` / `start_resize` / `do_resize` / `stop_resize` (зона краю `border = 20`, мінімум 300×100);
- заокруглені кути — `round_corners()` через `CreateRoundRectRgn` + `SetWindowRgn`; регіон **скидається** на час ресайзу і накладається знову в `stop_resize`.

`bind_resize_events` знаходить заголовок за жорстко зашитим Tk-шляхом `".!ctkframe.!ctklabel"`. Зміна порядку/ієрархії створення віджетів у `ErrorWindow.create_widgets()` зламає цей lookup (буде тільки `print` про помилку, мовчазна деградація перетягування).

### Теми

`ThemeManager.load_theme(name)` робить `importlib.import_module(f"themes.{name}_theme")` і читає з модуля `THEME_SETTINGS`. Доступні: `dark`, `light`, `custom`, `adaica_light`.

Щоб додати тему: створити `themes/<name>_theme.py` з `THEME_SETTINGS` і додати пункт у `ContextMenu._populate_menu()` (обидві гілки — з іконками і без).

**Контракт:** усі чотири теми зараз мають **ідентичний набір ключів**. `ThemeManager.update_widgets_theme()` звертається до ключів напряму, без `.get()` — відсутній ключ дасть `KeyError` при перемиканні теми. Додаючи ключ, додавай його в усі теми.

Додаючи новий стилізований віджет, треба змінити **два** місця: `ErrorWindow.create_widgets()` (початкове створення) і `ThemeManager.update_widgets_theme()` (перемикання на льоту), плюс зареєструвати віджет у словнику `widgets_to_update`.

### Ресурси і PyInstaller

`PathUtils.resource_path()` (`utils/path.py`) резолвить шляхи через `sys._MEIPASS` у зібраному вигляді і `os.path.abspath(".")` у dev. У `ui/ui_assets.py` є **дубль** тієї самої функції; там же `HEADER_ICON_PATH` уже резолвнутий, а решта констант — відносні шляхи, які резолвляться вже у викликачів (`ImageManager`, `TrayManager`). Непослідовно, але саме так це працює.

`logger.spec` виводить два списки глобами, тож нові файли підхоплюються самі:

- `datas` — глоб по `src/*` (іконки + ini) у цільову теку `'src'`;
- `hiddenimports` — глоб по `themes/*_theme.py`. **Обов'язковий**: `ThemeManager.load_theme` тягне теми через `importlib.import_module`, статичний аналіз PyInstaller такий імпорт не бачить. Без цього exe падає на старті з `ModuleNotFoundError: No module named 'themes'`.

Збірка windowed (`console=False`), іконка exe — `src/Header.ico`.

**Куди пишуться конфіги в зібраному вигляді.** Збірка однотечна (`COLLECT`), тому `sys._MEIPASS` вказує на `dist/logger/_internal` — постійну теку поруч з exe, а не на тимчасову (тимчасова була б лише при `--onefile`). Перевірено: після запуску exe `_internal/src/window_config.ini` оновлюється і зміни переживають перезапуск.

Наслідок інший: конфіг лежить усередині теки встановлення. Під `C:\Program Files` запис впаде без прав адміністратора, а перевстановлення застосунку затре налаштування користувача.

### Логування в зібраному вигляді

`rthook_logfile.py` — PyInstaller runtime hook (`runtime_hooks` у spec), який перенаправляє `sys.stdout` і `sys.stderr` у файл:

```
%LOCALAPPDATA%\LogTracker\logger.log     — поточний запуск
%LOCALAPPDATA%\LogTracker\logger.log.1   — попередній
```

Активується строго за умовою `sys.frozen and sys.stdout is None`, тобто **лише** в windowed-збірці. Запуск із сирців (`python logger.py`) і збірка з `console=True` працюють як раніше — вивід у консоль.

Деталі, які не варто ламати при правках хука:

- **`buffering=1` (line buffering) обов'язковий** — `LogTrackerApp.on_closing` завершується через `os._exit(0)`, який не скидає буфери Python; при блоковій буферизації хвіст лога губиться.
- **Ліміт `MAX_BYTES` (5 МБ)** — `WindowHandler.do_resize` друкує ~6 рядків на кожну подію руху миші, без обмеження файл росте необмежено. Після ліміту запис тихо припиняється, застосунок працює далі.
- Файл у UTF-8. `Get-Content` у Windows PowerShell 5.1 читає в ANSI і покаже кирилицю кракозябрами — читати `Get-Content ... -Encoding UTF8`.
- Весь хук обгорнутий у `try/except`, щоб збій логування не завалив старт.

Завдяки цьому виняток на старті потрапляє у файл. Без хука `console=False` дає лише діалог «Unhandled exception in script» без тексту — жодної діагностики.

Усі ресурси `src/` (іконки + ini) тепер у git. `ImageManager.get_ctk_image()` при відсутньому файлі повертає `None` мовчки, а `TrayManager` переходить на згенеровану `create_image()`-заглушку — тобто пропалий ассет не дає помилки, лише порожню іконку. Якщо іконки зникли, шукати треба саме тут.

## Життєвий цикл вікна

`WM_DELETE_WINDOW` перевизначено на `TrayManager.minimize_to_tray` — хрестик **не закриває** застосунок. Реальний вихід — `app.on_closing()` (пункти «Exit» у бургер-меню та в меню трея), який зупиняє observer, зберігає геометрію і завершується через `os._exit(0)`.

`is_window_open` — прапорець стану; коли він `False` і приходить нова помилка, `on_error_found` сам піднімає вікно з трею.

Меню трея будується заново при кожному згортанні (`minimize_to_tray`), запускається через `run_detached()`.

## Windows-only

`ctypes.windll` викликається без охорони платформи в `utils/rdp.py`, `ui/window_handler.py`, `pin.py`. Тільки `logger.py` перевіряє `sys.platform`. Крос-платформні гілки є лише у `FileHandler` (відкриття файлу, буфер обміну, показ у провіднику).

## Мертвий код

Не редагувати без потреби, не брати за приклад:

- `pin.py` — окремий демо-скрипт `RoundedWindow`, ніде не імпортується;
- `WindowHandler.save_window_params_2` — не викликається (використовується `save_window_params`);
- `build/`, `dist/` (від `pyinstaller logger.spec`) та `output/` (від auto-py-to-exe) — артефакти збірки, у `.gitignore`.

## Мова

Коментарі й повідомлення в коді змішані: українська, російська, англійська. Логування — виключно `print()`, без модуля `logging`. Дотримуйся стилю файлу, який редагуєш.