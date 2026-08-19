/**
 * TU COMPARATIVA (T6 del doc 16-08). La comparativa de fotos del panel, traída al lado del
 * cliente con los dos cambios que pide el doc:
 *
 *   - DOS FOTOS POR DEFECTO, no cuatro: "de dónde vengo" y "cómo estoy hoy", con un botón
 *     para añadir la del medio y otro para verlas todas. El coach compara fases; el cliente
 *     quiere ver de dónde viene y cómo está hoy, y con cuatro fotos de 1/4 de ancho en un
 *     teléfono no se ve ninguna.
 *   - FUERA EL % GRASO: lo estima Jesús mirando las fotos, y el cliente no lo toca.
 *
 * Las etiquetas son las de siempre (`lib/comparativaFotos.js`), las mismas que ve el coach:
 * si un día cambia el nombre de una foto, cambia en los dos sitios.
 *
 * Las fotos van con la sesión, así que se piden con el token y se pintan desde el blob (el
 * mismo camino que `TresFotos`): el token no viaja nunca en una URL de imagen.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Camera } from 'lucide-react';
import { construirComparativa, TITULO_ETIQUETA } from '../lib/comparativaFotos';
import { MEDIDAS, valorAnterior } from '../lib/medidas';

const POSE_ORDEN = ['frente', 'perfil', 'espalda'];

const _fecha = (f) => {
    if (!f) return '';
    const d = new Date(`${f}T12:00:00`);
    return isNaN(d) ? f : d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
};

const _kilos = (v) => `${String(v).replace('.', ',')} kg`;

// El peso más cercano a una fecha (dentro de tres semanas). Es el mismo criterio que en la
// ficha del panel: la foto se anota con el peso de ese momento, no con el de hoy.
const _pesoCercano = (pesos, fecha) => {
    if (!fecha || !pesos?.length) return null;
    const objetivo = new Date(`${fecha}T12:00:00`).getTime();
    let mejor = null, distancia = Infinity;
    for (const p of pesos) {
        const d = Math.abs(new Date(`${String(p.date).slice(0, 10)}T12:00:00`).getTime() - objetivo);
        if (d < distancia) { distancia = d; mejor = p.w; }
    }
    return distancia <= 21 * 864e5 ? mejor : null;
};

/** Una foto del cliente, descargada con su sesión. */
const FotoDelCliente = ({ api, foto }) => {
    const [url, setUrl] = useState(null);
    useEffect(() => {
        let vivo = true;
        api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' })
            .then(r => { if (vivo) setUrl(URL.createObjectURL(r.data)); })
            .catch((e) => { console.error('No se pudo cargar una foto de la comparativa:', e); });
        return () => { vivo = false; };
    }, [api, foto.id]);

    return (
        <div className="aspect-[3/4] rounded-xl overflow-hidden bg-muted">
            {url && <img src={url} alt="" className="w-full h-full object-cover" />}
        </div>
    );
};

/** «Cintura 84 · y 9 medidas más», debajo de la foto de hoy. */
const MedidasDeLaFoto = ({ medidas }) => {
    const conValor = MEDIDAS
        .map(({ key, label }) => ({ key, label, valor: valorAnterior(medidas, key) }))
        .filter(m => m.valor != null);
    if (!conValor.length) return null;
    const primera = conValor.find(m => m.key === 'cintura') || conValor[0];
    const resto = conValor.length - 1;
    const alPasar = conValor.filter(m => m.key !== primera.key).map(m => `${m.label}: ${m.valor} cm`).join('\n');
    return (
        <p className="text-[11px] text-muted-foreground leading-tight" title={alPasar || undefined}>
            {primera.label} <b className="text-foreground">{primera.valor}</b>
            {resto > 0 && ` · y ${resto} ${resto === 1 ? 'medida más' : 'medidas más'}`}
        </p>
    );
};

