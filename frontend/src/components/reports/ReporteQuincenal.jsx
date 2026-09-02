/**
 * PASO 2 DEL QUINCENAL · TUS SENSACIONES Y TUS DUDAS
 *
 * «Todo lo validado antes del 1 de septiembre», «Las tres pantallas»:
 *
 *     Sensaciones generales hasta ahora
 *     [0 · · · · · · · · · 10]
 *     0 · Muy malas, demasiado exigente para mí   10 · Genial, mejor imposible
 *
 *     ¿Cuánto te está costando?          Valoración esfuerzo / resultados
 *     [0 · · · · · · · · · 10]
 *     0 · Mal, mucho esfuerzo para pocos avances  10 · Genial, mejor imposible
 *
 *     ¿Algún ejercicio que te dé molestias o alguna máquina que no tengas?
 *     Dudas o lo que quieras contarme · Ahora es el momento y el lugar
 *     [Enviar reporte]
 *
 * DE DÓNDE VIENE ESTA PANTALLA. Era el quincenal entero en una sola página (T7 del doc
 * 16-08, «de seis preguntas a cuatro»), con el peso arriba y las sensaciones en estrellas.
 * Ahora es el segundo de tres pasos, y por eso ya no lleva ni cabecera propia -- la pone
 * `CabeceraDePasos` -- ni el peso -- que es del paso 1, con sus días --, ni el bloque de
 * huecos, que también se fue al paso 1 con los demás.
 *
 * Y LAS SENSACIONES CAMBIAN DE ESCALA, de cinco estrellas a 0-10 con los extremos escritos.
 * No es lo mismo preguntado de otra forma: cinco estrellas sin etiquetas dejaban el 3 en
 * «ni bien ni mal», y lo que él quiere saber es si el programa le está resultando
 * demasiado exigente. Los reportes viejos conservan su `sensaciones` de 1 a 5; esto es un
 * campo nuevo (`sensaciones_0a10`) y no se pisan.
 */
import React from 'react';
import { Bloque, Escala0a10, TextoLibre } from './piezas';

const ReporteQuincenal = ({ valores, set, bloques }) => {
    // Molestias solo si el servidor la pide (sin rutina no hay ejercicios por los que
    // preguntar). Sin lista, comportamiento de siempre: se pregunta.
    const conMolestias = !bloques || bloques.includes('molestias');
    // La semana que viene, solo en la cadencia semanal (doc 21-08): la manda el servidor
    // en los bloques, porque el quincenal y el mensual rápido no la llevan.
    const conSemanaProxima = !!bloques && bloques.includes('semana_proxima');

    return (
        <div className="space-y-4" data-testid="reporte-quincenal">
            {/* ── LAS DOS ESCALAS, con sus extremos escritos ── */}
            <Bloque testid="quincenal-sensaciones">
                <Escala0a10 testid="sensaciones-0a10"
                    pregunta="Sensaciones generales hasta ahora"
                    valor={valores.sensaciones_0a10}
                    onChange={(v) => set('sensaciones_0a10', v)}
                    minLabel="0 · Muy malas, demasiado exigente para mí"
                    maxLabel="10 · Genial, mejor imposible" />
            </Bloque>

            {/* «¿Cuánto te está costando?» y debajo, en pequeño, de qué va la escala: el
                esfuerzo CONTRA los resultados. Las dos líneas son suyas y dicen cosas
                distintas -- la pregunta y la unidad --, así que van las dos. */}
            <Bloque testid="quincenal-esfuerzo">
                <div>
                    <p className="text-sm text-foreground">¿Cuánto te está costando?</p>
                    <p className="text-[11px] text-muted-foreground mb-2">
                        Valoración esfuerzo / resultados
                    </p>
                    <Escala0a10 testid="esfuerzo-resultados"
                        valor={valores.esfuerzo_resultados}
                        onChange={(v) => set('esfuerzo_resultados', v)}
                        minLabel="0 · Mal, mucho esfuerzo para pocos avances"
                        maxLabel="10 · Genial, mejor imposible" />
                </div>
            </Bloque>

            {/* Molestias. Es la pregunta que hace que la rutina se pueda cambiar a tiempo.
                Solo al que tiene rutina: al resto no se le pregunta por ejercicios que no
                existen. */}
            {conMolestias && (
                <Bloque testid="quincenal-molestias">
                    <TextoLibre testid="molestias-input"
                        etiqueta="¿Algún ejercicio que te dé molestias o alguna máquina que no tengas?"
                        valor={valores.molestias} onChange={(v) => set('molestias', v)} filas={3} />
                </Bloque>
            )}

            {/* El campo libre, con su empujón: «Ahora es el momento y el lugar». Sin esa
                línea el campo se queda en blanco casi siempre. */}
            <Bloque testid="quincenal-libre">
                <div>
                    <p className="text-sm text-foreground">Dudas o lo que quieras contarme</p>
                    <p className="text-[11px] text-muted-foreground mb-2">
                        Ahora es el momento y el lugar
                    </p>
                    <TextoLibre testid="notes-textarea" valor={valores.notes}
                        onChange={(v) => set('notes', v)} filas={4} />
                </div>
            </Bloque>

            {/* La semana que viene, solo en el SEMANAL (doc 21-08). Es la pregunta que
                hace que el ajuste sirva: el feedback del domingo es para la semana que
                entra, y un viaje o un cambio de turno lo cambian todo. */}
            {conSemanaProxima && (
                <Bloque titulo="La semana que viene" testid="quincenal-semana-proxima">
                    <TextoLibre testid="semana-proxima-input"
                        etiqueta="¿Hay algo la semana que viene que te altere la rutina? Un viaje, una cena, un cambio de turno, unas vacaciones..."
                        valor={valores.semana_proxima} onChange={(v) => set('semana_proxima', v)} filas={3} />
                </Bloque>
            )}
        </div>
    );
};

export default ReporteQuincenal;
