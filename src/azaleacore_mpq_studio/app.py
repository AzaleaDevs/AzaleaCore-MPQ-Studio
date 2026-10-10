"""Interfaz gráfica de AzaleaCore MPQ Studio."""

from __future__ import annotations

import hashlib
import struct
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .catalog import known_paths
from .mpq import (
    MPQ_FILE_COMPRESS,
    MPQ_FILE_DELETE_MARKER,
    MPQ_FILE_ENCRYPTED,
    MPQ_FILE_EXISTS,
    MPQ_FILE_FIX_KEY,
    MPQ_FILE_IMPLODE,
    MPQ_FILE_PATCH_FILE,
    MPQ_FILE_SECTOR_CRC,
    MPQ_FILE_SINGLE_UNIT,
    MPQArchive,
    MPQError,
    MPQFile,
    load_listfile_paths,
)
from .packer import (
    PackagingError,
    PatchPlan,
    create_and_install_patch,
    is_protected_gluexml,
    plan_patch,
)
from .workspace import ExportRequest, Workspace, export_files, prepare_workspace


DEFAULT_DATA_DIR = Path(r"D:\World of Warcraft 3.3.5a\Data")


@dataclass(frozen=True)
class QueuedExport:
    source_mpq: Path
    file: MPQFile


def filter_mpq_files(files: tuple[MPQFile, ...], query: str) -> tuple[MPQFile, ...]:
    """Filtra por cualquier fragmento de la ruta, sin distinguir mayúsculas."""
    normalized = query.strip().casefold()
    if not normalized:
        return files
    return tuple(item for item in files if normalized in item.path.casefold())


def describe_mpq_flags(flags: int) -> str:
    """Convierte los indicadores MPQ conocidos en una descripción legible."""
    known_flags = (
        (MPQ_FILE_EXISTS, "EXISTE"),
        (MPQ_FILE_COMPRESS, "COMPRIMIDO"),
        (MPQ_FILE_IMPLODE, "IMPLODE"),
        (MPQ_FILE_ENCRYPTED, "CIFRADO"),
        (MPQ_FILE_FIX_KEY, "CLAVE AJUSTADA"),
        (MPQ_FILE_PATCH_FILE, "DELTA"),
        (MPQ_FILE_SINGLE_UNIT, "UNIDAD ÚNICA"),
        (MPQ_FILE_DELETE_MARKER, "MARCADO BORRADO"),
        (MPQ_FILE_SECTOR_CRC, "CRC DE SECTORES"),
    )
    labels = [label for mask, label in known_flags if flags & mask]
    known_mask = sum(mask for mask, _label in known_flags)
    unknown = flags & ~known_mask
    if unknown:
        labels.append(f"OTROS 0x{unknown:08X}")
    return f"0x{flags:08X}" + (f" · {' | '.join(labels)}" if labels else "")


