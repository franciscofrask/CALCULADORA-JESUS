import React from 'react';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { seExcede, fmtGramos } from '../../lib/exceso';
import { num1 } from '../../lib/numeros';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

// Progress Bar Component
export const ProgressBar = ({ value, max, color, height = 6, showCheck = false, statusColor }) => {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    const isOver = value > max;
    const isOk = Math.abs(value - max) <= 0;
    // statusColor (opcional): color según estado Cuadrado/Válido/fuera, calculado por
    // el llamador con sus umbrales. Sin él, comportamiento clásico (rojo si se pasa).
    const actualColor = statusColor || (isOver ? '#EF4444' : color);

    return (
        <div className="flex items-center gap-2 w-full">
            <div className="flex-1 bg-muted rounded-full overflow-hidden" style={{ height }}>
                <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: actualColor }}
                />
            </div>
            {showCheck && <Check className={`w-4 h-4 flex-shrink-0 ${isOk && value > 0 ? 'text-emerald-500' : 'invisible'}`} />}
        </div>
    );
};

// DOS COLORES Y NINGÚN AMARILLO (punto 116 del artifact del 25-08: «el amarillo desaparece
// de la app»). Aquí había cuatro tonos -- gris, verde, rojo y ámbar -- para decir lo que
// ahora dicen dos: verde si está resuelto y naranja si te pide algo.
//
// LA COMIDA VACÍA VUELVE AL GRIS (punto 196 del 27-08, que corrige el 116 y el 117). Estaba
// en naranja «porque le falta todo», y eso se escribió antes de cerrar la regla del color del
// punto 76: el naranja es sólo para lo que se PASA. Una comida sin crear no es un error, es
// que aún no la has hecho, y con el naranja puesto un día a medias salía entero en color de
// aviso sin haber nada mal. El punto se queda -- dice de qué comida hablamos -- pero apagado.
// Y lo mismo con la que va corta: ir por debajo no es un error, es que no has terminado, así
// que el naranja se queda SOLO para la que se pasa. Es la misma lista del punto 196.
const STATUS_DOT = {
    empty: 'bg-muted-foreground/40',
    cuadrada: 'bg-ok',
    sobra: 'bg-pasado',
    falta: 'bg-muted-foreground/40',
};
export const StatusDot = ({ status, className = '' }) => (
    <span className={`inline-block w-2.5 h-2.5 rounded-full ${STATUS_DOT[status] || STATUS_DOT.empty} ${className}`} />
);

/**
 * Tabla del día: lo que lleva cada comida, el total y el objetivo. Extraída para que
 * la cabecera nueva (DayHeader) la pueda desplegar sin duplicarla.
 */
