import customtkinter as ctk
from ui.window_handler import WindowHandler


class SettingsWindow:

    @staticmethod
    def open_settings_window(app):
        """
        Відкриває вікно налаштувань для шляхів.
        """
        settings_window = ctk.CTkToplevel(app.root)
        settings_window.title("Path settings")

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

        entry_target_directory = ctk.CTkEntry(settings_window, width=300)
        entry_target_directory.insert(0, app.directory)
        entry_target_directory.pack(pady=5)

        # Кнопки збереження та відміни
        btn_save = ctk.CTkButton(
            settings_window,
            text="Save",
            command=lambda: SettingsWindow.save_settings(
                app,
                settings_window,
                entry_source_directory.get(),
                entry_target_directory.get()
            )
        )
        btn_save.pack(pady=10)

        btn_cancel = ctk.CTkButton(
            settings_window,
            text="Cancel",
            command=settings_window.destroy
        )
        btn_cancel.pack(pady=5)

        # Зберігання позиції вікна налаштувань при його зміні
        settings_window.bind("<Configure>",
                             lambda event: WindowHandler.save_window_size('Window_path', settings_window))

    @staticmethod
    def save_settings(app, settings_window, source_directory, target_directory):
        """
        Зберігає налаштування шляхів та закриває вікно налаштувань.
        """
        app.config.set('Settings', 'source_directory', source_directory)
        app.config.set('Settings', 'directory', target_directory)

        # Уникаємо циклічного імпорту, імпортуючи config_path тут
        from logger import config_path
        with open(config_path, 'w') as configfile:
            app.config.write(configfile)

        app.source_directory = source_directory
        app.directory = target_directory

        WindowHandler.save_window_size('Window_path', settings_window)
        settings_window.destroy()
