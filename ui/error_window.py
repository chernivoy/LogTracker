import os
import customtkinter as ctk

from utils import path as Path
from ui.image_manager import ImageManager
from ui.window_handler import WindowHandler
from tray_manager import TrayManager
from ui.context_menu import ContextMenu


class ErrorWindow:
    def __init__(self, app, root, image_manager):
        self.app = app
        self.root = root
        self.image_manager = image_manager
        self.widgets_to_update = {}

        self.setup_window()
        self.create_widgets()
        self.bind_events()

    def setup_window(self):
        """Налаштовує основні властивості вікна."""
        theme_manager = self.app.theme_manager
        current_theme = theme_manager.current_theme_data

        # Встановлення теми CTk
        ctk.set_appearance_mode(current_theme["ctk_appearance_mode"])
        ctk.set_default_color_theme(current_theme["default_color_theme"])

        TRANSPARENT_COLOR = "#000001"

        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        # self.root.attributes('-alpha', 0.9)
        self.root.attributes('-alpha', current_theme["window_alpha"])
        self.root.title("LogTracker")
        self.root.minsize(300, 100)

        # Завантаження та встановлення геометрії
        geometry_string = WindowHandler.load_window_size('Window', self.root)
        if geometry_string:
            self.root.geometry(geometry_string)
        else:
            self.root.geometry('400x200+100+100')

        header_icon_path = os.path.join("src", "Header.ico")
        bug_icon_path = os.path.join("src", "bug2.png")

        header_icon = Path.PathUtils.resource_path(header_icon_path)
        self.app.app_icon = self.image_manager.get_ctk_image(path=bug_icon_path, size=(16, 16))

        if os.path.exists(header_icon):
            self.root.iconbitmap(header_icon)
        else:
            print(f"Error: The icon file is not found by: {header_icon}")

        self.root.attributes('-topmost', True)

    def create_widgets(self):
        """Створює віджети для вікна та зберігає їх."""
        theme_manager = self.app.theme_manager
        current_theme = theme_manager.current_theme_data

        # Grid-конфігурація для кореневого вікна
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self.root, fg_color=current_theme["main_frame_fg_color"])
        self.main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        # НАЛАШТОВУЄМО GRID ДЛЯ main_frame:
        # row 0 (заголовок і кнопки) має weight 0
        # row 1 (фрейм з текстом) має weight 1, щоб розтягуватися по висоті
        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Створюємо дві колонки в main_frame:
        # Колонка 0 (для заголовка) - weight=1, щоб розтягувалася
        # Колонка 1 (для кнопок) - weight=0, щоб залишалася фіксованою
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)

        self.file_label = ctk.CTkLabel(
            self.main_frame,
            text=" LogTracker",
            anchor="w",
            text_color=current_theme["header_label_text_color"],
            font=current_theme["header_label_font"],
            image=self.app.app_icon,
            compound="left"
        )
        self.file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        self.to_tray_button = ctk.CTkButton(
            self.main_frame,
            text="x",
            height=20, width=20,
            fg_color=current_theme["to_tray_button_fg_color"],
            text_color=current_theme["to_tray_button_text_color"],
            font=current_theme["to_tray_button_font"],
            hover_color=current_theme["to_tray_button_hover_color"],
            command=lambda: TrayManager.minimize_to_tray(self.root, self.app)
        )
        self.to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        self.burger_button = ctk.CTkButton(
            self.main_frame,
            text="...",
            height=20, width=20,
            fg_color=current_theme["burger_button_fg_color"],
            text_color=current_theme["burger_button_text_color"],
            font=current_theme["burger_button_font"],
            hover_color=current_theme["burger_button_hover_color"],
            command=lambda: ContextMenu.show_context_menu(self.root, self.app, self.image_manager)
        )
        self.burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

        self.error_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=current_theme["error_frame_fg_color"],
            border_color=current_theme["error_frame_border_color"],
            border_width=current_theme["error_frame_border_width"]
        )
        self.error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        self.error_text_widget_frame = ctk.CTkFrame(self.error_frame, fg_color="transparent")
        # self.error_text_widget_frame.pack(fill="both", expand=True)
        self.error_text_widget_frame.grid(row=0, column=0, sticky="nsew")

        self.error_text_widget = ctk.CTkTextbox(
            self.error_text_widget_frame,
            height=20,
            corner_radius=current_theme["error_textbox_corner_radius"],
            border_width=current_theme["error_textbox_border_width"],
            fg_color=current_theme["error_textbox_fg_color"],
            wrap="word",
            state="disabled",
            text_color=current_theme["error_textbox_text_color"],
            font=current_theme["error_textbox_font"],
            yscrollcommand=lambda *args: None
        )
        # self.error_text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.error_text_widget.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.error_frame.grid_rowconfigure(0, weight=1)
        self.error_frame.grid_columnconfigure(0, weight=1)

        self.error_text_widget_frame.grid_rowconfigure(0, weight=1)
        self.error_text_widget_frame.grid_columnconfigure(0, weight=1)

        # Зберігаємо віджети, які потрібно оновлювати, у словник
        self.widgets_to_update = {
            "main_frame": self.main_frame,
            "file_label": self.file_label,
            "to_tray_button": self.to_tray_button,
            "burger_button": self.burger_button,
            "error_frame": self.error_frame,
            "error_text_widget_frame": self.error_text_widget_frame,
            "error_text_widget": self.error_text_widget
        }

        self.root.update_idletasks()
        self.root.update()

    def bind_events(self):
        """Прив'язує всі події до віджетів."""
        WindowHandler.round_corners(self.root, 30)
        WindowHandler.bind_resize_events(self.root)
        # У майбутньому, цей метод буде більш повним
        self.file_label.bind("<ButtonPress-1>", lambda event: WindowHandler.start_move(event, self.root))
        self.file_label.bind("<B1-Motion>", lambda event: WindowHandler.do_move(event, self.root))
        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, self.app))

    @staticmethod
    def create_error_window_old(root: ctk.CTk, app, image_manager: ImageManager):

        theme_manager = app.theme_manager
        current_theme = theme_manager.current_theme_data

        # Шляхи до іконок
        header_icon_path = os.path.join("src", "Header.ico")
        bug_icon_path = os.path.join("src", "bug2.png")

        # Встановлення теми CTk
        ctk.set_appearance_mode(current_theme["ctk_appearance_mode"])
        ctk.set_default_color_theme(current_theme["default_color_theme"])

        TRANSPARENT_COLOR = "#000001"

        root.overrideredirect(True)
        root.configure(bg=TRANSPARENT_COLOR)
        root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        # root.attributes('-alpha', 0.9)

        root.title("LogTracker")
        root.minsize(300, 100)

        # Завантаження та встановлення геометрії
        geometry_string = WindowHandler.load_window_size('Window', root)
        if geometry_string:
            root.geometry(geometry_string)
        else:
            root.geometry('400x200+100+100')

        header_icon = Path.PathUtils.resource_path(header_icon_path)

        app.app_icon = image_manager.get_ctk_image(path=bug_icon_path, size=(16, 16))

        if os.path.exists(header_icon):
            root.iconbitmap(header_icon)
        else:
            print(f"Error: The icon file is not found by: {header_icon}")

        root.attributes('-topmost', True)
        root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(root, app))
        root.update_idletasks()
        root.update()

        WindowHandler.round_corners(root, 30)

        main_frame = ctk.CTkFrame(root, fg_color=current_theme["main_frame_fg_color"])
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        file_label = ctk.CTkLabel(
            main_frame,
            text=" LogTracker",
            anchor="w",
            text_color=current_theme["header_label_text_color"],
            font=current_theme["header_label_font"],
            image=app.app_icon,
            compound="left"
        )
        file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        to_tray_button = ctk.CTkButton(
            main_frame,
            text="x",
            height=20,
            width=20,
            fg_color=current_theme["to_tray_button_fg_color"],
            text_color=current_theme["to_tray_button_text_color"],
            font=current_theme["to_tray_button_font"],
            hover_color=current_theme["to_tray_button_hover_color"],
            command=lambda: TrayManager.minimize_to_tray(root, app)
        )
        to_tray_button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        burger_button = ctk.CTkButton(
            main_frame,
            text="...",
            height=20,
            width=20,
            fg_color=current_theme["burger_button_fg_color"],
            text_color=current_theme["burger_button_text_color"],
            font=current_theme["burger_button_font"],
            hover_color=current_theme["burger_button_hover_color"],
            command=lambda: ContextMenu.show_context_menu(root, app, image_manager)
        )
        burger_button.grid(row=0, column=1, padx=30, pady=5, sticky="ne")

        error_frame = ctk.CTkFrame(
            main_frame,
            fg_color=current_theme["error_frame_fg_color"],
            border_color=current_theme["error_frame_border_color"],
            border_width=current_theme["error_frame_border_width"]
        )
        error_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=1, pady=1)

        error_text_widget_frame = ctk.CTkFrame(error_frame, fg_color="transparent")
        error_text_widget_frame.pack(fill="both", expand=True)

        error_text_widget = ctk.CTkTextbox(
            error_text_widget_frame,
            height=20,
            corner_radius=current_theme["error_textbox_corner_radius"],
            border_width=current_theme["error_textbox_border_width"],
            fg_color=current_theme["error_textbox_fg_color"],
            wrap="word",
            state="disabled",
            text_color=current_theme["error_textbox_text_color"],
            font=current_theme["error_textbox_font"],
            yscrollcommand=lambda *args: None
        )
        error_text_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Grid конфігурація
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Resize + переміщення
        WindowHandler.bind_resize_events(root)
        file_label.bind("<ButtonPress-1>", lambda event: WindowHandler.start_move(event, root))
        file_label.bind("<B1-Motion>", lambda event: WindowHandler.do_move(event, root))

        # ЗБЕРІГАЄМО ВІДЖЕТИ, ЯКІ ПОТРІБНО ОНОВЛЮВАТИ, У СЛОВНИК
        # Це ключовий крок для надійної зміни теми
        widgets_to_update = {
            "main_frame": main_frame,
            "file_label": file_label,
            "to_tray_button": to_tray_button,
            "burger_button": burger_button,
            "error_frame": error_frame,
            "error_text_widget_frame": error_text_widget_frame,
            "error_text_widget": error_text_widget
        }

        return root, error_text_widget, file_label, widgets_to_update
