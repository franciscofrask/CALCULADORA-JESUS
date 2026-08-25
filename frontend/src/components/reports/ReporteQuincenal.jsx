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
    // El peso de la semana, ya calculado por el servidor con la cascada del punto 34: la
    // pareja de días seguidos desde el miércoles, y si no la hay, la media de la semana, y
    // si tampoco, el último peso conocido. Aquí solo se pinta.
    const semanal = datos?.peso_semanal;
    // SOLO SE ESCRIBE EN EL CAMPO EL PESO DE ESTA SEMANA (ramas a y b de la cascada).
    //
    // Lo que se manda en el reporte se archiva en la serie CON LA FECHA DE HOY
    // (`routes/reports.py`, `anotar_peso(..., dia_reporte, pisa_pesajes=False)`), y eso con
    // la media es lo que Jesús pide -- «ese será tu peso semanal, lo que debes registrar
    // semana a semana» --, pero con la rama c sería inventarse un pesaje: el que no se pesó
    // en toda la semana enviaría de un toque su peso de hace nueve días como si se hubiera
    // pesado hoy, la curva se quedaría plana con un punto que no existió y su entrenador le
    // ajustaría los macros con un peso viejo creyéndolo de hoy. En ese caso el número no se
    // pone y la línea de debajo le dice cuál fue el último y de cuándo, que es lo que hacía
    // antes.
    //
    // OJO CON EL `pisa_pesajes=False` DE AHÍ (fallo 5 del repaso del 24-08): el servidor ya
    // no deja que el reporte borre un pesaje de verdad de ese día, pero ESO NO SUSTITUYE A
    // ESTA REGLA. En la rama c justamente no hay pesaje de esta semana, así que el día está
    // libre y el número SÍ entraría en la serie: quien lo tiene que dejar fuera es esto.
    const mediaPuesta = semanal?.de_esta_semana ? semanal.valor : undefined;
    // Molestias solo si el servidor la pide (sin rutina no hay ejercicios por los que
    // preguntar). Sin lista, comportamiento de siempre: se pregunta.
    const conMolestias = !bloques || bloques.includes('molestias');
    // La semana que viene, solo en la cadencia semanal (doc 21-08): la manda el servidor
    // en los bloques, porque el quincenal y el mensual rápido no la llevan.
    const conSemanaProxima = !!bloques && bloques.includes('semana_proxima');

    // LA MEDIA VA YA PUESTA, PERO EL CAMPO SIGUE EDITABLE (decisión de Jesús, 24-08): si el
    // cliente lo cambia, manda lo que él escriba. Solo se rellena si está vacío, y las
    // dependencias son la media y no `valores.weight`, para no pisarle lo que teclea ni
    // volver a ponerlo cuando borra el campo a propósito.
    React.useEffect(() => {
        if (mediaPuesta != null && (valores.weight === '' || valores.weight == null)) {
            set('weight', String(mediaPuesta));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mediaPuesta]);

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
                {/* CON EL CAMPO VACÍO, LA PISTA VA ARRIBA, que es donde estaba siempre: se
                    lee antes de escribir, porque es lo que ayuda a escribir. Si el servidor
                    manda el peso de la semana (aunque no sea de esta semana y por eso no se
                    haya puesto en el campo), esa frase dice más que «Último registro», así
                    que gana ella y la de siempre no sale: dos líneas diciendo lo mismo con
                    otras palabras es peor que una.

                    Y DICE LOS KILOS (fallo 6 del repaso del 24-08). Esto sólo se sostiene
                    porque la frase de la rama «último» los lleva dentro
                    (`de_donde_sale_el_peso`, en core/datos_reporte.py): con el campo vacío
                    y una frase sin número, al que no se pesó esta semana se le pedía el
                    peso sin recordarle cuál era el suyo. Si algún día se quita el kilo de
                    esa frase, esta línea deja de valer y hay que volver a sacar
                    «Último registro» debajo. */}
                {mediaPuesta == null && (semanal?.de_donde ? (
                    <p className="text-[13px] text-muted-foreground -mt-1" data-testid="peso-de-donde">
                        {semanal.de_donde}
                    </p>
                ) : peso && (
                    <p className="text-[13px] text-muted-foreground -mt-1">
                        Último registro: {kg(peso.valor)}, el {peso.fecha_label}
                    </p>
                ))}
                <div className="flex items-center gap-2">
                    <input
                        type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} inputMode="decimal"
                        value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                        placeholder="—" data-testid="weight-input"
                        className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                    />
                    <span className="text-lg text-foreground/40 font-bold">kg</span>
                </div>
                {/* De dónde sale el número que ya está escrito. Debajo del campo a
                    propósito: se lee después de ver el kilo, que es cuando surge la duda. */}
                {mediaPuesta != null && semanal?.de_donde && (
                    <p className="text-[13px] text-muted-foreground" data-testid="peso-de-donde">
                        {semanal.de_donde}
                    </p>
                )}
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
