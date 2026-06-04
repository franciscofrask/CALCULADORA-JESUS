import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { ProgressBar } from './DaySummary';
import {
    ChevronDown, ChevronUp, Plus, Trash2, Minus, Zap, Wrench, RefreshCw
} from 'lucide-react';

const MealProgressBars = ({ mealKey, getMealTarget, calculateMealMacros, getMealStatus }) => {
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const status = getMealStatus(mealKey);

    const getMacroDiff = (servedVal, targetVal) => {
        const diff = targetVal - servedVal;
        if (Math.abs(diff) <= 4) return { ok: true, diff: 0 };
        return { ok: false, diff };
    };

    const pDiff = getMacroDiff(served.P, target.P);
    const hDiff = getMacroDiff(served.H, target.H);
    const gDiff = !isPeri ? getMacroDiff(served.G, target.G) : { ok: true, diff: 0 };

    const pOver = served.P > target.P + 4;
    const hOver = served.H > target.H + 4;
    const gOver = !isPeri && served.G > target.G + 4;

    let statusMessage = '';
    let statusColor = '';

    if (status === 'cuadrada') {
        statusMessage = '🟢 Cuadrada'; statusColor = 'text-green-600';
    } else if (pOver || hOver || gOver) {
        const parts = [];
        if (pOver) parts.push(`${(served.P - target.P).toFixed(0)}g P`);
        if (hOver) parts.push(`${(served.H - target.H).toFixed(0)}g H`);
        if (gOver) parts.push(`${(served.G - target.G).toFixed(0)}g G`);
        statusMessage = `🔴 Sobran ${parts.join(', ')}`; statusColor = 'text-red-600';
    } else if (status === 'falta') {
        const parts = [];
        if (!pDiff.ok && pDiff.diff > 0) parts.push(`${pDiff.diff.toFixed(0)}g P`);
        if (!hDiff.ok && hDiff.diff > 0) parts.push(`${hDiff.diff.toFixed(0)}g H`);
        if (!gDiff.ok && gDiff.diff > 0) parts.push(`${gDiff.diff.toFixed(0)}g G`);
        if (parts.length > 0) { statusMessage = `🟡 Faltan ${parts.join(', ')}`; statusColor = 'text-yellow-600'; }
    }

    const bars = [
        { emoji: '🟢', label: 'P', val: served.P, tgt: target.P, color: '#4CAF50', over: pOver },
        { emoji: '🔵', label: 'H', val: served.H, tgt: target.H, color: '#2196F3', over: hOver },
    ];
    if (!isPeri) bars.push({ emoji: '🟠', label: 'G', val: served.G, tgt: target.G, color: '#FFA500', over: gOver });

    return (
        <div className="bg-gray-50 rounded-lg p-3 mb-3" data-testid={`meal-progress-${mealKey}`}>
            {bars.map(({ emoji, label, val, tgt, color, over }) => (
                <div key={label} className="flex items-center gap-2 mb-2">
                    <span className="w-5 text-center text-sm">{emoji}</span>
                    <span className="w-4 text-xs font-semibold text-gray-600">{label}</span>
                    <div className="flex-1"><ProgressBar value={val} max={tgt} color={color} height={8} showCheck /></div>
                    <span className={`text-xs font-mono w-16 text-right ${over ? 'text-red-500 font-bold' : ''}`}>{val.toFixed(0)}/{tgt.toFixed(0)}g</span>
                </div>
            ))}
            {statusMessage && <div className={`text-xs font-semibold ${statusColor} mt-1`}>{statusMessage}</div>}
        </div>
    );
};

