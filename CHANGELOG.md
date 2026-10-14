# Registro de versiones

## 0.22.0 — 2026-10-14

### Nuevo

- Editor de color independiente para el fondo y el texto de los botones del login.
- Controles RGB, saturación y brillo con valores numéricos y vista previa en vivo.
- Detección automática de los colores ya instalados y opción de volver a los
  colores originales desmarcando la personalización.

### Seguridad y validación

- El tintado conserva las texturas y el relieve originales mediante
  `SetVertexColor`; no sustituye ni degrada los recursos gráficos.
- La configuración se escribe en `AccountLogin.lua` dentro de la misma
  operación atómica y restaurable que el fondo y los elementos de marca.
- Resultado rojo/blanco cálido verificado visualmente en el cliente real y 33
  pruebas automáticas superadas.

## 0.21.0 — 2026-10-14

### Nuevo

- Selector de música MP3 personalizada para la pantalla de acceso.
- Detección del MPQ global efectivo que contiene
  `Sound\\Music\\GlueScreenMusic\\WotLK_main_title.mp3`.
- Controles independientes de volumen para música y ambiente, persistidos en
  `WTF\\Config.wtf` para el siguiente inicio del cliente.
- Copias de seguridad y restauración conjunta del MP3, los volúmenes, el fondo
  y los elementos de marca.

### Seguridad y validación

- Validación de cabecera ID3 y tramas MPEG Layer III antes de instalar una
  canción.
- Sustitución atómica y comprobación byte a byte del MP3 dentro del MPQ.
- 31 pruebas automáticas superadas, incluidas instalación/restauración de
  música y configuración de ambos volúmenes.

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
