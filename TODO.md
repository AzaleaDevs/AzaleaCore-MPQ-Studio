# AzaleaCore MPQ Studio — Lista de tareas

Cada tarea debe terminar con pruebas superadas, repositorio limpio y commit
subido a `main`. No se mezclan tareas salvo que una dependencia lo exija.

## Base completada

- [x] 1. Crear el repositorio, estructura Python y lanzador para Windows.
- [x] 2. Implementar lector MPQ estrictamente de solo lectura.
- [x] 3. Crear selector de MPQ y árbol de carpetas expandible.
- [x] 4. Reconocer `patch-9.MPQ` mediante catálogo de rutas conocidas.
- [x] 5. Añadir pila múltiple de extracción con doble clic y botones `>>`/`<<`.
- [x] 6. Crear automáticamente las carpetas `exportar` y `empaquetar`.
- [x] 7. Extraer archivos conservando la ruta interna y generar manifiesto SHA-256.
- [x] 8. Añadir pestaña IMPORTAR con selección individual, por carpeta o completa.
- [x] 9. Construir MPQ mínimos, reabrirlos y validar sus archivos byte a byte.
- [x] 10. Calcular la siguiente ranura segura `patch-1` a `patch-9` sin sobrescribir.
- [x] 11. Detectar destinos localizados, por ejemplo `patch-esES-N.MPQ`.
- [x] 12. Bloquear la falsa prioridad de `patch-10.MPQ` en el modo WoW 3.3.5a.
- [x] 13. Advertir cuando un paquete contiene GlueXML protegido.

## Próximos pasos esenciales

- [x] 14. Añadir buscador y filtro instantáneo de rutas dentro del MPQ abierto.
- [x] 15. Añadir panel de propiedades del archivo seleccionado.
- [x] 16. Mostrar ruta completa, tamaños, flags y SHA-256 bajo demanda.
- [x] 17. Permitir cargar un `(listfile)` externo desde la interfaz.
- [ ] 18. Crear un catálogo editable de rutas conocidas.
- [ ] 19. Guardar y reutilizar catálogos sin modificar los MPQ.
- [ ] 20. Resolver el proveedor efectivo de una ruta recorriendo una carpeta `Data`.
- [ ] 21. Mostrar todas las copias encontradas y su orden de prioridad.
- [ ] 22. Comparar hashes y tamaños de una misma ruta entre varios MPQ.

## Vista previa e investigación

- [ ] 23. Vista previa segura de Lua, XML, TOC y TXT.
- [ ] 24. Vista hexadecimal limitada para formatos desconocidos.
- [ ] 25. Leer metadatos BLP: versión, dimensiones, compresión y mipmaps.
- [ ] 26. Mostrar una vista previa visual de imágenes BLP compatibles.
- [ ] 27. Leer cabeceras DBC y mostrar número de registros/campos.
- [ ] 28. Añadir exportación del informe de propiedades a JSON.

## Proyectos, instalación y reversión

- [ ] 29. Guardar la sesión de trabajo y las pilas en un archivo de proyecto.
- [ ] 30. Reabrir un proyecto anterior sin perder sus rutas de origen.
- [ ] 31. Registrar cada parche creado o instalado.
- [ ] 32. Añadir restauración segura de parches instalados por Studio.
- [ ] 33. Verificar hashes antes de retirar o restaurar un parche.
- [ ] 34. Añadir modo simulación: mostrar el plan sin escribir archivos.
- [ ] 35. Separar “MPQ genérico” de “Parche WoW 3.3.5a”.
- [ ] 36. Permitir nombre libre únicamente en modo MPQ genérico.

## Compatibilidad MPQ

- [ ] 37. Añadir archivos comprimidos con zlib al constructor.
- [ ] 38. Ampliar los métodos de descompresión soportados.
- [ ] 39. Detectar archivos cifrados y explicar su estado sin fallar todo el árbol.
- [ ] 40. Investigar y probar MPQ con cabecera incrustada o desplazada.
- [ ] 41. Investigar archivos delta MPQ sin implementarlos prematuramente.
- [x] 42. Añadir opción para incluir `(listfile)` en MPQ creados por Studio.
- [x] 43. Mantener el modo de parche mínimo sin `(listfile)`.

## Experiencia de usuario y distribución

- [ ] 44. Añadir arrastrar y soltar para abrir MPQ y añadir archivos.
- [ ] 45. Incorporar menú contextual y atajos de teclado.
- [ ] 46. Añadir barra de progreso y cancelación para operaciones largas.
- [x] 47a. Copiar errores y avisos con versión, título y detalle desde el diálogo.
- [ ] 47b. Generar un registro técnico exportable.
- [x] 48. Recordar de forma opcional la última carpeta de trabajo.
- [x] 49a. Mostrar versión e información del proyecto en “Acerca de”.
- [x] 49b. Crear icono de aplicación.
- [x] 49c. Usar el icono propio en la barra de tareas de Windows.
- [ ] 50. Empaquetar una versión portable para Windows.
- [ ] 51. Probar la versión portable en un equipo sin Python instalado.
- [ ] 52. Preparar manual de usuario y capturas para AzerothCore Labs.

## Regla de cierre para cada tarea

1. Implementar sólo el alcance numerado.
2. Añadir o actualizar pruebas automáticas.
3. Ejecutar todas las pruebas existentes.
4. Probar la interacción gráfica afectada.
5. Actualizar versión y documentación cuando corresponda.
6. Crear un commit independiente y subirlo al remoto.
