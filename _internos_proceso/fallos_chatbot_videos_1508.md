# Los 7 vídeos de Jesús del 15-08 (madrugada): qué enseña cada uno

Siete grabaciones de pantalla con su voz (WhatsApp, carpeta `Desktop/wp videos`).
Transcritas con Whisper y vistas fotograma a fotograma. Aquí está cada fallo con la
frase literal de Jesús, lo que se ve en pantalla, y por dónde huele cada uno.

La sesión que está arreglando el chatbot: esto es la lista de la compra. El orden de
los apartados es el de gravedad según lo vive él, no el de los vídeos.

---

## 1 · El asistente vive en un día que no es el que estás mirando (vídeo 1, 2:19)

**Jesús:** «Estoy en un día, me voy a mañana, me voy al asistente IA y me sale esto,
¿por qué? Si yo me he cambiado de día... Esto tiene que coincidir con el día. Si yo
estoy aquí en un día y me voy al día siguiente, que siempre estén en el día.»

**Pantalla:** Nutrición en `?date=2026-08-16` (domingo, vacío), y el chat diciendo
«Vamos con **Hoy**... Seguimos por Comida 4. Te faltan 13 P · 17 H · 1 G». Solo después
de reiniciar la conversación (pantalla «¡Hola! → Empezar») el chat arranca con «Vamos
con **domingo, 16 de agosto**».

**El fallo:** la sesión del chat guarda su propio día y cambiar el día en Nutrición no
la mueve. El cliente no tiene ninguna forma visible de cambiar de día desde el chat
(existe escribir «mañana», pero no lo descubre ni Jesús). La única salida que encontró
fue borrar la conversación.

**Lo que espera:** el asistente abre SIEMPRE en el día que está viendo en Nutrición.
Punto. Si la sesión guardada es de otro día, se muda (o se abre limpia en el día nuevo),
no se queda donde estaba.

**Dos quejas más del mismo vídeo:**
- Tras el reinicio, el bot suelta de golpe «Perfecto, día de entrenamiento con 4
  comidas... ¿Qué quieres tomar?» — «**no me han hecho ninguna pregunta**, directamente
  me han dicho esto». El arranque va demasiado lanzado.
- «Si quiero cambiar el horario del domingo, ¿cómo lo cambio? ¿Y el entrenamiento?» —
  no encuentra cómo tocar horario/entreno-descanso de OTRO día. (En Nutrición está el
  conmutador Entreno/Descanso del día, pero él no lo ve como respuesta; y desde el chat
  no hay camino claro.)

---

## 2 · Se pasa de proteína, lo justifica, y encima pierde un ingrediente (vídeo 2, 1:15)

**Jesús:** «Le he pedido una tortilla de claras, con jamón, **yogur** y pan... se ha
pasado 9 gramos de proteína... tenía que haber puesto menos claras... no me puede
pasar... ajustar hasta el final, pero **metiendo, no pasándose**.»

**Pantalla:** montó Claras 29,7 P + Jamón cocido (Hacendado) 9,5 P + Pan 15 H.
Objetivo 30 P. Resultado: «Te pasas 9.2 g de proteína · Faltan 10 g de grasa». Y el
texto del bot: «vamos pasados unos 9 g (**no pasa nada, es un ligero extra de
proteína**)».

**Los fallos, que son tres:**
1. **El compositor llena la proteína con las claras SOLAS y luego suma el jamón encima.**
   Deja las claras a tope del objetivo y el jamón lo desborda. Tenía que repartir:
   claras ~20 P + jamón ~9,5 P = clavado. Es el mismo defecto de fondo que
   «sugerencias por piezas»: cada ingrediente se dimensiona como si rematara él solo.
2. **El yogur desapareció sin decirlo.** Pidió cuatro cosas, montó tres. Si algo no
   cabe o no lo encuentra, se dice («el yogur no entra sin pasarnos; ¿lo cambio por X
   o lo quito?»), no se calla.
3. **«No pasa nada, es un ligero extra»**: el bot no puede quitarle importancia a
   pasarse. La regla de Jesús es dura: por abajo se ajusta, por arriba no se pasa.

---

## 3 · Cantidades feas, verdura a 50, y opciones que nadie pidió (vídeo 3, 1:05)

**Jesús:** «Los vegetales siempre que sugiera 100 gramos, no 50 por defecto... aquí ha
metido acabado en 1 y en 6: se acaba en 0 y en 5... las claras, que ofrezca 200 aunque
no se ajuste del todo... le he dicho "vamos con la comida 2" y me ha dado 3 opciones
**sin yo pedirlo**.»

