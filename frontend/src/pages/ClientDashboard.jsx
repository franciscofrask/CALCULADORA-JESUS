import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { leer as leerLocal, escribir as escribirLocal } from '../lib/almacenLocal';
import { plural, nombreDePlan } from '../lib/labels';
import { num1 } from '../lib/numeros';
import { objetivoDelDia, varianteDelDia } from '../lib/estadoMacros';
import {
    aFecha, diaLocal, hoyLocal, etiquetaMomento, fechaLargaDeHoy, textoPlazo,
} from '../lib/horaEspana';
import { useEsTelefono } from '../lib/esTelefono';
import { useOnboarding } from '../context/OnboardingContext';
import { Card, CardContent } from '../components/ui/card';
import BodyFatSlider from '../components/SelectorGrasa';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Home, Dumbbell, Apple, FileText, MessageCircle, User,
    LogOut, Bell, ChevronRight, CreditCard, Target, Bot,
    Flame, Activity, Scale, Search, SlidersHorizontal, Pill,
    ClipboardCheck, Menu, X, PanelLeftClose, PanelLeftOpen,
    CheckCircle2, Circle, Sparkles, LayoutDashboard, AlertTriangle, Phone, Clock, TrendingUp, Moon,
    CalendarRange
} from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import { verComo } from '../lib/modoRevision';
import { seLeOfreceLaRevision } from '../lib/revision';
import LimiteDeError from '../components/LimiteDeError';
import TuDietaHoy from '../components/inicio/TuDietaHoy';
import ExtrasDelDia from '../components/nutrition/ExtrasDelDia';
import HeroInicio from '../components/inicio/BannerInicio';
import BottomNav from '../components/BottomNav';

// ===== Macro colors (identidad 12EN12) =====
const MACRO = { protein: '#FF671F', carbs: '#2196F3', fat: '#FFA500' };

// testids ASCII-estables (sin diacríticos)
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-');

// ===== Shared brand bits =====
const JG12Logo = ({ size = 'md', tone = 'dark' }) => <Logo12EN12 size={size} tone={tone} />;

const PlanBadge = ({ plan, planName }) => {
    // EL NOMBRE DEL PLAN, NO SU CÓDIGO (#64 del informe del 15-08: «RETO12EN12_GOLD»).
    // Donde se pasaba `planName` ya salía bien; donde no -- la tabla de clientes y la de
    // rutinas -- caía en `plan.toUpperCase()` y el panel gritaba el código de la base. El
    // nombre está en el catálogo, que ya viaja en el contexto de sesión.
    const { planCatalog } = useAuth();
    // Quitar el sufijo "(legacy)" de la insignia: es info interna, no de cara al usuario.
    const label = (planName || (plan ? nombreDePlan(plan, planCatalog) : '') || '')
        .replace(/\s*\(legacy\)/i, '').trim();
    if (!label) return <span className="badge-silver opacity-70" data-testid="plan-badge">Sin plan</span>;
    const cls = {
        gold: 'badge-gold', silver: 'badge-silver', bronze: 'badge-bronze', elm: 'badge-elm',
        reto12en12_gold: 'badge-gold', reto12en12_silver: 'badge-silver',
    }[plan] || 'badge-elm';
    return <span className={cls} data-testid="plan-badge">{label}</span>;
};


/**
 * UN MACRO DEL DÍA: el número grande, el nombre y cuánto es el objetivo.
 *
 * Sustituye al anillo + barra del panel (documento del 10-08, pantalla 4). Tres decisiones,
 * y las tres son suyas:
 *
 *  - «Los números suben de tamaño y se les quita el anillo». El anillo ocupaba 92 px para
 *    decir lo mismo que dice el número.
 *  - «"de 190" DEBAJO del número, no arriba en una franja aparte»: antes había que mirar a
 *    dos sitios para saber cuánto faltaba.
 *  - El nombre del macro debajo del número y en negrita.
 *
 * La barra fina de abajo se queda: es lo que sustituye al anillo de un vistazo y ocupa, en
 * palabras del documento, «una décima parte». Cuando se pasa del objetivo se pone en rojo,
 * que es la única alarma de esta pantalla.
 */
const MacroGrande = ({ valor, objetivo, label, color }) => {
    const pct = objetivo > 0 ? Math.min((valor / objetivo) * 100, 100) : 0;
    const pasado = valor > objetivo + 4;
    return (
        <div className="text-center" data-testid={`macro-${slug(label)}`}>
            <p className="font-data font-bold leading-none text-foreground text-[34px] sm:text-[40px]">
                {Math.round(valor)}
            </p>
            <p className="text-sm font-bold mt-1.5" style={{ color: pasado ? '#DC2626' : color }}>{label}</p>
            <p className="text-sm text-muted-foreground font-data">de {Math.round(objetivo)}</p>
            <div className="h-1 bg-muted rounded-full overflow-hidden mt-2">
                <div className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, backgroundColor: pasado ? '#DC2626' : color }} />
            </div>
        </div>
    );
};

// ===== Checklist de primeros pasos (onboarding) =====
const OnboardingChecklist = ({ steps, onDismiss, navigate, onResume, showResume }) => {
    const doneCount = steps.filter(s => s.done).length;
    const pct = Math.round((doneCount / steps.length) * 100);
    return (
        <div className="surface p-5 relative overflow-hidden" data-testid="onboarding-checklist">
            <div className="absolute top-0 right-0 w-40 h-40 bg-brand/5 rounded-full blur-3xl pointer-events-none" />
            <button onClick={onDismiss} data-testid="dismiss-checklist-btn"
                className="absolute top-3 right-3 w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                title="Ocultar">
                <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 mb-1">
                <Sparkles className="w-4 h-4 text-brand" />
                <p className="caption text-brand">Primeros pasos</p>
            </div>
            <h2 className="font-heading text-2xl font-bold uppercase text-foreground leading-none mb-1">Empieza aquí</h2>
            <p className="text-muted-foreground text-sm mb-4">Completa estos pasos para aprovechar al máximo tu plan.</p>

            {/* Barra de progreso */}
            <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                    <div className="bg-brand h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-data font-bold text-muted-foreground whitespace-nowrap">{doneCount}/{steps.length}</span>
            </div>

            <div className="space-y-2">
                {steps.map((s) => (
                    <button key={s.label} onClick={() => !s.done && navigate(s.path)}
                        disabled={s.done}
                        data-testid={`step-${s.id}`}
                        className={`w-full flex items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-colors ${s.done ? 'bg-muted/50 cursor-default' : 'bg-muted/40 hover:bg-muted'}`}>
                        {s.done
                            ? <CheckCircle2 className="w-5 h-5 text-brand flex-shrink-0" />
                            : <Circle className="w-5 h-5 text-muted-foreground flex-shrink-0" />}
                        <div className="min-w-0 flex-1">
                            <p className={`text-sm font-bold ${s.done ? 'text-muted-foreground line-through' : 'text-foreground'}`}>{s.label}</p>
                            {!s.done && s.sub && <p className="text-xs text-muted-foreground">{s.sub}</p>}
                        </div>
                        {!s.done && <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />}
                    </button>
                ))}
            </div>

            {showResume && (
                <button onClick={onResume} data-testid="resume-tour-btn"
                    className="mt-4 w-full flex items-center justify-center gap-2 rounded-xl bg-brand/10 hover:bg-brand/15 text-brand font-bold text-sm py-3 transition-colors">
                    <Sparkles className="w-4 h-4" /> Continuar recorrido guiado
                </button>
            )}
        </div>
    );
};

