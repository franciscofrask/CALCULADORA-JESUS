/**
 * PASO 4 DEL MENSUAL · TU PLAN NUEVO Y MI FEEDBACK DIRECTO
 *
 * Documento «El reporte mensual» (1-09-2026). Hasta ahora, al enviar el mensual, el
 * cliente veía una tarjeta con «Reporte enviado» y una línea. El documento convierte eso
 * en un paso del reporte, y con motivo: es donde se le entrega algo.
 *
 * Dos bloques, y la diferencia entre los dos es el tiempo:
 *
 *   YA LO TIENES              su informe, ahora mismo, con el botón para abrirlo.
 *   ANTES DEL PRÓXIMO ...     el programa nuevo, que lo escribe una persona.
 *
 * EL DÍA LO DICE EL SERVIDOR (`promesa_dia`), no está escrito aquí. La promesa se decide
 * en un solo sitio (`core/promesa_del_reporte.py`) y de ahí sale también el aviso que le
 * salta al equipo si ese día llega sin contestar. Escribir el día a mano en esta pantalla
 * era la forma segura de que un día dijeran cosas distintas.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { CabeceraDelMensual, RotuloDelPaso } from './PasosDelMensual';

const ORANGE = '#FF671F';

/** «12 de agosto», para el pie de cada foto. La de hoy se dice «Hoy». */
const cuando = (iso, hoy) => {
    const dia = String(iso || '').slice(0, 10);
    if (!dia) return '';
    if (dia === hoy) return 'Hoy';
    const d = new Date(`${dia}T12:00:00`);
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
};

/**
 * «Y MIENTRAS TANTO, MÍRATE»: tres fotos suyas de frente, mientras espera el programa.
 *
 * El rótulo estaba puesto y debajo NO HABÍA NADA: un título que no presenta nada, que es
 * peor que no ponerlo. La maqueta enseña tres de la misma pose en tres momentos, y el
 * sentido es ese: lo que se ve comparando es el cambio, no una foto suelta.
 *
 * LA PRIMERA, UNA DEL MEDIO Y LA ÚLTIMA. Con dos, salen las dos; con una, no sale nada --
 * ni el rótulo --, porque una foto sola no compara con nada. De frente, que es la pose que
 * todo el mundo tiene: es la que se pide primero.
 */
