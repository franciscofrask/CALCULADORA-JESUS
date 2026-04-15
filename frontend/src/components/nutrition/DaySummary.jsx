import React from 'react';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';

// Progress Bar Component
export const ProgressBar = ({ value, max, color, height = 6, showCheck = false }) => {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    const isOver = value > max + 4;
    const isOk = Math.abs(value - max) <= 4;
    const actualColor = isOver ? '#EF4444' : color;

    return (
        <div className="flex items-center gap-2 w-full">
            <div className="flex-1 bg-gray-200 rounded-full overflow-hidden" style={{ height }}>
                <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: actualColor }}
                />
            </div>
            {showCheck && isOk && value > 0 && <Check className="w-4 h-4 text-green-500 flex-shrink-0" />}
        </div>
    );
};

// Day Summary (sticky top bar)
const DaySummary = ({
    tipoDia, summaryExpanded, setSummaryExpanded,
    dayMacros, dayTarget, servedPeriP, servedPeriH, totalPeriP, totalPeriH,
    opcionPeri, mealOrder, mealInfo, calculateMealMacros, getMealStatus, getDayStatus,
}) => {
    const dayStatus = getDayStatus();

    const getMealStatusDot = (mealKey) => {
        const status = getMealStatus(mealKey);
        if (status === 'empty') return '⚪';
        if (status === 'cuadrada') return '🟢';
        if (status === 'sobra') return '🔴';
        return '🟡';
    };

    return (
        <div
            className="sticky top-[52px] z-30 bg-white shadow-md border-b cursor-pointer"
            onClick={() => setSummaryExpanded(!summaryExpanded)}
            data-testid="day-summary"
        >
            <div className="max-w-lg mx-auto px-4 py-3">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                        {tipoDia === 'entrenamiento' ? 'Día de Entrenamiento' : 'Día de Descanso'}
                    </span>
                    {dayStatus === 'cuadrado' && <span className="px-2 py-0.5 bg-green-500 text-white text-xs font-bold rounded-full">Cuadrado</span>}
                    {dayStatus === 'sobra' && <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-bold rounded-full">Te pasas</span>}
                </div>

                {[
                    { emoji: '🟢', label: 'P', val: dayMacros.P, tgt: dayTarget.P_total, color: '#4CAF50' },
                    { emoji: '🔵', label: 'H', val: dayMacros.H, tgt: dayTarget.H_total, color: '#2196F3' },
                    { emoji: '🟠', label: 'G', val: dayMacros.G, tgt: dayTarget.G_total, color: '#FFA500' },
                ].map(({ emoji, label, val, tgt, color }) => (
                    <div key={label} className="flex items-center gap-2 text-xs mb-1.5">
                        <span className="w-4 text-center">{emoji}</span>
                        <span className="w-6 font-semibold">{label}:</span>
                        <div className="flex-1"><ProgressBar value={val} max={tgt || 0} color={color} height={6} /></div>
                        <span className={`w-20 text-right font-mono ${val > (tgt || 0) + 4 ? 'text-red-500' : ''}`}>
                            {val.toFixed(0)}/{(tgt || 0).toFixed(0)}g
                        </span>
                    </div>
                ))}

                {tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri' && (
                    <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-center text-xs text-gray-500">
                        Peri: {servedPeriP.toFixed(0)}/{totalPeriP.toFixed(0)}P · {servedPeriH.toFixed(0)}/{totalPeriH.toFixed(0)}H
                    </div>
                )}

                <div className="mt-2 flex items-center justify-center gap-1 text-xs">
                    {mealOrder.map((mealKey, idx) => (
                        <span key={mealKey} className="flex items-center">
                            {idx > 0 && <span className="text-gray-300 mx-1">|</span>}
                            <span className="text-gray-500">{mealInfo[mealKey].shortName}</span>
                            <span className="ml-0.5">{getMealStatusDot(mealKey)}</span>
                        </span>
                    ))}
                </div>

                {summaryExpanded && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                        <table className="w-full text-xs">
                            <thead><tr className="text-gray-500">
                                <th className="text-left font-medium py-1"></th>
                                <th className="text-right font-medium py-1 w-16">P</th>
                                <th className="text-right font-medium py-1 w-16">H</th>
                                <th className="text-right font-medium py-1 w-16">G</th>
                            </tr></thead>
                            <tbody>
                                {mealOrder.map(mealKey => {
                                    const served = calculateMealMacros(mealKey);
                                    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
                                    return (
                                        <tr key={mealKey} className="border-t border-gray-100">
                                            <td className="py-1 text-gray-700">{mealInfo[mealKey].name}</td>
                                            <td className="text-right font-mono">{served.P.toFixed(0)}g</td>
                                            <td className="text-right font-mono">{served.H.toFixed(0)}g</td>
                                            <td className="text-right font-mono">{isPeri ? '-' : `${served.G.toFixed(0)}g`}</td>
                                        </tr>
                                    );
                                })}
                                <tr className="border-t-2 border-gray-300 font-bold">
                                    <td className="py-1">TOTAL</td>
                                    <td className="text-right font-mono">{dayMacros.P.toFixed(0)}g</td>
                                    <td className="text-right font-mono">{dayMacros.H.toFixed(0)}g</td>
                                    <td className="text-right font-mono">{dayMacros.G.toFixed(0)}g</td>
                                </tr>
                                <tr className="text-gray-500">
                                    <td className="py-1">OBJETIVO</td>
                                    <td className="text-right font-mono">{(dayTarget.P_total || 0).toFixed(0)}g</td>
                                    <td className="text-right font-mono">{(dayTarget.H_total || 0).toFixed(0)}g</td>
                                    <td className="text-right font-mono">{(dayTarget.G_total || 0).toFixed(0)}g</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                )}

                <div className="mt-2 flex justify-center">
                    {summaryExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </div>
            </div>
        </div>
    );
};

export default DaySummary;
