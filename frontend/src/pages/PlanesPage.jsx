/**
 * PlanesPage - Elegir nivel.
 *
 * La comparativa de la parte 1 de la especificación del 31-07-2026, tal cual: tres
 * niveles, ciclos de 12 semanas, y lo que incluye cada uno fila a fila.
 *
 * Dos cosas que no son de estilo:
 *   - El Nivel 3 no lleva a un pago, lleva a agendar una llamada ("cómo se compra: por
 *     llamada"). Cobrar 1.500 € sin hablar antes con la persona no es lo que se quiere.
 *   - Lo que se enseña sale del catálogo del servidor, no de una copia aquí. Si Jesús
 *     cambia un precio o una habilitación desde el panel, esta pantalla cambia con él.
 *     Solo las filas descriptivas que no tienen equivalente en el catálogo (llamada
 *     inicial, videollamada) están escritas aquí.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Check, Minus, Phone, Loader2, ArrowLeft, ArrowRight, Compass, RotateCcw } from 'lucide-react';

const ORDEN = ['nivel1', 'nivel2', 'nivel3'];

// Resultado del test de nivel (/test). Lo deja ahí el propio test, en el mismo
// sessionStorage, para que sobreviva al registro: quien lo hace sin cuenta pasa por
// /auth antes de llegar aquí y su resultado tiene que seguir en pie al aterrizar.
const CLAVE_TEST = 'quiz_venta_resultado';

const leerResultadoTest = () => {
    try {
        const crudo = sessionStorage.getItem(CLAVE_TEST);
        return crudo ? JSON.parse(crudo) : null;
    } catch {
        return null;   // modo privado o JSON de otra versión: como si no hubiera test
    }
};

// Lo que el catálogo no sabe decir por sí solo. Se indexa por código de plan para que
// añadir un nivel no obligue a tocar la tabla entera.
const DETALLE = {
    nivel1: {
        gancho: 'Te lo montas tú, con el método detrás',
        macros: 'Automáticos',
        ajuste: 'Cada 4 semanas',
        chat: false, llamadaInicial: false, videollamada: false, seguimiento: null,
    },
    nivel2: {
        gancho: 'Con un entrenador encima de tus números',
        macros: 'Los revisa el equipo',
        ajuste: 'Cada 2 semanas',
        chat: true, llamadaInicial: false, videollamada: false, seguimiento: 'Quincenal',
        destacado: true,
    },
    nivel3: {
        gancho: 'Todo lo anterior, y hablamos',
        macros: 'Los revisa el equipo',
        ajuste: 'Cada 2 semanas',
        chat: true, llamadaInicial: true, videollamada: 'Mensual', seguimiento: 'Semanal',
        porLlamada: true,
    },
};

const Si = () => <Check className="w-4 h-4 text-emerald-500 mx-auto" />;
const No = () => <Minus className="w-4 h-4 text-muted-foreground/40 mx-auto" />;
const Texto = ({ children }) => (
    <span className="text-[13px] text-foreground">{children || <No />}</span>
);

const PlanesPage = () => {
    const { api, profile, refreshProfile } = useAuth();
    const navigate = useNavigate();
    const [planes, setPlanes] = useState(null);
    const [comprando, setComprando] = useState(null);
    // Se lee UNA vez al montar: el test lo borra de sessionStorage nada más leerlo, para
    // que no persiga al cliente por toda la sesión, pero sigue en pantalla mientras elige.
    const [resultadoTest] = useState(leerResultadoTest);
    // Volviendo de pagar no se enseña la comparativa ni un fotograma: acaba de elegir plan,
    // volver a ponerle los tres delante mientras se confirma el cobro es desconcertante.
    // Se decide en el primer render, antes de pintar nada.
    const [confirmando, setConfirmando] = useState(
        () => new URLSearchParams(window.location.search).get('checkout') === 'success');

    useEffect(() => {
        if (resultadoTest) {
            try { sessionStorage.removeItem(CLAVE_TEST); } catch { /* modo privado */ }
        }
    }, [resultadoTest]);

    useEffect(() => {
        api.get('/plans?estado=activo')
            .then(r => setPlanes(r.data))
            .catch(() => toast.error('No hemos podido cargar los planes'));
    }, [api]);

    // Vuelta de Stripe. Antes esta pantalla mandaba a /dashboard?alta=ok y NADIE
    // confirmaba el pago: el cliente pagaba, aterrizaba en su panel y su plan solo se
    // activaba cuando llegara el webhook. Si tardaba o fallaba, había pagado y no veía
    // nada. Esto lo hacía bien /onboarding y se trae aquí al unificar las dos pantallas.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const checkout = params.get('checkout');
        if (checkout === 'success') {
            const sessionId = params.get('session_id');
            (async () => {
                try {
                    if (sessionId) {
                        await api.post('/billing/checkout-session/sync', { session_id: sessionId });
                    }
                    // El perfil recién confirmado decide el destino AQUÍ. Antes se pasaba
                    // siempre por /dashboard y era el panel el que reenviaba al
                    // cuestionario: el cliente veía su panel medio segundo y saltaba solo.
                    const fresco = await api.get('/clients/profile')
                        .then(r => r.data).catch(() => null);
                    await refreshProfile();
                    toast.success('¡Pago confirmado! Tu plan está activo');
                    const alCuestionario = fresco?.status === 'activo' && !fresco?.questionnaire_completed;
                    navigate(alCuestionario ? '/questionnaire' : '/dashboard', { replace: true });
                } catch {
                    setConfirmando(false);   // que vuelva a ver los planes y no un spinner eterno
                    toast.error('No pudimos confirmar el pago. Si te cobraron, recarga en unos segundos.');
                }
            })();
        } else if (checkout === 'canceled') {
            toast.info('Pago cancelado. Puedes elegir un plan cuando quieras.');
            window.history.replaceState({}, '', '/planes');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al montar
    }, []);

    const comprar = async (code) => {
        setComprando(code);
        try {
            const r = await api.post('/billing/checkout-session', {
                plan: code,
                success_path: '/planes?checkout=success',
                cancel_path: '/planes?checkout=canceled',
            });
            if (r.data?.checkout_url) window.location.href = r.data.checkout_url;
            else toast.error('No hemos podido abrir el pago');
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'No hemos podido abrir el pago');
            setComprando(null);
        }
    };

    // Vuelta del pago: una sola pantalla honesta mientras se confirma con Stripe, y de
    // ahí directo a donde toque. Sin comparativa de por medio y sin pasar por el panel.
    if (confirmando) {
        return (
            <div className="min-h-[70vh] flex flex-col items-center justify-center px-6 text-center"
                data-testid="planes-confirmando">
                <Loader2 className="w-8 h-8 animate-spin text-brand mb-5" />
                <p className="font-heading text-2xl font-bold uppercase text-foreground">
                    Confirmando tu pago
                </p>
                <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                    Es cosa de un par de segundos. No cierres esta pantalla.
                </p>
            </div>
        );
    }

    if (!planes) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-brand" />
            </div>
        );
    }

    // Solo los tres niveles y en su orden. La membresía no sale aquí: es la salida del
    // que no renueva, no algo que se compre.
    const visibles = ORDEN.filter(c => planes[c]).map(c => ({ code: c, ...planes[c], ...DETALLE[c] }));
    const actual = profile?.plan;

    const FILAS = [
        { etiqueta: 'Precio por ciclo', render: p => (
            <span className="font-heading text-2xl font-bold text-foreground">{p.precio} €</span>) },
        { etiqueta: 'Duración', render: p => <Texto>{p.ciclo?.semanas} semanas</Texto> },
        { etiqueta: 'Calculadora y menús', render: () => <Si /> },
        { etiqueta: 'Macros iniciales', render: p => <Texto>{p.macros}</Texto> },
        { etiqueta: 'Ajuste de macros', render: p => <Texto>{p.ajuste}</Texto> },
        { etiqueta: 'Reportes', render: p => (
            <Texto>{(p.habilitaciones?.reportes || []).join(' + ') || null}</Texto>) },
        { etiqueta: 'Rutina', render: p => (
            p.habilitaciones?.rutina === 'personalizada'
                ? <Texto>Personalizada</Texto>
                : <No />) },
        { etiqueta: 'Suplementación', render: p => (
            <Texto>{p.habilitaciones?.suplementacion ? 'Personalizada' : 'Sugerencia automática'}</Texto>) },
        { etiqueta: 'Chat con el equipo', render: p => (p.chat ? <Si /> : <No />) },
        { etiqueta: 'Llamada inicial', render: p => (p.llamadaInicial ? <Si /> : <No />) },
        { etiqueta: 'Videollamada', render: p => <Texto>{p.videollamada}</Texto> },
        { etiqueta: 'Seguimiento', render: p => <Texto>{p.seguimiento}</Texto> },
    ];

    const Boton = ({ plan }) => {
        if (actual === plan.code) {
            return (
                <div className="w-full h-11 rounded-xl border border-border flex items-center justify-center text-sm text-muted-foreground">
                    Tu plan actual
                </div>
            );
        }
        if (plan.porLlamada) {
            return (
                <button onClick={() => navigate('/dashboard/messages')}
                    data-testid={`agendar-${plan.code}`}
                    className="w-full h-11 rounded-xl border border-brand text-brand font-bold text-sm flex items-center justify-center gap-2 hover:bg-brand hover:text-white transition-colors">
                    <Phone className="w-4 h-4" /> Agendar una llamada
                </button>
            );
        }
        return (
            <button onClick={() => comprar(plan.code)} disabled={!!comprando}
                data-testid={`comprar-${plan.code}`}
                className="w-full h-11 rounded-xl bg-brand text-white font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-60">
                {comprando === plan.code
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <>Empezar <ArrowRight className="w-4 h-4" /></>}
            </button>
        );
    };

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto pb-24" data-testid="planes-page">
            {/* Esta pantalla va fuera del layout de cliente (no hay menú lateral del que
                tirar), así que sin esto se entra y no se sale. Al panel y no history.back():
                aquí se llega desde el panel, desde el test y desde la vuelta de Stripe, y
                volver "una atrás" en el último caso te devuelve al pago. */}
            <button onClick={() => navigate('/dashboard')} data-testid="planes-volver"
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6">
                <ArrowLeft className="w-4 h-4" /> Volver
            </button>

            <header className="text-center mb-8">
                <p className="caption text-brand mb-1">Elige cómo quieres hacerlo</p>
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none">
                    Tres formas de trabajar
                </h1>
                <p className="text-muted-foreground text-sm mt-3 max-w-lg mx-auto">
                    El método es el mismo en los tres. Lo que cambia es cuánta gente hay detrás
                    de tus números y cada cuánto se miran.
                </p>
            </header>

            {/* Elegir entre tres cosas parecidas es donde la gente se atasca y se va. El test
                de nivel ya existía (/test) pero no se llegaba a él desde ningún sitio de la
                app: solo por el enlace del embudo. Aquí, que es donde se decide, o se ofrece
                hacerlo o se le recuerda lo que le salió. */}
            {resultadoTest ? (
                <div className="surface border-brand/40 bg-brand/5 p-5 mb-8 flex flex-col sm:flex-row sm:items-center gap-4"
                    data-testid="planes-resultado-test">
                    <Compass className="w-8 h-8 text-brand flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                        <p className="caption text-brand mb-0.5">Tu test de nivel</p>
                        <p className="font-heading text-lg font-bold uppercase text-foreground leading-tight">
                            {resultadoTest.nombre || 'Ya tienes tu resultado'}
                        </p>
                        {resultadoTest.por_que && (
                            <p className="text-sm text-muted-foreground mt-1">{resultadoTest.por_que}</p>
                        )}
                        <p className="text-[13px] text-muted-foreground mt-2">
                            Es una recomendación, no una condena: puedes contratar cualquiera de los tres.
                        </p>
                    </div>
                    <button onClick={() => navigate('/test')} data-testid="planes-repetir-test"
                        className="flex-shrink-0 inline-flex items-center gap-2 text-sm font-bold text-brand hover:underline">
                        <RotateCcw className="w-4 h-4" /> Repetir el test
                    </button>
                </div>
            ) : (
                <div className="surface p-5 mb-8 flex flex-col sm:flex-row sm:items-center gap-4"
                    data-testid="planes-invitacion-test">
                    <Compass className="w-8 h-8 text-brand flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                        <p className="font-heading text-lg font-bold uppercase text-foreground leading-tight">
                            ¿No sabes cuál elegir?
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Cuatro preguntas y te decimos por dónde empezar. Un minuto, y no hace
                            falta que dejes el correo para ver el resultado.
                        </p>
                    </div>
                    <button onClick={() => navigate('/test')} data-testid="planes-hacer-test"
                        className="btn-brand flex-shrink-0 h-11 px-5 inline-flex items-center justify-center gap-2">
                        Hacer el test <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Móvil: una tarjeta por nivel. La tabla no cabe y partirla es peor. */}
            <div className="grid gap-4 lg:hidden">
                {visibles.map(plan => (
                    <div key={plan.code} data-testid={`plan-${plan.code}`}
                        className={`surface p-5 ${plan.code === resultadoTest?.plan ? 'border-brand ring-2 ring-brand/30' : plan.destacado ? 'border-brand' : ''}`}>
                        {plan.code === resultadoTest?.plan && (
                            <span className="inline-block mb-2 px-2 py-0.5 rounded-full bg-brand text-white text-[10px] font-bold uppercase tracking-wider"
                                data-testid={`plan-${plan.code}-tu-resultado`}>
                                Tu resultado
                            </span>
                        )}
                        <div className="flex items-baseline justify-between gap-3">
                            <h2 className="font-heading text-xl font-bold uppercase text-foreground">{plan.name}</h2>
                            <span className="font-heading text-2xl font-bold text-brand">{plan.precio} €</span>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 mb-4">{plan.gancho}</p>
                        <dl className="space-y-2 mb-5">
                            {FILAS.slice(2).map(f => (
                                <div key={f.etiqueta} className="flex items-center justify-between gap-3 text-[13px]">
                                    <dt className="text-muted-foreground">{f.etiqueta}</dt>
                                    <dd>{f.render(plan)}</dd>
                                </div>
                            ))}
                        </dl>
                        <Boton plan={plan} />
                    </div>
                ))}
            </div>

            {/* Escritorio: la comparativa, que es como se decide entre tres cosas */}
            <div className="hidden lg:block surface overflow-hidden">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-border">
                            <th className="w-[26%]" />
                            {visibles.map(plan => (
                                <th key={plan.code} data-testid={`plan-${plan.code}`}
                                    className={`p-5 text-left align-top ${plan.code === resultadoTest?.plan ? 'bg-brand/10' : plan.destacado ? 'bg-brand/5' : ''}`}>
                                    {plan.code === resultadoTest?.plan ? (
                                        <span className="inline-block mb-2 px-2 py-0.5 rounded-full bg-brand text-white text-[10px] font-bold uppercase tracking-wider"
                                            data-testid={`plan-${plan.code}-tu-resultado`}>
                                            Tu resultado
                                        </span>
                                    ) : plan.destacado && (
                                        <span className="inline-block mb-2 px-2 py-0.5 rounded-full bg-brand text-white text-[10px] font-bold uppercase tracking-wider">
                                            El más elegido
                                        </span>
                                    )}
                                    <p className="font-heading text-xl font-bold uppercase text-foreground">{plan.name}</p>
                                    <p className="text-[13px] text-muted-foreground mt-1 min-h-[2.5rem]">{plan.gancho}</p>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {FILAS.map((f, i) => (
                            <tr key={f.etiqueta} className={i % 2 ? 'bg-muted/20' : ''}>
                                <th className="px-5 py-3 text-left text-[13px] font-normal text-muted-foreground">
                                    {f.etiqueta}
                                </th>
                                {visibles.map(plan => (
                                    <td key={plan.code}
                                        className={`px-5 py-3 text-center ${plan.destacado ? 'bg-brand/5' : ''}`}>
                                        {f.render(plan)}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        <tr>
                            <td />
                            {visibles.map(plan => (
                                <td key={plan.code} className={`p-5 ${plan.destacado ? 'bg-brand/5' : ''}`}>
                                    <Boton plan={plan} />
                                </td>
                            ))}
                        </tr>
                    </tbody>
                </table>
            </div>

            <p className="text-center text-[11px] text-muted-foreground mt-6">
                Todos los ciclos son de 12 semanas y se renuevan al mismo precio. Tu precio se
                queda congelado mientras no te des de baja.
            </p>
        </div>
    );
};

export default PlanesPage;
