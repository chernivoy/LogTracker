import customtkinter as ctk

from tray_manager import TrayManager
from ui.context_menu import ContextMenu
from ui.toast import Toast
from ui.ui_assets import APP_ICON_PATH, CLOSE_ICON_PATH, BURGER_MENU_ICON_PATH, APP_ICO_PATH
from ui.window_handler import WindowHandler


class ErrorWindow:
    def __init__(self, app, root, image_manager):
        self.app = app
        self.root = root
        self.image_manager = image_manager
        self.context_menu = ContextMenu(self.root, self.app, self.image_manager)
        self.toast = None  # створюється в create_widgets, коли є контейнер
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

        transparent_color = current_theme["transparent_color"]

        self.root.overrideredirect(True)
        self.root.configure(bg=transparent_color)
        self.root.wm_attributes('-transparentcolor', transparent_color)
        self.root.attributes('-alpha', current_theme["window_alpha"])
        self.root.title("ADAICA: Log Tracker")
        self.root.iconbitmap(APP_ICO_PATH)
        # minsize виставляється в create_widgets → apply_dynamic_min_height
        # (динамічна висота під заголовок). Ранній фіксований minsize тут був
        # зайвий: вікно не показується до mainloop, а до того minsize ні на що
        # не впливає.

        self._load_window_geometry()

        # Тримаємо посилання на self (ErrorWindow), а не на app: іконки потрібні
        # лише цьому вікну, а живе воно стільки ж, скільки app.error_window, тож
        # від GC вони захищені так само — без засмічення простору імен app.
        # size=(16,16) — ЛОГІЧНИЙ розмір; CTkImage домножує його на масштаб
        # вікна (DPI) при малюванні. Джерело app_icon.png — 256px, тож на
        # будь-якому DPI це чітке ЗМЕНШення, а не розмите збільшення.
        self.app_icon = self.image_manager.get_ctk_image(path=APP_ICON_PATH, size=(16, 16))
        self.close_icon = self.image_manager.get_ctk_image(path=CLOSE_ICON_PATH, size=(11, 11))
        self.burger_menu_icon = self.image_manager.get_ctk_image(path=BURGER_MENU_ICON_PATH, size=(11, 11))

        self.root.attributes('-topmost', True)

    def _load_window_geometry(self):
        # Завантаження та встановлення геометрії
        geometry_string = WindowHandler.load_window_size('Window', self.root)
        if geometry_string:
            self.root.geometry(geometry_string)
        else:
            self.root.geometry('400x200+100+100')

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

        # Три колонки в main_frame:
        # Колонка 0 (заголовок) — weight=1, розтягується й ЗВУЖУЄТЬСЯ першою;
        # Колонки 1 (бургер) і 2 (згорнути в трей) — weight=0, фіксовані.
        # Раніше обидві кнопки стояли в одній комірці (column=1) і не
        # накладались лише завдяки різному padx — крихко до зміни ширини/іконок.
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)
        self.main_frame.grid_columnconfigure(2, weight=0)

        self.file_label = ctk.CTkLabel(
            self.main_frame,
            text=" LogTracker",
            anchor="w",
            text_color=current_theme["header_label_text_color"],
            font=current_theme["header_label_font"],
            image=self.app_icon,
            compound="left"
        )
        self.file_label.grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        self.to_tray_button = ctk.CTkButton(
            self.main_frame,
            text="",
            height=20, width=20,
            fg_color=current_theme["to_tray_button_fg_color"],
            text_color=current_theme["to_tray_button_text_color"],
            font=current_theme["to_tray_button_font"],
            hover_color=current_theme["to_tray_button_hover_color"],
            image=self.close_icon,
            compound="right",
            command=lambda: TrayManager.minimize_to_tray(self.root, self.app)
        )
        self.to_tray_button.grid(row=0, column=2, padx=(0, 5), pady=5, sticky="ne")

        self.burger_button = ctk.CTkButton(
            self.main_frame,
            text="",
            height=20, width=20,
            fg_color=current_theme["burger_button_fg_color"],
            text_color=current_theme["burger_button_text_color"],
            font=current_theme["burger_button_font"],
            hover_color=current_theme["burger_button_hover_color"],
            image=self.burger_menu_icon,
            compound="left",
            command=lambda: self.context_menu.show_menu(self.burger_button)
        )
        self.burger_button.grid(row=0, column=1, padx=(0, 5), pady=5, sticky="ne")

        self.error_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=current_theme["error_frame_fg_color"],
            border_color=current_theme["error_frame_border_color"],
            border_width=current_theme["error_frame_border_width"]
        )
        self.error_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=1, pady=1)

        # Верх контент-фрейму = нижня межа заголовка. WindowHandler бере це,
        # щоб уся смуга заголовка над контентом рухала вікно, а не ресайзила.
        self.root._content_frame = self.error_frame

        # Текстбокс кладемо прямо в error_frame. Раніше між ними стояв прозорий
        # error_text_widget_frame, який нічого не стилізував (update_widgets_theme
        # його не чіпав) — зайвий рівень вкладеності.
        self.error_text_widget = ctk.CTkTextbox(
            self.error_frame,
            height=20,
            corner_radius=current_theme["error_textbox_corner_radius"],
            border_width=current_theme["error_textbox_border_width"],
            fg_color=current_theme["error_textbox_fg_color"],
            wrap="word",
            state="disabled",
            text_color=current_theme["error_textbox_text_color"],
            font=current_theme["error_textbox_font"],
            # Ховаємо смуги прокрутки CTkTextbox (при мінімальному розмірі вікна
            # текст переносився й з'являвся вертикальний скролбар). Скрол колесом
            # лишається — його дає сама tkinter.Text, а не скролбар. Попередній
            # yscrollcommand=lambda:None не працював: CTk перекриває його своїм
            # _y_scrollbar.set.
            activate_scrollbars=False,
        )

        self.error_text_widget.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        self.error_frame.grid_rowconfigure(0, weight=1)
        self.error_frame.grid_columnconfigure(0, weight=1)

        # Плашка-підтвердження ('Copied!') — оверлей ВСЕРЕДИНІ вікна, тож
        # створюється тут, коли вже є всі віджети, відносно яких вона стає:
        # мітка з іменем файла, кнопка (далі неї в заголовку не можна) і саме
        # поле помилки. Один екземпляр на вікно на ОБИДВА місця показу — він
        # прибирає попередню плашку при новому показі, тож повторні
        # натискання не громадять їх одна на одну.
        self.toast = Toast(self.root, self.app.theme_manager,
                           self.file_label, self.burger_button, self.error_frame,
                           bind_move=self._bind_move)

        # Зберігаємо віджети, які потрібно оновлювати, у словник
        self.widgets_to_update = {
            "main_frame": self.main_frame,
            "file_label": self.file_label,
            "to_tray_button": self.to_tray_button,
            "burger_button": self.burger_button,
            "error_frame": self.error_frame,
            "error_text_widget": self.error_text_widget
        }

        # root.update() (а не лише update_idletasks) потрібен тут: він мапить
        # вікно на його реальному моніторі ще під час побудови, щоб CustomTkinter
        # застосував збережену геометрію у ФІЗИЧНОМУ розмірі за DPI саме цього
        # монітора. Без нього при старті на моніторі з іншим DPI, ніж первинний,
        # вікно з'являлося замалим (логічний розмір без домноження на масштаб) і
        # виправлялося лише після ручного ресайзу. update_idletasks вікно НЕ
        # мапить, тож самого його недостатньо. logger.run() ще й повторно
        # застосовує геометрію через after(), коли масштаб уже точний.
        self.root.update_idletasks()
        self.root.update()
        self.apply_dynamic_min_height()

    def apply_dynamic_min_height(self):
        """Рахує мінімальну висоту вікна (заголовок + запас під ~5 рядків) і
        застосовує її як root._min_height_logical та root.minsize.

        Без цього при найменшому розмірі (100 лог.) нижня грань обрізала
        останній рядок у полі помилки: заголовок з'їдав ~40 лог., і для тексту
        лишалося менш ніж 3 рядки. Заголовок міряємо (його висота залежить від
        шрифту й DPI). Значення читає і WindowHandler.do_resize, щоб межа
        ручного ресайзу збігалася з root.minsize. Викликається в create_widgets
        і повторно з logger.run() через after(), коли winfo_* уже точні.
        """
        try:
            scale = WindowHandler._window_scale(self.root)
            header_logical = int(WindowHandler._header_bottom(self.root) / scale)
            min_height_logical = max(100, header_logical + 95)
        except Exception:
            min_height_logical = 135
        self.root._min_height_logical = min_height_logical
        self.root.minsize(300, min_height_logical)

    def bind_events(self):
        """Прив'язує події до віджетів: ресайз — на root (bind_resize_events),
        переміщення за заголовок — напряму на file_label і main_frame."""
        WindowHandler.round_corners(self.root, WindowHandler.CORNER_RADIUS)
        WindowHandler.bind_resize_events(self.root)

        self._bind_move(self.file_label)
        self._bind_move(self.main_frame)
        self.root.protocol("WM_DELETE_WINDOW", lambda: TrayManager.minimize_to_tray(self.root, self.app))

    def _bind_move(self, widget):
        """Робить віджет «ручкою» для перетягування вікна.

        Окремий метод, бо ту саму пару прив'язок отримує не лише статичний
        заголовок, а й плашка Toast, яка з'являється в ньому на час показу.
        """
        widget.bind("<ButtonPress-1>", lambda event: WindowHandler.start_move(event, self.root))
        widget.bind("<B1-Motion>", lambda event: WindowHandler.do_move(event, self.root))
