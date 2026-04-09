/**
 * MacroProgressBar - Barra de progreso para macros
 */
import React from 'react';

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
                <span className="text-zinc-400">{label}</span>
                <span className={isOver ? 'text-red-400' : 'text-zinc-300'}>
                    {current.toFixed(1)}g / {target}g
                    {showPercentage && <span className="text-zinc-500 ml-1">({Math.round(percentage)}%)</span>}
                </span>
            </div>
            <div className="h-2 bg-zinc-700 rounded-full overflow-hidden">
                <div 
                    className={`h-full transition-all duration-300 ${isOver ? 'bg-red-500' : color}`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
};

export default MacroProgressBar;
