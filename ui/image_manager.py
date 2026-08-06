import customtkinter as ctk
from PIL import Image

from utils import path as Path


class ImageManager:
    """
    Відповідає за завантаження та кешування зображень для віджетів CustomTkinter.

    Окремої гілки для нативних tkinter-віджетів тут більше немає: єдиним її
    споживачем було бургер-меню на tk.Menu, якому доводилося масштабувати
    PhotoImage вручну (Tk не бачить per-monitor DPI при awareness V2). Меню
    тепер будується на CTk-віджетах, а CTkImage масштабує себе сам.
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
            print(f"INFO: Retrieving CTk image from cache for path: {full_path}")
            return self._cache[cache_key]

        try:
            image = Image.open(full_path)
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            self._cache[cache_key] = ctk_image
            print(f"INFO: Loaded and cached new CTk image for path: {full_path}")
            return ctk_image
        except FileNotFoundError:
            print(f"Error: icon file not found at path: {full_path}")
            return None
