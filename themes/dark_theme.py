# themes/dark_theme.py
# Налаштування для темної теми
THEME_SETTINGS = {
    "name": "dark",
    "ctk_appearance_mode": "Dark",
    "default_color_theme": "blue",
    "main_frame_fg_color": "transparent",
    # Window Transparency
    "transparent_color": "#000001",
    "window_alpha": 0.9,
    #Стиль для header_label
    "header_label_text_color": "#5f8dfc",
    "header_label_font": ("Inter", 13, "bold"),
    #Стиль для button
    "button_text_color": "#ce885f",
    "button_font": ("Inter", 12),
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
    # Поле в dark прозоре (немає суцільного фону), тож бордер кольором
    # transparent_color лишав би прозору «щілину», а будь-який інший колір було б
    # видно. Тому рамку тут прибираємо зовсім (width 0) — колір нижче не рендериться.
    "error_frame_border_color": "#000001",
    "error_frame_border_width": 0,
    #Стиль для error_textbox
    "error_textbox_fg_color": "transparent",
    "error_textbox_text_color": "#b4b361",
    "error_textbox_font": ("Inter", 13),
    "error_textbox_border_width": 0,
    "error_textbox_corner_radius": 1,
    "error_text_color": "#b4b361",
    #Стиль для context_menu
    # Суцільний темний під примарний (transparent) фон вікна теми.
    "context_menu_bg": "#2b2c2f",
    "context_menu_fg": "#e2e0e6",
    "context_menu_active_bg": "#2d436e",
    "context_menu_active_fg": "#e2e0e6",
    #Стиль для settings_window (модальне вікно Path settings)
    # Стиль співпадає з головним вікном: фон як у вікна теми (context_menu_bg),
    # текст нейтральний, поля темніші за фон, кнопки — синій акцент.
    "settings_bg": "#2b2c2f",
    "settings_text_color": "#e2e0e6",
    "settings_font": ("Inter", 13),
    "settings_entry_fg_color": "#1e1f22",
    "settings_entry_border_color": "#3a3d42",
    "settings_button_fg_color": "#2d436e",
    "settings_button_hover_color": "#375a94",
    "settings_button_text_color": "#e2e0e6",
    "text_color": "#e2e0e6",
}