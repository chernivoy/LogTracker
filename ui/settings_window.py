import os

import customtkinter as ctk

from config_manager import ConfigManager
from ui.ui_assets import HEADER_ICON_PATH
from ui.window_handler import WindowHandler
from utils import rdp


class SettingsWindow:
    """Модальне вікно налаштування шляхів.

    Стиль повністю береться з поточної теми через групу ключів settings_* —
    ті самі, що є в усіх темах (контракт: набір ключів однаковий скрізь). Тож
    вікно візуально належить до того ж застосунку, що й головне вікно з полем
    помилки, і виглядає коректно в кожній темі. Тема застосовується один раз
    при відкритті: вікно модальне (grab_set), тож змінити тему, поки воно
    відкрите, неможливо — живого оновлення стилю не потрібно.
    """

    # Колір повідомлення про помилку валідації. Фіксований, а не з теми: це
    # службовий індикатор стану, а не частина палітри, і читається на фоні
    # всіх трьох тем (світлій, темній, graphite). Заводити заради нього ключ
    # у theme-контракт (довелося б додати в кожну тему) не варто.
    _ERROR_COLOR = "#e06c75"

    @staticmethod
    def open_settings_window(app):
        """Відкриває вікно налаштувань для шляхів, стилізоване під поточну тему."""
        # Guard від другого вікна: обидва роблять grab_set() і стекалися б,
        # перехоплюючи фокус одне в одного. Наявне — просто піднімаємо.
        existing = getattr(app, "_settings_window", None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        theme = app.theme_manager.current_theme_data

        window = ctk.CTkToplevel(app.root, fg_color=theme["settings_bg"])
        window.title("Path settings")
        app._settings_window = window

        SettingsWindow._apply_deferred_icon(window)
        SettingsWindow._apply_geometry(window)
        window.minsize(400, 270)
        window.grab_set()  # Заблокувати інші вікна до закриття цього

        source_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to source directory:", app.source_directory)
        destination_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to destination directory:", app.destination_directory)

        # Рядок для повідомлень валідації: доти порожній і місця майже не
        # займає. save_settings пише сюди текст замість мовчазного закриття.
        status_label = ctk.CTkLabel(
            window, text="", text_color=SettingsWindow._ERROR_COLOR,
            font=theme["settings_font"], wraplength=360, justify="center")
        status_label.pack(pady=(4, 0))
        window._status_label = status_label

        def _save():
            SettingsWindow.save_settings(
                app, window, source_entry.get(), destination_entry.get())

        SettingsWindow._add_button(window, theme, "Save", pady=10, command=_save)
        SettingsWindow._add_button(
            window, theme, "Cancel", pady=5, command=window.destroy)

        SettingsWindow._bind_geometry_autosave(window)
        SettingsWindow._bind_keyboard(window, _save)
        source_entry.focus_set()

    # ---- Побудова стилізованих під тему віджетів ----

    @staticmethod
    def _add_labeled_entry(window, theme, label_text, value):
        """Підпис + поле вводу під ним, обидва в стилі теми. Повертає поле."""
        ctk.CTkLabel(
            window,
            text=label_text,
            text_color=theme["settings_text_color"],
            font=theme["settings_font"],
        ).pack(pady=10)

        entry = ctk.CTkEntry(
            window,
            width=300,
            fg_color=theme["settings_entry_fg_color"],
            text_color=theme["settings_text_color"],
            border_color=theme["settings_entry_border_color"],
            font=theme["settings_font"],
        )
        entry.insert(0, value)
        entry.pack(pady=5)
        return entry

    @staticmethod
    def _add_button(window, theme, text, command, pady):
        """Кнопка Save/Cancel у стилі теми."""
        ctk.CTkButton(
            window,
            text=text,
            command=command,
            fg_color=theme["settings_button_fg_color"],
            hover_color=theme["settings_button_hover_color"],
            text_color=theme["settings_button_text_color"],
            font=theme["settings_font"],
        ).pack(pady=pady)

    # ---- Вікно: іконка, геометрія, автозбереження позиції, клавіатура ----

    @staticmethod
    def _apply_deferred_icon(window):
        """Ставить іконку заголовка з відкладенням.

        CTkToplevel сам виставляє свою іконку ~через 200 мс після створення,
        тож ранній iconbitmap він затер би. try/except — бо відсутній .ico
        кинув би TclError.
        """
        def _apply():
            try:
                window.iconbitmap(HEADER_ICON_PATH)
            except Exception as e:
                print(f"INFO: settings window icon not set: {e}")

        window.after(250, _apply)

    @staticmethod
    def _apply_geometry(window):
        geometry_string = WindowHandler.load_window_size('Window_path', window)
        if geometry_string:
            window.geometry(geometry_string)
            return

        # Дефолт: позицію клампимо у видимий екран так само, як load_window_size.
        # Хардкод +668+661 на іншій конфігурації моніторів (RDP-реконект з
        # іншою роздільністю) міг опинитися поза екраном — і модальне вікно
        # було б невидиме, тоді як grab_set блокує решту UI. Розмір логічний
        # (400x270), у фізичну оцінку для клампа переводимо через масштаб CTk.
        scale = WindowHandler._window_scale(window)
        x, y = rdp.clamp_to_visible(668, 661, int(400 * scale), int(270 * scale))
        window.geometry(f'400x270+{x}+{y}')

    @staticmethod
    def _bind_geometry_autosave(window):
        """Зберігає позицію вікна при зміні — з дебаунсом, інакше кожна подія
        <Configure> під час перетягування переписує ini."""
        window._geometry_save_job = None

        def _save_geometry():
            window._geometry_save_job = None
            # Save/Cancel можуть знищити вікно, поки запис ще відкладений.
            if window.winfo_exists():
                WindowHandler.save_window_size('Window_path', window)

        def _on_configure(event):
            # <Configure> надходить і від дочірніх віджетів; реагуємо лише на
            # переміщення/ресайз самого вікна, щоб не смикати дебаунс дарма.
            if event.widget is not window:
                return
            if window._geometry_save_job is not None:
                window.after_cancel(window._geometry_save_job)
            window._geometry_save_job = window.after(500, _save_geometry)

        window.bind("<Configure>", _on_configure)

    @staticmethod
    def _bind_keyboard(window, save_command):
        """Enter — зберегти, Escape — закрити. Модальний діалог має реагувати
        на клавіатуру, а не лише на кліки по кнопках."""
        window.bind("<Return>", lambda _e: save_command())
        window.bind("<Escape>", lambda _e: window.destroy())

    # ---- Валідація і збереження ----

    @staticmethod
    def _validate(source_directory, destination_directory):
        """Повертає текст помилки або None, якщо шляхи придатні.

        Раніше поля писалися в config як є: порожній рядок, друкарська
        помилка чи source == destination тихо ламали копіювання аж до
        наступного перегляду налаштувань. Тепер відмова видима, а некоректні
        значення взагалі не зберігаються.
        """
        if not source_directory:
            return "Source directory is required."
        if not destination_directory:
            return "Destination directory is required."
        if not os.path.isdir(source_directory):
            return "Source directory does not exist."
        if os.path.normcase(os.path.abspath(source_directory)) == \
                os.path.normcase(os.path.abspath(destination_directory)):
            return "Source and destination must differ."
        # Неіснуючу теку призначення дозволяємо — застосунок її створить
        # (create_directory_if_not_exists). Але наявний ФАЙЛ за цим шляхом
        # текою стати не може.
        if os.path.exists(destination_directory) and \
                not os.path.isdir(destination_directory):
            return "Destination path is not a directory."
        return None

    @staticmethod
    def save_settings(app, settings_window, source_directory, destination_directory):
        """Валідує, зберігає шляхи, застосовує їх наживо і закриває вікно."""
        # .strip() прибирає випадкові пробіли, .strip('"') — лапки навколо
        # вставленого з провідника шляху; і те, й те інакше мовчки ламало б шлях.
        source_directory = source_directory.strip().strip('"')
        destination_directory = destination_directory.strip().strip('"')

        error = SettingsWindow._validate(source_directory, destination_directory)
        if error:
            status = getattr(settings_window, "_status_label", None)
            if status is not None and status.winfo_exists():
                status.configure(text=error)
            return  # Вікно лишається відкритим — користувач виправляє ввід.

        # ConfigManager.load_config при відсутньому файлі створює його лише
        # з секцією [Window] — байдуже, який це конфіг. Тож на свіжій
        # інсталяції (немає src/config.ini) секції [Settings] не існувало,
        # і .set() падав з NoSectionError просто по кнопці Save.
        if not app.config.has_section('Settings'):
            app.config.add_section('Settings')

        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'destination_directory', destination_directory)

        # Уникаємо циклічного імпорту, імпортуючи config_path тут
        from constants import CONFIG_PATH
        ConfigManager.save_atomic(app.config, CONFIG_PATH)

        # Застосувати наживо. Без цього зміна теки призначення діяла б лише
        # після перезапуску: її тримають закешованою обробник і watchdog.
        app.apply_directory_settings(source_directory, destination_directory)

        WindowHandler.save_window_size('Window_path', settings_window)
        settings_window.destroy()
