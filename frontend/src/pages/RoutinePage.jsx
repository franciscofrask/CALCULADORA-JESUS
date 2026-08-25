import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { plural } from '../lib/labels';
import {
    Dumbbell, Repeat, ChevronDown, ChevronUp, History,
    Flame, Moon, Play, Timer, Trophy, ChevronRight, FileText, Check
} from 'lucide-react';

const DAYS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const DAY_LABELS = { lunes: 'L', martes: 'M', 'miércoles': 'X', jueves: 'J', viernes: 'V', 'sábado': 'S', domingo: 'D' };
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

// Lo que se le dice a quien YA pidió su rutina del mes. La fecha viene como día suelto
// («2026-08-24») y se monta a mediodía a propósito: a las 00:00 el huso se la lleva al día
// anterior y le diríamos que la pidió un día antes de pedirla.
const textoDeLaPeticion = (p) => {
    if (!p) return '';
    const cual = p.modalidad === 'avanzada' ? 'avanzada' : 'básica';
    const cuando = p.fecha
        ? new Date(`${p.fecha}T12:00:00`).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })
        : null;
    return (cuando ? `Nos pediste tu rutina ${cual} el ${cuando}.` : `Nos pediste tu rutina ${cual}.`)
        // Si ya se le entregó la del mes, no se le dice que la estamos preparando.
        + (p.rutina_puesta ? ' Ya la tienes puesta aquí.'
                           : ' El equipo se pone con ella y la tendrás aquí en cuanto esté.')
        // Del cobro solo se habla cuando el servidor dice que NO entró. Antes esto colgaba
        // de `!cobrado`, y la petición que llega del reporte mensual no trae ese dato: al
        // que ya había pagado se le decía «el cobro se quedó pendiente» sin ser verdad.
        + (p.cobro_pendiente ? ' El cobro se quedó pendiente: te escribimos para resolverlo.' : '');
};

// Fuera del componente a propósito, por lo mismo que el marco de RecuperarPage (13-08):
// definido dentro, cada render creaba una función nueva y React remontaba la página entera
// en vez de actualizarla. Aquí no hay ningún campo que escribir, así que no se pierde el
// foco, pero ExerciseCard sí perdía su useState: al cambiar de día se cerraban todos los
// ejercicios que tuvieras desplegados, y el animate-fade-in se relanzaba solo.
// No usa nada del ámbito del componente, así que sube tal cual.
const Wrap = ({ children }) => (
    <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto animate-fade-in" data-testid="routine-page">{children}</div>
);

