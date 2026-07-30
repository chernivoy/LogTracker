import customtkinter as ctk

from ui.ui_assets import HEADER_ICON_PATH
from ui.window_handler import WindowHandler


class SettingsWindow:
    """Модальне вікно налаштування шляхів.

    Стиль повністю береться з поточної теми через групу ключів settings_* —
    ті самі, що є в усіх темах (контракт: набір ключів однаковий скрізь). Тож
    вікно візуально належить до того ж застосунку, що й головне вікно з полем
    помилки, і виглядає коректно в кожній темі. Тема застосовується один раз
    при відкритті: вікно модальне (grab_set), тож змінити тему, поки воно
    відкрите, неможливо — живого оновлення стилю не потрібно.
    """

    @staticmethod
    def open_settings_window(app):
        """Відкриває вікно налаштувань для шляхів, стилізоване під поточну тему."""
        theme = app.theme_manager.current_theme_data

        window = ctk.CTkToplevel(app.root, fg_color=theme["settings_bg"])
        window.title("Path settings")

        SettingsWindow._apply_deferred_icon(window)
        SettingsWindow._apply_geometry(window)
        window.minsize(400, 270)
        window.grab_set()  # Заблокувати інші вікна до закриття цього

        source_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to source directory:", app.source_directory)
        destination_entry = SettingsWindow._add_labeled_entry(
            window, theme, "Path to destination directory:", app.destination_directory)

        SettingsWindow._add_button(
            window, theme, "Save", pady=10,
            command=lambda: SettingsWindow.save_settings(
                app, window, source_entry.get(), destination_entry.get()))
        SettingsWindow._add_button(
            window, theme, "Cancel", pady=5, command=window.destroy)

        SettingsWindow._bind_geometry_autosave(window)

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

    # ---- Вікно: іконка, геометрія, автозбереження позиції ----

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
        else:
            window.geometry('400x270+668+661')  # Дефолтні розміри та позиція

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
    def save_settings(app, settings_window, source_directory, destination_directory):
        """
        Зберігає налаштування шляхів та закриває вікно налаштувань.
        """
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
        with open(CONFIG_PATH, 'w') as configfile:
            app.config.write(configfile)

        app.source_directory = source_directory
        app.destination_directory = destination_directory

        WindowHandler.save_window_size('Window_path', settings_window)
        settings_window.destroy()
