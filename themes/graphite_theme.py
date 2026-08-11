# themes/graphite_theme.py
# Графітова тема: суцільний непрозорий фон #383b40 (світліший за near-black
# dark), ті самі акценти, що й dark. На відміну від dark (main_frame прозорий →
# показує gray14), тут фон — конкретний колір, тож settings_bg/context_menu_bg
# дорівнюють саме йому.
THEME_SETTINGS = {
    "ctk_appearance_mode": "Dark",
    "default_color_theme": "blue",
    "main_frame_fg_color": "#383b40",
    # Контур самого вікна — колір бордера полів цієї теми, на крок світліший за
    # фон вікна (#383b40). Логіка та сама, що в dark.
    "window_border_color": "#4a4d52",
    "window_border_width": 1,
    # Window Transparency
    "transparent_color": "#000001",
    "window_alpha": 0.9,
    #Стиль для header_label
    "header_label_text_color": "#5f8dfc",
    "header_label_font": ("Inter", 13, "bold"),
    #Стиль для to_tray_button
    "to_tray_button_text_color": "#ce885f",
    "to_tray_button_font": ("Inter", 11, "bold"),
    "to_tray_button_fg_color": "transparent",
    "to_tray_button_hover_color": "#2d436e",
    #Стиль для burger_button
    "burger_button_text_color": "#ce885f",
    "burger_button_font": ("Inter", 11, "bold"),
    "burger_button_fg_color": "transparent",
    "burger_button_hover_color": "#2d436e",
    #Стиль для error_frame
    "error_frame_fg_color": "transparent",
    # Збігається з фоном поля (main_frame_fg_color), щоб бордер був невидимий.
    "error_frame_border_color": "#383b40",
    "error_frame_border_width": 1,
    #Стиль для error_textbox
    "error_textbox_fg_color": "transparent",
    "error_textbox_text_color": "#b4b361",
    "error_textbox_font": ("Inter", 13),
    "error_textbox_border_width": 0,
    "error_textbox_corner_radius": 1,
    #Стиль для context_menu (бургер-меню — власний попап, ui/context_menu.py)
    # Та сама логіка, що в dark: меню висить над вікном, тож його фон — піднята
    # поверхня, на крок світліша за фон вікна (#383b40), як і в плашки Toast.
    "context_menu_bg": "#42464d",
    "context_menu_fg": "#e2e0e6",
    "context_menu_active_bg": "#2d436e",
    "context_menu_active_fg": "#e2e0e6",
    "context_menu_border_color": "#4a4d52",
    "context_menu_separator_color": "#4a4d52",
    "context_menu_accent_color": "#5f8dfc",
    "context_menu_muted_fg": "#9b9aa3",
    "context_menu_font": ("Inter", 13),
    #Стиль для settings_panel (смуга Path settings унизу вікна)
    # Стиль співпадає з головним вікном: фон як у вікна теми (main_frame_fg_color),
    # текст нейтральний, поля темніші за фон, кнопки — синій акцент.
    "settings_bg": "#383b40",
    "settings_text_color": "#e2e0e6",
    "settings_font": ("Inter", 13),
    "settings_entry_fg_color": "#2b2c2f",
    "settings_entry_border_color": "#4a4d52",
    "settings_button_fg_color": "#2d436e",
    "settings_button_hover_color": "#375a94",
    "settings_button_text_color": "#e2e0e6",
    #Стиль для toast (плашка «Copied!» у заголовку, одразу за іменем файла)
    # Та сама логіка, що в dark: фон на крок світліший за фон вікна (#383b40),
    # рамка кольору бордера полів, акцент — у тексті, той самий, що в імені
    # файла поруч.
    "toast_bg": "#42464d",
    "toast_border_color": "#4a4d52",
    "toast_text_color": "#5f8dfc",
    "toast_font": ("Inter", 12, "bold"),
}
