/**
 * EL REPORTE MENSUAL (T8 del doc 16-08). Orden nuevo, y distinto por plan.
 *
 * Tres cosas cambian respecto al de antes:
 *
 *  1. EL PESO, LAS MEDIDAS Y LAS FOTOS VAN AL PRINCIPIO. Estaban debajo del botón de
 *     enviar -- las fotos, literalmente después de enviar --, así que lo que más cuesta
 *     de todo el reporte era lo último que veía, cuando ya lo había dado por terminado.
 *  2. CADA BLOQUE EMPIEZA POR EL DATO. "Este mes has registrado 25 de 28 días" y solo
 *     entonces la pregunta que no se puede deducir: "¿te ha costado seguirla?".
 *  3. NO ES EL MISMO PARA LOS TRES. Lesiones y cardio son de quien lleva entrenador
 *     detrás; el que no lleva rutina en su plan tiene en su lugar la rutina del mes.
 *
 * La numeración de los bloques la calcula el formulario, no está escrita a mano: quien
 * no lleva lesiones ni cardio tiene once bloques y su suplementación es la 06, no la 08.
 *
 * Se caen los deslizadores de sueño, energía y estrés. El sueño se pregunta ahora en el
 * cierre del día, y la energía solo se pregunta aquí si la lleva baja.
 */
import React from 'react';
import { Bloque, Dato, DosBotones, Estrellas, EstrellasMedia, Opciones, TextoLibre, enumerarFechas, kg } from './piezas';
import TresFotos from './TresFotos';
import { MEDIDAS, VIDEO_MEDIDAS, valorAnterior, diferencia } from '../../lib/medidas';
import { PESO_MIN, PESO_MAX } from '../../lib/pesoValido';

const ORANGE = '#FF671F';

// El precio de la rutina del mes para quien no la lleva en su plan. Está aquí y no
// mezclado en el texto para que se vea de un vistazo cuál es el único importe de todo
// el reporte: "una sola oferta, la rutina. Fuera menús, trimestral, CBD y FIT3D".
const PRECIO_RUTINA_DEL_MES = '57 €';

/**
 * "Cuadraste los macros 19 días y 6 te quedaste corto de proteína".
 *
 * Con cero días cuadrados la frase del doc se lee fatal ("Cuadraste los macros 0 días"),
 * así que ahí se dice lo que hay: los días que se quedó corto. Y si no hay ni una cosa ni
 * la otra no se dice nada, en vez de un cero que parece un suspenso.
 */
const fraseDeLosMacros = (dieta) => {
    const cuadrados = dieta.dias_cuadrados || 0;
    const cortos = dieta.dias_corto_proteina || 0;
    const dias = (n) => `${n} ${n === 1 ? 'día' : 'días'}`;
    if (cuadrados > 0) {
        return `Cuadraste los macros ${dias(cuadrados)}`
            + (cortos > 0 ? ` y ${cortos} te quedaste corto de proteína` : '');
    }
    if (cortos > 0) return `Te quedaste corto de proteína ${dias(cortos)}`;
    return null;
};

// Cuantos dias sin confirmar se enseñan de entrada: los demas, detras de «ver mas».
const DIAS_A_LA_VISTA = 2;

