import React from 'react';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

// Progress Bar Component
export const ProgressBar = ({ value, max, color, height = 6, showCheck = false }) => {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    const isOver = value > max;
    const isOk = Math.abs(value - max) <= 0;
    const actualColor = isOver ? '#EF4444' : color;

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

const STATUS_DOT = {
    empty: 'bg-neutral-300 dark:bg-neutral-600',
    cuadrada: 'bg-emerald-500',
    sobra: 'bg-red-500',
    falta: 'bg-amber-400',
};
export const StatusDot = ({ status, className = '' }) => (
    <span className={`inline-block w-2.5 h-2.5 rounded-full ${STATUS_DOT[status] || STATUS_DOT.empty} ${className}`} />
);

// Day Summary
const DaySummary = ({
    tipoDia, summaryExpanded, setSummaryExpanded,
    dayMacros, dayTarget, servedPeriP, servedPeriH, servedPeriG = 0, totalPeriP, totalPeriH,
    opcionPeri, mealOrder, mealInfo, calculateMealMacros, getMealStatus, getDayStatus,
}) => {
    const mainP = dayMacros.P - servedPeriP;
    const mainH = dayMacros.H - servedPeriH;
    const mainG = dayMacros.G - servedPeriG;
    const tgtP = dayTarget.P_entreno ?? dayTarget.P_total;
    const tgtH = dayTarget.H_entreno ?? dayTarget.H_total;
    const tgtG = dayTarget.G_entreno ?? dayTarget.G_total;
    const dayStatus = getDayStatus();

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
                    const over = val > (tgt || 0) + 4;
                    return (
                        <div key={key} className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-[11px] font-bold w-3 flex-shrink-0" style={{ color }}>{key}</span>
                            <div className="flex-1 min-w-0"><ProgressBar value={val} max={tgt || 0} color={color} height={7} /></div>
                            <span className={`font-data text-[11px] w-[72px] text-right ${over ? 'text-red-500 font-bold' : 'text-muted-foreground'}`}>
                                {val.toFixed(0)}/{(tgt || 0).toFixed(0)}g
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Peri + meal dots */}
            <div className="px-4 sm:px-5 pb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border pt-2.5">
                {tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri' ? (
                    <span className="text-[11px] text-muted-foreground font-data">
                        Peri {servedPeriP.toFixed(0)}/{totalPeriP.toFixed(0)}P · {servedPeriH.toFixed(0)}/{totalPeriH.toFixed(0)}H
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
                            {mealOrder.map(mealKey => {
                                const served = calculateMealMacros(mealKey);
                                const isPeri = mealKey === 'Intra' || mealKey === 'Post';
                                return (
                                    <tr key={mealKey} className="border-t border-border">
                                        <td className="py-1.5 text-foreground">{mealInfo[mealKey].name}</td>
                                        <td className="text-right font-data text-muted-foreground">{served.P.toFixed(0)}</td>
                                        <td className="text-right font-data text-muted-foreground">{served.H.toFixed(0)}</td>
                                        <td className="text-right font-data text-muted-foreground">{isPeri ? '-' : served.G.toFixed(0)}</td>
                                    </tr>
                                );
                            })}
                            <tr className="border-t-2 border-border font-bold text-foreground">
                                <td className="py-1.5">TOTAL</td>
                                <td className="text-right font-data">{dayMacros.P.toFixed(0)}</td>
                                <td className="text-right font-data">{dayMacros.H.toFixed(0)}</td>
                                <td className="text-right font-data">{mainG.toFixed(0)}</td>
                            </tr>
                            <tr className="text-muted-foreground">
                                <td className="py-1">OBJETIVO</td>
                                <td className="text-right font-data">{(tgtP || 0).toFixed(0)}</td>
                                <td className="text-right font-data">{(tgtH || 0).toFixed(0)}</td>
                                <td className="text-right font-data">{(tgtG || 0).toFixed(0)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default DaySummary;
