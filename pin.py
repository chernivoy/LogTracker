import customtkinter as ctk
import ctypes
from ctypes import wintypes

class RoundedWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Задаем начальные размеры окна
        self.geometry("350x140")

        # Убираем стандартный заголовок окна
        self.overrideredirect(True)

        # Установка цвета фона для предотвращения артефактов
        self.config(bg="white")

        # Основной фрейм окна
        self.main_frame = ctk.CTkFrame(self, corner_radius=20, fg_color='white')
        self.main_frame.pack(fill="both", expand=True)

        # Создание пользовательского заголовка окна
        self.title_bar = ctk.CTkFrame(self.main_frame, height=50, fg_color="white", corner_radius=2)
        self.title_bar.pack(fill="x", padx=0, pady=0, side="top")

        # Метка для заголовка окна
        self.title_label = ctk.CTkLabel(self.title_bar, fg_color="transparent", text="Настройки путей", anchor="w")
        self.title_label.pack(side="left", padx=10)

        # Кнопка Pin
        self.pin_button = ctk.CTkButton(self.title_bar, text="Pin", width=25, command=self.toggle_pin)
        self.pin_button.pack(side="right", padx=10)

        # Логика перемещения окна
        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.on_motion)

        # Флаг закрепления окна
        self.is_pinned = False

        # Пример содержимого окна
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="White")
        self.content_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.example_label = ctk.CTkLabel(self.content_frame, text="Пример содержимого окна")
        self.example_label.pack(pady=10)

        # Кнопка для закрытия окна
        self.close_button = ctk.CTkButton(self.title_bar, text="x", width=10,height=10, command=self.destroy, corner_radius=10)
        self.close_button.pack(side="right", padx=(0, 10))

        # Обновляем размеры окна после создания пользовательского заголовка
        self.update_idletasks()
        self.round_corners(20)

    def toggle_pin(self):
        """Переключает закрепление окна поверх всех окон."""
        self.is_pinned = not self.is_pinned
        self.attributes("-topmost", self.is_pinned)
        self.pin_button.configure(text="Unpin" if self.is_pinned else "Pin")

    def start_move(self, event):
        """Запоминает начальные координаты при перемещении окна."""
        self.x = event.x
        self.y = event.y

    def on_motion(self, event):
        """Перемещает окно в новую позицию."""
        x = event.x_root - self.x
        y = event.y_root - self.y
        self.geometry(f"+{x}+{y}")

    def round_corners(self, radius=30):
        """Скругляет углы окна."""
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, self.winfo_width(), self.winfo_height(), radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)

# Пример использования
if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.geometry("800x600")

    # Кнопка для открытия окна "Настройки путей"
    open_settings_button = ctk.CTkButton(root, text="Открыть настройки путей", command=lambda: RoundedWindow(root))
    open_settings_button.pack(pady=1)

    root.mainloop()