const ReporteMensual = ({ datos, perfil, bloques, valores, set, setEntreno, plazo,
                          api, token, prev }) => {
    const dieta = datos?.dieta || {};
    const entreno = datos?.entreno || {};
    const cardio = entreno.cardio || {};
    // Los días de entreno sin confirmar se enseñan de dos en dos (ver el bloque 05).
    const [verTodosLosDias, setVerTodosLosDias] = React.useState(false);
    const cierres = datos?.cierres || {};
    const peso = datos?.peso_ultimo;
    const lesiones = datos?.lesiones || [];

    // "01", "02"... en el orden que le toca a ESTE cliente.
    const numero = (clave) => {
        const i = (bloques || []).indexOf(clave);
        return i < 0 ? null : String(i + 1).padStart(2, '0');
    };
    const lleva = (clave) => (bloques || []).includes(clave);

    const medidaSet = (key, v) => set('measurements', { ...valores.measurements, [key]: v });

    return (
        <div className="space-y-4" data-testid="reporte-mensual">
            {/* ── LA CABECERA, IGUAL PARA LOS TRES ── */}
            <div>
                {plazo?.semana != null && (
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        Semana {plazo.semana} de tu ciclo
                    </p>
                )}
                <h2 className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.03em' }}>
                    Tu reporte mensual
                </h2>
                <p className="text-[15px] text-muted-foreground">Tus fotos, tus medidas y unas preguntas.</p>
                {plazo?.cierre && (
                    <p className="text-[13px] mt-1" style={{ color: ORANGE }} data-testid="mensual-plazo">
                        Hasta el {plazo.cierre}{plazo.queda ? ` · ${plazo.queda}` : ''}
                    </p>
                )}
            </div>

            {/* ── 01 · TU PESO ── */}
            <Bloque numero={numero('peso')} titulo="Tu peso" testid="mensual-peso">
                <div className="flex items-center gap-2">
                    <input
                        type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} inputMode="decimal"
                        value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                        placeholder="—" data-testid="weight-input"
                        className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                    />
                    <span className="text-lg text-foreground/40 font-bold">kg</span>
                </div>
                {peso && (
                    <p className="text-[13px] text-muted-foreground">
                        Último registro: {kg(peso.valor)}, el {peso.fecha_label}
                    </p>
                )}
            </Bloque>

            {/* ── EL % DE GRASA · solo cada 12 semanas ──
                La pantalla donde se lo pedimos la primera vez se lo promete al pie, y no
                había ningún sitio donde volviera a pedirse: el dato se quedaba con la edad
                que tuviera y con él se calculan los macros. Sale detrás del peso, que es
                cuando está mirándose los números, y solo el mes que toca. */}
            {lleva('grasa') && (
                <Bloque numero={numero('grasa')} titulo="Tu porcentaje de grasa"
                    sub="Toca repetirlo: se estima cada 12 semanas." testid="mensual-grasa">
                    <div className="flex items-center gap-2">
                        <input
                            type="number" step="0.5" min="3" max="70" inputMode="decimal"
                            value={valores.body_fat ?? ''} onChange={(e) => set('body_fat', e.target.value)}
                            placeholder="—" data-testid="body-fat-input"
                            className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                        />
                        <span className="text-lg text-foreground/40 font-bold">%</span>
                    </div>
                    {datos?.grasa?.valor != null && (
                        <p className="text-[13px] text-muted-foreground">
                            El último fue {datos.grasa.valor} %
                            {datos.grasa.semanas != null && `, hace ${datos.grasa.semanas} semanas`}.
                            Con las fotos de referencia de tu perfil.
                        </p>
                    )}
                </Bloque>
            )}

            {/* ── 02 · TUS MEDIDAS · con la del mes pasado al lado ── */}
            <Bloque numero={numero('medidas')} titulo="Tus medidas" sub="Las diez, en centímetros."
                testid="medidas">
                <p className="text-[13px] text-muted-foreground -mt-1">
                    Si te puede medir alguien, y siempre el mismo, mejor.
                </p>
                {/* El vídeo delante: lo que hace que el error de medir se repita igual cada
                    mes, que es lo que permite comparar. */}
                <details className="rounded-xl overflow-hidden border border-border">
                    <summary className="cursor-pointer select-none px-3 py-2 text-[13px] font-bold uppercase tracking-wider text-foreground/70">
                        Cómo medir los perímetros
                    </summary>
                    <div className="bg-black" style={{ aspectRatio: '16 / 9' }}>
                        <iframe src={VIDEO_MEDIDAS} title="Cómo medir los perímetros"
                            allow="fullscreen; picture-in-picture" data-testid="video-medidas"
                            className="w-full h-full border-0" />
                    </div>
                </details>

                <div className="space-y-2">
                    {MEDIDAS.map(({ key, label }) => {
                        const antes = valorAnterior(prev?.measurements, key);
                        const dif = diferencia(valores.measurements[key], antes);
                        return (
                            <div key={key} className="grid grid-cols-[1fr_5rem_4.5rem] gap-2 items-center">
                                <label className="text-sm text-foreground/80">{label}</label>
                                <input
                                    type="number" step="0.1" inputMode="decimal"
                                    value={valores.measurements[key] ?? ''}
                                    onChange={(e) => medidaSet(key, e.target.value)}
                                    placeholder="—" data-testid={`medida-${key}`}
                                    className="h-10 px-2 rounded-lg bg-muted text-center text-base font-bold outline-none focus:ring-2 focus:ring-brand"
                                />
                                {/* A la derecha, la del mes pasado, "para que sepa si va bien":
                                    en cuanto escribe, la diferencia. */}
                                <span className="text-[11px] text-right tabular-nums">
                                    {dif ? (
                                        <span className={dif.signo === 0 ? 'text-foreground/40'
                                            : dif.signo > 0 ? 'text-blue-500' : 'text-emerald-500'}>
                                            {dif.texto}
                                        </span>
                                    ) : antes != null ? (
                                        <span className="text-foreground/30">{String(antes).replace('.', ',')}</span>
                                    ) : null}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </Bloque>

            {/* ── 03 · TUS FOTOS ── */}
            <Bloque numero={numero('fotos')} titulo="Tus fotos"
                sub="De frente, de espaldas y de perfil. Relajado." testid="mensual-fotos">
                <p className="text-[13px] text-muted-foreground -mt-1">
                    Recuerda hacértelas siempre en las mismas buenas condiciones en que te hiciste las primeras.
                </p>
                <TresFotos api={api} token={token} esMensual />
            </Bloque>

            {/* ── 04 · TU DIETA · el dato primero ── */}
            <Bloque numero={numero('dieta')} titulo="Tu dieta" testid="mensual-dieta">
                {dieta.dias_periodo > 0 && (
                    <Dato testid="dato-dieta"
                        encabezado="ESTE MES HAS REGISTRADO"
                        cifra={`${dieta.dias_registrados} de ${dieta.dias_periodo} ${dieta.dias_periodo === 1 ? 'día' : 'días'}`}
                        pct={dieta.pct}
                        nota={fraseDeLosMacros(dieta)} />
                )}
                <Opciones testid="dieta-dificultad" pregunta="¿Te ha costado seguirla?"
                    valor={valores.dieta_dificultad} onChange={(v) => set('dieta_dificultad', v)}
                    columnas={2}
                    opciones={[
                        { value: 'nada', label: 'Nada, la llevo bien' },
                        { value: 'algun_dia', label: 'Algún día suelto' },
                        { value: 'bastante', label: 'Bastante' },
                        { value: 'no_he_podido', label: 'No he podido' },
                    ]} />
                <Opciones testid="viabilidad-ajuste" pregunta="¿Podrías con un ajuste nuevo?"
                    valor={valores.viabilidad_ajuste} onChange={(v) => set('viabilidad_ajuste', v)}
                    opciones={[
                        { value: 'me_adapto', label: 'Me adapto a lo que me pongas' },
                        { value: 'necesito_mas', label: 'Necesito comer más para poder cumplir' },
                        { value: 'necesito_menos', label: 'Necesito comer menos para poder cumplir' },
                    ]} />
            </Bloque>

            {/* ── 05 · TU ENTRENO · aquí es donde se separan los tres.
                Si no lleva rutina cargada, el servidor no manda este bloque: no habría ni
                dato que enseñar ni pregunta que hacer (regla 3 del doc). ── */}
            {lleva('entreno') && (
            <Bloque numero={numero('entreno')} titulo="Tu entreno" testid="mensual-entreno">
                {entreno.previstos > 0 && perfil !== 'sin_rutina' && (
                    <Dato testid="dato-entreno"
                        encabezado="ESTE MES HAS ENTRENADO"
                        cifra={`${entreno.hechos} de ${entreno.previstos} ${entreno.previstos === 1 ? 'día' : 'días'}`}
                        pct={entreno.pct} />
                )}

                {/* Quien lleva entrenador detrás no contesta nada del entreno: está
                    registrado día a día, y las sensaciones también. */}
                {perfil === 'completo' && entreno.media_estrellas != null && (
                    <p className="text-sm text-foreground flex items-center gap-2" data-testid="entreno-media">
                        Sensaciones <EstrellasMedia valor={entreno.media_estrellas} />
                        <span className="text-[13px] text-muted-foreground">media de lo que has ido marcando</span>
                    </p>
                )}

                {/* Con rutina pero sin registro diario encima: se le confirma SOLO lo que
                    falta, no se le pregunta por todo el mes. */}
                {perfil === 'con_rutina' && (
                    <>
                        {(entreno.sin_registrar || []).length > 0 && (
                            <div className="space-y-2" data-testid="entreno-confirmar">
                                <p className="text-sm text-foreground">
                                    Te faltan {entreno.sin_registrar.length} por confirmar
                                    <span className="text-muted-foreground">
                                        {' '}el {enumerarFechas(entreno.sin_registrar_labels)}
                                    </span>
                                </p>
                                {/* DE DOS EN DOS, NO EL MES ENTERO (Francisco, 17-08). El
                                    documento lo escribió pensando en dos o tres días sueltos;
                                    un cliente que no registró nada se encontraba dieciséis
                                    fechas con dos botones cada una, y eso ya no es una
                                    pregunta, es un muro. Se enseñan las dos primeras y el
                                    resto se abre si quiere. */}
                                {entreno.sin_registrar
                                    .slice(0, verTodosLosDias ? undefined : DIAS_A_LA_VISTA)
                                    .map((fecha, i) => (
                                    <div key={fecha}>
                                        <p className="text-[13px] text-muted-foreground mb-1">
                                            {entreno.sin_registrar_labels[i]}
                                        </p>
                                        <DosBotones testid={`confirmar-${fecha}`}
                                            valor={(valores.entreno.confirmacion || {})[fecha]}
                                            onChange={(v) => setEntreno('confirmacion', {
                                                ...(valores.entreno.confirmacion || {}), [fecha]: v })}
                                            opciones={[
                                                { value: 'si_no_lo_apunte', label: 'Sí entrené, no lo apunté' },
                                                { value: 'no_entrene', label: 'No entrené' },
                                            ]} />
                                    </div>
                                ))}
                                {entreno.sin_registrar.length > DIAS_A_LA_VISTA && (
                                    <button type="button" data-testid="entreno-ver-mas-dias"
                                        onClick={() => setVerTodosLosDias(!verTodosLosDias)}
                                        className="text-sm text-brand font-bold hover:underline">
                                        {verTodosLosDias
                                            ? 'Ver menos'
                                            : (entreno.sin_registrar.length - DIAS_A_LA_VISTA === 1
                                                ? 'Ver el día que falta'
                                                : `Ver los ${entreno.sin_registrar.length - DIAS_A_LA_VISTA} días que faltan`)}
                                    </button>
                                )}
                            </div>
                        )}
                        <div>
                            <p className="text-sm text-foreground mb-2">¿Qué tal el entrenamiento este mes?</p>
                            <Estrellas testid="entreno-estrellas" valor={valores.entreno.estrellas}
                                onChange={(v) => setEntreno('estrellas', v)}
                                minLabel="fatal" maxLabel="de lujo" />
                        </div>
                        <TextoLibre testid="entreno-nota" etiqueta="Lo que quieras contarme."
                            valor={valores.entreno.nota} onChange={(v) => setEntreno('nota', v)} />
                    </>
                )}

                {/* Sin rutina en su plan: se le pregunta por su regularidad, y aquí va la
                    ÚNICA oferta que queda en todo el reporte. */}
                {perfil === 'sin_rutina' && (
                    <>
                        <Opciones testid="entreno-regularidad"
                            pregunta="¿Entrenaste este mes de forma regular?"
                            valor={valores.entreno.regularidad}
                            onChange={(v) => setEntreno('regularidad', v)}
                            opciones={[
                                { value: 'a_mi_manera_sigo', label: 'Sí, a mi manera, y este mes quiero seguir así' },
                                { value: 'a_mi_manera_quiero_rutina', label: 'Sí, a mi manera, pero este mes quiero probar con una rutina tuya' },
                                { value: 'con_tu_rutina_sigo', label: 'Sí, con una rutina tuya, y quiero seguir así' },
                            ]} />

                        <div className="rounded-xl border p-3.5 space-y-3" style={{ borderColor: `${ORANGE}55` }}
                            data-testid="rutina-del-mes">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                                    Todos los meses
                                </p>
                                <p className="text-lg font-bold text-foreground">La rutina del mes</p>
                                <p className="text-[13px] text-muted-foreground mt-0.5">
                                    Por estar en Bronze la tienes en {PRECIO_RUTINA_DEL_MES}. Te llega en unos días,
                                    junto con el ajuste nuevo de tus macros.
                                </p>
                            </div>
                            <Opciones testid="rutina-mes-op" valor={valores.entreno.rutina_del_mes}
                                onChange={(v) => setEntreno('rutina_del_mes', v)}
                                opciones={[
                                    { value: 'basica', label: 'Sí · modalidad básica' },
                                    { value: 'avanzada', label: 'Sí · modalidad avanzada' },
                                    // Aplazarla una semana marcándolo (doc 19-08): no es un
                                    // «no», es un «pregúntamelo en unos días».
                                    { value: 'aplazar_una_semana', label: 'Pregúntame en una semana' },
                                    { value: 'ahora_no', label: 'Ahora no' },
                                ]} />
                            <p className="text-[13px] text-muted-foreground">
                                Al marcar «Sí» autorizas el cargo en tu tarjeta.
                            </p>
                        </div>

                        <div className="space-y-2">
                            <p className="text-sm text-foreground">¿O prefieres tenerla todos los meses?</p>
                            <p className="text-[13px] text-muted-foreground -mt-1">
                                Eso es el plan Silver. Marca aquí y te cuento cómo pasarte.
                            </p>
                            <DosBotones testid="silver"
                                valor={valores.entreno.quiere_saber_del_silver === true ? 'si'
                                    : valores.entreno.quiere_saber_del_silver === false ? 'no' : ''}
                                onChange={(v) => setEntreno('quiere_saber_del_silver',
                                    v === 'si' ? true : v === 'no' ? false : null)}
                                opciones={[
                                    { value: 'si', label: 'Cuéntame el Silver' },
                                    { value: 'no', label: 'Ahora no' },
                                ]} />
                        </div>
                    </>
                )}
            </Bloque>
            )}

            {/* ── 06 · LESIONES Y MOLESTIAS · solo quien lo lleva en su plan ── */}
            {lleva('lesiones') && (
                <Bloque numero={numero('lesiones')} titulo="Lesiones y molestias" testid="mensual-lesiones">
                    {lesiones.length > 0 && (
                        <>
                            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                                Lo que ya me contaste
                            </p>
                            {lesiones.map((l, i) => (
                                <div key={`${l.zona}-${i}`} className="rounded-xl bg-muted p-3 space-y-2">
                                    <p className="text-sm font-bold text-foreground">
                                        {l.zona}
                                        {l.desde && <span className="font-normal text-muted-foreground"> desde {l.desde}</span>}
                                    </p>
                                    <Opciones testid={`lesion-${i}`} pregunta="¿Cómo está respecto al mes pasado?"
                                        columnas={4}
                                        valor={(valores.lesiones[i] || {}).estado_mes}
                                        onChange={(v) => set('lesiones', valores.lesiones.map(
                                            (x, j) => (j === i ? { ...x, estado_mes: v } : x)))}
                                        opciones={[
                                            { value: 'peor', label: 'Peor' },
                                            { value: 'igual', label: 'Igual' },
                                            { value: 'mejor', label: 'Mejor' },
                                            { value: 'superada', label: 'Superada' },
                                        ]} />
                                    <EjerciciosVetados
                                        lista={(valores.lesiones[i] || {}).ejercicios || []}
                                        onChange={(ejercicios) => set('lesiones', valores.lesiones.map(
                                            (x, j) => (j === i ? { ...x, ejercicios } : x)))}
                                        testid={`vetados-${i}`} />
                                </div>
                            ))}
                        </>
                    )}
                    <p className="text-sm text-foreground">¿Alguna nueva?</p>
                    <DosBotones testid="lesion-nueva"
                        valor={valores.lesion_nueva_hay}
                        onChange={(v) => set('lesion_nueva_hay', v)}
                        opciones={[
                            { value: 'no', label: 'Nada nuevo' },
                            { value: 'si', label: 'Sí, te cuento' },
                        ]} />
                    {valores.lesion_nueva_hay === 'si' && (
                        <TextoLibre testid="lesion-nueva-texto"
                            ayuda="Qué es, desde cuándo y qué ejercicios no puedes hacer."
                            valor={valores.lesion_nueva} onChange={(v) => set('lesion_nueva', v)} />
                    )}
                </Bloque>
            )}

            {/* ── 07 · TU CARDIO · solo quien lo lleva en su plan ── */}
            {lleva('cardio') && (
                <Bloque numero={numero('cardio')} titulo="Tu cardio" testid="mensual-cardio">
                    {cardio.previstas > 0 && (
                        <Dato testid="dato-cardio" encabezado="ESTE MES HAS HECHO"
                            cifra={`${cardio.hechas} de ${cardio.previstas} ${cardio.previstas === 1 ? 'sesión' : 'sesiones'}`}
                            pct={cardio.pct} />
                    )}
                    {cierres.dias_movio_menos > 0 && (
                        <p className="text-[13px] text-muted-foreground">
                            Te moviste menos de lo habitual {cierres.dias_movio_menos} días de los {cierres.dias_periodo}
                        </p>
                    )}
                    <Opciones testid="cardio-proximo" pregunta="De cara al mes que viene"
                        valor={valores.cardio_proximo_mes} onChange={(v) => set('cardio_proximo_mes', v)}
                        opciones={[
                            { value: 'mismas', label: 'Puedo con las mismas sesiones' },
                            { value: 'mas', label: 'Puedo con más sesiones' },
                            { value: 'menos', label: 'Necesito menos sesiones' },
                        ]} />
                </Bloque>
            )}

            {/* ── TU SUPLEMENTACIÓN · los tres ── */}
            <Bloque numero={numero('suplementacion')} titulo="Tu suplementación" testid="mensual-suplementacion">
                <Opciones testid="suplementacion" pregunta="¿Estás tomando la que te pauté?"
                    columnas={3}
                    valor={valores.suplementacion.respuesta}
                    onChange={(v) => set('suplementacion', { ...valores.suplementacion, respuesta: v })}
                    opciones={[
                        { value: 'todos', label: 'Todos' },
                        { value: 'alguno_no', label: 'Alguno no' },
                        { value: 'ninguno', label: 'Ninguno' },
                    ]} />
                {['alguno_no', 'ninguno'].includes(valores.suplementacion.respuesta) && (
                    <TextoLibre testid="suplementacion-detalle" etiqueta="¿Cuál y por qué?"
                        ayuda="Y si quieres que te lo quite."
                        valor={valores.suplementacion.detalle}
                        onChange={(v) => set('suplementacion', { ...valores.suplementacion, detalle: v })} />
                )}
            </Bloque>

            {/* ── TU ENERGÍA · SOLO si la lleva baja. Si va bien, el bloque no aparece, y
                el servidor ya lo ha quitado de la lista para que no quede un hueco en la
                numeración ── */}
            {lleva('energia') && (
                <Bloque numero={numero('energia')} titulo="Tu energía" testid="mensual-energia">
                    <Dato testid="dato-energia" encabezado="POR TUS CIERRES DEL DÍA"
                        cifra={`Llevas ${cierres.dias_energia_baja} ${cierres.dias_energia_baja === 1 ? 'día' : 'días'} marcando la energía por debajo de 3.`} />
                    <Opciones testid="energia-motivo" pregunta="¿A qué crees que se debe?" columnas={4}
                        valor={valores.energia_motivo} onChange={(v) => set('energia_motivo', v)}
                        opciones={[
                            { value: 'duermo_poco', label: 'Duermo poco' },
                            { value: 'estres_trabajo', label: 'Estrés del trabajo' },
                            { value: 'como_poco', label: 'Como poco' },
                            { value: 'no_lo_se', label: 'No lo sé' },
                        ]} />
                </Bloque>
            )}

            {/* ── CÓMO LO VALORAS · las dos preguntas nuevas ── */}
            <Bloque numero={numero('valoracion')} titulo="Cómo lo valoras" testid="mensual-valoracion">
                <div>
                    <p className="text-sm text-foreground mb-2">
                        ¿Cómo valoras el resultado teniendo en cuenta el esfuerzo que has invertido?
                    </p>
                    <Estrellas testid="valoracion" valor={valores.valoracion_resultado}
                        onChange={(v) => set('valoracion_resultado', v)} />
                </div>
                <div>
                    <p className="text-sm text-foreground mb-2">
                        Y de cara al mes que viene, ¿cómo estás de motivación y de ganas?
                    </p>
                    <Estrellas testid="motivacion" valor={valores.motivacion}
                        onChange={(v) => set('motivacion', v)} />
                </div>
            </Bloque>

            {/* ── TU PRÓXIMO OBJETIVO · es el que dispara el cambio de fase ── */}
            <Bloque numero={numero('objetivo')} titulo="Tu próximo objetivo"
                sub="De cara a las próximas 4 semanas. Puede ser el mismo o puedes cambiar (piénsalo bien)."
                testid="mensual-objetivo">
                <Opciones testid="proximo-objetivo" columnas={3}
                    valor={valores.proximo_objetivo} onChange={(v) => set('proximo_objetivo', v)}
                    opciones={[
                        { value: 'definicion', label: 'Definición' },
                        { value: 'volumen', label: 'Volumen' },
                        { value: 'mantenimiento', label: 'Mantenimiento' },
                    ]} />
            </Bloque>

            {/* ── LO QUE QUIERAS CONTARME ── */}
            <Bloque numero={numero('libre')} titulo="Lo que quieras contarme" testid="mensual-libre">
                <TextoLibre testid="notes-textarea" etiqueta="¿Alguna dificultad o algún logro de este mes?"
                    valor={valores.notes} onChange={(v) => set('notes', v)} filas={4} />
            </Bloque>

            {/* ── SUGERENCIAS · nueva, y opcional ── */}
            <Bloque numero={numero('sugerencias')} titulo="Sugerencias" sub="Opcional."
                testid="mensual-sugerencias">
                <TextoLibre testid="sugerencias" etiqueta="¿Qué nos sugieres para mejorar la aplicación?"
                    valor={valores.sugerencias} onChange={(v) => set('sugerencias', v)} />
            </Bloque>
        </div>
    );
};

/**
 * "Ejercicios que no puedes hacer": los que ya dijo, más los que añada.
 *
 * Es la mitad útil de una lesión. Saber que le duele el hombro no cambia nada; saber que
 * no puede hacer press militar sí cambia la rutina del mes que viene.
 */
const EjerciciosVetados = ({ lista, onChange, testid }) => {
    const [nuevo, setNuevo] = React.useState('');
    const [escribiendo, setEscribiendo] = React.useState(false);

    const anadir = () => {
        const t = nuevo.trim();
        if (!t) { setEscribiendo(false); return; }
        onChange([...(lista || []), t]);
        setNuevo('');
        setEscribiendo(false);
    };

    return (
        <div data-testid={testid}>
            <p className="text-[13px] text-muted-foreground mb-1.5">Ejercicios que no puedes hacer</p>
            <div className="flex flex-wrap items-center gap-1.5">
                {(lista || []).map((e, i) => (
                    <button key={`${e}-${i}`} type="button"
                        onClick={() => onChange(lista.filter((_, j) => j !== i))}
                        className="px-2.5 py-1 rounded-lg bg-card border border-border text-[13px] text-foreground/80 hover:border-foreground/30"
                        title="Quitar">
                        {e} <span className="text-muted-foreground">×</span>
                    </button>
                ))}
                {escribiendo ? (
                    <input autoFocus value={nuevo} onChange={(e) => setNuevo(e.target.value)}
                        onBlur={anadir}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); anadir(); } }}
                        data-testid={`${testid}-input`} placeholder="Press militar"
                        className="px-2.5 py-1 rounded-lg bg-card border border-input text-[13px] text-foreground outline-none focus:border-[#FF671F]" />
                ) : (
                    <button type="button" onClick={() => setEscribiendo(true)} data-testid={`${testid}-anadir`}
                        className="px-2.5 py-1 rounded-lg border border-dashed border-border text-[13px] text-muted-foreground hover:text-foreground">
                        + añadir
                    </button>
                )}
            </div>
        </div>
    );
};

export default ReporteMensual;
