# AzaleaCore MPQ Studio

Aplicación de escritorio para investigar, extraer, validar y crear archivos MPQ de forma segura, con atención inicial a World of Warcraft 3.3.5a (build 12340).

## Estado

La versión 0.20 incluye un lector MPQ de solo lectura, búsqueda instantánea,
exportación múltiple con
rutas conservadas y creación validada de parches mínimos. La interfaz puede
cambiar entre español e inglés con el botón del encabezado y recuerda la
preferencia. Los flujos genéricos de exportación e importación no editan los
MPQ de origen; la operación especializada **FONDO LOGIN** sí reemplaza dos MPQ
de forma controlada, siempre después de crear copias de seguridad restaurables.

El botón **Acerca de** muestra la versión y el objetivo de la herramienta.

La pestaña **FONDO LOGIN** detecta el `patch-<locale>-3.MPQ` efectivo y permite
cambiar la pantalla animada entre los modelos nativos de Classic, The Burning
Crusade y Wrath of the Lich King. Antes del primer cambio crea una copia
`.before-login-background`; el botón **Restaurar copia** permite volver al
estado anterior. El reemplazo conserva las demás entradas del MPQ, incluidas
las que no tengan un nombre recuperable en el `(listfile)`. `Wow.exe` debe estar
cerrado durante la aplicación o restauración.

En la misma pestaña se pueden ocultar por separado el logo de Blizzard y la
clasificación PEGI. Studio no elimina sus objetos XML: les aplica transparencia
total para conservar las referencias internas que espera el cliente. El cambio
del M2, Blizzard y PEGI se valida y se instala como una sola operación atómica.
La opción **Centrar logo de WoW sobre el acceso** mueve `AccountLoginLogo` desde
la esquina superior izquierda hasta el centro, encima del formulario. Conserva
la textura original y solamente cambia su anclaje XML.

La opción **Usar logo personalizado** acepta PNG, JPG, WebP, TGA, BMP o BLP.
Las imágenes comunes se encajan sin deformación en un lienzo transparente de
512×256 y se convierten a BLP2 DXT5 con mipmaps. La posición se configura en
`patch-esES-3.MPQ`, mientras que la textura se instala en `Data\patch-9.MPQ`
sobre la ruta global que el cliente 3.3.5a carga realmente. Studio conserva una
copia `.before-login-logo` independiente y **Restaurar copia** recupera ambos
MPQ.

El icono de la ventana y la barra de tareas utiliza el logo de YouTube proporcionado para el proyecto.
El recurso multirresolución y el PNG original están en `assets/`.

Los errores y avisos usan un cuadro que permite copiar versión, título y detalle
al portapapeles para pegarlos en un comentario o incidencia.

La casilla **Recordar carpeta** restaura la última carpeta de trabajo al iniciar.
La preferencia se guarda en `%APPDATA%\AzaleaCore MPQ Studio\settings.json` y se
puede desactivar en cualquier momento.

## Flujo gráfico

1. Seleccionar una carpeta de trabajo. Studio crea `exportar` y `empaquetar`.
2. En **EXPORTAR**, abrir un MPQ y enviar archivos a la pila con doble clic o `>>`.
3. Extraer la pila en `exportar`, conservando cada ruta interna.
4. Copiar a `empaquetar` únicamente los archivos que formarán el nuevo parche.
5. En **IMPORTAR**, seleccionar archivos concretos o usar `Todo >>`.
6. Elegir el directorio de instalación y revisar el nombre propuesto.
7. Confirmar la creación. Studio reabre el MPQ y compara todos sus bytes antes
   de instalarlo.

En IMPORTAR, **Añadir (listfile)** agrega de forma opcional un índice con las
rutas internas al MPQ nuevo. La casilla está desactivada por defecto; sin ella,
se conserva el modo de parche mínimo.

En la pestaña EXPORTAR, el campo **Buscar** filtra instantáneamente por cualquier
fragmento de la ruta interna. `Ctrl+F` lleva el foco al buscador.

Los árboles de archivos tienen menú contextual (botón derecho) para añadir
archivos o carpetas a las colas, quitar elementos, copiar la ruta interna y
vaciar una cola. Atajos: `Ctrl+O` abre un MPQ, `Ctrl+F` enfoca el buscador,
`Ctrl+E` extrae la cola, `F5` actualiza la pestaña activa y `Supr` quita la
selección cuando el foco está en una cola. `Enter` añade o quita elementos según
el árbol activo.

