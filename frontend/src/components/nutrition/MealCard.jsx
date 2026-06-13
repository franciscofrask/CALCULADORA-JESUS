import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { ProgressBar } from './DaySummary';
import {
    ChevronDown, ChevronUp, Plus, Trash2, Minus, Zap, Wrench, RefreshCw, ArrowUp
} from 'lucide-react';

// Calma rounds the per-meal target to the nearest 0.5 g FOR DISPLAY ONLY (stepRedondeo).
// The engine/remaining stay unrounded, so suggestions match Calma exactly.
const fmtHalf = (x) => (Math.round((x || 0) * 2) / 2).toString();
// Calma d(n,1): round to 1 decimal, drop trailing ".0" (e.g. 10.6, 50, 13.9).
const fmt1 = (x) => { const r = Math.round((x || 0) * 10) / 10; return Number.isInteger(r) ? String(r) : r.toFixed(1); };

const MealProgressBars = ({ mealKey, getMealTarget, calculateMealMacros }) => {
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';

    // Calma per-macro status (calcularIcono + etiqueta, margenValido = 4), r = target - served
    // UNROUNDED: round(r)==0 -> "Cuadrado" (green); else "[Válido · ]?(faltan|sobran) X.Xg"
    // where the "Válido" prefix shows when |r| < 4 (amber), otherwise danger (faltan yellow /
    // sobran red). Matches Calma e.g. "Cuadrado", "Válido · sobran 3.3g", "sobran 14.8g".
    const macroState = (servedVal, tgtVal) => {
        const r = tgtVal - servedVal;
        if (Math.round(r) === 0) return { txt: 'Cuadrado', cls: 'text-green-600', over: false };
        const within = Math.abs(r) < 4;
        const amt = (Math.round(Math.abs(r) * 10) / 10).toFixed(1);
        const verb = r > 0 ? 'faltan' : 'sobran';
        const txt = within ? `Válido · ${verb} ${amt}g` : `${r > 0 ? 'Faltan' : 'Sobran'} ${amt}g`;
        const cls = within ? 'text-amber-500' : (r > 0 ? 'text-yellow-600' : 'text-red-600');
        return { txt, cls, over: !within && r < 0 };
    };

    const bars = [
        { emoji: '🟢', label: 'P', val: served.P, tgt: target.P, color: '#4CAF50', st: macroState(served.P, target.P) },
        { emoji: '🔵', label: 'H', val: served.H, tgt: target.H, color: '#2196F3', st: macroState(served.H, target.H) },
    ];
    if (!isPeri) bars.push({ emoji: '🟠', label: 'G', val: served.G, tgt: target.G, color: '#FFA500', st: macroState(served.G, target.G) });

    return (
        <div className="bg-gray-50 rounded-lg p-3 mb-3" data-testid={`meal-progress-${mealKey}`}>
            {bars.map(({ emoji, label, val, tgt, color, st }) => (
                <div key={label} className="mb-2">
                    <div className="flex items-center gap-2">
                        <span className="w-5 text-center text-sm">{emoji}</span>
                        <span className="w-4 text-xs font-semibold text-gray-600">{label}</span>
                        <div className="flex-1"><ProgressBar value={val} max={tgt} color={color} height={8} showCheck /></div>
                        <span className={`text-xs font-mono w-16 text-right ${st.over ? 'text-red-500 font-bold' : ''}`}>{val.toFixed(1)}/{fmtHalf(tgt)}g</span>
                    </div>
                    <div className={`text-[10px] font-semibold ${st.cls} ml-9`}>{st.txt}</div>
                </div>
            ))}
        </div>
    );
};

const MealCard = ({
    mealKey, mealInfo, mealsData, expandedMeals, setExpandedMeals,
    getMealTarget, calculateMealMacros, getMealStatus,
    loadMenuOptions, setBuildMealModal, openRepeatModal,
    removeFood, moveFoodUp, updateFoodQuantity, updateFoodQuantityDirect,
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
                            {isPeri ? `${fmtHalf(target.P)}P | ${fmtHalf(target.H)}H` : `${fmtHalf(target.P)}P | ${fmtHalf(target.H)}H | ${fmtHalf(target.G)}G`}
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
                                                        <Button variant="outline" size="icon"
                                                            className="h-8 w-8 rounded-full shrink-0 border-brand-orange/40 text-brand-orange bg-brand-orange/5 hover:bg-brand-orange hover:text-white disabled:opacity-25 disabled:border-gray-200 disabled:text-gray-300 disabled:bg-transparent disabled:cursor-not-allowed"
                                                            disabled={idx === 0} onClick={() => moveFoodUp(mealKey, idx)} title="Subir">
                                                            <ArrowUp className="w-4 h-4" strokeWidth={2.5} />
                                                        </Button>
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
                                                        {hasMacros ? (
                                                        <span>({[
                                                            macros.P > 0 && `${fmt1(macros.P)}P`,
                                                            macros.H > 0 && `${fmt1(macros.H)}H`,
                                                            macros.G > 0 && `${fmt1(macros.G)}G`,
                                                        ].filter(Boolean).join(' | ')})</span>
                                                    ) : <span className="text-gray-400">(no aporta macros)</span>}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            <Button variant="ghost" className="w-full text-brand-orange hover:text-brand-orange-dark disabled:opacity-40 disabled:cursor-not-allowed" disabled={status === 'cuadrada' || status === 'sobra'} onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}><Plus className="w-4 h-4 mr-1" /> Añadir ingrediente</Button>
                            <button className="w-full text-xs text-gray-400 hover:text-red-500 mt-2 py-1" onClick={() => clearMeal(mealKey)}>Vaciar comida</button>
                        </>
                    )}
                </CardContent>
            )}
        </Card>
    );
};

export default MealCard;
