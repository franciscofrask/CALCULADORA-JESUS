import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import GraficaDePeso from '../components/GraficaDePeso';
import {
    FileText, TrendingUp, Scale,
    Activity, ChevronRight, ChevronLeft, Calendar
} from 'lucide-react';
import InformeMensual from '../components/reports/InformeMensual';
import EvolucionMedidas from '../components/EvolucionMedidas';
import ComparativaCliente from '../components/ComparativaCliente';
import Diario from '../components/Diario';
import TresFotos from '../components/reports/TresFotos';
import TusFotosYMetricas from '../components/TusFotosYMetricas';
import FormularioReporte from '../components/reports/FormularioReporte';
import HistorialDeMacros from '../components/HistorialDeMacros';
import { verComo } from '../lib/modoRevision';

const ORANGE = '#FF671F';

/**
 * LOS AJUSTES DE MACROS DENTRO DE EVOLUCIÓN (doc 19-08, bloque 09): para el cliente con
 * entrenador, que ya no tiene la pestaña de Mis macros. Trae su historial y pinta la misma
 * tabla que verían los demás allí.
 */
const HistorialDeAjustes = ({ api }) => {
    const [entradas, setEntradas] = useState(null);
    useEffect(() => {
        let vivo = true;
        api.get('/macros/historial')
            .then(r => { if (vivo) setEntradas(r.data?.entradas || []); })
            .catch(() => { if (vivo) setEntradas([]); });
        return () => { vivo = false; };
    }, [api]);
    if (!entradas || entradas.length < 2) return null;
    return <HistorialDeMacros entradas={entradas} />;
};

// Estado de la ventana de envío. Cada cadencia tiene la suya (el semanal, viernes 10:00
// -> sábado 10:00, doc 21-08); las fechas las manda el servidor y aquí solo se enseñan,
// en la hora del navegador (_plazoDelCliente).
const WindowBanner = ({ w }) => {
    const base = "rounded-2xl p-4 border text-sm flex items-center gap-2";
    if (w?.revision) {
        return (
            <div className={`${base} border-brand/40 bg-brand/5 text-foreground`}>
                <Calendar className="w-4 h-4 text-brand flex-shrink-0" />
                Modo revisión: estás viendo el {w.tipo_label?.toLowerCase()} fuera de su semana. Enviarlo no funcionará.
            </div>
        );
    }
    if (!w || !w.due) {
        return (
            <div className={`${base} border-border bg-muted text-foreground/60`}>
                <Calendar className="w-4 h-4 text-foreground/40 flex-shrink-0" />
                Esta semana no toca reporte. Te avisaremos cuando abra la ventana.
            </div>
        );
    }
    if (w.submitted) {
        return (
            <div className={`${base} border-green-500/40 bg-green-500/5 text-foreground`}>
                <Calendar className="w-4 h-4 text-green-500 flex-shrink-0" />
                Ya enviaste tu {w.tipo_label?.toLowerCase()} de esta semana. ¡Bien hecho!
            </div>
        );
    }
    if (w.is_open) {
        return (
            <div className={`${base} border-yellow-500/40 bg-yellow-500/5 text-foreground`}>
                <Calendar className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                Ventana abierta: rellena tu {w.tipo_label?.toLowerCase()} antes del {_plazoDelCliente(w.closes_at) || w.closes_label}.
            </div>
        );
    }
    const before = w.opens_at && new Date(w.opens_at).getTime() > Date.now();
    // Cerrada del todo: la fecha que sirve es la del SIGUIENTE, no la de la ventana que
    // ya pasó. El servidor la manda en `proximo` (con su ISO para poder decir la hora).
    const proximaApertura = _plazoDelCliente(w.proximo?.abre) || w.proximo?.abre_label;
    return (
        <div className={`${base} ${before ? 'border-yellow-500/40 bg-yellow-500/5' : 'border-red-500/40 bg-red-500/5'} text-foreground`}>
            <Calendar className={`w-4 h-4 flex-shrink-0 ${before ? 'text-yellow-500' : 'text-red-500'}`} />
            {/* «La semana que viene» no es una fecha, y el servidor sabe cuándo vuelve a abrir:
                lo mandaba en `opens_label` y aquí no se usaba (Jesús, 11-08). */}
            {/* UN BOTÓN GRIS INFORMA; UNO QUE NO ESTÁ, NO (doc 21-08): cerrada o aún sin
                abrir, se dice CUÁNDO se enciende y CON HORA -- «Se abre el viernes a las
                10:00» --, en la hora del navegador del cliente. */}
            {before
                ? `Todavía no toca. Se abre el ${_plazoDelCliente(w.opens_at) || w.opens_label}.`
                : proximaApertura
                    ? `La ventana de esta semana se cerró. Se abre el ${proximaApertura}.`
                    : w.opens_label
                        ? `La ventana de esta semana se cerró. Se abría el ${w.opens_label}.`
                        : 'La ventana de esta semana se cerró. Espera a la semana que viene.'}
        </div>
    );
};