const MientrasTantoMirate = ({ api, token }) => {
    const [fotos, setFotos] = useState(null);
    const [urls, setUrls] = useState({});

    useEffect(() => {
        if (!api) { setFotos([]); return; }
        api.get('/reports/photos')
            .then((r) => setFotos(r.data?.photos || []))
            .catch(() => setFotos([]));
    }, [api]);

    const base = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
    // `urls` NO entra en las dependencias, y por eso el «ya la tengo» se pregunta dentro
    // del `setUrls`: con `urls` fuera, cada foto que llega volvería a disparar el efecto y
    // el efecto volvería a pedirlas todas, que es un bucle que no para.
    const traer = useCallback((id) => {
        if (!id) return;
        setUrls((u) => {
            if (u[id]) return u;
            fetch(`${base}/api/reports/photos/${id}`, { headers: { Authorization: `Bearer ${token}` } })
                .then((r) => (r.ok ? r.blob() : Promise.reject(new Error('no'))))
                .then((b) => setUrls((v) => ({ ...v, [id]: URL.createObjectURL(b) })))
                .catch(() => { });
            return { ...u, [id]: '' };      // apuntada como pedida, para no pedirla dos veces
        });
    }, [base, token]);

    const deFrente = (fotos || [])
        .filter((f) => (f.pose || 'frente') === 'frente' && f.taken_at)
        .sort((a, b) => String(a.taken_at).localeCompare(String(b.taken_at)));

    // La primera, una del medio y la última: tres momentos, no las tres últimas semanas.
    const tres = deFrente.length <= 3
        ? deFrente
        : [deFrente[0], deFrente[Math.floor((deFrente.length - 1) / 2)], deFrente[deFrente.length - 1]];

    // Por los ids y no por el array: `tres` se rehace en cada render y como dependencia no
    // pararía nunca.
    const idsDeLasTres = tres.map((f) => f.id).join(',');
    useEffect(() => {
        idsDeLasTres.split(',').filter(Boolean).forEach((id) => traer(id));
    }, [idsDeLasTres, traer]);

    if (fotos === null || tres.length < 2) return null;
    const hoy = new Date().toISOString().slice(0, 10);

    return (
        <div className="space-y-2" data-testid="paso4-mirate">
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground px-1">
                Y mientras tanto, mírate
            </p>
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${tres.length}, minmax(0, 1fr))` }}>
                {tres.map((f) => (
                    <div key={f.id} className="space-y-1">
                        <div className="aspect-[3/4] rounded-xl bg-muted overflow-hidden">
                            {urls[f.id] && (
                                <img src={urls[f.id]} alt={`De frente, ${cuando(f.taken_at, hoy)}`}
                                    className="w-full h-full object-cover" />
                            )}
                        </div>
                        <p className="text-[11px] text-muted-foreground text-center">
                            {cuando(f.taken_at, hoy)}
                        </p>
                    </div>
                ))}
            </div>
            <p className="text-[13px] text-muted-foreground px-1">
                De frente, relajado. Los tres primeros días de cada mes.
            </p>
        </div>
    );
};

const MensualPaso4 = ({ plazo, promesaDia, informeId, onVerInforme, api, token }) => {
    const dia = promesaDia || 'viernes';

    return (
        <div className="space-y-4" data-testid="mensual-paso4">
            <CabeceraDelMensual paso={4} plazo={plazo} />
            <RotuloDelPaso paso={4} />

            {/* ── YA LO TIENES ──
                SOLO SI DE VERDAD LO TIENE. El documento del 1-09 lo da por entregado al
                momento («Te lo entrego ya»), pero desde T9 (doc 16-08) el informe no le sale
                al cliente hasta que Jesús lo revisa: se le prometió «con mi feedback», y
                enseñarle antes el montado a secas es entregarle media promesa.

                Las dos cosas no pueden ser verdad a la vez, así que aquí manda el dato: la
                tarjeta sale cuando el informe ya se puede abrir, y no sale cuando no. Lo que
                nunca hace es decirle «ya lo tienes» y dejarle sin nada que pulsar. */}
            {informeId && (
                <div className="rounded-2xl bg-card border border-border p-4 space-y-3"
                    data-testid="paso4-informe">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        Ya lo tienes
                    </p>
                    <p className="text-base font-bold text-foreground">Tu informe del mes</p>
                    <p className="text-sm text-foreground/80">
                        Te lo entrego ya. Es un <b>análisis objetivo</b> que sale de toda la
                        información que has dejado guardada en la calculadora.
                    </p>
                    <p className="text-sm text-foreground/80">
                        Recuerda que <b>cuantos más datos registres, mejores informes recibirás</b> y
                        mejores ajustes, por supuesto.
                    </p>
                    <button type="button" onClick={() => onVerInforme(informeId)}
                        data-testid="paso4-ver-informe"
                        className="inline-flex items-center gap-1.5 text-sm font-bold"
                        style={{ color: ORANGE }}>
                        Ver mi informe
                        <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* ── ANTES DEL PRÓXIMO ... ── */}
            <div className="rounded-2xl border p-4 space-y-3"
                style={{ borderColor: `${ORANGE}55`, backgroundColor: `${ORANGE}0D` }}
                data-testid="paso4-programa">
                <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                    Antes del próximo {dia}
                </p>
                <p className="text-base font-bold text-foreground">Nuevo programa y feedback</p>
                <p className="text-sm text-foreground/80">
                    Analizamos tus respuestas, comparamos fotos y métricas y, a partir de ahí,
                    ajustamos tus macros, revisamos tu plan de suplementos y preparamos la rutina
                    para las próximas 4 semanas.
                </p>
                <p className="text-sm text-foreground/80">
                    Recibirás todo antes del {dia}. Te aviso por aquí.
                </p>
            </div>

            {/* ── Y MIENTRAS TANTO, MÍRATE ── */}
            <MientrasTantoMirate api={api} token={token} />
        </div>
    );
};

export default MensualPaso4;
