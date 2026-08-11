/**
 * RenovacionPage - La semana 12.
 *
 * Especificación 31-07-2026, parte 3: "su foto del día 1 al lado de la de hoy, su
 * evolución y su resumen del ciclo. Tres salidas: renovar, subir de nivel, o salir a
 * la membresía".
 *
 * El orden importa y no es de estilo: PRIMERO lo que ha conseguido, y solo después lo
 * que puede hacer. Al revés sería un cobro con fotos de adorno; así es un balance del
 * que sale una decisión.
 *
 * Y se le dice claramente que si no hace nada se renueva solo. Esta pantalla no es un
 * muro: es donde decide si quiere cambiar algo antes de que le cobren.
 */
import React, { useEffect, useState } from 'react';
import { euros } from '../lib/precios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Loader2, TrendingDown, TrendingUp, Check, ArrowRight, Info } from 'lucide-react';

const fmtPct = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${x}%`);

const RenovacionPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [datos, setDatos] = useState(null);
    const [yendo, setYendo] = useState(null);

    useEffect(() => {
        api.get('/billing/renovacion')
            .then(r => setDatos(r.data))
            .catch(() => toast.error('No hemos podido cargar tu ciclo'));
    }, [api]);

    const elegir = async (salida) => {
        // Seguir en el mismo plan no necesita checkout: su suscripción ya renueva sola.
        if (salida.tipo === 'renovar') {
            toast.success('Perfecto, seguimos. No tienes que hacer nada más.');
            navigate('/dashboard');
            return;
        }
        setYendo(salida.plan);
        try {
            const r = await api.post('/billing/checkout-session', {
                plan: salida.plan,
                success_path: '/dashboard?renovado=ok',
                cancel_path: '/renovacion',
            });
            if (r.data?.checkout_url) window.location.href = r.data.checkout_url;
            else toast.error('No hemos podido abrir el pago');
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'No hemos podido abrir el pago');
            setYendo(null);
        }
    };

    if (!datos) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-brand" />
            </div>
        );
    }

    const { ciclo, resumen, salidas, renueva_solo, motivo_cambio } = datos;
    const { peso, grasa, fotos, constancia, ajustes_de_macros } = resumen;
    const bajado = (peso.cambio_pct ?? 0) < 0;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto pb-24" data-testid="renovacion-page">
            <header className="mb-8">
                {/* SIN FECHA DE FIN NO SE INVENTAN DÍAS.
                    A los clientes anteriores al calendario de arranque no se les guardó el fin
                    de ciclo, y el servidor lo dice con `conocido: false` y manda
                    `dias_restantes: null`. Aquí no se miraba, así que el titular salía literal:
                    «TE QUEDAN NULL DÍAS». Lo vio Francisco el 10-08.
                    Lo que sí se sabe siempre es la semana, y con eso se sitúa igual. */}
                <p className="caption text-brand mb-1">
                    {ciclo.ya_vencido ? 'Tu ciclo ha terminado'
                        : ciclo.dias_restantes == null
                            ? `Vas por la semana ${ciclo.semana}`
                            : `Te queda${ciclo.dias_restantes === 1 ? '' : 'n'} ${ciclo.dias_restantes} día${ciclo.dias_restantes === 1 ? '' : 's'}`}
                </p>
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none">
                    Mira lo que has cambiado
                </h1>
            </header>

            {/* 1 · LO QUE HA CONSEGUIDO */}
            {fotos.comparables ? (
                <section className="surface p-5 mb-4">
                    <p className="caption mb-3">Tú, el primer día y hoy</p>
                    <div className="grid grid-cols-2 gap-3">
                        {[['Día 1', fotos.antes], ['Hoy', fotos.ahora]].map(([etiqueta, lista]) => (
                            <div key={etiqueta}>
                                <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-2">{etiqueta}</p>
                                <div className="grid grid-cols-3 gap-1.5">
                                    {lista.map((src, i) => (
                                        <div key={i} className="aspect-[3/4] rounded-lg overflow-hidden bg-muted">
                                            <img src={src} alt="" className="w-full h-full object-cover" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            ) : (
                <section className="surface p-5 mb-4 flex items-start gap-3">
                    <Info className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-muted-foreground">
                        No tenemos fotos de las dos puntas del ciclo, así que no podemos ponerlas
                        una al lado de otra. Es lo que más enseña el cambio: si te haces unas hoy,
                        las tendrás para el ciclo que viene.
                    </p>
                </section>
            )}

            <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <div className="surface p-4">
                    <p className="caption mb-1">Peso</p>
                    <div className="flex items-baseline gap-1.5">
                        {peso.cambio_pct != null && (bajado
                            ? <TrendingDown className="w-4 h-4 text-emerald-500" />
                            : <TrendingUp className="w-4 h-4 text-brand" />)}
                        <span className="font-data text-2xl font-bold text-foreground">{fmtPct(peso.cambio_pct)}</span>
                    </div>
                    {peso.cambio_kg != null && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                            {peso.antes} → {peso.ahora} kg
                        </p>
                    )}
                </div>
                <div className="surface p-4">
                    <p className="caption mb-1">Grasa</p>
                    <span className="font-data text-2xl font-bold text-foreground">
                        {grasa.ahora != null ? `${grasa.ahora}%` : '—'}
                    </span>
                    {grasa.antes != null && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">venías del {grasa.antes}%</p>
                    )}
                </div>
                <div className="surface p-4">
                    <p className="caption mb-1">Constancia</p>
                    <span className="font-data text-2xl font-bold text-foreground">{constancia.pct}%</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                        {constancia.dias_registrados} de {constancia.dias_totales} días
                    </p>
                </div>
                <div className="surface p-4">
                    <p className="caption mb-1">Ajustes</p>
                    <span className="font-data text-2xl font-bold text-foreground">{ajustes_de_macros}</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5">de tus macros</p>
                </div>
            </section>

            {/* 2 · LO QUE PUEDE HACER */}
            <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-1">Y ahora, ¿qué?</h2>
            {motivo_cambio && (
                <p className="text-sm text-muted-foreground mb-4">{motivo_cambio}.</p>
            )}
            {!motivo_cambio && renueva_solo && (
                <p className="text-sm text-muted-foreground mb-4">
                    Si no haces nada, tu plan se renueva solo y sigues sin interrupciones.
                </p>
            )}

            <div className="space-y-3">
                {salidas.map(s => (
                    <button key={s.plan + s.tipo} onClick={() => elegir(s)} disabled={!!yendo}
                        data-testid={`salida-${s.tipo}-${s.plan}`}
                        className={`w-full surface surface-hover p-4 flex items-center justify-between gap-4 text-left disabled:opacity-60 ${
                            s.tipo === 'renovar' ? 'border-brand' : ''}`}>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <p className="font-bold text-foreground">{s.titulo}</p>
                                {s.precio_congelado && (
                                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 text-[10px] font-bold uppercase tracking-wider">
                                        Tu precio de siempre
                                    </span>
                                )}
                            </div>
                            <p className="text-sm text-muted-foreground mt-0.5">{s.detalle}</p>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                            <span className="font-heading text-lg font-bold text-foreground">{euros(s.precio)}</span>
                            {yendo === s.plan
                                ? <Loader2 className="w-4 h-4 animate-spin text-brand" />
                                : s.tipo === 'renovar'
                                    ? <Check className="w-5 h-5 text-brand" />
                                    : <ArrowRight className="w-5 h-5 text-muted-foreground" />}
                        </div>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default RenovacionPage;
