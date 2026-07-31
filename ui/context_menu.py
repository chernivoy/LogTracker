# Файл: ui/context_menu.py

import tkinter as tk

from ui.settings_window import SettingsWindow
from ui.ui_assets import (
    EXIT_ICON_PATH, SETTINGS_ICON_PATH, THEME_ICON_PATH,
    DARK_THEME_ICON_PATH, LIGHT_THEME_ICON_PATH, GRAPHITE_THEME_ICON_PATH
)
from ui.window_handler import WindowHandler


class ContextMenu:
    def __init__(self, root, app, image_manager):
        self.root = root
        self.app = app
        self.image_manager = image_manager
        self.menu = None
        self._icons = {}
        self._has_icons = False

    def show_menu(self, button):
        current_theme = self.app.theme_manager.current_theme_data

        # Шрифт меню робимо ІДЕНТИЧНИМ до поля з помилкою. Поле — це CTkTextbox,
        # і CTk домножує його темовий error_textbox_font на widget_scaling,
        # переводячи кегль у ПІКСЕЛІ (напр. ("Inter", 13) → "Inter -26" при
        # scale 2.0). Нативний tk.Menu такого масштабування не отримує (Tk не
        # бачить per-monitor DPI при awareness V2), тож замість ручної формули
        # копіюємо вже готовий масштабований спек із поля помилки.
        menu_font = self._error_field_font()

        self._load_icons()

        # Кольори меню беремо з теми (context_menu_*). Фон навмисно збігається з
        # тим, що РЕНДЕРИТЬ головне вікно (див. значення в themes/*), щоб меню
        # читалось як частина того ж вікна.
        menu_colors = {
            "bg": current_theme["context_menu_bg"],
            "fg": current_theme["context_menu_fg"],
            "activebackground": current_theme["context_menu_active_bg"],
            "activeforeground": current_theme["context_menu_active_fg"],
        }
        # borderwidth=0 + relief=flat прибирає 3D-рамку, але цього НЕ досить:
        # activeborderwidth дефолтом = 1 і малює світлий 1px бордер по периметру
        # меню й навколо активного пункту (на темному фоні виглядає білим). Тому
        # явно 0 — меню стає пласким кольоровим блоком без світлої облямівки.
        self.menu = tk.Menu(self.root, tearoff=0, font=menu_font,
                            borderwidth=0, activeborderwidth=0, relief="flat", **menu_colors)

        self._populate_menu(menu_font, menu_colors)

        # Позиція під кнопкою. winfo_* — фізичні пікселі (при DPI-awareness), саме
        # їх чекає tk_popup; якщо меню не влазить у екран — Tk сам підправить.
        x = button.winfo_rootx() + button.winfo_width() // 2
        y = button.winfo_rooty() + button.winfo_height()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _error_field_font(self):
        """Спек шрифту, яким ЗАРАЗ рендериться поле з помилкою — щоб tk.Menu мав
        ІДЕНТИЧНИЙ шрифт.

        Беремо його з внутрішнього tkinter.Text у CTkTextbox: cget('font') віддає
        вже масштабований CTk спек (сім'я + кегль у пікселях, напр. "Inter -26"),
        придатний як font= для нативного меню. Так меню збігається з полем за
        сім'єю, кеглем і DPI автоматично й лишається однаковим при зміні теми,
        без ручного відтворення формули масштабування CTk.

        Фолбек (якщо внутрішній віджет недоступний) відтворює масштаб CTk для
        темового error_textbox_font вручну: розмір у пікселях = -round(base*scale),
        сім'я й накреслення — ті самі.
        """
        try:
            return self.app.error_text_widget._textbox.cget("font")
        except Exception:
            scale = WindowHandler._window_scale(self.root)
            base = self.app.theme_manager.current_theme_data["error_textbox_font"]
            return (base[0], -round(abs(base[1]) * scale), *base[2:])

    def _populate_menu(self, menu_font, menu_colors):
        # Одна побудова замість двох гілок: коли всіх іконок нема
        # (_has_icons=False), _img повертає порожній dict і пункти будуються лише
        # з текстом. get_tk_photo_image повертає None на відсутній файл, тож без
        # цієї перевірки в меню потрапив би image=None замість текстового фолбеку.
        icons = self._icons if self._has_icons else {}

        def _img(key):
            return {"image": icons[key], "compound": "left"} if icons else {}

        # Сепаратори МАЮТЬ явний background = фон меню. Порожній background
        # змушував Tk на Windows брати системний СВІТЛИЙ колір (SystemButtonFace,
        # майже білий) як базу для 3D-гравірованої лінії — звідси біла смуга на
        # темному фоні. Похідна від темного фону лінія стає делікатним
        # розділювачем у колір теми, а не білою (кути меню все одно прямі —
        # native tk.Menu не дає їх заокруглити).
        sep_bg = menu_colors["bg"]

        theme_menu = tk.Menu(self.menu, tearoff=0, font=menu_font,
                             borderwidth=0, activeborderwidth=0, relief="flat", **menu_colors)
        theme_menu.add_command(label="Dark", command=lambda: self.app.toggle_theme("dark"), **_img("dark_theme"))
        theme_menu.add_separator(background=sep_bg)
        theme_menu.add_command(label="Light", command=lambda: self.app.toggle_theme("light"), **_img("light_theme"))
        theme_menu.add_separator(background=sep_bg)
        theme_menu.add_command(label="Graphite", command=lambda: self.app.toggle_theme("graphite"), **_img("graphite_theme"))

        self.menu.add_cascade(label="Theme", menu=theme_menu, **_img("theme"))
        self.menu.add_separator(background=sep_bg)
        self.menu.add_command(label="Path settings",
                              command=lambda: SettingsWindow.open_settings_window(self.app), **_img("settings"))
        self.menu.add_separator(background=sep_bg)
        self.menu.add_command(label="Exit", command=self.app.on_closing, **_img("exit"))

    def _load_icons(self):
        # base_icon_size — ЛОГІЧНИЙ розмір (16×16); get_tk_photo_image домножить
        # його на scale до фізичного. Джерельні PNG зберігаються у 128×128, тож
        # це завжди ЗМЕНШення (крізь LANCZOS) — чітко на будь-якому DPI.
        base_icon_size = (16, 16)
        # Той самий масштаб CTk, яким масштабується шрифт меню (_error_field_font):
        # беремо розмір іконки й кегль тексту з ОДНОГО джерела, щоб не розходились.
        # Кешоване значення CTk, без Win32-виклику на кожне відкриття меню.
        scale = WindowHandler._window_scale(self.root)
        icon_paths = {
            'settings': SETTINGS_ICON_PATH,
            'exit': EXIT_ICON_PATH,
            'theme': THEME_ICON_PATH,
            'dark_theme': DARK_THEME_ICON_PATH,
            'light_theme': LIGHT_THEME_ICON_PATH,
            'graphite_theme': GRAPHITE_THEME_ICON_PATH,
        }

        self._icons = {}
        try:
            # Кеш ImageManager (за шляхом+розміром+DPI) переживає повторні
            # відкриття меню, тож force_reload не потрібен — PNG читається один раз.
            for name, path in icon_paths.items():
                self._icons[name] = self.image_manager.get_tk_photo_image(
                    path, base_icon_size, scale=scale)
        except Exception as e:
            print(f"Error when loading menu icons: {e}")

        # get_tk_photo_image повертає None на відсутній файл (не кидає виняток),
        # тож меню з іконками показуємо лише коли завантажились УСІ. Часткова
        # невдача → чистимо словник і йдемо на текстовий фолбек у _populate_menu.
        self._has_icons = bool(self._icons) and all(
            img is not None for img in self._icons.values())
        if not self._has_icons:
            self._icons = {}
            print("WARNING: not all menu icons loaded, falling back to text labels.")
