/**
 * PASO 2 DEL MENSUAL · TUS SENSACIONES Y TUS DUDAS (T8 del doc 16-08, repartido en pasos
 * por el documento «El reporte mensual» del 1-09-2026).
 *
 * Aquí vive lo que se le PREGUNTA. Lo que se le enseña está en el paso 1 y lo que se le
 * pide medir, en el paso 3.
 *
 * Las tres ideas de T8 siguen mandando dentro del paso:
 *
 *  1. CADA BLOQUE EMPIEZA POR EL DATO. "Este mes has registrado 25 de 28 días" y solo
 *     entonces la pregunta que no se puede deducir: "¿te ha costado seguirla?".
 *  2. NO ES EL MISMO PARA LOS TRES. Lesiones y cardio son de quien lleva entrenador
 *     detrás; el que no lleva rutina en su plan tiene en su lugar la rutina del mes.
 *  3. Se caen los deslizadores de sueño, energía y estrés. El sueño se pregunta en el
 *     cierre del día, y la energía solo aquí si la lleva baja.
 *
 * LOS BLOQUES YA NO VAN NUMERADOS. Los números son ahora de los cuatro pasos, y tener dos
 * numeraciones a la vez -- «paso 2» y dentro «06 Lesiones» -- es contar dos veces cosas
 * distintas. Qué bloques salen lo sigue decidiendo el servidor con `bloques`.
 */
import React from 'react';
import { Bloque, Dato, DosBotones, Estrellas, EstrellasMedia, Opciones, TextoLibre, enumerarFechas } from './piezas';

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

/**
 * «¿CUÁNTO TE HA COSTADO LA DIETA?», las cuatro del documento del 1-09.
 *
 * Cada opción lleva dentro las dos respuestas que antes se preguntaban por separado: lo
 * que le ha costado (`dieta_dificultad`) y hacia dónde tendría que ir el ajuste
 * (`viabilidad_ajuste`). Se guardan las dos, así que nada de lo que ya lee esos campos
 * -- el panel, el informe, el histórico -- se entera del cambio.
 *
 * En la primera, «me_adapto» no es un invento: quien dice que comer así le resulta
 * facilísimo se adapta a lo que le pongas, que es exactamente lo que significa ese valor.
 */
const COSTE_DE_LA_DIETA = [
    { value: 'nada', dificultad: 'nada', viabilidad: 'me_adapto',
      label: 'Nada, comiendo así es facilísimo' },
    { value: 'me_cuesta', dificultad: 'algun_dia', viabilidad: 'me_adapto',
      label: 'Me cuesta, pero no fallo. Podría adaptarme a un nuevo ajuste de macros sin problema' },
    { value: 'necesito_mas', dificultad: 'bastante', viabilidad: 'necesito_mas',
      label: 'Sí, o me pones más comida o no me veo capaz de aguantar, aún a riesgo de evolucionar más despacio' },
    { value: 'necesito_menos', dificultad: 'bastante', viabilidad: 'necesito_menos',
      label: 'Sí, baja mis macros porque no llego por mucho que me esfuerce' },
];

/** Cuál de las cuatro está marcada, leyendo los dos campos que se guardan. */
const costeDeLaDieta = (valores) => (COSTE_DE_LA_DIETA.find(
    o => o.dificultad === valores.dieta_dificultad
        && o.viabilidad === valores.viabilidad_ajuste) || {}).value || '';

/** El objetivo que tiene puesto, dicho como se dice. */
const FRASE_DEL_OBJETIVO = {
    definicion: 'Bajar mis niveles de grasa al máximo',
    volumen: 'Ganar la máxima masa muscular',
    mantenimiento: 'Mantener lo que he conseguido',
};

/**
 * LA ESCALA DE 0 A 10, con sus dos extremos escritos.
 *
 * De 0 a 10 y no de 1 a 5 con estrellas: es la de la maqueta, y el cero es una respuesta
 * («No, esperaba más»), no la ausencia de respuesta. Por eso se compara con `!= null` en
 * vez de mirar si el número es verdadero, que dejaría el cero sin poder marcarse.
 */