/**
 * LA PORTADA DE SEGUIMIENTO (documento del 10-08, pantalla 20).
 *
 * «Una sola entrada. Lo que toca ahora, arriba y en naranja; lo que ya hizo, en gris.
 * Nunca tiene que elegir entre cuatro formularios.»
 *
 * Sustituye a las dos entradas de hoy -- Reportes y Check-ins eran dos sitios distintos en
 * el menú -- y a que esta pantalla abriera con el formulario del mes desplegado entero.
 *
 * Lo que el documento pide y AQUÍ TODAVÍA NO ESTÁ, para que no se dé por hecho: la tarjeta
 * de «Esta semana» con el balance («cuadraste 5 de 7 días») necesita un dato que la app no
 * calcula hoy, y la revisión mensual en seis pasos (pantallas 22 a 24) es otra pantalla.
 * Aquí cada tarjeta lleva a lo que ya existe.
 */
const TarjetaSeguimiento = ({ cuando, titulo, sub, extra, cta, onClick, tono = 'gris', testid }) => {
    const destacada = tono === 'ahora';
    return (
        <button onClick={onClick} data-testid={testid}
            className={`w-full text-left rounded-2xl p-4 border transition-colors ${
                destacada ? 'border-brand/50 bg-brand/5 hover:bg-brand/10' : 'border-border bg-card hover:border-foreground/20'}`}>
            {cuando && <p className={`text-xs font-bold uppercase tracking-wider ${destacada ? 'text-brand' : 'text-muted-foreground'}`}>{cuando}</p>}
            <p className={`text-lg font-bold text-foreground ${cuando ? 'mt-1' : ''}`}>{titulo}</p>
            {sub && <p className="text-[15px] text-muted-foreground mt-0.5">{sub}</p>}
            {extra && <p className="text-[13px] text-muted-foreground mt-1">{extra}</p>}
            {cta && (
                <span className={`inline-flex items-center gap-1 mt-3 text-sm font-bold ${destacada ? 'text-brand' : 'text-foreground/70'}`}>
                    {cta} <ChevronRight className="w-4 h-4" />
                </span>
            )}
        </button>
    );
};

// Una de las TRES puertas de Seguimiento: Reportes, Evolución y Diario. Sin etiqueta de
// "cuándo" porque están siempre: el título, lo que hay dentro y la flecha.
const PuertaSeguimiento = ({ titulo, sub, onClick, testid }) => (
    <button onClick={onClick} data-testid={testid}
        className="w-full text-left rounded-2xl p-4 border border-border bg-card hover:border-foreground/20 transition-colors flex items-center gap-3">
        <span className="flex-1 min-w-0">
            <span className="block text-lg font-bold text-foreground">{titulo}</span>
            <span className="block text-[15px] text-muted-foreground">{sub}</span>
        </span>
        <ChevronRight className="w-5 h-5 text-foreground/30 flex-shrink-0" />
    </button>
);

// EL PLAZO, EN LA HORA DEL CLIENTE (doc 21-08, apartado 15). El plazo se FIJA en España
// -- el servidor manda `closes_at` en UTC y la regla es de allí --, pero se ENSEÑA en la
// hora del navegador: al que vive en Canarias o está de viaje, "hasta el sábado a las
// 10:00" a secas le miente una hora o varias. Si el reloj del navegador coincide con el
// de España se enseña tal cual y sin coletilla; si no, la hora local con la de España
// entre paréntesis. Se monta por partes porque el formato de un tirón mete comas donde
// el doc no las tiene. Este es el punto central: WindowBanner, la portada y el
// formulario (plazoLabel) formatean por aquí.
const MADRID = 'Europe/Madrid';