// EL PLAN SE ACABÓ (punto 41 del doc del 07-08).
//
// La calculadora antigua ya lo tenía resuelto y es lo que se copia: se corta el acceso, se
// dice que la suscripción ha caducado y se le da salida. Y la salida de la que se habló:
// la Membresía, que es donde cae el que no renueva.
//
// EL «PONTE EN CONTACTO» ERA UNA PUERTA PINTADA (14-08-2026). Ofrecía escribir por
// WhatsApp y el número nunca llegó a ponerse, así que lo que salía era «escríbenos y lo
// vemos» sin decir a quién ni dónde. Ahora deja su correo y entra en Leads, que es donde
// alguien lo va a ver: «que deje su mail y queda como lead».
// LA VENTANA DE LAS 12 SEMANAS (doc 19-08, «Fotos, medidas y % de grasa: la regla»).
//
//     «Llevas 12 semanas sin actualizar tu porcentaje de grasa · Te recomiendo medirlo
//      cada 12 semanas.» Tres salidas, y una vez al día como mucho aunque abra la app
//      varias veces.
//
// El servidor decide si toca (`profile.grasa.mostrar_ventana`): aquí solo se pinta, se
// apunta que hoy ya salió, y se ejecuta la salida que elija.
const VentanaGrasa = ({ api, profile, onCerrada }) => {
    const [abierta, setAbierta] = useState(true);
    const [eligiendo, setEligiendo] = useState(false);
    const [grasa, setGrasa] = useState(profile?.grasa?.valor ?? profile?.body_fat ?? null);
    const [guardando, setGuardando] = useState(false);

    useEffect(() => {
        // Se apunta nada más salir: si cierra la app sin tocar nada, hoy ya no vuelve.
        api.post('/clients/me/grasa/ventana', { accion: 'vista' }).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const salida = async (accion) => {
        try { await api.post('/clients/me/grasa/ventana', { accion }); } catch { /* ya quedó vista */ }
        setAbierta(false);
        onCerrada?.();
    };

    const guardar = async () => {
        setGuardando(true);
        try {
            await api.post('/clients/me/grasa', { valor: grasa });
            toast.success('Porcentaje actualizado');
            setAbierta(false);
            onCerrada?.();
        } catch (e) {
            console.error('[grasa] no se pudo guardar', e);
            toast.error('No se pudo guardar. Inténtalo en un momento.');
        } finally {
            setGuardando(false);
        }
    };

    if (!abierta) return null;
    return (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
            data-testid="ventana-grasa">
            <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
                <h2 className="text-xl font-bold text-foreground leading-tight mb-1">
                    Llevas 12 semanas sin actualizar tu porcentaje de grasa
                </h2>
                <p className="text-sm text-muted-foreground mb-4">
                    Te recomiendo medirlo cada 12 semanas.
                </p>
                {eligiendo ? (
                    <div className="space-y-3">
                        <BodyFatSlider value={grasa} onChange={setGrasa} sexo={profile?.sex || 'hombre'} />
                        <button onClick={guardar} disabled={guardando || grasa == null}
                            data-testid="grasa-guardar" className="btn-brand w-full disabled:opacity-60">
                            {guardando ? 'Guardando…' : 'Guardar mi porcentaje'}
                        </button>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <button onClick={() => setEligiendo(true)} data-testid="grasa-actualizar"
                            className="btn-brand w-full">Actualizarlo ahora</button>
                        <button onClick={() => salida('recordar')} data-testid="grasa-recordar"
                            className="w-full text-sm text-foreground/70 hover:text-foreground py-2">
                            Recordármelo la semana que viene
                        </button>
                        <button onClick={() => salida('nunca')} data-testid="grasa-nunca"
                            className="w-full text-xs text-foreground/40 hover:text-foreground/60 py-1">
                            No volver a mostrar
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};


const PlanCaducado = ({ navigate, nombre, api, email }) => {
    const [enviando, setEnviando] = useState(false);
    const [hecho, setHecho] = useState('');

    // SIN PEDIRLE EL CORREO (doc 19-08, «Mi plan y la baja»): «hoy dice "déjanos tu
    // correo y te escribimos", y el correo ya lo tenemos». Es SU sesión: un botón y ya.
    const pedirContacto = async () => {
        setEnviando(true);
        try {
            const r = await api.post('/leads/quiero-volver', { email: (email || '').trim() });
            setHecho(r.data?.mensaje || 'Hecho. Te escribimos enseguida.');
        } catch (err) {
            // Al cliente no se le enseña el detalle del backend: frase humana aquí y el
            // porqué a la consola, que es donde sirve.
            console.error('[caducado] no se pudo registrar el contacto', err);
            toast.error('No hemos podido apuntarlo. Inténtalo en un momento.');
        } finally {
            setEnviando(false);
        }
    };

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto animate-fade-in" data-testid="plan-caducado">
            <div className="surface p-8 text-center">
                <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Clock className="w-8 h-8 text-brand" />
                </div>
                <h2 className="heading-2 text-foreground mb-2">Tu suscripción ha terminado</h2>
                <p className="text-muted-foreground mb-6 text-sm">
                    Para seguir entrenando con nosotros, renueva tu plan. Y si quieres que te
                    llamemos y lo vemos juntos, dínoslo.
                </p>

                {hecho ? (
                    <p className="text-brand font-medium text-sm" data-testid="caducado-hecho">{hecho}</p>
                ) : (
                    <div className="flex flex-col sm:flex-row gap-2 justify-center">
                        {/* SU PLAN, NO EL CATÁLOGO (Francisco, 25-08). Los dos botones de
                            esta pantalla traían a la misma lista entera, y al que pulsa
                            «Renovar mi plan» no hay que ponerle delante Premium, Gold y
                            Calculadora: ya ha dicho lo que quiere. Con `solo=mio` se le
                            enseña el suyo y, debajo, la puerta a los demás. «Ver mis
                            opciones», más abajo, sigue trayendo la lista completa. */}
                        <button onClick={() => navigate('/renovacion?solo=mio')} className="btn-brand whitespace-nowrap"
                            data-testid="caducado-renovar">
                            Renovar mi plan
                        </button>
                        <button onClick={pedirContacto} disabled={enviando}
                            className="text-brand text-sm hover:underline disabled:opacity-60 px-4 py-2.5"
                            data-testid="caducado-enviar">
                            {enviando ? 'Enviando...' : 'Que me escriban'}
                        </button>
                    </div>
                )}

                {/* La salida del que no renueva es Mantenimiento (doc 19-08, fallo 06:
                    «es donde aterriza todo el que termina un ciclo y no renueva»). Antes
                    aquí se ofrecía la Membresía de 97, que se vende por su propio embudo. */}
                <div className="mt-6 pt-6 border-t border-border">
                    <p className="text-sm text-foreground font-medium mb-1">¿Prefieres seguir por tu cuenta?</p>
                    {/* A /renovacion Y NO A /planes (24-08). Este boton prometia
                        Mantenimiento y llevaba a la comparativa de 247, 847 y 1.500, donde
                        Mantenimiento no sale por ningun lado: /planes pinta solo los tres
                        niveles a proposito, porque la membresia no se compra, se aterriza
                        en ella. El unico sitio donde Mantenimiento existe para el cliente
                        es la pantalla de renovacion, como salida «Dejarlo por ahora»
                        (core/renovacion.py). Al que se le acaba el ciclo y estaba dudando,
                        enseñarle tres precios mas caros que el que acaba de leer es lo que
                        hace que se vaya.

                        Y SE DICE DONDE VA A CAER. Los dos botones de esta pantalla acaban en
                        la misma pagina, asi que el de abajo tenia que prometer solo lo que
                        hay: la salida esta ahi, pero es la ultima tarjeta y se titula
                        «Dejarlo por ahora», no «Mantenimiento». Quien no lo sabe cree que se
                        equivoco de boton y se va. La otra mitad -- que la pantalla de
                        renovacion baje sola hasta esa tarjeta -- es de RenovacionPage.jsx. */}
                    <p className="text-muted-foreground text-xs mb-3">
                        Mantenimiento son 60 €/mes y te deja la calculadora y tus alimentos. Lo tienes con
                        tus opciones de renovación, el último, como «Dejarlo por ahora».
                    </p>
                    <button onClick={() => navigate('/renovacion')} className="text-brand text-sm hover:underline" data-testid="ver-membresia">
                        Ver mis opciones
                    </button>
                </div>
            </div>
        </div>
    );
};

// =============== INICIO NUEVO (T1 del doc del 16-08) ===============
//
// «Un bloque, "Lo que toca hoy", con macros, suplementación y entreno. Debajo,
// "Pendiente". Y arriba del todo, la frase del día.»
//
// Lo que cambia respecto al Inicio de siempre, que sigue vivo debajo:
//
//  - Los macros son el bloque «Tu dieta hoy» del doc del 21-08: el deslizador de cuatro
//    posiciones (Macros · Dieta · Llevas · Falta) y las comidas con su casilla. Vive en
//    `components/inicio/TuDietaHoy.jsx`, que es donde está explicada cada cuenta.
//  - Desaparece la pila de banners: lo pendiente es una lista de líneas iguales, en el
//    orden del documento, y cuando no queda nada se dice y ya está.
//  - La línea de entreno sale por el DATO (tiene rutina cargada), no por el plan; y si no
//    la marca se queda sin marcar. Nunca en rojo (regla 3 del doc).
//
// Todo esto vive detrás del interruptor `t1_inicio_nuevo` del panel: apagado, el cliente
// ve el Inicio de siempre sin que nadie despliegue nada.

// La fecha de hoy con la que viajan las dietas: LA DEL RELOJ DEL CLIENTE (bloque F,
// 23-08). Estuvo clavada a España «para coincidir con el servidor», pero eso le abría a
// un cliente en América un día que aún no había vivido y le marcaba la cena de su sábado
// en el domingo. Ahora el criterio es el contrario y es de producto: su día es el suyo;
// el servidor acepta la fecha del cliente en todos los caminos del día vivido
// (`dia_del_cliente`), y España queda para los plazos. Nutrición usa este mismo reloj.
const hoyDeLaDieta = () => hoyLocal();

// El día de mañana con el mismo criterio (el reloj del cliente): para la línea «Mañana»
// y para abrir Nutrición en ese día (`?date=`, el mismo camino que usa Mi semana).
const mananaDeLaDieta = () =>
    new Date(Date.parse(`${hoyLocal()}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);

const estrellas = (n) => (n >= 1 && n <= 5 ? '★'.repeat(n) + '☆'.repeat(5 - n) : '');

// Una línea de «Lo que toca hoy» o de «Pendiente»: título, detalle y, a la derecha, la
// flecha de entrar o el «✓ hecho». Nada de rojos ni de la palabra «pendiente».
const LineaDeHoy = ({ icono: Icono, titulo, detalle, cursiva, extra, hecho, onClick, testId }) => {
    const Contenedor = onClick ? 'button' : 'div';
    return (
        <Contenedor onClick={onClick} data-testid={testId}
            className={`surface w-full p-4 flex items-center gap-4 text-left ${onClick ? 'surface-hover group' : ''}`}>
            {Icono && (
                <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Icono className="w-5 h-5 text-brand" />
                </div>
            )}
            <div className="min-w-0 flex-1">
                <p className="font-bold text-foreground text-sm">{titulo}</p>
                {detalle && <p className={`text-muted-foreground text-sm truncate${cursiva ? ' italic' : ''}`}>{detalle}</p>}
                {extra && <p className="text-muted-foreground text-xs mt-0.5">{extra}</p>}
            </div>
            {hecho ? (
                <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-600 dark:text-emerald-400 flex-shrink-0"
                    data-testid={testId ? `${testId}-hecho` : undefined}>
                    <CheckCircle2 className="w-4 h-4" /> hecho
                </span>
            ) : onClick ? (
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
            ) : null}
        </Contenedor>
    );
};

// El «Te faltan 94 · de 120» por macro (MacroQueFalta) se retiró el 21-08: el doc de ese
// día lo sustituye por el deslizador de cuatro posiciones de `components/inicio/TuDietaHoy`,
// donde «Falta» es una de las vistas y sale de la misma cuenta.

// Los tres cierres del documento. Rotan por día: dentro del mismo día siempre el mismo,
// que si no cambiaría de frase cada vez que recarga.
const CIERRES = [
    'Hoy no tienes nada más pendiente. Otra semana más, sigue así que vas bien.',
    'Hoy no tienes nada más pendiente. Ahora a descansar, que ya toca.',
    'Hoy no tienes nada más pendiente.',
];

const InicioNuevo = () => {
    const { user, profile, api, can, appSettings, pantalla, habilitaciones, planCatalog } = useAuth();
    const navigate = useNavigate();
    const [comido, setComido] = useState({ P: 0, H: 0, G: 0 });
    // El objetivo del día ya resuelto por el servidor (el del día menos el peri): el mismo
    // número que la cabecera de Nutrición. No se recalcula aquí, y no hay segunda fuente:
    // mientras no llegue, arriba no hay números (ver `diaCargado`).
    const [objetivoComidas, setObjetivoComidas] = useState(null);
    // El documento entero del día (`GET /diets/{hoy}`): TuDietaHoy necesita las comidas
    // una a una para la lista de «Marca lo que ya te has comido».
    const [dieta, setDieta] = useState(null);
    const [diaCargado, setDiaCargado] = useState(false);
    // LOS EXTRAS DEL DÍA DE QUIEN NO TIENE MACROS. Con macros, el bloque lo pinta TuDietaHoy
    // y lleva su propia lista; sin macros, ese componente no se monta y el cliente se
    // quedaba sin campo de extras en Inicio (los puntos 26 y 29 de Jesús dicen que el campo
    // está en Inicio, sin condiciones: apuntar lo que se ha comido no depende de tener los
    // macros puestos). Esta lista solo se usa en esa rama, así que nunca hay dos a la vez.
    const [extrasSinMacros, setExtrasSinMacros] = useState([]);
    // La configuración de dieta QUE TIENE PUESTA el cliente (`GET /user/diet-config`), que es
    // la que manda los días que todavía no ha montado. Aquí solo se usa el `opcion_peri`,
    // para el rótulo del perientreno: ver `conPerientreno`.
    const [configDieta, setConfigDieta] = useState(null);
    const [suplementos, setSuplementos] = useState([]);
    const [rutina, setRutina] = useState(null);
    const [entrenoDeHoy, setEntrenoDeHoy] = useState(null);
    // Lo que le toca hoy según el servidor: si tiene rutina, qué día es y si es descanso.
    const [entrenoDelDia, setEntrenoDelDia] = useState(null);
    // La rutina en PDF que sube el entrenador: para quien la tiene, ESA es su rutina
    // (mismo patrón que RoutinePage tras el arreglo del 21-08).
    const [pdfRutina, setPdfRutina] = useState(null);
    // La semana de su rutina (`GET /routines/semana`): de ahí sale el nombre de lo que
    // entrena hoy («Pectoral - Tríceps»), que es lo que pide el punto 24 del 24-08.
    const [semanaRutina, setSemanaRutina] = useState(null);
    // El día de mañana, para la línea «Mañana · aún sin dieta · Repetir la de hoy».
    const [dietaManana, setDietaManana] = useState(null);
    const [ultimoCierre, setUltimoCierre] = useState(null);
    const [reportes, setReportes] = useState([]);
    const [tienePreferencias, setTienePreferencias] = useState(true);

    useEffect(() => {
        if (!profile) return;
        const cargar = async () => {
            // Cada petición con su red: una función que no está (el registro de entreno se
            // está construyendo) o un plan sin suplementación no pueden dejar Inicio en
            // blanco. Lo que no llega, no se pinta.
            // OJO: aquí NO se pide `/macros`. El objetivo del día no se compone de dos
            // fuentes -- ese fue el fallo: según cuál llegara antes, Inicio enseñaba 190, 235
            // o 225 del mismo día mientras el cliente miraba. Viene resuelto con la dieta o
            // no viene.
            const [dietaRes, suplRes, rutinaRes, logRes, cierreRes, dueRes, prefsRes, pdfRes, mananaRes,
                   semanaRes, cfgRes] = await Promise.all([
                api.get(`/diets/${hoyDeLaDieta()}`).catch(() => ({ data: { exists: false } })),
                api.get('/supplements/current').catch(() => ({ data: null })),
                api.get('/routines/current').catch(() => ({ data: null })),
                api.get(`/workout-logs/hoy?fecha=${hoyLocal()}`).catch(() => ({ data: { log: null } })),
                api.get('/checkins?type=daily&limit=1').catch(() => ({ data: [] })),
                api.get('/reports/due').catch(() => ({ data: { items: [] } })),
                api.get('/user/preferences').catch(() => ({ data: { has_preferences: true } })),
                api.get('/routines/pdf/info').catch(() => ({ data: { hay: false } })),
                api.get(`/diets/${mananaDeLaDieta()}`).catch(() => ({ data: { exists: false } })),
                // QUÉ LE TOCA HOY, POR SU NOMBRE (punto 24 del doc del 24-08: «TU ENTRENO
                // PREVISTO · Pectoral - Tríceps · VER»). El servidor ya lo sabía -- el
                // reparto del PDF cruzado con los días que entrena -- y esta pantalla no lo
                // preguntaba: para el que tiene la rutina en PDF la línea decía «Tu rutina,
                // en PDF» y había que abrir el PDF para saber qué tocaba.
                api.get(`/routines/semana?hoy_cliente=${hoyLocal()}`).catch(() => ({ data: { hay: false } })),
                // LA CONFIGURACIÓN QUE TIENE PUESTA, para los días que aún no ha montado.
                // Es la MISMA petición que hace TuDietaHoy en ese caso para pedir el reparto,
                // y aquí hace falta por lo mismo: sin ella esta pantalla no sabe si el
                // cliente lleva perientreno y el rótulo del punto 49 se lo inventaba.
                api.get('/user/diet-config').catch(() => ({ data: null })),
            ]);
            // EN INICIO, SOLO LA SUYA. Desde el 18-08 el servidor manda la suplementación
            // general a quien no tiene la suya escrita, y ahí está bien: la pestaña tiene
            // que enseñar siempre algo. Pero «Lo que toca hoy · Tu suplementación» es lo
            // que le ha pautado él, y una lista general anunciada como suya en la portada
            // sería decirle que le hemos puesto algo que no le hemos puesto.
            setSuplementos(suplRes.data?.es_generica ? [] : (suplRes.data?.actual || []));
            setRutina(rutinaRes.data);
            setEntrenoDeHoy(logRes.data?.log || null);
            // Qué le toca hoy lo dice el SERVIDOR, que cuenta los días en hora de España.
            setEntrenoDelDia(logRes.data?.tiene_rutina ? logRes.data : null);
            setPdfRutina(pdfRes.data?.hay ? pdfRes.data : null);
            setSemanaRutina(semanaRes.data?.hay ? semanaRes.data : null);
            setConfigDieta(cfgRes.data || null);
            setDietaManana(mananaRes.data || null);
            setUltimoCierre(Array.isArray(cierreRes.data) ? cierreRes.data[0] || null : null);
            setReportes(dueRes.data?.items || []);
            setTienePreferencias(!!prefsRes.data?.has_preferences);

            const dieta = dietaRes.data;
            setDieta(dieta || null);
            // Viene aunque el día no exista todavía: el objetivo es del día, no de lo que
            // haya puesto.
            setObjetivoComidas(dieta?.objetivo_comidas || null);
            // Los extras ya apuntados hoy, para la rama sin macros (ver `extrasSinMacros`).
            setExtrasSinMacros((dieta?.exists && dieta.extras) || []);
            // LO SERVIDO TAMBIÉN LO CUENTA EL SERVIDOR (punto 3 del 17-08).
            //
            // Aquí se sumaba `macros_efectivos` de cada alimento tal y como estuviera
            // guardado en la dieta. Nutrición no hace eso: pide la calibración del día y
            // pinta lo que le devuelve. Dos cuentas del mismo número, y la de aquí fallaba
            // en silencio cuando el campo no estaba guardado -- pasa, y entonces Inicio
            // decía «Te faltan 180 de 180» de un día que Nutrición daba por cerrado.
            // Ahora `servido_comidas` viene resuelto de `GET /diets/{fecha}`, con el
            // perientreno ya fuera, igual que `objetivo_comidas`.
            if (dieta?.servido_comidas) setComido(dieta.servido_comidas);
            setDiaCargado(true);
        };
        cargar().catch((err) => {
            // Al cliente no se le enseña una traza: si algo no llega, Inicio se pinta con
            // lo que tenga.
            console.error('[inicio] no se pudieron cargar los datos del día', err);
            setDiaCargado(true);
        });
    }, [api, profile]);

    // EL OBJETIVO, EL MISMO QUE ENSEÑA NUTRICIÓN. Lo resuelve el servidor con el reparto de
    // ese día, ya con el perientreno descontado. O ese, o ninguno: no hay segundo camino.
    // (TuDietaHoy le suma el peri por su cuenta para la vista «Macros», con el reparto vivo.)
    const objetivo = objetivoDelDia(objetivoComidas);

    // El cierre del día de HOY (hora de España, que es como cuenta el backend).
    const cierreDeHoy = ultimoCierre && diaLocal(aFecha(ultimoCierre.created_at) || new Date()) === hoyLocal()
        ? ultimoCierre : null;
    // «✓ hecho» en suplementación cuando lo marcó en el cierre de hoy. El campo lo escribe
    // T4; mientras no exista, la línea sale sin marcar y no pasa nada.
    const suplementosTomados = (() => {
        const r = (cierreDeHoy?.suplementos?.respuesta || '').toString().trim().toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        // Solo el «sí» entero: «no todos» y «no» se quedan sin marca.
        return r === 'si';
    })();

    const nombresSuplementos = suplementos.map((s) => s.titulo).filter(Boolean).join(' · ');

    // La línea de entreno sale por el dato, no por el plan (regla 3): si tiene rutina
    // cargada para hoy. El día de descanso no se anuncia: no hay nada que hacer.
    //
    // QUÉ DÍA ES HOY LO DICE EL SERVIDOR, NO EL NAVEGADOR. Esto miraba
    // `new Date().toLocaleDateString(...)`, o sea el día del aparato del cliente, mientras
    // la cabecera de arriba escribe el día de España: a un cliente que no esté en España la
    // misma pantalla le decía «Lunes, 17 de agosto» y buscaba su entreno en el domingo, así
    // que un día de descanso ahí le borraba la línea de entreno del lunes. El backend ya lo
    // resuelve en `GET /workout-logs/hoy`, que desde el bloque F recibe el día del cliente.
    const grupoMuscular = entrenoDelDia?.dia_rutina || '';
    const esDiaDeEntreno = !!entrenoDelDia && !entrenoDelDia.descanso;
    // Lo previsto para hoy en la semana de su rutina: el que tiene la rutina en PDF no
    // tiene «rutina estructurada», pero su reparto sí dice qué grupo le toca hoy.
    //
    // SOLO SI PUEDE ABRIR LA RUTINA. `GET /routines/semana` contesta sin mirar el plan («si
    // su entrenador le subió la rutina, es suya»), pero /dashboard/routine va detrás de
    // CAP.RUTINA -- el plan más el interruptor t3_entreno -- y CapabilityRoute devuelve a
    // Inicio sin decir nada. Sin esa llave, la línea del PDF se queda como estaba y abre el
    // PDF, que es lo único que sí funciona para él: mejor un enlace pobre que uno muerto.
    const hoyDeLaSemana = (semanaRutina && can('rutina')) ? (semanaRutina.hoy || null) : null;
    const grupoPrevisto = hoyDeLaSemana?.entrena ? (hoyDeLaSemana.grupo || '') : '';
    const descansoPrevisto = !!hoyDeLaSemana && !hoyDeLaSemana.entrena;
    const soloCardio = esDiaDeEntreno && entrenoDelDia.tipo === 'cardio';
    const duracionCardio = (() => {
        const d = entrenoDelDia?.cardio_minutos;
        if (d == null || d === '') return '';
        return /^\d+$/.test(String(d).trim()) ? `${d} minutos` : String(d);
    })();
    const resumenEntreno = [estrellas(entrenoDeHoy?.estrellas),
        entrenoDeHoy?.pesos?.[0]?.ejercicio
            ? `${entrenoDeHoy.pesos[0].ejercicio}${entrenoDeHoy.pesos[0].peso_kg != null ? ` ${num1(entrenoDeHoy.pesos[0].peso_kg)} kg` : ''}`
            : ''].filter(Boolean).join(' · ');

    // «· día de entreno / día de descanso» en la cabecera, como el Inicio de siempre.
    // Manda el día guardado (es del que salen los macros); si no hay, lo que diga la rutina.
    const tipoDeDia = dieta?.exists && dieta.tipo_dia
        ? (dieta.tipo_dia === 'descanso' ? 'descanso' : 'entreno')
        : entrenoDelDia ? (entrenoDelDia.descanso ? 'descanso' : 'entreno') : null;

    // EL DÍA PUEDE EXISTIR SIN DIETA MONTADA: desde el 24-08 apuntar un extra hace upsert
    // del documento del día, así que `exists` ya no significa «configurado». El marcador
    // bueno es `num_comidas`, que solo lo escribe un guardado de dieta de verdad (la misma
    // regla y por la misma razón que `diaConfigurado` en components/inicio/TuDietaHoy.jsx).
    const diaConfigurado = Boolean(dieta?.exists && dieta.num_comidas);

    // EL PERIENTRENO YA NO SE ROTULA DESDE AQUÍ (puntos 86 a 88 del artifact del 25-08).
    // Desde el 24-08 había una frase, «Tus macros de hoy llevan el perientreno dentro», y
    // para decidir si salía se recalculaba aquí la configuración del día -- con su propia
    // precedencia, que tenía que coincidir con la de `TuDietaHoy` o el rótulo describía otro
    // número. Ahora en su sitio hay un INTERRUPTOR, y vive donde viven los números, así que
    // lee el mismo reparto que ellos y no puede desmentirlos: components/inicio/TuDietaHoy.

    // El PDF se abre vía blob porque el visor del navegador no manda el token (mismo
    // camino que RoutinePage y EntrenoPage).
    const abrirPdfRutina = async () => {
        try {
            const r = await api.get('/routines/pdf', { responseType: 'blob' });
            window.open(URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })), '_blank');
        } catch { toast.error('No hemos podido abrir tu rutina. Inténtalo en un momento.'); }
    };

    // ── 4.3: PLAN POR PLAN, POR EL CATÁLOGO (habilitaciones), jamás por nombre de plan ──
    const h = habilitaciones || {};
    // «Tus macros los pones tú · Cambiarlos»: los planes de autogestión (el catálogo lo
    // dice con `edita_macros`). Gold y Premium lo llevan a false y no ven la tarjeta.
    const ponesTusMacros = can('edita_macros') && !!objetivo;
    // «La rutina del mes» sin rutina cargada: Calculadora y ELM (`rutina: del_mes`).
    // `can('rutina')` añade el interruptor t3 del panel, el mismo que abre la ruta.
    const rutinaDelMes = h.rutina === 'del_mes' && can('rutina');
    // «Escribir a tu entrenador»: el apartado de contacto de los planes sin entrenador,
    // si su catálogo trae un canal de verdad (el de solo incidencias técnicas no lo es).
    const canalContacto = (h.canal_contacto || '').trim();
    const escribirAlEntrenador = h.acompanamiento === 'solo_app' && canalContacto
        && !/^ninguno$/i.test(canalContacto) && !/incidencias/i.test(canalContacto);
    const contestaElViernes = /viernes/i.test(canalContacto);
    // La tarjeta de venta del que no lleva rutina pero puede comprarla (`rutina: opcional`,
    // hoy Mantenimiento). El precio es el del complemento del catálogo («Suelta»), que
    // desde el 24-08 son 57 € como en todas partes: si el catálogo no lo dice, no hay
    // tarjeta. El número NO se escribe aquí, para que no vuelva a haber dos.
    const precioRutinaSuelta = (planCatalog?.rutina_mes?.precios || [])
        .find((p) => /suelta/i.test(p.label || ''))?.importe;
    const ventaRutina = h.rutina === 'opcional' && !entrenoDelDia && !rutina && !pdfRutina
        && precioRutinaSuelta != null;

    // ── La línea de mañana: a Nutrición en el día de mañana (?date=, como Mi semana) ──
    const manana = (() => {
        const d = dietaManana;
        const comidas = (d?.exists && d.comidas) || {};
        const conAlimentos = Object.entries(comidas)
            .filter(([k]) => k !== 'Intra' && k !== 'Post')
            .filter(([, c]) => (c?.alimentos || []).length > 0).length;
        if (!conAlimentos) return { detalle: 'aún sin dieta', accion: 'Repetir la de hoy' };
        const total = d.num_comidas || 4;
        if (conAlimentos < total) return { detalle: `empezada · ${conAlimentos} de ${total} comidas`, accion: 'Terminarla' };
        return { detalle: 'dieta creada', accion: 'Verla' };
    })();

    // ── Lo pendiente, en el orden del documento ──
    const pendientes = [];
    // SIN PLAN, LO PRIMERO ES ELEGIRLO (bug del 20-08): el recién registrado que volvía
    // atrás desde /planes se quedaba sin ningún camino para volver a verlos.
    if (profile && !profile.plan) {
        pendientes.push({
            id: 'plan', icono: User, titulo: 'Elige tu plan',
            detalle: 'Con él se desbloquea la app entera',
            path: '/planes',
        });
    }
    // EL CIERRE DEL DÍA, CON SU LLAVE PROPIA (decisión de Jesús del 24-08). Aquí se pedía
    // `reportes` y por eso la línea no le salía a los 81 clientes cuyo plan no vende
    // ningún reporte -- ELM, Mantenimiento, Calculadora JP, Básica --, que son justo los
    // que solo tienen esto para contar su día. Ver CAP.CIERRE_DIA en lib/planAccess.js.
    if (can('cierre_dia') && !cierreDeHoy) {
        pendientes.push({
            id: 'cierre', icono: ClipboardCheck, titulo: '¿Cómo fuiste hoy?',
            // En cursiva, como lo pide el doc 19-08: es una aclaración, no una orden.
            detalle: 'Para rellenar al final del día', cursiva: true,
            // La fecha y la hora del último, en vez de la palabra «pendiente».
            extra: ultimoCierre ? `último registro: ${etiquetaMomento(ultimoCierre.created_at)}` : null,
            path: '/dashboard/checkins',
        });
    }
    const faltaElAjuste = profile?.questionnaire_completed && !profile?.ajuste_macros_completado
        && !profile?.macros_puestos_por_alguien;
    const faltaElNivel1 = can('macros_personalizados') && profile?.questionnaire_completed
        && (profile?.ajuste_macros_completado || profile?.macros_puestos_por_alguien)
        && !profile?.questionnaire_nivel1_completed;
    if (faltaElAjuste || faltaElNivel1) {
        pendientes.push({
            id: 'perfil', icono: User, titulo: 'Completar perfil',
            // Corto: en 390 px el subtítulo se cortaba en «Para terminar de ajustar t...»
            // (recorrido móvil del 23-08). La línea es de una sola fila a propósito.
            detalle: 'Para tener tus macros buenos',
            path: faltaElAjuste ? '/questionnaire?ajustar=1' : '/questionnaire',
        });
    }
    if (!tienePreferencias) {
        pendientes.push({
            id: 'preferentes', icono: Apple, titulo: 'Alimentos preferentes',
            detalle: 'Lo rellenas una vez', path: '/dashboard/nutrition',
        });
    }
    // LOS QUE YA ESTABAN DENTRO (bloque 6 del doc del 18-08). Lo que pregunta el alta nueva
    // solo lo contesta quien entre a partir de ahora: de los que ya pagan, ninguno tiene
    // biotipo, ni peso máximo, ni mejor forma. Es el dato que alimenta el modelo, así que se
    // les pasa el básico aquí dentro -- solo lo que falte -- y CON LA RAZÓN POR DELANTE, que
    // es lo que hace que lo contesten: no «rellena tu ficha», sino qué ganan.
    //
    // No se le enseña al que todavía tiene el perfil largo a medias: ese ya tiene su tarjeta
    // y son el mismo recorrido; dos avisos de «contesta cosas» a la vez no son dos avisos,
    // son ruido.
    const queFaltaDelBasico = (() => {
        if (!profile || !profile.questionnaire_completed || faltaElNivel1) return [];
        return [
            [!profile.biotype && profile.sex !== 'mujer', 'tu biotipo'],
            [!profile.peso_maximo, 'tu peso máximo'],
            // «Si no, pásala» (doc 23-08) es una respuesta: quien la dio no tiene mejor
            // forma que contar y no se le persigue con la tarjeta.
            [!profile.peso_mejor_momento && !profile.mejor_forma_pasada, 'tu mejor forma'],
            // Las proteínas ya no se preguntan (doc 23-08, punto 14: en su lugar van las
            // exclusiones, que pueden estar vacías legítimamente). Contarlas aquí dejaba
            // a todo cliente nuevo con una tarjeta imposible de quitar.
            [!profile.tiempo_intentandolo, 'cuánto llevas intentándolo'],
            [!profile.training_experience, 'tu experiencia entrenando'],
            [!profile.birthdate, 'tu fecha de nacimiento'],
        ].filter(([falta]) => falta).map(([, texto]) => texto);
    })();
    if (queFaltaDelBasico.length) {
        pendientes.push({
            id: 'completar-basico', icono: ClipboardCheck,
            titulo: queFaltaDelBasico.length === 1 ? 'Nos falta un dato tuyo' : 'Nos faltan cosas tuyas',
            detalle: `Con ${queFaltaDelBasico.length === 1 ? 'él' : 'ellas'} te recalculamos los macros`,
            extra: queFaltaDelBasico.slice(0, 3).join(' · ') + (queFaltaDelBasico.length > 3 ? '...' : ''),
            path: '/questionnaire?completar=1',
        });
    }
    reportes.forEach((r) => {
        // PASADA LA HORA DESAPARECE. Un plazo vencido en Inicio solo sirve para recordarle
        // cada mañana que llega tarde a algo que ya no puede mandar.
        const plazo = textoPlazo(r.deadline);
        if (!r.is_open || r.overdue || !plazo || plazo.pasado) return;
        pendientes.push({
            id: `reporte-${r.tipo}`, icono: FileText, titulo: r.tipo_label,
            detalle: plazo.texto, path: '/dashboard/reports',
        });
    });

    // LA FRASE NO PUEDE DESAPARECER (punto 103 del 25-08). El panel lo promete con estas
    // palabras: «si un día no hay frase nueva, el cliente sigue viendo la última»
    // (AdminPlansPage). Aquí se exigía ADEMÁS que la frase guardada fuese la de hoy, así que
    // en cuanto la cola se vaciaba el hueco se quedaba en blanco: dos días seguidos con 125
    // clientes entrando. Se quitó ese candado porque intentaba resolver otra cosa (que una
    // misma frase no se repitiera semanas) tapando el bloque entero, y un hueco vacío se ve
    // más que una frase repetida.
    //
    // La cola sigue mandando: cuando a una programada le llega su día, `ajustes_app` la
    // asciende a frase del día (routes/settings.py) y ésta pasa a ser la última. Sin cola,
    // se queda la que hay, que es justo lo prometido. La variedad se resuelve cargando
    // frases (backend/_cargar_frases.py), no escondiendo el bloque.
    const frase = pantalla('frase_del_dia') ? (appSettings?.frase_del_dia?.texto || null) : null;

    return (
        <div className="pb-6 animate-fade-in" data-testid="inicio-nuevo">
            {/* El saludo va sobre la foto del mes en blanco y negro (el hero de fondo vive
                en components/inicio/BannerInicio; la foto no ocupa bloque propio). */}
            {/* El saludo Y la frase del día van SOBRE la foto del mes en blanco y negro: la
                imagen es el fondo de todo el bloque de arriba y se funde con el fondo de la
                pantalla al llegar a «Tu dieta hoy» (no ocupa un bloque propio). La frase, si
                hoy no hay nueva, se queda la del día anterior y no se dice de cuándo es. */}
            <HeroInicio>
                <header>
                    <p className="text-sm text-white/75 first-letter:uppercase" data-testid="inicio-fecha">
                        {fechaLargaDeHoy()}
                        {/* «DÍA DE ENTRENO», no «entreno» (la regla del 13-08, la misma que en
                            el Inicio viejo): es el tipo de día del que salen los macros. */}
                        {tipoDeDia && <span> · día de {tipoDeDia === 'descanso' ? 'descanso' : 'entreno'}</span>}
                    </p>
                    <h1 className="font-heading text-3xl font-bold capitalize text-white leading-tight mt-1">
                        Hola, {user?.name?.split(' ')[0]}
                    </h1>
                </header>
                {frase && (
                    <section className="mt-4" data-testid="frase-del-dia">
                        <p className="caption text-brand mb-1">La frase del día</p>
                        <p className="text-white/90 text-lg leading-snug italic">«{frase}»</p>
                    </section>
                )}
            </HeroInicio>

            {/* El resto del Inicio va en la columna central (la foto de arriba es a sangre). */}
            <div className="px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto space-y-6 mt-4">

            {/* «TU DIETA HOY» (doc del 21-08, tarea 4.2): el deslizador Macros · Dieta ·
                Llevas · Falta y, debajo, «Marca lo que ya te has comido». Vive en
                components/inicio/TuDietaHoy.

                MIENTRAS NO SE SEPA EL OBJETIVO, NO HAY NÚMEROS: la regla de siempre. Un
                número que se corrige solo mientras lo miras no se vuelve a creer. */}
            {!diaCargado ? (
                <div className="surface p-5 animate-pulse" data-testid="macros-cargando">
                    <div className="h-4 w-32 bg-muted rounded" />
                    <div className="grid grid-cols-3 gap-3 mt-4">
                        {[0, 1, 2].map((i) => <div key={i} className="h-20 bg-muted rounded-xl" />)}
                    </div>
                </div>
            ) : objetivo ? (
                /* Los números, la lista de comidas y los extras. El interruptor del
                   perientreno va dentro, en el pie de «Macros»: hasta el 25-08 aquí había
                   una frase suelta explicándolo, y hacía falta un truco de `order` para que
                   cayera pegada a los números en vez de dentro de los extras. */
                <TuDietaHoy api={api} userId={user?.id} fecha={hoyDeLaDieta()} dieta={dieta}
                    objetivo={objetivo} servido={comido} navigate={navigate} />
            ) : (
                <>
                    <LineaDeHoy icono={Scale} titulo="Configura tus macros"
                        detalle="Introduce tu peso, % graso y objetivo" testId="inicio-sin-macros"
                        onClick={() => navigate('/dashboard/macro-calculator')} />
                    {/* «EL CAMPO ESTÁ EN INICIO» (puntos 26 y 29), TAMBIÉN SIN MACROS. El
                        bloque de extras vive dentro de TuDietaHoy, que solo se monta cuando
                        hay objetivo; el que todavía no tiene los macros puestos se quedaba
                        sin dónde apuntar lo que se comió y solo le quedaban Nutrición y la
                        pregunta de la noche. Apuntar un extra no necesita macros: no cuenta
                        contra nada (punto 28), solo se guarda. */}
                    <ExtrasDelDia api={api} fecha={hoyDeLaDieta()} extras={extrasSinMacros}
                        origen="inicio"
                        onAnadido={(e) => setExtrasSinMacros((prev) => [...prev, e])}
                        onQuitado={(id) => setExtrasSinMacros((prev) => prev.filter((x) => x.id !== id))} />
                </>
            )}

            {/* «Tus macros los pones tú · Cambiarlos»: solo si el catálogo dice que este
                plan edita sus macros (Calculadora, ELM, Mantenimiento...). */}
            {diaCargado && ponesTusMacros && (
                <LineaDeHoy icono={SlidersHorizontal} titulo="Tus macros los pones tú"
                    detalle="Cambiarlos" testId="linea-mis-macros"
                    onClick={() => navigate('/dashboard/macro-calculator')} />
            )}

            {/* «TU ENTRENO PREVISTO», en una línea: el entreno con su grupo si se conoce, el
                PDF de rutina si es lo que hay (patrón de RoutinePage tras el arreglo de
                hoy), la rutina del mes si el plan la trae por catálogo, o Descanso.

                «PREVISTO», NO «HOY» (punto 24 del doc del 24-08): «es el plan, no un hecho.
                El hecho lo cuenta él por la noche en el check-in». */}
            {diaCargado && (esDiaDeEntreno || entrenoDelDia?.descanso || pdfRutina || rutinaDelMes || ventaRutina) && (
                <section className="space-y-3" data-testid="tu-entreno-hoy">
                    <p className="caption">Tu entreno previsto</p>
                    {esDiaDeEntreno ? (
                        entrenoDeHoy?.hecho ? (
                            /* El grupo por su nombre y sin «Entreno ·» delante: el titulillo
                               de arriba ya dice que esto es el entreno (punto 24, 24-08). */
                            <LineaDeHoy icono={Dumbbell}
                                titulo={grupoMuscular || grupoPrevisto || 'Entreno'}
                                detalle={resumenEntreno || null} hecho testId="linea-entreno"
                                onClick={() => navigate('/dashboard/entreno')} />
                        ) : soloCardio ? (
                            <LineaDeHoy icono={Flame} titulo="Hoy solo cardio"
                                detalle={[duracionCardio, 'ver la pauta'].filter(Boolean).join(' · ')}
                                testId="linea-entreno" onClick={() => navigate('/dashboard/entreno')} />
                        ) : (
                            <LineaDeHoy icono={Dumbbell}
                                titulo={grupoMuscular || grupoPrevisto || 'Entreno'}
                                detalle="Ver la rutina" testId="linea-entreno"
                                onClick={() => navigate('/dashboard/entreno')} />
                        )
                    ) : entrenoDelDia?.descanso ? (
                        <LineaDeHoy icono={Moon} titulo="Descanso"
                            detalle="Hoy no te toca entrenar" testId="linea-entreno"
                            onClick={() => navigate('/dashboard/entreno')} />
                    ) : pdfRutina ? (
                        /* Sin rutina estructurada pero CON PDF: esa ES su rutina. Y si su
                           reparto dice qué le toca hoy, se dice por su nombre y «Ver la
                           rutina» la carga, en vez de mandarle a abrir el PDF a buscarlo
                           (punto 24 del 24-08).

                           LA CAÍDA IMPORTA: sin reparto guardado -- hoy en producción son
                           los DOS PDFs que hay -- la línea se queda como estaba, «Tu
                           rutina, en PDF · Abrirla», que dice menos que el grupo pero más
                           que un «Entreno» a secas. */
                        grupoPrevisto ? (
                            <LineaDeHoy icono={Dumbbell} titulo={grupoPrevisto}
                                detalle="Ver la rutina" testId="linea-entreno-previsto"
                                onClick={() => navigate('/dashboard/routine')} />
                        ) : descansoPrevisto ? (
                            <LineaDeHoy icono={Moon} titulo="Descanso"
                                detalle="Hoy no te toca entrenar" testId="linea-entreno-descanso"
                                onClick={() => navigate('/dashboard/routine')} />
                        ) : (
                            <LineaDeHoy icono={FileText} titulo="Tu rutina, en PDF"
                                detalle="Abrirla" testId="linea-entreno-pdf" onClick={abrirPdfRutina} />
                        )
                    ) : rutinaDelMes ? (
                        <LineaDeHoy icono={Dumbbell} titulo="La rutina del mes"
                            detalle="Ver la de este mes" testId="linea-rutina-del-mes"
                            onClick={() => navigate('/dashboard/routine')} />
                    ) : (
                        /* Mantenimiento sin rutina: la tarjeta de venta, con el precio del
                           catálogo (complemento rutina_mes, «Suelta»). El cobro suelto aún
                           no tiene pantalla propia: de momento se pide por Mensajes. */
                        <LineaDeHoy icono={Dumbbell}
                            titulo={`Quiero la rutina del mes · ${Math.round(precioRutinaSuelta)} €`}
                            detalle="Pídela y te la preparamos" testId="linea-venta-rutina"
                            onClick={() => navigate('/dashboard/messages')} />
                    )}
                </section>
            )}

            <div className="space-y-3">
                {/* LA SUPLEMENTACIÓN NUNCA DICE «PENDIENTE»: se pincha y ve lo que le hemos
                    pautado. Si no tiene nada pautado, no hay línea. */}
                {nombresSuplementos && (
                    <LineaDeHoy icono={Pill} titulo="Tu suplementación"
                        detalle={suplementosTomados ? null : nombresSuplementos}
                        hecho={suplementosTomados} testId="linea-suplementacion"
                        onClick={() => navigate('/dashboard/supplements')} />
                )}

                {/* «Escribir a tu entrenador»: el apartado de contacto que el catálogo da a
                    los planes sin entrenador (hoy, ELM: «te contesta el viernes»). */}
                {escribirAlEntrenador && (
                    <LineaDeHoy icono={MessageCircle} titulo="Escribir a tu entrenador"
                        detalle={contestaElViernes ? 'Te contesta el viernes' : canalContacto}
                        testId="linea-contacto" onClick={() => navigate('/dashboard/messages')} />
                )}

                {/* Cerrado el día, la línea se queda con su marca: es lo hecho hoy,
                    no algo pendiente. */}
                {cierreDeHoy && (
                    <LineaDeHoy icono={ClipboardCheck} titulo="¿Cómo fuiste hoy?" hecho
                        testId="linea-cierre-hecho" onClick={() => navigate('/dashboard/checkins')} />
                )}

                {/* MAÑANA, al final: para programar la víspera sin pasar por Mi semana.
                    Navega a Nutrición en el día de mañana, que es donde se repite o se
                    termina. «Repetir la de hoy» se remata allí: aquí solo se abre el día. */}
                {diaCargado && (
                    <button onClick={() => navigate(`/dashboard/nutrition?date=${mananaDeLaDieta()}`)}
                        data-testid="linea-manana"
                        className="surface surface-hover w-full p-4 flex items-center gap-4 text-left group">
                        <div className="min-w-0 flex-1">
                            <p className="font-bold text-foreground text-sm">
                                Mañana <span className="text-muted-foreground font-normal">· {manana.detalle}</span>
                            </p>
                        </div>
                        <span className="text-xs font-bold uppercase tracking-wider text-brand flex-shrink-0">
                            {manana.accion}
                        </span>
                        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
                    </button>
                )}
            </div>

            {pendientes.length > 0 && (
                <section className="space-y-3">
                    <p className="caption">Pendiente</p>
                    {pendientes.map((p) => (
                        <LineaDeHoy key={p.id} icono={p.icono} titulo={p.titulo} detalle={p.detalle}
                            cursiva={p.cursiva} extra={p.extra} testId={`pendiente-${p.id}`} onClick={() => navigate(p.path)} />
                    ))}
                </section>
            )}

            {pendientes.length === 0 && (
                <p className="text-muted-foreground text-sm" data-testid="inicio-cierre">
                    {varianteDelDia(CIERRES, user?.id)}
                </p>
            )}

            {/* LA REVISIÓN PERSONALIZADA, siempre a mano. Su pantalla de venta
                (/dashboard/revision) no está en el menú a propósito -- «una línea pequeña, sin
                botón grande», documento del 06-08 --, pero la única línea que llevaba a ella
                en Inicio se quedó en el Inicio viejo. Con el Inicio nuevo encendido, quien
                salía de esa pantalla no tenía forma de volver salvo escribiendo la URL.
                También se entra desde Mis macros, que es el otro momento del documento. */}
            {profile?.ajuste_macros_completado && seLeOfreceLaRevision(profile, can) && (
                <p className="text-xs text-muted-foreground" data-testid="revision-suelta-linea">
                    ¿Prefieres que lo miremos nosotros?{' '}
                    <button onClick={() => navigate('/dashboard/revision')}
                        className="underline text-brand hover:text-brand/80 font-medium">
                        Solicita tu revisión personalizada
                    </button>.
                </p>
            )}

            {/* Y si ya la pagó, en qué punto está: si no, la pantalla de venta le vuelve a
                ofrecer lo que acaba de comprar. */}
            {profile?.revision_suelta?.estado === 'pendiente' && (
                <p className="text-xs text-muted-foreground" data-testid="revision-suelta-pendiente">
                    Tu revisión personalizada está pagada. La estamos mirando y te avisamos aquí.
                </p>
            )}
            </div>
        </div>
    );
};

// =============== CLIENT DASHBOARD ===============

const ClientDashboard = () => {
    const { user, profile, api, myPlan, planUnpaid, can, pantalla, refreshProfile } = useAuth();
    // LA VENTANA DE LAS 12 SEMANAS SE ARMA UNA VEZ Y SE QUEDA (fallo cazado en el
    // navegador): montarla marca «vista hoy», el perfil se refresca, la condición del
    // servidor pasa a false y el modal se desmontaba solo antes de que nadie lo viera.
    // El gate se fija al detectarlo y solo lo cierra una salida del propio modal.
    const [ventanaGrasaArmada, setVentanaGrasaArmada] = useState(false);
    useEffect(() => {
        if (profile?.grasa?.mostrar_ventana) setVentanaGrasaArmada(true);
    }, [profile?.grasa?.mostrar_ventana]);
    // El Inicio nuevo del doc del 16-08 (T1), detrás de su interruptor. Apagado -- que es
    // como nace -- aquí no cambia nada: se sigue viendo el Inicio de siempre.
    const inicioNuevo = pantalla('t1_inicio_nuevo');
    const enTelefono = useEsTelefono();
    const { resumeTour, active: tourActive, completed: tourCompleted } = useOnboarding();
    const navigate = useNavigate();
    const [routine, setRoutine] = useState(null);
    // ¿Hay rutina en PDF subida por su entrenador? Sin esto, el cliente con PDF y sin
    // rutina estructurada leía aquí «Sin rutina asignada» teniendo la suya subida.
    const [hayPdfRutina, setHayPdfRutina] = useState(false);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [macros, setMacros] = useState(null);
    const [todayConsumed, setTodayConsumed] = useState({ P: 0, H: 0, G: 0 });
    // EL OBJETIVO DEL DÍA, EL MISMO QUE ENSEÑA NUTRICIÓN (16-08-2026).
    //
    // Inicio pintaba el objetivo CRUDO del cliente (120 P · 50 H) y Nutrición el del día ya
    // repartido, que suma el perientreno (135 P · 65 H). Mismo día, mismo cliente, dos
    // pantallas seguidas y quince gramos de diferencia en dos macros. El día guardado ya
    // trae el total bueno en `macros_snapshot`, así que se usa ese y solo se cae al crudo
    // cuando todavía no hay día montado.
    const [totalDelDia, setTotalDelDia] = useState(null);
    const [hasPreferences, setHasPreferences] = useState(true); // optimista: evita parpadeo del checklist
    const [hasDiet, setHasDiet] = useState(false);
    // POR CLIENTE (punto 4.7). Esta bandera dice si ya cerró el checklist, y guardada sin
    // dueño el segundo que entrara en el mismo navegador se lo encontraba cerrado sin haberlo
    // tocado. La verdad vive en su perfil, en el servidor; esto es solo caché.
    const [checklistDismissed, setChecklistDismissed] = useState(false);
    useEffect(() => {
        if (user?.id) setChecklistDismissed(leerLocal('onboarding-checklist-dismissed', user.id) === '1');
    }, [user?.id]);
    const [dashDataLoaded, setDashDataLoaded] = useState(false);
    const [dueReports, setDueReports] = useState([]);

    // La compra de la revisión suelta vive ahora en su pantalla (/dashboard/revision):
    // desde aquí solo se entra, que es lo que pide el documento del 06-08-2026.

    // El cierre/completado vive en el perfil (backend); localStorage es solo caché local.
    useEffect(() => {
        if (profile?.checklist_dismissed) {
            escribirLocal('onboarding-checklist-dismissed', user?.id, '1');
            setChecklistDismissed(true);
        }
    }, [profile?.checklist_dismissed, user?.id]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                // El día LOCAL del cliente, no el UTC (bloque F, 23-08): `toISOString`
                // pedía los macros de mañana desde media tarde en América.
                const today = hoyLocal();
                const [routineRes, pdfRes, messagesRes, macrosRes, dietRes, prefsRes, dueRes] = await Promise.all([
                    api.get('/routines/current').catch(() => ({ data: null })),
                    api.get('/routines/pdf/info').catch(() => ({ data: { hay: false } })),
                    api.get('/messages/unread-count').catch(() => ({ data: { count: 0 } })),
                    api.get('/macros').catch(() => ({ data: null })),
                    api.get(`/diets/${today}`).catch(() => ({ data: { exists: false } })),
                    api.get('/user/preferences').catch(() => ({ data: { has_preferences: true } })),
                    api.get('/reports/due').catch(() => ({ data: { items: [] } })),
                ]);
                setRoutine(routineRes.data);
                setHayPdfRutina(!!pdfRes.data?.hay);
                setUnreadMessages(messagesRes.data.count);
                setDueReports(dueRes.data.items || []);
                setMacros(macrosRes.data);
                setHasPreferences(!!prefsRes.data?.has_preferences);
                const diet = dietRes.data;
                let dietHasFood = false;
                if (diet && diet.exists && diet.comidas) {
                    let totalP = 0, totalH = 0, totalG = 0;
                    Object.values(diet.comidas).forEach(meal => {
                        (meal.alimentos || []).forEach(a => {
                            const ef = a.macros_efectivos || {};
                            totalP += ef.P || 0; totalH += ef.H || 0; totalG += ef.G || 0;
                            dietHasFood = true;
                        });
                    });
                    setTodayConsumed({ P: Math.round(totalP * 10) / 10, H: Math.round(totalH * 10) / 10, G: Math.round(totalG * 10) / 10 });
                    const snap = diet.macros_snapshot;
                    if (snap && (snap.P_total || snap.H_total || snap.G_total)) {
                        setTotalDelDia({ P: snap.P_total || 0, H: snap.H_total || 0, G: snap.G_total || 0 });
                    }
                }
                setHasDiet(dietHasFood);
                setDashDataLoaded(true);
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        };
        // Con el Inicio nuevo encendido, esto no se pinta: no hay por qué pedir las seis
        // cosas que alimentan la pantalla vieja.
        if (profile && !inicioNuevo) fetchData();
    }, [api, profile, inicioNuevo]);

    const dismissChecklist = useCallback(() => {
        escribirLocal('onboarding-checklist-dismissed', user?.id, '1');
        setChecklistDismissed(true);
        api.patch('/clients/onboarding', { checklist_dismissed: true }).catch(() => {});
    }, [api, user?.id]);

    // Al completar los 3 pasos una vez, el checklist queda cerrado para siempre
    // (si no, el paso "primer día de comidas" volvería a salir incompleto cada día).
    useEffect(() => {
        if (!dashDataLoaded || checklistDismissed || !profile) return;
        const mt0 = macros?.training || profile?.macros_training;
        const done = !!(mt0 && (mt0.protein || mt0.proteinas)) && hasPreferences && hasDiet;
        if (done) dismissChecklist();
    }, [dashDataLoaded, checklistDismissed, profile, macros, hasPreferences, hasDiet, dismissChecklist]);

    // AL QUE SE LE ACABÓ EL PLAN NO SE LE DA LA BIENVENIDA (punto 41 del doc del 07-08).
    // Hasta ahora el cliente que llevaba un año pagando y terminaba su ciclo veía la misma
    // pantalla que el que acaba de registrarse: "Bienvenido a 12EN12, selecciona un plan".
    // No es lo mismo no haber empezado que haber terminado. El servidor dice cuál de los
    // tres casos es (profile.acceso.motivo).
    // `?ver=caducado` (solo equipo) enseña esta pantalla sin tener que caducarle el plan a
    // nadie: es la salida del que no renueva y hasta ahora no había forma de repasarla.
    if (profile?.acceso?.motivo === 'caducado' || verComo(user) === 'caducado') {
        return <PlanCaducado navigate={navigate} nombre={user?.name} api={api} email={user?.email} />;
    }
    if (!profile || planUnpaid) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto animate-fade-in">
                <div className="surface p-8 text-center">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Target className="w-8 h-8 text-brand" />
                    </div>
                    <h2 className="heading-2 text-foreground mb-2">Bienvenido a 12EN12</h2>
                    <p className="text-muted-foreground mb-6 text-sm">
                        {planUnpaid
                            ? 'El pago de tu plan no llegó a completarse. Elige un plan para terminar la compra.'
                            : 'Para comenzar tu transformación, selecciona un plan.'}
                    </p>
                    <button onClick={() => navigate('/onboarding')} className="btn-brand inline-flex items-center gap-2" data-testid="onboarding-btn">
                        Seleccionar plan <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
            </div>
        );
    }

    // A partir de aquí, el Inicio de siempre. El nuevo se pinta entero aparte para no
    // dejar la pantalla vieja llena de condiciones: mientras el interruptor esté apagado,
    // lo de abajo es exactamente lo que había.
    // La ventana de las 12 semanas sale en los DOS Inicios (doc 19-08): con el nuevo
    // encendido este return corta antes de llegar al bloque de abajo, y sin esto el
    // cliente del Inicio nuevo no la veía nunca.
    if (inicioNuevo) return (
        <>
            {ventanaGrasaArmada && (
                <VentanaGrasa api={api} profile={profile}
                    onCerrada={() => { setVentanaGrasaArmada(false); refreshProfile(); }} />
            )}
            <InicioNuevo />
        </>
    );

    const mt = macros?.training || profile?.macros_training;
    const mr = macros?.rest || profile?.macros_rest;
    // El perientreno y de dónde salen los macros ya no se leen aquí: se quitó el pie de la
    // tarjeta el 13-08 y no queda nadie en esta pantalla que los use.
    const hasMacros = mt && (mt.protein || mt.proteinas);

    const getP = (m) => m?.protein || m?.proteinas || 0;
    const getH = (m) => m?.carbs || m?.hidratos || 0;
    const getG = (m) => m?.fat || m?.grasas || 0;

    const checklistSteps = [
        { id: 'macros', label: 'Tus macros están calculados', sub: 'Revisa tus objetivos', done: !!hasMacros, path: '/dashboard/nutrition' },
        { id: 'preferences', label: 'Configura tus preferencias de comida', sub: 'Qué te gusta y qué evitar', done: hasPreferences, path: '/dashboard/nutrition' },
        { id: 'diet', label: 'Prepara tu primer día de comidas', sub: 'Reparte tus macros en comidas', done: hasDiet, path: '/dashboard/nutrition' },
    ];
    const showChecklist = !checklistDismissed && checklistSteps.some(s => !s.done);

    // Ciclo del plan: nº de semanas (null si es mensual indefinido / variable).
    // EL TOTAL CON EL QUE SE CONTÓ LA SEMANA, NO EL DEL CATÁLOGO (24-08). Aquí se leía
    // `myPlan.ciclo.semanas` y la semana la calcula el servidor con core/cycle, que busca el
    // plan sin resolver alias: con un perfil migrado escrito «CalMa» no le encontraba el
    // ciclo, la semana crecía sin dar la vuelta y salía «Semana 63/12». `cycle_total_weeks`
    // viene de esa misma cuenta, así que los dos números van siempre a la par.
    const cicloSemanas = profile.cycle_total_weeks ?? null;
    const weekProgress = cicloSemanas ? Math.min((profile.week / cicloSemanas) * 100, 100) : null;
    const todayRoutine = routine?.days?.find(d =>
        d.day.toLowerCase() === new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase());
    const isRestDay = todayRoutine?.is_rest;
    const activeTarget = isRestDay ? mr : mt;

    // UN AVISO CADA VEZ, EL DE MÁS ARRIBA QUE CUMPLA (documento del 10-08, pantalla 4).
    //
    // Aquí salían apilados: el reporte que toca, la checklist de primeros pasos, el de
    // ajustar macros, el de elegir plan y el del perfil a medias. Cinco tarjetas grandes,
    // una debajo de otra, antes de llegar a nada. Cuando le pides cinco cosas a la vez no
    // le estás pidiendo ninguna.
    //
    // El orden es el del documento, adaptado a los avisos que hoy tienen dato de verdad.
    // Los que faltan por poder calcularlos -- «estos son tus macros provisionales» y «ya
    // puedes hacer tu revisión mensual» -- van cuando exista de dónde sacarlos, y su sitio
    // es esta lista.
    //
    // Y SOLO EN EL TELÉFONO: en escritorio se apilan como estaban, que ahí caben y el
    // rediseño todavía no ha llegado a esa vista. `enTelefono` mira el mismo corte que usa
    // Tailwind para `lg` (1024 px), porque esto no se puede resolver con una clase: no es
    // ocultar una tarjeta, es elegir cuál de las cinco se pinta.
    const avisoPendiente = (() => {
        if (!enTelefono) return null;                                 // en escritorio, todos
        if (!myPlan) return 'plan';                                   // sin plan no puede hacer nada
        if (profile?.questionnaire_completed && !profile?.ajuste_macros_completado
            && !profile?.macros_puestos_por_alguien) return 'ajustar';
        if (can('macros_personalizados') && profile?.questionnaire_completed
            && (profile?.ajuste_macros_completado || profile?.macros_puestos_por_alguien)
            && !profile?.questionnaire_nivel1_completed) return 'perfil';
        if (dueReports.length) return 'reporte';
        if (showChecklist) return 'checklist';
        return null;
    })();
    // En el teléfono manda la lista de arriba (uno solo); en escritorio, la condición de
    // siempre de cada tarjeta, que es como estaba.
    const sale = (id, condicionDeSiempre) => (enTelefono ? avisoPendiente === id : condicionDeSiempre);

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6 animate-fade-in" data-testid="client-dashboard">
            {/* La ventana de las 12 semanas (doc 19-08): el servidor decide si toca hoy. */}
            {ventanaGrasaArmada && (
                <VentanaGrasa api={api} profile={profile}
                    onCerrada={() => { setVentanaGrasaArmada(false); refreshProfile(); }} />
            )}
            {/* LA CABECERA SE QUEDA como estaba: «Panel del cliente», el saludo y el plan
                contratado. La quité en la primera pasada por ganar los 300 px que ocupa, y
                Francisco la devolvió: «era info que no molestaba». Y es verdad que no
                molesta -- es lo primero que se lee y se lee de un vistazo --, así que lo
                que había que recortar no era esto.

                Lo único que no vuelve es la semana, que aquí salía al lado de la insignia
                del plan y ahora la lleva la tarjeta de Ciclo con su barra. Decirla dos
                veces en la misma pantalla sí sobraba. */}
            <header className="flex items-end justify-between gap-4">
                <div>
                    <p className="caption text-brand mb-1">Panel del cliente</p>
                    <h1 className="font-heading text-4xl md:text-5xl font-bold uppercase text-foreground leading-none">
                        Hola, {user?.name?.split(' ')[0]}
                    </h1>
                    <div className="flex items-center gap-3 mt-2">
                        <PlanBadge plan={profile.plan} planName={myPlan?.name} />
                        {/* La semana, solo en escritorio: en el teléfono la lleva la tarjeta
                            de Ciclo con su barra, y decirla dos veces en la misma pantalla
                            sobra. */}
                        <span className="hidden lg:inline text-muted-foreground text-sm">
                            {cicloSemanas ? `Semana ${profile.week}/${cicloSemanas}` : `Semana ${profile.week}`}
                        </span>
                    </div>
                </div>
                {unreadMessages > 0 && (
                    <button onClick={() => navigate('/dashboard/messages')} data-testid="notif-btn"
                        className="relative w-11 h-11 rounded-xl border border-border bg-card flex items-center justify-center hover:border-brand transition-colors">
                        <Bell className="w-5 h-5 text-foreground" />
                        <span className="absolute -top-1.5 -right-1.5 min-w-5 h-5 px-1 bg-brand text-white text-xs rounded-full flex items-center justify-center font-bold">{unreadMessages}</span>
                    </button>
                )}
            </header>

            {/* Reporte pendiente esta semana (amarillo en plazo, rojo vencido). Solo el
                primero: si le tocan dos, el segundo sale cuando mande el primero. */}
            {sale('reporte', dueReports.length > 0) && (enTelefono ? dueReports.slice(0, 1) : dueReports).map((r) => (
                <div key={r.tipo}
                    className={`surface p-4 flex flex-col sm:flex-row sm:items-center gap-3 border ${
                        r.overdue ? 'border-red-500/40 bg-red-500/5' : 'border-yellow-500/40 bg-yellow-500/5'
                    }`}
                    data-testid={`due-report-${r.tipo}`}>
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        r.overdue ? 'bg-red-500/15' : 'bg-yellow-500/15'
                    }`}>
                        <AlertTriangle className={`w-5 h-5 ${r.overdue ? 'text-red-500' : 'text-yellow-500'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-foreground font-semibold text-sm">
                            {r.overdue
                                ? `Tu ${r.tipo_label.toLowerCase()} está fuera de plazo`
                                : r.is_open
                                    ? `Tienes tu ${r.tipo_label.toLowerCase()} pendiente`
                                    : `Este fin de semana toca tu ${r.tipo_label.toLowerCase()}`}
                        </p>
                        <p className="text-muted-foreground text-xs">
                            {r.overdue
                                ? 'La ventana de esta semana se cerró; podrás enviarlo la próxima.'
                                : r.is_open
                                    ? `Rellénalo antes del ${r.deadline_label}.`
                                    : `La ventana abre el ${r.opens_label}.`}
                        </p>
                    </div>
                    {r.is_open && (
                        <button onClick={() => navigate('/dashboard/reports')}
                            className="btn-brand flex items-center gap-1.5 text-sm flex-shrink-0 self-start sm:self-auto"
                            data-testid={`due-report-btn-${r.tipo}`}>
                            Hacer reporte <ChevronRight className="w-4 h-4" />
                        </button>
                    )}
                </div>
            ))}

            {/* Checklist de primeros pasos */}
            {sale('checklist', showChecklist) && (
                <OnboardingChecklist steps={checklistSteps} onDismiss={dismissChecklist} navigate={navigate}
                    onResume={resumeTour} showResume={!tourCompleted && !tourActive} />
            )}

            {/* Main grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Macros / Today */}
                <div className="lg:col-span-8">
                    {hasMacros ? (
                        <div className="surface surface-hover overflow-hidden cursor-pointer h-full" data-testid="macro-trackers-card" onClick={() => navigate('/dashboard/nutrition')}>
                            {/* LA FECHA ARRIBA, y el tipo de día detrás (documento del 10-08,
                                pantalla 4). Antes ponía «Hoy · Entreno», que no sitúa: el
                                cliente que abre la app a las once de la noche o el que navega
                                a otro día necesita ver de qué día son estos números. */}
                            <div className="px-5 pt-5 pb-1">
                                <p className="text-sm font-semibold text-foreground first-letter:uppercase" data-testid="hoy-fecha">
                                    {new Date().toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
                                    {/* «DÍA DE ENTRENO», no «entreno» (Francisco, 13-08-2026).
                                        Suelto detrás de la fecha, «entreno» se lee como si
                                        fuera la hora del entrenamiento y no lo que es: el tipo
                                        de día del que salen estos macros. El descanso va igual,
                                        que si no la misma línea dice una cosa de dos maneras. */}
                                    <span className="text-muted-foreground font-normal"> · {isRestDay ? 'día de descanso' : 'día de entreno'}</span>
                                </p>
                            </div>
                            <div className="px-5 pb-5 pt-3">
                                {/* NÚMEROS GRANDES, SIN ANILLO. Del documento: «el anillo dice
                                    lo mismo que la barra, y la barra ocupa una décima parte».
                                    En el teléfono estaban las dos cosas -- tres anillos de
                                    92 px y, debajo, tres barras con los mismos números --,
                                    media pantalla para decir una cosa dos veces.

                                    En el ordenador seguían los anillos, porque el encargo era
                                    no tocar el escritorio. Jesús, 11-08: *«el anillo se ve
                                    bonito y hay que interpretarlo»*. Con el número hay que
                                    hacer una resta, pero al menos está escrito; con el anillo
                                    hay que medir un hueco a ojo.

                                    Ojo, que él compara con el «te queda por comer» del móvil y
                                    eso es de OTRA pantalla: vive en la cabecera de Nutrición
                                    (DayHeader). Aquí, en Inicio, se enseña lo comido sobre el
                                    objetivo, y así es en los dos aparatos. Si hay que cambiar
                                    a «lo que queda», se cambia en Inicio para los dos, y esa
                                    es una decisión aparte -- no parte de igualar el escritorio
                                    con el móvil, que es lo que se está haciendo aquí. */}
                                <div className="grid grid-cols-3 gap-3">
                                    <MacroGrande valor={todayConsumed.P} objetivo={totalDelDia ? totalDelDia.P : getP(activeTarget)} label="Proteína" color={MACRO.protein} />
                                    <MacroGrande valor={todayConsumed.H} objetivo={totalDelDia ? totalDelDia.H : getH(activeTarget)} label="Hidratos" color={MACRO.carbs} />
                                    <MacroGrande valor={todayConsumed.G} objetivo={totalDelDia ? totalDelDia.G : getG(activeTarget)} label="Grasa" color={MACRO.fat} />
                                </div>
                            </div>
                            {/* AQUÍ IBA EL PIE DEL PERIENTRENO, y se ha quitado entero
                                (Francisco, 13-08-2026): «lo de perientreno lo ajustas tú, eso
                                sobra».

                                Eran dos datos que no pintan nada en Inicio. El perientreno ya
                                está sumado en los tres números grandes de arriba, así que
                                repetirlo suelto solo invita a restar. Y el «lo ajustas tú» era
                                el último resto de la palabra cruda del dato («MANUAL»/«AUTO»),
                                que el 11-08 se tradujo a algo legible en vez de quitarse: al
                                cliente le da igual quién le cuadró los macros, y en Inicio no
                                puede hacer nada con esa información.

                                Donde sí vive esto es en Nutrición (DaySummary y DayHeader),
                                que es la pantalla donde se reparten las comidas. */}
                        </div>
                    ) : (
                        <button onClick={() => navigate('/dashboard/macro-calculator')} data-testid="setup-macros-card"
                            className="surface surface-hover w-full p-6 text-center h-full">
                            <Scale className="w-8 h-8 text-brand mx-auto mb-2" />
                            <p className="font-bold text-foreground text-sm uppercase">Configura tus macros</p>
                            <p className="text-muted-foreground text-xs mt-1">Introduce tu peso, % graso y objetivo</p>
                        </button>
                    )}
                </div>

                {/* La columna de al lado, tal cual estaba. EL CICLO SE QUEDA también en el
                    teléfono: lo quité en la primera pasada por considerarlo repetido con la
                    semana de la cabecera, y Francisco lo devolvió. El número dice en qué
                    semana está; la barra dice cuánto le queda, que es lo que sitúa en un
                    método que se llama 12 en 12. */}
                <div className="lg:col-span-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-5">
                <div className="surface p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="caption">Ciclo</span>
                        <span className="text-xs text-muted-foreground font-data">
                            {cicloSemanas ? `${profile.week}/${cicloSemanas}` : `Semana ${profile.week}`}
                        </span>
                    </div>
                    {cicloSemanas ? (
                        <>
                            <div className="w-full bg-muted rounded-full h-2">
                                <div className="bg-brand h-2 rounded-full transition-all duration-500" style={{ width: `${weekProgress}%` }} />
                            </div>
                            <p className="text-xs text-muted-foreground mt-2">Semana {profile.week} de tu ciclo de {plural(cicloSemanas, 'semana')}</p>
                        </>
                    ) : (
                        <p className="text-xs text-muted-foreground mt-1">Plan mensual · semana {profile.week}</p>
                    )}
                    {(myPlan?.habilitaciones?.reportes?.length > 0) && (
                        <p className="text-[11px] text-muted-foreground mt-2 capitalize">
                            Reportes: {myPlan.habilitaciones.reportes.join(' + ')}
                        </p>
                    )}
                </div>

                {/* La próxima renovación, solo en escritorio: en el teléfono es de Mi perfil,
                    que es donde alguien va a mirar qué paga y cuándo. */}
                {profile.next_payment && (
                    <div className="hidden lg:flex surface p-4 items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
                            <CreditCard className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                            <p className="caption">Próxima renovación</p>
                            <p className="text-sm text-foreground mt-0.5">
                                {new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })} · <span className="text-brand font-bold font-data">{profile.price}€</span>
                            </p>
                        </div>
                    </div>
                )}
                </div>
            </div>

            {/* Ajustar macros: el cuestionario del paso 2. Sale mientras tenga los macros
                provisionales del alta, porque hasta que lo rellene sus numeros no estan ajustados.
                En el plan con coach el boton se llama "Rellena tu formulario", que es lo que es:
                el coach lo revisa con el despues. */}
            {/* Aquí se separan los planes: el mismo hueco dice tres cosas distintas.
                El Nivel 3 no rellena nada -- se lo preguntan en la llamada -- así que ni
                se le manda al cuestionario ni se le dice que le falta algo por hacer. */}
            {/* Y SOLO SI DE VERDAD LE FALTA (punto 4.1). `ajuste_macros_completado` es False
                para todo el que no pasó por NUESTRO cuestionario de ajuste, y eso son los 160
                que vinieron de Calma más todo aquel al que el coach le puso los macros a mano:
                medido en producción, 169 de los 174 activos veían este aviso. Gente que lleva
                meses con Jesús, a la que él mismo les pone los números cada quincena, abriendo
                la app y leyendo que les falta terminar de sacar sus macros.
                `macros_puestos_por_alguien` lo calcula el servidor mirando quién escribió su
                último ajuste. */}
            {sale('ajustar', profile?.questionnaire_completed && !profile?.ajuste_macros_completado
                && !profile?.macros_puestos_por_alguien) && (() => {
                const porLlamada = (profile?.plan || '') === 'nivel3';
                const conCoach = can('macros_personalizados');
                const texto = porLlamada
                    ? { titulo: 'Agenda tu llamada',
                        desc: 'Tus macros los sacamos contigo en la llamada. No tienes que rellenar nada.' }
                    : conCoach
                        ? { titulo: 'Completa tu cuestionario inicial',
                            desc: 'Unas preguntas más y nos ponemos con tus números.' }
                        : { titulo: 'Termina de ajustar tus macros iniciales',
                            // Fuera «los tienes finos» (punto 82 del 23-08).
                            desc: 'Unas preguntas más y tendrás tus macros definitivos.' };
                return (
                    <button onClick={() => navigate(porLlamada ? '/dashboard/messages' : '/questionnaire?ajustar=1')}
                        data-testid="ajustar-macros-banner"
                        className="surface surface-hover w-full p-4 flex items-center justify-between group border-2 border-brand/40">
                        <div className="flex items-center gap-4">
                            <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                                {porLlamada ? <Phone className="w-5 h-5 text-brand" />
                                            : <SlidersHorizontal className="w-5 h-5 text-brand" />}
                            </div>
                            <div className="text-left">
                                <p className="font-bold text-foreground text-sm uppercase tracking-wide">{texto.titulo}</p>
                                <p className="text-muted-foreground text-sm">{texto.desc}</p>
                            </div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                    </button>
                );
            })()}

            {/* Sin plan contratado no puede hacer casi nada, y hasta ahora no habia forma de
                llegar a contratarlo desde dentro de la app. Va lo primero a proposito. */}
            {sale('plan', !myPlan) && (
                <button onClick={() => navigate('/planes')} data-testid="elegir-plan-banner"
                    className="surface surface-hover w-full p-4 flex items-center justify-between group border border-brand/40">
                    <div className="flex items-center gap-4">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-brand" />
                        </div>
                        <div className="text-left">
                            <p className="font-bold text-foreground text-sm uppercase tracking-wide">
                                {planUnpaid ? 'Te quedó un pago a medias' : 'Elige cómo quieres hacerlo'}
                            </p>
                            <p className="text-muted-foreground text-sm">
                                {planUnpaid
                                    ? 'Retoma donde lo dejaste y empieza.'
                                    : 'Tres niveles, el mismo método. Cambia cuánta gente hay detrás de tus números.'}
                            </p>
                        </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                </button>
            )}

            {/* Revisión suelta: solo para quien se autogestiona y ya tiene sus macros ajustados.
                Es la puerta de entrada a tener coach: prueba lo que se siente y, si sube de plan
                en 30 días, lo que pagó se le descuenta.

                Era una tarjeta grande con su flecha. El documento de Jesús del 06-08-2026 dice
                que esto va "como una línea pequeña, sin botón grande", y que nunca interrumpa:
                lo que vende es la pantalla (/dashboard/revision), no el sitio desde el que se
                entra. Los dos momentos de verdad son al recibir los macros de inicio y al
                recibir el ajuste del mes; esto es solo la puerta que queda siempre a mano. */}
            {profile?.ajuste_macros_completado && seLeOfreceLaRevision(profile, can) && (
                <p className="text-xs text-muted-foreground px-1" data-testid="revision-suelta-banner">
                    ¿Prefieres que lo miremos nosotros?{' '}
                    <button onClick={() => navigate('/dashboard/revision')}
                        className="underline text-brand hover:text-brand/80 font-medium">
                        Solicita tu revisión personalizada
                    </button>.
                </p>
            )}

            {/* Ya la pagó: que sepa en qué punto está. */}
            {profile?.revision_suelta?.estado === 'pendiente' && (
                <div className="surface w-full p-4 flex items-center gap-4 border border-brand/30">
                    <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                        <ClipboardCheck className="w-5 h-5 text-brand" />
                    </div>
                    <div>
                        <p className="font-bold text-foreground text-sm uppercase tracking-wide">Revisión en marcha</p>
                        <p className="text-muted-foreground text-sm">
                            Estamos revisando tus macros. Te avisamos en cuanto estén.
                        </p>
                    </div>
                </div>
            )}

            {/* Cuestionario Nivel 1 pendiente (planes con coach): retomable, no bloqueante.
                UN AVISO CADA VEZ, NO DOS (punto 17). Antes este salía a la vez que el de
                arriba, así que el cliente veía «Completa tu cuestionario inicial» y
                «Completa tu perfil para tu coach» uno debajo del otro y parecía que había
                dos cuestionarios. No los hay: es el mismo recorrido, y el de arriba sigue
                de largo hasta aquí sin cortes. Este solo tiene sentido cuando el de arriba
                ya está hecho -- es decir, cuando de verdad se quedó a medias. */}
            {/* Y también para quien compró el ajuste a medida: hace el completo igual que un
                Gold (doc del cuestionario, 18-08), así que la tarjeta que le lleva a
                terminarlo tiene que salirle a él también. */}
            {sale('perfil', (can('macros_personalizados') || profile?.ajuste_a_medida?.cobrado)
                && profile?.questionnaire_completed
                && (profile?.ajuste_macros_completado || profile?.macros_puestos_por_alguien)
                && !profile?.questionnaire_nivel1_completed) && (
                <button onClick={() => navigate('/questionnaire')} data-testid="nivel1-pending-banner"
                    className="surface surface-hover w-full p-4 flex items-center justify-between group border-2 border-brand/40">
                    <div className="flex items-center gap-4">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                            <ClipboardCheck className="w-5 h-5 text-brand" />
                        </div>
                        <div className="text-left">
                            {/* NI «COACH» NI «ENTRENADOR»: HABLAMOS EN PLURAL.
                                El 4.18 cambió «coach» por «entrenador»; el repaso del 11-08 va
                                un paso más allá y quita los dos de todo lo que lee el cliente.
                                Y de paso el aviso dice qué gana él, no a quién le llega. */}
                            {/* «TERMINAMOS DE AJUSTAR», no «te afinamos» (Francisco, 13-08).
                                Afinar suena a retoque fino de algo que ya está bien; lo que
                                pasa de verdad es que los macros están a medias hasta que
                                conteste, y la frase tiene que decir eso. */}
                            <p className="font-bold text-foreground text-sm uppercase tracking-wide">Completa tu perfil y terminamos de ajustar tus macros</p>
                            <p className="text-muted-foreground text-sm">Te quedan unas preguntas: biotipo, salud, entreno...</p>
                        </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                </button>
            )}

            {/* Today routine highlight (solo si el plan incluye rutina) */}
            {can('rutina') && (
            <button onClick={() => navigate('/dashboard/routine')} data-testid="routine-card"
                className="surface surface-hover w-full p-5 flex items-center justify-between group">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center group-hover:bg-brand/15 transition-colors">
                        <Dumbbell className="w-6 h-6 text-brand" />
                    </div>
                    <div className="text-left">
                        <p className="font-bold text-foreground text-sm uppercase tracking-wide">Entreno de hoy · <span className="capitalize font-medium text-muted-foreground">{new Date().toLocaleDateString('es-ES', { weekday: 'long' })}</span></p>
                        {todayRoutine ? (
                            todayRoutine.is_rest
                                ? <p className="text-muted-foreground text-sm">Día de descanso activo</p>
                                : <p className="text-muted-foreground text-sm">{plural(todayRoutine.exercises?.length || 0, 'ejercicio')} programados</p>
                        ) : hayPdfRutina
                            /* Con PDF subido no hay «sin rutina» que valga: la tarjeta ya
                               lleva a /dashboard/routine, donde se abre. */
                            ? <p className="text-muted-foreground text-sm">Tu rutina está en PDF. Entra a verla</p>
                            : <p className="text-muted-foreground text-sm">Sin rutina asignada</p>}
                    </div>
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
            </button>
            )}

            {/* AQUÍ IBAN LOS OCHO ACCESOS RÁPIDOS.
                «Repetían la barra de abajo. Eran cuatro cosas que ocupaban media pantalla y
                no llevaban a ningún sitio nuevo» (documento del 10-08, pantalla 4). En el
                teléfono eran ocho, con icono, título y subtítulo, y se llevaban 1.000 de los
                1.616 px de la pantalla, así que se quitaron.

                En el ordenador se quedaron, porque el encargo era no tocar el escritorio, y
                ahí duplicaban la barra lateral entera: Nutrición, Macros, Asistente,
                Reportes, Alimentos, Suplementos, Check-ins y Chat ya están a la izquierda y
                siempre a la vista, que es más de lo que tiene el móvil (Jesús, 11-08). No se
                pierde ninguna puerta, se deja de tener dos veces la misma. */}
        </div>
    );
};

// =============== NAV CONFIG ===============

// `cap`: capacidad del plan requerida para ver el ítem (ver lib/planAccess.js).
// Sin `cap` = siempre visible.
const NAV_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina', cap: 'rutina' },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/foods', icon: Search, label: 'Alimentos' },
    // «MIS MACROS» EN TODOS LOS PLANES (tarea 7.3 del 21-08, hueco 1c del doc de Jesús):
    // el rótulo del menú es el nombre de la pantalla, y la pantalla la tiene todo el
    // mundo -- el de autogestión con su calculadora, el de coach en solo lectura --.
    // Lo que cambia por plan se decide DENTRO (macros_ajustables y ventana_revision),
    // no escondiendo la entrada.
    { path: '/dashboard/macro-calculator', icon: SlidersHorizontal, label: 'Mis macros' },
    { path: '/dashboard/supplements', icon: Pill, label: 'Suplementos', cap: 'suplementacion' },
    { path: '/dashboard/chatbot', icon: Bot, label: 'Asistente IA' },
    // Seguimiento y el cierre del día van con la llave del cierre (24-08), no con la de
    // reportes: dentro de Seguimiento el que no vende reportes ve su historial, su
    // Evolución y su Diario, y no ve el formulario. Ver CAP.CIERRE_DIA en lib/planAccess.js.
    { path: '/dashboard/reports', icon: FileText, label: 'Reportes', cap: 'cierre_dia' },
    { path: '/dashboard/checkins', icon: ClipboardCheck, label: 'Check-ins', cap: 'cierre_dia' },
    // El plan «solo app» no lleva entrenador: enseñarle el Chat es prometerle una persona
    // que no tiene (TABLA 20 del documento del 09-08).
    { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat', cap: 'chat' },
    { path: '/dashboard/profile', icon: User, label: 'Mi perfil' },
];

// LAS CUATRO DE ABAJO (documento del 10-08): Inicio · Nutrición · Seguimiento · Perfil.
//
// Antes eran tres más un botón «Más» que abría un cajón con las once. Dos problemas: el
// cajón escondía media app detrás de una palabra que no dice nada, y «Macros» ocupaba un
// hueco de cuatro para una pantalla a la que se entra una vez al mes.
//
// «Seguimiento» en vez de «Reportes» es del documento, y es la unificación de las cuatro
// vías de hoy (reportes, check-ins, fotos e informe). Mientras esas cuatro no se junten de
// verdad -- pantallas 20 a 24 del recorrido -- apunta a Reportes, que es donde está lo
// principal, y las otras siguen alcanzables desde Perfil.
//
// Todo lo que sale de aquí tiene su entrada en Perfil. Ninguna pantalla se queda sin puerta.
const BOTTOM_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/reports', icon: TrendingUp, label: 'Seguimiento', cap: 'cierre_dia' },
    { path: '/dashboard/profile', icon: User, label: 'Perfil' },
];

const SidebarLink = ({ item, collapsed, unread, onClick }) => (
    <NavLink to={item.path} end={item.end} onClick={onClick}
        title={collapsed ? item.label : undefined}
        className={({ isActive }) => `relative flex items-center gap-3 rounded-xl transition-all ${collapsed ? 'justify-center px-0 py-3' : 'px-3.5 py-2.5'} ${isActive ? 'bg-brand text-white font-semibold' : 'text-white/60 hover:text-white hover:bg-white/[0.07]'}`}
        data-testid={`nav-${slug(item.label)}`}>
        <span className="relative flex-shrink-0">
            <item.icon className="w-5 h-5" strokeWidth={2} />
            {item.path.includes('messages') && unread > 0 && (
                <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-brand text-white text-[10px] rounded-full flex items-center justify-center font-bold border border-ink">{unread}</span>
            )}
        </span>
        {!collapsed && <span className="text-sm">{item.label}</span>}
    </NavLink>
);

// =============== CLIENT LAYOUT ===============

const ClientLayout = () => {
    const { user, logout, profile, perfilNoCargado, api, can, planUnpaid, myPlan, pantalla, refreshProfile } = useAuth();

    // AVISO DE MODO PRUEBAS: si el que prueba ha puesto su cuenta en un estado ficticio
    // (caducado, sin plan...), puede quedarse sin forma de volver desde esa misma pantalla.
    // Este botón flotante lo restaura desde cualquier sitio. Solo para cuentas es_pruebas.
    const restaurarPruebas = async () => {
        try {
            await api.post('/settings/mis-pruebas/restaurar');
            await refreshProfile();
        } catch (e) { /* silencioso: es una herramienta interna */ }
    };
    // «MIS MACROS» PARA TODOS (tarea 7.3 del 21-08). El doc 19-08 la había quitado al de
    // coach («un papel colgado en la pared»); el hueco 1c del doc de Jesús lo revierte:
    // la pestaña existe en todos los planes -- en solo lectura para quien no edita -- y
    // dentro viven sus tres bloques (los de ahora, cambiarlos tú, el botón Revisar).
    // «SEGUIMIENTO» ES LA ÚNICA PUERTA, EN EL TELÉFONO Y EN EL ORDENADOR.
    //
    // El menú tenía «Reportes» y «Check-ins» como dos entradas distintas, y el cliente tenía
    // que saber de antemano en cuál de las dos está lo que busca. Las dos se sustituyen por
    // una sola, «Seguimiento», que es la portada desde la que se entra a cada cosa: la
    // revisión del mes, el check-in de hoy, la evolución y lo ya mandado.
    //
    // Esto se hizo el 10-08 solo en el teléfono, porque el encargo era no tocar el
    // escritorio. Jesús, 11-08: *«en el teléfono hay nueve entradas y una se llama
    // Seguimiento; en el ordenador hay once, y ahí siguen Reportes y Check-ins por
    // separado»*. La misma persona abre la app en el móvil por la mañana y en el ordenador
    // por la tarde: si la sección se llama distinto en cada sitio, la busca dos veces. Una
    // sola lista para los dos.
    //
    // La ruta /dashboard/checkins sigue viva: lo que desaparece es la entrada del menú, no
    // la pantalla, y a ella se entra desde Seguimiento.
    const navItems = NAV_ITEMS
        .filter(i => (!i.cap || can(i.cap)) && i.path !== '/dashboard/checkins')
        .map(i => i.path === '/dashboard/reports'
            ? { ...i, icon: TrendingUp, label: 'Seguimiento' }
            : i)
        // «MI SEMANA» TAMBIÉN EN EL ORDENADOR: la página nació el 21-08 con su única
        // puerta en la barra de abajo del móvil, y en escritorio solo se llegaba por
        // URL. Entra en el menú lateral entre Inicio y Rutina -- el orden de la barra
        // del móvil -- y detrás del MISMO interruptor que ella (t1_inicio_nuevo), para
        // que el lunes se encienda todo junto. En el móvil no duplica nada: la hoja de
        // «Más» descarta las rutas que ya están en la barra.
        .flatMap(i => (i.path === '/dashboard' && pantalla('t1_inicio_nuevo'))
            ? [i, { path: '/dashboard/semana', icon: CalendarRange, label: 'Mi semana' }]
            : [i]);
    // La barra de abajo no se toca: ahí ya pone «Macros» a secas, que vale para los dos casos y
    // es lo que cabe en un móvil.
    const bottomItems = BOTTOM_ITEMS.filter(i => !i.cap || can(i.cap));
    const navigate = useNavigate();
    const location = useLocation();
    const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === '1');
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [unread, setUnread] = useState(0);

    // Campanita: novedades del coach (rutina, macros, feedback, suplementos, coach)
    const [notifCount, setNotifCount] = useState(0);
    const [notifOpen, setNotifOpen] = useState(false);
    const [notifItems, setNotifItems] = useState([]);
    // Si ya se preguntó o se está preguntando. El panel se abre antes de que lleguen los
    // avisos, y sin esto la primera vez decía «No hay nada pendiente» encima de una lista
    // que estaba llegando: al segundo intento aparecían. Decirle que no tiene nada cuando
    // todavía no se sabe es lo mismo que mentirle.
    const [notifCargando, setNotifCargando] = useState(false);

    useEffect(() => {
        api.get('/messages/unread-count').then(r => setUnread(r.data.count || 0)).catch(() => {});
        api.get('/notifications/unread-count').then(r => setNotifCount(r.data.count || 0)).catch(() => {});
    }, [api, location.pathname]);

    const openNotifications = async () => {
        setNotifOpen(true);
        setNotifCargando(true);
        try {
            const res = await api.get('/notifications');
            setNotifItems(res.data.notifications || []);
            if (notifCount > 0) {
                await api.put('/notifications/read-all');
                setNotifCount(0);
            }
        } catch { /* silencioso */ } finally {
            setNotifCargando(false);
        }
    };

    const notifTime = (iso) => {
        const d = new Date(iso);
        const days = Math.floor((new Date() - d) / 86400000);
        if (days === 0) return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        if (days === 1) return 'Ayer';
        return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
    };

    // Cuestionario inicial: tras contratar un plan (perfil activo), si no lo ha
    // completado, forzar el quiz para calcular sus macros. Mientras el pago esté
    // pendiente (status != 'activo') no se fuerza.
    useEffect(() => {
        if (profile && profile.status === 'activo' && !profile.questionnaire_completed) {
            navigate('/questionnaire', { replace: true });
        }
    }, [profile, navigate]);

    useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

    const toggleCollapsed = useCallback(() => {
        setCollapsed(c => { localStorage.setItem('sidebar-collapsed', !c ? '1' : '0'); return !c; });
    }, []);

    const handleLogout = () => { logout(); navigate('/auth'); toast.success('Sesión cerrada'); };
    const isStaff = ['admin', 'trainer'].includes(user?.role);

    const UserChip = ({ compact }) => (
        <div className={`flex items-center gap-3 ${compact ? 'justify-center' : ''}`}>
            <div className="w-10 h-10 bg-brand/15 rounded-xl flex items-center justify-center flex-shrink-0">
                <span className="text-brand font-bold font-heading text-lg">{user?.name?.charAt(0)?.toUpperCase()}</span>
            </div>
            {!compact && (
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-white text-sm truncate">{user?.name}</p>
                    {profile && !planUnpaid && <PlanBadge plan={profile.plan} planName={myPlan?.name} />}
                </div>
            )}
        </div>
    );

    return (
        <div className="min-h-screen bg-background flex">
            {/* Aviso flotante de modo pruebas: solo para cuentas es_pruebas con un escenario puesto. */}
            {user?.es_pruebas && profile?.pruebas_escenario && (
                <div className="fixed bottom-24 lg:bottom-6 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3 rounded-full border border-yellow-500/50 bg-yellow-500/15 backdrop-blur px-4 py-2 shadow-lg">
                    <span className="text-xs font-semibold text-yellow-200">Cuenta en modo prueba: {profile.pruebas_escenario}</span>
                    <button onClick={restaurarPruebas} className="text-xs font-bold rounded-full bg-yellow-500 text-black px-3 py-1 hover:bg-yellow-400 transition-colors">
                        Restaurar
                    </button>
                </div>
            )}
            {/* ===== Desktop sidebar ===== */}
            <aside className={`hidden lg:flex flex-col bg-ink h-screen sticky top-0 flex-shrink-0 transition-[width] duration-300 ${collapsed ? 'w-[78px]' : 'w-64'}`} data-testid="desktop-sidebar">
                <div className={`flex items-center h-16 border-b border-white/10 ${collapsed ? 'justify-center px-0' : 'justify-between px-4'}`}>
                    {!collapsed && <Logo12EN12 size="sm" tone="dark" />}
                    <button onClick={toggleCollapsed} data-testid="sidebar-toggle"
                        className="w-9 h-9 rounded-lg flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-colors">
                        {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
                    </button>
                </div>
                <nav className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-1">
                    {/* «AVISOS», NO «NOVEDADES» (Jesús, 18-08). Dentro de la app todo esto
                        son avisos -- así se llaman en el doc del 16-08 y así se los nombra
                        él -- y el rótulo era lo único que seguía diciendo otra cosa. */}
                    <button onClick={openNotifications} data-testid="client-bell-desktop"
                        title={collapsed ? 'Avisos' : undefined}
                        className={`relative flex items-center gap-3 rounded-xl w-full transition-all text-white/60 hover:text-white hover:bg-white/[0.07] ${collapsed ? 'justify-center px-0 py-3' : 'px-3.5 py-2.5'}`}>
                        <span className="relative flex-shrink-0">
                            <Bell className="w-5 h-5" strokeWidth={2} />
                            {(notifCount + unread) > 0 && (
                                <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-brand text-white text-[10px] rounded-full flex items-center justify-center font-bold border border-ink">{notifCount + unread}</span>
                            )}
                        </span>
                        {!collapsed && <span className="text-sm">Avisos</span>}
                    </button>
                    {navItems.map(item => <SidebarLink key={item.path} item={item} collapsed={collapsed} unread={unread} />)}
                </nav>
                <div className="p-3 border-t border-white/10 space-y-2">
                    <UserChip compact={collapsed} />
                    {isStaff && (
                        <button onClick={() => navigate('/admin')} data-testid="go-admin-btn"
                            className={`flex items-center gap-2 w-full rounded-lg text-white/50 hover:text-brand hover:bg-brand/10 transition-colors ${collapsed ? 'justify-center py-2.5' : 'px-3 py-2.5'}`}>
                            <LayoutDashboard className="w-4 h-4" /> {!collapsed && <span className="text-sm">Volver al panel</span>}
                        </button>
                    )}
                    <button onClick={handleLogout} data-testid="logout-btn"
                        className={`flex items-center gap-2 w-full rounded-lg text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors ${collapsed ? 'justify-center py-2.5' : 'px-3 py-2.5'}`}>
                        <LogOut className="w-4 h-4" /> {!collapsed && <span className="text-sm">Cerrar sesión</span>}
                    </button>
                </div>
            </aside>

            {/* ===== Main ===== */}
            <div className="flex-1 min-w-0 flex flex-col">
                {/* Mobile top bar */}
                {/* EL LOGO, CENTRADO DE VERDAD. Con `justify-between` el logo se coloca entre
                    lo que tiene a los lados, y a la izquierda hay un botón y a la derecha
                    dos: quedaba desplazado a la izquierda. Se centra sobre la barra entera y
                    los dos grupos de botones se quedan en sus esquinas. */}
                <header className="lg:hidden sticky top-0 z-40 bg-ink h-14 flex items-center justify-between px-4 relative">
                    <button onClick={() => setDrawerOpen(true)} data-testid="mobile-menu-btn"
                        className="w-10 h-10 -ml-2 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10 relative z-10">
                        <Menu className="w-6 h-6" />
                    </button>
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <Logo12EN12 size="sm" tone="dark" />
                    </div>
                    <div className="flex items-center -mr-2 relative z-10">
                        <button onClick={openNotifications} data-testid="client-bell"
                            className="relative w-10 h-10 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10">
                            <Bell className="w-5 h-5" />
                            {(notifCount + unread) > 0 && <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-brand rounded-full" />}
                        </button>
                    </div>
                </header>

                <main className="flex-1 pb-20 lg:pb-0">
                    {/* Si el perfil no ha podido cargarse, DECIRLO. Sin esto la app se
                        comporta como si el cliente no tuviera plan -- sin macros, sin
                        acceso -- y él no tiene forma de saber que lo que ve es un fallo
                        y no su cuenta. */}
                    {perfilNoCargado && (
                        <div data-testid="aviso-perfil-no-cargado"
                            className="mx-4 mt-4 rounded-lg border border-amber-400/40 bg-amber-50 dark:bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
                            No hemos podido cargar tus datos ahora mismo, así que puede que
                            veas la app incompleta. Vuelve a entrar en un momento y, si sigue
                            igual, escríbenos.
                        </div>
                    )}
                    {/* Igual que en el panel del coach: un fallo de una pantalla no puede
                        dejar al cliente sin app. Ver LimiteDeError. */}
                    <LimiteDeError clave={location.pathname + location.search}>
                        <Outlet />
                    </LimiteDeError>
                </main>
            </div>

            {/* ===== Mobile bottom nav ===== */}
            {/* LA BARRA NUEVA DEL DOC (21-08): Inicio · Mi semana · Rutina · Más, detrás
                del MISMO interruptor que el Inicio nuevo (t1_inicio_nuevo) para que el
                lunes se encienda todo junto. Apagado, la barra de siempre, sin cambios. */}
            {pantalla('t1_inicio_nuevo') ? (
                <BottomNav items={navItems} unread={unread} />
            ) : (
            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-ink border-t border-white/10" data-testid="mobile-bottom-nav">
                <div className="flex items-stretch h-16">
                    {bottomItems.map(item => (
                        <NavLink key={item.path} to={item.path} end={item.end}
                            className={({ isActive }) => `flex flex-col items-center justify-center flex-1 min-w-0 gap-1 px-0.5 transition-colors ${isActive ? 'text-brand' : 'text-white/55'}`}
                            data-testid={`bottomnav-${slug(item.label)}`}>
                            {({ isActive }) => (<>
                                <item.icon className="w-[22px] h-[22px] flex-shrink-0" strokeWidth={isActive ? 2.5 : 2} />
                                {/* `min-w-0` y `truncate`: sin eso, «Seguimiento» marca el ancho
                                    mínimo de su cuarto de barra y en un móvil estrecho la barra
                                    entera se pasa de la pantalla. Medido a 280 px. */}
                                <span className={`text-[10px] max-w-full truncate ${isActive ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </>)}
                        </NavLink>
                    ))}
                    {/* SIN «MÁS» (documento del 10-08): eran cuatro pestañas y un cajón que
                        escondía media app detrás de una palabra que no dice qué hay dentro.
                        Lo que había en el cajón vive ahora en Perfil, con su nombre.
                        El cajón sigue existiendo para el escritorio, donde es la barra
                        lateral entera y ahí sí tiene sentido.
                        (Con `t1_inicio_nuevo` encendido manda la barra nueva de arriba,
                        que vuelve a traer «Más»: es lo que piden los mockups del 21-08.) */}
                </div>
            </nav>
            )}

            {/* ===== Panel de avisos (campanita) ===== */}
            {notifOpen && (
                <div className="fixed inset-0 z-[80] flex items-start justify-center p-4 pt-16 lg:pt-24" data-testid="notif-panel">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setNotifOpen(false)} />
                    <div className="relative bg-card border border-border rounded-2xl shadow-xl w-full max-w-sm max-h-[70vh] flex flex-col animate-slide-up">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                            <p className="font-bold text-foreground uppercase tracking-wider text-sm">Avisos</p>
                            <button onClick={() => setNotifOpen(false)} className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            {unread > 0 && (
                                <button onClick={() => { setNotifOpen(false); navigate('/dashboard/messages'); }}
                                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted border-b border-border">
                                    <Bell className="w-4 h-4 text-brand flex-shrink-0" />
                                    <span className="text-sm text-foreground flex-1">Tienes {unread} mensaje{unread > 1 ? 's' : ''} sin leer</span>
                                </button>
                            )}
                            {notifItems.map(n => (
                                <button key={n.id} onClick={() => { setNotifOpen(false); if (n.link) navigate(n.link); }}
                                    className="w-full px-4 py-3 text-left hover:bg-muted border-b border-border last:border-0">
                                    <div className="flex items-start gap-2">
                                        {!n.read && <span className="w-2 h-2 rounded-full bg-brand mt-1.5 flex-shrink-0" />}
                                        <div className="flex-1 min-w-0">
                                            <p className={`text-sm ${n.read ? 'text-muted-foreground' : 'text-foreground font-medium'}`}>{n.title}</p>
                                            {/* Entrecomillado solo si lo ha escrito una persona. Los avisos que
                                                genera la app traen `clave`; ponerles comillas hace que parezca
                                                que se lo ha dicho alguien. */}
                                            {n.body && (
                                                <p className="text-xs text-foreground/80 mt-1 whitespace-pre-wrap">
                                                    {n.clave ? n.body : `"${n.body}"`}
                                                </p>
                                            )}
                                            <p className="text-[11px] text-muted-foreground mt-0.5">{notifTime(n.created_at)}</p>
                                            {/* «No puedo esta semana» TAMBIÉN EN EL AVISO (doc 19-08):
                                                el que lee el recordatorio y sabe que no va a llegar no
                                                tiene que ir a buscar el botón al reporte. Lleva al
                                                formulario con el aplazamiento ya abierto. */}
                                            {/^(mensual|quincenal)_(abierto|ultimo):|^reporte_no_llego:/.test(n.clave || '') && (
                                                <span role="button" data-testid="aviso-no-puedo"
                                                    onClick={(e) => { e.stopPropagation(); setNotifOpen(false); navigate('/dashboard/reports?aplazar=1'); }}
                                                    className="inline-block mt-1.5 px-2.5 py-1 rounded-lg border border-border text-[12px] text-foreground/70 hover:border-foreground/30">
                                                    No puedo esta semana
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </button>
                            ))}
                            {/* LA LISTA SE CIERRA DICIENDO QUE NO QUEDA NADA.
                                Una lista de avisos que solo termina cuando se acaban deja la
                                duda de si falta algo por cargar. Al abrir el panel ya se marcan
                                todos como leídos, así que el estado real es ese: no hay nada
                                más pendiente, y se dice (Jesús, 11-08). */}
                            {/* MIENTRAS SE BUSCAN, SE DICE. El panel se abre al instante y la
                                lista tarda lo que tarde el servidor (medido en desarrollo:
                                cinco segundos largos). Sin esta línea eran cinco segundos de
                                caja blanca vacía, que se lee como «no tengo nada» o como que
                                la app se ha colgado. Decir «no hay nada» todavía no se puede:
                                no se sabe. */}
                            {notifCargando ? (
                                <p className="text-muted-foreground text-sm text-center py-10">Buscando avisos...</p>
                            ) : notifItems.length === 0 && unread === 0 ? (
                                <p className="text-muted-foreground text-sm text-center py-10">No hay nada pendiente</p>
                            ) : (
                                <p className="text-muted-foreground/70 text-xs text-center py-4">No hay nada más pendiente</p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ===== Mobile drawer ===== */}
            {drawerOpen && (
                <div className="lg:hidden fixed inset-0 z-[60]" data-testid="mobile-drawer">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setDrawerOpen(false)} />
                    <div className="absolute inset-y-0 left-0 w-[82%] max-w-xs bg-ink flex flex-col animate-slide-up">
                        <div className="flex items-center justify-between h-14 px-4 border-b border-white/10">
                            <Logo12EN12 size="sm" tone="dark" />
                            <button onClick={() => setDrawerOpen(false)} data-testid="drawer-close"
                                className="w-9 h-9 rounded-lg flex items-center justify-center text-white/60 hover:bg-white/10">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
                            {navItems.map(item => <SidebarLink key={item.path} item={item} collapsed={false} unread={unread} onClick={() => setDrawerOpen(false)} />)}
                        </nav>
                        <div className="p-3 border-t border-white/10 space-y-2">
                            <UserChip />
                            {isStaff && (
                                <button onClick={() => navigate('/admin')}
                                    className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg text-white/50 hover:text-brand hover:bg-brand/10 transition-colors">
                                    <LayoutDashboard className="w-4 h-4" /> <span className="text-sm">Volver al panel</span>
                                </button>
                            )}
                            <button onClick={handleLogout}
                                className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                                <LogOut className="w-4 h-4" /> <span className="text-sm">Cerrar sesión</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export { ClientDashboard, ClientLayout, PlanBadge, JG12Logo, MACRO };
