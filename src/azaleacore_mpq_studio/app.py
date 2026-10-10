"""Interfaz gráfica inicial de AzaleaCore MPQ Studio."""

from __future__ import annotations

import struct
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .catalog import known_paths
from .mpq import MPQArchive, MPQError, MPQFile


DEFAULT_DATA_DIR = Path(r"D:\World of Warcraft 3.3.5a\Data")


def discover_mpqs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() == ".mpq"
        ),
        key=lambda path: str(path).casefold(),
    )


class MPQStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AzaleaCore MPQ Studio")
        self.root.geometry("920x620")
        self.root.minsize(720, 440)
        self.selected_path = tk.StringVar()
        self.status = tk.StringVar(value="Selecciona un archivo MPQ para comenzar.")
        self._configure_style()
        self._build_ui()
        self.refresh_archive_list()
        if self.selected_path.get():
            self.root.after_idle(self.open_selected)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
        style.configure("Muted.TLabel", foreground="#5f6b7a")
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 14))
        ttk.Label(header, text="AzaleaCore MPQ Studio", style="Title.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(header, text="SOLO LECTURA", foreground="#176a3a").pack(
            side=tk.RIGHT
        )

        chooser = ttk.LabelFrame(outer, text="Archivo MPQ", padding=10)
        chooser.pack(fill=tk.X, pady=(0, 12))
        self.combo = ttk.Combobox(
            chooser,
            textvariable=self.selected_path,
            state="readonly",
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.combo.bind("<<ComboboxSelected>>", lambda _event: self.open_selected())
        ttk.Button(chooser, text="Examinar...", command=self.browse).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            chooser, text="Actualizar", command=self.refresh_archive_list
        ).pack(side=tk.LEFT)

        browser = ttk.LabelFrame(outer, text="Contenido del MPQ", padding=8)
        browser.pack(fill=tk.BOTH, expand=True)
        columns = ("type", "size", "packed")
        self.tree = ttk.Treeview(browser, columns=columns, show="tree headings")
        self.tree.heading("#0", text="Nombre")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("packed", text="En MPQ")
        self.tree.column("#0", width=470, minwidth=220)
        self.tree.column("type", width=100, anchor=tk.CENTER)
        self.tree.column("size", width=110, anchor=tk.E)
        self.tree.column("packed", width=110, anchor=tk.E)
        scrollbar = ttk.Scrollbar(browser, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", self._toggle_folder)

        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel").pack(
            fill=tk.X, pady=(10, 0)
        )

    def refresh_archive_list(self) -> None:
        paths = discover_mpqs(DEFAULT_DATA_DIR)
        values = [str(path) for path in paths]
        current = self.selected_path.get()
        if current and current not in values and Path(current).is_file():
            values.insert(0, current)
        self.combo["values"] = values
        if not current and values:
            preferred = str(DEFAULT_DATA_DIR / "patch-9.MPQ")
            self.selected_path.set(preferred if preferred in values else values[0])

    def browse(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Seleccionar archivo MPQ",
            initialdir=str(
                DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()
            ),
            filetypes=(
                ("Archivos MPQ", "*.MPQ *.mpq"),
                ("Todos los archivos", "*.*"),
            ),
        )
        if not filename:
            return
        values = list(self.combo["values"])
        if filename not in values:
            values.insert(0, filename)
            self.combo["values"] = values
        self.selected_path.set(filename)
        self.open_selected()

    def open_selected(self) -> None:
        path = Path(self.selected_path.get())
        self._clear_tree()
        try:
            with MPQArchive(path) as archive:
                inventory = archive.inventory(known_paths())
        except (OSError, MPQError, struct.error) as exc:
            self.status.set("No se pudo abrir el archivo.")
            messagebox.showerror("Error al abrir MPQ", str(exc), parent=self.root)
            return

        self._populate_tree(inventory.files)
        source = (
            "(listfile) + catálogo"
            if inventory.has_listfile
            else "catálogo de rutas conocidas"
        )
        self.status.set(
            f"{path.name} · {len(inventory.files)} identificados de "
            f"{inventory.active_entries} entradas · {source} · Solo lectura"
        )
        if inventory.unknown_entries:
            self.status.set(
                self.status.get()
                + f" · {inventory.unknown_entries} entrada(s) todavía sin nombre"
            )

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _populate_tree(self, files: tuple[MPQFile, ...]) -> None:
        folders: dict[tuple[str, ...], str] = {}
        for item in files:
            parts = tuple(
                part
                for part in item.path.replace("/", "\\").split("\\")
                if part
            )
            parent = ""
            for depth, part in enumerate(parts[:-1], start=1):
                key = parts[:depth]
                if key not in folders:
                    folders[key] = self.tree.insert(
                        parent,
                        tk.END,
                        text=part,
                        values=("Carpeta", "", ""),
                        open=False,
                    )
                parent = folders[key]
            if parts:
                suffix = Path(parts[-1]).suffix.upper().lstrip(".") or "Archivo"
                self.tree.insert(
                    parent,
                    tk.END,
                    text=parts[-1],
                    values=(
                        suffix,
                        format_bytes(item.size),
                        format_bytes(item.packed_size),
                    ),
                )

    def _toggle_folder(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if item and self.tree.get_children(item):
            self.tree.item(item, open=not bool(self.tree.item(item, "open")))


def format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"


def run() -> None:
    root = tk.Tk()
    MPQStudioApp(root)
    root.mainloop()