En **EXPORTAR**, se puede cargar un listfile externo de texto. Studio combina
esas rutas con las rutas conocidas y con el `(listfile)` interno del MPQ; cada
ruta externa se contrasta con las tablas del archivo antes de mostrarla. El
botón **Quitar** descarga la lista para la sesión actual.

Al seleccionar un único archivo o carpeta, el panel inferior muestra sus
propiedades. Para los archivos incluye la ruta interna, los tamaños real y
almacenado, los flags MPQ y un botón que calcula el SHA-256 bajo demanda sin
escribir en el archivo original.

El programa nunca sobrescribe un parche. Propone los sufijos en orden
`1`–`9`, `A`–`Z`; por ejemplo, tras `patch-9.MPQ` propone `patch-A.MPQ`, y tras
`patch-A.MPQ` propone `patch-B.MPQ`. El formato `patch-10.MPQ` no se genera.
Las pruebas disponibles confirman que el cliente de laboratorio carga el sufijo
`A`; el siguiente sufijo alfabético debe verificarse en cada instalación.

Studio permite empaquetar rutas `Interface\GlueXML` sin una alerta emergente.
Eso no garantiza que cada archivo GlueXML funcione con todos los ejecutables o
clientes: prueba los cambios en una copia del cliente y conserva una copia de
seguridad. La edición de cadenas Lua y la sustitución de XML pueden tener
resultados distintos.

## Principios

- Los archivos originales se abren en modo de solo lectura.
- La aplicación nunca sobrescribe un MPQ del cliente por defecto.
- Todo MPQ generado se vuelve a abrir y validar.
- Las operaciones importantes producen un registro y un manifiesto reproducible.
- La interfaz y la documentación están disponibles en español e inglés.

## Tutorial de uso (Español)

### Cambiar el fondo animado del login

1. Cierra `Wow.exe`.
2. Abre **FONDO LOGIN** y selecciona la carpeta raíz del cliente.
3. Pulsa **Detectar** y comprueba que Studio encuentre el MPQ localizado que
   contiene `Interface\GlueXML\AccountLogin.lua`.
4. Elige Classic, The Burning Crusade o Wrath of the Lich King.
5. Marca **Ocultar logo de Blizzard** y/o **Ocultar clasificación PEGI** si lo
   deseas.
6. Marca **Centrar logo de WoW sobre el acceso** si quieres mover el logotipo
   principal desde la esquina hasta encima del formulario.
7. Para cambiar su imagen, marca **Usar logo personalizado**, pulsa
   **Elegir PNG/BLP...** y selecciona tu archivo.
8. Pulsa **Aplicar fondo** y confirma. Studio crea las copias de seguridad,
   actualiza el Lua/XML localizado y, si procede, la textura BLP global; después
   valida los MPQ resultantes.
9. Usa **Restaurar copia** si quieres recuperar el estado previo al primer
   cambio realizado por Studio.

### 1. Iniciar Studio y elegir el idioma

