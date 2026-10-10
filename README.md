# AzaleaCore MPQ Studio

Aplicación de escritorio para investigar, extraer, validar y crear archivos MPQ de forma segura, con atención inicial a World of Warcraft 3.3.5a (build 12340).

## Estado

La versión 0.8 incluye un lector MPQ de solo lectura, búsqueda instantánea,
exportación múltiple con
rutas conservadas y creación validada de parches mínimos. La aplicación nunca
edita un MPQ existente.

El botón **Acerca de** muestra la versión y el objetivo de la herramienta.

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

En la pestaña EXPORTAR, el campo **Buscar** filtra instantáneamente por cualquier
fragmento de la ruta interna. `Ctrl+F` lleva el foco al buscador.

En **EXPORTAR**, se puede cargar un listfile externo de texto. Studio combina
esas rutas con las rutas conocidas y con el `(listfile)` interno del MPQ; cada
ruta externa se contrasta con las tablas del archivo antes de mostrarla. El
botón **Quitar** descarga la lista para la sesión actual.

Al seleccionar un único archivo o carpeta, el panel inferior muestra sus
propiedades. Para los archivos incluye la ruta interna, los tamaños real y
almacenado, los flags MPQ y un botón que calcula el SHA-256 bajo demanda sin
escribir en el archivo original.

El programa nunca sobrescribe un parche. Si detecta `patch-8.MPQ`, propone
`patch-9.MPQ`. Si ya existe la ranura 9, bloquea `patch-10.MPQ` porque el cargador
de WoW 3.3.5a observado sólo demuestra nombres de un dígito.

Si la selección contiene `Interface\GlueXML`, Studio muestra una advertencia
visible y la repite antes de crear el MPQ. La prueba local confirmó que el
cliente original rechaza esos cambios como interfaz de inicio dañada.

## Principios

- Los archivos originales se abren en modo de solo lectura.
- La aplicación nunca sobrescribe un MPQ del cliente por defecto.
- Todo MPQ generado se vuelve a abrir y validar.
- Las operaciones importantes producen un registro y un manifiesto reproducible.
- La interfaz y la documentación estarán disponibles en español.

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

## Seguridad

Trabaja siempre con copias o destinos de laboratorio. No abras ni distribuyas recursos para los que no tengas autorización.

