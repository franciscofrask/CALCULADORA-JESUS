/**
 * FoodItem - Componente de alimento individual con controles
 */
import React from 'react';
import { Plus, Minus, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { getFoodEmoji, formatQuantity } from './constants';

export const FoodItem = ({ 
    food, 
    onIncrease, 
    onDecrease, 
    onRemove,
    onQuantityChange,
    editable = true 
}) => {
    const { nombre, cantidad, unidad, macros, categorias } = food;
    
    const handleQuantityInput = (e) => {
        const value = parseInt(e.target.value) || 0;
        if (onQuantityChange) {
            onQuantityChange(value);
        }
    };

    return (
        <div 
            className="flex items-center justify-between py-2 px-3 bg-zinc-800/50 rounded-lg"
            data-testid={`food-item-${food.alimento_id || food.id}`}
        >
            <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="text-lg">{getFoodEmoji(categorias)}</span>
                <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{nombre}</div>
                    <div className="text-xs text-zinc-500">
                        P={macros?.P || 0}g H={macros?.H || 0}g G={macros?.G || 0}g
                    </div>
                </div>
            </div>
            
            {editable ? (
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-zinc-400 hover:text-white"
                        onClick={onDecrease}
                        data-testid="decrease-qty-btn"
                    >
                        <Minus size={14} />
                    </Button>
                    
                    <input
                        type="number"
                        value={cantidad}
                        onChange={handleQuantityInput}
                        className="w-14 text-center text-sm bg-zinc-700 border-none rounded px-1 py-0.5 text-white"
                        data-testid="qty-input"
                    />
                    <span className="text-xs text-zinc-500 w-6">
                        {unidad === 'ud' ? 'ud' : 'g'}
                    </span>
                    
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-zinc-400 hover:text-white"
                        onClick={onIncrease}
                        data-testid="increase-qty-btn"
                    >
                        <Plus size={14} />
                    </Button>
                    
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-red-400 hover:text-red-300"
                        onClick={onRemove}
                        data-testid="remove-food-btn"
                    >
                        <Trash2 size={14} />
                    </Button>
                </div>
            ) : (
                <span className="text-sm text-zinc-400">
                    {formatQuantity(cantidad, unidad)}
                </span>
            )}
        </div>
    );
};

export default FoodItem;