**Pantalla:** cantidades **81 g**, **136 g**, **206 g** de claras. Y tras «vamos con la
comida 2», tres menús con «¿Sigues con la opción 1, la opción 2 o la opción 3?».

**Los fallos:**
1. **Redondeo:** los gramos que salen del cuadre van al gramo (81, 136, 206). Regla
   nueva de Jesús: **todo gramaje sugerido acaba en 0 o en 5** (las piezas ya van por
   unidades). Prefiere 200 g de claras «aunque no se ajuste del todo» a 206.
2. **Verdura por defecto 100 g, nunca 50.** (Ya era regla de Calma; se ve sugerida a 50.)
3. **«Vamos con la comida 2» no es «dame opciones».** Es situarse. La respuesta es
   «Comida 2, te faltan X · ¿qué quieres tomar?» — no tres menús espontáneos.

---

## 4 · Dos «opción 2» vivas a la vez: el lío central (vídeos 4 y 5, 1:02 + 0:20)

**Jesús:** «Le digo un batido de proteínas y me pone queso batido con nueces, **esto no
es un batido**... le digo "la 2, ajustada" y me dice: una es la ensalada con atún y la
otra es el batido... **se lía tío, se lía**.»

**Pantalla (la secuencia entera):**
1. En Comida 3 había una ronda ANTERIOR de opciones (una era «ensalada con patata y
   atún»).
2. Pide «un batido de proteínas». El bot propone: **Opción 1: Queso fresco batido 0% +
   nueces** («batido espeso tipo yogur bebible») y **Opción 2: aislado + leche de
   almendras + nueces + crema de arroz**, avisando de que la 2 va pasada de hidratos
   (24P/20H/15G sobre 24P/10H/15G) y ofreciendo ajustarla.
3. Jesús: «**la 2, pero ajustada**».
4. Bot: «Vale, hay **dos opciones 2** delante: una es la ensalada con patata y atún, la
   otra es el batido... ¿con cuál me quedo?» ← aquí se rompe todo.
5. (Vídeo 5) Jesús escribe «batido» y el bot, en vez de actuar: «ya tienes una opción de
   batido montada (la opción 2)... ¿te quedas con esa o te propongo otro?» — bucle.

**Los fallos:**
1. **Las listas de opciones viejas no caducan.** «La 2» tiene que referirse SIEMPRE a la
   última lista enseñada; al proponer una lista nueva, las anteriores mueren. El candado
   del 14-08 («cuando la comida se toca, las tarjetas anteriores caducan») cubrió el
   estado de la comida, pero NO caduca una lista cuando se propone la siguiente: por eso
   convivían la «opción 2 ensalada» y la «opción 2 batido».
2. **«Batido» ≠ «queso fresco batido».** Está casando por nombre («batido» aparece en
   «queso fresco **batido** 0%»). Un batido pedido en el chat es bebida de shaker:
   proteína en polvo + líquido (+ fruta/crema de arroz si caben). El queso batido podrá
   ser alternativa ofrecida como «si prefieres cuchara», nunca la opción 1 de «batido».
3. **Confirmar no ejecuta.** «La 2, pero ajustada» es una instrucción completa (elige la
   2 Y ajústala). Respuesta correcta: ajustar la 2 y enseñarla. En vez de eso pregunta
   otra vez. Mismo patrón de [[bucles-del-asistente]]: tras el «sí» del cliente falta la
   mitad de la instrucción que dice qué pasa después.

---

## 5 · Un litro de leche, guardar roto, y dos mensajes que se contradicen (vídeo 6, 0:43)

**Jesús:** «Ahora dice que me mete de golpe **un litro de leche**... se hace un lío...
"no puedo guardar comida vacía", no entiendo tío.»

**Pantalla:** la Comida 3 quedó: Whey Isolate **47,9 P** (objetivo ~24 P), **Leche de
almendras 1000 g**, nueces 23 g, crema de arroz 40 H. Aviso: «Te pasas **23,9 g de
proteína y 30 g de hidratos y 15 g de grasa**». El bot, con ese incendio delante, solo
propone «¿te bajo la crema de arroz a 12 g?». Luego: «**Comida guardada ✓** ⚠ En Comida
3 te pasas 23.9...» y a renglón seguido «**No puedes guardar una comida vacía**. Dime
qué quieres comer primero» (eso era por la Comida 4, vacía, pero para el cliente es el
mismo botón dos frases seguidas: guardado ✓ / no puedo guardar).

