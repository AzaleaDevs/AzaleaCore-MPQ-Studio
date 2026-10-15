# Registro de versiones

## 0.25.0 — 2026-10-15

### Módulo DBC autónomo

- El visor permite escoger y abrir un patch MPQ sin pasar por **EXPORTAR**.
- Lista todos los DBC identificados dentro del patch y los abre con doble clic.
- Las celdas aceptan valores `uint32` o texto mediante doble clic.
- Cada edición se exporta automáticamente a la carpeta `empaquetar`, conservando
  la ruta interna y manteniendo el MPQ original en solo lectura.

## 0.24.0 — 2026-10-15

### Visor DBC

- Nueva cuarta pestaña **VISOR DBC** para abrir tablas locales o cargarlas
  directamente desde la selección del MPQ.
- Validación de la cabecera WDBC, el tamaño de registros y el bloque de cadenas.
- Tabla horizontal con todos los campos, interpretación de offsets de texto y
  navegación paginada de 250 registros.
- Pruebas automáticas para cabeceras, registros, cadenas y archivos inválidos.

## 0.23.0 — 2026-10-15

### Vista previa de colores

- La muestra plana se sustituye por un botón completo que combina fondo y texto.
- La previsualización carga la textura BLP real del cliente detectado y reproduce
  la multiplicación de color que realiza `SetVertexColor`.
- Si todavía no hay un cliente disponible, se usa una textura azul de respaldo
  con el mismo tamaño y un comportamiento visual equivalente.
- Los diez controles de fondo y texto se reorganizan en una cuadrícula compacta
  de dos columnas, con deslizadores de longitud reducida.
- Pruebas automáticas para la multiplicación RGB, conservación del alfa y
  dimensiones de la textura de respaldo.

## 0.22.1 — 2026-10-14

### Corrección de seguridad

- Nueva opción **Mantener el fondo actual**, que permite cambiar colores,
  música, volúmenes y logotipos sin reescribir ninguna llamada
  `AccountLogin:SetModel`.
- Cuando Studio detecta un M2 personalizado o ambiguo selecciona automáticamente
  esta opción segura, evitando sustituir fondos comunitarios como Shadowlands.

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
