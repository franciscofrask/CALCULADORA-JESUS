/**
 * RevisionPage - "Solicita tu revisión personalizada" (147 €).
 *
 * Documento de Jesús del 06-08-2026. Dos reglas suyas que mandan sobre el diseño:
 *
 *   - Nunca como popup. "Un popup interrumpe, y esto no puede interrumpir: si aparece
 *     encima de lo que está haciendo, es publicidad aunque el texto sea suave". Por eso
 *     esto es una PANTALLA a la que se llega desde una línea pequeña, y no un modal que
 *     salta solo.
 *   - A los Niveles 2 y 3 no se les enseña nunca, porque ya la tienen incluida. Se
 *     comprueba aquí y también en el backend (billing devuelve 400 si el plan trae coach).
 *
 * Los textos son suyos, cerrados, y están tal cual. Si hay que cambiarlos, se cambian
 * con él: no son de relleno.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { euros } from '../lib/precios';
import { PRECIO_REVISION } from '../lib/revision';
import { mensajeDeError } from '../lib/mensajeDeError';

const RevisionPage = () => {
    const navigate = useNavigate();
    const { api, profile, can } = useAuth();
    const [pagando, setPagando] = useState(false);

    const yaTieneCoach = can && can('macros_personalizados');
    const pendiente = profile?.revision_suelta?.estado === 'pendiente';

    const comprar = async () => {
        setPagando(true);
        try {
            const r = await api.post('/billing/revision-suelta/checkout', {});
            if (r.data?.checkout_url) window.location.href = r.data.checkout_url;
            else throw new Error('Sin enlace de pago');
        } catch (e) {
            toast.error(mensajeDeError(e, 'No hemos podido abrir el pago'));
            setPagando(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-6 animate-fade-in" data-testid="revision-page">
            <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-4 h-4" /> Volver
            </button>

            <h1 className="font-heading font-bold text-3xl md:text-4xl text-foreground leading-tight">
                Solicita tu revisión personalizada
            </h1>

            <div className="space-y-4 text-foreground/80 text-[15px] leading-relaxed">
                <p>
                    Cuando ajustas tus macros, el sistema aplica mi método: con todos tus registros,
                    tu evolución y las respuestas del reporte, y tomando como referencia cómo suele ir
                    un perfil como el tuyo, recibes unos macros nuevos. Son mis tablas y mis criterios,
                    aplicados a tu caso.
                </p>
                <p>
                    La revisión personalizada va más allá de los números: te damos nuestra visión y un
                    ajuste 100 % a tu medida.
                </p>
                <p>
                    Vemos tus fotos, comparamos tus métricas, leemos tu reporte, y nos apoyamos en
                    perfiles como el tuyo como referencia, pero decidimos con tu contexto: lo que has
                    podido cumplir, cómo te ha ido y qué se te puede pedir ahora.
                </p>
                <p className="font-semibold text-foreground">
                    Y tus fotos son lo único que ningún sistema puede leer por ti.
                </p>
                <p>
                    Cada revisión queda guardada. Así vamos aprendiendo cómo responde tu cuerpo y qué
                    te funciona a ti, y con eso construimos tu propio modelo: cada vez los ajustes y
                    las sugerencias encajan más contigo.
                </p>
                <p className="font-heading font-bold text-xl text-foreground pt-2">
                    El ajuste mira tus números. La revisión te mira a ti.
                </p>
                <p>
                    Además recibes un plan de suplementación a tu medida para las próximas semanas.
                </p>
            </div>

            <div className="rounded-2xl border-2 border-border bg-card p-5 space-y-4">
                <div className="flex items-baseline justify-between gap-4 flex-wrap">
                    <span className="font-heading font-extrabold text-3xl text-brand">{euros(PRECIO_REVISION)}</span>
                    <span className="text-sm text-muted-foreground">Te contestamos en 48 horas.</span>
                </div>
                <p className="text-sm text-muted-foreground">
                    Y si en los próximos 30 días pasas a un plan con entrenador, te lo descontamos entero.
                </p>

                {yaTieneCoach ? (
                    <p className="text-sm text-foreground/70 border-t border-border pt-4">
                        Tu plan ya la incluye: tus macros los revisa tu entrenador.
                    </p>
                ) : pendiente ? (
                    <p className="text-sm text-foreground/70 border-t border-border pt-4" data-testid="revision-pendiente">
                        Ya tienes una revisión en marcha. Te avisamos en cuanto la tengamos.
                    </p>
                ) : (
                    <button onClick={comprar} disabled={pagando} data-testid="revision-comprar"
                        className="w-full bg-brand hover:bg-brand/90 text-white font-bold rounded-xl py-3.5 transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
                        {pagando ? <><Loader2 className="w-4 h-4 animate-spin" /> Abriendo el pago...</> : 'Solicitar mi revisión'}
                    </button>
                )}
            </div>
        </div>
    );
};

export default RevisionPage;
