/**
 * EL HISTÓRICO DE AJUSTES, COMPARTIDO (doc 19-08, bloque 09).
 *
 * La misma tabla vive en dos sitios según el plan: en «Mis macros» para el que se los
 * calcula él, y en Seguimiento → Evolución para el que se los lleva un entrenador («al
 * lado de su peso, sus medidas y sus fotos. Que es donde se ve que estás trabajando»).
 * Un solo componente para que nunca cuenten historias distintas.
 *
 * También sale de aquí la frase del último ajuste de la cabecera del doc:
 * «Último ajuste: −20 g de hidratos en entreno, −10 g de grasa en descanso».
 */
import React, { useState } from 'react';
import { MACRO } from '../pages/ClientDashboard';

const CAMPOS = [
    { key: 'proteina', corto: 'P', nombre: 'proteína', color: MACRO.protein },
    { key: 'hidratos', corto: 'H', nombre: 'hidratos', color: MACRO.carbs },
    { key: 'grasa', corto: 'G', nombre: 'grasa', color: MACRO.fat },
];

const numero = (v) => (v === null || v === undefined ? '-' : v);

export const fechaCorta = (iso) => {
    if (!iso) return '-';
    return new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', {
        day: 'numeric', month: 'short', year: '2-digit',
    });
};

/**
 * «Último ajuste: −20 g de hidratos en entreno, −10 g de grasa en descanso».
 * Se compara el ajuste vigente con el anterior, bloque a bloque; lo que no se movió no se
 * nombra. Sin anterior (el primer ajuste) no hay frase.
 */
export const ultimoAjusteLegible = (entradas) => {
    if (!entradas || entradas.length < 2) return null;
    const [ahora, antes] = entradas;
    const BLOQUES = [['entreno', 'entreno'], ['peri', 'perientreno'], ['descanso', 'descanso']];
    const partes = [];
    for (const [key, nombre] of BLOQUES) {
        for (const c of CAMPOS) {
            const a = ahora?.[key]?.[c.key];
            const b = antes?.[key]?.[c.key];
            if (a == null || b == null) continue;
            const delta = a - b;
            if (!delta) continue;
            partes.push(`${delta > 0 ? '+' : '−'}${Math.abs(delta)} g de ${c.nombre} en ${nombre}`);
        }
    }
    return partes.length ? partes.join(', ') : null;
};

// EN COLOR LO QUE CAMBIÓ respecto al ajuste anterior, igual que lo ve el entrenador. La
// marca viene calculada del servidor (`cambios`), que es la que se guardó al hacer el
// ajuste; sin ella (entradas viejas, las importadas de Calma) no se marca nada.
const Celdas = ({ macros, cambios, conGrasa = true }) => {
    const campos = conGrasa ? CAMPOS : CAMPOS.slice(0, 2);
    return campos.map(c => {
        const cambio = !!cambios?.[c.key];
        return (
            <td key={c.key}
                className={`px-1.5 py-2 text-right font-data ${cambio ? 'text-red-600 dark:text-red-400 font-bold' : 'text-foreground/70'}`}>
                {numero(macros?.[c.key])}
            </td>
        );
    });
};

// Cuántos ajustes se enseñan de entrada; el resto a un clic.
const AJUSTES_A_LA_VISTA = 12;

const HistorialDeMacros = ({ entradas }) => {
    const [todo, setTodo] = useState(false);
    const filas = entradas || [];
    const visibles = todo ? filas : filas.slice(0, AJUSTES_A_LA_VISTA);
    // Con una sola entrada no hay escalera que leer.
    if (filas.length < 2) return null;
    return (
        <section className="space-y-2" data-testid="mis-macros-historico">
            <div className="flex items-baseline justify-between gap-2 flex-wrap">
                <p className="caption">Tu histórico</p>
                <p className="text-[11px] text-muted-foreground">En rojo, lo que cambió en cada ajuste</p>
            </div>
            <div className="surface p-2 overflow-x-auto">
                <table className="w-full text-sm min-w-[520px]">
                    <thead>
                        <tr className="text-muted-foreground text-[10px] uppercase tracking-wider border-b border-border">
                            {/* La fecha se queda fija al desplazar (revisión del 2-09): en
                                móvil la tabla se va de lado y la fecha quedaba cortada en
                                «6», «4», «23», así que no se sabía de qué ajuste era la
                                fila que se estaba mirando. */}
                            <th rowSpan={2} className="px-2 py-1.5 text-left font-semibold sticky left-0 z-10 bg-card">Fecha</th>
                            <th rowSpan={2} className="px-2 py-1.5 text-right font-semibold">Peso</th>
                            <th colSpan={3} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Entreno</th>
                            <th colSpan={2} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Peri</th>
                            <th colSpan={3} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Descanso</th>
                        </tr>
                        <tr className="text-muted-foreground/70 text-[10px] uppercase border-b border-border">
                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th><th className="px-1.5 pb-1.5 text-right font-medium">G</th>
                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th>
                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th><th className="px-1.5 pb-1.5 text-right font-medium">G</th>
                        </tr>
                    </thead>
                    <tbody>
                        {visibles.map((h, i) => (
                            <tr key={h.id || i} className="border-b border-border last:border-0">
                                <td className="px-2 py-2 whitespace-nowrap font-data text-foreground sticky left-0 z-10 bg-card">{fechaCorta(h.fecha)}</td>
                                <td className="px-2 py-2 text-right whitespace-nowrap font-data text-foreground">
                                    {h.peso != null ? `${h.peso} kg` : '-'}
                                </td>
                                <Celdas macros={h.entreno} cambios={h.cambios?.entreno} />
                                <Celdas macros={h.peri} cambios={h.cambios?.perientreno} conGrasa={false} />
                                <Celdas macros={h.descanso} cambios={h.cambios?.descanso} />
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {filas.length > visibles.length && (
                <button type="button" onClick={() => setTodo(true)}
                    className="text-xs font-semibold text-brand hover:underline"
                    data-testid="mis-macros-ver-todo">
                    Ver los {filas.length} ajustes
                </button>
            )}
        </section>
    );
};

export default HistorialDeMacros;
