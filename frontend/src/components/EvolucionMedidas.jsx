/**
 * LA EVOLUCIÓN DE CADA MEDIDA. La misma tabla para el coach y para el cliente.
 *
 * Vivía suelta dentro de la ficha del panel (punto 35 del doc del 07-08). El doc del 16-08
 * (T6) la lleva también a la pantalla de Evolución del cliente: "la pantalla de Evolución
 * ya está hecha: es la pestaña Seguimiento de la ficha del cliente". Se extrae aquí en vez
 * de copiarla, porque son la misma tabla y tienen que decir lo mismo: si un día cambia la
 * forma de leer la diferencia, cambia en los dos sitios a la vez.
 *
 * Tabla y no gráfico a propósito: son diez series a la vez, y en un gráfico de diez líneas
 * no se lee ninguna. Aquí cada fila es una medida y cada columna una fecha.
 *
 * Lo único que cambia entre los dos sitios es el `tono`: el panel es oscuro a pelo y la app
 * del cliente va con los colores del tema (que tiene modo claro). Y el pie de la tabla, que
 * en el lado del cliente dice "tu entrenador" porque es a él a quien se lo dice.
 */
import React from 'react';
import { MEDIDAS, valorAnterior, diferencia } from '../lib/medidas';

// Las columnas caben hasta cierto punto: se enseñan las últimas y se dice cuántas quedan
// fuera, que es mejor que cortar en silencio.
const SESIONES_A_LA_VISTA = 8;

const _fechaCorta = (f) => (f ? f.split('-').reverse().join('/') : '-');

const TONOS = {
    admin: {
        caja: 'rounded-xl border bg-[#111] border-[#222] p-5',
        titulo: 'text-xs font-bold text-white/40 uppercase tracking-wider',
        apunte: 'text-[10px] text-white/30',
        vacio: 'text-white/30 text-sm',
        cabecera: 'text-white/40 border-b border-[#222]',
        fila: 'border-b border-[#1a1a1a] last:border-0 hover:bg-white/[0.03]',
        medida: 'px-2 py-1.5 text-white/70 whitespace-nowrap',
        valor: 'text-white font-medium',
        igual: 'text-white/30',
        sube: 'text-blue-400',
        baja: 'text-emerald-400',
        pie: 'text-[10px] text-white/25 mt-2',
        quienLoPone: 'el coach',
    },
    cliente: {
        caja: 'bg-card border border-border rounded-2xl p-4',
        titulo: 'text-xs font-bold text-foreground/40 uppercase tracking-wider',
        apunte: 'text-[10px] text-muted-foreground',
        vacio: 'text-muted-foreground text-sm',
        cabecera: 'text-muted-foreground border-b border-border',
        fila: 'border-b border-border/50 last:border-0',
        medida: 'px-2 py-1.5 text-foreground/70 whitespace-nowrap',
        valor: 'text-foreground font-medium',
        igual: 'text-muted-foreground',
        sube: 'text-blue-500',
        baja: 'text-emerald-500',
        pie: 'text-[10px] text-muted-foreground mt-2',
        quienLoPone: 'tu entrenador',
    },
};

const EvolucionMedidas = ({ reports, tono = 'cliente', titulo }) => {
    const t = TONOS[tono] || TONOS.cliente;
    const cabecera = titulo || (tono === 'admin' ? 'Evolución de las medidas' : 'Tus medidas');

    const sesiones = React.useMemo(() => {
        const conMedidas = (reports || [])
            .filter(r => r?.created_at && r?.measurements && Object.keys(r.measurements).length)
            .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
        return { todas: conMedidas.length, vistas: conMedidas.slice(-SESIONES_A_LA_VISTA) };
    }, [reports]);

    if (sesiones.vistas.length === 0) {
        return (
            <div className={t.caja} data-testid="evolucion-medidas-vacio">
                <p className={`${t.titulo} mb-2`}>{cabecera}</p>
                <p className={t.vacio}>
                    {tono === 'admin'
                        ? 'Todavía no ha mandado ningún reporte con medidas.'
                        : 'Todavía no has mandado ningún reporte con medidas.'}
                </p>
            </div>
        );
    }

    const fuera = sesiones.todas - sesiones.vistas.length;
    return (
        <div className={t.caja} data-testid="evolucion-medidas">
            <div className="flex items-baseline justify-between gap-2 flex-wrap mb-3">
                <p className={t.titulo}>{cabecera}</p>
                <p className={t.apunte}>
                    {fuera > 0 ? `Las ${sesiones.vistas.length} últimas de ${sesiones.todas}` : `${sesiones.todas} ${sesiones.todas === 1 ? 'toma' : 'tomas'}`}
                    {' · '}la diferencia es con la toma anterior
                </p>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-xs min-w-[520px]">
                    <thead>
                        <tr className={t.cabecera}>
                            <th className="text-left font-normal px-2 py-1.5">Medida</th>
                            {sesiones.vistas.map(r => (
                                <th key={r.created_at} className="text-right font-normal px-2 py-1.5 whitespace-nowrap tabular-nums">
                                    {_fechaCorta(String(r.created_at).slice(0, 10)).slice(0, 5)}
                                </th>
                            ))}
                            <th className="text-right font-normal px-2 py-1.5 whitespace-nowrap">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {MEDIDAS.map(({ key, label }) => {
                            const valores = sesiones.vistas.map(r => valorAnterior(r.measurements, key));
                            if (valores.every(v => v == null)) return null;   // esa medida no la ha dado nunca
                            const primero = valores.find(v => v != null);
                            const ultimo = [...valores].reverse().find(v => v != null);
                            const total = diferencia(ultimo, primero);
                            return (
                                <tr key={key} className={t.fila}>
                                    <td className={t.medida}>{label}</td>
                                    {valores.map((v, i) => {
                                        const antes = valores.slice(0, i).reverse().find(x => x != null);
                                        const d = v != null ? diferencia(v, antes ?? null) : null;
                                        return (
                                            <td key={i} className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap">
                                                <span className={t.valor}>{v ?? '-'}</span>
                                                {d && d.signo !== 0 && (
                                                    <span className={`ml-1 text-[10px] ${d.signo > 0 ? t.sube : t.baja}`}>{d.texto}</span>
                                                )}
                                            </td>
                                        );
                                    })}
                                    <td className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap">
                                        {total && total.signo !== 0
                                            ? <span className={`font-bold ${total.signo > 0 ? t.sube : t.baja}`}>{total.texto}</span>
                                            : <span className={t.igual}>igual</span>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            <p className={t.pie}>
                En azul lo que sube y en verde lo que baja. Sin juzgar: subir de brazo y subir de
                cintura no son lo mismo, y eso lo pone {t.quienLoPone}, no el color.
            </p>
        </div>
    );
};

export default EvolucionMedidas;