// LA MISMA DÉCIMA QUE EL RESTO DE LA APP (Francisco, 3-09-2026). Esta tabla escribía
// `toFixed(0)`, así que la comida que arriba dice «73,2» aquí salía «73» y el TOTAL no era la
// suma de sus filas. Es la única regla de redondeo que queda: la décima, en todas partes.
export const DayDetailTable = ({
    mealOrder, mealInfo, calculateMealMacros, tipoDia, opcionPeri,
    mainP, mainH, mainG, tgtP, tgtH, tgtG, totalPeriP, totalPeriH,
}) => {
    const esPeri = (k) => k === 'Intra' || k === 'Post';
    const comidasPrincipales = mealOrder.filter(k => !esPeri(k));
    const comidasPeri = mealOrder.filter(esPeri);
    const hayPeri = comidasPeri.length > 0 && tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri';

    return (
        <div>
            <table className="w-full text-xs">
                <thead><tr className="text-muted-foreground">
                    <th className="text-left font-medium py-1.5">Comida</th>
                    <th className="text-right font-medium py-1.5 w-14">P</th>
                    <th className="text-right font-medium py-1.5 w-14">H</th>
                    <th className="text-right font-medium py-1.5 w-14">G</th>
                </tr></thead>
                <tbody>
                    {comidasPrincipales.map(mealKey => {
                        const served = calculateMealMacros(mealKey);
                        return (
                            <tr key={mealKey} className="border-t border-border">
                                <td className="py-1.5 text-foreground">{mealInfo[mealKey].name}</td>
                                <td className="text-right font-data text-muted-foreground">{num1(served.P)}</td>
                                <td className="text-right font-data text-muted-foreground">{num1(served.H)}</td>
                                <td className="text-right font-data text-muted-foreground">{num1(served.G)}</td>
                            </tr>
                        );
                    })}
                    {/* TOTAL y OBJETIVO van SIN peri, para que se puedan comparar entre si.
                        Antes el total sumaba el peri en P y H pero no en G, y el objetivo no
                        lo contaba nunca: las dos filas no cuadraban y no habia forma de saber
                        por que. El peri tiene su propio objetivo y va debajo, aparte. */}
                    <tr className="border-t-2 border-border font-bold text-foreground">
                        <td className="py-1.5">TOTAL</td>
                        <td className="text-right font-data">{num1(mainP)}</td>
                        <td className="text-right font-data">{num1(mainH)}</td>
                        <td className="text-right font-data">{num1(mainG)}</td>
                    </tr>
                    <tr className="text-muted-foreground">
                        <td className="py-1">OBJETIVO</td>
                        <td className="text-right font-data">{num1(tgtP)}</td>
                        <td className="text-right font-data">{num1(tgtH)}</td>
                        <td className="text-right font-data">{num1(tgtG)}</td>
                    </tr>
                </tbody>
            </table>

            {hayPeri && (
                <div className="mt-3 pt-2.5 border-t border-dashed border-border">
                    <p className="caption mb-1">Peri-entreno</p>
                    <table className="w-full text-xs">
                        <tbody>
                            {comidasPeri.map(mealKey => {
                                const served = calculateMealMacros(mealKey);
                                return (
                                    <tr key={mealKey}>
                                        <td className="py-1 text-foreground">{mealInfo[mealKey].name}</td>
                                        <td className="text-right font-data text-muted-foreground w-14">{num1(served.P)}</td>
                                        <td className="text-right font-data text-muted-foreground w-14">{num1(served.H)}</td>
                                        <td className="text-right font-data text-muted-foreground w-14">-</td>
                                    </tr>
                                );
                            })}
                            <tr className="border-t border-border text-muted-foreground">
                                <td className="py-1">OBJETIVO PERI</td>
                                <td className="text-right font-data w-14">{num1(totalPeriP)}</td>
                                <td className="text-right font-data w-14">{num1(totalPeriH)}</td>
                                <td className="text-right font-data w-14">-</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

// Day Summary
// SIN USO desde que la cabecera es DayHeader. Se conserva mientras se decide si la nueva
// se queda; si se queda, esto se borra (ProgressBar, StatusDot y DayDetailTable siguen
// usándose desde MealCard y DayHeader).
const DaySummary = ({
    tipoDia, summaryExpanded, setSummaryExpanded,
    dayMacros, dayTarget, servedPeriP, servedPeriH, servedPeriG = 0, totalPeriP, totalPeriH,
    opcionPeri, mealOrder, mealInfo, calculateMealMacros, getMealStatus, getDayStatus,
}) => {
    const mainP = dayMacros.P - servedPeriP;
    const mainH = dayMacros.H - servedPeriH;
    const mainG = dayMacros.G - servedPeriG;
    // Mismo criterio que DayHeader: el objetivo de las comidas es el total del día menos el
    // peri que se cuenta aparte (P_entreno se queda corto cuando el peri se reparte entre las
    // comidas, que es lo que pasa en `sin_peri` y en `solo_intra`).
    const tgtP = (dayTarget.P_total ?? 0) - (totalPeriP || 0);
    const tgtH = (dayTarget.H_total ?? 0) - (totalPeriH || 0);
    const tgtG = dayTarget.G_total ?? 0;
    const dayStatus = getDayStatus();

    // El peri (intra y post) se lleva su propia cuenta: no entra en el total del dia ni en su
    // objetivo, que son los de las comidas normales.
    const esPeri = (k) => k === 'Intra' || k === 'Post';
    const comidasPrincipales = mealOrder.filter(k => !esPeri(k));
    const comidasPeri = mealOrder.filter(esPeri);
    const hayPeri = comidasPeri.length > 0 && tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri';

    const macros = [
        { key: 'P', label: 'Proteína', val: mainP, tgt: tgtP, color: MACRO.P },
        { key: 'H', label: 'Hidratos', val: mainH, tgt: tgtH, color: MACRO.H },
        { key: 'G', label: 'Grasas', val: mainG, tgt: tgtG, color: MACRO.G },
    ];

    return (
        <div className="surface overflow-hidden" data-testid="day-summary">
            {/* Header */}
            <button
                className="w-full flex items-center justify-between gap-3 px-4 sm:px-5 py-3 text-left"
                onClick={() => setSummaryExpanded(!summaryExpanded)}
            >
                <div className="flex items-center gap-2.5 min-w-0">
                    <span className="caption">{tipoDia === 'entrenamiento' ? 'Día de entreno' : 'Día de descanso'}</span>
                    {dayStatus === 'cuadrado' && <span className="px-2 py-0.5 bg-emerald-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Cuadrado</span>}
                    {dayStatus === 'sobra' && <span className="px-2 py-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Te pasas</span>}
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                    <span className="text-[11px] hidden sm:inline">{summaryExpanded ? 'Ocultar detalle' : 'Ver detalle'}</span>
                    {summaryExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
            </button>

            {/* Macro bars - vertical en móvil, 3 columnas en desktop */}
            <div className="px-4 sm:px-5 pb-3 grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-2">
                {macros.map(({ key, label, val, tgt, color }) => {
                    // Solo hidratos y grasa se pintan en rojo por arriba (Jesús, 13-08).
                    const over = seExcede(key, val, tgt || 0);
                    return (
                        <div key={key} className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-[11px] font-bold w-3 flex-shrink-0" style={{ color }}>{key}</span>
                            <div className="flex-1 min-w-0">
                                <ProgressBar value={val} max={tgt || 0} color={color} height={7}
                                    statusColor={over ? '#EF4444' : color} />
                            </div>
                            <span className={`font-data text-[11px] w-[72px] text-right ${over ? 'text-red-500 font-bold' : 'text-muted-foreground'}`}>
                                {num1(val)}/{num1(tgt)} g
                            </span>
                            {over && <span className="font-data text-[11px] text-red-500 font-bold flex-shrink-0">+{fmtGramos(val - (tgt || 0))} g</span>}
                        </div>
                    );
                })}
            </div>

            {/* Peri + meal dots */}
            <div className="px-4 sm:px-5 pb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border pt-2.5">
                {tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri' ? (
                    <span className="text-[11px] text-muted-foreground font-data">
                        {/* «Perientreno», no «Peri» (punto 4.18). */}
                        Perientreno {num1(servedPeriP)}/{num1(totalPeriP)}P · {num1(servedPeriH)}/{num1(totalPeriH)}H
                    </span>
                ) : <span />}
                <div className="flex items-center gap-2.5 flex-wrap">
                    {mealOrder.map((mealKey) => (
                        <span key={mealKey} className="flex items-center gap-1">
                            <StatusDot status={getMealStatus(mealKey)} />
                            <span className="text-[11px] text-muted-foreground">{mealInfo[mealKey].shortName}</span>
                        </span>
                    ))}
                </div>
            </div>

            {/* Expanded table */}
            {summaryExpanded && (
                <div className="px-4 sm:px-5 pb-4 pt-1 border-t border-border">
                    <table className="w-full text-xs">
                        <thead><tr className="text-muted-foreground">
                            <th className="text-left font-medium py-1.5">Comida</th>
                            <th className="text-right font-medium py-1.5 w-14">P</th>
                            <th className="text-right font-medium py-1.5 w-14">H</th>
                            <th className="text-right font-medium py-1.5 w-14">G</th>
                        </tr></thead>
                        <tbody>
                            {comidasPrincipales.map(mealKey => {
                                const served = calculateMealMacros(mealKey);
                                return (
                                    <tr key={mealKey} className="border-t border-border">
                                        <td className="py-1.5 text-foreground">{mealInfo[mealKey].name}</td>
                                        <td className="text-right font-data text-muted-foreground">{num1(served.P)}</td>
                                        <td className="text-right font-data text-muted-foreground">{num1(served.H)}</td>
                                        <td className="text-right font-data text-muted-foreground">{num1(served.G)}</td>
                                    </tr>
                                );
                            })}
                            {/* TOTAL y OBJETIVO van SIN peri, para que se puedan comparar entre si.
                                Antes el total sumaba el peri en P y H pero no en G, y el objetivo no
                                lo contaba nunca: las dos filas no cuadraban y no habia forma de saber
                                por que. El peri tiene su propio objetivo y va debajo, aparte. */}
                            <tr className="border-t-2 border-border font-bold text-foreground">
                                <td className="py-1.5">TOTAL</td>
                                <td className="text-right font-data">{num1(mainP)}</td>
                                <td className="text-right font-data">{num1(mainH)}</td>
                                <td className="text-right font-data">{num1(mainG)}</td>
                            </tr>
                            <tr className="text-muted-foreground">
                                <td className="py-1">OBJETIVO</td>
                                <td className="text-right font-data">{num1(tgtP)}</td>
                                <td className="text-right font-data">{num1(tgtH)}</td>
                                <td className="text-right font-data">{num1(tgtG)}</td>
                            </tr>
                        </tbody>
                    </table>

                    {hayPeri && (
                        <div className="mt-3 pt-2.5 border-t border-dashed border-border">
                            <p className="caption mb-1">Peri-entreno</p>
                            <table className="w-full text-xs">
                                <tbody>
                                    {comidasPeri.map(mealKey => {
                                        const served = calculateMealMacros(mealKey);
                                        return (
                                            <tr key={mealKey}>
                                                <td className="py-1 text-foreground">{mealInfo[mealKey].name}</td>
                                                <td className="text-right font-data text-muted-foreground w-14">{num1(served.P)}</td>
                                                <td className="text-right font-data text-muted-foreground w-14">{num1(served.H)}</td>
                                                <td className="text-right font-data text-muted-foreground w-14">-</td>
                                            </tr>
                                        );
                                    })}
                                    <tr className="border-t border-border text-muted-foreground">
                                        <td className="py-1">OBJETIVO PERI</td>
                                        <td className="text-right font-data w-14">{num1(totalPeriP)}</td>
                                        <td className="text-right font-data w-14">{num1(totalPeriH)}</td>
                                        <td className="text-right font-data w-14">-</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default DaySummary;
