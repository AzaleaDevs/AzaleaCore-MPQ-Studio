# Registro de versiones

## 0.20.0 — 2026-10-12

### Nuevo

- Pestaña **FONDO LOGIN** para detectar el MPQ localizado efectivo y cambiar
  el escenario animado entre Classic, The Burning Crusade y Wrath of the Lich
  King.
- Controles independientes para ocultar el logo de Blizzard y la clasificación
  PEGI sin eliminar los objetos XML esperados por el cliente.
- Opción para mover el logo principal desde la esquina superior izquierda y
  centrarlo encima del formulario de acceso.
- Selector de logo personalizado compatible con PNG, JPG, WebP, TGA, BMP y BLP.
- Conversión automática a BLP2 DXT5 de 512×256, con transparencia, proporción
  conservada y cadena completa de mipmaps.
- Instalación coordinada en `patch-esES-3.MPQ` para Lua/XML y en
  `Data\patch-9.MPQ` para la textura global que carga WoW 3.3.5a.

### Seguridad y restauración

- Copias independientes `.before-login-background` y `.before-login-logo`
  creadas antes del primer cambio.
- Sustitución atómica y validación byte a byte de las entradas modificadas.
- Conservación de entradas MPQ desconocidas que no figuren en el `(listfile)`.
- **Restaurar copia** recupera conjuntamente el fondo, XML y logo originales.
- Detección de `Wow.exe` bloqueando los archivos y mensajes de error legibles.

### Compatibilidad verificada

- World of Warcraft 3.3.5a, compilación 12340, cliente esES.
- Fondo Classic, ocultación de Blizzard/PEGI, logo centrado y logo PNG
  personalizado verificados visualmente en el cliente real.
- 29 pruebas automáticas superadas y ejecutable portable comprobado.

### Notas de uso

- `Wow.exe` debe estar cerrado al aplicar o restaurar cambios.
- El cliente carga el XML localizado desde `patch-esES-3.MPQ`, pero la textura
  personalizada debe sobrescribir la ruta gráfica global desde `patch-9.MPQ`.
- Para aprovechar toda el área del logo se recomienda una imagen transparente
  con proporción 2:1.