// ─────────────────────────────────────────────────────────────────────────────
// LA SEMANA DE LA RUTINA (tarea 7.1 del 21-08, apartados 12 y 19 del doc de Jesús).
// Con el reparto que puso el entrenador al subir el PDF y los días que eligió el
// cliente en su alta, esto dice «Rutina #2 · Semana 3 de 8 · 4 días», pinta la tira de
// lunes a domingo con el grupo o el descanso, y el «Hoy · jueves · Empuje» con MARCAR.
// El descanso es un estado, no un fallo: «Hoy no entrenas», sin rojo y sin pedir nada.
// A nivel de módulo por lo mismo que Wrap: definido dentro se remonta en cada render.
// ─────────────────────────────────────────────────────────────────────────────
const SemanaDeRutina = ({ semana, abrirPdf, tienePdf, onMarcarHoy, onSiLoHice, onRecuperar, marcando }) => {
    // El selector del día para recuperar: null = cerrado.
    const [eligiendoDia, setEligiendoDia] = useState(false);
    if (!semana?.hay) return null;

    const { numero, semanas, semana_actual, dias_de_entreno, dias, hoy, pendiente, puede_marcar } = semana;
    const cab = [
        numero ? `Rutina #${numero}` : 'Tu rutina',
        semana_actual ? (semanas ? `Semana ${Math.min(semana_actual, semanas)} de ${semanas}` : `Semana ${semana_actual}`) : null,
        plural(dias_de_entreno, 'día'),
    ].filter(Boolean).join(' · ');

    // Los días de descanso donde aún se puede recuperar: de hoy en adelante.
    const diasParaRecuperar = dias.filter(d => !d.entrena && d.fecha >= hoy.fecha);

    return (
        <div className="space-y-3 max-w-2xl" data-testid="semana-rutina">
            {/* Cabecera: qué rutina es, por qué semana va y el PDF a un toque. */}
            <div className="surface p-4 flex items-center justify-between gap-3 flex-wrap">
                <p className="font-bold text-foreground text-sm" data-testid="semana-rutina-cabecera">{cab}</p>
                {tienePdf && (
                    <button onClick={abrirPdf} data-testid="semana-rutina-pdf"
                        className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline underline-offset-4">
                        <FileText className="w-4 h-4" /> Abrir el PDF
                    </button>
                )}
            </div>

            {/* La tira de la semana: L a D con el grupo o la luna del descanso. */}
            <div className="grid grid-cols-7 gap-1.5" data-testid="semana-rutina-tira">
                {dias.map(d => (
                    <div key={d.fecha} data-testid={`semana-dia-${d.fecha}`}
                        className={`rounded-xl border px-1 py-2 text-center min-w-0
                            ${d.hoy ? 'border-brand bg-brand/10' : 'border-border bg-card'}`}>
                        <p className={`text-[10px] font-bold uppercase ${d.hoy ? 'text-brand' : 'text-muted-foreground'}`}>
                            {DAY_LABELS[d.dia]}
                        </p>
                        <div className="mt-1 h-8 flex flex-col items-center justify-center">
                            {d.entrena ? (
                                <>
                                    <p className="text-[9px] font-semibold text-foreground leading-tight truncate w-full px-0.5"
                                        title={d.grupo}>{d.grupo}</p>
                                    {d.hecho ? <Check className="w-3 h-3 text-emerald-500 mt-0.5" />
                                        : d.recuperado_en ? <span className="text-[8px] text-muted-foreground">→ otro día</span>
                                        : null}
                                </>
                            ) : (
                                <Moon className="w-3.5 h-3.5 text-muted-foreground/60" />
                            )}
                        </div>
                        {d.recuperacion && <p className="text-[8px] text-brand font-semibold">recup.</p>}
                    </div>
                ))}
            </div>

            {/* Hoy: el grupo con su MARCAR, o el descanso dicho en paz. */}
            {hoy.entrena ? (
                <div className="surface p-4 flex items-center justify-between gap-3" data-testid="semana-rutina-hoy">
                    <div>
                        <p className="caption">Hoy · {hoy.dia}</p>
                        <p className="font-heading text-xl font-bold uppercase text-foreground leading-tight">{hoy.grupo}</p>
                    </div>
                    {puede_marcar && (hoy.hecho ? (
                        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-500">
                            <Check className="w-4 h-4" /> Hecho
                        </span>
                    ) : (
                        <button onClick={() => onMarcarHoy(hoy)} disabled={marcando} data-testid="semana-rutina-marcar"
                            className="btn-brand px-5 py-2.5 font-bold text-sm disabled:opacity-60">
                            Marcar
                        </button>
                    ))}
                </div>
            ) : (
                <div className="surface p-4 flex items-center gap-3" data-testid="semana-rutina-hoy">
                    <Moon className="w-5 h-5 text-violet-400 flex-shrink-0" />
                    <div>
                        <p className="caption">Descanso</p>
                        <p className="font-semibold text-foreground text-sm">Hoy no entrenas.</p>
                    </div>
                </div>
            )}

            {/* El que se dejó: se pregunta, no se riñe. «No se puede mover. Si se ha
                perdido, se recupera otro día» (decisión del apartado 12). */}
            {pendiente && (
                <div className="surface border-brand/30 p-4 space-y-3" data-testid="semana-rutina-pendiente">
                    <p className="text-sm text-foreground">
                        El {pendiente.dia} te dejaste <span className="font-bold">{pendiente.grupo}</span>.
                    </p>
                    {eligiendoDia ? (
                        <div className="space-y-2">
                            <p className="text-xs text-muted-foreground">¿Qué día de descanso lo recuperas?</p>
                            <div className="flex gap-2 flex-wrap">
                                {diasParaRecuperar.map(d => (
                                    <button key={d.fecha} disabled={marcando}
                                        onClick={() => { setEligiendoDia(false); onRecuperar(pendiente, d); }}
                                        data-testid={`semana-recuperar-${d.fecha}`}
                                        className="px-3 py-2 rounded-xl border border-border bg-card text-sm font-semibold text-foreground hover:border-brand/50 capitalize disabled:opacity-60">
                                        {d.dia}
                                    </button>
                                ))}
                                <button onClick={() => setEligiendoDia(false)}
                                    className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground">
                                    Atrás
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex gap-2 flex-wrap">
                            <button onClick={() => onSiLoHice(pendiente)} disabled={marcando} data-testid="semana-si-lo-hice"
                                className="px-4 py-2 rounded-xl border border-emerald-500/50 text-emerald-500 text-sm font-bold hover:bg-emerald-500/10 disabled:opacity-60">
                                Sí lo hice
                            </button>
                            {diasParaRecuperar.length > 0 && (
                                <button onClick={() => setEligiendoDia(true)} disabled={marcando} data-testid="semana-recuperar-otro-dia"
                                    className="px-4 py-2 rounded-xl border border-border text-foreground text-sm font-bold hover:border-brand/50 disabled:opacity-60">
                                    Recuperarlo otro día
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// LA RUTINA A LA VISTA, SIN SALIR DE LA PANTALLA (Jesús, 24-08)
//
// Hasta hoy el que tiene su rutina en PDF veía una tarjeta con «Abrir mi rutina» que se la
// abría en otra pestaña. Ahora se ve aquí dentro.
//
// TRES DECISIONES, y las tres son por el móvil, que es donde se abre:
//
//  1. El PDF se pide con el token (`api`, como todos los ficheros de la casa) y se pinta
//     desde un blob: poniéndolo en un `src=` a pelo el visor no manda la cabecera y el
//     servidor contesta 401.
//  2. En móvil NO se carga sola. Pesan entre 300 KB y 4,6 MB y van dentro del documento de
//     Mongo; bajarle eso con datos a quien solo entró a marcar el desayuno no está bien.
//     Ahí se pide con un botón, y en escritorio se carga al abrir la pantalla.
//  3. «Abrirla a pantalla completa» SE QUEDA SIEMPRE. Un PDF metido en la página se porta
//     mal fuera del escritorio: Safari de iOS pinta la primera página y no deja pasar de
//     ahí, y Chrome de Android muchas veces ni la pinta. Si nos quedáramos solo con la
//     vista previa habría clientes que no podrían leer su rutina, así que la vista previa
//     es un añadido y el botón de siempre sigue siendo la salida buena.
//
// El día que haga falta la rutina página a página dentro de la app, hace falta un visor de
// PDF de verdad (pdf.js) y eso es una dependencia nueva: hoy no hay ninguna en el proyecto.
// ─────────────────────────────────────────────────────────────────────────────
const esPantallaPequena = () =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(max-width: 767px)').matches
        : false;

const VistaPreviaPdf = ({ api, info, abrirPdf }) => {
    const [enMovil] = useState(esPantallaPequena);
    const [url, setUrl] = useState(null);
    // 'espera' (el móvil, hasta que lo pida) · 'cargando' · 'lista' · 'fallo'
    const [estado, setEstado] = useState(enMovil ? 'espera' : 'cargando');

    const cargar = React.useCallback(async () => {
        setEstado('cargando');
        try {
            const r = await api.get('/routines/pdf', { responseType: 'blob' });
            setUrl(URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })));
            setEstado('lista');
        } catch (e) {
            console.error('[vista previa de la rutina]', e?.response?.status || e);
            setEstado('fallo');
        }
    }, [api]);

    useEffect(() => { if (!enMovil) cargar(); }, [cargar, enMovil]);
    // El blob se suelta al salir: sin esto la pestaña se queda con los megas en memoria.
    useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

    // Si ya está descargada, se abre esa y no se vuelve a pedir al servidor.
    const abrirEntera = () => (url ? window.open(url, '_blank', 'noopener') : abrirPdf());

    return (
        <div className="surface p-4 sm:p-5 space-y-4 max-w-3xl" data-testid="routine-pdf-preview">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground leading-tight">Tu rutina, en PDF</h2>
                    <p className="text-muted-foreground text-sm">
                        Tu entrenador te la ha preparado el {new Date(info.uploaded_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })}.
                    </p>
                </div>
                <button onClick={abrirEntera} data-testid="routine-pdf-btn"
                    className="btn-brand inline-flex items-center gap-2 shrink-0">
                    Abrirla entera <ChevronRight className="w-4 h-4" />
                </button>
            </div>

            {estado === 'espera' && (
                <button onClick={cargar} data-testid="routine-pdf-ver-aqui"
                    className="w-full rounded-2xl border border-dashed border-border py-8 text-center hover:border-brand/50 transition-colors">
                    <FileText className="w-7 h-7 text-brand/60 mx-auto mb-2" />
                    <p className="font-semibold text-foreground text-sm">Verla aquí</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Son unos megas: mejor con wifi.</p>
                </button>
            )}

            {estado === 'cargando' && <div className="h-64 rounded-2xl bg-muted animate-pulse" />}

            {estado === 'fallo' && (
                <div className="rounded-2xl border border-border p-6 text-center space-y-3">
                    <p className="text-sm text-muted-foreground">
                        No hemos podido enseñártela aquí. Ábrela entera y la verás igual.
                    </p>
                    <button onClick={cargar} className="text-sm font-semibold text-brand hover:underline underline-offset-4">
                        Volver a intentarlo
                    </button>
                </div>
            )}

            {estado === 'lista' && url && (
                <object data={url} type="application/pdf" aria-label="Tu rutina en PDF"
                    data-testid="routine-pdf-object"
                    className="w-full h-[60vh] min-h-[320px] rounded-2xl border border-border bg-card">
                    {/* Lo que se ve donde el navegador no sabe pintar un PDF dentro de la
                        página, que en móvil es la mitad de las veces. */}
                    <div className="p-6 text-center space-y-3">
                        <p className="text-sm text-muted-foreground">
                            Tu navegador no la enseña aquí dentro. Ábrela entera y la verás igual.
                        </p>
                        <button onClick={abrirEntera} className="btn-brand">Abrirla entera</button>
                    </div>
                </object>
            )}
        </div>
    );
};

const RoutinePage = () => {
    const { api, myPlan, planCatalog, loading: cargandoSesion } = useAuth();
    const [routine, setRoutine] = useState(null);
    // NO SE PINTA LA OFERTA HASTA SABER QUÉ PLAN TIENE (verificación 24-08, fallo 15).
    //
    // `myPlan` sale de cruzar el perfil con el CATÁLOGO de planes, y AuthContext pide el
    // catálogo aparte (context/AuthContext.jsx:288-291): hasta que llega vale null. Con
    // null, esto daba `false` y en esa ventana un Premium o un Gold -- 116 clientes que la
    // llevan incluida -- leía un instante «Tu plan no incluye rutina · Quiero mi rutina ·
    // 57 €». No cobraba de más (el servidor lo rechaza con un 400), pero es el cartel
    // equivocado en la pantalla donde hay un botón de pagar.
    //
    // Por eso ahora son TRES estados y no dos: true (la lleva), false (no la lleva) y null
    // (todavía no lo sabemos). Con null no se enseña ni la oferta ni el «tu entrenador la
    // está preparando»: se espera.
    const planPorSaber = cargandoSesion || !Object.keys(planCatalog || {}).length;
    const rutinaIncluida = planPorSaber ? null : (() => {
        const r = myPlan?.habilitaciones?.rutina;
        // «opcional» es justo eso: no la lleva de serie, se le ofrece comprarla.
        return !!r && r !== 'ninguna' && r !== 'opcional';
    })();
    // Y si el catálogo no llega NUNCA (la petición de /plans falló, y AuthContext no la
    // reintenta), no se puede dejar la pantalla esperando para siempre: a los seis segundos
    // se enseña el cartel neutro, que es verdad lleve rutina o no. Lo que no se hace nunca a
    // ciegas es ofrecer los 57 €.
    const [planTardaDemasiado, setPlanTardaDemasiado] = useState(false);
    useEffect(() => {
        if (!planPorSaber) return undefined;
        const reloj = setTimeout(() => setPlanTardaDemasiado(true), 6000);
        return () => clearTimeout(reloj);
    }, [planPorSaber]);
    const [comprando, setComprando] = useState(null);      // null | 'eligiendo' | 'basica' | 'avanzada'
    const [compraHecha, setCompraHecha] = useState(null);  // el mensaje del servidor
    // LA PETICIÓN QUE YA HIZO (24-08). Hasta hoy la compra solo vivía en el estado de
    // React: el cliente pagaba 57 €, recargaba la pantalla y volvía a ver el botón como si
    // no hubiera pasado nada, con el segundo cargo a un clic. Ahora el servidor la apunta
    // en su ficha y la pantalla la pregunta al abrirse.
    const [peticion, setPeticion] = useState(null);
    const cargarPeticion = React.useCallback(() => {
        // Solo cuando SABEMOS que su plan no la lleva. Con `if (rutinaIncluida) return` y
        // el tri-estado nuevo, el null de «todavía no lo sé» habría colado la petición.
        if (rutinaIncluida !== false) return;
        api.get('/routines/quiero-la-rutina')
            .then(r => setPeticion(r.data?.pedida ? r.data : null)).catch(() => {});
    }, [api, rutinaIncluida]);
    useEffect(() => { cargarPeticion(); }, [cargarPeticion]);

    // ¿HAY RUTINA DEL MES QUE ENTREGAR? (verificación 24-08, fallo 14.) El botón cobraba 57 €
    // aunque no hubiera nada preparado: cero plantillas marcadas y ningún PDF del mes. El
    // servidor ya no deja pagar en ese caso; aquí se pregunta antes para no enseñar siquiera
    // un botón que va a rebotar. null mientras no se sabe: la oferta espera.
    const [rutinaDelMesLista, setRutinaDelMesLista] = useState(null);
    useEffect(() => {
        if (rutinaIncluida !== false) return;
        api.get('/routines/rutina-del-mes/disponible')
            .then(r => setRutinaDelMesLista(!!r.data?.disponible))
            // Si la pregunta falla no se le esconde la compra: que lo intente y que sea el
            // servidor quien diga que no. Esconderla por un corte de red es perder una venta.
            .catch(() => setRutinaDelMesLista(true));
    }, [api, rutinaIncluida]);

    // SE COMPRA, NO SE PIDE (Jesús, 24-08). Antes esto apuntaba la petición y cobraba en la
    // tarjeta guardada: al que no tenía tarjeta -- el que viene de Calma, el de Calculadora --
    // se le decía «te escribimos para resolverlo» y ahí se quedaba. Ahora va por la pasarela,
    // como la revisión suelta y el ajuste a medida: paga cualquiera, con factura, y al
    // volver la tiene puesta.
    const comprarRutina = async (modalidad) => {
        setComprando(modalidad);
        try {
            const r = await api.post('/billing/rutina-del-mes/checkout', { modalidad });
            if (r.data?.checkout_url) { window.location.href = r.data.checkout_url; return; }
            // Cuenta de pruebas: no pasa por Stripe y la rutina ya está puesta. Hay que
            // recargarla toda, no solo la petición: sin esto la pantalla decía «ya la tienes
            // puesta» encima del «Tu plan no incluye rutina» hasta que recargabas a mano.
            setCompraHecha(r.data?.mensaje || 'Hecho. Ya tienes tu rutina.');
            cargarPeticion(); cargarPdf(); cargarSemana(); fetchRoutine();
        } catch (e) {
            console.error('[rutina-del-mes/checkout]', e?.response?.data || e);
            toast.error(e?.response?.data?.detail || 'No hemos podido abrir el pago. Inténtalo en un momento.');
            setComprando('eligiendo');
            // Si el servidor la rechaza porque ya estaba pedida, que la pantalla se entere
            // y deje de ofrecerla en vez de dejar el botón puesto.
            cargarPeticion();
        }
    };
    const [routineHistory, setRoutineHistory] = useState([]);
    const [selectedDay, setSelectedDay] = useState(null);
    const [loading, setLoading] = useState(true);
    // La rutina no ha podido cargarse (no es lo mismo que no tenerla): ver fetchRoutine.
    const [fallo, setFallo] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    // La rutina en PDF que sube su entrenador (la de EntrenoPage). Hasta ahora esta
    // pantalla ni preguntaba por ella: el cliente con PDF y sin rutina estructurada leía
    // «Sin rutina asignada» teniendo su rutina subida. Se pide aparte del Promise.all a
    // propósito: si /routines/current falla, el PDF se enseña igual.
    const [pdfInfo, setPdfInfo] = useState(null);
    const cargarPdf = React.useCallback(() => {
        api.get('/routines/pdf/info').then(r => setPdfInfo(r.data?.hay ? r.data : null)).catch(() => {});
    }, [api]);
    useEffect(() => { cargarPdf(); }, [cargarPdf]);

    // La semana de la rutina (7.1 del 21-08): reparto del PDF + días del cliente. Se
    // pide aparte de /routines/current por lo mismo que el PDF: una no tapa a la otra.
    const [semana, setSemana] = useState(null);
    const [marcando, setMarcando] = useState(false);
    const cargarSemana = React.useCallback(() => {
        // Con el «hoy» del reloj del cliente (bloque F, 23-08).
        api.get(`/routines/semana?hoy_cliente=${new Date().toLocaleDateString('en-CA')}`)
            .then(r => setSemana(r.data?.hay ? r.data : null)).catch(() => {});
    }, [api]);
    useEffect(() => { cargarSemana(); }, [cargarSemana]);

    // LA VUELTA DEL PAGO. Stripe devuelve a /dashboard/routine?rutina=ok&session_id=...
    // El webhook hace lo mismo por su cuenta, pero puede tardar (o no estar configurado en
    // local): sin esto el cliente vuelve de pagar y se encuentra otra vez el botón de
    // comprar, que es justo el sitio donde no se le puede dejar dudar.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        if (params.get('rutina') !== 'ok') return;
        const sesion = params.get('session_id');
        const seguir = () => {
            // Se quita el ?rutina=ok de la barra: recargar no puede volver a sincronizar.
            window.history.replaceState({}, '', window.location.pathname);
            toast.success('Pago hecho. Tu rutina ya es tuya.');
            cargarPeticion(); cargarPdf(); cargarSemana(); fetchRoutine();
        };
        // El `{CHECKOUT_SESSION_ID}` sin sustituir significa que no venimos de Stripe.
        if (sesion && !sesion.includes('{')) {
            api.post('/billing/checkout-session/sync', { session_id: sesion })
                .catch(e => console.error('[rutina: vuelta del pago]', e?.response?.data || e))
                .finally(seguir);
        } else {
            seguir();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // MARCAR el entreno de hoy: el check de T3, por el endpoint de siempre
    // (workout_logs). Marcar aquí y en la pantalla de Entreno escriben la misma fila.
    const marcarHoy = async (hoy) => {
        setMarcando(true);
        try {
            await api.post('/workout-logs', {
                hecho: true, tipo: 'entreno', estrellas: null, nota: null,
                pesos: [], compartida: false, dia_rutina: hoy.grupo || null,
            });
            toast.success('Entreno marcado.');
            cargarSemana();
        } catch { toast.error('No hemos podido marcar tu entreno. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // «Sí lo hice»: el día de esta semana que se quedó sin marcar.
    const siLoHice = async (pendiente) => {
        setMarcando(true);
        try {
            await api.post('/routines/semana/hecho', { fecha: pendiente.fecha, grupo: pendiente.grupo, hoy: new Date().toLocaleDateString('en-CA') });
            toast.success('Apuntado.');
            cargarSemana();
        } catch { toast.error('No hemos podido apuntarlo. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // «Recuperarlo otro día»: no se mueve, se recupera en un día de descanso.
    const recuperar = async (pendiente, dia) => {
        setMarcando(true);
        try {
            await api.post('/routines/semana/recuperar', { fecha_original: pendiente.fecha, fecha: dia.fecha, hoy: new Date().toLocaleDateString('en-CA') });
            toast.success(`${pendiente.grupo} pasa al ${dia.dia}.`);
            cargarSemana();
        } catch { toast.error('No hemos podido apuntar la recuperación. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // Se abre vía blob porque el visor del navegador no manda el token (mismo camino que
    // EntrenoPage).
    const abrirPdf = async () => {
        try {
            const r = await api.get('/routines/pdf', { responseType: 'blob' });
            window.open(URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })), '_blank');
        } catch { toast.error('No hemos podido abrir tu rutina. Inténtalo en un momento.'); }
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { fetchRoutine(); }, []);

    const fetchRoutine = async () => {
        setFallo(false);
        try {
            const [currentRes, historyRes] = await Promise.all([
                api.get('/routines/current'),
                api.get('/routines/history')
            ]);
            setRoutine(currentRes.data);
            setRoutineHistory(historyRes.data || []);
            const today = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
            setSelectedDay(today);
        } catch (error) {
            console.error('Error fetching routine:', error);
            // UN 500 NO ES «SIN RUTINA» (24-08). Un 403, un 402 o un 404 son estados
            // normales aquí -- su plan no la lleva, la suscripción no está al día, aún no
            // hay perfil -- y la pantalla ya sabe qué decir en cada uno. Pero cuando la
            // petición reventaba (un ejercicio con las series en blanco tumba
            // GET /current entero) el cliente leía «Sin rutina asignada» teniendo la suya
            // puesta, y el panel le decía «Activa».
            const estado = error?.response?.status;
            if (!estado || estado >= 500) setFallo(true);
        } finally {
            setLoading(false);
        }
    };

    const getDayData = (day) => routine?.days?.find(d => d.day.toLowerCase() === day);
    const todayName = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
    const dayRoutine = getDayData(selectedDay);
    const trainingDays = routine?.days?.filter(d => !d.is_rest).length || 0;
    const totalExercises = routine?.days?.reduce((sum, d) => sum + (d.exercises?.length || 0), 0) || 0;

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-4">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-20 bg-muted rounded-2xl" />
            <div className="h-64 bg-muted rounded-2xl" />
        </div></Wrap>;
    }

    if (!routine) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6" data-testid="routine-heading">Mi rutina</h1>
            {pdfInfo ? (
                /* Sin rutina estructurada pero CON PDF: esa ES su rutina, no un «sin rutina
                   asignada». Se enseña ENTERA aquí dentro (Jesús, 24-08), y encima la
                   semana -- cabecera, tira, hoy y lo pendiente -- cuando hay reparto y sus
                   días puestos, que es el apartado 12. */
                <div className="space-y-5" data-testid="routine-content">
                    {semana?.hay && (
                        /* Sin el «Abrir el PDF» de la cabecera: la rutina está justo
                           debajo, y dos botones para lo mismo a dos dedos uno de otro
                           solo hacen dudar. */
                        <SemanaDeRutina semana={semana} abrirPdf={abrirPdf}
                            onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                            marcando={marcando} />
                    )}
                    <VistaPreviaPdf api={api} info={pdfInfo} abrirPdf={abrirPdf} />
                </div>
            ) : (
                <div className="surface p-10 text-center" data-testid="routine-content">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Dumbbell className="w-8 h-8 text-brand/60" />
                    </div>
                    {fallo ? (
                        /* No es que no tenga rutina: es que no hemos podido traerla. */
                        <div data-testid="routine-fallo">
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">No hemos podido cargar tu rutina</h2>
                            <p className="text-muted-foreground text-sm mb-5 max-w-sm mx-auto">
                                Ha sido cosa nuestra, no tuya. Inténtalo otra vez en un momento y, si sigue igual, dínoslo por el chat.
                            </p>
                            <button onClick={fetchRoutine} data-testid="routine-reintentar" className="btn-brand">
                                Volver a intentarlo
                            </button>
                        </div>
                    ) : (rutinaIncluida === null && !planTardaDemasiado) ? (
                        /* Todavía no sabemos qué plan tiene: ni oferta ni «tu entrenador la
                           está preparando». Un esqueleto dura lo que tarda el catálogo
                           (milisegundos) y no dice ninguna mentira. */
                        <div data-testid="rutina-plan-cargando" className="animate-pulse space-y-3 max-w-sm mx-auto">
                            <div className="h-6 bg-muted rounded w-2/3 mx-auto" />
                            <div className="h-4 bg-muted rounded w-full" />
                            <div className="h-4 bg-muted rounded w-4/5 mx-auto" />
                        </div>
                    ) : rutinaIncluida === null ? (
                        /* El catálogo no ha llegado y ya no va a llegar: lo neutro, que es
                           verdad en los dos casos. Sin botón de pagar. */
                        <>
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Sin rutina asignada</h2>
                            <p className="text-muted-foreground text-sm">Aquí verás tu rutina en cuanto la tengas. Si crees que ya debería estar, dínoslo por el chat.</p>
                        </>
                    ) : rutinaIncluida ? (
                        <>
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Sin rutina asignada</h2>
                            <p className="text-muted-foreground text-sm">Tu entrenador está preparando tu rutina personalizada.</p>
                        </>
                    ) : (compraHecha || peticion) ? (
                        /* Ya la pidió: lo que se le enseña es cuándo, no otra vez el botón
                           de 57 €. `compraHecha` es el mensaje de este mismo momento;
                           `peticion` es lo que quedó apuntado en su ficha y sobrevive a
                           recargar la pantalla. */
                        <p className="text-sm text-foreground max-w-sm mx-auto" data-testid="rutina-compra-hecha">
                            {compraHecha || textoDeLaPeticion(peticion)}
                        </p>
                    ) : rutinaDelMesLista === false ? (
                        /* NO SE OFRECE LO QUE NO HAY (verificación 24-08, fallo 14): sin
                           rutina del mes preparada, ni botón ni precio. El servidor también
                           lo rechaza, pero un botón de pagar que rebota es peor que no
                           tenerlo. */
                        <div data-testid="rutina-del-mes-no-lista">
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Tu plan no incluye rutina</h2>
                            <p className="text-muted-foreground text-sm max-w-sm mx-auto">
                                La rutina de este mes todavía no está lista. En cuanto la tengamos podrás pedirla desde aquí.
                            </p>
                        </div>
                    ) : rutinaDelMesLista === null ? (
                        /* Igual que con el plan: la oferta no se pinta hasta saber que hay
                           algo que vender. */
                        <div data-testid="rutina-oferta-cargando" className="animate-pulse space-y-3 max-w-sm mx-auto">
                            <div className="h-6 bg-muted rounded w-2/3 mx-auto" />
                            <div className="h-4 bg-muted rounded w-full" />
                        </div>
                    ) : (
                        /* Su plan no lleva rutina: el aviso y el botón de compra del
                           DECIDIDO (P72, doc 23-08), con el precio delante. */
                        <div data-testid="quiero-mi-rutina">
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Tu plan no incluye rutina</h2>
                            {/* YA NO SE COBRA EN LA TARJETA GUARDADA (24-08). Esta pantalla
                                manda al checkout de Stripe, así que decirle «se cobra en la
                                tarjeta que ya tienes guardada» era mentira justo donde se
                                paga: el que viene de Calma no tiene ninguna guardada. */}
                            <p className="text-muted-foreground text-sm max-w-sm mx-auto mb-5">
                                Si quieres, te preparamos la rutina del mes por 57 €. Se paga con tarjeta y te mandamos la factura.
                            </p>
                            {comprando === null ? (
                                <button onClick={() => setComprando('eligiendo')} data-testid="quiero-mi-rutina-btn"
                                    className="btn-brand inline-flex items-center gap-2">
                                    Quiero mi rutina · 57 €
                                </button>
                            ) : (
                                <div className="max-w-sm mx-auto space-y-2">
                                    <p className="text-sm text-foreground/80">¿Cómo la quieres?</p>
                                    <div className="flex gap-2 justify-center">
                                        <button onClick={() => comprarRutina('basica')} disabled={comprando !== 'eligiendo'}
                                            data-testid="rutina-basica"
                                            className="btn-brand px-5 disabled:opacity-50">
                                            {comprando === 'basica' ? 'Un momento...' : 'Básica'}
                                        </button>
                                        <button onClick={() => comprarRutina('avanzada')} disabled={comprando !== 'eligiendo'}
                                            data-testid="rutina-avanzada"
                                            className="btn-brand px-5 disabled:opacity-50">
                                            {comprando === 'avanzada' ? 'Un momento...' : 'Avanzada'}
                                        </button>
                                        <button onClick={() => setComprando(null)} disabled={comprando !== 'eligiendo'}
                                            className="px-4 rounded-xl border border-border text-sm text-foreground/70">
                                            Ahora no
                                        </button>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground">Al elegirla te llevamos a la pantalla de pago de los 57 €. Al volver la tienes aquí.</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </Wrap>;
    }

    return (
        <Wrap>
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="routine-heading">Mi rutina</h1>
                <button onClick={() => setShowHistory(!showHistory)} data-testid="toggle-history-btn"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <History className="w-4 h-4" /> {showHistory ? 'Actual' : 'Historial'}
                </button>
            </div>

            {showHistory ? (
                <div className="space-y-3 max-w-2xl" data-testid="routine-history">
                    {routineHistory.length > 0 ? routineHistory.map((r, i) => (
                        <div key={r.id} className={`surface p-4 flex items-center justify-between ${i === 0 ? 'border-brand/40' : ''}`}>
                            <div>
                                <p className="font-semibold text-foreground text-sm">{new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
                                <p className="text-xs text-muted-foreground">{plural(r.days?.filter(d => !d.is_rest).length || 0, 'día')} de entreno</p>
                            </div>
                            {i === 0 && <span className="badge-elm">Actual</span>}
                        </div>
                    )) : <p className="text-center text-muted-foreground py-10 text-sm">No hay rutinas anteriores.</p>}
                </div>
            ) : (
                <div className="space-y-5">
                    {/* La semana (7.1 del 21-08): también con rutina estructurada, que
                        es la que pone los grupos si el PDF no trae reparto. */}
                    <SemanaDeRutina semana={semana} abrirPdf={abrirPdf} tienePdf={!!pdfInfo}
                        onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                        marcando={marcando} />

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-3 sm:gap-4 max-w-2xl">
                        <StatCard value={trainingDays} label="Días entreno" color={MACRO_O} icon={Dumbbell} testId="stat-training-days" />
                        <StatCard value={totalExercises} label="Ejercicios" color="#16A34A" icon={Trophy} testId="stat-exercises" />
                        <StatCard value={7 - trainingDays} label="Descanso" color="#7C3AED" icon={Moon} testId="stat-rest-days" />
                    </div>

                    {/* Day selector + detail */}
                    <div className="grid lg:grid-cols-12 gap-5 items-start">
                        {/* Selector: horizontal en móvil, vertical en desktop */}
                        <div className="lg:col-span-4">
                            <p className="caption mb-2 hidden lg:block">Días</p>
                            <div className="grid grid-cols-7 lg:grid-cols-1 gap-1.5 lg:gap-2" data-testid="day-selector">
                                {DAYS_ES.map((day) => {
                                    const d = getDayData(day);
                                    const isToday = todayName === day;
                                    const selected = selectedDay === day;
                                    const isRest = d?.is_rest;
                                    return (
                                        <button key={day} onClick={() => setSelectedDay(day)} data-testid={`day-btn-${slug(day)}`}
                                            className={`relative rounded-xl transition-all border
                                                flex flex-col items-center py-2.5 lg:flex-row lg:items-center lg:justify-between lg:px-4 lg:py-3
                                                ${selected ? 'bg-brand text-white border-brand shadow-sm' : 'bg-card border-border hover:border-border'}`}>
                                            {/* Mobile */}
                                            <span className={`lg:hidden text-[11px] font-bold uppercase ${selected ? 'text-white' : 'text-foreground'}`}>{DAY_LABELS[day]}</span>
                                            <span className="lg:hidden text-[9px] mt-0.5">
                                                {isRest ? <Moon className={`w-3 h-3 ${selected ? 'text-white/80' : 'text-muted-foreground'}`} /> : <span className={selected ? 'text-white/80 font-data' : 'text-muted-foreground font-data'}>{d?.exercises?.length || 0}</span>}
                                            </span>
                                            {/* Desktop */}
                                            <span className="hidden lg:flex items-center gap-2">
                                                <span className={`text-sm font-semibold capitalize ${selected ? 'text-white' : 'text-foreground'}`}>{day}</span>
                                                {isToday && <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${selected ? 'bg-white/20 text-white' : 'bg-brand/10 text-brand'}`}>Hoy</span>}
                                            </span>
                                            <span className="hidden lg:flex items-center gap-1 text-xs">
                                                {isRest
                                                    ? <span className={`flex items-center gap-1 ${selected ? 'text-white/80' : 'text-muted-foreground'}`}><Moon className="w-3.5 h-3.5" /> Descanso</span>
                                                    : <span className={`font-data ${selected ? 'text-white/90' : 'text-muted-foreground'}`}>{d?.exercises?.length || 0} ej</span>}
                                            </span>
                                            {isToday && <span className={`lg:hidden absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${selected ? 'bg-card' : 'bg-brand'}`} />}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Detail */}
                        <div className="lg:col-span-8 space-y-3">
                            {dayRoutine ? (
                                dayRoutine.is_rest ? (
                                    <div className="surface p-8 text-center">
                                        <Moon className="w-10 h-10 text-violet-400 mx-auto mb-3" />
                                        <h3 className="font-heading text-xl font-bold uppercase text-foreground mb-1">Día de descanso</h3>
                                        <p className="text-muted-foreground text-sm">Recupera energías. Tu cuerpo crece mientras descansas.</p>
                                    </div>
                                ) : (
                                    <div className="space-y-3" data-testid="exercises-list">
                                        {dayRoutine.exercises?.map((exercise, index) => (
                                            <ExerciseCard key={index} exercise={exercise} index={index} />
                                        ))}
                                    </div>
                                )
                            ) : (
                                <div className="surface p-8 text-center"><p className="text-muted-foreground text-sm">No hay ejercicios programados para este día.</p></div>
                            )}

                            {dayRoutine && !dayRoutine.is_rest && dayRoutine.cardio && (
                                <div className="surface bg-brand/[0.04] border-brand/20 p-4 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-brand/15 rounded-xl flex items-center justify-center flex-shrink-0">
                                        <Flame className="w-5 h-5 text-brand" />
                                    </div>
                                    <div>
                                        <p className="font-bold text-foreground text-sm uppercase">Cardio · {dayRoutine.cardio.type}</p>
                                        <p className="text-xs text-muted-foreground">{dayRoutine.cardio.duration}{dayRoutine.cardio.notes && ` - ${dayRoutine.cardio.notes}`}</p>
                                    </div>
                                </div>
                            )}

                            {routine.trainer_notes && (
                                <div className="surface bg-brand/[0.04] border-brand/20 p-4">
                                    <p className="text-[11px] font-bold text-brand uppercase tracking-wider mb-1.5">Notas del entrenador</p>
                                    <p className="text-sm text-muted-foreground leading-relaxed">{routine.trainer_notes}</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Si además hay PDF, la estructurada manda y el PDF queda de enlace
                        secundario (mismo patrón que el botón de EntrenoPage). */}
                    {pdfInfo && (
                        <button onClick={abrirPdf} data-testid="routine-pdf-link"
                            className="w-full max-w-2xl flex items-center justify-between p-4 bg-card border border-border rounded-2xl hover:border-white/30 transition-colors">
                            <span className="flex items-center gap-2 font-bold text-foreground text-sm">
                                <FileText className="w-4 h-4 text-brand" /> Tu rutina en PDF
                            </span>
                            <ChevronRight className="w-4 h-4 text-foreground/40" />
                        </button>
                    )}
                </div>
            )}
        </Wrap>
    );
};

const MACRO_O = '#FF671F';

const StatCard = ({ value, label, color, icon: Icon, testId }) => (
    <div className="surface p-4 text-center" data-testid={testId}>
        <div className="flex items-center justify-center gap-1.5 mb-1">
            <Icon className="w-4 h-4" style={{ color }} />
            <span className="font-heading text-3xl font-bold" style={{ color }}>{value}</span>
        </div>
        <p className="text-[11px] text-muted-foreground uppercase tracking-wider font-semibold">{label}</p>
    </div>
);

const ExerciseCard = ({ exercise, index }) => {
    const [expanded, setExpanded] = useState(false);
    const totalSets = exercise.sets || 0;
    return (
        <div className="surface surface-hover overflow-hidden" data-testid={`exercise-${index}`}>
            <button className="w-full flex items-center gap-3 p-4 text-left" onClick={() => setExpanded(!expanded)}>
                <div className="w-10 h-10 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                    <span className="font-heading text-lg font-bold text-brand">{index + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-foreground text-sm">{exercise.name}</p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <span className="flex items-center gap-1"><Repeat className="w-3.5 h-3.5" /><span className="text-brand font-bold font-data">{totalSets}</span> × {exercise.reps}</span>
                        <span className="flex items-center gap-1"><Timer className="w-3.5 h-3.5" /> {exercise.rest}</span>
                    </div>
                </div>
                {(exercise.notes || exercise.video_url) && (expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />)}
            </button>
            {expanded && (exercise.notes || exercise.video_url) && (
                <div className="px-4 pb-4 pt-0 space-y-2 border-t border-border">
                    {exercise.notes && <p className="text-xs text-muted-foreground italic pt-3 pl-13" style={{ paddingLeft: '3.25rem' }}>{exercise.notes}</p>}
                    {exercise.video_url && (
                        <a href={exercise.video_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs text-brand hover:underline pt-1 font-semibold">
                            <Play className="w-3 h-3" /> Ver vídeo
                        </a>
                    )}
                </div>
            )}
        </div>
    );
};

export default RoutinePage;
