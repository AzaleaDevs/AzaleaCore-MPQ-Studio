AzaleaCore MPQ Studio 0.20.0 - versión portable

1. Extrae el ZIP completo en una carpeta normal.
2. Abre la carpeta "AzaleaCore MPQ Studio".
3. Ejecuta "AzaleaCore MPQ Studio.exe".

No requiere instalar Python. No muevas el EXE fuera de su carpeta: los archivos
de soporte de Windows y Tcl/Tk van incluidos junto al programa.

Studio abre los MPQ de origen en modo de solo lectura durante la exploración y
la extracción. Comprueba siempre el destino propuesto antes de crear un parche.

La pestaña "FONDO LOGIN" es la única operación especializada que reemplaza un
MPQ existente. Antes crea automáticamente una copia
".before-login-background" y permite restaurarla. Cierra Wow.exe antes de
aplicar o restaurar el fondo.

En esa pestaña también se pueden ocultar el logo de Blizzard y la clasificación
PEGI sin eliminar los objetos que espera el cliente, y centrar el logo principal
de WoW encima del formulario de acceso.

El logo principal también se puede sustituir por un PNG, JPG, WebP, TGA, BMP o
BLP. Studio lo convierte a BLP2 DXT5 e instala la textura en "Data\patch-9.MPQ",
con una copia independiente ".before-login-logo".
