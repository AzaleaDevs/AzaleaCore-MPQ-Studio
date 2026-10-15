"""Interfaz gráfica de AzaleaCore MPQ Studio."""

from __future__ import annotations

import ctypes
import colorsys
import hashlib
import struct
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from . import __version__
from .blp import BLPConversionError, prepare_login_logo
from .button_preview import (
    fallback_button_texture,
    load_button_texture_from_client,
    tint_button_texture,
)
from .catalog import known_paths
from .dbc import DBCError, DBCFile, parse_dbc
from .i18n import normalize_language, translate_text
from .login_background import (
    ACCOUNT_LOGIN_PATH,
    ACCOUNT_LOGIN_XML_PATH,
    BACKUP_SUFFIX,
    LOGO_BACKUP_SUFFIX,
    MUSIC_BACKUP_SUFFIX,
    SOUND_CONFIG_BACKUP_SUFFIX,
    LOGIN_MODELS,
    LoginBackgroundError,
    apply_login_background,
    apply_login_customization,
    apply_custom_login_logo,
    apply_custom_login_music,
    apply_login_sound_volumes,
    custom_login_logo_is_active,
    custom_login_music_is_active,
    detect_login_background,
    detect_login_colors,
    detect_hidden_login_logos,
    detect_centered_wow_logo,
    find_global_logo_archive,
    find_login_archives,
    find_login_music_archive,
    read_login_sound_volumes,
    restore_login_background,
    restore_custom_login_logo,
    restore_custom_login_music,
    restore_login_sound_volumes,
    validate_login_music,
)
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
    plan_patch,
)
from .settings import (
    default_settings_path,
    load_language_setting,
    load_workspace_settings,
    save_language_setting,
    save_workspace_settings,
)
from .workspace import ExportRequest, Workspace, export_files, prepare_workspace


DEFAULT_DATA_DIR = Path(r"D:\World of Warcraft 3.3.5a\Data")
APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
APP_ICON_PATH = APP_ROOT / "assets" / "azaleacore-mpq-studio.ico"
APP_ICON_PNG_PATH = APP_ROOT / "assets" / "emotetails-youtube-logo.png"
WINDOWS_APP_USER_MODEL_ID = "AzaleaDevs.AzaleaCoreMPQStudio"
DBC_PAGE_SIZE = 250


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


def format_error_for_clipboard(title: str, message: str) -> str:
    """Forma un informe breve que se puede pegar en una incidencia o comentario."""
    return f"AzaleaCore MPQ Studio {__version__}\n{title}\n\n{message}"