const _partesPlazo = (d, tz) => {
    const partes = new Intl.DateTimeFormat('es-ES', {
        ...(tz ? { timeZone: tz } : {}), weekday: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false,
    }).formatToParts(d);
    const p = (tipo) => partes.find(x => x.type === tipo)?.value || '';
    return {
        texto: `${p('weekday')} ${p('day')} a las ${p('hour')}:${p('minute')}`,
        hora: `${p('hour')}:${p('minute')}`,
    };
};

const _plazoDelCliente = (iso) => {
    const d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return null;
    const espana = _partesPlazo(d, MADRID);
    let local = espana;
    try { local = _partesPlazo(d); } catch { /* sin huso legible: se queda la de España */ }
    // Mismo reloj (España, o un huso con su misma hora): tal cual y sin coletilla.
    if (local.texto === espana.texto) return espana.texto;
    return `${local.texto} (${espana.hora} h España)`;
};

const _diaMadrid = (d) => new Intl.DateTimeFormat('en-CA', {
    timeZone: MADRID, year: 'numeric', month: '2-digit', day: '2-digit',
}).format(d);

// "te quedan 2 días": días de calendario en España, no horas. Es como lo cuenta el cliente.
const _cuantoQueda = (iso) => {
    const d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return null;
    const dias = Math.round(
        (new Date(`${_diaMadrid(d)}T12:00:00Z`) - new Date(`${_diaMadrid(new Date())}T12:00:00Z`)) / 86400000);
    if (dias <= 0) return 'hoy es el último día';
    return dias === 1 ? 'te queda 1 día' : `te quedan ${dias} días`;
};

const PortadaSeguimiento = ({ windowState, vencido, conDiario, onRevision, onEvolucion, onHistorial, onDiario }) => {
    // Le toca reporte y no lo ha mandado: es lo único que va arriba y en naranja.
    // LA FECHA LÍMITE VA EN LA TARJETA: la ventana son cuatro días y sin fecha nadie sabe
    // cuánto margen tiene («hasta el jueves 15», Jesús 11-08). El servidor ya mandaba
    // `closes_label` y `opens_label`; aquí no se usaban.
    //
    // «TE TOCA» ES CUANDO YA SE PUEDE, NO CUANDO ESTÁ PREVISTO.
    // La tarjeta miraba solo `due`, que dice que este periodo lleva reporte, no que la
    // ventana esté abierta. Resultado: salía en naranja con «Empezar» y detrás aparecía el
    // formulario en gris con «se abre el viernes». Prometía algo que no se podía hacer, que
    // es de lo que se queja Jesús el 11-08 sobre esta pantalla. Con `is_open` la tarjeta
    // dice lo que hay: cuando abra, en naranja; hasta entonces, en gris y con la fecha.
    //
    // TRES COSAS Y NADA MÁS (doc 16-08, T6): Reportes, Evolución y Diario. Los informes van
    // DENTRO de Reportes, no como una cuarta cosa, y la tarjeta «¿Cómo vas hoy?» se cae de
    // aquí: al cierre del día se entra desde Inicio.
    //
    // PASADA LA HORA, EL REPORTE DESAPARECE. Un reporte vencido en la portada es una puerta
    // que no lleva a ningún sitio: el servidor lo rechaza fuera de plazo. Se cae de aquí
    // igual que de Inicio, y en su lugar queda lo que sí puede hacer: lo siguiente.
    const proximo = windowState?.proximo;
    const yaPuede = windowState?.is_open !== false;
    const yaMandado = !!windowState?.submitted;
    const tocaRevision = !!windowState?.due && !yaMandado && yaPuede && !vencido;
    // Le toca este periodo pero la ventana todavía no ha abierto.
    const aunNoAbre = !!windowState?.due && !yaMandado && !yaPuede && !vencido;
    const hayReporteALaVista = tocaRevision || yaMandado || aunNoAbre;
    // El plazo, en hora de España y con lo que queda: la ventana son unos días y sin fecha
    // nadie sabe cuánto margen tiene (Jesús, 11-08).
    const plazo = _plazoDelCliente(windowState?.closes_at);
    const queda = _cuantoQueda(windowState?.closes_at);
    // Aún sin abrir: cuándo se enciende, con hora y en su huso (doc 21-08).
    const apertura = _plazoDelCliente(windowState?.opens_at) || windowState?.opens_label;

    return (
        <div className="space-y-3" data-testid="portada-seguimiento">
            {hayReporteALaVista && (
                <TarjetaSeguimiento
                    testid="seg-revision"
                    cuando={tocaRevision ? 'Esta semana · te toca' : yaMandado ? 'Esta semana · hecho' : 'Esta semana · aún no'}
                    titulo={windowState?.tipo_label || 'Tu revisión'}
                    sub={yaMandado
                        ? 'Ya lo mandaste. Lo estamos mirando.'
                        : 'Unas breves preguntas para ajustar tus macros si hace falta.'}
                    extra={tocaRevision && plazo
                        ? `Hasta el ${plazo}${queda ? ` · ${queda}` : ''}`
                        : aunNoAbre && apertura
                            ? `Se abre el ${apertura}.`
                            : null}
                    cta={tocaRevision ? 'Empezar' : 'Ver'}
                    tono={tocaRevision ? 'ahora' : 'gris'}
                    onClick={onRevision} />
            )}

            {/* Y detrás del que toca, el siguiente. Va pegada a su tarjeta porque habla de
                ella. Con esto el cliente ve su calendario y no solo el día de hoy: el del
                Nivel 2 sabe que después de este quincenal le llega el mensual, que es el que
                pide fotos y medidas y con el que hay que contar antes. */}
            {proximo && hayReporteALaVista && (
                <p className="text-[13px] text-muted-foreground px-1 -mt-1" data-testid="seg-proximo">
                    Después de este: tu {proximo.tipo_label.toLowerCase()}, el {proximo.abre_label}.
                </p>
            )}

            {/* Sin reporte a la vista -- porque no toca o porque se pasó la hora -- lo que
                queda es su calendario, para que la pantalla no calle sobre lo que viene. */}
            {!hayReporteALaVista && proximo && (
                <p className="text-[13px] text-muted-foreground px-1" data-testid="seg-proximo">
                    Lo próximo es tu {proximo.tipo_label.toLowerCase()}, el {proximo.abre_label}.
                </p>
            )}

            <PuertaSeguimiento
                testid="seg-historial"
                titulo="Reportes"
                sub="Los que mandaste y los informes que te di"
                onClick={onHistorial} />

            <PuertaSeguimiento
                testid="seg-evolucion"
                titulo="Evolución"
                sub="Tus fotos y tus métricas"
                onClick={onEvolucion} />

            {/* El Diario solo se ofrece si su interruptor está encendido: una puerta que
                lleva a un «todavía no está disponible» es peor que no estar. */}
            {conDiario && (
                <PuertaSeguimiento
                    testid="seg-diario"
                    titulo="Diario"
                    sub="Tus notas, día a día"
                    onClick={onDiario} />
            )}
        </div>
    );
};