const ComparativaCliente = ({ api, reports, faseDesde }) => {
    const [fotos, setFotos] = useState([]);
    const [conLaDelMedio, setConLaDelMedio] = useState(false);
    const [verTodas, setVerTodas] = useState(false);

    const cargar = useCallback(() => {
        api.get('/reports/photos')
            .then(r => setFotos(r.data?.photos || []))
            .catch((e) => { console.error('No se pudieron cargar las fotos:', e); });
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    // El peso de cada momento sale de sus propios reportes: es la serie que él ya conoce.
    const pesos = useMemo(() => (reports || [])
        .filter(r => r?.weight != null && r?.created_at)
        .map(r => ({ date: r.created_at, w: r.weight })), [reports]);

    const medidasPorFecha = useMemo(() => {
        const m = {};
        (reports || []).forEach(r => {
            const f = String(r.created_at || '').slice(0, 10);
            if (f && r.measurements && Object.keys(r.measurements).length) m[f] = r.measurements;
        });
        return m;
    }, [reports]);

    // Un día con fotos es una sesión: es lo que se compara, no cada foto suelta.
    const sesiones = useMemo(() => {
        const porDia = new Map();
        for (const f of fotos) {
            const dia = String(f.taken_at || f.uploaded_at || '').slice(0, 10);
            if (!dia) continue;
            if (!porDia.has(dia)) porDia.set(dia, []);
            porDia.get(dia).push(f);
        }
        return [...porDia.entries()].map(([fecha, suyas]) => ({
            fecha,
            peso: _pesoCercano(pesos, fecha),
            medidas: medidasPorFecha[fecha] || null,
            fotos: [...suyas].sort((a, b) => POSE_ORDEN.indexOf(a.pose) - POSE_ORDEN.indexOf(b.pose)),
        }));
    }, [fotos, pesos, medidasPorFecha]);

    const comparativa = useMemo(() => construirComparativa(sesiones, faseDesde), [sesiones, faseDesde]);

    // LAS DOS DEL DOC: la primera y la última, con sus nombres fijos. Cuando solo hay una
    // sesión sale una sola foto con las dos etiquetas, que es la regla de siempre (nunca la
    // misma foto dos veces).
    const aLaVista = useMemo(() => {
        if (conLaDelMedio || comparativa.length <= 1) return comparativa;
        const primera = { ...comparativa[0], etiquetas: ['inicial'] };
        const ultima = { ...comparativa[comparativa.length - 1], etiquetas: ['actual'] };
        return [primera, ultima];
    }, [comparativa, conLaDelMedio]);

    const hayDelMedio = comparativa.length > 2;

    if (!fotos.length) {
        return (
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3" data-testid="comparativa-sin-fotos">
                <Camera className="w-5 h-5 text-foreground/25 shrink-0 mt-0.5" />
                <div>
                    <p className="text-sm font-bold text-foreground">Tu comparativa</p>
                    {/* Ya no es un callejón: los botones de arriba dejan subirlas cuando
                        quiera (doc 19-08, «Lo que falta en Seguimiento»). */}
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Todavía no has subido fotos. Puedes subirlas cuando quieras con el botón
                        de arriba; te las recomendamos cada 4 semanas.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-card border border-border rounded-2xl p-4 space-y-3" data-testid="comparativa-cliente">
            <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-brand" />
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider">Tu comparativa</p>
            </div>

            {verTodas ? (
                <div className="grid grid-cols-3 gap-2">
                    {[...sesiones].sort((a, b) => b.fecha.localeCompare(a.fecha)).map(s => s.fotos.map(f => (
                        <div key={f.id}>
                            <FotoDelCliente api={api} foto={f} />
                            <p className="text-[10px] text-muted-foreground text-center mt-0.5">{_fecha(s.fecha)}</p>
                        </div>
                    )))}
                </div>
            ) : (
                /* COLUMNAS FIJAS, aunque haya menos fotos. Con el reparto automático, el
                   cliente que solo tiene una sesión -- o sea, todo el que empieza -- se
                   encontraba la foto a pantalla completa y había que hacer scroll para
                   pasar de ella. Dos columnas (las dos del doc) y tres cuando pide la del
                   medio: cada foto ocupa siempre lo mismo y la primera se queda a la
                   izquierda, que es la regla de Jesús. */
                <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${conLaDelMedio ? Math.max(aLaVista.length, 3) : 2}, minmax(0, 1fr))` }}>
                    {aLaVista.map((c, i) => {
                        const esLaDeHoy = i === aLaVista.length - 1;
                        return (
                            <div key={c.fecha} className="space-y-1">
                                {c.fotos[0] && <FotoDelCliente api={api} foto={c.fotos[0]} />}
                                <p className="text-[10px] font-bold uppercase tracking-wider text-brand leading-tight">
                                    {c.etiquetas.map(e => TITULO_ETIQUETA[e] || e).join(' · ')}
                                </p>
                                <p className="text-[11px] text-muted-foreground leading-tight">
                                    {_fecha(c.fecha)}
                                    {c.peso != null && <span className="block font-bold text-foreground">{_kilos(c.peso)}</span>}
                                </p>
                                {/* Las medidas van con la de hoy: es la que se mira para saber
                                    dónde está, y debajo de la primera no dicen nada que la tabla
                                    de aquí abajo no cuente mejor. */}
                                {esLaDeHoy && c.medidas && <MedidasDeLaFoto medidas={c.medidas} />}
                            </div>
                        );
                    })}
                </div>
            )}

            <div className="flex gap-2">
                {hayDelMedio && !verTodas && (
                    <button type="button" onClick={() => setConLaDelMedio(!conLaDelMedio)} data-testid="la-del-medio"
                        className="flex-1 py-2 text-xs font-bold text-muted-foreground hover:text-brand border border-border rounded-xl transition-colors">
                        {conLaDelMedio ? 'Solo el antes y el ahora' : '+ La del medio'}
                    </button>
                )}
                <button type="button" onClick={() => setVerTodas(!verTodas)} data-testid="mostrar-todas-fotos"
                    className="flex-1 py-2 text-xs font-bold text-muted-foreground hover:text-brand border border-border rounded-xl transition-colors">
                    {verTodas ? 'Volver a la comparativa' : 'Mostrar todas'}
                </button>
            </div>
        </div>
    );
};

export default ComparativaCliente;