**Los fallos:**
1. **Sin techo por alimento en líquidos/acompañantes**: 1000 g de leche como relleno es
   una barbaridad que ningún humano montaría. Las piezas ya tienen techo; los gramajes
   continuos no (o no uno razonable por categoría).
2. **Deja guardar una comida pasada en 24P/30H/15G con un simple ⚠.** Pasarse un poco y
   avisar, vale; guardar algo fuera de margen en TODOS los macros sin frenar, no.
3. **El diagnóstico del bot no ve el conjunto**: con 24 g de proteína sobrante, ofrece
   recortar 10 g de hidratos de la crema. Cuando una comida está rota por varios lados,
   la salida es remontarla (o proponer vaciarla), no limar una esquina.
4. **Los dos mensajes seguidos** («guardada ✓» / «no puedes guardar una vacía») piden
   una transición: «Comida 3 guardada. La Comida 4 está vacía: dime qué quieres tomar y
   la montamos» — no un error seco.

---

## 6 · Una sola conversación por cliente: se pisan (vídeo 7, 0:36)

**Jesús:** «Claude lo ha abierto en el mismo día... es una sola conversación por
cliente... se ha quedado en el móvil y no lo ha dado a la vez, **se pisan**... y además
me da error cuando metes un plátano con no sé qué.»

**Pantalla:** dos ventanas con el MISMO chat (una en el día de la tortilla, otra en el
domingo 16 con el post-entreno), y una sesión de Claude Code en paralelo explicándole
justo eso: «el asistente no abre una conversación por pestaña: es una sola conversación
por cliente, guardada en el servidor... mi plátano y tu tortilla mezclados».

**Los fallos:**
1. **`chatbot_sessions` es una por cliente** (decisión del 19-07 para persistir entre
   workers). Con dos ventanas abiertas (o el coach entrando con «actuar como» mientras
   el cliente escribe, o el móvil quedado abierto), las dos escriben en la misma
   conversación y se mezclan. Como mínimo: sesión **por cliente y por día** (encaja con
   que el chat es «montar el día» y arregla de paso el fallo 1); mejor aún, detectar la
   ventana vieja (versión de sesión) y decirle «esta conversación siguió en otro sitio,
   recarga».
2. **El error del plátano**: «me da error cuando metes un plátano con no sé qué». En los
   fotogramas no se ve la traza (la otra sesión de Claude se lo estaba reproduciendo).
   Queda por reproducir: pedir «un batido de proteína con un plátano» en el post-entreno
   del domingo. Puede ser el guion del peri-entreno (0 G de objetivo) o la pieza.

---

## 7 · Transversal: números de máquina en boca del asistente

En todos los vídeos: «Te faltan 13 P · 17 H · 1 G», «Tu objetivo son 40.5 P · 10 H ·
15.0 G», «Falta: proteína **-9.2 g**» (la cabecera con negativo cuando va pasado),
«15.0 P · 15.0 H · 0.0 G», decimales con punto y cero pegado.

Ya estaba señalado por la otra sesión de Claude en el vídeo 7. Para el cliente:
«40,5 g de proteína», «te pasas 9 g» (nunca un negativo), coma decimal, y sin `.0`.

---

## Resumen para atacarlo (mi orden)

1. **Sesión por día + abrir siempre en el día de Nutrición** (mata los fallos 1 y 6.1).
2. **Caducar las listas de opciones al proponer una nueva** y que «la N» sea solo de la
   última (mata el 4.1 y buena parte de «se lía a medida que avanza»).
3. **Compositor: repartir sin pasarse** (claras al hueco que deja el jamón, no al techo),
   **techo por alimento** (nada de 1000 g de leche) y **no perder ingredientes pedidos
   sin decirlo** (2.1, 2.2, 5.1).
4. **Redondeo a 0/5 en gramos + verdura a 100** (3.1, 3.2) — es una pasada por el
   formateo de cantidades del compositor.
5. **«Batido» = shaker** (4.2) — al buscar por término de forma de plato, no casar por
   substring del nombre comercial.
6. **No guardar comidas fuera de margen sin frenar + transición guardada/vacía** (5.2,
   5.4).
7. **Formato humano de números** (7).
8. Reproducir **el error del plátano** (6.2) antes de darlo por entendido.

Los vídeos quedan en `Desktop/wp videos`; los fotogramas y transcripciones, en el
scratchpad de la sesión del 15-08 (`videos/`).
