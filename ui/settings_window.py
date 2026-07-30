import customtkinter as ctk

from ui.ui_assets import HEADER_ICON_PATH
from ui.window_handler import WindowHandler


class SettingsWindow:

    @staticmethod
    def open_settings_window(app):
        """
        Відкриває вікно налаштувань для шляхів.
        """
        settings_window = ctk.CTkToplevel(app.root)
        settings_window.title("Path settings")

        # Іконку заголовка виставляємо з відкладенням: CTkToplevel сам ставить
        # свою іконку ~через 200 мс після створення, тож ранній iconbitmap він
        # затер би. try/except — бо відсутній .ico кинув би TclError.
        def _apply_icon():
            try:
                settings_window.iconbitmap(HEADER_ICON_PATH)
            except Exception as e:
                print(f"INFO: settings window icon not set: {e}")

        settings_window.after(250, _apply_icon)

        # Завантаження та застосування геометрії для підвікна
        geometry_string = WindowHandler.load_window_size('Window_path', settings_window)
        if geometry_string:
            settings_window.geometry(geometry_string)
        else:
            settings_window.geometry('400x270+668+661')  # Дефолтні розміри та позиція

        settings_window.minsize(400, 270)
        settings_window.grab_set()  # Заблокувати інші вікна до закриття цього

        # Віджети для налаштувань шляхів
        label_source_directory = ctk.CTkLabel(settings_window, text="Path to source directory:")
        label_source_directory.pack(pady=10)

        entry_source_directory = ctk.CTkEntry(settings_window, width=300)
        entry_source_directory.insert(0, app.source_directory)
        entry_source_directory.pack(pady=5)

        label_target_directory = ctk.CTkLabel(settings_window, text="Path to destination directory:")
        label_target_directory.pack(pady=10)

        entry_destination_directory = ctk.CTkEntry(settings_window, width=300)
        entry_destination_directory.insert(0, app.destination_directory)
        entry_destination_directory.pack(pady=5)

        # Кнопки збереження та відміни
        btn_save = ctk.CTkButton(
            settings_window,
            text="Save",
            command=lambda: SettingsWindow.save_settings(
                app,
                settings_window,
                entry_source_directory.get(),
                entry_destination_directory.get()
            )
        )
        btn_save.pack(pady=10)

        btn_cancel = ctk.CTkButton(
            settings_window,
            text="Cancel",
            command=settings_window.destroy
        )
        btn_cancel.pack(pady=5)

        # Зберігання позиції вікна налаштувань при його зміні — з дебаунсом,
        # інакше кожна подія <Configure> під час перетягування переписує ini.
        settings_window._geometry_save_job = None

        def _save_geometry():
            settings_window._geometry_save_job = None
            # Save/Cancel можуть знищити вікно, поки запис ще відкладений.
            if settings_window.winfo_exists():
                WindowHandler.save_window_size('Window_path', settings_window)

        def _on_configure(event):
            # <Configure> надходить і від дочірніх віджетів; реагуємо лише на
            # переміщення/ресайз самого вікна, щоб не смикати дебаунс дарма.
            if event.widget is not settings_window:
                return
            if settings_window._geometry_save_job is not None:
                settings_window.after_cancel(settings_window._geometry_save_job)
            settings_window._geometry_save_job = settings_window.after(500, _save_geometry)

        settings_window.bind("<Configure>", _on_configure)

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
