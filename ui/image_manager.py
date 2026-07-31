import tkinter as tk

import customtkinter as ctk
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
            print(f"INFO: Retrieving CTk image from cache for path: {full_path}")
            return self._cache[cache_key]

        try:
            image = Image.open(full_path)
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            self._cache[cache_key] = ctk_image
            print(f"INFO: Loaded and cached new CTk image for path: {full_path}")
            return ctk_image
        except FileNotFoundError:
            print(f"Помилка: Файл іконки не знайдено за шляхом: {full_path}")
            return None

    def get_tk_photo_image(self, path: str, base_size: tuple, force_reload: bool = False,
                           scale: float | None = None) -> tk.PhotoImage | None:
        """
        Завантажує та масштабує зображення для нативних Tkinter віджетів (напр., Menu).

        Результат кешується за (шлях, розмір, DPI): бургер-меню будується заново
        на кожне відкриття, і без кешу кожен клік знову читав би PNG з диска й
        гнав LANCZOS-resize. Ключ включає DPI, тож зміна масштабу (реконект RDP)
        дає новий запис, а не стару картинку. force_reload обходить кеш.

        scale — DPI-множник ЯВНО. Викликач (context_menu) передає сюди той самий
        масштаб CTk, яким масштабується шрифт меню (WindowHandler._window_scale),
        щоб розмір іконки й кегль тексту бралися з ОДНОГО джерела й не розходились.
        Це ще й уникає Win32-виклику get_windows_dpi_scale на кожне відкриття меню.
        Якщо None — запасний варіант: власний запит DPI монітора (Win32).

        Джерело тепер зберігається у високій роздільності (128×128), тож 16*scale
        завжди ЗМЕНШує його (навіть при 200% DPI → 32 px) — LANCZOS-зменшення дає
        чіткість на всіх DPI, на відміну від колишнього збільшення 16→32.
        """
        full_path = Path.PathUtils.resource_path(path)
        dpi_scale_factor = scale if scale is not None else rdp.get_windows_dpi_scale(self.root)
        cache_key = (full_path, "tk", base_size, dpi_scale_factor)

        if not force_reload and cache_key in self._cache:
            print(f"INFO: Retrieving Tk PhotoImage from cache for path: {full_path}")
            return self._cache[cache_key]

        try:
            pil_image = Image.open(full_path)
            scaled_width = int(base_size[0] * dpi_scale_factor)
            scaled_height = int(base_size[1] * dpi_scale_factor)

            if scaled_width <= 0: scaled_width = 1
            if scaled_height <= 0: scaled_height = 1
            print(
                f"INFO: Scaling Tk PhotoImage from {base_size} to ({scaled_width}, {scaled_height}) with DPI factor {dpi_scale_factor}")

            resized_image = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)
            tk_photo = ImageTk.PhotoImage(resized_image)
            self._cache[cache_key] = tk_photo
            print(f"INFO: Loaded and cached new Tk PhotoImage for path: {full_path}")
            return tk_photo
        except FileNotFoundError:
            print(f"Помилка: Файл іконки Tkinter PhotoImage не знайдено за шляхом: {full_path}")
            return None
        except Exception as e:
            print(f"Помилка завантаження tk.PhotoImage з {full_path}: {e}")
            return None
