import tkinter as tk
from tkinter import ttk

from src.gui_synth import SyntheticDataScreen
from src.config import AppConfig
from src.gui_relational import RelationalDataScreen



class HomeScreen(ttk.Frame):
    """
    Home screen: user chooses which functionality to open.
    """
    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent, padding=16)
        self.app = app

        title = ttk.Label(self, text="Generic Data Application", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            self,
            text="Choose a tool to launch. (MVP: Synthetic Data Generator)",
        )
        subtitle.pack(anchor="w", pady=(0, 16))

        card = ttk.LabelFrame(self, text="Tools", padding=12)
        card.pack(fill="x")

        btn = ttk.Button(
            card,
            text="Synthetic Data → Generate / Preview / Export",
            command=lambda: self.app.show_screen("synthetic"),
        )
        btn.pack(fill="x", pady=6)

        # Placeholder buttons for future features
        ttk.Button(card, text="Relational Data → Customers / Orders / Items", command=lambda: self.app.show_screen("relational"),).pack(fill="x", pady=6)

        ttk.Button(card, text="(Coming soon) Multi-table relational generator", state="disabled").pack(fill="x", pady=6)
        ttk.Button(card, text="(Coming soon) Schema designer", state="disabled").pack(fill="x", pady=6)


class App(ttk.Frame):
    """
    App container that manages multiple 'screens' (Frames) and switches between them.
    """
    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        super().__init__(root)
        self.root = root
        self.cfg = cfg

        self.root.title("Generic Data Application")
        self.root.geometry("1000x650")

        self.pack(fill="both", expand=True)

        # Screens live in this container
        self.screen_container = ttk.Frame(self)
        self.screen_container.pack(fill="both", expand=True)

        # Create screens
        self.screens: dict[str, ttk.Frame] = {}

        self.screens["home"] = HomeScreen(self.screen_container, self)
        self.screens["synthetic"] = SyntheticDataScreen(self.screen_container, self, cfg)
        self.screens["relational"] = RelationalDataScreen(self.screen_container, self, cfg)


        # Put all screens in the same grid cell; raise the active one
        for frame in self.screens.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.screen_container.rowconfigure(0, weight=1)
        self.screen_container.columnconfigure(0, weight=1)

        self.show_screen("home")

    def show_screen(self, name: str) -> None:
        frame = self.screens[name]
        frame.tkraise()

    def go_home(self) -> None:
        self.show_screen("home")
