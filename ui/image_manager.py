import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
from utils import path as Path
from utils import rdp


class ImageManager:
    """
    Відповідає за завантаження, кешування та масштабування зображень
    для віджетів CustomTkinter і Tkinter.
    """

    def __init__(self, root: ctk.CTk):
        self.root = root
        self._cache = {}

    def get_ctk_image(self, path: str, size: tuple) -> ctk.CTkImage | None:
        """
        Завантажує зображення для CTk віджетів.
        """
        full_path = Path.PathUtils.resource_path(path)
        cache_key = (full_path, "ctk", size)

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            image = Image.open(full_path)
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            self._cache[cache_key] = ctk_image
            return ctk_image
        except FileNotFoundError:
            print(f"Помилка: Файл іконки не знайдено за шляхом: {full_path}")
            return None

    def get_tk_photo_image(self, path: str, base_size: tuple) -> tk.PhotoImage | None:
        """
        Завантажує та масштабує зображення для нативних Tkinter віджетів (напр., Menu).
        """
        full_path = Path.PathUtils.resource_path(path)
        dpi_scale_factor = rdp.get_windows_dpi_scale(self.root)
        cache_key = (full_path, "tk", base_size, dpi_scale_factor)

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            pil_image = Image.open(full_path)
            scaled_width = int(base_size[0] * dpi_scale_factor)
            scaled_height = int(base_size[1] * dpi_scale_factor)

            if scaled_width <= 0: scaled_width = 1
            if scaled_height <= 0: scaled_height = 1

            resized_image = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)
            tk_photo = ImageTk.PhotoImage(resized_image)
            self._cache[cache_key] = tk_photo
            return tk_photo
        except FileNotFoundError:
            print(f"Помилка: Файл іконки Tkinter PhotoImage не знайдено за шляхом: {full_path}")
            return None
        except Exception as e:
            print(f"Помилка завантаження tk.PhotoImage з {full_path}: {e}")
            return None