class CopyableErrorDialog(tk.Toplevel):
    """Diálogo modal de problema con copia del informe al portapapeles."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        message: str,
        *,
        warning: bool = False,
        language: str = "es",
    ) -> None:
        super().__init__(parent)
        self.language = normalize_language(language)
        title = translate_text(title, self.language)
        message = translate_text(message, self.language)
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        self.minsize(520, 260)
        self.geometry("740x360")
        self.report = format_error_for_clipboard(title, message)
        self.copy_status = tk.StringVar(value="")

        body = ttk.Frame(self, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        heading = "Aviso de AzaleaCore MPQ Studio" if warning else "Error de AzaleaCore MPQ Studio"
        ttk.Label(body, text=heading, style="Title.TLabel").pack(anchor=tk.W, pady=(0, 8))

        details_frame = ttk.Frame(body)
        details_frame.pack(fill=tk.BOTH, expand=True)
        details = tk.Text(details_frame, wrap=tk.WORD, height=10, width=84)
        scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details.yview)
        details.configure(yscrollcommand=scrollbar.set)
        details.insert("1.0", message)
        details.configure(state=tk.DISABLED)
        details.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(body)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(footer, textvariable=self.copy_status, style="Muted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.copy_button = ttk.Button(
            footer,
            text=translate_text("Copiar al portapapeles", self.language),
            command=self.copy_report,
        )
        self.copy_button.pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(
            footer, text=translate_text("Cerrar", self.language), command=self.destroy
        ).pack(side=tk.RIGHT)
        for widget in (body, *body.winfo_children()):
            try:
                label = widget.cget("text")
            except tk.TclError:
                continue
            if label:
                widget.configure(text=translate_text(label, self.language))
        self.report = format_error_for_clipboard(title, message)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.focus_set()

    def copy_report(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self.report)
            self.update_idletasks()
        except tk.TclError:
            self.copy_status.set(
                translate_text("No se pudo acceder al portapapeles.", self.language)
            )
        else:
            self.copy_status.set(
                translate_text("Informe copiado; ya puedes pegarlo.", self.language)
            )


class LocalizedStringVar(tk.StringVar):
    """StringVar que traduce al actualizar un mensaje visible de la interfaz."""

    def __init__(self, master: tk.Misc, language_getter, value: str = "") -> None:
        self._language_getter = language_getter
        super().__init__(master=master)
        self.set(value)

    def set(self, value: str) -> None:
        super().set(translate_text(str(value), self._language_getter()))


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
        self.window_icon_photo: ImageTk.PhotoImage | None = None
        self._native_icon_handles: list[int] = []
        self._apply_window_icon()
        self.root.after(250, self._apply_window_icon)
        self.root.after(1000, self._apply_window_icon)
        self.root.geometry("1180x900")
        self.root.minsize(900, 560)

        self.settings_path = default_settings_path()
        self.language = load_language_setting(self.settings_path)
        self._localized_vars: list[LocalizedStringVar] = []
        self.remember_workspace = tk.BooleanVar(value=True)
        self.selected_path = tk.StringVar()
        self.search_text = tk.StringVar()
        self.listfile_text = self._localized_var("No cargado")
        self.include_listfile = tk.BooleanVar(value=False)
        self.workspace_text = tk.StringVar(value=self._tr("No seleccionada"))
        self.export_status = self._localized_var("Selecciona un archivo MPQ.")
        self.import_status = self._localized_var("Selecciona una carpeta de trabajo.")
        self.destination_text = tk.StringVar(value=self._tr("No seleccionado"))
        self.plan_text = self._localized_var("Selecciona el directorio de destino.")
        self.login_game_root = tk.StringVar(value=str(DEFAULT_DATA_DIR.parent))
        self.login_archive_text = tk.StringVar(value=self._tr("No detectado"))
        self.login_background = tk.StringVar(value="keep_current")
        self.hide_blizzard_logo = tk.BooleanVar(value=False)
        self.hide_rating_logo = tk.BooleanVar(value=False)
        self.center_wow_logo = tk.BooleanVar(value=False)
        self.use_custom_wow_logo = tk.BooleanVar(value=False)
        self.custom_wow_logo_text = tk.StringVar(value=self._tr("No seleccionado"))
        self.custom_wow_logo_source: Path | None = None
        self.use_custom_login_music = tk.BooleanVar(value=False)
        self.custom_login_music_text = tk.StringVar(value=self._tr("No seleccionado"))
        self.custom_login_music_source: Path | None = None
        self.music_volume = tk.DoubleVar(value=50.0)
        self.ambience_volume = tk.DoubleVar(value=50.0)
        self.music_volume_text = tk.StringVar(value="50 %")
        self.ambience_volume_text = tk.StringVar(value="50 %")
        self.use_custom_login_colors = tk.BooleanVar(value=False)
        self.button_color_r = tk.DoubleVar(value=255)
        self.button_color_g = tk.DoubleVar(value=255)
        self.button_color_b = tk.DoubleVar(value=255)
        self.button_color_saturation = tk.DoubleVar(value=100)
        self.button_color_brightness = tk.DoubleVar(value=100)
        self.text_color_r = tk.DoubleVar(value=255)
        self.text_color_g = tk.DoubleVar(value=199)
        self.text_color_b = tk.DoubleVar(value=0)
        self.text_color_saturation = tk.DoubleVar(value=100)
        self.text_color_brightness = tk.DoubleVar(value=100)
        self.color_value_texts: dict[str, tk.StringVar] = {}
        self.color_preview_caption = tk.StringVar()
        self.button_color_preview: tk.Label | None = None
        self.button_preview_texture = fallback_button_texture()
        self.button_preview_photo: ImageTk.PhotoImage | None = None
        self.login_status = self._localized_var(
            "Selecciona la carpeta del cliente y pulsa Detectar."
        )
        self.login_archive: Path | None = None
        self.login_logo_archive: Path | None = None
        self.login_logo_archive_text = tk.StringVar(value=self._tr("No detectado"))
        self.login_music_archive: Path | None = None
        self.login_music_archive_text = tk.StringVar(value=self._tr("MPQ de música no detectado"))
        self.property_name = tk.StringVar(value=self._tr("Sin selección"))
        self.property_type = self._localized_var("—")
        self.property_source = tk.StringVar(value="—")
        self.property_path = tk.StringVar(value="—")
        self.property_size = tk.StringVar(value="—")
        self.property_packed_size = tk.StringVar(value="—")
        self.property_flags = self._localized_var("—")
        self.property_sha256 = self._localized_var("—")
        self.dbc_archive_path = tk.StringVar()
        self.dbc_archive_status = self._localized_var("Selecciona un patch MPQ.")
        self.dbc_source_text = self._localized_var("Ningún DBC cargado.")
        self.dbc_summary_text = self._localized_var(
            "Escoge un patch y abre uno de sus archivos DBC."
        )
        self.dbc_page_text = tk.StringVar(value="—")
        self.dbc_document: DBCFile | None = None
        self.dbc_page = 0
        self.dbc_archive: Path | None = None
        self.dbc_internal_path: str | None = None
        self.dbc_file_items: dict[str, MPQFile] = {}

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
        self.context_menus: list[tk.Menu] = []

        self._configure_style()
        self._build_ui()
        self._apply_language()
        remember, last_workspace = load_workspace_settings(self.settings_path)
        self.remember_workspace.set(remember)
        if remember and last_workspace is not None:
            self._set_workspace(last_workspace, save_preference=False)
        self.refresh_archive_list()
        self._update_actions()
        if self.selected_path.get():
            self.root.after_idle(self.open_selected)

    def _apply_window_icon(self) -> None:
        """Aplica el icono tanto a Tk como a la ventana nativa de Windows."""
        try:
            if APP_ICON_PATH.is_file():
                self.root.iconbitmap(default=str(APP_ICON_PATH))
            if APP_ICON_PNG_PATH.is_file():
                with Image.open(APP_ICON_PNG_PATH) as source:
                    icon = source.convert("RGBA")
                    icon.thumbnail((256, 256), Image.Resampling.LANCZOS)
                    self.window_icon_photo = ImageTk.PhotoImage(icon)
                self.root.iconphoto(True, self.window_icon_photo)
        except (OSError, tk.TclError):
            pass

        if sys.platform != "win32" or not APP_ICON_PATH.is_file():
            return

        try:
            import ctypes

            user32 = ctypes.windll.user32
            find_window = user32.FindWindowW
            find_window.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
            find_window.restype = ctypes.c_void_p
            hwnd = find_window(None, self.root.title())
            if not hwnd:
                return

            # La barra de tareas consulta los iconos WM_ICON_SMALL y WM_ICON_BIG.
            # Si no existen, Windows muestra el icono genérico de pythonw/Tk.
            load_image = user32.LoadImageW
            load_image.argtypes = (
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            )
            load_image.restype = ctypes.c_void_p
            send_message = user32.SendMessageW
            send_message.argtypes = (
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_void_p,
            )
            send_message.restype = ctypes.c_void_p

            self._native_icon_handles = []
            for icon_type, size in ((0, 16), (1, 32)):
                handle = load_image(
                    None,
                    str(APP_ICON_PATH),
                    1,
                    size,
                    size,
                    0x0010,
                )
                if handle:
                    send_message(hwnd, 0x0080, icon_type, handle)
                    self._native_icon_handles.append(handle)
        except OSError:
            pass

    def _tr(self, text: str) -> str:
        return translate_text(text, self.language)

    def _localized_var(self, value: str = "") -> LocalizedStringVar:
        variable = LocalizedStringVar(self.root, lambda: self.language, value)
        self._localized_vars.append(variable)
        return variable

    def toggle_language(self) -> None:
        self.language = "en" if self.language == "es" else "es"
        self._apply_language()
        try:
            save_language_setting(self.settings_path, self.language)
        except OSError as exc:
            self._show_error("No se pudo guardar la preferencia", str(exc), warning=True)

    def _apply_language(self) -> None:
        def visit(parent: tk.Misc) -> None:
            for widget in parent.winfo_children():
                if isinstance(widget, ttk.Notebook):
                    for tab_id in widget.tabs():
                        current = widget.tab(tab_id, "text")
                        widget.tab(tab_id, text=self._tr(current))
                if isinstance(widget, ttk.Treeview):
                    for column in ("#0", *widget["columns"]):
                        heading = widget.heading(column, "text")
                        if heading:
                            widget.heading(column, text=self._tr(heading))
                    for item in widget.get_children(""):
                        self._translate_tree_values(widget, item)
                else:
                    try:
                        current = widget.cget("text")
                    except tk.TclError:
                        current = ""
                    if current:
                        try:
                            widget.configure(text=self._tr(current))
                        except tk.TclError:
                            pass
                visit(widget)

        visit(self.root)
        for menu in self.context_menus:
            end_index = menu.index("end")
            for index in range(int(end_index) + 1 if end_index is not None else 0):
                label = menu.entrycget(index, "label")
                if label:
                    menu.entryconfigure(index, label=self._tr(label))
        self.language_button.configure(
            text="English" if self.language == "es" else "Español"
        )
        for variable in self._localized_vars:
            variable.set(variable.get())
        if self.property_name.get() in {"Sin selección", "No selection"}:
            self.property_name.set(self._tr("Sin selección"))
        self._update_color_previews()
        self._render_dbc_page()

    def _translate_tree_values(self, tree: ttk.Treeview, item: str) -> None:
        values = tree.item(item, "values")
        if values:
            tree.item(item, values=tuple(self._tr(value) for value in values))
        for child in tree.get_children(item):
            self._translate_tree_values(tree, child)

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
        self.about_button = ttk.Button(
            header, text="Acerca de", command=self.show_about
        )
        self.about_button.pack(side=tk.RIGHT, padx=(0, 10))
        self.language_button = ttk.Button(
            header,
            text="English" if self.language == "es" else "Español",
            command=self.toggle_language,
        )
        self.language_button.pack(side=tk.RIGHT, padx=(0, 8))

        workspace_bar = ttk.LabelFrame(outer, text="Carpeta de trabajo", padding=8)
        workspace_bar.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(workspace_bar, textvariable=self.workspace_text).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            workspace_bar, text="Seleccionar...", command=self.choose_workspace
        ).pack(side=tk.RIGHT)
        self.remember_workspace_button = ttk.Checkbutton(
            workspace_bar,
            text="Recordar carpeta",
            variable=self.remember_workspace,
            command=self._remember_workspace_changed,
        )
        self.remember_workspace_button.pack(side=tk.RIGHT, padx=(0, 12))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook = notebook
        self.export_tab = ttk.Frame(notebook, padding=6)
        self.import_tab = ttk.Frame(notebook, padding=6)
        self.login_tab = ttk.Frame(notebook, padding=12)
        self.dbc_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.export_tab, text="EXPORTAR")
        notebook.add(self.import_tab, text="IMPORTAR")
        notebook.add(self.login_tab, text="FONDO LOGIN")
        notebook.add(self.dbc_tab, text="VISOR DBC")
        self._build_export_tab()
        self._build_import_tab()
        self._build_login_tab()
        self._build_dbc_tab()
        self._bind_shortcuts()
        self.root.after_idle(self.detect_login_archive)

    def _bind_shortcuts(self) -> None:
        """Atajos globales de la ventana; los menús de contexto complementan la UI."""
        self.root.bind_all("<Control-o>", self._shortcut_open_archive)
        self.root.bind_all("<Control-f>", self._focus_search)
        self.root.bind_all("<Control-e>", self._shortcut_extract)
        self.root.bind_all("<F5>", self._shortcut_refresh)
        self.root.bind_all("<Delete>", self._shortcut_remove_from_queue)

    def show_about(self) -> None:
        messagebox.showinfo(
            self._tr("Acerca de AzaleaCore MPQ Studio"),
            self._tr(
                f"AzaleaCore MPQ Studio\n"
                f"Versión {__version__}\n\n"
                "Herramienta de AzerothCore Labs para explorar, extraer y crear "
                "archivos MPQ de World of Warcraft 3.3.5a.\n\n"
                "Los MPQ de origen se abren en modo de solo lectura."
            ),
            parent=self.root,
        )

    def _show_error(self, title: str, message: str, *, warning: bool = False) -> None:
        CopyableErrorDialog(
            self.root, title, message, warning=warning, language=self.language
        )

    def _show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(self._tr(title), self._tr(message), parent=self.root)

    def _ask_yesno(self, title: str, message: str) -> bool:
        return messagebox.askyesno(
            self._tr(title), self._tr(message), parent=self.root
        )

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
        self.archive_tree.bind("<Return>", self._shortcut_queue_archive)
        self.archive_menu = tk.Menu(self.root, tearoff=False)
        self.archive_menu.add_command(
            label="Añadir selección a extracción", command=self.queue_selected
        )
        self.archive_menu.add_command(
            label="Calcular SHA-256", command=self._calculate_selected_sha256
        )
        self.archive_menu.add_command(
            label="Copiar ruta interna", command=self._copy_selected_internal_path
        )
        self._bind_context_menu(self.archive_tree, self.archive_menu)

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
        self.export_tree.bind("<Return>", self._shortcut_remove_export)
        self.export_menu = tk.Menu(self.root, tearoff=False)
        self.export_menu.add_command(
            label="Quitar selección de la pila", command=self.unqueue_selected
        )
        self.export_menu.add_command(
            label="Vaciar pila", command=self._clear_export_queue
        )
        self._bind_context_menu(self.export_tree, self.export_menu)

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
        self.package_tree.bind("<Return>", self._shortcut_queue_package)
        self.package_menu = tk.Menu(self.root, tearoff=False)
        self.package_menu.add_command(
            label="Añadir selección al MPQ", command=self.queue_package_selected
        )
        self.package_menu.add_command(
            label="Añadir todos los archivos", command=self.queue_package_all
        )
        self._bind_context_menu(self.package_tree, self.package_menu)

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
        self.package_queue_tree.bind("<Return>", self._shortcut_remove_package)
        self.package_queue_menu = tk.Menu(self.root, tearoff=False)
        self.package_queue_menu.add_command(
            label="Quitar selección de la cola", command=self.unqueue_package
        )
        self.package_queue_menu.add_command(
            label="Vaciar cola", command=self._clear_package_queue
        )
        self._bind_context_menu(self.package_queue_tree, self.package_queue_menu)

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
        self.include_listfile_check = ttk.Checkbutton(
            destination,
            text="Añadir (listfile)",
            variable=self.include_listfile,
        )
        self.include_listfile_check.pack(side=tk.RIGHT, padx=(0, 12))

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

    def _color_variables(
        self, prefix: str
    ) -> tuple[tk.DoubleVar, tk.DoubleVar, tk.DoubleVar, tk.DoubleVar, tk.DoubleVar]:
        return (
            getattr(self, f"{prefix}_color_r"),
            getattr(self, f"{prefix}_color_g"),
            getattr(self, f"{prefix}_color_b"),
            getattr(self, f"{prefix}_color_saturation"),
            getattr(self, f"{prefix}_color_brightness"),
        )

    def _effective_login_color(self, prefix: str) -> tuple[float, float, float]:
        red, green, blue, saturation, brightness = self._color_variables(prefix)
        rgb = tuple(
            min(1.0, max(0.0, channel.get() / 255.0))
            for channel in (red, green, blue)
        )
        hue, base_saturation, base_value = colorsys.rgb_to_hsv(*rgb)
        adjusted = colorsys.hsv_to_rgb(
            hue,
            min(1.0, base_saturation * saturation.get() / 100.0),
            min(1.0, base_value * brightness.get() / 100.0),
        )
        return tuple(float(channel) for channel in adjusted)

    @staticmethod
    def _color_hex(color: tuple[float, float, float]) -> str:
        channels = tuple(round(min(1.0, max(0.0, value)) * 255) for value in color)
        return "#{:02X}{:02X}{:02X}".format(*channels)

    def _update_color_previews(self, _value: str | None = None) -> None:
        button = self._effective_login_color("button")
        text = self._effective_login_color("text")
        button_hex = self._color_hex(button)
        text_hex = self._color_hex(text)
        self.color_preview_caption.set(
            f"{self._tr('Fondo')} {button_hex} · {self._tr('Texto')} {text_hex}"
        )
        for prefix, variables in (
            ("button", self._color_variables("button")),
            ("text", self._color_variables("text")),
        ):
            for name, variable in zip(
                ("r", "g", "b", "saturation", "brightness"), variables
            ):
                label = self.color_value_texts.get(f"{prefix}_{name}")
                if label is not None:
                    label.set(str(round(variable.get())))
        if self.button_color_preview is not None:
            rendered = tint_button_texture(self.button_preview_texture, button)
            rendered = rendered.resize((192, 48), Image.Resampling.LANCZOS)
            self.button_preview_photo = ImageTk.PhotoImage(rendered)
            self.button_color_preview.configure(
                text=self._tr("Iniciar sesión"),
                image=self.button_preview_photo,
                compound=tk.CENTER,
                background="#10141C",
                foreground=text_hex,
            )

    def _refresh_button_preview_texture(self) -> None:
        root = Path(self.login_game_root.get().strip() or ".")
        texture = load_button_texture_from_client(root)
        self.button_preview_texture = texture or fallback_button_texture()
        self._update_color_previews()

    def _set_color_controls(
        self, prefix: str, color: tuple[float, float, float]
    ) -> None:
        variables = self._color_variables(prefix)
        for variable, channel in zip(variables[:3], color):
            variable.set(round(channel * 255))
        variables[3].set(100)
        variables[4].set(100)

    def _build_color_control_grid(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Ajustes", padding=6)
        panel.grid(row=0, column=1, sticky=tk.NSEW)
        ttk.Label(panel, text="").grid(row=0, column=0)
        ttk.Label(panel, text="Fondo", anchor=tk.CENTER).grid(
            row=0, column=1, sticky=tk.EW, padx=(4, 7)
        )
        ttk.Label(panel, text="Texto", anchor=tk.CENTER).grid(
            row=0, column=2, sticky=tk.EW, padx=(7, 4)
        )
        rows = (
            ("R", "r", 0, 255),
            ("G", "g", 1, 255),
            ("B", "b", 2, 255),
            ("Saturación", "saturation", 3, 200),
            ("Brillo", "brightness", 4, 200),
        )
        for row, (label, key, variable_index, maximum) in enumerate(rows, start=1):
            ttk.Label(panel, text=label).grid(
                row=row, column=0, sticky=tk.W, padx=(0, 5), pady=1
            )
            for column, prefix in enumerate(("button", "text"), start=1):
                variable = self._color_variables(prefix)[variable_index]
                control = ttk.Frame(panel)
                control.grid(
                    row=row,
                    column=column,
                    sticky=tk.EW,
                    padx=(4, 7) if prefix == "button" else (7, 4),
                    pady=1,
                )
                ttk.Scale(
                    control,
                    from_=0,
                    to=maximum,
                    variable=variable,
                    command=self._update_color_previews,
                    length=84,
                ).pack(side=tk.LEFT)
                value_text = tk.StringVar(value=str(round(variable.get())))
                self.color_value_texts[f"{prefix}_{key}"] = value_text
                ttk.Label(control, textvariable=value_text, width=3, anchor=tk.E).pack(
                    side=tk.LEFT, padx=(4, 0)
                )
        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(2, weight=1)

    def _build_login_tab(self) -> None:
        canvas = tk.Canvas(self.login_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.login_tab, orient=tk.VERTICAL, command=canvas.yview
        )
        content = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        content_window = canvas.create_window((0, 0), window=content, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        intro = ttk.Frame(content)
        intro.pack(fill=tk.X, pady=(4, 14))
        ttk.Label(
            intro,
            text="Personalizar la pantalla de acceso",
            style="Title.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            intro,
            text=(
                "Configura el modelo M2, la música MP3, los volúmenes, los colores y los logotipos. "
                "Studio crea copias de seguridad antes del primer cambio."
            ),
            style="Muted.TLabel",
            wraplength=920,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(5, 0))

        client = ttk.LabelFrame(content, text="Cliente de WoW 3.3.5a", padding=10)
        client.pack(fill=tk.X, pady=(0, 10))
        ttk.Entry(client, textvariable=self.login_game_root).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(client, text="Examinar...", command=self.choose_login_game_root).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(client, text="Detectar", command=self.detect_login_archive).pack(
            side=tk.LEFT
        )

        detected = ttk.LabelFrame(content, text="MPQ efectivo del login", padding=10)
        detected.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(detected, textvariable=self.login_archive_text).pack(anchor=tk.W)
        ttk.Label(
            detected,
            text=f"Archivo interno: {ACCOUNT_LOGIN_PATH}",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(
            detected,
            textvariable=self.login_logo_archive_text,
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        selection = ttk.LabelFrame(content, text="Fondo animado", padding=10)
        selection.pack(fill=tk.X, pady=(0, 10))
        options = (
            (
                "Mantener el fondo actual",
                "keep_current",
                "No modifica ninguna llamada AccountLogin:SetModel",
            ),
            ("Classic", "classic", LOGIN_MODELS["classic"]),
            ("The Burning Crusade", "burning_crusade", LOGIN_MODELS["burning_crusade"]),
            ("Wrath of the Lich King", "northrend", LOGIN_MODELS["northrend"]),
        )
        for row, (label, value, model_path) in enumerate(options):
            ttk.Radiobutton(
                selection,
                text=label,
                value=value,
                variable=self.login_background,
            ).grid(row=row, column=0, sticky=tk.W, pady=3)
            ttk.Label(selection, text=model_path, style="Muted.TLabel").grid(
                row=row, column=1, sticky=tk.W, padx=(18, 0), pady=3
            )
        selection.columnconfigure(1, weight=1)

        audio = ttk.LabelFrame(content, text="Música y ambiente", padding=10)
        audio.pack(fill=tk.X, pady=(0, 10))
        music_file = ttk.Frame(audio)
        music_file.pack(fill=tk.X)
        ttk.Checkbutton(
            music_file,
            text="Usar música MP3 personalizada",
            variable=self.use_custom_login_music,
        ).pack(side=tk.LEFT)
        ttk.Button(
            music_file,
            text="Elegir MP3...",
            command=self.choose_custom_login_music,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            music_file,
            textvariable=self.custom_login_music_text,
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        ttk.Label(
            audio,
            textvariable=self.login_music_archive_text,
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(4, 5))

        volume_grid = ttk.Frame(audio)
        volume_grid.pack(fill=tk.X)
        ttk.Label(volume_grid, text="Música").grid(row=0, column=0, sticky=tk.W)
        ttk.Scale(
            volume_grid,
            from_=0,
            to=100,
            variable=self.music_volume,
            command=self._update_volume_labels,
        ).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Label(volume_grid, textvariable=self.music_volume_text, width=6).grid(
            row=0, column=2, sticky=tk.E
        )
        ttk.Label(volume_grid, text="Ambiente").grid(row=1, column=0, sticky=tk.W)
        ttk.Scale(
            volume_grid,
            from_=0,
            to=100,
            variable=self.ambience_volume,
            command=self._update_volume_labels,
        ).grid(row=1, column=1, sticky=tk.EW, padx=8)
        ttk.Label(volume_grid, textvariable=self.ambience_volume_text, width=6).grid(
            row=1, column=2, sticky=tk.E
        )
        volume_grid.columnconfigure(1, weight=1)

        colors = ttk.LabelFrame(
            content, text="Colores de los botones", padding=10
        )
        colors.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(
            colors,
            text="Usar colores personalizados",
            variable=self.use_custom_login_colors,
        ).pack(anchor=tk.W)
        ttk.Label(
            colors,
            text=(
                "RGB define el tono base; la vista previa multiplica el color "
                "sobre la textura real del cliente."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(2, 6))
        color_editors = ttk.Frame(colors)
        color_editors.pack(anchor=tk.W)
        preview_panel = ttk.LabelFrame(
            color_editors, text="Vista previa real", padding=8
        )
        preview_panel.grid(row=0, column=0, sticky=tk.NS, padx=(0, 8))
        self.button_color_preview = tk.Label(
            preview_panel,
            text="",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#3B4659",
            font=("Georgia", 11, "bold"),
        )
        self.button_color_preview.pack(padx=4, pady=(4, 2))
        ttk.Label(
            preview_panel,
            textvariable=self.color_preview_caption,
            style="Muted.TLabel",
        ).pack(pady=(0, 3))
        self._build_color_control_grid(color_editors)
        self._refresh_button_preview_texture()

        logos = ttk.LabelFrame(content, text="Elementos de marca", padding=10)
        logos.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(
            logos,
            text="Ocultar logo de Blizzard",
            variable=self.hide_blizzard_logo,
        ).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(
            logos,
            text="Ocultar clasificación PEGI",
            variable=self.hide_rating_logo,
        ).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(
            logos,
            text="Centrar logo de WoW sobre el acceso",
            variable=self.center_wow_logo,
        ).pack(anchor=tk.W, pady=2)
        custom_logo = ttk.Frame(logos)
        custom_logo.pack(fill=tk.X, pady=(2, 0))
        ttk.Checkbutton(
            custom_logo,
            text="Usar logo personalizado",
            variable=self.use_custom_wow_logo,
        ).pack(side=tk.LEFT)
        ttk.Button(
            custom_logo,
            text="Elegir PNG/BLP...",
            command=self.choose_custom_wow_logo,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            custom_logo,
            textvariable=self.custom_wow_logo_text,
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        ttk.Label(
            logos,
            text=(
                "Los objetos permanecen definidos para mantener la compatibilidad; "
                "Studio los vuelve transparentes."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(5, 0))

        actions = ttk.Frame(self.login_tab)
        actions.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(actions, textvariable=self.login_status, style="Muted.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.login_restore_button = ttk.Button(
            actions,
            text="Restaurar copia",
            command=self.restore_login_archive,
            state=tk.DISABLED,
        )
        self.login_restore_button.pack(side=tk.RIGHT, padx=(8, 0))
        self.login_apply_button = ttk.Button(
            actions,
            text="Aplicar personalización",
            command=self.apply_selected_login_background,
            state=tk.DISABLED,
        )
        self.login_apply_button.pack(side=tk.RIGHT)

    def _build_dbc_tab(self) -> None:
        archive_bar = ttk.LabelFrame(self.dbc_tab, text="Patch MPQ", padding=8)
        archive_bar.pack(fill=tk.X, pady=(0, 8))
        archive_controls = ttk.Frame(archive_bar)
        archive_controls.pack(fill=tk.X)
        ttk.Label(archive_controls, text="Archivo MPQ:").pack(side=tk.LEFT, padx=(0, 6))
        self.dbc_archive_combo = ttk.Combobox(
            archive_controls,
            textvariable=self.dbc_archive_path,
            state="normal",
            width=72,
        )
        self.dbc_archive_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.dbc_archive_combo.bind("<Return>", lambda _event: self.open_dbc_archive())
        ttk.Button(
            archive_controls, text="Examinar...", command=self.browse_dbc_archive
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            archive_controls, text="Abrir patch", command=self.open_dbc_archive
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            archive_controls,
            text="DBC suelto...",
            command=self.open_local_dbc,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            archive_bar, textvariable=self.dbc_archive_status, style="Muted.TLabel"
        ).pack(anchor=tk.W, fill=tk.X, pady=(6, 0))

        panes = ttk.Panedwindow(self.dbc_tab, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)
        dbc_files_panel = ttk.LabelFrame(panes, text="DBC del patch", padding=6)
        viewer = ttk.Frame(panes)
        panes.add(dbc_files_panel, weight=1)
        panes.add(viewer, weight=5)

        self.dbc_file_tree = self._make_tree(dbc_files_panel, ("size",))
        self.dbc_file_tree.heading("#0", text="Ruta interna")
        self.dbc_file_tree.heading("size", text="Tamaño")
        self.dbc_file_tree.column("#0", width=270, minwidth=180)
        self.dbc_file_tree.column("size", width=85, anchor=tk.E, stretch=False)
        self.dbc_file_tree.bind("<Double-1>", lambda _event: self.open_dbc_from_patch())
        ttk.Button(
            dbc_files_panel,
            text="Abrir DBC seleccionado",
            command=self.open_dbc_from_patch,
        ).pack(fill=tk.X, pady=(6, 0))

        summary = ttk.LabelFrame(viewer, text="Cabecera WDBC", padding=8)
        summary.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(summary, textvariable=self.dbc_source_text).pack(anchor=tk.W)
        ttk.Label(summary, textvariable=self.dbc_summary_text).pack(anchor=tk.W)
        ttk.Label(
            summary,
            text=(
                "Los campos se muestran como uint32; los offsets válidos del bloque "
                "de cadenas incluyen el texto. Haz doble clic en una celda para editarla."
            ),
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        table = ttk.LabelFrame(viewer, text="Registros", padding=6)
        table.pack(fill=tk.BOTH, expand=True)
        self.dbc_tree = ttk.Treeview(
            table,
            columns=(),
            show="headings",
            selectmode="browse",
            height=12,
        )
        dbc_y_scroll = ttk.Scrollbar(
            table, orient=tk.VERTICAL, command=self.dbc_tree.yview
        )
        dbc_x_scroll = ttk.Scrollbar(
            table, orient=tk.HORIZONTAL, command=self.dbc_tree.xview
        )
        self.dbc_tree.configure(
            yscrollcommand=dbc_y_scroll.set, xscrollcommand=dbc_x_scroll.set
        )
        self.dbc_tree.bind("<Double-1>", self._edit_dbc_cell)
        self.dbc_tree.grid(row=0, column=0, sticky=tk.NSEW)
        dbc_y_scroll.grid(row=0, column=1, sticky=tk.NS)
        dbc_x_scroll.grid(row=1, column=0, sticky=tk.EW)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        footer = ttk.Frame(viewer)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(footer, textvariable=self.dbc_page_text).pack(side=tk.LEFT)
        self.dbc_next_button = ttk.Button(
            footer, text="Siguiente", command=lambda: self._change_dbc_page(1)
        )
        self.dbc_next_button.pack(side=tk.RIGHT)
        self.dbc_previous_button = ttk.Button(
            footer, text="Anterior", command=lambda: self._change_dbc_page(-1)
        )
        self.dbc_previous_button.pack(side=tk.RIGHT, padx=(0, 8))
        self._render_dbc_page()

    def refresh_dbc_archive_list(self) -> None:
        if not hasattr(self, "dbc_archive_combo"):
            return
        values = [str(path) for path in discover_mpqs(DEFAULT_DATA_DIR)]
        current = self.dbc_archive_path.get().strip()
        if current and current not in values and Path(current).is_file():
            values.insert(0, current)
        self.dbc_archive_combo["values"] = values
        if not current and values:
            preferred = str(DEFAULT_DATA_DIR / "patch-9.MPQ")
            self.dbc_archive_path.set(preferred if preferred in values else values[0])

    def browse_dbc_archive(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title=self._tr("Seleccionar patch MPQ"),
            initialdir=str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()),
            filetypes=((self._tr("Archivos MPQ"), "*.MPQ *.mpq"), (self._tr("Todos"), "*.*")),
        )
        if filename:
            self.dbc_archive_path.set(filename)
            self.refresh_dbc_archive_list()
            self.open_dbc_archive()

    def open_dbc_archive(self) -> None:
        path = Path(self.dbc_archive_path.get().strip())
        self._clear_tree(self.dbc_file_tree)
        self.dbc_file_items.clear()
        self._clear_dbc_document()
        try:
            with MPQArchive(path) as archive:
                inventory = archive.inventory(known_paths())
        except (OSError, MPQError, struct.error) as exc:
            self.dbc_archive_status.set("No se pudo abrir el patch.")
            self._show_error("Error al abrir MPQ", str(exc))
            return
        dbc_files = tuple(
            item for item in inventory.files if item.path.casefold().endswith(".dbc")
        )
        self.dbc_archive = path
        for item in dbc_files:
            node = self.dbc_file_tree.insert(
                "", tk.END, text=item.path, values=(format_bytes(item.size),)
            )
            self.dbc_file_items[node] = item
        self.dbc_archive_status.set(
            f"{path.name} · {len(dbc_files)} DBC identificados · Solo lectura"
        )

    def open_dbc_from_patch(self) -> None:
        selection = self.dbc_file_tree.selection()
        item = self.dbc_file_items.get(selection[0]) if len(selection) == 1 else None
        if item is None:
            self._show_error(
                "Selecciona un archivo DBC",
                "Elige un DBC de la lista del patch y vuelve a intentarlo.",
                warning=True,
            )
            return
        if self.dbc_archive is None:
            return
        try:
            with MPQArchive(self.dbc_archive) as archive:
                payload = archive.read_file(item.path)
        except (OSError, MPQError, struct.error) as exc:
            self._show_error("No se pudo abrir el DBC", str(exc))
            return
        if payload is None:
            self._show_error("No se pudo abrir el DBC", f"Archivo no encontrado: {item.path}")
            return
        self._load_dbc(
            payload,
            f"{self.dbc_archive.name} · {item.path}",
            item.path,
        )

    def open_local_dbc(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title=self._tr("Seleccionar archivo DBC"),
            initialdir=str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()),
            filetypes=((self._tr("Archivos DBC"), "*.dbc *.DBC"), (self._tr("Todos"), "*.*")),
        )
        if not filename:
            return
        source = Path(filename)
        try:
            payload = source.read_bytes()
        except OSError as exc:
            self._show_error("No se pudo abrir el DBC", str(exc))
            return
        self._load_dbc(payload, str(source), f"DBFilesClient\\{source.name}")

    def _load_dbc(self, payload: bytes, source: str, internal_path: str) -> None:
        try:
            document = parse_dbc(payload)
        except (DBCError, struct.error) as exc:
            self._show_error("DBC no válido", str(exc))
            return
        self.dbc_document = document
        self.dbc_internal_path = internal_path
        self.dbc_page = 0
        self.dbc_source_text.set(source)
        header = document.header
        self.dbc_summary_text.set(
            f"{header.record_count} registros · {header.field_count} campos · "
            f"{header.record_size} bytes/registro · bloque de cadenas: "
            f"{header.string_block_size} bytes"
        )
        self._render_dbc_page()
        self.notebook.select(self.dbc_tab)

    def _clear_dbc_document(self) -> None:
        self.dbc_document = None
        self.dbc_internal_path = None
        self.dbc_page = 0
        self.dbc_source_text.set("Ningún DBC cargado.")
        self.dbc_summary_text.set("Escoge un patch y abre uno de sus archivos DBC.")
        self._render_dbc_page()

    def _edit_dbc_cell(self, event: tk.Event) -> None:
        document = self.dbc_document
        row = self.dbc_tree.identify_row(event.y)
        column_id = self.dbc_tree.identify_column(event.x)
        if document is None or not row or not column_id.startswith("#"):
            return
        field_index = int(column_id[1:]) - 2
        if field_index < 0 or field_index >= document.header.field_count:
            return
        record_index = int(self.dbc_tree.set(row, "record"))
        if self.workspace is None:
            self.choose_workspace()
            if self.workspace is None:
                return
        raw_value = document.record(record_index)[field_index]
        current_text = document.string_at(raw_value)
        initial = f"texto:{current_text}" if current_text is not None else str(raw_value)
        answer = simpledialog.askstring(
            self._tr("Editar campo DBC"),
            self._tr(
                "Escribe un uint32 decimal/hexadecimal o usa texto:contenido. "
                "El cambio se exportará automáticamente a empaquetar."
            ),
            initialvalue=initial,
            parent=self.root,
        )
        if answer is None:
            return
        try:
            if answer.casefold().startswith("texto:"):
                modified = document.replace_with_string(
                    record_index, field_index, answer[6:]
                )
            else:
                try:
                    value = int(answer.strip(), 0)
                except ValueError:
                    value = int(answer.strip(), 10)
                modified = document.replace_value(record_index, field_index, value)
        except (ValueError, UnicodeError) as exc:
            self._show_error("Valor DBC no válido", str(exc), warning=True)
            return
        if not self._export_modified_dbc(modified):
            return
        self.dbc_document = modified
        self._update_dbc_summary()
        self._render_dbc_page()

    def _export_modified_dbc(self, document: DBCFile) -> bool:
        if self.workspace is None or self.dbc_internal_path is None:
            return False
        internal_path = PureWindowsPath(self.dbc_internal_path)
        parts = internal_path.parts
        if (
            internal_path.is_absolute()
            or internal_path.drive
            or not parts
            or any(part in {"", ".", ".."} for part in parts)
        ):
            self._show_error("Ruta DBC no válida", self.dbc_internal_path)
            return False
        destination = self.workspace.package_dir.joinpath(*parts)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(document.to_bytes())
        except OSError as exc:
            self._show_error("No se pudo exportar el DBC", str(exc))
            return False
        self.dbc_archive_status.set(f"Cambio exportado: {destination}")
        self.refresh_package_tree()
        return True

    def _update_dbc_summary(self) -> None:
        if self.dbc_document is None:
            return
        header = self.dbc_document.header
        self.dbc_summary_text.set(
            f"{header.record_count} registros · {header.field_count} campos · "
            f"{header.record_size} bytes/registro · bloque de cadenas: "
            f"{header.string_block_size} bytes"
        )

    def _change_dbc_page(self, offset: int) -> None:
        if self.dbc_document is None:
            return
        last_page = max(
            0,
            (self.dbc_document.header.record_count - 1) // DBC_PAGE_SIZE,
        )
        self.dbc_page = min(last_page, max(0, self.dbc_page + offset))
        self._render_dbc_page()

    def _render_dbc_page(self) -> None:
        if not hasattr(self, "dbc_tree"):
            return
        self._clear_tree(self.dbc_tree)
        document = self.dbc_document
        if document is None:
            self.dbc_tree.configure(columns=())
            self.dbc_page_text.set(self._tr("Ningún DBC cargado."))
            self.dbc_previous_button.configure(state=tk.DISABLED)
            self.dbc_next_button.configure(state=tk.DISABLED)
            return

        columns = ("record",) + tuple(
            f"field_{index}" for index in range(document.header.field_count)
        )
        self.dbc_tree.configure(columns=columns)
        self.dbc_tree.heading("record", text="#")
        self.dbc_tree.column("record", width=72, minwidth=60, stretch=False, anchor=tk.E)
        for index in range(document.header.field_count):
            column = f"field_{index}"
            self.dbc_tree.heading(column, text=f"{self._tr('Campo')} {index}")
            self.dbc_tree.column(column, width=130, minwidth=80, stretch=False)

        start = self.dbc_page * DBC_PAGE_SIZE
        stop = min(start + DBC_PAGE_SIZE, document.header.record_count)
        for record_index in range(start, stop):
            values = document.record(record_index)
            self.dbc_tree.insert(
                "",
                tk.END,
                values=(
                    record_index,
                    *(document.display_value(value) for value in values),
                ),
            )
        page_count = max(
            1, (document.header.record_count + DBC_PAGE_SIZE - 1) // DBC_PAGE_SIZE
        )
        page_separator = "of" if self.language == "en" else "de"
        self.dbc_page_text.set(
            f"{self._tr('Página')} {self.dbc_page + 1} {page_separator} {page_count} · "
            f"{start}–{max(start, stop - 1)}"
        )
        self.dbc_previous_button.configure(
            state=tk.NORMAL if self.dbc_page > 0 else tk.DISABLED
        )
        self.dbc_next_button.configure(
            state=tk.NORMAL if self.dbc_page + 1 < page_count else tk.DISABLED
        )

    def choose_login_game_root(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title=self._tr("Seleccionar cliente de WoW 3.3.5a"),
            initialdir=self.login_game_root.get() or str(Path.cwd()),
        )
        if selected:
            self.login_game_root.set(selected)
            self.detect_login_archive()

    def _update_volume_labels(self, _value: str | None = None) -> None:
        self.music_volume_text.set(f"{round(self.music_volume.get())} %")
        self.ambience_volume_text.set(f"{round(self.ambience_volume.get())} %")

    def choose_custom_login_music(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title=self._tr("Seleccionar música del login"),
            filetypes=(("MP3", "*.mp3"), (self._tr("Todos los archivos"), "*.*")),
        )
        if selected:
            self.custom_login_music_source = Path(selected)
            self.custom_login_music_text.set(selected)
            self.use_custom_login_music.set(True)

    def choose_custom_wow_logo(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title=self._tr("Seleccionar logo personalizado"),
            filetypes=(
                (self._tr("Imágenes compatibles"), "*.png *.blp *.jpg *.jpeg *.webp *.tga *.bmp"),
                ("PNG", "*.png"),
                ("BLP", "*.blp"),
                (self._tr("Todos los archivos"), "*.*"),
            ),
        )
        if selected:
            self.custom_wow_logo_source = Path(selected)
            self.custom_wow_logo_text.set(selected)
            self.use_custom_wow_logo.set(True)

    def detect_login_archive(self) -> None:
        root = Path(self.login_game_root.get().strip() or ".")
        self._refresh_button_preview_texture()
        archives = find_login_archives(root)
        if not archives:
            self.login_archive = None
            self.login_logo_archive = None
            self.login_music_archive = None
            self.login_archive_text.set(self._tr("No detectado"))
            self.login_logo_archive_text.set(self._tr("MPQ gráfico no detectado"))
            self.login_music_archive_text.set(self._tr("MPQ de música no detectado"))
            self.login_status.set(
                "No se encontró un patch de locale 3 que contenga AccountLogin.lua."
            )
            self._update_login_actions()
            return

        preferred = next(
            (path for path in archives if path.parent.name.casefold() == "eses"),
            archives[0],
        )
        self.login_archive = preferred
        self.login_logo_archive = find_global_logo_archive(root)
        self.login_music_archive = find_login_music_archive(root)
        self.login_archive_text.set(str(preferred))
        self.login_logo_archive_text.set(
            f"MPQ gráfico: {self.login_logo_archive}"
            if self.login_logo_archive is not None
            else self._tr("MPQ gráfico no detectado")
        )
        self.login_music_archive_text.set(
            f"MPQ de música: {self.login_music_archive}"
            if self.login_music_archive is not None
            else self._tr("MPQ de música no detectado")
        )
        try:
            with MPQArchive(preferred) as archive:
                payload = archive.read_file(ACCOUNT_LOGIN_PATH)
                xml_payload = archive.read_file(ACCOUNT_LOGIN_XML_PATH)
            detected = detect_login_background(payload) if payload is not None else None
            login_colors = detect_login_colors(payload) if payload is not None else None
            hidden_logos = (
                detect_hidden_login_logos(xml_payload)
                if xml_payload is not None
                else (False, False)
            )
            centered_wow_logo = (
                detect_centered_wow_logo(xml_payload)
                if xml_payload is not None
                else False
            )
            custom_wow_logo = bool(
                self.login_logo_archive is not None
                and custom_login_logo_is_active(self.login_logo_archive)
            )
            custom_login_music = bool(
                self.login_music_archive is not None
                and custom_login_music_is_active(self.login_music_archive)
            )
            music_volume, ambience_volume = read_login_sound_volumes(root)
        except (OSError, MPQError, LoginBackgroundError) as exc:
            self.login_status.set(f"No se pudo inspeccionar el fondo actual: {exc}")
        else:
            labels = {
                "classic": "Classic",
                "burning_crusade": "The Burning Crusade",
                "northrend": "Wrath of the Lich King",
            }
            if detected:
                self.login_background.set("keep_current")
                self.login_status.set(
                    f"Fondo actual detectado: {labels[detected]}. "
                    "Se mantendrá salvo que elijas otro explícitamente."
                )
            else:
                self.login_background.set("keep_current")
                self.login_status.set(
                    "Fondo personalizado detectado; se mantendrá sin cambios."
                )
            self.hide_blizzard_logo.set(hidden_logos[0])
            self.hide_rating_logo.set(hidden_logos[1])
            self.center_wow_logo.set(centered_wow_logo)
            self.use_custom_wow_logo.set(custom_wow_logo)
            self.custom_wow_logo_source = None
            self.custom_wow_logo_text.set(
                self._tr("Instalado dentro del MPQ")
                if custom_wow_logo
                else self._tr("No seleccionado")
            )
            self.use_custom_login_music.set(custom_login_music)
            self.custom_login_music_source = None
            self.custom_login_music_text.set(
                self._tr("Instalada dentro del MPQ")
                if custom_login_music
                else self._tr("No seleccionado")
            )
            self.music_volume.set(round(music_volume * 100))
            self.ambience_volume.set(round(ambience_volume * 100))
            self._update_volume_labels()
            if login_colors is not None:
                self.use_custom_login_colors.set(True)
                self._set_color_controls("button", login_colors[0])
                self._set_color_controls("text", login_colors[1])
            else:
                self.use_custom_login_colors.set(False)
                self._set_color_controls("button", (1.0, 1.0, 1.0))
                self._set_color_controls("text", (1.0, 199 / 255, 0.0))
            self._update_color_previews()
        self._update_login_actions()

    def apply_selected_login_background(self) -> None:
        if self.login_archive is None:
            return
        root = Path(self.login_game_root.get().strip() or ".")
        label = {
            "keep_current": "actual (sin cambiar el M2)",
            "classic": "Classic",
            "burning_crusade": "The Burning Crusade",
            "northrend": "Wrath of the Lich King",
        }[self.login_background.get()]
        selected_background = (
            None
            if self.login_background.get() == "keep_current"
            else self.login_background.get()
        )
        backup = self.login_archive.with_name(self.login_archive.name + BACKUP_SUFFIX)
        logo_changes = []
        if self.hide_blizzard_logo.get():
            logo_changes.append("ocultar logo de Blizzard")
        if self.hide_rating_logo.get():
            logo_changes.append("ocultar clasificación PEGI")
        if self.center_wow_logo.get():
            logo_changes.append("centrar logo de WoW")
        if self.use_custom_wow_logo.get():
            logo_changes.append("usar logo personalizado")
        logo_summary = ", ".join(logo_changes) if logo_changes else "mostrar ambos logotipos"

        custom_logo_payload = None
        if self.use_custom_wow_logo.get() and self.custom_wow_logo_source is not None:
            try:
                custom_logo_payload = prepare_login_logo(self.custom_wow_logo_source)
            except (OSError, BLPConversionError) as exc:
                self._show_error("No se pudo preparar el logo", str(exc))
                return
        if (
            self.use_custom_wow_logo.get()
            and custom_logo_payload is None
            and not (
                self.login_logo_archive is not None
                and custom_login_logo_is_active(self.login_logo_archive)
            )
        ):
            self._show_error(
                "No se pudo preparar el logo",
                "Elige primero un archivo PNG o BLP para el logo personalizado.",
            )
            return

        custom_music_payload = None
        if (
            self.use_custom_login_music.get()
            and self.custom_login_music_source is not None
        ):
            try:
                custom_music_payload = self.custom_login_music_source.read_bytes()
                validate_login_music(custom_music_payload)
            except (OSError, LoginBackgroundError) as exc:
                self._show_error("No se pudo preparar la música", str(exc))
                return
        current_custom_music = bool(
            self.login_music_archive is not None
            and custom_login_music_is_active(self.login_music_archive)
        )
        if (
            self.use_custom_login_music.get()
            and custom_music_payload is None
            and not current_custom_music
        ):
            self._show_error(
                "No se pudo preparar la música",
                "Elige primero un archivo MP3 para la música del login.",
            )
            return
        if self.use_custom_login_music.get() and self.login_music_archive is None:
            self._show_error(
                "No se pudo preparar la música",
                "No se encontró un MPQ global donde instalar la pista.",
            )
            return

        logo_backup = (
            self.login_logo_archive.with_name(
                self.login_logo_archive.name + LOGO_BACKUP_SUFFIX
            )
            if self.login_logo_archive is not None
            else None
        )
        music_backup = (
            self.login_music_archive.with_name(
                self.login_music_archive.name + MUSIC_BACKUP_SUFFIX
            )
            if self.login_music_archive is not None
            else None
        )
        music_summary = (
            self.custom_login_music_source.name
            if self.custom_login_music_source is not None
            else (
                "mantener la música personalizada instalada"
                if self.use_custom_login_music.get()
                else "música original/no modificada"
            )
        )
        music_percent = round(self.music_volume.get())
        ambience_percent = round(self.ambience_volume.get())
        button_color = (
            self._effective_login_color("button")
            if self.use_custom_login_colors.get()
            else None
        )
        text_color = (
            self._effective_login_color("text")
            if self.use_custom_login_colors.get()
            else None
        )
        color_summary = (
            f"botón {self._color_hex(button_color)}, "
            f"texto {self._color_hex(text_color)}"
            if button_color is not None and text_color is not None
            else "colores originales"
        )
        if not self._ask_yesno(
            "Confirmar personalización del login",
            f"Se aplicará el fondo {label} en:\n{self.login_archive}\n\n"
            f"Elementos de marca: {logo_summary}.\n\n"
            f"Música: {music_summary}.\n"
            f"Volumen de música: {music_percent} %.\n"
            f"Volumen de ambiente: {ambience_percent} %.\n"
            f"Colores: {color_summary}.\n\n"
            f"Copia del fondo: {backup}\n"
            f"MPQ gráfico: {self.login_logo_archive or 'no detectado'}\n"
            f"Copia gráfica: {logo_backup or 'no disponible'}\n"
            f"MPQ de música: {self.login_music_archive or 'no detectado'}\n"
            f"Copia de música: {music_backup or 'no disponible'}\n\n"
            "Wow.exe debe estar cerrado.",
        ):
            return

        try:
            result = apply_login_customization(
                self.login_archive,
                selected_background,
                hide_blizzard_logo=self.hide_blizzard_logo.get(),
                hide_rating_logo=self.hide_rating_logo.get(),
                center_wow_logo=self.center_wow_logo.get(),
                button_color=button_color,
                text_color=text_color,
            )
            if self.use_custom_wow_logo.get():
                if self.login_logo_archive is None:
                    raise LoginBackgroundError(
                        "No se encontró Data\\patch-9.MPQ para instalar la textura."
                    )
                if custom_logo_payload is not None:
                    apply_custom_login_logo(
                        self.login_logo_archive, custom_logo_payload
                    )
            elif (
                self.login_logo_archive is not None
                and custom_login_logo_is_active(self.login_logo_archive)
            ):
                restore_custom_login_logo(self.login_logo_archive)

            if self.use_custom_login_music.get():
                if custom_music_payload is not None:
                    apply_custom_login_music(
                        self.login_music_archive, custom_music_payload
                    )
            elif current_custom_music and self.login_music_archive is not None:
                restore_custom_login_music(self.login_music_archive)

            apply_login_sound_volumes(
                root,
                self.music_volume.get() / 100.0,
                self.ambience_volume.get() / 100.0,
            )
        except (OSError, MPQError, LoginBackgroundError) as exc:
            self._show_error("No se pudo personalizar el login", str(exc))
            return

        self.login_status.set(f"Personalización aplicada: {label}.")
        self._show_info(
            "Login actualizado",
            f"Modelo M2:\n{result.model_path}\n\n"
            f"Logo de Blizzard oculto: {'sí' if result.hide_blizzard_logo else 'no'}\n"
            f"Clasificación PEGI oculta: {'sí' if result.hide_rating_logo else 'no'}\n"
            f"Logo de WoW centrado: {'sí' if result.center_wow_logo else 'no'}\n"
            f"Logo personalizado: {'sí' if self.use_custom_wow_logo.get() else 'no'}\n"
            f"Música personalizada: {'sí' if self.use_custom_login_music.get() else 'no'}\n"
            f"Volúmenes: música {music_percent} %, ambiente {ambience_percent} %\n"
            f"Colores: {color_summary}\n\n"
            f"Copia de seguridad:\n{result.backup}",
        )
        self._update_login_actions()

    def restore_login_archive(self) -> None:
        if self.login_archive is None:
            return
        root = Path(self.login_game_root.get().strip() or ".")
        if not self._ask_yesno(
            "Restaurar personalización anterior",
            f"Se restaurarán las copias de seguridad disponibles sobre:\n"
            f"{self.login_archive}\n\n"
            "Wow.exe debe estar cerrado.",
        ):
            return
        try:
            restored_items = []
            if self.login_archive.with_name(
                self.login_archive.name + BACKUP_SUFFIX
            ).is_file():
                restored_items.append(
                    f"Fondo: {restore_login_background(self.login_archive)}"
                )
            if (
                self.login_logo_archive is not None
                and self.login_logo_archive.with_name(
                    self.login_logo_archive.name + LOGO_BACKUP_SUFFIX
                ).is_file()
            ):
                restored_items.append(
                    f"Logo: {restore_custom_login_logo(self.login_logo_archive)}"
                )
            if (
                self.login_music_archive is not None
                and self.login_music_archive.with_name(
                    self.login_music_archive.name + MUSIC_BACKUP_SUFFIX
                ).is_file()
            ):
                restored_items.append(
                    f"Música: {restore_custom_login_music(self.login_music_archive)}"
                )
            config = root / "WTF" / "Config.wtf"
            if config.with_name(
                config.name + SOUND_CONFIG_BACKUP_SUFFIX
            ).is_file():
                restored_items.append(
                    f"Volúmenes: {restore_login_sound_volumes(root)}"
                )
        except (OSError, MPQError, LoginBackgroundError) as exc:
            self._show_error("No se pudo restaurar el login", str(exc))
            return
        self.login_status.set("Copias de seguridad restauradas.")
        restored = (
            "\n\n".join(restored_items)
            if restored_items
            else "No había ninguna copia pendiente."
        )
        self._show_info("Login restaurado", restored)
        self.detect_login_archive()

    def _update_login_actions(self) -> None:
        available = self.login_archive is not None and self.login_archive.is_file()
        self.login_apply_button.configure(state=tk.NORMAL if available else tk.DISABLED)
        background_backup = bool(
            available
            and self.login_archive is not None
            and self.login_archive.with_name(
                self.login_archive.name + BACKUP_SUFFIX
            ).is_file()
        )
        logo_backup = bool(
            self.login_logo_archive is not None
            and self.login_logo_archive.with_name(
                self.login_logo_archive.name + LOGO_BACKUP_SUFFIX
            ).is_file()
        )
        music_backup = bool(
            self.login_music_archive is not None
            and self.login_music_archive.with_name(
                self.login_music_archive.name + MUSIC_BACKUP_SUFFIX
            ).is_file()
        )
        root = Path(self.login_game_root.get().strip() or ".")
        config = root / "WTF" / "Config.wtf"
        audio_backup = config.with_name(
            config.name + SOUND_CONFIG_BACKUP_SUFFIX
        ).is_file()
        self.login_restore_button.configure(
            state=(
                tk.NORMAL
                if background_backup or logo_backup or music_backup or audio_backup
                else tk.DISABLED
            )
        )

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
        selected = filedialog.askdirectory(
            parent=self.root, title=self._tr("Carpeta de trabajo")
        )
        if not selected:
            return
        self._set_workspace(selected)

    def _set_workspace(self, selected: Path | str, *, save_preference: bool = True) -> None:
        try:
            self.workspace = prepare_workspace(selected)
        except OSError as exc:
            self._show_error("No se pudo preparar la carpeta", str(exc))
            return
        self.workspace_text.set(str(self.workspace.root))
        self.package_dir_label.configure(text=str(self.workspace.package_dir))
        self.import_status.set("Carpetas exportar y empaquetar preparadas.")
        self.refresh_package_tree()
        self._update_actions()
        if save_preference:
            self._save_workspace_preference()

    def _remember_workspace_changed(self) -> None:
        self._save_workspace_preference()

    def _save_workspace_preference(self) -> None:
        try:
            save_workspace_settings(
                self.settings_path,
                remember=self.remember_workspace.get(),
                workspace=(
                    self.workspace.root
                    if self.remember_workspace.get() and self.workspace is not None
                    else None
                ),
            )
        except OSError as exc:
            self._show_error(
                "No se pudo guardar la preferencia",
                f"Studio mantiene la carpeta seleccionada durante esta sesión, "
                f"pero no pudo recordarla:\n{exc}",
                warning=True,
            )

    def refresh_archive_list(self) -> None:
        values = [str(path) for path in discover_mpqs(DEFAULT_DATA_DIR)]
        current = self.selected_path.get()
        if current and current not in values and Path(current).is_file():
            values.insert(0, current)
        self.combo["values"] = values
        if not current and values:
            preferred = str(DEFAULT_DATA_DIR / "patch-9.MPQ")
            self.selected_path.set(preferred if preferred in values else values[0])
        self.refresh_dbc_archive_list()

    def browse_archive(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title=self._tr("Seleccionar archivo MPQ"),
            initialdir=str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.is_dir() else Path.cwd()),
            filetypes=(
                (self._tr("Archivos MPQ"), "*.MPQ *.mpq"),
                (self._tr("Todos"), "*.*"),
            ),
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
            title=self._tr("Seleccionar listfile externo"),
            filetypes=(
                (self._tr("Listfile o texto"), "(listfile) *.txt *.lst"),
                (self._tr("Todos los archivos"), "*.*"),
            ),
        )
        if not filename:
            return
        try:
            paths = load_listfile_paths(filename)
        except (OSError, UnicodeError) as exc:
            self._show_error("No se pudo leer el listfile", str(exc))
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
            self._show_error("Error al abrir MPQ", str(exc))
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

    def _shortcut_open_archive(self, _event: tk.Event) -> str:
        self.browse_archive()
        return "break"

    def _shortcut_extract(self, _event: tk.Event) -> str:
        self.extract_queue()
        return "break"

    def _shortcut_refresh(self, _event: tk.Event) -> str:
        if self.notebook.select() == str(self.import_tab):
            self.refresh_package_tree()
        else:
            self.refresh_archive_list()
            if self.selected_path.get():
                self.open_selected()
        return "break"

    def _shortcut_remove_from_queue(self, _event: tk.Event) -> str | None:
        focused = self.root.focus_get()
        if focused == self.export_tree:
            self.unqueue_selected()
            return "break"
        if focused == self.package_queue_tree:
            self.unqueue_package()
            return "break"
        return None

    def _shortcut_queue_archive(self, _event: tk.Event) -> str:
        self.queue_selected()
        return "break"

    def _shortcut_remove_export(self, _event: tk.Event) -> str:
        self.unqueue_selected()
        return "break"

    def _shortcut_queue_package(self, _event: tk.Event) -> str:
        self.queue_package_selected()
        return "break"

    def _shortcut_remove_package(self, _event: tk.Event) -> str:
        self.unqueue_package()
        return "break"

    def _bind_context_menu(self, tree: ttk.Treeview, menu: tk.Menu) -> None:
        self.context_menus.append(menu)

        def show_menu(event: tk.Event) -> str:
            row = tree.identify_row(event.y)
            if row:
                if row not in tree.selection():
                    tree.selection_set(row)
                tree.focus(row)
            else:
                return "break"
            if menu is self.archive_menu:
                is_file = row in self.archive_items
                menu.entryconfigure(1, state=tk.NORMAL if is_file else tk.DISABLED)
                menu.entryconfigure(2, state=tk.NORMAL if is_file else tk.DISABLED)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        tree.bind("<Button-3>", show_menu)

    def _copy_selected_internal_path(self) -> None:
        selection = self.archive_tree.selection()
        if len(selection) != 1:
            return
        file = self.archive_items.get(selection[0])
        if file is None:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(file.path)
            self.export_status.set("Ruta interna copiada al portapapeles.")
        except tk.TclError:
            self._show_error("No se pudo copiar la ruta", "Windows no permitió acceder al portapapeles.")

    def _clear_export_queue(self) -> None:
        self.export_queue.clear()
        self._refresh_export_queue()

    def _clear_package_queue(self) -> None:
        self.package_queue.clear()
        self._refresh_package_queue()

    def _populate_archive_tree(self, files: tuple[MPQFile, ...]) -> None:
        folders: dict[tuple[str, ...], str] = {}
        for item in files:
            parts = tuple(part for part in item.path.replace("/", "\\").split("\\") if part)
            parent = ""
            for depth, part in enumerate(parts[:-1], start=1):
                key = parts[:depth]
                if key not in folders:
                    folders[key] = self.archive_tree.insert(
                        parent, tk.END, text=part, values=(self._tr("Carpeta"), ""), open=False
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

    def _archive_descendant_files(self, node: str) -> list[str]:
        descendants: list[str] = []
        for child in self.archive_tree.get_children(node):
            if child in self.archive_items:
                descendants.append(child)
            descendants.extend(self._archive_descendant_files(child))
        return descendants

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
            self._show_error("Error al calcular SHA-256", str(exc))
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
        nodes = list(self.archive_tree.selection())
        for node in tuple(nodes):
            nodes.extend(self._archive_descendant_files(node))
        for node in nodes:
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
            overwrite = self._ask_yesno(
                "Archivos existentes",
                f"Ya existen {len(collisions)} archivo(s). ¿Quieres sobrescribirlos?",
            )
            if not overwrite:
                return
        try:
            results = export_files(requests, self.workspace, overwrite=overwrite)
        except (OSError, MPQError, ValueError) as exc:
            self._show_error("Error de extracción", str(exc))
            return
        self._show_info(
            "Extracción completada",
            f"Se extrajeron {len(results)} archivo(s) en:\n{self.workspace.export_dir}",
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
                    parent_node,
                    tk.END,
                    text=path.name,
                    values=(self._tr("Carpeta"), ""),
                    open=False,
                )
                folders[path] = node
            elif path.is_file():
                node = self.package_tree.insert(
                    parent_node,
                    tk.END,
                    text=path.name,
                    values=(
                        path.suffix.upper().lstrip(".") or self._tr("Archivo"),
                        format_bytes(path.stat().st_size),
                    ),
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
        if self.workspace is not None:
            for path in sorted(self.package_queue.values(), key=lambda item: str(item).casefold()):
                internal = path.relative_to(self.workspace.package_dir).as_posix().replace("/", "\\")
                self.package_queue_tree.insert(
                    "", tk.END, text=internal, values=(format_bytes(path.stat().st_size),)
                )
        self._update_actions()

    def choose_destination(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title=self._tr("Directorio donde se instalará el parche"),
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
        listfile_notice = (
            "\n\nSe añadirá un `(listfile)` con las rutas internas del paquete."
            if self.include_listfile.get()
            else "\n\nEl paquete se mantendrá mínimo, sin `(listfile)`."
        )
        if not self._ask_yesno(
            "Confirmar creación e instalación",
            f"{self.patch_plan.message}\n\nDestino:\n{self.patch_plan.target}\n\n"
            f"Archivos ({len(files)}):\n{summary}"
            f"{listfile_notice}"
            "\n\nNo se sobrescribirá ningún MPQ.",
        ):
            return
        try:
            digest, size = create_and_install_patch(
                files,
                self.patch_plan,
                include_listfile=self.include_listfile.get(),
            )
        except (OSError, PackagingError, MPQError) as exc:
            self._show_error("No se pudo crear el parche", str(exc))
            return
        self._show_info(
            "Parche creado y validado",
            f"{self.patch_plan.target}\n\nTamaño: {format_bytes(size)}\nSHA-256: {digest}",
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
    _set_windows_app_user_model_id()
    root = tk.Tk()
    MPQStudioApp(root)
    root.mainloop()


def _set_windows_app_user_model_id() -> bool:
    """Evita que la barra de tareas agrupe la ventana bajo el icono de Python."""
    if sys.platform != "win32":
        return False
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        set_app_id = shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        return set_app_id(WINDOWS_APP_USER_MODEL_ID) == 0
    except (AttributeError, OSError):
        return False