const Escala0a10 = ({ pregunta, valor, onChange, minLabel, maxLabel, testid }) => (
    <div data-testid={testid}>
        {pregunta && <p className="text-sm text-foreground mb-2">{pregunta}</p>}
        <div className="flex gap-1">
            {Array.from({ length: 11 }, (_, n) => {
                const puesto = valor === n;
                return (
                    <button key={n} type="button" data-testid={`${testid}-${n}`}
                        onClick={() => onChange(puesto ? null : n)}
                        className={`flex-1 min-w-0 h-9 rounded-lg border text-[13px] font-bold tabular-nums transition-all ${
                            puesto ? 'border-[#FF671F] bg-[#FF671F] text-white'
                                   : 'border-border bg-muted text-foreground/60 hover:border-foreground/30'}`}>
                        {n}
                    </button>
                );
            })}
        </div>
        <div className="flex justify-between gap-4 mt-1.5">
            <span className="text-[11px] text-muted-foreground">{minLabel}</span>
            <span className="text-[11px] text-muted-foreground text-right">{maxLabel}</span>
        </div>
    </div>
);

const ReporteMensual = ({ datos, perfil, bloques, valores, set, setEntreno }) => {
    const dieta = datos?.dieta || {};
    const entreno = datos?.entreno || {};
    const cardio = entreno.cardio || {};
    // Los días de entreno sin confirmar se enseñan de dos en dos (ver el bloque del entreno).
    const [verTodosLosDias, setVerTodosLosDias] = React.useState(false);
    const cierres = datos?.cierres || {};
    const lesiones = datos?.lesiones || [];
    // Los días que no tomó la suplementación, que es lo que decide si se le pregunta.
    // Sin el bloque de suplementos en su plan no hay `de` y no se pregunta nada.
    const suplementacion = cierres.suplementacion || {};
    const diasSinSuplementacion = suplementacion.de
        ? Math.max(0, suplementacion.de - (suplementacion.cumplidos || 0)) : 0;

    const lleva = (clave) => (bloques || []).includes(clave);

    return (
        <div className="space-y-4" data-testid="reporte-mensual">
            {/* ── TU DIETA · el dato primero ── */}
            <Bloque titulo="Tu dieta" testid="mensual-dieta">
                {dieta.dias_periodo > 0 && (
                    <Dato testid="dato-dieta"
                        encabezado="ESTE MES HAS REGISTRADO"
                        cifra={`${dieta.dias_registrados} de ${dieta.dias_periodo} ${dieta.dias_periodo === 1 ? 'día' : 'días'}`}
                        pct={dieta.pct}
                        nota={fraseDeLosMacros(dieta)} />
                )}
                {/* UNA PREGUNTA, NO DOS (documento del 1-09). Antes se preguntaba «¿te ha
                    costado seguirla?» y después «¿podrías con un ajuste nuevo?», y las dos
                    juntas se contestaban mal: el que decía «bastante» y «me adapto» dejaba
                    al entrenador sin saber si tenía que subirle o bajarle la comida.

                    Las cuatro opciones del documento llevan las dos respuestas dentro, y
                    por eso siguen guardándose los dos campos: el panel y el informe leen
                    `dieta_dificultad` y `viabilidad_ajuste`, y ninguno se entera. */}
                <Opciones testid="dieta-dificultad" pregunta="¿Cuánto te ha costado la dieta?"
                    ayuda="Lo que te ha costado a ti, no lo que hayas cumplido"
                    valor={costeDeLaDieta(valores)}
                    onChange={(v) => {
                        const o = COSTE_DE_LA_DIETA.find(x => x.value === v);
                        set('dieta_dificultad', o ? o.dificultad : '');
                        set('viabilidad_ajuste', o ? o.viabilidad : '');
                    }}
                    opciones={COSTE_DE_LA_DIETA} />
            </Bloque>

            {/* ── TU ENTRENO · aquí es donde se separan los tres.
                Si no lleva rutina cargada, el servidor no manda este bloque: no habría ni
                dato que enseñar ni pregunta que hacer (regla 3 del doc). ── */}
            {lleva('entreno') && (
            <Bloque titulo="Tu entreno" testid="mensual-entreno">
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

            {/* ── LESIONES Y MOLESTIAS · solo quien lo lleva en su plan ── */}
            {lleva('lesiones') && (
                <Bloque titulo="Lesiones y molestias" testid="mensual-lesiones">
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

            {/* ── TU CARDIO · solo quien lo lleva en su plan ── */}
            {/* SOLO SI FALLÓ SESIONES («las dos del centro solo salen si falló», doc 1-09).
                Al que las hizo todas no se le pregunta nada: ya está contestado en el paso
                1, donde lee «Cardio 12 de 12». Antes se le preguntaba igual, todos los
                meses, y la respuesta más honrada era no tocar nada. */}
            {lleva('cardio') && cardio.previstas > 0 && cardio.hechas < cardio.previstas && (
                <Bloque titulo="Tu cardio" testid="mensual-cardio">
                    <p className="text-sm text-foreground">
                        Hiciste {cardio.hechas} {cardio.hechas === 1 ? 'sesión' : 'sesiones'} de
                        cardio de las {cardio.previstas} programadas.
                    </p>
                    {cierres.dias_movio_menos > 0 && (
                        <p className="text-[13px] text-muted-foreground -mt-1">
                            Y te moviste menos de lo habitual {cierres.dias_movio_menos} días de los {cierres.dias_periodo}.
                        </p>
                    )}
                    <Opciones testid="cardio-proximo"
                        pregunta="Si te bajo el número de sesiones, ¿sería viable para que cumplieras?"
                        valor={valores.cardio_proximo_mes} onChange={(v) => set('cardio_proximo_mes', v)}
                        opciones={[
                            { value: 'mismas', label: 'No, mantenme las mismas: este mes cumplo' },
                            { value: 'menos', label: 'Sí, bájamelas y las cumplo' },
                            { value: 'quitar', label: 'Quítamelo, no lo voy a hacer' },
                        ]} />
                </Bloque>
            )}

            {/* ── TU SUPLEMENTACIÓN · los tres ── */}
            {/* LA OTRA CONDICIONAL: solo si dejó días sin tomarla. El dato sale de sus
                cierres, así que preguntarle «¿estás tomando la que te pauté?» al que la ha
                marcado 28 noches seguidas es pedirle que repita lo que ya dijo. */}
            {diasSinSuplementacion > 0 && (
                <Bloque titulo="Tu suplementación" testid="mensual-suplementacion">
                    <p className="text-sm text-foreground">
                        No tomaste la suplementación {diasSinSuplementacion}{' '}
                        {diasSinSuplementacion === 1 ? 'día' : 'días'} de
                        los {suplementacion.de}.
                    </p>
                    <Opciones testid="suplementacion"
                        ayuda="Indica el motivo y si tienes previsto tomarla el mes que viene o te la quito"
                        valor={valores.suplementacion_motivo}
                        onChange={(v) => {
                            set('suplementacion_motivo', v);
                            // El campo de siempre se sigue rellenando: el panel y el informe
                            // leen `suplementacion.respuesta`, y quien deja días sin tomarla
                            // es «alguno no» salvo que diga que la deja del todo.
                            set('suplementacion', {
                                ...valores.suplementacion,
                                respuesta: !v ? '' : v === 'no_quiero_seguir' ? 'ninguno' : 'alguno_no',
                            });
                        }}
                        opciones={[
                            { value: 'se_me_olvidaba', label: 'Se me olvidaba' },
                            { value: 'se_me_acabo', label: 'Se me acabó' },
                            { value: 'no_me_sentaba_bien', label: 'No me sentaba bien' },
                            { value: 'no_quiero_seguir', label: 'No quiero seguir tomándola' },
                        ]} />
                    {valores.suplementacion_motivo && (
                        <TextoLibre testid="suplementacion-detalle" etiqueta="¿Cuál?"
                            ayuda="Si es solo uno de ellos, dime cuál."
                            valor={valores.suplementacion.detalle}
                            onChange={(v) => set('suplementacion', { ...valores.suplementacion, detalle: v })} />
                    )}
                </Bloque>
            )}

            {/* ── TU ENERGÍA · SOLO si la lleva baja. Si va bien, el bloque no aparece, y
                el servidor ya lo ha quitado de la lista para que no quede un hueco en la
                numeración ── */}
            {lleva('energia') && (
                <Bloque titulo="Tu energía" testid="mensual-energia">
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

            {/* ── LAS MÁQUINAS QUE NO TIENE ──
                Nueva del documento del 1-09, y es la mitad que faltaba de las molestias: sin
                saber a qué gimnasio va, la rutina del mes puede salir con ejercicios que no
                puede hacer aunque no le duela nada. Sale con lo que dejó el mes pasado, para
                que solo tenga que corregir lo que haya cambiado. */}
            <Bloque titulo="¿Y máquinas que no tienes?"
                sub="Actualiza aquí tu listado: si ha entrado alguna nueva, dímelo"
                testid="mensual-maquinas">
                <ListaDeEtiquetas testid="maquinas"
                    lista={valores.maquinas_no_disponibles || []}
                    onChange={(v) => set('maquinas_no_disponibles', v)}
                    etiqueta={null} ejemplo="Prensa horizontal" anadir="+ Añadir máquina" />
            </Bloque>

            {/* ── EL COMPROMISO Y LAS EXPECTATIVAS ──
                Sustituyen a las dos estrellas de «Cómo lo valoras». No es el mismo par de
                preguntas con otra escala: la primera habla DE ÉL («si has dado todo o te
                quedas con la sensación de haber fallado») y la segunda DEL PROGRAMA. Antes
                las dos preguntaban por el resultado y por las ganas, que es otra cosa. */}
            <Bloque titulo="Cómo lo valoras" testid="mensual-valoracion">
                <Opciones testid="compromiso"
                    pregunta="¿Cómo consideras que ha sido tu grado de compromiso con el programa hasta el momento?"
                    ayuda="Ahora hablo de ti, de si has dado todo o te quedas con la sensación de haber fallado"
                    valor={valores.compromiso} onChange={(v) => set('compromiso', v)}
                    opciones={[
                        { value: 'maximo', label: 'Mi compromiso es máximo, dentro de mis posibilidades estoy dando lo mejor de mí' },
                        { value: 'bastante_bien', label: 'He cumplido bastante bien, pero podría haberlo hecho mejor' },
                        { value: 'circunstancias', label: 'Por circunstancias no he podido hacer bien las cosas, pero asumo mi responsabilidad y las próximas 4 semanas voy a por todas' },
                        { value: 'no_he_podido', label: 'No he sido capaz de llevarlo a cabo, demasiado exigente para lo que puedo dar a día de hoy' },
                    ]} />
                <Escala0a10 testid="expectativas"
                    pregunta="En líneas generales, ¿el programa está cumpliendo tus expectativas?"
                    valor={valores.expectativas} onChange={(v) => set('expectativas', v)}
                    minLabel="0 · No, esperaba más" maxLabel="10 · Genial, mejor imposible" />
            </Bloque>

            {/* ── TU OBJETIVO AHORA · es el que dispara el cambio de fase ──
                El documento le enseña primero el que tiene y solo le pregunta si ha
                cambiado. Es la regla de siempre (primero el dato, luego la pregunta) y
                además evita que cambie de fase sin querer al pasar por encima: para
                cambiarlo hay que decir «Sí» a propósito. */}
            <Bloque titulo="Tu objetivo ahora" testid="mensual-objetivo">
                {valores.objetivo_actual && (
                    <Dato testid="dato-objetivo" encabezado="TU OBJETIVO AHORA"
                        cifra={FRASE_DEL_OBJETIVO[valores.objetivo_actual] || valores.objetivo_actual} />
                )}
                <div>
                    <p className="text-sm text-foreground">¿Ha cambiado en algo respecto al mes pasado?</p>
                    <p className="text-[13px] text-muted-foreground mb-2">Si dices que sí, te pregunto cuál</p>
                </div>
                <DosBotones testid="objetivo-cambio"
                    valor={valores.objetivo_cambio}
                    onChange={(v) => {
                        set('objetivo_cambio', v);
                        // Con «No» se manda el que ya tenía: el servidor compara contra su
                        // fase y no cambia nada, pero el reporte queda diciendo cuál era.
                        set('proximo_objetivo', v === 'no' ? (valores.objetivo_actual || '') : '');
                    }}
                    opciones={[{ value: 'si', label: 'Sí' }, { value: 'no', label: 'No' }]} />
                {valores.objetivo_cambio === 'si' && (
                    <Opciones testid="proximo-objetivo" columnas={3}
                        pregunta="¿Cuál es ahora?"
                        valor={valores.proximo_objetivo} onChange={(v) => set('proximo_objetivo', v)}
                        opciones={[
                            { value: 'definicion', label: 'Definición' },
                            { value: 'volumen', label: 'Volumen' },
                            { value: 'mantenimiento', label: 'Mantenimiento' },
                        ]} />
                )}
            </Bloque>

            {/* ── DUDAS O LO QUE QUIERAS CONTARME ── */}
            <Bloque titulo="Dudas o lo que quieras contarme" testid="mensual-libre">
                <TextoLibre testid="notes-textarea" ayuda="Ahora es el momento y el lugar"
                    valor={valores.notes} onChange={(v) => set('notes', v)} filas={4} />
            </Bloque>

            {/* ── SUGERENCIAS · nueva, y opcional ── */}
            <Bloque titulo="Sugerencias" sub="Opcional."
                testid="mensual-sugerencias">
                <TextoLibre testid="sugerencias" etiqueta="¿Qué nos sugieres para mejorar la aplicación?"
                    valor={valores.sugerencias} onChange={(v) => set('sugerencias', v)} />
            </Bloque>
        </div>
    );
};

/**
 * UNA LISTA DE ETIQUETAS QUITABLES: las que ya dijo, más las que añada.
 *
 * Se usa dos veces, y las dos salen del documento del 1-09 con la misma forma: los
 * ejercicios que le dan molestias y las máquinas que no tiene. En los dos casos la lista
 * llega con lo de la última vez -- «Estos son los que me diste. Quita los que ya no y
 * añade los nuevos» -- y lo que se guarda es la lista entera, no lo que cambió.
 */
const ListaDeEtiquetas = ({ lista, onChange, testid, etiqueta, ejemplo, anadir: textoAnadir }) => {
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
            {etiqueta && <p className="text-[13px] text-muted-foreground mb-1.5">{etiqueta}</p>}
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
                        data-testid={`${testid}-input`} placeholder={ejemplo}
                        className="px-2.5 py-1 rounded-lg bg-card border border-input text-[13px] text-foreground outline-none focus:border-[#FF671F]" />
                ) : (
                    <button type="button" onClick={() => setEscribiendo(true)} data-testid={`${testid}-anadir`}
                        className="px-2.5 py-1 rounded-lg border border-dashed border-border text-[13px] text-muted-foreground hover:text-foreground">
                        {textoAnadir}
                    </button>
                )}
            </div>
        </div>
    );
};

/**
 * "Ejercicios que te dan molestias": los que ya dijo, más los que añada.
 *
 * Es la mitad útil de una lesión. Saber que le duele el hombro no cambia nada; saber que
 * no puede hacer press militar sí cambia la rutina del mes que viene.
 */
const EjerciciosVetados = ({ lista, onChange, testid }) => (
    <ListaDeEtiquetas lista={lista} onChange={onChange} testid={testid}
        etiqueta="Estos son los que me diste. Quita los que ya no y añade los nuevos"
        ejemplo="Press militar" anadir="+ Añadir ejercicio" />
);

export default ReporteMensual;