def calculate_mpq_sha256(source: Path, internal_path: str) -> str:
    """Calcula el SHA-256 del contenido lógico de un archivo dentro del MPQ."""
    with MPQArchive(source) as archive:
        payload = archive.read_file(internal_path)
    if payload is None:
        raise MPQError(f"No se encontró el archivo: {internal_path}")
    return hashlib.sha256(payload).hexdigest()


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
        self.root.geometry("1180x720")
        self.root.minsize(900, 560)

        self.selected_path = tk.StringVar()
        self.search_text = tk.StringVar()
        self.listfile_text = tk.StringVar(value="No cargado")
        self.workspace_text = tk.StringVar(value="No seleccionada")
        self.export_status = tk.StringVar(value="Selecciona un archivo MPQ.")
        self.import_status = tk.StringVar(value="Selecciona una carpeta de trabajo.")
        self.destination_text = tk.StringVar(value="No seleccionado")
        self.plan_text = tk.StringVar(value="Selecciona el directorio de destino.")
        self.glue_warning = tk.StringVar()
        self.property_name = tk.StringVar(value="Sin selección")
        self.property_type = tk.StringVar(value="—")
        self.property_source = tk.StringVar(value="—")
        self.property_path = tk.StringVar(value="—")
        self.property_size = tk.StringVar(value="—")
        self.property_packed_size = tk.StringVar(value="—")
        self.property_flags = tk.StringVar(value="—")
        self.property_sha256 = tk.StringVar(value="—")

        self.workspace: Workspace | None = None
        self.patch_plan: PatchPlan | None = None
        self.current_archive: Path | None = None
        self.current_files: tuple[MPQFile, ...] = ()
        self.current_archive_summary = ""
        self.external_listfile: Path | None = None
        self.external_listfile_paths: tuple[str, ...] = ()
        self.archive_items: dict[str, MPQFile] = {}
        self.export_queue: dict[str, QueuedExport] = {}
        self.package_items: dict[str, Path] = {}
        self.package_queue: dict[str, Path] = {}

        self._configure_style()
        self._build_ui()
        self.refresh_archive_list()
        self._update_actions()
        if self.selected_path.get():
            self.root.after_idle(self.open_selected)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 10))
        style.configure("Muted.TLabel", foreground="#5f6b7a")
        style.configure("Success.TLabel", foreground="#176a3a")
        style.configure("Warning.TLabel", foreground="#a33a16")
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(16, 10))
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(header, text="AzaleaCore MPQ Studio", style="Title.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(header, text="PARCHE MÍNIMO Y SEGURO", style="Success.TLabel").pack(
            side=tk.RIGHT
        )

        workspace_bar = ttk.LabelFrame(outer, text="Carpeta de trabajo", padding=8)
        workspace_bar.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(workspace_bar, textvariable=self.workspace_text).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            workspace_bar, text="Seleccionar...", command=self.choose_workspace
        ).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.export_tab = ttk.Frame(notebook, padding=6)
        self.import_tab = ttk.Frame(notebook, padding=6)
        notebook.add(self.export_tab, text="EXPORTAR")
        notebook.add(self.import_tab, text="IMPORTAR")
        self._build_export_tab()
        self._build_import_tab()

    def _build_export_tab(self) -> None:
        chooser = ttk.Frame(self.export_tab)
        chooser.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(chooser, text="Archivo MPQ:").pack(side=tk.LEFT, padx=(0, 6))
        self.combo = ttk.Combobox(
            chooser, textvariable=self.selected_path, state="readonly"
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.combo.bind("<<ComboboxSelected>>", lambda _event: self.open_selected())
        ttk.Button(chooser, text="Examinar...", command=self.browse_archive).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            chooser, text="Actualizar", command=self.refresh_archive_list
        ).pack(side=tk.LEFT)

        listfile_bar = ttk.Frame(self.export_tab)
        listfile_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(listfile_bar, text="Listfile externo:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(
            listfile_bar, textvariable=self.listfile_text, style="Muted.TLabel"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            listfile_bar, text="Cargar...", command=self.browse_listfile
        ).pack(side=tk.RIGHT, padx=(6, 0))
        self.clear_listfile_button = ttk.Button(
            listfile_bar, text="Quitar", command=self.clear_listfile, state=tk.DISABLED
        )
        self.clear_listfile_button.pack(side=tk.RIGHT)

        search = ttk.Frame(self.export_tab)
        search.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search, text="Buscar:").pack(side=tk.LEFT, padx=(0, 6))
        self.search_entry = ttk.Entry(search, textvariable=self.search_text)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(search, text="Limpiar", command=lambda: self.search_text.set("")).pack(
            side=tk.LEFT
        )
        self.search_text.trace_add("write", lambda *_args: self._apply_archive_filter())
        self.root.bind("<Control-f>", self._focus_search)

        panes = ttk.Panedwindow(self.export_tab, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(panes, text="Contenido del MPQ", padding=6)
        middle = ttk.Frame(panes, padding=8)
        right = ttk.LabelFrame(panes, text="Pila de extracción", padding=6)
        panes.add(left, weight=4)
        panes.add(middle, weight=0)
        panes.add(right, weight=4)

        self.archive_tree = self._make_tree(left, ("type", "size"))
        self.archive_tree.heading("#0", text="Nombre")
        self.archive_tree.heading("type", text="Tipo")
        self.archive_tree.heading("size", text="Tamaño")
        self.archive_tree.column("#0", width=370, minwidth=180)
        self.archive_tree.column("type", width=75, anchor=tk.CENTER)
        self.archive_tree.column("size", width=90, anchor=tk.E)
        self.archive_tree.bind("<Double-1>", self._archive_double_click)
        self.archive_tree.bind("<<TreeviewSelect>>", self._update_properties)

        ttk.Button(middle, text=">>", width=6, command=self.queue_selected).pack(
            pady=(150, 8)
        )
        ttk.Button(middle, text="<<", width=6, command=self.unqueue_selected).pack()

        self.export_tree = self._make_tree(right, ("source", "size"))
        self.export_tree.heading("#0", text="Ruta interna")
        self.export_tree.heading("source", text="MPQ")
        self.export_tree.heading("size", text="Tamaño")
        self.export_tree.column("#0", width=390, minwidth=190)
        self.export_tree.column("source", width=110)
        self.export_tree.column("size", width=90, anchor=tk.E)
        self.export_tree.bind("<Double-1>", lambda _event: self.unqueue_selected())

        properties = ttk.LabelFrame(
            self.export_tab, text="Propiedades de la selección", padding=8
        )
        properties.pack(fill=tk.X, pady=(8, 0))
        self._property_row(properties, 0, "Nombre", self.property_name)
        self._property_row(properties, 0, "Tipo", self.property_type, column=2)
        self._property_row(
            properties, 1, "MPQ de origen", self.property_source, value_span=3
        )
        self._property_row(
            properties, 2, "Ruta interna", self.property_path, value_span=3
        )
        self._property_row(properties, 3, "Tamaño real", self.property_size)
        self._property_row(
            properties, 3, "Tamaño almacenado", self.property_packed_size, column=2
        )
        self._property_row(
            properties, 4, "Flags MPQ", self.property_flags, value_span=3
        )
        self._property_row(
            properties, 5, "SHA-256", self.property_sha256, value_span=2
        )
        self.hash_button = ttk.Button(
            properties,
            text="Calcular SHA-256",
            command=self._calculate_selected_sha256,
            state=tk.DISABLED,
        )
        self.hash_button.grid(row=5, column=3, sticky=tk.E, padx=(10, 0), pady=1)
        properties.columnconfigure(1, weight=1)
        properties.columnconfigure(3, weight=1)

        footer = ttk.Frame(self.export_tab)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(footer, textvariable=self.export_status, style="Muted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.extract_button = ttk.Button(
            footer, text="Extraer selección", command=self.extract_queue
        )
        self.extract_button.pack(side=tk.RIGHT)

    @staticmethod
    def _property_row(
        parent: ttk.LabelFrame,
        row: int,
        title: str,
        variable: tk.StringVar,
        *,
        column: int = 0,
        value_span: int = 1,
    ) -> None:
        ttk.Label(parent, text=f"{title}:", style="Section.TLabel").grid(
            row=row, column=column, sticky=tk.W, padx=(0, 10), pady=1
        )
        ttk.Label(parent, textvariable=variable).grid(
            row=row,
            column=column + 1,
            columnspan=value_span,
            sticky=tk.W,
            pady=1,
        )

    def _build_import_tab(self) -> None:
        source_bar = ttk.Frame(self.import_tab)
        source_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(source_bar, text="Origen:").pack(side=tk.LEFT, padx=(0, 6))
        self.package_dir_label = ttk.Label(
            source_bar, text="Selecciona primero una carpeta de trabajo."
        )
        self.package_dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            source_bar, text="Actualizar", command=self.refresh_package_tree
        ).pack(side=tk.RIGHT)

        panes = ttk.Panedwindow(self.import_tab, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(panes, text="Carpeta empaquetar", padding=6)
        middle = ttk.Frame(panes, padding=8)
        right = ttk.LabelFrame(panes, text="Contenido del nuevo MPQ", padding=6)
        panes.add(left, weight=4)
        panes.add(middle, weight=0)
        panes.add(right, weight=4)

        self.package_tree = self._make_tree(left, ("type", "size"))
        self.package_tree.heading("#0", text="Nombre")
        self.package_tree.heading("type", text="Tipo")
        self.package_tree.heading("size", text="Tamaño")
        self.package_tree.column("#0", width=360, minwidth=180)
        self.package_tree.column("type", width=75, anchor=tk.CENTER)
        self.package_tree.column("size", width=90, anchor=tk.E)
        self.package_tree.bind("<Double-1>", self._package_double_click)

        ttk.Button(middle, text=">>", width=7, command=self.queue_package_selected).pack(
            pady=(110, 8)
        )
        ttk.Button(middle, text="Todo >>", width=8, command=self.queue_package_all).pack(
            pady=(0, 8)
        )
        ttk.Button(middle, text="<<", width=7, command=self.unqueue_package).pack()

        self.package_queue_tree = self._make_tree(right, ("size",))
        self.package_queue_tree.heading("#0", text="Ruta interna")
        self.package_queue_tree.heading("size", text="Tamaño")
        self.package_queue_tree.column("#0", width=430, minwidth=210)
        self.package_queue_tree.column("size", width=100, anchor=tk.E)
        self.package_queue_tree.bind(
            "<Double-1>", lambda _event: self.unqueue_package()
        )

        ttk.Label(
            self.import_tab,
            textvariable=self.glue_warning,
            style="Warning.TLabel",
            wraplength=1050,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 0))

        destination = ttk.LabelFrame(
            self.import_tab, text="Directorio de instalación", padding=8
        )
        ttk.Label(
            self.import_tab, textvariable=self.import_status, style="Muted.TLabel"
        ).pack(fill=tk.X, pady=(8, 0))
        destination.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(destination, textvariable=self.destination_text).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            destination, text="Seleccionar...", command=self.choose_destination
        ).pack(side=tk.RIGHT)

        plan_bar = ttk.Frame(self.import_tab)
        plan_bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(plan_bar, textvariable=self.plan_text, style="Muted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.import_button = ttk.Button(
            plan_bar,
            text="Crear e importar parche",
            command=self.create_patch,
        )
        self.import_button.pack(side=tk.RIGHT)

    @staticmethod
    def _make_tree(parent: ttk.Widget, columns: tuple[str, ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(
            frame,
            columns=columns,
            show="tree headings",
            selectmode="extended",
            height=7,
        )
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def choose_workspace(self) -> None:
        selected = filedialog.askdirectory(parent=self.root, title="Carpeta de trabajo")
        if not selected:
            return
        try:
            self.workspace = prepare_workspace(selected)
        except OSError as exc:
            messagebox.showerror("No se pudo preparar la carpeta", str(exc), parent=self.root)
            return
        self.workspace_text.set(str(self.workspace.root))
        self.package_dir_label.configure(text=str(self.workspace.package_dir))
        self.import_status.set("Carpetas exportar y empaquetar preparadas.")
        self.refresh_package_tree()
        self._update_actions()

    def refresh_archive_list(self) -> None:
        values = [str(path) for path in discover_mpqs(DEFAULT_DATA_DIR)]
        current = self.selected_path.get()
        if current and current not in values and Path(current).is_file():
            values.insert(0, current)
        self.combo["values"] = values
        if not current and values:
            preferred = str(DEFAULT_DATA_DIR / "patch-9.MPQ")
            self.selected_path.set(preferred if preferred in values else values[0])

    def browse_archive(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Seleccionar archivo MPQ",
            initialdir=str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()),
            filetypes=(("Archivos MPQ", "*.MPQ *.mpq"), ("Todos", "*.*")),
        )
        if filename:
            values = list(self.combo["values"])
            if filename not in values:
                values.insert(0, filename)
                self.combo["values"] = values
            self.selected_path.set(filename)
            self.open_selected()

    def browse_listfile(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Seleccionar listfile externo",
            filetypes=(
                ("Listfile o texto", "(listfile) *.txt *.lst"),
                ("Todos los archivos", "*.*"),
            ),
        )
        if not filename:
            return
        try:
            paths = load_listfile_paths(filename)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("No se pudo leer el listfile", str(exc), parent=self.root)
            return
        self.external_listfile = Path(filename)
        self.external_listfile_paths = paths
        self.listfile_text.set(f"{self.external_listfile.name} · {len(paths)} rutas")
        self.clear_listfile_button.configure(state=tk.NORMAL)
        if self.selected_path.get():
            self.open_selected()

    def clear_listfile(self) -> None:
        self.external_listfile = None
        self.external_listfile_paths = ()
        self.listfile_text.set("No cargado")
        self.clear_listfile_button.configure(state=tk.DISABLED)
        if self.selected_path.get():
            self.open_selected()

    def open_selected(self) -> None:
        path = Path(self.selected_path.get())
        self._clear_tree(self.archive_tree)
        self.archive_items.clear()
        try:
            with MPQArchive(path) as archive:
                inventory = archive.inventory((*known_paths(), *self.external_listfile_paths))
        except (OSError, MPQError, struct.error) as exc:
            self.export_status.set("No se pudo abrir el archivo.")
            messagebox.showerror("Error al abrir MPQ", str(exc), parent=self.root)
            return
        self.current_archive = path
        self.current_files = inventory.files
        self.current_archive_summary = (
            f"{path.name}: {len(inventory.files)} identificados de "
            f"{inventory.active_entries} entradas · Solo lectura"
            + (
                f" · listfile externo: {len(self.external_listfile_paths)} rutas"
                if self.external_listfile is not None
                else ""
            )
            + (
                f" · {inventory.unknown_entries} todavía sin nombre"
                if inventory.unknown_entries
                else ""
            )
        )
        self._apply_archive_filter()

    def _apply_archive_filter(self) -> None:
        if not hasattr(self, "archive_tree"):
            return
        visible = filter_mpq_files(self.current_files, self.search_text.get())
        self._clear_tree(self.archive_tree)
        self.archive_items.clear()
        self._clear_properties()
        self._populate_archive_tree(visible)
        if self.search_text.get().strip():
            self.export_status.set(
                f"{self.current_archive_summary} · {len(visible)} resultado(s) visibles"
            )
        else:
            self.export_status.set(self.current_archive_summary or "Selecciona un archivo MPQ.")

    def _focus_search(self, _event: tk.Event) -> str:
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)
        return "break"

    def _populate_archive_tree(self, files: tuple[MPQFile, ...]) -> None:
        folders: dict[tuple[str, ...], str] = {}
        for item in files:
            parts = tuple(part for part in item.path.replace("/", "\\").split("\\") if part)
            parent = ""
            for depth, part in enumerate(parts[:-1], start=1):
                key = parts[:depth]
                if key not in folders:
                    folders[key] = self.archive_tree.insert(
                        parent, tk.END, text=part, values=("Carpeta", ""), open=False
                    )
                parent = folders[key]
            node = self.archive_tree.insert(
                parent,
                tk.END,
                text=parts[-1],
                values=(Path(parts[-1]).suffix.upper().lstrip("."), format_bytes(item.size)),
            )
            self.archive_items[node] = item

    def _archive_double_click(self, event: tk.Event) -> None:
        item = self.archive_tree.identify_row(event.y)
        if not item:
            return
        if item in self.archive_items:
            self.archive_tree.selection_set(item)
            self.queue_selected()
        elif self.archive_tree.get_children(item):
            self.archive_tree.item(item, open=not bool(self.archive_tree.item(item, "open")))

    def _update_properties(self, _event: tk.Event | None = None) -> None:
        selection = self.archive_tree.selection()
        if len(selection) != 1:
            self._clear_properties()
            return
        node = selection[0]
        file = self.archive_items.get(node)
        if file is not None:
            self.property_name.set(Path(file.path).name)
            self.property_type.set(Path(file.path).suffix.upper().lstrip(".") or "Archivo")
            self.property_source.set(
                str(self.current_archive) if self.current_archive is not None else "—"
            )
            self.property_path.set(file.path)
            self.property_size.set(f"{format_bytes(file.size)} ({file.size:,} bytes)")
            self.property_packed_size.set(
                f"{format_bytes(file.packed_size)} ({file.packed_size:,} bytes)"
            )
            self.property_flags.set(describe_mpq_flags(file.flags))
            self.property_sha256.set("Pendiente de calcular")
            self.hash_button.configure(state=tk.NORMAL)
            return
        self.property_name.set(self.archive_tree.item(node, "text"))
        self.property_type.set("Carpeta")
        self.property_source.set(
            str(self.current_archive) if self.current_archive is not None else "—"
        )
        self.property_path.set("—")
        self.property_size.set("—")
        self.property_packed_size.set("—")
        self.property_flags.set("—")
        self.property_sha256.set("—")
        self.hash_button.configure(state=tk.DISABLED)

    def _calculate_selected_sha256(self) -> None:
        selection = self.archive_tree.selection()
        if len(selection) != 1 or self.current_archive is None:
            return
        file = self.archive_items.get(selection[0])
        if file is None:
            return
        self.hash_button.configure(state=tk.DISABLED)
        self.property_sha256.set("Calculando…")
        self.root.update_idletasks()
        try:
            digest = calculate_mpq_sha256(self.current_archive, file.path)
        except (OSError, MPQError, struct.error) as exc:
            self.property_sha256.set("No disponible")
            messagebox.showerror("Error al calcular SHA-256", str(exc), parent=self.root)
        else:
            self.property_sha256.set(digest)
        finally:
            self.hash_button.configure(state=tk.NORMAL)

    def _clear_properties(self) -> None:
        self.property_name.set("Sin selección")
        self.property_type.set("—")
        self.property_source.set("—")
        self.property_path.set("—")
        self.property_size.set("—")
        self.property_packed_size.set("—")
        self.property_flags.set("—")
        self.property_sha256.set("—")
        if hasattr(self, "hash_button"):
            self.hash_button.configure(state=tk.DISABLED)

    def queue_selected(self) -> None:
        if self.current_archive is None:
            return
        for node in self.archive_tree.selection():
            item = self.archive_items.get(node)
            if item is not None:
                self.export_queue[item.path.casefold()] = QueuedExport(self.current_archive, item)
        self._refresh_export_queue()

    def unqueue_selected(self) -> None:
        for node in self.export_tree.selection():
            path = self.export_tree.item(node, "text")
            self.export_queue.pop(path.casefold(), None)
        self._refresh_export_queue()

    def _refresh_export_queue(self) -> None:
        self._clear_tree(self.export_tree)
        for queued in sorted(self.export_queue.values(), key=lambda item: item.file.path.casefold()):
            self.export_tree.insert(
                "",
                tk.END,
                text=queued.file.path,
                values=(queued.source_mpq.name, format_bytes(queued.file.size)),
            )
        self._update_actions()

    def extract_queue(self) -> None:
        if self.workspace is None or not self.export_queue:
            return
        requests = tuple(
            ExportRequest(item.source_mpq, item.file.path)
            for item in self.export_queue.values()
        )
        overwrite = False
        collisions = [
            self.workspace.export_dir.joinpath(*request.internal_path.split("\\"))
            for request in requests
            if self.workspace.export_dir.joinpath(*request.internal_path.split("\\")).exists()
        ]
        if collisions:
            overwrite = messagebox.askyesno(
                "Archivos existentes",
                f"Ya existen {len(collisions)} archivo(s). ¿Quieres sobrescribirlos?",
                parent=self.root,
            )
            if not overwrite:
                return
        try:
            results = export_files(requests, self.workspace, overwrite=overwrite)
        except (OSError, MPQError, ValueError) as exc:
            messagebox.showerror("Error de extracción", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "Extracción completada",
            f"Se extrajeron {len(results)} archivo(s) en:\n{self.workspace.export_dir}",
            parent=self.root,
        )
        self.export_status.set(f"Extracción completada: {len(results)} archivo(s).")

    def refresh_package_tree(self) -> None:
        self._clear_tree(self.package_tree)
        self.package_items.clear()
        if self.workspace is None:
            return
        root = self.workspace.package_dir
        folders: dict[Path, str] = {root: ""}
        paths = sorted(root.rglob("*"), key=lambda path: str(path).casefold())
        for path in paths:
            if path.is_symlink():
                continue
            parent_node = folders.get(path.parent, "")
            if path.is_dir():
                node = self.package_tree.insert(
                    parent_node, tk.END, text=path.name, values=("Carpeta", ""), open=False
                )
                folders[path] = node
            elif path.is_file():
                node = self.package_tree.insert(
                    parent_node,
                    tk.END,
                    text=path.name,
                    values=(path.suffix.upper().lstrip(".") or "Archivo", format_bytes(path.stat().st_size)),
                )
                self.package_items[node] = path
        self.import_status.set(f"{len(self.package_items)} archivo(s) disponibles para empaquetar.")

    def _package_double_click(self, event: tk.Event) -> None:
        item = self.package_tree.identify_row(event.y)
        if not item:
            return
        if item in self.package_items:
            self.package_tree.selection_set(item)
            self.queue_package_selected()
        elif self.package_tree.get_children(item):
            self.package_tree.item(item, open=not bool(self.package_tree.item(item, "open")))

    def queue_package_selected(self) -> None:
        selected = set(self.package_tree.selection())
        nodes = list(selected)
        for node in list(selected):
            nodes.extend(self._descendant_files(node))
        for node in nodes:
            path = self.package_items.get(node)
            if path is not None:
                self._queue_package_path(path)
        self._refresh_package_queue()

    def queue_package_all(self) -> None:
        for path in self.package_items.values():
            self._queue_package_path(path)
        self._refresh_package_queue()

    def _queue_package_path(self, path: Path) -> None:
        if self.workspace is None:
            return
        relative = path.relative_to(self.workspace.package_dir).as_posix().replace("/", "\\")
        self.package_queue[relative.casefold()] = path

    def _descendant_files(self, node: str) -> list[str]:
        result: list[str] = []
        for child in self.package_tree.get_children(node):
            if child in self.package_items:
                result.append(child)
            result.extend(self._descendant_files(child))
        return result

    def unqueue_package(self) -> None:
        for node in self.package_queue_tree.selection():
            internal = self.package_queue_tree.item(node, "text")
            self.package_queue.pop(internal.casefold(), None)
        self._refresh_package_queue()

    def _refresh_package_queue(self) -> None:
        self._clear_tree(self.package_queue_tree)
        queued_internal_paths: list[str] = []
        if self.workspace is not None:
            for path in sorted(self.package_queue.values(), key=lambda item: str(item).casefold()):
                internal = path.relative_to(self.workspace.package_dir).as_posix().replace("/", "\\")
                queued_internal_paths.append(internal)
                self.package_queue_tree.insert(
                    "", tk.END, text=internal, values=(format_bytes(path.stat().st_size),)
                )
        if any(is_protected_gluexml(path) for path in queued_internal_paths):
            self.glue_warning.set(
                "ADVERTENCIA GLUEXML: el cliente WoW 3.3.5a original rechazará "
                "este parche como interfaz de inicio de sesión dañada. Úsalo sólo "
                "con un cliente de laboratorio compatible."
            )
        else:
            self.glue_warning.set("")
        self._update_actions()

    def choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Directorio donde se instalará el parche",
            initialdir=str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()),
        )
        if not selected:
            return
        self.destination_text.set(selected)
        try:
            self.patch_plan = plan_patch(selected)
            self.plan_text.set(self.patch_plan.message)
        except PackagingError as exc:
            self.patch_plan = None
            self.plan_text.set(str(exc))
        self._update_actions()

    def create_patch(self) -> None:
        if self.workspace is None or self.patch_plan is None or not self.package_queue:
            return
        files = []
        for path in self.package_queue.values():
            internal = path.relative_to(self.workspace.package_dir).as_posix().replace("/", "\\")
            files.append((internal, path))
        ordered = sorted(files)
        visible = ordered[:20]
        summary = "\n".join(internal for internal, _ in visible)
        if len(ordered) > len(visible):
            summary += f"\n... y {len(ordered) - len(visible)} archivo(s) más"
        glue_notice = ""
        if any(is_protected_gluexml(internal) for internal, _ in files):
            glue_notice = (
                "\n\nADVERTENCIA: la selección contiene Interface\\GlueXML. "
                "El cliente 3.3.5a original rechazará el parche."
            )
        if not messagebox.askyesno(
            "Confirmar creación e instalación",
            f"{self.patch_plan.message}\n\nDestino:\n{self.patch_plan.target}\n\n"
            f"Archivos ({len(files)}):\n{summary}{glue_notice}"
            "\n\nNo se sobrescribirá ningún MPQ.",
            parent=self.root,
        ):
            return
        try:
            digest, size = create_and_install_patch(files, self.patch_plan)
        except (OSError, PackagingError, MPQError) as exc:
            messagebox.showerror("No se pudo crear el parche", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "Parche creado y validado",
            f"{self.patch_plan.target}\n\nTamaño: {format_bytes(size)}\nSHA-256: {digest}",
            parent=self.root,
        )
        self.import_status.set(f"Creado y validado: {self.patch_plan.target.name}")
        self.refresh_archive_list()
        self.patch_plan = None
        self.plan_text.set("Selecciona de nuevo el destino para recalcular la prioridad.")
        self._update_actions()

    def _update_actions(self) -> None:
        self.extract_button.configure(
            state=tk.NORMAL if self.workspace is not None and self.export_queue else tk.DISABLED
        )
        self.import_button.configure(
            state=(
                tk.NORMAL
                if self.workspace is not None and self.patch_plan is not None and self.package_queue
                else tk.DISABLED
            )
        )

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)


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