Abre **AzaleaCore MPQ Studio.exe** desde la carpeta portable, o inicia el
programa desde el código fuente siguiendo las instrucciones de más abajo. El
botón **English**/**Español** del encabezado cambia el idioma de la interfaz;
la preferencia se conserva para la próxima ejecución. Los nombres de archivos y
las rutas internas se muestran tal como están almacenados y no se traducen.

### 2. Preparar una carpeta de trabajo

En la pestaña **EXPORTAR**, selecciona una carpeta de laboratorio como carpeta
de trabajo. Studio crea dentro las carpetas `exportar` y `empaquetar`. Trabaja
con copias y no uses la carpeta de instalación del juego como carpeta de
trabajo.

### 3. Abrir e inspeccionar un MPQ

Pulsa **Abrir MPQ** (o `Ctrl+O`) y selecciona un archivo `.MPQ`, por ejemplo
uno de la carpeta `Data` del cliente. El panel izquierdo presenta las rutas que
Studio pudo identificar. Expande los triángulos para recorrer carpetas; usa
**Buscar** o `Ctrl+F` para filtrar por un fragmento del nombre o de la ruta.
Si hace falta, carga un listfile de texto: sus rutas se contrastan con el MPQ
antes de incluirlas en la vista. Seleccionar una entrada muestra sus propiedades
en el panel inferior.

### 4. Preparar y extraer archivos

En el árbol del MPQ, haz doble clic en un archivo o selecciónalo y pulsa `>>`.
Para retirar una entrada de la pila, vuelve a hacer doble clic sobre ella o
selecciónala en la pila y pulsa `<<`. El botón **Todo >>** añade el contenido
visible al lote. Pulsa **Extraer** (`Ctrl+E`) y elige `exportar` como destino.
La estructura de carpetas interna se conserva. Studio crea además un manifiesto
con información y hashes de los archivos exportados.

### 5. Preparar un parche nuevo

Edita fuera de Studio únicamente copias de los archivos que quieras incluir y
colócalas bajo `empaquetar`, conservando su ruta relativa. En la pestaña
**IMPORTAR**, actualiza la vista y selecciona los archivos o carpetas deseados;
usa **Todo >>** sólo si de verdad quieres incluir todo lo que hay allí. Revisa
la lista del MPQ nuevo. La casilla para añadir `(listfile)` es opcional y está
desactivada por defecto.

### 6. Crear e instalar el MPQ

Elige como destino una carpeta de instalación de prueba o una carpeta aparte.
Studio propone el siguiente nombre de parche disponible y no sobrescribe los
existentes. Comprueba el aviso y la ruta propuesta antes de confirmar. El
programa crea un MPQ nuevo, lo vuelve a abrir y valida su contenido contra los
archivos de entrada; conserva un registro y un manifiesto del resultado. Para
probar un parche de juego, instala primero en una copia del cliente y verifica
que el cliente lo carga. No uses este procedimiento para alterar los MPQ
originales.

### 7. Atajos, avisos y ayuda

`Ctrl+O` abre un MPQ, `Ctrl+F` enfoca la búsqueda, `Ctrl+E` extrae la pila,
`F5` actualiza la pestaña activa y `Supr` quita la selección de una cola. El
menú contextual aparece con el botón derecho. Si una operación muestra un
error, el diálogo permite copiar el detalle para compartirlo en una incidencia.
Los avisos sobre `Interface\\GlueXML` son intencionados: el cliente 3.3.5a
probado rechaza estos archivos de interfaz de login personalizados.

## User guide (English)

### Change the animated login background

1. Close `Wow.exe`.
2. Open **LOGIN BACKGROUND** and choose the client root folder.
3. Click **Detect** and verify that Studio finds the localized MPQ containing
   `Interface\GlueXML\AccountLogin.lua`.
4. Choose Classic, The Burning Crusade, or Wrath of the Lich King.
5. Optionally select **Hide Blizzard logo** and/or **Hide PEGI rating**.
6. Select **Center WoW logo above the login** to move the main logo from the
   top-left corner to the center above the form.
7. To replace its image, select **Use custom logo**, click **Choose PNG/BLP...**,
   and choose an image.
8. Click **Apply background** and confirm. Studio creates backups, updates
   only the login Lua and XML, and validates the resulting MPQ.
9. Use **Restore backup** to return to the state from before Studio's first
   change.

### 1. Start Studio and choose a language

Launch **AzaleaCore MPQ Studio.exe** from the portable folder, or run the source
version using the instructions below. The **English**/**Español** header button
switches the interface language, and the choice is remembered for the next
run. File names and internal paths remain unchanged because they are stored
that way in the archive.

### 2. Set up a workspace

In the **EXPORT** tab, choose a lab/workspace folder. Studio creates `exportar`
and `empaquetar` inside it. Work with copies; do not use the game's installation
folder as your workspace.

### 3. Open and inspect an MPQ

Click **Open MPQ** (or press `Ctrl+O`) and choose an `.MPQ` file, such as one in
the client's `Data` folder. The left pane lists paths Studio could identify.
Expand folders with the disclosure arrows and use **Search** or `Ctrl+F` to
filter by part of a name or path. If needed, load a text listfile; its paths
are checked against the MPQ before they are shown. Selecting an entry displays
its properties in the lower pane.

### 4. Queue and extract files

In the archive tree, double-click a file or select it and click `>>`. To remove
an entry from the queue, double-click it again or select it in the queue and
click `<<`. **Todo >>** adds the visible contents to the batch. Click
**Extract** (`Ctrl+E`) and choose `exportar` as the destination. The internal
folder structure is preserved. Studio also writes a manifest containing file
metadata and hashes.

### 5. Prepare a new patch

