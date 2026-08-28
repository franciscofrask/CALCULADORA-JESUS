import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { plural } from '../lib/labels';
import { abrirRutinaPdf } from '../lib/abrirRutina';
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
// `onElegirDia` y `diaElegido` solo llegan cuando ademas hay rutina estructurada: entonces
// esta tira ES el selector de dia, porque debajo habia OTRA lista con los mismos siete dias
// (Francisco, 27-08: «está la misma información repetida dos veces»). Sin rutina
// estructurada no hay nada que elegir y las casillas se quedan como estaban.
const SemanaDeRutina = ({ semana, abrirPdf, tienePdf, onMarcarHoy, onSiLoHice, onRecuperar, marcando,
                         onElegirDia, diaElegido }) => {
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
        <div className="space-y-3 min-w-0" data-testid="semana-rutina">
            {/* Cabecera: qué rutina es, por qué semana va y el PDF a un toque. */}
            <div className="surface p-4 flex items-center justify-between gap-3 flex-wrap">
                <p className="font-bold text-foreground text-sm" data-testid="semana-rutina-cabecera">{cab}</p>
                {tienePdf && (
                    <button onClick={abrirPdf} data-testid="semana-rutina-pdf"
                        className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline underline-offset-4">
                        {/* «Ver PDF», la misma palabra que el botón de abajo: los dos abren
                            lo mismo y no pueden llamarse distinto (Francisco, 27-08). */}
                        <FileText className="w-4 h-4" /> Ver PDF
                    </button>
                )}
            </div>

            {/* La tira de la semana: L a D con el grupo o la luna del descanso. */}
            <div className="grid grid-cols-7 gap-1.5" data-testid="semana-rutina-tira">
                {dias.map(d => {
                    const Casilla = onElegirDia ? 'button' : 'div';
                    const elegido = onElegirDia && diaElegido === d.dia;
                    return (
                    <Casilla key={d.fecha} data-testid={`semana-dia-${d.fecha}`}
                        {...(onElegirDia ? { type: 'button', onClick: () => onElegirDia(d.dia),
                                             'aria-pressed': elegido } : {})}
                        // El padding lateral va al mínimo: son siete casillas repartiéndose
                        // 390 px y cada píxel que se come el hueco se lo quita al nombre del
                        // grupo. Ver el `truncate` de abajo.
                        className={`rounded-xl border px-0.5 py-2 text-center min-w-0 w-full
                            ${onElegirDia ? 'transition-colors hover:border-brand/50' : ''}
                            ${elegido ? 'border-brand bg-brand/20'
                                : d.hoy ? 'border-brand bg-brand/10' : 'border-border bg-card'}`}>
                        <p className={`text-[10px] font-bold uppercase ${d.hoy ? 'text-brand' : 'text-muted-foreground'}`}>
                            {DAY_LABELS[d.dia]}
                        </p>
                        <div className="mt-1 h-8 flex flex-col items-center justify-center">
                            {d.entrena ? (
                                <>
                                    {/* SIN PADDING PROPIO: la casilla ya lo pone. En 390 px
                                        quedaban 34 px útiles y «Entreno» pide 38, así que la
                                        palabra corriente de un día de entreno salía cortada
                                        («Entr...») en la mitad de la semana (Francisco,
                                        26-08). Los nombres de grupo largos sí se cortan, y
                                        para eso está el `title`; pero la palabra genérica
                                        tiene que caber entera. */}
                                    <p className="text-[9px] font-semibold text-foreground leading-tight truncate w-full"
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
                    </Casilla>
                    );
                })}
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
// LA TARJETA DE LA RUTINA
//
// Aquí hubo una vista previa: el PDF se descargaba y se pintaba dentro de la pantalla, en
// un `<object>`. Se quita (Francisco, 27-08).
//
// No se pierde nada, y se dijo desde que se montó: un PDF metido en la página se porta mal
// fuera del escritorio. Safari de iOS pinta la primera página y no deja pasar de ahí, y
// Chrome de Android muchas veces ni la pinta. O sea que a quien lo abre desde el móvil --
// que es casi todo el mundo -- la vista previa le enseñaba una hoja muerta, y para leer su
// rutina tenía que pulsar el botón igual. Encima se bajaba entre 300 KB y 4,6 MB para eso.
//
// Queda el botón, que es el camino que siempre funcionó. Y se abre pidiendo la ventana
// DENTRO del gesto del dedo (lib/abrirRutina), que es lo que hacía que en el iPhone no
// pasara nada.
//
// EL RÓTULO DEL BOTÓN: «Ver PDF» (Francisco, 27-08). OJO, porque contradice al vídeo de esa
// misma mañana: en el minuto 8:46 Jesús dice «olvida el PDF, olvida la palabra PDF, eso no
// tiene sentido», y por eso ponía «Abrirla entera». Manda lo último que se ha pedido, pero
// si Jesús vuelve a verlo va a preguntar, así que queda escrito de dónde viene cada cosa.
// La fecha se queda -- saber de cuándo es sí le dice algo.
// ─────────────────────────────────────────────────────────────────────────────
const TarjetaDeLaRutina = ({ info, abrirPdf }) => (
    <div className="surface p-4 sm:p-5 min-w-0" data-testid="routine-pdf-preview">
        <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
                <h2 className="font-heading text-xl font-bold uppercase text-foreground leading-tight">Tu rutina</h2>
                <p className="text-muted-foreground text-sm">
                    Preparada el {new Date(info.uploaded_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })}.
                </p>
            </div>
            <button onClick={abrirPdf} data-testid="routine-pdf-btn"
                className="btn-brand inline-flex items-center gap-2 shrink-0">
                Ver PDF <ChevronRight className="w-4 h-4" />
            </button>
        </div>
    </div>
);

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

    // Se abre vía blob porque el visor del navegador no manda el token. La ventana se abre
    // dentro del toque y luego se le pone el fichero: ver lib/abrirRutina, que es donde está
    // contado por qué en el iPhone no abría.
    const abrirPdf = () => abrirRutinaPdf(api);

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
                /* UNA SOLA COLUMNA PARA TODO (Francisco, 25-08: «que quede todo en la
                   misma columna»). El ancho se decide aqui y una sola vez: antes cada caja
                   llevaba el suyo -- unas `max-w-2xl`, otras `max-w-3xl` y el bloque de
                   dias ninguno, asi que ese se iba a los 1.200 px del marco y rompia la
                   alineacion con todo lo de arriba. */
                <div className="space-y-5 max-w-2xl mx-auto" data-testid="routine-content">
                    {semana?.hay && (
                        /* Sin el «Abrir el PDF» de la cabecera: la rutina está justo
                           debajo, y dos botones para lo mismo a dos dedos uno de otro
                           solo hacen dudar. */
                        <SemanaDeRutina semana={semana} abrirPdf={abrirPdf}
                            onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                            marcando={marcando} />
                    )}
                    <TarjetaDeLaRutina info={pdfInfo} abrirPdf={abrirPdf} />
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
                <div className="space-y-3 max-w-2xl mx-auto" data-testid="routine-history">
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
                <div className="space-y-5 max-w-2xl mx-auto">
                    {/* La semana (7.1 del 21-08): también con rutina estructurada, que
                        es la que pone los grupos si el PDF no trae reparto. */}
                    <SemanaDeRutina semana={semana} abrirPdf={abrirPdf} tienePdf={!!pdfInfo}
                        onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                        marcando={marcando}
                        onElegirDia={setSelectedDay} diaElegido={selectedDay} />

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-3 sm:gap-4">
                        <StatCard value={trainingDays} label="Días entreno" color={MACRO_O} icon={Dumbbell} testId="stat-training-days" />
                        <StatCard value={totalExercises} label="Ejercicios" color="#16A34A" icon={Trophy} testId="stat-exercises" />
                        <StatCard value={7 - trainingDays} label="Descanso" color="#7C3AED" icon={Moon} testId="stat-rest-days" />
                    </div>

                    {/* Day selector + detail */}
                    {/* APILADO, Y EL DETALLE ARRIBA (Francisco, 25-08). Estaba en dos
                        columnas -- la lista de dias a la izquierda, el detalle a la
                        derecha -- y en un dia de descanso esa mitad derecha era una linea
                        de texto con media pantalla de hueco debajo. Ahora va lo que toca
                        hoy, debajo la lista de dias y debajo el PDF: se lee de arriba abajo
                        y no queda ningun hueco. */}
                    {/* Lo que toca hoy (o el dia que se elija abajo). */}
                    <div className="space-y-3">
                        {dayRoutine ? (
                            dayRoutine.is_rest ? (
                                /* EN UN DIA DE DESCANSO, AQUI NO VA NADA (Francisco, 27-08).
                                   Primero fue un panel entero, luego una linea («Dia de
                                   descanso. Tu cuerpo crece mientras descansas»), y las dos
                                   veces sobraba por lo mismo: la tira de arriba ya pinta la
                                   luna en ese dia, y si es hoy encima lo dice con palabras
                                   («Hoy no entrenas»). Decirlo una tercera vez no añade
                                   nada. */
                                null
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

                    {/* AQUÍ HABÍA LA MISMA SEMANA OTRA VEZ (Francisco, 27-08: «está la misma
                        información repetida dos veces»). Una lista de los siete días con su
                        «Descanso» o su «N ej», justo debajo de la tira de arriba, que ya dice
                        lo mismo con el grupo de cada día. Y detrás, un segundo «Ver PDF»
                        idéntico al de la cabecera.
                        Se van los dos. Elegir día no se pierde: ahora se toca la casilla de
                        la tira de arriba, que además es la que sabe si ese día está hecho o
                        se recuperó. Una semana, no dos. */}
                </div>
            )}
        </Wrap>
    );
};

const MACRO_O = '#FF671F';

// El padding lateral se estrecha en el móvil: son tres tarjetas repartiéndose el ancho, y
// con `p-4` en 360 px quedaban 61 px útiles mientras «Ejercicios» pide 70. La palabra se
// salía de su tarjeta. A 390 px cabía por poco, así que solo se veía en los móviles
// estrechos (26-08).
const StatCard = ({ value, label, color, icon: Icon, testId }) => (
    <div className="surface py-4 px-2 sm:px-4 text-center" data-testid={testId}>
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
