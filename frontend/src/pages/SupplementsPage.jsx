import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Pill, Clock, Beaker, Link2, CalendarClock, StickyNote } from 'lucide-react';

const Wrap = ({ children }) => (
    <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1100px] mx-auto animate-fade-in" data-testid="supplements-page">{children}</div>
);

const formatDate = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
};

const SupplementCard = ({ item }) => (
    <div className="surface p-0 overflow-hidden flex flex-col sm:flex-row" data-testid="supplement-card">
        <div className="sm:w-32 flex items-center justify-center bg-muted/40 p-3 flex-shrink-0">
            <img
                src={item.imagen || '/imgs/tarro.webp'}
                alt={item.titulo}
                className="max-h-24 object-contain"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
        </div>
        <div className="flex-1 p-4">
            <h3 className="font-semibold text-foreground mb-2">{item.titulo}</h3>
            {item.cuando && (
                <p className="text-sm text-muted-foreground flex gap-2 mb-1">
                    <Clock className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                    <span><span className="font-semibold text-foreground">¿Cuándo? </span>{item.cuando}</span>
                </p>
            )}
            {item.cuanto && (
                <p className="text-sm text-muted-foreground flex gap-2 mb-1">
                    <Beaker className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                    <span><span className="font-semibold text-foreground">¿Cuánto? </span>{item.cuanto}</span>
                </p>
            )}
            {item.observaciones && (
                <p className="text-sm text-muted-foreground italic mt-2">{item.observaciones}</p>
            )}
            {item.enlaces?.length > 0 && (
                <div className="flex flex-wrap gap-3 mt-2">
                    {item.enlaces.map((url, i) => (
                        <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-brand hover:underline font-semibold">
                            <Link2 className="w-3 h-3" /> Enlace {item.enlaces.length > 1 ? i + 1 : ''}
                        </a>
                    ))}
                </div>
            )}
        </div>
    </div>
);

const SupplementsPage = () => {
    const { api } = useAuth();
    const [protocol, setProtocol] = useState(null);
    const [loading, setLoading] = useState(true);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { fetchProtocol(); }, []);

    const fetchProtocol = async () => {
        try {
            const res = await api.get('/supplements/current');
            setProtocol(res.data);
        } catch (e) {
            console.error('Error fetching supplements:', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-4">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-24 bg-muted rounded-2xl" />
            <div className="h-24 bg-muted rounded-2xl" />
        </div></Wrap>;
    }

    const tieneActual = protocol?.actual?.length > 0;
    const tieneSiguiente = protocol?.siguiente?.length > 0;

    if (!protocol || (!tieneActual && !tieneSiguiente && !protocol.nota)) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6">Suplementación</h1>
            <div className="surface p-10 text-center">
                <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Pill className="w-8 h-8 text-brand/60" />
                </div>
                <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Sin protocolo asignado</h2>
                <p className="text-muted-foreground text-sm">Tu entrenador está preparando tu protocolo de suplementación.</p>
            </div>
        </Wrap>;
    }

    return (
        <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-2">Suplementación</h1>
            <p className="text-muted-foreground text-sm mb-5 max-w-2xl">
                Aquí ves algunos de los suplementos más habituales que recomiendo, así como su modo de empleo. Esta
                información es <span className="italic">orientativa</span>: pueden ser necesarios otros suplementos o dosis
                según tu situación, objetivos o tolerancias.
            </p>

            {protocol.nota && (
                <div className="surface bg-brand/[0.04] border-brand/20 p-4 mb-5 flex gap-3 max-w-2xl">
                    <StickyNote className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-[11px] font-bold text-brand uppercase tracking-wider mb-1">Nota personal</p>
                        <p className="text-sm text-muted-foreground leading-relaxed">{protocol.nota}</p>
                    </div>
                </div>
            )}

            {tieneActual && (
                <section className="mb-7">
                    <h2 className="caption mb-3">Suplementación actual</h2>
                    <div className="grid md:grid-cols-2 gap-3">
                        {protocol.actual.map((it, i) => <SupplementCard key={i} item={it} />)}
                    </div>
                </section>
            )}

            {tieneSiguiente && (
                <section>
                    <div className="flex items-center gap-2 mb-3">
                        <h2 className="caption">Suplementación siguiente</h2>
                        {protocol.siguiente_fecha && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-red-500/10 text-red-500">
                                <CalendarClock className="w-3 h-3" /> A partir del {formatDate(protocol.siguiente_fecha)}
                            </span>
                        )}
                    </div>
                    <div className="grid md:grid-cols-2 gap-3">
                        {protocol.siguiente.map((it, i) => <SupplementCard key={i} item={it} />)}
                    </div>
                </section>
            )}
        </Wrap>
    );
};

export default SupplementsPage;
