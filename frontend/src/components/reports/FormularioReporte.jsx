/**
 * EL FORMULARIO DEL REPORTE: el quincenal y el mensual, que ya no son el mismo.
 *
 * Hasta el doc del 16-08 había UN formulario y lo único que cambiaba entre uno y otro
 * eran las medidas. Son dos cuestionarios distintos (T7 y T8) y el mensual además no es
 * igual para los tres planes, así que aquí solo vive lo común: traer lo que la app ya
 * sabe, guardar lo que el cliente contesta, revisarlo antes de mandarlo y decirle qué
 * pasa ahora.
 *
 * Qué bloques lleva cada uno NO se decide aquí: lo dice el servidor en
 * `GET /reports/formulario`, leyendo las habilitaciones de su plan. El plan es un dato,
 * nunca un nombre.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Send } from 'lucide-react';
import ReporteQuincenal from './ReporteQuincenal';
import ReporteMensual from './ReporteMensual';
import MensualPaso1 from './MensualPaso1';
import MensualPaso3 from './MensualPaso3';
import MensualPaso4 from './MensualPaso4';
import QuincenalPaso1 from './QuincenalPaso1';
import QuincenalPaso3 from './QuincenalPaso3';
import {
    CabeceraDelMensual, CabeceraDePasos, RotuloDelPaso,
    PASOS_DEL_QUINCENAL, ROTULOS_DEL_QUINCENAL,
} from './PasosDelMensual';
import RevisaAntesDeEnviar from './RevisaAntesDeEnviar';
import { MEDIDAS } from '../../lib/medidas';
import { revisarPeso } from '../../lib/pesoValido';
import { useConfirm } from '../ui/confirm';
import { mensajeDeError } from '../../lib/mensajeDeError';

const ORANGE = '#FF671F';

// El título por cadencia (tarea 1.6). Antes era un ternario binario: todo lo que no era
// mensual se rotulaba «Tu reporte quincenal», y al de cadencia semanal el aviso le decía
// «semanal» y el formulario «quincenal». El tipo lo manda el servidor; si llega uno que
// no está aquí, se dice «Tu reporte» a secas antes que ponerle una cadencia inventada.
const TITULOS_REPORTE = {
    semanal: 'Tu reporte semanal',
    quincenal: 'Tu reporte quincenal',
    mensual: 'Tu reporte mensual',
};

// El de la CABECERA DE LOS PASOS, sin el «Tu» (doc 1-09: «Reporte quincenal», igual que
// «Reporte mensual»). Ahí el título va en versalitas y grande, y el posesivo delante de una
// palabra en mayúsculas se lee como un error de maquetación, no como cercanía.
const TITULOS_EN_LA_CABECERA = {
    semanal: 'Reporte semanal',
    quincenal: 'Reporte quincenal',
    mensual: 'Reporte mensual',
};

const valoresIniciales = (objetivoActual) => ({
    weight: '',
    // El % de grasa solo sale en el reporte que toca, cada 12 semanas.
    body_fat: '',
    measurements: Object.fromEntries(MEDIDAS.map(m => [m.key, ''])),
    // Quincenal
    entreno_huecos: '',
    molestias: '',
    sensaciones: null,
    // Las dos escalas de 0 a 10 del paso 2 (doc 1-09). No sustituyen a `sensaciones`, que
    // son las cinco estrellas de los reportes de antes: son otra pregunta y otra escala.
    sensaciones_0a10: null,
    esfuerzo_resultados: null,
    // Y las cinco estrellas del paso 1 cuando no hay check-in con los que llenarlo.
    dieta_grado: null,
    entreno_grado: null,
    cardio_grado: null,
    suplementacion_grado: null,
    descanso_grado: null,
    // Semanal (doc 21-08): qué le altera la rutina la semana que viene.
    semana_proxima: '',
    // Mensual · los huecos del paso 1, que es lo único que se contesta ahí.
    huecos_paso1: {},
    dieta_dificultad: '',
    viabilidad_ajuste: '',
    entreno: { confirmacion: {}, estrellas: null, nota: '', regularidad: '',
               rutina_del_mes: '', quiere_saber_del_silver: null },
    // `lesiones` se queda en el estado aunque ya no se pregunte: los reportes viejos se
    // leen con ella. Lo que se contesta desde el 3-09 es `ejercicios_molestos`.
    lesiones: [],
    lesion_nueva_hay: '',
    lesion_nueva: '',
    ejercicios_molestos: [],
    cardio_proximo_mes: '',
    suplementacion: { respuesta: '', detalle: '' },
    // El motivo de no haberla tomado, que solo se pregunta si dejó días (doc 1-09).
    suplementacion_motivo: '',
    energia_motivo: '',
    valoracion_resultado: null,
    motivacion: null,
    // Las del documento del 1-09: el compromiso (habla de él), las expectativas de 0 a 10
    // y las máquinas que no tiene. `objetivo_cambio` no viaja: solo decide si se le
    // pregunta cuál es el nuevo objetivo.
    compromiso: '',
    expectativas: null,
    maquinas_no_disponibles: [],
    objetivo_cambio: '',
    proximo_objetivo: '',
    notes: '',
    sugerencias: '',
    // Para el resumen: cuántas fotos hay subidas y con qué objetivo venía, para poder
    // decir "no cambia" sin preguntárselo otra vez.
    fotos_puestas: 0,
    objetivo_actual: objetivoActual || '',
});

const FormularioReporte = ({ api, token, tipoRevision, windowState, prev, perfilCliente,
                            onEnviado, onVerInforme }) => {
    const { confirm } = useConfirm();
    const [cargando, setCargando] = useState(true);
    const [ficha, setFicha] = useState(null);          // lo que manda el servidor
    const [valores, setValores] = useState(() => valoresIniciales(perfilCliente?.goal));
    const [paso, setPaso] = useState('form');          // form | resumen | enviado
    // LOS DOS VAN POR PASOS, y son los mismos primeros dos.
    //
    //   MENSUAL (doc «El reporte mensual», 1-09): 1 sus datos, 2 sus respuestas, 3 fotos y
    //   medidas, y el 4 es la entrega, que solo se ve después de mandarlo.
    //   QUINCENAL («Todo lo validado antes del 1 de septiembre»): 1 sus datos, 2 sus
    //   sensaciones y dudas, y el 3 es la respuesta, también después de mandarlo.
    //
    // Un solo contador para los dos: son la misma máquina y lo único que cambia es cuántos
    // pasos hay y qué se pinta en cada uno.
    const [pasoMensual, setPasoMensual] = useState(1);
    // El informe, si de verdad está publicado, para el paso 4. Sin esto la pantalla le
    // diría «ya lo tienes» sin nada que abrir.
    const [informeListo, setInformeListo] = useState(null);
    const [promesaDia, setPromesaDia] = useState(null);
    const [enviando, setEnviando] = useState(false);
    const [aplazado, setAplazado] = useState(false);
    // El aplazamiento en dos pasos (doc 19-08): «No puedo esta semana» abre la línea
    // opcional de «¿Quieres decirme algo?». Con ?aplazar=1 llega ya abierto: es el
    // camino desde el botón del aviso.
    const [pidiendoAplazar, setPidiendoAplazar] = useState(() =>
        new URLSearchParams(window.location.search).get('aplazar') === '1');
    const [notaAplazar, setNotaAplazar] = useState('');

    const set = (campo, valor) => setValores(v => ({ ...v, [campo]: valor }));
    const setEntreno = (campo, valor) => setValores(v => ({ ...v, entreno: { ...v.entreno, [campo]: valor } }));

    const cargar = useCallback(async () => {
        try {
            const r = await api.get('/reports/formulario', {
                params: tipoRevision ? { tipo: tipoRevision } : {},
            });
            setFicha(r.data);
            setAplazado(!!r.data?.aplazado_hasta);
            // Las lesiones abiertas entran ya en el estado: lo que se contesta es su
            // estado de este mes, no volver a escribirlas.
            const abiertas = (r.data?.datos?.lesiones || []).map(l => ({
                zona: l.zona, desde: l.desde, estado_mes: '',
                ejercicios: l.ejercicios_vetados || [],
            }));
            // EL PESO, YA PUESTO, PARA PODER CONFIRMARLO (paso 1 del doc del 1-09:
            // «Actualizar tus datos y confirmar que están bien»). El peso de la semana ya
            // lo calcula el servidor; si el cliente no lo toca, confirma ese.
            //
            // Menos en la rama «ultimo», donde la casilla se deja vacía A PROPÓSITO (punto
            // 34 del doc del 24-08): ese peso no es de esta semana, así que rellenarlo
            // sería darle por bueno un número viejo sin que nadie lo mire.
            const ps = r.data?.datos?.peso_semanal;
            const puesto = ps && ps.regla !== 'ultimo' && ps.valor != null
                ? String(ps.valor).replace('.', ',') : '';
            // Y las máquinas que no tiene, con lo que dejó la última vez: el documento dice
            // «actualiza aquí tu listado», y para eso el listado tiene que estar.
            const maquinas = r.data?.datos?.maquinas || [];
            // Y los ejercicios que le molestan, por lo mismo: «estos son los que me diste,
            // quita los que ya no». Vienen de `injuries`, con lo que dejó dentro de sus
            // lesiones abiertas sumado, para que la primera vez no le salga en blanco.
            const molestias = r.data?.datos?.ejercicios_molestos || [];
            setValores(v => ({ ...v, lesiones: abiertas, weight: v.weight || puesto,
                               maquinas_no_disponibles: maquinas,
                               ejercicios_molestos: molestias }));
        } catch (e) {
            console.error('No se pudo cargar el formulario del reporte', e);
            toast.error('No hemos podido preparar tu reporte. Inténtalo en un momento.');
        } finally {
            setCargando(false);
        }
    }, [api, tipoRevision]);

    useEffect(() => { cargar(); }, [cargar]);

    // «El rápido, mensual» (doc 19-08): en la Calculadora (y ELM) el mensual va con el
    // formulario corto. La cadencia la decide el servidor; aquí solo se elige pantalla.
    const esMensual = ficha?.tipo === 'mensual' && ficha?.forma !== 'rapido';
    const bloques = ficha?.bloques || [];

    // El plazo, en hora de España y con lo que queda. Lo calcula quien nos llama
    // (la pantalla ya lo tenía resuelto) y aquí solo se pinta.
    const plazo = {
        semana: windowState?.cycle?.week ?? windowState?.semana ?? null,
        cierre: windowState?.plazoLabel || null,
        queda: windowState?.quedaLabel || null,
    };

    const aplazar = async (nota) => {
        try {
            const r = await api.post('/reports/aplazar', nota ? { nota } : {});
            setAplazado(true);
            setPidiendoAplazar(false);
            toast.success(r.data?.titulo || 'Te lo he aplazado 7 días', {
                description: r.data?.mensaje, duration: 8000,
            });
        } catch (e) {
            console.error('No se pudo aplazar el reporte', e);
            toast.error(mensajeDeError(e, 'No hemos podido aplazártelo. Inténtalo en un momento.'));
        }
    };

    /** El peso: obligatorio, dentro de rango y sin saltos raros sin confirmar. */
    const revisarElPeso = async () => {
        if (!valores.weight) { toast.error('El peso es obligatorio'); return false; }
        const chequeo = revisarPeso(valores.weight, prev?.weight);
        if (!chequeo.ok) { toast.error(chequeo.error); return false; }
        if (chequeo.confirmar && !await confirm({
            title: 'Confírmame el peso',
            description: chequeo.confirmar,
            confirmLabel: 'Sí, es correcto', cancelLabel: 'Lo corrijo',
        })) return false;
        return true;
    };

    /** Las diez medidas, y van todas: media tabla no se puede comparar con el mes pasado. */
    const revisarLasMedidas = () => {
        const faltan = MEDIDAS.filter(m => !valores.measurements[m.key]);
        if (!faltan.length) return true;
        toast.error(faltan.length === 1
            ? `Te falta una medida: ${faltan[0].label.toLowerCase()}`
            : `Te faltan ${faltan.length} medidas, y van todas: empieza por ${faltan[0].label.toLowerCase()}`);
        return false;
    };

    /** Lo que no se puede mandar a medias. Devuelve true si se puede seguir. */
    const revisar = async () => {
        if (!await revisarElPeso()) return false;
        return esMensual ? revisarLasMedidas() : true;
    };

    /** Del formulario al resumen: se cuentan las fotos para poder decir "las tres". */
    const irAlResumen = async () => {
        if (!await revisar()) return;
        try {
            const r = await api.get('/reports/photos');
            const desde = ficha?.datos?.periodo?.desde || '';
            const poses = new Set((r.data?.photos || [])
                .filter(f => String(f.taken_at || '').slice(0, 10) >= desde)
                .map(f => f.pose));
            set('fotos_puestas', poses.size);
        } catch { /* si no se pueden contar, el resumen lo dice como "sin poner" */ }
        setPaso('resumen');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const enviar = async () => {
        if (paso === 'form' && !await revisar()) return;
        setEnviando(true);
        try {
            const payload = {
                tipo: ficha?.tipo,
                weight: parseFloat(String(valores.weight).replace(',', '.')),
                // Solo viaja el mes que toca (cada 12 semanas): el resto no se le pregunta,
                // así que va a null y el servidor no toca su serie.
                body_fat: valores.body_fat
                    ? parseFloat(String(valores.body_fat).replace(',', '.')) : null,
                measurements: Object.fromEntries(
                    Object.entries(valores.measurements).filter(([, v]) => v)
                        .map(([k, v]) => [k, parseFloat(String(v).replace(',', '.'))])),
                // El cumplimiento del entreno lo sigue calculando el servidor con esto:
                // la diferencia entre no entrenar y entrenar sin apuntarlo.
                huecos: huecosParaElServidor(ficha, valores),
                molestias: valores.molestias || null,
                sensaciones: valores.sensaciones,
                // Solo la rellena el semanal; en el resto ni se pregunta y viaja a null.
                semana_proxima: valores.semana_proxima || null,
                dieta_dificultad: valores.dieta_dificultad || null,
                viabilidad_ajuste: valores.viabilidad_ajuste || null,
                entreno: esMensual ? limpiarEntreno(valores.entreno) : null,
                lesiones: bloques.includes('lesiones')
                    ? valores.lesiones.filter(l => l.zona).map(l => ({
                        zona: l.zona, desde: l.desde || null,
                        estado_mes: l.estado_mes || null, ejercicios: l.ejercicios || [] }))
                    : null,
                lesion_nueva: valores.lesion_nueva_hay === 'si' ? (valores.lesion_nueva || null) : null,
                // La pregunta 5 del doc del 1-09. Va con el mismo candado que las lesiones:
                // solo la contesta quien lleva ese bloque en su plan.
                ejercicios_molestos: bloques.includes('lesiones')
                    ? (valores.ejercicios_molestos || []) : null,
                cardio_proximo_mes: valores.cardio_proximo_mes || null,
                suplementacion: valores.suplementacion.respuesta
                    ? { respuesta: valores.suplementacion.respuesta,
                        detalle: valores.suplementacion.detalle || null }
                    : null,
                suplementacion_motivo: valores.suplementacion_motivo || null,
                energia_motivo: valores.energia_motivo || null,
                valoracion_resultado: valores.valoracion_resultado,
                motivacion: valores.motivacion,
                // Las tres del documento del 1-09. Las máquinas viajan aunque la lista esté
                // vacía: vaciarla es una respuesta («ya no me falta ninguna») y mandarla a
                // null dejaría en el perfil las del mes pasado.
                compromiso: valores.compromiso || null,
                expectativas: valores.expectativas,
                maquinas_no_disponibles: esMensual ? (valores.maquinas_no_disponibles || []) : null,
                proximo_objetivo: valores.proximo_objetivo || null,
                notes: valores.notes || null,
                sugerencias: valores.sugerencias || null,
                // Las del quincenal de tres pasos (doc 1-09): las dos escalas del paso 2 y,
                // sólo cuando no había check-in que enseñar, las cinco del paso 1.
                sensaciones_0a10: valores.sensaciones_0a10,
                esfuerzo_resultados: valores.esfuerzo_resultados,
                dieta_grado: valores.dieta_grado,
                entreno_grado: valores.entreno_grado,
                cardio_grado: valores.cardio_grado,
                suplementacion_grado: valores.suplementacion_grado,
                descanso_grado: valores.descanso_grado,
            };
            const r = await api.post('/reports', payload);
            // El `mensaje_envio` del servidor ya no se pinta: los dos últimos pasos -- el 3
            // del quincenal y el 4 del mensual -- dicen lo mismo con más detalle y con la
            // hora dentro. El servidor lo sigue mandando y se usa en otros sitios.
            setPromesaDia(r.data?.promesa_dia || null);
            // ¿Le sale ya su informe? El paso 4 se lo ofrece SOLO si de verdad puede
            // abrirlo: mientras esté pendiente de revisión, el servidor se lo niega (T9),
            // y una tarjeta que dice «ya lo tienes» sin nada detrás es peor que no ponerla.
            if (esMensual && r.data?.id) {
                try {
                    await api.get(`/reports/${r.data.id}/informe`);
                    setInformeListo(r.data.id);
                } catch { setInformeListo(null); }
            }
            setPaso('enviado');
            window.scrollTo({ top: 0, behavior: 'smooth' });
            if (onEnviado) onEnviado();
        } catch (error) {
            console.error('Error al enviar el reporte', error);
            toast.error(mensajeDeError(error, 'No hemos podido enviar tu reporte. Inténtalo en un momento.'));
        } finally {
            setEnviando(false);
        }
    };

    if (cargando) {
        return (
            <div className="animate-pulse space-y-3">
                <div className="h-6 bg-muted rounded w-1/2" />
                <div className="h-40 bg-card rounded-2xl" />
                <div className="h-40 bg-card rounded-2xl" />
            </div>
        );
    }
    if (!ficha) return null;

    // ── Enviado. Lo que pasa ahora, con fecha: "antes del viernes", no "en breve" ──
    //
    // En el mensual eso ya no es una tarjeta: es el PASO 4, «Entregarte el plan nuevo con
    // el informe y darte feedback», que es el paso que justifica los otros tres.
    if (paso === 'enviado') {
        if (esMensual) {
            return (
                <MensualPaso4 plazo={plazo} promesaDia={promesaDia}
                    informeId={informeListo} onVerInforme={onVerInforme} />
            );
        }
        // Y en el quincenal, el PASO 3: «Este tercer paso es cosa nuestra». Era una tarjeta
        // de «Reporte enviado» con una línea; ahora es el paso que sale anunciado desde la
        // primera pantalla, y le da una hora en vez de un «en breve».
        return (
            <QuincenalPaso3 plazo={plazo} promesaDia={promesaDia}
                titulo={TITULOS_EN_LA_CABECERA[ficha?.tipo] || 'Reporte'} />
        );
    }

    if (paso === 'resumen') {
        return (
            <RevisaAntesDeEnviar
                valores={valores} datos={ficha.datos} bloques={bloques} perfil={ficha.perfil}
                prev={prev} enviando={enviando}
                onVolver={() => { setPaso('form'); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
                onEnviar={enviar} />
        );
    }

    /** Del paso 1 al 2: lo que se confirma ahí es el peso, así que se revisa ahí. */
    const confirmarPaso1 = async () => {
        if (!await revisarElPeso()) return;
        setPasoMensual(2);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    const irAPaso = (n) => { setPasoMensual(n); window.scrollTo({ top: 0, behavior: 'smooth' }); };

    // «No puedo esta semana» sale UNA vez, no en cada paso: es una decisión sobre el
    // reporte entero, y repetirla tres veces la convierte en una salida a mano.
    const bloqueAplazar = (
        <>
            {/* ── «NO PUEDO ESTA SEMANA», ABAJO (doc 19-08) ── En los dos reportes. Lo
                pide él y se le concede: no depende de que no conteste un correo. Al
                pulsarlo, la línea opcional de «¿Quieres decirme algo?», que es lo que su
                entrenador verá junto al aplazamiento en el panel. */}
            {aplazado ? (
                <div data-testid="aplazar"
                    className="w-full rounded-2xl p-4 border text-sm border-green-500/40 bg-green-500/5 text-foreground">
                    {/* Sin día de la semana: el quincenal cierra en jueves y el mensual
                        en lunes, y esto sale en los dos (P44 del 23-08). Y en plural. */}
                    Te lo hemos aplazado 7 días: tu reporte se vuelve a abrir la semana que viene, el mismo día de siempre. Sigue registrando como hasta ahora.
                </div>
            ) : !pidiendoAplazar ? (
                <button type="button" onClick={() => setPidiendoAplazar(true)} data-testid="aplazar"
                    className="w-full text-center rounded-2xl p-3 border text-sm transition-colors border-border bg-card text-foreground/70 hover:border-foreground/30">
                    No puedo esta semana
                </button>
            ) : (
                <div className="w-full rounded-2xl p-4 border border-border bg-card space-y-3" data-testid="aplazar-confirmar">
                    <p className="text-sm text-foreground/80">Te lo aplazo 7 días. ¿Quieres decirme algo? <span className="text-muted-foreground">(opcional)</span></p>
                    <textarea value={notaAplazar} onChange={(e) => setNotaAplazar(e.target.value)}
                        rows={2} maxLength={500} placeholder="Estoy de viaje hasta el jueves..."
                        data-testid="aplazar-nota"
                        className="w-full bg-muted border border-input rounded-xl px-3 py-2 text-sm text-foreground placeholder-foreground/30 focus:outline-none focus:border-[#FF671F] resize-none" />
                    <div className="flex gap-2">
                        <button type="button" data-testid="aplazar-si"
                            onClick={() => aplazar(notaAplazar.trim() || undefined)}
                            className="flex-1 rounded-xl py-2.5 text-sm font-bold text-white"
                            style={{ backgroundColor: ORANGE }}>
                            Aplázamelo
                        </button>
                        <button type="button" onClick={() => setPidiendoAplazar(false)}
                            className="rounded-xl px-4 py-2.5 text-sm text-foreground/70 border border-border hover:border-foreground/30">
                            Sí puedo
                        </button>
                    </div>
                </div>
            )}
        </>
    );

    // ── EL QUINCENAL: TRES PASOS («Todo lo validado antes del 1 de septiembre») ──
    //
    // Era una sola pantalla con cuatro preguntas (T7 del 16-08) y pasa a tener la misma
    // forma que el mensual: 1 sus datos, 2 sus sensaciones y dudas, y el 3 la respuesta,
    // que se ve al mandarlo. La cabecera «Son 3 pasos» sale en los tres, con el suyo
    // marcado, y por eso desde el primero ya sabe que después de enviar pasa algo.
    //
    // El paso 1 es el que más cambia: antes se le PEDÍA el peso y ahora se le ENSEÑA su
    // semana entera -- lo que ha hecho, cómo se ha sentido y de qué dos días sale su peso
    // -- para que solo tenga que confirmarla.
    if (!esMensual) {
        const tituloQuincenal = TITULOS_EN_LA_CABECERA[ficha?.tipo] || 'Reporte';
        return (
            <div className="space-y-4">
                <CabeceraDePasos paso={pasoMensual} plazo={plazo}
                    pasos={PASOS_DEL_QUINCENAL} titulo={tituloQuincenal} />

                {pasoMensual === 1 && (
                    <>
                        {/* EL SUBTÍTULO LO PONE EL PASO, no esta pantalla: en la versión
                            sin check-in dice otra cosa («Cinco preguntas y pasas al paso
                            2»), y tenerlo aquí escribía «Sale de tu check-in» encima de un
                            aviso que dice justo que no los tenemos. */}
                        <RotuloDelPaso paso={1} rotulos={ROTULOS_DEL_QUINCENAL} />
                        <QuincenalPaso1
                            api={api} valores={valores} set={set}
                            huecosRespuestas={valores.huecos_paso1}
                            onHueco={(tipo, v) => set('huecos_paso1',
                                { ...(valores.huecos_paso1 || {}), [tipo]: v })}
                            onConfirmar={confirmarPaso1} />
                        {bloqueAplazar}
                    </>
                )}

                {pasoMensual === 2 && (
                    <>
                        <RotuloDelPaso paso={2} rotulos={ROTULOS_DEL_QUINCENAL} />
                        <ReporteQuincenal valores={valores} set={set} bloques={bloques} />
                        <div className="flex gap-2">
                            <button type="button" onClick={() => irAPaso(1)} data-testid="quincenal-atras"
                                className="rounded-xl px-4 py-3 text-sm font-bold border border-border bg-card text-foreground/70 hover:border-foreground/30 transition-colors">
                                Atrás
                            </button>
                            <button type="button" onClick={enviar} disabled={enviando}
                                data-testid="submit-report-btn"
                                className="flex-1 py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40"
                                style={{ backgroundColor: ORANGE }}>
                                <Send className="w-4 h-4" />
                                {enviando ? 'Enviando...' : 'Enviar reporte'}
                            </button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // ── EL MENSUAL: los cuatro pasos del documento del 1-09 ──
    return (
        <div className="space-y-4">
            <CabeceraDelMensual paso={pasoMensual} plazo={plazo} />

            {pasoMensual === 1 && (
                <>
                    {/* El subtítulo, dentro del paso: cambia con la versión (ver arriba). */}
                    <RotuloDelPaso paso={1} />
                    <MensualPaso1
                        api={api} valores={valores} set={set}
                        pideGrasa={bloques.includes('grasa')} grasa={ficha.datos?.grasa}
                        huecosRespuestas={valores.huecos_paso1}
                        onHueco={(tipo, v) => set('huecos_paso1',
                            { ...(valores.huecos_paso1 || {}), [tipo]: v })}
                        onConfirmar={confirmarPaso1} />
                    {bloqueAplazar}
                </>
            )}

            {pasoMensual === 2 && (
                <>
                    <RotuloDelPaso paso={2} />
                    <ReporteMensual
                        datos={ficha.datos} perfil={ficha.perfil} bloques={bloques}
                        valores={valores} set={set} setEntreno={setEntreno} />
                    <div className="flex gap-2">
                        <button type="button" onClick={() => irAPaso(1)} data-testid="mensual-atras"
                            className="rounded-xl px-4 py-3 text-sm font-bold border border-border bg-card text-foreground/70 hover:border-foreground/30 transition-colors">
                            Atrás
                        </button>
                        <button type="button" onClick={() => irAPaso(3)} data-testid="mensual-siguiente"
                            className="flex-1 rounded-xl py-3 text-sm font-bold text-white uppercase tracking-wider"
                            style={{ backgroundColor: ORANGE }}>
                            Siguiente
                        </button>
                    </div>
                </>
            )}

            {pasoMensual === 3 && (
                <>
                    <RotuloDelPaso paso={3} sub="Lo último, y es lo que más me dice a mí." />
                    <MensualPaso3 api={api} token={token} valores={valores} set={set}
                        prev={prev} plazo={plazo} />
                    <div className="flex gap-2">
                        <button type="button" onClick={() => irAPaso(2)} data-testid="mensual-atras"
                            className="rounded-xl px-4 py-3 text-sm font-bold border border-border bg-card text-foreground/70 hover:border-foreground/30 transition-colors">
                            Atrás
                        </button>
                        {/* El botón dice «Enviar reporte», como en el documento. Antes de
                            mandarlo de verdad se le enseña el resumen: sigue siendo el
                            último sitio donde puede ver lo que va a mandar. */}
                        <button type="button" onClick={irAlResumen} disabled={enviando}
                            data-testid="revisar-y-enviar"
                            className="flex-1 rounded-xl py-3 text-sm font-bold text-white uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-40"
                            style={{ backgroundColor: ORANGE }}>
                            <Send className="w-4 h-4" />
                            Enviar reporte
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

/**
 * Los huecos, como los entiende el servidor.
 *
 * En el quincenal es una respuesta sola. En el mensual del que confirma día a día se
 * resume: si dice que entrenó aunque sea un día sin apuntarlo, cuenta como registro que
 * faltaba; si dice que no entrenó ninguno, cuenta como no hecho. El detalle día a día no
 * se pierde -- va en `entreno.confirmacion` --, esto es solo para el porcentaje.
 */
const huecosParaElServidor = (ficha, valores) => {
    if (ficha?.tipo !== 'mensual') {
        if (!valores.entreno_huecos) return {};
        return { entrenamiento: valores.entreno_huecos === 'si_no_lo_apunte'
            ? 'si_pero_no_apunte' : 'no_lo_hice' };
    }
    // LOS DEL PASO 1 MANDAN (documento del 1-09). Ahí es donde se le enseñan los huecos y
    // donde contesta, y además son los dos: el de entrenos y el de la dieta, que antes no
    // se preguntaba en el mensual. Los valores ya vienen como los entiende el servidor.
    const salida = {};
    const p1 = valores.huecos_paso1 || {};
    if (p1.entreno) salida.entrenamiento = p1.entreno;
    if (p1.dieta) salida.dieta = p1.dieta;

    // La confirmación día a día del bloque del entreno sigue existiendo para el perfil
    // «con_rutina», y se respeta si el paso 1 no trajo respuesta: es más fina, porque va
    // por fechas concretas.
    if (!salida.entrenamiento) {
        const respuestas = Object.values(valores.entreno?.confirmacion || {}).filter(Boolean);
        if (respuestas.length) {
            salida.entrenamiento = respuestas.includes('si_no_lo_apunte')
                ? 'si_pero_no_apunte' : 'no_lo_hice';
        }
    }
    return salida;
};

/** Solo lo que se le ha llegado a preguntar: un plan sin rutina no manda estrellas. */
const limpiarEntreno = (entreno) => ({
    confirmacion: Object.fromEntries(
        Object.entries(entreno.confirmacion || {}).filter(([, v]) => v)),
    estrellas: entreno.estrellas ?? null,
    nota: entreno.nota || null,
    regularidad: entreno.regularidad || null,
    rutina_del_mes: entreno.rutina_del_mes || null,
    quiere_saber_del_silver: entreno.quiere_saber_del_silver,
});

export default FormularioReporte;
