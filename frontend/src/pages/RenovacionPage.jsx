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
 * Y se le dice claramente qué pasa si no hace nada, que desde el 20-08 es lo contrario de
 * lo que ponía aquí: no se renueva solo nadie (todo se vende como pago único), así que la
 * renovación la confirma él en esta pantalla. Solo al que arrastra una suscripción de las
 * de antes se le sigue cobrando sin tocar nada, y eso lo decide el servidor
 * (`renueva_solo`). Esta pantalla no es un muro: es donde decide.
 */
import React, { useEffect, useState } from 'react';
import { euros } from '../lib/precios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Loader2, TrendingDown, TrendingUp, Check, ArrowRight, ArrowLeft, Info, Phone } from 'lucide-react';
import { mensajeDeError } from '../lib/mensajeDeError';

const fmtPct = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${x}%`);

const RenovacionPage = () => {
    const { api, refreshProfile } = useAuth();
    const navigate = useNavigate();
    const [datos, setDatos] = useState(null);
    const [yendo, setYendo] = useState(null);
    const [confirmando, setConfirmando] = useState(
        () => new URLSearchParams(window.location.search).get('renovado') === 'ok');

    useEffect(() => {
        api.get('/billing/renovacion')
            .then(r => setDatos(r.data))
            .catch(() => toast.error('No hemos podido cargar tu ciclo'));
    }, [api]);

    // LA VUELTA DE STRIPE SE CONFIRMA AQUÍ, no se espera al webhook (24-08).
    //
    // La renovación mandaba a /dashboard?renovado=ok y allí no lee ese parámetro nadie:
    // el cliente pagaba, aterrizaba en su panel y no veía ni un «pago confirmado». Si el
    // webhook tardaba o fallaba, se quedaba mirando «tu suscripción ha terminado» con el
    // dinero ya cobrado y sin ninguna forma de forzar la sincronización. Las otras tres
    // vueltas de Stripe (alta, planes y bienvenida) ya lo hacían bien; esta vuelve a la
    // propia pantalla de renovación, sincroniza y de ahí le lleva a su panel.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        if (params.get('renovado') !== 'ok') return;
        const sessionId = params.get('session_id');
        // CADA SALIDA VUELVE CON LA SUYA. Las tres usan el mismo `success_path`, así que
        // al que acaba de bajarse a Mantenimiento (60 €/mes) se le decía «tu ciclo nuevo
        // ya está en marcha»: justo lo contrario de lo que había hecho. El tipo de salida
        // viaja en la vuelta porque el servidor ya lo sabe y aquí, tras el redirect de
        // Stripe, no queda nada del estado de la pantalla.
        const confirmado = {
            salida: '¡Pago confirmado! Ya estás en Mantenimiento.',
            cambiar: '¡Pago confirmado! Ya estás en tu plan nuevo.',
        }[params.get('salida')] || '¡Pago confirmado! Tu ciclo nuevo ya está en marcha.';
        (async () => {
            try {
                if (sessionId) {
                    await api.post('/billing/checkout-session/sync', { session_id: sessionId });
                }
                await refreshProfile();
                toast.success(confirmado);
                navigate('/dashboard', { replace: true });
            } catch {
                // Que vea su pantalla y no un spinner eterno: recargar reintenta.
                setConfirmando(false);
                toast.error('No hemos podido confirmar el pago. Si te han cobrado, recarga en unos segundos.');
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al volver de Stripe
    }, []);

    const elegir = async (salida) => {
        // Seguir en el mismo plan solo se salta la pasarela cuando de verdad renueva solo,
        // que hoy es únicamente el que arrastra una suscripción viva de las de antes:
        // desde el 20-08 todo lo que se vende es de pago único. Quien decide es
        // `por_checkout`, que lo calcula el servidor (core/renovacion.py).
        //
        // Hasta el 24-08 esto se cumplía solo para el plan antiguo reabierto, así que a un
        // cliente de nivel1, nivel2, ELM o Mantenimiento se le decía «no tienes que hacer
        // nada más» y no se le cobraba: llegaba el fin de ciclo y se quedaba caducado
        // creyendo que había renovado.
        if (salida.tipo === 'renovar' && !salida.por_checkout) {
            toast.success('Perfecto, seguimos. No tienes que hacer nada más.');
            navigate('/dashboard');
            return;
        }
        // El plan que se cierra hablando no abre pasarela: lleva al chat, que es donde se
        // pide la llamada. Sin esto, pulsarlo mandaba a pagar 1.500 € por su cuenta algo que
        // el catálogo dice que se contrata por teléfono.
        if (salida.por_llamada) {
            toast.success('Te llamamos para verlo contigo. Dinos por aquí cuándo te viene bien.');
            navigate('/dashboard/messages');
            return;
        }
        setYendo(salida.plan);
        try {
            const r = await api.post('/billing/checkout-session', {
                plan: salida.plan,
                // Vuelve AQUÍ para confirmar el cobro antes de mandarle al panel, y con
                // qué eligió: renovar, cambiar de plan y bajarse a Mantenimiento no se
                // confirman con la misma frase.
                success_path: `/renovacion?renovado=ok&salida=${salida.tipo}`,
                cancel_path: '/renovacion',
            });
            if (r.data?.checkout_url) window.location.href = r.data.checkout_url;
            else toast.error('No hemos podido abrir el pago');
        } catch (e) {
            toast.error(mensajeDeError(e, 'No hemos podido abrir el pago'));
            setYendo(null);
        }
    };

    if (!datos || confirmando) {
        return (
            <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-brand" />
                {/* Volver del pago y ver el balance del ciclo VIEJO, con su botón de
                    renovar, parece que el cobro no ha entrado. */}
                {confirmando && (
                    <p className="text-sm text-muted-foreground">Confirmando tu pago...</p>
                )}
            </div>
        );
    }

    const { ciclo, resumen, salidas, renueva_solo, motivo_cambio } = datos;

    // «RENOVAR MI PLAN» ENSEÑA SU PLAN, NO EL CATALOGO (Francisco, 25-08).
    //
    // Desde el caducado salen dos botones y los dos traian aqui, a la lista entera. Al que
    // pulsa «Renovar mi plan» no hay que ponerle delante Premium, Gold y Calculadora: ya ha
    // dicho lo que quiere. Con `?solo=mio` se le enseña solo el suyo, y debajo la puerta
    // para ver el resto por si cambia de idea. «Ver mis opciones» sigue trayendo a todo.
    //
    // Si su plan NO se puede renovar -- retirado y sin reabrir -- no hay «Seguir igual» que
    // enseñar, asi que se le enseña todo igualmente: mas vale la lista que una pantalla
    // vacia con un titulo que promete.
    const soloElSuyo = new URLSearchParams(window.location.search).get('solo') === 'mio';
    const tieneElSuyo = salidas.some(s => s.tipo === 'renovar');
    const aEnseñar = (soloElSuyo && tieneElSuyo)
        ? salidas.filter(s => s.tipo === 'renovar')
        : salidas;
    const { peso, grasa, fotos, constancia, ajustes_de_macros } = resumen;
    const bajado = (peso.cambio_pct ?? 0) < 0;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto pb-24" data-testid="renovacion-page">
            {/* UNA PUERTA PARA SALIR (Francisco, 25-08). Esta pantalla no tenía ninguna:
                se entra desde «Ver mis opciones» del caducado y desde el aviso de fin de
                ciclo, y una vez dentro la única forma de volver era el botón del navegador.
                Al cliente que solo venía a mirar sus opciones se le dejaba encerrado entre
                botones de pagar, que es el peor sitio para no tener salida. */}
            <button onClick={() => navigate('/dashboard')}
                className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4 -ml-1 transition-colors"
                data-testid="renovacion-volver">
                <ArrowLeft className="w-4 h-4" /> Volver al inicio
            </button>
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
                    {/* El texto es el del doc del 23-08 (P55), literal: «las dos puntas del
                        ciclo» no se entendía. */}
                    <p className="text-sm text-muted-foreground">
                        No tienes fotos del principio y del final, así que no podemos compararlas.
                        Si te haces unas hoy, el próximo ciclo sí las tendrás.
                    </p>
                </section>
            )}

            <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                {/* EN KILOS Y CON SIGNO, NO EN PORCENTAJE.
                    Aquí ponía «PESO 0 %» debajo de «75,5 → 75,9»: había subido 400 gramos y la
                    cifra grande decía cero, porque 0,4 sobre 75 redondea a 0 %. El porcentaje
                    esconde justo lo que se viene a mirar. Jesús, 11-08: «mejor en kilos y con
                    signo: +0,4 kg». */}
                <div className="surface p-4">
                    <p className="caption mb-1">Peso</p>
                    <div className="flex items-baseline gap-1.5">
                        {peso.cambio_kg != null && (bajado
                            ? <TrendingDown className="w-4 h-4 text-emerald-500" />
                            : <TrendingUp className="w-4 h-4 text-brand" />)}
                        <span className="font-data text-2xl font-bold text-foreground">
                            {peso.cambio_kg == null
                                ? '—'
                                : `${peso.cambio_kg > 0 ? '+' : ''}${Math.round(peso.cambio_kg * 10) / 10} kg`}
                        </span>
                    </div>
                    {peso.antes != null && peso.ahora != null && (
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
                {/* LA CONSTANCIA, DICHA COMO LO QUE ES. Un «15 %» a secas, justo cuando le
                    ofreces subir de nivel, juega en tu contra: parece un suspenso y no dice
                    qué hacer con él. El mismo dato contado como lo que es -- lo que más pesa
                    en el resultado, y lo que cambia cuando hay alguien encima -- empuja hacia
                    arriba en vez de hundir (Jesús, 11-08). */}
                <div className="surface p-4">
                    <p className="caption mb-1">Constancia</p>
                    <span className="font-data text-2xl font-bold text-foreground">
                        {constancia.dias_registrados} <span className="text-base font-normal text-muted-foreground">de {constancia.dias_totales}</span>
                    </span>
                    <p className="text-[11px] text-muted-foreground mt-0.5">días con el día cuadrado</p>
                </div>
                <div className="surface p-4">
                    <p className="caption mb-1">Ajustes</p>
                    <span className="font-data text-2xl font-bold text-foreground">{ajustes_de_macros}</span>
                    <p className="text-[11px] text-muted-foreground mt-0.5">de tus macros</p>
                </div>
            </section>

            {/* Lo que la constancia significa, debajo de los cuatro números y no dentro de la
                tarjeta: es la frase que convierte un dato flojo en el argumento de subir de
                nivel. Solo cuando hay margen de mejora; con la constancia alta sobra. */}
            {constancia.dias_totales > 0 && constancia.pct < 70 && (
                <p className="text-sm text-muted-foreground -mt-2 mb-6 max-w-prose">
                    La constancia es lo que más pesa en el resultado, y es justo lo que cambia
                    cuando hay alguien encima.
                </p>
            )}

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
            {/* El plan antiguo reabierto para los suyos: puede quedarse, pero esta vez tiene
                que darle él, porque su plan ya no se cobra solo. Decirlo evita que se quede
                esperando una renovación que no va a llegar.
                Quién es «antiguo» lo dice `renovacion_legacy` y no `por_checkout`: desde el
                24-08 a la pasarela va también el del catálogo, y con eso a un cliente de
                nivel2 se le decía que su plan ya no se vende. */}
            {!motivo_cambio && !renueva_solo && salidas.some(s => s.tipo === 'renovar' && s.renovacion_legacy) && (
                <p className="text-sm text-muted-foreground mb-4" data-testid="aviso-renovacion-legacy">
                    Tu plan ya no se vende, pero puedes seguir en él. Eso sí, esta vez la
                    renovación la tienes que confirmar tú aquí.
                </p>
            )}
            {/* Ningún plan renueva solo desde el 20-08: al que sigue en el catálogo también
                hay que decírselo, o se queda esperando un cobro que no va a llegar.
                Y AL QUE YA HA VENCIDO TAMBIÉN SE LE DICE ALGO. Esto exigía `!ya_vencido`, y
                en cuanto `ya_vencido` empezó a funcionar de verdad (24-08) el caducado del
                catálogo se quedó sin una sola línea: «Tu ciclo ha terminado» y tres botones.
                Lo que cambia con el ciclo vencido no es que haya que callarse, es que la
                promesa de encadenar ya no le sirve: esa semana la ha perdido. */}
            {!motivo_cambio && !renueva_solo && !salidas.some(s => s.tipo === 'renovar' && s.renovacion_legacy) && (
                <p className="text-sm text-muted-foreground mb-4" data-testid="aviso-renovacion-manual">
                    Tu plan no se renueva solo: {ciclo.ya_vencido
                        ? 'para volver a tenerlo, la renovación la confirmas tú aquí abajo.'
                        : 'cuando quieras seguir, la renovación la confirmas tú aquí. Si renuevas antes de que acabe, el ciclo nuevo empieza donde termina este y no pierdes ni una semana.'}
                </p>
            )}

            <div className="space-y-3">
                {aEnseñar.map(s => (
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
                        {/* EL QUE SE CIERRA HABLANDO NO LLEVA PRECIO NI FLECHA DE PAGAR.
                            Aquí salía el Nivel 3 con «1.500 €» y su flecha, invitando a pagarlo
                            por dentro cuando el propio catálogo dice que se contrata por
                            llamada. En /planes ya está bien resuelto con «Agendar una llamada»;
                            esta pantalla vendía lo mismo mucho peor (Jesús, 11-08). */}
                        <div className="flex items-center gap-3 flex-shrink-0">
                            {s.por_llamada ? (
                                <span className="font-bold text-brand text-sm whitespace-nowrap">Pedir llamada</span>
                            ) : (
                                <span className="font-heading text-lg font-bold text-foreground">
                                    {euros(s.precio)}
                                    {/* Los planes mensuales lo dicen (P51): 97 € a secas al
                                        lado de un 847 € por ciclo compara peras con manzanas.
                                        El periodo viene del catálogo, por dato. */}
                                    {s.periodo === 'mes' && <span className="text-sm font-normal text-muted-foreground">/mes</span>}
                                </span>
                            )}
                            {yendo === s.plan
                                ? <Loader2 className="w-4 h-4 animate-spin text-brand" />
                                : s.por_llamada
                                    ? <Phone className="w-5 h-5 text-brand" />
                                    : (s.tipo === 'renovar' && !s.por_checkout)
                                        ? <Check className="w-5 h-5 text-brand" />
                                        : <ArrowRight className="w-5 h-5 text-muted-foreground" />}
                        </div>
                    </button>
                ))}
            </div>

            {/* Enseñándole solo el suyo, la puerta al resto tiene que estar: el que llega
                aquí decidido puede cambiar de idea al ver el precio. */}
            {soloElSuyo && tieneElSuyo && salidas.length > 1 && (
                <button onClick={() => navigate('/renovacion')}
                    className="mt-4 text-sm text-brand hover:underline"
                    data-testid="renovacion-ver-todas">
                    Ver todas mis opciones
                </button>
            )}
        </div>
    );
};

export default RenovacionPage;
