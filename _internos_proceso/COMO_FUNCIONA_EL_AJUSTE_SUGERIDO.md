# Cómo funciona el "Ajuste sugerido por el asistente"

Explicación para Jesús, en cristiano.

## En una frase

No es una calculadora. Es un asistente al que le hemos metido tu método por escrito,
le damos delante la ficha entera del cliente y le pedimos que proponga el ajuste del
mes como lo propondrías tú. Tú lo lees, lo cambias si quieres y lo confirmas. Hasta que
no le das a guardar, no se toca nada ni el cliente ve nada.

## De dónde saca los datos

Cuando pulsas "Sugerir ajuste (IA)", la app va a buscar cinco cosas:

1. **Los macros que tiene hoy.** Los 8 números tal y como están en su ficha (entreno,
   intra, descanso), más el sexo, la fase, el biotipo y el % graso si consta. Le pasamos
   ya sumado el HC total del día de entreno (entreno + intra), que es la cifra con la que
   tú lees dónde está.
2. **Todos sus pesajes.** Se juntan los de Calma, los de los reportes de la app y los que
   quedaron apuntados en cambios de macros anteriores, se ordenan por fecha y se limpian
   los errores de coma (un 819 se lee como 81,9). De ahí salen las tres líneas de arriba
   de la tarjeta: último peso y fecha, cuánto se ha movido desde el pesaje anterior y en
   cuántos días, y cuánto desde el inicio. Además se le pasa cada tramo en % del peso
   corporal, no en kilos sueltos.
3. **Su último reporte.** Cumplimiento de dieta, esfuerzo que le cuesta, cumplimiento de
   entreno y cardio, descanso, objetivo y el comentario que escribió. De ahí sale el
   "cumplimiento al 70%" y también la fase (si en el objetivo pone volumen, va a volumen).
4. **Su historial de ajustes.** Todos los cambios de macros que se le han hecho, los
   importados de Calma y los hechos en la app. Los de la app llevan además el criterio que
   escribiste al hacerlos y cómo evaluaste la fase después. Eso es lo que más le enseña:
   repite lo que a esa persona le funcionó y no repite lo que se marcó como malo.
5. **La memoria de la cartera.** Su perfil, las reglas de su perfil y casos parecidos de
   otros clientes (misma fase, mismo sexo, estado similar) con el desenlace de cada uno:
   de qué estado partía, qué se le movió y qué hizo el peso después.

## El recuadro del perfil, número a número

Todo eso se calcula del propio camino de cada cliente, no del cuestionario.

- **Motor alto (5,06 g HC/kg en su techo).** Es cuánto hidrato tolera: los gramos de HC
  total por kilo a los que llegó en su punto más alto. Alto, medio o bajo se decide
  comparándolo con el resto de tu cartera, partida por sexo. No hay números inventados.
- **Respondedor sin dato.** Este eje mide si coge músculo comiendo mucho, y necesita
  % graso apuntado en varios momentos. Casi nadie lo tiene en el histórico, así que en la
  mayoría sale "sin dato" y el asistente lo dice en vez de inventárselo.
- **Techo/suelo 430/230 g.** La suma más alta de HC a la que ha llegado y el punto más
  bajo que ha aguantado, sacados de su historial. Son sus límites, no unos generales.
- **Umbral vol. 420 g.** El punto a partir del cual, en su caso, se le subió el hidrato y
  el peso no subió. Es lo que hace que el asistente diga "aquí ya no rinde empujar más".
- **2 reglas de su perfil.** La mediana de lo que se hizo de verdad con clientes de su
  mismo perfil, en esa fase y con ese cumplimiento, y lo que hizo el peso después. Solo
  se usan grupos con 5 casos o más, para que sea una regla y no una anécdota.

## Cómo llega a la conclusión

En su cabeza está escrito tu método, con las reglas que no se saltan nunca:

- La proteína no se toca en un ajuste normal, solo en cambio de fase.
- El HC de entreno es el que manda y arrastra a los demás.
- El intra acompaña al HC de entreno por tramos, no va suelto.
- El HC de descanso nunca iguala ni supera al de entreno.
- Suelos: la grasa no baja de 40, y en el punto más bajo no más de un mes.
- Los escalones son reales: 10, 15, 20, 25, 30, 40, 50 o 60. Si no merece la pena mover
  10, no se mueve nada.
- El techo y el suelo son de cada persona.
- Pautado contra real, en tres escalones: si no ha cumplido no se toca nada porque el
  fallo no es del ajuste; si ha cumplido a medias, nada grande; si ha cumplido de verdad,
  el ajuste que toque.
- El ritmo se lee en % del peso corporal, nunca en kilos sueltos.

El caso de la tarjeta encaja solo: está en su techo histórico (430), lleva 42 días sin
mover el peso, y por encima de 420 ya se vio que subir hidrato no le sube el peso. Y el
cumplimiento es 70%. Con esas tres cosas, la regla del pautado contra real manda:
el problema es la adherencia, no el ajuste. Por eso propone mantener y explicar por qué,
y deja dicho qué pasaría el mes que viene si cumple de verdad y el peso sigue plano.

## El repaso automático de después

Cuando el asistente ya ha propuesto, un chequeo aparte, sin IA, revisa la propuesta
contra el método: que la proteína no se haya movido sin cambio de fase, que los saltos
sean escalones de verdad, que la grasa no baje de 40, que descanso no supere a entreno,
que el intra acompañe y no vaya al revés, y que todo sea múltiplo de 5. Si algo chirría
te sale como aviso en la tarjeta. No bloquea: te avisa y decides tú.

## Lo que no hace

- No guarda macros ni avisa al cliente. Si le das a "Usar esta propuesta", solo te rellena
  el editor y sigues tú.
- No se inventa lo que no tiene. Cuando falta un dato lo pone en los avisos y baja la
  confianza. Por eso ahí abajo aparece "sin datos nuevos de % graso".
- No aprende solo de un día para otro. Lo que le hace mejorar es lo que vais escribiendo:
  cada ajuste con su criterio, cada fase evaluada como buena o mala y de quién fue la
  culpa, y sobre todo el % graso, que es el dato que más falta.

Cada sugerencia queda guardada, así que se puede ver luego cuáles aceptaste tal cual y
cuáles corregiste, y en qué.