Edit copies outside Studio and place only the files you want to include under
`empaquetar`, preserving their relative paths. In **IMPORT**, refresh the view
and select the desired files or folders; use **Todo >>** only if everything in
that folder should be included. Review the new MPQ's file list. Adding a
`(listfile)` is optional and disabled by default.

### 6. Build and install the MPQ

Choose a test installation folder or another separate destination. Studio
suggests the next available patch filename and will not overwrite an existing
one. Review the proposed path and file list before confirming. The app creates a
new MPQ, reopens it, and validates its contents against the input files; it
also keeps a log and manifest. Test game patches against a copy of the client
first. Do not use this workflow to alter original MPQs.

### 7. Shortcuts, warnings, and help

`Ctrl+O` opens an MPQ, `Ctrl+F` focuses search, `Ctrl+E` extracts the queue,
`F5` refreshes the active tab, and `Delete` removes the selection from a queue.
Right-click an item for its context menu. If an operation fails, the error
dialog can copy its details for an issue report. Studio permits packaging
`Interface\\GlueXML` paths without a warning dialog, but does not guarantee
compatibility with every client executable. Test on a client copy and keep a
backup; Lua string edits and XML replacements may behave differently.

## Alcance previsto

1. Abrir y explorar un MPQ.
2. Buscar rutas y archivos internos.
3. Extraer archivos o directorios.
4. Comparar la presencia y prioridad de recursos entre varios MPQ.
5. Construir parches nuevos sin modificar los archivos originales.
6. Validar estructura, contenido y hashes del resultado.

## Ejecución del esqueleto

Requiere Python 3.11 o posterior.

En Windows se puede abrir con doble clic en:

```text
Iniciar AzaleaCore MPQ Studio.bat
```

O desde PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m azaleacore_mpq_studio
```

También se puede inspeccionar un MPQ desde consola:

```powershell
python -m azaleacore_mpq_studio --inspect "D:\World of Warcraft 3.3.5a\Data\patch-9.MPQ"
```

### Sobre los nombres internos

MPQ almacena hashes de las rutas. Si el archivo contiene `(listfile)`, Studio
lo utiliza. Si no lo contiene, prueba un catálogo local de rutas conocidas y
avisa del número de entradas cuyo nombre todavía no puede recuperar.

## Versión portable para Windows

La carpeta portable se puede copiar y ejecutar en Windows sin instalar Python.
Para descargar una versión ya compilada, abre la página de
[Releases de AzaleaCore MPQ Studio](https://github.com/AzaleaDevs/AzaleaCore-MPQ-Studio/releases),
entra en la versión más reciente y descarga el ZIP portable que aparece en
**Assets**. También puedes usar la
[descarga directa de la versión 0.20.0](https://github.com/AzaleaDevs/AzaleaCore-MPQ-Studio/releases/download/v0.20.0/AzaleaCore.MPQ.Studio.0.20.0.portable.zip).
Descomprímelo y ejecuta `AzaleaCore MPQ Studio.exe` desde la carpeta extraída;
no hace falta instalar Python. El ZIP de código fuente de GitHub no es el
portable compilado.

Para compilar el portable desde el código fuente en Windows con Python 3.11 o
posterior, ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_portable.ps1
```

La primera compilación crea un entorno virtual local e instala PyInstaller desde
PyPI; requiere conexión a Internet. El resultado contiene la carpeta completa
de la aplicación y un ZIP para distribuir. Se compila en Windows porque
PyInstaller no es un compilador cruzado.

## Download the Windows portable app

To download a prebuilt version, open the
[AzaleaCore MPQ Studio Releases page](https://github.com/AzaleaDevs/AzaleaCore-MPQ-Studio/releases),
open the latest release, and download the portable ZIP listed under **Assets**.
You can also use the
[direct download for version 0.20.0](https://github.com/AzaleaDevs/AzaleaCore-MPQ-Studio/releases/download/v0.20.0/AzaleaCore.MPQ.Studio.0.20.0.portable.zip).
Extract the ZIP and run `AzaleaCore MPQ Studio.exe` from the extracted folder;
Python does not need to be installed. GitHub's source-code ZIP is not the
prebuilt portable app.

To build the portable app from source on Windows with Python 3.11 or newer, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_portable.ps1
```

## Seguridad

Trabaja siempre con copias o destinos de laboratorio. No abras ni distribuyas recursos para los que no tengas autorización.

