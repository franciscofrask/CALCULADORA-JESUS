/**
 * EL REPORTE QUINCENAL (T7 del doc 16-08): de seis preguntas a cuatro.
 *
 * "Cuatro preguntas: el resto ya lo ha marcado cada día." Se caen «¿has seguido la
 * dieta?», «¿has cumplido el cardio?» y «¿tomas la suplementación?», que es justo lo que
 * el cliente marca en el cierre del día: preguntárselo otra vez cada dos semanas es
 * pedirle que se puntúe sobre algo que la app ya sabe.
 *
 * Lo único que la app no puede saber va aquí: el peso, si algún ejercicio le da
 * molestias, cómo se ha sentido y lo que quiera contar.
 *
 * Antes de las cuatro va el bloque de los huecos: los días de rutina que no registró.
 * No es una pregunta de cumplimiento -- es la diferencia entre no entrenar y entrenar
 * sin apuntarlo --, y de ahí sale el porcentaje que ve su entrenador.
 */
import React from 'react';
import { Bloque, DosBotones, Estrellas, TextoLibre, kg } from './piezas';
import { PESO_MIN, PESO_MAX } from '../../lib/pesoValido';

// Sin título por defecto (tarea 1.6): el default «Tu reporte quincenal» tapaba al que
// llamara sin pasarlo, y este formulario también sirve la cadencia semanal. El título
// lo decide siempre quien conoce el tipo (FormularioReporte, con TITULOS_REPORTE).
const ReporteQuincenal = ({ datos, valores, set, plazo, titulo, bloques }) => {
    const entreno = datos?.entreno || {};
    const sinRegistrar = (entreno.sin_registrar || []).length;
    const peso = datos?.peso_ultimo;
    // Molestias solo si el servidor la pide (sin rutina no hay ejercicios por los que
    // preguntar). Sin lista, comportamiento de siempre: se pregunta.
    const conMolestias = !bloques || bloques.includes('molestias');
    // La semana que viene, solo en la cadencia semanal (doc 21-08): la manda el servidor
    // en los bloques, porque el quincenal y el mensual rápido no la llevan.
    const conSemanaProxima = !!bloques && bloques.includes('semana_proxima');

    return (
        <div className="space-y-4" data-testid="reporte-quincenal">
            {/* La cabecera: dónde está y hasta cuándo. El plazo, en hora de España. */}
            <div>
                {plazo?.semana != null && (
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        Semana {plazo.semana}{plazo?.cierre ? ` · hasta el ${plazo.cierre}` : ''}
                    </p>
                )}
                <h2 className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.03em' }}>
                    {titulo}
                </h2>
            </div>

            {/* ANTES DE RELLENAR · los días de rutina que la app no tiene.
                Solo sale si hay huecos: al que lo registró todo no se le pregunta nada. */}
            {entreno.previstos && sinRegistrar > 0 && (
                <Bloque titulo="ANTES DE RELLENAR" testid="quincenal-huecos">
                    <p className="text-sm text-foreground">
                        No registraste el entreno {sinRegistrar} {sinRegistrar === 1 ? 'día' : 'días'} de
                        los {entreno.previstos} que tenías.
                    </p>
                    <DosBotones testid="quincenal-huecos-op"
                        valor={valores.entreno_huecos}
                        onChange={(v) => set('entreno_huecos', v)}
                        opciones={[
                            { value: 'no_entrene', label: 'No entrené' },
                            { value: 'si_no_lo_apunte', label: 'Sí entrené, no lo apunté' },
                        ]} />
                </Bloque>
            )}

            {/* 1 · Peso. El único obligatorio de los cuatro. */}
            <Bloque numero="1" titulo="Peso" sub="Obligatorio" testid="quincenal-peso">
                {peso && (
                    <p className="text-[13px] text-muted-foreground -mt-1">
                        Último registro: {kg(peso.valor)}, el {peso.fecha_label}
                    </p>
                )}
                <div className="flex items-center gap-2">
                    <input
                        type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} inputMode="decimal"
                        value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                        placeholder="—" data-testid="weight-input"
                        className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                    />
                    <span className="text-lg text-foreground/40 font-bold">kg</span>
                </div>
            </Bloque>

            {/* 2 · Molestias. Es la pregunta que hace que la rutina se pueda cambiar a
                tiempo. Solo al que tiene rutina: al resto no se le pregunta por
                ejercicios que no existen. */}
            {conMolestias && (
                <Bloque numero="2" titulo="Molestias" testid="quincenal-molestias">
                    <TextoLibre testid="molestias-input"
                        etiqueta="¿Algún ejercicio de la rutina te da molestias o te falta alguna máquina?"
                        valor={valores.molestias} onChange={(v) => set('molestias', v)} filas={3} />
                </Bloque>
            )}

            {/* Sensaciones, con estrellas. */}
            <Bloque numero={conMolestias ? '3' : '2'} titulo="Sensaciones" testid="quincenal-sensaciones">
                <Estrellas testid="sensaciones" valor={valores.sensaciones}
                    onChange={(v) => set('sensaciones', v)}
                    minLabel="fatal" maxLabel="de lujo" />
            </Bloque>

            {/* Libre. */}
            <Bloque numero={conMolestias ? '4' : '3'} titulo="Y lo que quieras contarme." testid="quincenal-libre">
                <TextoLibre testid="notes-textarea" valor={valores.notes}
                    onChange={(v) => set('notes', v)} filas={4} />
            </Bloque>

            {/* La semana que viene, solo en el SEMANAL (doc 21-08). Es la pregunta que
                hace que el ajuste sirva: el feedback del domingo es para la semana que
                entra, y un viaje o un cambio de turno lo cambian todo. */}
            {conSemanaProxima && (
                <Bloque numero={conMolestias ? '5' : '4'} titulo="La semana que viene" testid="quincenal-semana-proxima">
                    <TextoLibre testid="semana-proxima-input"
                        etiqueta="¿Hay algo la semana que viene que te altere la rutina? Un viaje, una cena, un cambio de turno, unas vacaciones..."
                        valor={valores.semana_proxima} onChange={(v) => set('semana_proxima', v)} filas={3} />
                </Bloque>
            )}
            {/* Y no hay nada más. Lo que se cayó (dieta, cardio y suplementación) no se
                sustituye por una explicación: se cayó porque ya está marcado cada día. */}
        </div>
    );
};

export default ReporteQuincenal;
