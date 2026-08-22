/**
 * MacroProgressBar - Barra de progreso para macros
 */
import React from 'react';

// Coma decimal y sin ceros de relleno, como el resto de la casa (QA 15-08).
const gr = (x) => {
    const n = Math.round((Number(x) || 0) * 10) / 10;
    return Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
};

export const MacroProgressBar = ({ 
    label, 
    current, 
    target, 
    color = 'bg-orange-500',
    showPercentage = true 
}) => {
    const percentage = target > 0 ? Math.min((current / target) * 100, 100) : 0;
    const isOver = current > target;
    
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className={isOver ? 'text-red-400' : 'text-foreground'}>
                    {gr(current)} g / {gr(target)} g
                    {showPercentage && <span className="text-muted-foreground ml-1">({Math.round(percentage)}%)</span>}
                </span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                    className={`h-full transition-all duration-300 ${isOver ? 'bg-red-500' : color}`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
};

export default MacroProgressBar;
