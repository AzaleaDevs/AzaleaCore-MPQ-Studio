# Hoja de ruta inicial

## Fase 1 — Fundamentos

- Definir requisitos funcionales y tecnológicos.
- Incorporar pruebas con MPQ pequeños y copias controladas.
- Separar claramente lectura, extracción y escritura.

## Fase 2 — Lector

- Analizar cabecera y tablas MPQ.
- Enumerar archivos cuando exista `(listfile)`.
- Leer y extraer archivos sin modificar el contenedor.
- Mostrar errores y metadatos de forma comprensible.

## Fase 3 — Interfaz

- Ventana principal y selector de archivos.
- Árbol de rutas internas.
- Búsqueda, panel de propiedades y visor de texto.
- Extracción mediante selector de destino.

## Fase 4 — Empaquetado

- Crear MPQ nuevos desde un directorio de proyecto.
- Generar manifiesto y hashes.
- Reabrir y validar cada archivo generado.
- Impedir por defecto la sobrescritura de archivos existentes.

## Fase 5 — Distribución

- Pruebas automatizadas.
- Manual de usuario.
- Compilación portable para Windows.

