# AzaleaCore MPQ Studio

Aplicación de escritorio para investigar, extraer, validar y crear archivos MPQ de forma segura, con atención inicial a World of Warcraft 3.3.5a (build 12340).

## Estado

La primera versión incluye un lector MPQ de solo lectura y una ventana gráfica
con selector de archivo y árbol de carpetas expandible. Todavía no extrae ni
crea archivos MPQ.

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

