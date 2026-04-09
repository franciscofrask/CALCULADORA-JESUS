/**
 * MealCard - Tarjeta de comida con acordeón
 */
import React from 'react';
import { ChevronDown, ChevronUp, Plus, Zap, Wrench, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import MacroProgressBar from './MacroProgressBar';
import FoodItem from './FoodItem';

export const MealCard = ({
    mealKey,
    mealNumber,
    label,
    foods = [],
    target = { P: 0, H: 0, G: 0 },
    current = { P: 0, H: 0, G: 0 },
    isOpen,
    onToggle,
    onSuggestMenu,
    onBuildMeal,
    onRepeatMeal,
    onFoodIncrease,
    onFoodDecrease,
    onFoodRemove,
    onFoodQuantityChange,
    isPeriworkout = false,
    periType = null
}) => {
    const isEmpty = foods.length === 0;
    
    // Calculate progress percentages
    const pProgress = target.P > 0 ? (current.P / target.P) * 100 : 0;
    const hProgress = target.H > 0 ? (current.H / target.H) * 100 : 0;
    const gProgress = target.G > 0 ? (current.G / target.G) * 100 : 0;
    const avgProgress = (pProgress + hProgress + gProgress) / 3;
    
    const getStatusColor = () => {
        if (isEmpty) return 'bg-zinc-700';
        if (avgProgress >= 90) return 'bg-green-500/20 border-green-500/30';
        if (avgProgress >= 50) return 'bg-yellow-500/20 border-yellow-500/30';
        return 'bg-orange-500/20 border-orange-500/30';
    };

    return (
        <Collapsible open={isOpen} onOpenChange={onToggle}>
            <div className={`rounded-xl border transition-colors ${getStatusColor()}`}>
                <CollapsibleTrigger asChild>
                    <button 
                        className="w-full p-4 flex items-center justify-between"
                        data-testid={`meal-card-${mealKey}`}
                    >
                        <div className="flex items-center gap-3">
                            <div className="flex flex-col items-start">
                                <span className="font-semibold text-white">
                                    {label || `Comida ${mealNumber}`}
                                </span>
                                {isPeriworkout && (
                                    <span className="text-xs text-orange-400 flex items-center gap-1">
                                        <Zap size={12} />
                                        {periType === 'intra' ? 'Intra-entreno' : 'Post-entreno'}
                                    </span>
                                )}
                            </div>
                        </div>
                        
                        <div className="flex items-center gap-4">
                            <div className="text-right">
                                <div className="text-xs text-zinc-400">
                                    {foods.length} alimento{foods.length !== 1 ? 's' : ''}
                                </div>
                                <div className="text-xs">
                                    <span className="text-orange-400">P:{current.P.toFixed(0)}</span>
                                    <span className="text-zinc-500 mx-1">/</span>
                                    <span className="text-blue-400">H:{current.H.toFixed(0)}</span>
                                    <span className="text-zinc-500 mx-1">/</span>
                                    <span className="text-yellow-400">G:{current.G.toFixed(0)}</span>
                                </div>
                            </div>
                            {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                        </div>
                    </button>
                </CollapsibleTrigger>
                
                <CollapsibleContent>
                    <div className="px-4 pb-4 space-y-4">
                        {/* Progress bars */}
                        <div className="space-y-2">
                            <MacroProgressBar 
                                label="Proteínas" 
                                current={current.P} 
                                target={target.P}
                                color="bg-orange-500"
                            />
                            <MacroProgressBar 
                                label="Hidratos" 
                                current={current.H} 
                                target={target.H}
                                color="bg-blue-500"
                            />
                            <MacroProgressBar 
                                label="Grasas" 
                                current={current.G} 
                                target={target.G}
                                color="bg-yellow-500"
                            />
                        </div>
                        
                        {/* Foods list */}
                        {foods.length > 0 && (
                            <div className="space-y-2">
                                {foods.map((food, idx) => (
                                    <FoodItem
                                        key={`${food.alimento_id}-${idx}`}
                                        food={food}
                                        onIncrease={() => onFoodIncrease(mealKey, idx)}
                                        onDecrease={() => onFoodDecrease(mealKey, idx)}
                                        onRemove={() => onFoodRemove(mealKey, idx)}
                                        onQuantityChange={(qty) => onFoodQuantityChange(mealKey, idx, qty)}
                                    />
                                ))}
                            </div>
                        )}
                        
                        {/* Action buttons */}
                        {isEmpty ? (
                            <div className="flex flex-col gap-2">
                                <Button
                                    onClick={() => onSuggestMenu(mealKey)}
                                    className="w-full bg-orange-500 hover:bg-orange-600"
                                    data-testid={`suggest-menu-${mealKey}`}
                                >
                                    <Zap size={16} className="mr-2" />
                                    Sugiéreme un menú
                                </Button>
                                <div className="flex gap-2">
                                    <Button
                                        onClick={() => onBuildMeal(mealKey)}
                                        variant="outline"
                                        className="flex-1 border-zinc-600"
                                        data-testid={`build-meal-${mealKey}`}
                                    >
                                        <Wrench size={16} className="mr-2" />
                                        Lo hago yo
                                    </Button>
                                    <Button
                                        onClick={() => onRepeatMeal(mealKey)}
                                        variant="outline"
                                        className="flex-1 border-zinc-600"
                                        data-testid={`repeat-meal-${mealKey}`}
                                    >
                                        <RefreshCw size={16} className="mr-2" />
                                        Repetir
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            <div className="flex gap-2">
                                <Button
                                    onClick={() => onBuildMeal(mealKey)}
                                    variant="outline"
                                    size="sm"
                                    className="flex-1 border-zinc-600"
                                >
                                    <Plus size={14} className="mr-1" />
                                    Añadir alimento
                                </Button>
                            </div>
                        )}
                    </div>
                </CollapsibleContent>
            </div>
        </Collapsible>
    );
};

export default MealCard;
