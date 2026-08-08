# Daily 5 de agosto

Día del documento de Jesús ("14 · LO QUE HAY QUE CORREGIR — 5 agosto"). 14 commits, ninguno
en producción todavía: espera su visto bueno en dev.

## El documento, punto por punto

**Bloque 1 — check-ins y catálogo**
- Los check-ins del coach decían "No entrenó" a clientes a los que nadie preguntó si
  entrenaba. Ahora la ausencia de pregunta y la respuesta "no" se distinguen.
- Catálogo: 4 cereales proteicos estaban fuera de su categoría, los pistachos figuraban con
  0 g de proteína y la tortita colgaba de la categoría 0. Arreglado en dev y en producción,
  con copia de seguridad previa. Los duplicados marca/genérico quedan listados, sin tocar.

**Bloque 2 — la pantalla donde ajusta los macros** (completo)
- La tabla de macros pasa encima de la caja de ajuste, y lo que cambia se pinta en rojo.
- El peso que se guarda es el de hoy, la fecha de efecto es mañana y se pide confirmación.
- El entrenamiento se lleva aparte, con material y lesiones editables.
- Los suplementos que vinieron cargados ya se pueden editar.
- Las fotos, todas juntas y en la misma pantalla donde ajusta.

**Bloque 3 — las fotos**
- Comparativa de cuatro fotos, cada una respondiendo a algo: de dónde vengo, dónde empezó
  esta fase, qué he hecho este mes, cómo estoy hoy. Con sus reglas de fusión de etiquetas.
  Misma lógica en la pestaña de Seguimiento y en el informe del cliente, con 10 tests.
- Fuera el comparador antes/después, que la comparativa deja sin sentido.
- El % graso se anota en la foto, que es donde se estima. Va a una serie por fecha.

**Punto 5 — las tres preguntas del reporte**
Próximo objetivo, viabilidad del ajuste y cumplimiento del entreno. Son las que traen la
fase: sin ellas no había forma de saber cuándo empezó, y el bloque 3.2 dependía de eso.

## Lo que salió por el camino

- El asistente ofrecía masa de pizza, pan y tortillas para el post. Faltaba portar la lista
  de prioridad de Calma.
- El volcado de macros no se habilitaba con las comidas cuadradas: la cabecera del día
  comparaba contra el objetivo sin descontar el peri.
- El agente ya ve cómo el coach corrigió sus propias propuestas, y de dónde salió cada
  ajuste (suyo, del quiz, de la calculadora del cliente).
- Convertir un lead cobraba 149 € en vez de lo que dice el catálogo.
- Dos fallos míos de estos días que destapó el % graso: un bucle de renders, y que
  **cualquier** guardado en la ficha del cliente se quedaba en cola detrás de las descargas
  de fotos y no llegaba nunca al servidor, sin dar error. Ahora tarda 290 ms.

## Pendiente de Jesús

- 3.3: dónde quiere que la app pida el % graso cada mes.
- 2.6: qué medidas se comparan (las suyas no coinciden con las que guarda la app).
- 6: los duplicados marca/genérico, 3 de ellos con macros distintos.
- Las tres respuestas que le debo pedir: los 7 perfiles frente a la lectura de los datos,
  10 % o 10 g de proteína, y su método grabado.