// Modo revisión (solo equipo): `?ver=mensual`, `?ver=quincenal` o `?ver=semanal` abren el
// formulario aunque no sea su semana ni su fin de semana. Es la única forma de repasar los
// textos del reporte un martes, o de ver el mensual (con las diez medidas) el mes que toca
// quincenal. Enviarlo sigue pasando por el servidor, que no sabe nada de esto y lo rechaza
// fuera de plazo: se puede MIRAR, no colar.
const VENTANA_DE_MENTIRA = (tipo) => ({
    due: true, is_open: true, submitted: false, revision: true,
    tipo_label: { mensual: 'Reporte mensual', quincenal: 'Reporte quincenal',
                  semanal: 'Reporte semanal' }[tipo],
    tipos: [tipo],
    opens_label: 'modo revisión', closes_label: 'modo revisión',
});

const ReportsPage = () => {
    const { api, token, profile, user, pantalla } = useAuth();
    // La Evolución completa (medidas y comparativa) va detrás de su interruptor del panel
    // (T6). Con él apagado se queda la gráfica de peso, que es lo que hay hoy en producción.
    const evolucionCompleta = pantalla('t6_evolucion');
    const diarioActivo = pantalla('t5_diario');
    const revision = verComo(user);
    const tipoRevision = ['mensual', 'quincenal', 'semanal'].includes(revision) ? revision : null;
    const [reports, setReports] = useState([]);
    const [evolution, setEvolution] = useState(null);
    const [loading, setLoading] = useState(true);
    // LA PANTALLA ABRE EN LA PORTADA, TAMBIÉN EN EL ORDENADOR.
    //
    // `seccionAbierta` dice en cuál de las cuatro tarjetas ha entrado, y mientras vale null
    // se ve la portada (documento del 10-08, pantalla 20).
    //
    // Esto era solo del teléfono, porque el encargo era no tocar el escritorio, y en el
    // ordenador seguían las tres pestañas con el formulario entero desplegado de entrada:
    // peso, vídeo, las diez medidas, dos preguntas, tres barras, notas, objetivo, dos
    // preguntas más, enviar y las tres fotos, tocara reporte o no. Y en gris, con un «la
    // ventana se cerró» encima: se le enseñaba todo lo que no podía hacer (Jesús, 11-08).
    // Es el mismo cliente y el mismo trámite, así que es la misma solución.

    // En modo revisión se entra directamente al formulario: es lo que se viene a mirar.
    // Y «?abrir=evolucion» aterriza en Evolución: es a donde apuntan el botón «Ver mi
    // evolución» de Mis macros y la ruta vieja de macros para los planes con entrenador
    // (doc 19-08, bloque 09).
    // Y «?aplazar=1» aterriza en el formulario con el aplazamiento abierto: es el camino
    // desde «No puedo esta semana» del aviso (doc 19-08, bloque 11).
    const abrirPedida = new URLSearchParams(window.location.search).get('abrir');
    const aplazarPedido = new URLSearchParams(window.location.search).get('aplazar') === '1';
    const [seccionAbierta, setSeccionAbierta] = useState(
        tipoRevision || aplazarPedido ? 'form' : abrirPedida === 'evolucion' ? 'evolution' : null);
    const vista = seccionAbierta;
    const [windowState, setWindowState] = useState(null);   // ventana de envío (la de su cadencia)
    // Si el plazo ya pasó. Lo dice el servidor en `items[].overdue` y no se calcula aquí:
    // la hora buena es la suya, no la del reloj del teléfono. Pasada la hora, el reporte
    // pendiente desaparece de esta pantalla (y de Inicio, que ya lo hacía).
    const [vencido, setVencido] = useState(false);
    const [prev, setPrev] = useState(null);                 // último reporte (referencia de medidas)

    // El informe del mes: se pide solo cuando abre uno, porque cruza dietas, check-ins
    // y macros de todo el periodo y no tiene sentido calcularlo para la lista entera.
    const [informeAbierto, setInformeAbierto] = useState(null);   // id del reporte abierto
    const [informe, setInforme] = useState(null);
    const [cargandoInforme, setCargandoInforme] = useState(false);

    const verInforme = async (reportId) => {
        if (informeAbierto === reportId) { setInformeAbierto(null); setInforme(null); return; }
        setInformeAbierto(reportId);
        setInforme(null);
        setCargandoInforme(true);
        try {
            const r = await api.get(`/reports/${reportId}/informe`);
            setInforme(r.data);
        } catch (e) {
            toast.error('No hemos podido crear tu informe');
            setInformeAbierto(null);
        } finally {
            setCargandoInforme(false);
        }
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch solo al montar
    useEffect(() => { fetchData(); }, []);

    const fetchData = async () => {
        try {
            // La confirmación de huecos ya no se pide aquí: cada reporte trae los suyos
            // dentro (`/reports/formulario`), con los días de rutina que le faltan por
            // registrar en vez de una cuenta de check-ins.
            const [reportsRes, evolutionRes, dueRes, prevRes] = await Promise.all([
                api.get('/reports'),
                api.get('/reports/evolution'),
                api.get('/reports/due').catch(() => ({ data: { window: null } })),
                api.get('/reports/previous').catch(() => ({ data: null })),
            ]);
            setReports(reportsRes.data);
            setHasMore(reportsRes.data.length === 50);
            setEvolution(evolutionRes.data);
            setWindowState(tipoRevision ? VENTANA_DE_MENTIRA(tipoRevision) : (dueRes.data?.window || null));
            setVencido(!tipoRevision && (dueRes.data?.items || []).some(i => i.overdue));
            setPrev(prevRes.data && Object.keys(prevRes.data).length ? prevRes.data : null);
        } catch (error) {
            console.error('Error fetching reports:', error);
        } finally {
            setLoading(false);
        }
    };

    // Paginación del historial: "Cargar más" trae el siguiente bloque
    const [hasMore, setHasMore] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const loadMore = async () => {
        setLoadingMore(true);
        try {
            const res = await api.get('/reports', { params: { skip: reports.length } });
            setReports(prev => [...prev, ...res.data]);
            setHasMore(res.data.length === 50);
        } catch { /* silencioso */ }
        finally { setLoadingMore(false); }
    };

    // Qué reporte toca esta semana. Lo usa la subida de fotos suelta: las fotos son del
    // mensual, pero se pueden subir cualquier día (punto 21 / 2.2).
    const esMensual = (windowState?.tipos || []).includes('mensual');

    // EL ENVÍO VIVE EN EL FORMULARIO (T7, T8 y T9). Aquí estaba el `handleSubmit` de los
    // dos reportes juntos: peso, medidas, tres deslizadores y tres preguntas, todo en el
    // mismo sitio. Ahora cada reporte tiene su cuestionario, el mensual pasa por la
    // pantalla de revisión y lo que se le dice al terminar depende de su plan, así que el
    // envío se fue con ellos a `components/reports/FormularioReporte`.
    const formOpen = windowState ? (windowState.is_open && !windowState.submitted) : true;

    // Sin formatear: la gráfica necesita la fecha de verdad para poner el eje en el tiempo.
    // Antes se le daba ya convertida a «9 ago», y con dietas desde 2022 hay cuatro «9 ago»
    // distintos que el eje juntaba en una sola columna.
    const weightData = evolution?.weight?.map(w => ({ fecha: w.date, peso: w.value })) || [];

    if (loading) {
        return (
            <div className="px-4 pt-6 pb-28">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/3" />
                    <div className="h-48 bg-card rounded-2xl" />
                </div>
            </div>
        );
    }

    return (
        <div className="px-4 pt-6 pb-28 max-w-2xl mx-auto space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${ORANGE}20` }}>
                    <FileText className="w-5 h-5" style={{ color: ORANGE }} />
                </div>
                <div>
                    {/* Un solo nombre: en el menú pone «Seguimiento» y aquí ponía «Mis
                        reportes» en el ordenador, así que la misma sección se llamaba de
                        dos maneras según el aparato desde el que la abrieras. */}
                    <h1 className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.05em' }} data-testid="reports-heading">
                        SEGUIMIENTO
                    </h1>
                    {/* Lo que hay dentro, con sus nombres: reportes, evolución y diario. Las
                        tres cosas del doc 16-08, ni una más -- los check-ins ya no viven
                        aquí, y nombrarlos era prometer una puerta que ya no está. */}
                    <p className="text-xs text-foreground/30">Tus reportes, tu evolución y tu diario</p>
                </div>
            </div>

            {/* LA PORTADA DE SEGUIMIENTO (documento del 10-08, pantalla 20). Una sola
                entrada en vez de dos -- Reportes y Check-ins eran dos sitios distintos --,
                con lo que toca ahora arriba y lo que ya está hecho debajo en gris: «nunca
                tiene que elegir entre cuatro formularios».

                Antes esta pantalla abría directamente con el formulario del reporte entero
                desplegado: peso, las diez medidas, los huecos, las notas, tres preguntas,
                las fotos y enviar. 3.770 px, cuatro pantallas y media de móvil, tanto si le
                tocaba reporte como si no. */}
            {!seccionAbierta && (
                <PortadaSeguimiento
                    windowState={windowState}
                    vencido={vencido}
                    conDiario={diarioActivo}
                    onRevision={() => setSeccionAbierta('form')}
                    onEvolucion={() => setSeccionAbierta('evolution')}
                    onHistorial={() => setSeccionAbierta('history')}
                    onDiario={() => setSeccionAbierta('diario')}
                />
            )}

            {/* Al entrar en una sección, la portada deja sitio y aparece la vuelta. */}
            {seccionAbierta && (
                <button onClick={() => setSeccionAbierta(null)} data-testid="volver-seguimiento"
                    className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground">
                    <ChevronLeft className="w-4 h-4" /> Seguimiento
                </button>
            )}

            {/* Aquí iban las tres pestañas del escritorio. Ya no hacen falta: la portada
                hace lo mismo diciendo además cuál toca ahora, y tener las dos cosas a la
                vez era ofrecer dos navegaciones para la misma pantalla. */}

            {/* ── EL FORMULARIO (T7 y T8) ──
                Ya no es un formulario con campos sueltos: son dos cuestionarios distintos
                -- el quincenal de cuatro preguntas y el mensual por bloques -- y el
                mensual además cambia según lo que incluya su plan. Todo eso vive en
                `components/reports/FormularioReporte`; aquí solo queda la ventana de
                envío, que es de esta pantalla. */}
            {vista === 'form' && (
                <div className="space-y-4">
                    <WindowBanner w={windowState} />
                    {windowState && !windowState.due ? null : formOpen ? (
                        <FormularioReporte
                            api={api} token={token}
                            tipoRevision={tipoRevision}
                            windowState={{
                                ...windowState,
                                // La semana que decidió ESTE reporte (doc 19-08): la de su
                                // rutina si la tiene; sin rutina, la de su ciclo de siempre.
                                semana: windowState?.semana_reporte ?? profile?.week,
                                plazoLabel: _plazoDelCliente(windowState?.closes_at),
                                quedaLabel: _cuantoQueda(windowState?.closes_at),
                            }}
                            prev={prev}
                            perfilCliente={profile}
                            onEnviado={fetchData} />
                    ) : (
                        // Ventana cerrada o ya mandado: el formulario no se pinta en gris
                        // detrás de un cartel (punto 4.18). Lo que sí sigue estando son las
                        // fotos: se suben solas, en su propia petición, y que se pidan en el
                        // mensual es una cosa y que el resto del mes no se puedan subir es otra.
                        <TresFotos api={api} token={token} esMensual={esMensual} />
                    )}
                </div>
            )}

            {/* ── EVOLUCIÓN ──
                «Tus fotos y tus métricas». Hasta el doc 16-08 aquí solo estaba la gráfica de
                peso: ni fotos, ni medidas, ni comparativa, cuando todo eso ya existía en la
                ficha del panel. Ahora se enseña lo mismo que ve su entrenador, con los dos
                cambios de T6: dos fotos por defecto y sin el % graso, que lo pone Jesús. */}
            {vista === 'evolution' && (
                <div className="space-y-4">
                    <div>
                        <p className="text-lg font-bold text-foreground">Evolución</p>
                        <p className="text-[15px] text-muted-foreground">Tus fotos y tus métricas</p>
                    </div>

                    {/* LOS TRES BOTONES (doc 19-08, «Lo que falta en Seguimiento»): subir
                        fotos, añadir medidas y actualizar el % de grasa, cuando quiera. La
                        pantalla decía «se piden en el reporte mensual» y no dejaba hacer
                        nada. */}
                    <TusFotosYMetricas api={api} token={token} profile={profile}
                        onGuardado={fetchData} />


                    {weightData.length > 0 ? (
                        <div className="bg-card border border-border rounded-2xl p-4">
                            <div className="flex items-center gap-2 mb-4">
                                <Scale className="w-4 h-4" style={{ color: ORANGE }} />
                                <p className="text-sm font-bold text-foreground uppercase tracking-wider">Tu peso</p>
                            </div>
                            {/* La gráfica es la MISMA que ve su entrenador (punto 4.13). Aquí
                                los ejes iban pintados de blanco a pelo, y esta tarjeta es
                                blanca en tema claro: eran fechas y kilos escritos en blanco
                                sobre blanco. */}
                            {/* Con su objetivo al lado: el color del cambio se decide
                                contra él (doc 23-08, bloque 10). */}
                            <GraficaDePeso puntos={weightData} objetivo={profile?.goal} />
                        </div>
                    ) : (
                        <div className="bg-card border border-border rounded-2xl p-8 text-center">
                            <TrendingUp className="w-10 h-10 text-foreground/20 mx-auto mb-3" />
                            <p className="text-foreground font-bold mb-1">Sin datos de evolución</p>
                            <p className="text-xs text-foreground/30">Envía tu primer reporte para ver tu progreso.</p>
                        </div>
                    )}

                    {evolucionCompleta && (
                        <>
                            <ComparativaCliente api={api} reports={reports} faseDesde={profile?.fase_desde} />
                            {/* La misma tabla que la ficha del panel, con el tono de la app del
                                cliente: la diferencia con la toma anterior y la columna Total. */}
                            <EvolucionMedidas reports={reports} />
                        </>
                    )}

                    {/* SUS AJUSTES DE MACROS, AQUÍ, para el que se los lleva un entrenador
                        (doc 19-08, bloque 09): la pestaña de Mis macros ya no existe para él
                        y su histórico va «al lado de su peso, sus medidas y sus fotos. Que
                        es donde se ve que estás trabajando». La misma tabla que ve el que
                        se los calcula, del mismo componente. */}
                    {profile?.macros_ajustables?.puede === false && (
                        <HistorialDeAjustes api={api} />
                    )}
                </div>
            )}

            {/* ── EL DIARIO (T5) ──
                Vive DENTRO de Seguimiento, no es una pestaña nueva del menú. Solo lectura:
                aquí cae lo que ya escribió en el cierre del día y en sus entrenos. */}
            {vista === 'diario' && (
                diarioActivo ? (
                    <Diario api={api} />
                ) : (
                    <div className="bg-card border border-border rounded-2xl p-8 text-center">
                        <p className="text-sm text-muted-foreground">Tu diario todavía no está disponible.</p>
                    </div>
                )
            )}

            {/* ── HISTORY TAB ── */}
            {vista === 'history' && (
                <div className="space-y-3">
                    {reports.length > 0 ? reports.map((report) => (
                        <div key={report.id} className="bg-card border border-border rounded-2xl p-4">
                            <button onClick={() => verInforme(report.id)} data-testid={`ver-informe-${report.id}`}
                                className="w-full text-left flex items-start justify-between mb-3">
                                <div>
                                    <p className="text-xs text-foreground/40 uppercase tracking-wider">
                                        {new Date(report.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                                    </p>
                                    <p className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {report.weight} <span className="text-base text-foreground/40">kg</span>
                                    </p>
                                    <p className="text-[11px] mt-0.5" style={{ color: ORANGE }}>
                                        {informeAbierto === report.id ? 'Ocultar mi informe' : 'Ver mi informe del mes'}
                                    </p>
                                </div>
                                <ChevronRight className={`w-4 h-4 text-foreground/20 mt-1 transition-transform ${informeAbierto === report.id ? 'rotate-90' : ''}`} />
                            </button>

                            {informeAbierto === report.id && (
                                <div className="mb-3">
                                    {cargandoInforme
                                        ? <p className="text-sm text-foreground/40 py-4 text-center">Creando tu informe...</p>
                                        // EL INFORME NO SALE HASTA QUE LO REVISAN (T9). Mientras está
                                        // pendiente no se le enseña el "te falta una foto" del informe
                                        // sin generar: ahí no le falta nada a él, le falta a Jesús.
                                        : informe?.motivo === 'pendiente_revision'
                                            ? <p className="text-sm text-muted-foreground py-4 text-center" data-testid="informe-pendiente">
                                                {informe.mensaje}
                                              </p>
                                            : <InformeMensual informe={informe} onPedirFotos={() => setSeccionAbierta('form')} />}
                                </div>
                            )}
                            {/* Con el informe abierto, estos dos sobran: el cumplimiento de
                                verdad (el de lo registrado) y la explicación del coach ya van
                                dentro, y verlos dos veces confunde sobre cuál es el bueno.
                                Los deslizadores además son justo lo que la especificación
                                manda sustituir por la confirmación de huecos. */}
                            {informeAbierto !== report.id && (report.training_compliance != null || report.nutrition_compliance != null) && (
                                <div className="grid grid-cols-2 gap-2">
                                    <div className="bg-muted rounded-xl px-3 py-2 flex items-center gap-2">
                                        <Activity className="w-3.5 h-3.5" style={{ color: ORANGE }} />
                                        <span className="text-xs text-foreground/60">Entreno <span className="text-foreground font-bold">{report.training_compliance != null ? `${report.training_compliance}%` : '-'}</span></span>
                                    </div>
                                    <div className="bg-muted rounded-xl px-3 py-2 flex items-center gap-2">
                                        <Activity className="w-3.5 h-3.5 text-green-400" />
                                        <span className="text-xs text-foreground/60">Nutrición <span className="text-foreground font-bold">{report.nutrition_compliance != null ? `${report.nutrition_compliance}%` : '-'}</span></span>
                                    </div>
                                </div>
                            )}
                            {informeAbierto !== report.id && report.trainer_feedback && (
                                <div className="mt-3 p-3 rounded-xl border" style={{ backgroundColor: `${ORANGE}10`, borderColor: `${ORANGE}30` }}>
                                    <p className="text-xs font-bold mb-1" style={{ color: ORANGE }}>Feedback del entrenador</p>
                                    <p className="text-sm text-foreground/70">{report.trainer_feedback}</p>
                                </div>
                            )}
                        </div>
                    )) : (
                        <div className="bg-card border border-border rounded-2xl p-8 text-center">
                            <Calendar className="w-10 h-10 text-foreground/20 mx-auto mb-3" />
                            <p className="text-foreground/40 text-sm">No hay reportes anteriores.</p>
                        </div>
                    )}
                    {hasMore && (
                        <button onClick={loadMore} disabled={loadingMore} data-testid="reports-load-more"
                            className="w-full py-3 rounded-2xl border border-border text-sm text-foreground/60 hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50">
                            {loadingMore ? 'Cargando...' : 'Cargar más reportes'}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default ReportsPage;