const MealCard = ({
    mealKey, mealInfo, mealsData, expandedMeals, setExpandedMeals,
    getMealTarget, calculateMealMacros, getMealStatus,
    loadMenuOptions, setBuildMealModal, openRepeatModal,
    removeFood, updateFoodQuantity, updateFoodQuantityDirect,
    editingQuantity, setEditingQuantity, getQuantityIncrement,
    clearMeal, getFoodEmoji, formatFoodQuantity,
}) => {
    const isExpanded = expandedMeals[mealKey];
    const target = getMealTarget(mealKey);
    const foods = mealsData[mealKey]?.alimentos || [];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const info = mealInfo[mealKey];
    const status = getMealStatus(mealKey);

    const statusSymbol = status === 'empty' ? '⚪' : status === 'cuadrada' ? '🟢' : status === 'sobra' ? '🔴' : '🟡';

    return (
        <Card className={`bg-white shadow-md rounded-2xl overflow-hidden transition-all duration-200 ${isPeri ? 'border-l-4 border-l-brand-orange' : ''}`}>
            <button className="w-full text-left p-4 flex items-center justify-between"
                onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}
                data-testid={`meal-card-${mealKey}`}
            >
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{info.emoji}</span>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="font-bold text-gray-900">{info.name}</h3>
                            <span className="text-sm">{statusSymbol}</span>
                        </div>
                        <p className="text-xs text-gray-500">
                            {isPeri ? `${target.P.toFixed(0)}P | ${target.H.toFixed(0)}H` : `${target.P.toFixed(0)}P | ${target.H.toFixed(0)}H | ${target.G.toFixed(0)}G`}
                        </p>
                    </div>
                </div>
                {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </button>

            {isExpanded && (
                <CardContent className="pt-0 px-4 pb-4">
                    <MealProgressBars mealKey={mealKey} getMealTarget={getMealTarget} calculateMealMacros={calculateMealMacros} getMealStatus={getMealStatus} />

                    {foods.length === 0 && !isPeri && (
                        <div className="space-y-2">
                            <Button className="w-full h-12 bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full shadow-lg shadow-brand-orange/30"
                                onClick={() => loadMenuOptions(mealKey)} data-testid={`menu-options-${mealKey}`}>
                                <Zap className="w-5 h-5 mr-2" /> SUGIÉREME UN MENÚ
                            </Button>
                            <div className="grid grid-cols-2 gap-2">
                                <Button variant="outline" className="h-10 rounded-full border-gray-300"
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'normal' })} data-testid={`build-meal-${mealKey}`}>
                                    <Wrench className="w-4 h-4 mr-1" /> Lo hago yo
                                </Button>
                                <Button variant="outline" className="h-10 rounded-full border-gray-300"
                                    onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                    <RefreshCw className="w-4 h-4 mr-1" /> Repetir
                                </Button>
                            </div>
                        </div>
                    )}
                    {foods.length === 0 && mealKey === 'Intra' && (
                        <Button className="w-full h-10 rounded-full bg-brand-orange/10 border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white"
                            onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'intra' })}>
                            <Zap className="w-4 h-4 mr-1" /> Construir Intra
                        </Button>
                    )}
                    {foods.length === 0 && mealKey === 'Post' && (
                        <Button className="w-full h-10 rounded-full bg-brand-orange/10 border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white"
                            onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'post' })}>
                            <Zap className="w-4 h-4 mr-1" /> Construir Post
                        </Button>
                    )}

                    {foods.length > 0 && (
                        <>
                            <div className="border-t border-gray-100 pt-3 mb-3">
                                <p className="text-xs text-gray-500 mb-2 font-semibold">── INGREDIENTES ──</p>
                                <div className="space-y-3">
                                    {foods.map((food, idx) => {
                                        const macros = food.macros_efectivos || {};
                                        const increment = getQuantityIncrement(food);
                                        const isEditing = editingQuantity.mealKey === mealKey && editingQuantity.foodIndex === idx;
                                        const hasMacros = (macros.P || 0) > 0 || (macros.H || 0) > 0 || (macros.G || 0) > 0;
                                        return (
                                            <div key={idx} className="bg-gray-50 rounded-lg p-3">
                                                <div className="flex items-center justify-between mb-1">
                                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                                        <span className="text-xl">{getFoodEmoji(food.categorias)}</span>
                                                        <span className="text-sm font-semibold text-gray-800 truncate">{food.nombre}</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-7 w-7 text-gray-400 hover:text-red-500" onClick={() => removeFood(mealKey, idx)}>
                                                        <Trash2 className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-1">
                                                        <Button variant="outline" size="icon" className="h-8 w-8 rounded-full" onClick={() => updateFoodQuantity(mealKey, idx, -increment)}><Minus className="w-3 h-3" /></Button>
                                                        {isEditing ? (
                                                            <input type="number" defaultValue={food.cantidad_g || 0} className="w-16 h-8 text-center text-sm font-bold border rounded-lg" autoFocus
                                                                onBlur={(e) => updateFoodQuantityDirect(mealKey, idx, e.target.value)}
                                                                onKeyDown={(e) => { if (e.key === 'Enter') updateFoodQuantityDirect(mealKey, idx, e.target.value); if (e.key === 'Escape') setEditingQuantity({ mealKey: null, foodIndex: null }); }} />
                                                        ) : (
                                                            <button className="min-w-[64px] h-8 px-2 text-sm font-bold text-center bg-white border border-gray-200 rounded-lg hover:border-brand-orange"
                                                                onClick={() => setEditingQuantity({ mealKey, foodIndex: idx })}>
                                                                {formatFoodQuantity ? formatFoodQuantity(food) : `${food.cantidad_g || 0}g`}
                                                            </button>
                                                        )}
                                                        <Button variant="outline" size="icon" className="h-8 w-8 rounded-full" onClick={() => updateFoodQuantity(mealKey, idx, increment)}><Plus className="w-3 h-3" /></Button>
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        {hasMacros ? <span>({(macros.P || 0).toFixed(0)}P | {(macros.H || 0).toFixed(0)}H | {(macros.G || 0).toFixed(0)}G)</span> : <span className="text-gray-400">(no aporta macros)</span>}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            <Button variant="ghost" className="w-full text-brand-orange hover:text-brand-orange-dark" onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}><Plus className="w-4 h-4 mr-1" /> Añadir ingrediente</Button>
                            <button className="w-full text-xs text-gray-400 hover:text-red-500 mt-2 py-1" onClick={() => clearMeal(mealKey)}>Vaciar comida</button>
                        </>
                    )}
                </CardContent>
            )}
        </Card>
    );
};

export default MealCard;
