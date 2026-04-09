/**
 * DaySummary - Resumen sticky del día con macros
 */
import React from 'react';
import { Save, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '../ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import MacroProgressBar from './MacroProgressBar';

export const DaySummary = ({
    totals = { P: 0, H: 0, G: 0 },
    targets = { P: 0, H: 0, G: 0 },
    isExpanded,
    onToggle,
    onSave,
    isSaving = false,
    hasChanges = false
}) => {
    // Calculate overall progress
    const pProgress = targets.P > 0 ? (totals.P / targets.P) * 100 : 0;
    const hProgress = targets.H > 0 ? (totals.H / targets.H) * 100 : 0;
    const gProgress = targets.G > 0 ? (totals.G / targets.G) * 100 : 0;
    
    return (
        <div className="bg-zinc-900/95 backdrop-blur-sm border-b border-zinc-800 sticky top-0 z-40">
            <Collapsible open={isExpanded} onOpenChange={onToggle}>
                <div className="p-4">
                    {/* Header row */}
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
                            Resumen del día
                        </h3>
                        <div className="flex items-center gap-2">
                            {hasChanges && (
                                <Button
                                    size="sm"
                                    onClick={onSave}
                                    disabled={isSaving}
                                    className="bg-green-600 hover:bg-green-700 h-8"
                                    data-testid="save-day-btn"
                                >
                                    <Save size={14} className="mr-1" />
                                    {isSaving ? 'Guardando...' : 'Guardar'}
                                </Button>
                            )}
                            <CollapsibleTrigger asChild>
                                <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    className="h-8 w-8 p-0"
                                    data-testid="toggle-summary-btn"
                                >
                                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                </Button>
                            </CollapsibleTrigger>
                        </div>
                    </div>
                    
                    {/* Compact macro display */}
                    <div className="grid grid-cols-3 gap-4">
                        <MacroCircle 
                            label="P" 
                            current={totals.P} 
                            target={targets.P}
                            progress={pProgress}
                            color="text-orange-500"
                        />
                        <MacroCircle 
                            label="H" 
                            current={totals.H} 
                            target={targets.H}
                            progress={hProgress}
                            color="text-blue-500"
                        />
                        <MacroCircle 
                            label="G" 
                            current={totals.G} 
                            target={targets.G}
                            progress={gProgress}
                            color="text-yellow-500"
                        />
                    </div>
                </div>
                
                <CollapsibleContent>
                    <div className="px-4 pb-4 space-y-3 border-t border-zinc-800 pt-3">
                        <MacroProgressBar 
                            label="Proteínas" 
                            current={totals.P} 
                            target={targets.P}
                            color="bg-orange-500"
                        />
                        <MacroProgressBar 
                            label="Hidratos" 
                            current={totals.H} 
                            target={targets.H}
                            color="bg-blue-500"
                        />
                        <MacroProgressBar 
                            label="Grasas" 
                            current={totals.G} 
                            target={targets.G}
                            color="bg-yellow-500"
                        />
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </div>
    );
};

// Small circular progress indicator
const MacroCircle = ({ label, current, target, progress, color }) => {
    const isOver = current > target;
    const clampedProgress = Math.min(progress, 100);
    
    return (
        <div className="flex flex-col items-center">
            <div className="relative w-12 h-12">
                {/* Background circle */}
                <svg className="w-12 h-12 transform -rotate-90">
                    <circle
                        cx="24"
                        cy="24"
                        r="20"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="4"
                        className="text-zinc-700"
                    />
                    <circle
                        cx="24"
                        cy="24"
                        r="20"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="4"
                        strokeDasharray={`${clampedProgress * 1.256} 125.6`}
                        className={isOver ? 'text-red-500' : color}
                    />
                </svg>
                <span className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${color}`}>
                    {label}
                </span>
            </div>
            <div className="text-center mt-1">
                <span className={`text-sm font-medium ${isOver ? 'text-red-400' : 'text-white'}`}>
                    {current.toFixed(0)}
                </span>
                <span className="text-xs text-zinc-500">/{target}</span>
            </div>
        </div>
    );
};

export default DaySummary;
