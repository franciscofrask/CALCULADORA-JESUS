import React from 'react';
import { ProgressBar, StatusDot } from './DaySummary';
import {
    ChevronDown, ChevronUp, Plus, Trash2, Minus, Zap, Wrench, RefreshCw, ArrowUp, Lock, Download
} from 'lucide-react';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

const fmtHalf = (x) => (Math.round((x || 0) * 2) / 2).toString();
const fmt1 = (x) => { const r = Math.round((x || 0) * 10) / 10; return Number.isInteger(r) ? String(r) : r.toFixed(1); };

const macrosLine = (m) => {
    const parts = [
        (m.P || 0) > 0 && `${fmt1(m.P)}P`,
        (m.H || 0) > 0 && `${fmt1(m.H)}H`,
        (m.G || 0) > 0 && `${fmt1(m.G)}G`,
    ].filter(Boolean);
    return parts.length ? parts.join(' · ') : 'sin macros';
};

// ===== Selector item (master-detail) =====
export const MealSelectorItem = ({ mealKey, mealInfo, getMealTarget, calculateMealMacros, getMealStatus, isLocked, selected, onSelect }) => {
    const info = mealInfo[mealKey];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const status = getMealStatus(mealKey);
    const bars = [
        { c: MACRO.P, v: served.P, t: target.P },
        { c: MACRO.H, v: served.H, t: target.H },
    ];
    if (!isPeri) bars.push({ c: MACRO.G, v: served.G, t: target.G });

    return (
        <button onClick={onSelect} data-testid={`meal-select-${mealKey}`}
            className={`text-left rounded-xl p-3 transition-all w-full border ${selected ? 'border-brand bg-brand/5 ring-1 ring-brand/40' : 'border-border bg-card hover:border-foreground/15'} ${isLocked ? 'opacity-60' : ''}`}>
            <div className="flex items-center gap-2.5">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 font-heading font-bold text-sm ${isPeri ? 'bg-brand/10 text-brand' : 'bg-muted text-foreground'}`}>
                    {isPeri ? <Zap className="w-4 h-4" /> : info.shortName}
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                        <span className="font-bold text-foreground text-sm truncate">{info.name}</span>
                        <StatusDot status={status} className="flex-shrink-0" />
                        {isLocked && <Lock className="w-3 h-3 text-amber-500 flex-shrink-0" />}
                    </div>
                    <span className="text-[10px] text-muted-foreground font-data">
                        {isPeri ? `${fmtHalf(target.P)}P·${fmtHalf(target.H)}H` : `${fmtHalf(target.P)}P·${fmtHalf(target.H)}H·${fmtHalf(target.G)}G`}
                    </span>
                </div>
            </div>
            <div className="flex items-center gap-1 mt-2.5">
                {bars.map((b, i) => (
                    <div key={i} className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full transition-all" style={{ width: `${b.t > 0 ? Math.min((b.v / b.t) * 100, 100) : 0}%`, backgroundColor: b.v > b.t + 4 ? '#EF4444' : b.c }} />
                    </div>
                ))}
            </div>
        </button>
    );
};

// ===== Tab (desktop) =====
export const MealTab = ({ mealKey, mealInfo, getMealTarget, calculateMealMacros, getMealStatus, isLocked, selected, onSelect }) => {
    const info = mealInfo[mealKey];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const status = getMealStatus(mealKey);
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const r = (x) => Math.round(x || 0);
    return (
        <button onClick={onSelect} data-testid={`meal-tab-${mealKey}`} role="tab" aria-selected={selected}
            className={`text-left rounded-xl px-3 py-2.5 border transition-all min-w-0 ${selected ? 'bg-brand text-white border-brand shadow-sm' : 'bg-card text-foreground border-border hover:border-foreground/25'} ${isLocked ? 'opacity-60' : ''}`}>
            <div className="flex items-center gap-1.5 mb-1.5">
                {isPeri && <Zap className={`w-3.5 h-3.5 flex-shrink-0 ${selected ? 'text-white' : 'text-brand'}`} />}
                <span className="font-heading font-bold uppercase tracking-wide text-sm leading-none truncate">{info.name}</span>
                {isLocked && <Lock className={`w-3 h-3 flex-shrink-0 ${selected ? 'text-white' : 'text-amber-500'}`} />}
                <StatusDot status={status} className="flex-shrink-0 ml-auto" />
            </div>
            <div className={`font-data text-[10px] leading-none truncate ${selected ? 'text-white/85' : 'text-muted-foreground'}`}>
                {r(served.P)}/{r(target.P)}P·{r(served.H)}/{r(target.H)}H{!isPeri && `·${r(served.G)}/${r(target.G)}G`}
            </div>
        </button>
    );
};

// ===== Macro progress block =====
const MealProgressBars = ({ mealKey, getMealTarget, calculateMealMacros, hasFoods }) => {
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';

    const macroState = (servedVal, tgtVal) => {
        if (!(servedVal > 0)) return { label: null, cls: '', over: false };
        const r = tgtVal - servedVal;
        if (Math.round(r) === 0) return { label: 'Cuadrado', cls: 'text-emerald-600 dark:text-emerald-400', over: false };
        if (Math.abs(r) < 4) return { label: 'Válido', cls: 'text-amber-500', over: false };
        return r > 0
            ? { label: `faltan ${fmt1(r)}g`, cls: 'text-red-500', over: false }
            : { label: `sobran ${fmt1(-r)}g`, cls: 'text-red-500', over: true };
    };

    const bars = [
        { label: 'P', name: 'Proteína', val: served.P, tgt: target.P, color: MACRO.P, st: macroState(served.P, target.P) },
        { label: 'H', name: 'Hidratos', val: served.H, tgt: target.H, color: MACRO.H, st: macroState(served.H, target.H) },
    ];
    if (!isPeri) bars.push({ label: 'G', name: 'Grasas', val: served.G, tgt: target.G, color: MACRO.G, st: macroState(served.G, target.G) });

    return (
        <div className="bg-muted/50 rounded-xl p-3.5 space-y-3" data-testid={`meal-progress-${mealKey}`}>
            {bars.map(({ label, name, val, tgt, color, st }) => (
                <div key={label}>
                    <div className="flex items-center gap-2.5">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                        <span className="text-xs font-bold w-16 flex-shrink-0 hidden sm:inline" style={{ color }}>{name}</span>
                        <span className="text-xs font-bold w-3 flex-shrink-0 sm:hidden" style={{ color }}>{label}</span>
                        <div className="flex-1 min-w-0"><ProgressBar value={val} max={tgt} color={color} height={9} showCheck /></div>
                        <span className={`text-xs font-data w-[72px] text-right ${hasFoods && st.over ? 'text-red-500 font-bold' : 'text-muted-foreground'}`}>{val.toFixed(1)}/{fmtHalf(tgt)}g</span>
                    </div>
                    {hasFoods && st.label && <div className={`text-[10px] font-semibold text-right ${st.cls}`}>{st.label}</div>}
                </div>
            ))}
        </div>
    );
};

// ===== Ingredient row =====
const IngredientRow = ({ food, idx, mealKey, isLocked, isEditing, increment,
    moveFoodUp, removeFood, updateFoodQuantity, updateFoodQuantityDirect,
    setEditingQuantity, formatFoodQuantity }) => {
    const macros = food.macros_efectivos || {};
    return (
        <div className="rounded-xl border border-border bg-muted/40 p-2.5">
            {/* Nombre completo (ya no se recorta) + macros */}
            <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground leading-snug">{food.nombre}</p>
                <p className="text-[11px] text-muted-foreground font-data mt-0.5">{macrosLine(macros)}</p>
            </div>

            {/* Controles debajo: prioridad + cantidad a la izquierda, eliminar a la derecha */}
            <div className="flex items-center justify-between gap-2 mt-2">
                <div className="flex items-center gap-2">
                    {/* Reorder (prioridad) */}
                    <button
                        className="flex flex-col items-center justify-center h-10 w-8 rounded-lg text-muted-foreground hover:text-brand hover:bg-brand/10 disabled:opacity-20 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors flex-shrink-0"
                        disabled={idx === 0 || isLocked} onClick={() => moveFoodUp(mealKey, idx)} title="Subir prioridad"
                        data-testid={`reorder-${mealKey}-${idx}`}
                    >
                        <ArrowUp className="w-4 h-4" strokeWidth={2.5} />
                        <span className="text-[9px] font-data leading-none mt-0.5">{idx + 1}</span>
                    </button>

                    {/* Cantidad (gramos) - stepper conectado */}
                    <div className="inline-flex items-stretch rounded-lg border border-border bg-card overflow-hidden flex-shrink-0" title="Cantidad en gramos">
                        <button className="px-2.5 flex items-center text-foreground hover:bg-brand hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground transition-colors" disabled={isLocked} onClick={() => updateFoodQuantity(mealKey, idx, -increment)} aria-label="Menos gramos">
                            <Minus className="w-3.5 h-3.5" />
                        </button>
                        {isEditing ? (
                            <input type="number" defaultValue={food.cantidad_g || 0} autoFocus
                                className="w-14 text-center text-sm font-bold font-data bg-transparent border-x border-border text-foreground focus:outline-none"
                                onBlur={(e) => updateFoodQuantityDirect(mealKey, idx, e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter') updateFoodQuantityDirect(mealKey, idx, e.target.value); if (e.key === 'Escape') setEditingQuantity({ mealKey: null, foodIndex: null }); }} />
                        ) : (
                            <button className="min-w-[64px] px-2 text-sm font-bold font-data text-center text-foreground border-x border-border hover:text-brand disabled:opacity-50 transition-colors" disabled={isLocked}
                                onClick={() => !isLocked && setEditingQuantity({ mealKey, foodIndex: idx })} data-testid={`qty-${mealKey}-${idx}`}>
                                {formatFoodQuantity ? formatFoodQuantity(food) : `${food.cantidad_g || 0}g`}
                            </button>
                        )}
                        <button className="px-2.5 flex items-center text-foreground hover:bg-brand hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground transition-colors" disabled={isLocked} onClick={() => updateFoodQuantity(mealKey, idx, increment)} aria-label="Más gramos">
                            <Plus className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>

                {/* Eliminar */}
                <button className="h-9 w-9 rounded-lg flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10 disabled:opacity-30 transition-colors flex-shrink-0" disabled={isLocked} onClick={() => removeFood(mealKey, idx)} aria-label="Eliminar alimento" data-testid={`remove-${mealKey}-${idx}`}>
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

// ===== Meal card =====
const MealCard = ({
    mealKey, mealInfo, mealsData, expandedMeals, setExpandedMeals,
    getMealTarget, calculateMealMacros, getMealStatus,
    loadMenuOptions, setBuildMealModal, openRepeatModal,
    removeFood, moveFoodUp, updateFoodQuantity, updateFoodQuantityDirect,
    editingQuantity, setEditingQuantity, getQuantityIncrement,
    clearMeal, formatFoodQuantity,
    isLocked = false, canVolcar = false, onVolcar,
    mealMode = 'auto', setMealMode, forceExpanded = false,
}) => {
    const isExpanded = forceExpanded ? true : expandedMeals[mealKey];
    const target = getMealTarget(mealKey);
    const foods = mealsData[mealKey]?.alimentos || [];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const info = mealInfo[mealKey];
    const status = getMealStatus(mealKey);

    const HeaderInner = (
        <>
            <div className="flex items-center gap-3 min-w-0">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 font-heading font-bold text-lg ${isPeri ? 'bg-brand/10 text-brand' : 'bg-muted text-foreground'}`}>
                    {isPeri ? <Zap className="w-5 h-5" /> : info.shortName}
                </div>
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-heading font-bold uppercase tracking-wide text-foreground text-lg truncate">{info.name}</h3>
                        <StatusDot status={status} className="flex-shrink-0" />
                        {isLocked && <Lock className="w-4 h-4 text-amber-500 flex-shrink-0" />}
                    </div>
                    <p className="text-xs text-muted-foreground font-data mt-0.5">
                        Objetivo: {isPeri ? `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H` : `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H · ${fmtHalf(target.G)}G`}
                    </p>
                </div>
            </div>
            {!forceExpanded && (isExpanded ? <ChevronUp className="w-5 h-5 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="w-5 h-5 text-muted-foreground flex-shrink-0" />)}
        </>
    );

    return (
        <div className={`surface overflow-hidden ${isPeri ? 'border-l-4 border-l-brand' : ''} ${isLocked ? 'opacity-70' : ''} ${!forceExpanded && !isExpanded ? 'surface-hover' : ''}`} data-testid={`meal-card-${mealKey}`}>
            {/* Header */}
            {forceExpanded ? (
                <div className="p-4 sm:p-5 flex items-center justify-between gap-3 border-b border-border">{HeaderInner}</div>
            ) : (
                <button className="w-full text-left p-3.5 sm:p-4 flex items-center justify-between gap-3"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}>
                    {HeaderInner}
                </button>
            )}

            {isExpanded && (
                <div className={forceExpanded ? 'p-4 sm:p-5 space-y-4' : 'px-3.5 sm:px-4 pb-4 pt-1 space-y-3'}>
                    {/* Modo de cálculo */}
                    {!isPeri && !isLocked && setMealMode && (
                        <div className="flex items-center justify-between gap-3 rounded-xl bg-muted/50 px-3.5 py-3">
                            <div className="min-w-0">
                                <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Modo de cálculo</p>
                                <p className="text-[11px] text-muted-foreground/80 mt-0.5">{mealMode === 'manual' ? 'Cantidad libre, sin autoajuste' : 'Ajusta cantidades a tus macros'}</p>
                            </div>
                            <div className="inline-flex rounded-lg bg-card p-0.5 border border-border flex-shrink-0">
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode !== 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'auto')} data-testid={`mode-auto-${mealKey}`}>Automático</button>
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode === 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'manual')} data-testid={`mode-manual-${mealKey}`}>Manual</button>
                            </div>
                        </div>
                    )}

                    <MealProgressBars mealKey={mealKey} getMealTarget={getMealTarget} calculateMealMacros={calculateMealMacros} hasFoods={foods.length > 0} />

                    {isLocked && (
                        <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/25 rounded-xl px-3 py-2">
                            <Lock className="w-3.5 h-3.5 shrink-0" />
                            <span>Bloqueada - los macros del día están volcados en otra comida. Quita el volcado para editar.</span>
                        </div>
                    )}

                    {/* Empty states */}
                    {foods.length === 0 && !isPeri && !isLocked && (
                        <div className="space-y-2">
                            <button className="btn-brand w-full h-12 flex items-center justify-center gap-2 uppercase tracking-wide"
                                onClick={() => loadMenuOptions(mealKey)} data-testid={`menu-options-${mealKey}`}>
                                <Zap className="w-5 h-5" /> Sugiéreme un menú
                            </button>
                            <div className="grid grid-cols-2 gap-2">
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'normal' })} data-testid={`build-meal-${mealKey}`}>
                                    <Wrench className="w-4 h-4" /> Lo hago yo
                                </button>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                    <RefreshCw className="w-4 h-4" /> Repetir
                                </button>
                            </div>
                        </div>
                    )}
                    {foods.length === 0 && mealKey === 'Intra' && !isLocked && (
                        <button className="w-full h-11 rounded-xl bg-brand/10 border border-brand text-brand font-semibold hover:bg-brand hover:text-white transition-colors flex items-center justify-center gap-1.5"
                            onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'intra' })}>
                            <Zap className="w-4 h-4" /> Construir Intra
                        </button>
                    )}
                    {foods.length === 0 && mealKey === 'Post' && !isLocked && (
                        <button className="w-full h-11 rounded-xl bg-brand/10 border border-brand text-brand font-semibold hover:bg-brand hover:text-white transition-colors flex items-center justify-center gap-1.5"
                            onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'post' })}>
                            <Zap className="w-4 h-4" /> Construir Post
                        </button>
                    )}

                    {/* Ingredients */}
                    {foods.length > 0 && (
                        <div className="space-y-3">
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <p className="caption">Ingredientes</p>
                                    <span className="text-[11px] text-muted-foreground">↑ = prioridad · −/+ = gramos</span>
                                </div>
                                <div className="space-y-2">
                                    {foods.map((food, idx) => (
                                        <IngredientRow key={idx} food={food} idx={idx} mealKey={mealKey} isLocked={isLocked}
                                            isEditing={editingQuantity.mealKey === mealKey && editingQuantity.foodIndex === idx}
                                            increment={getQuantityIncrement(food)}
                                            moveFoodUp={moveFoodUp} removeFood={removeFood}
                                            updateFoodQuantity={updateFoodQuantity} updateFoodQuantityDirect={updateFoodQuantityDirect}
                                            setEditingQuantity={setEditingQuantity} formatFoodQuantity={formatFoodQuantity} />
                                    ))}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button className="flex-1 py-2.5 rounded-xl border border-dashed border-border text-brand font-semibold text-sm hover:bg-brand/5 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-1.5 transition-colors" disabled={isLocked} onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}>
                                    <Plus className="w-4 h-4" /> Añadir ingrediente
                                </button>
                                {!isLocked && <button className="text-xs text-muted-foreground hover:text-red-500 px-3 py-2.5 transition-colors" onClick={() => clearMeal(mealKey)}>Vaciar</button>}
                            </div>
                        </div>
                    )}

                    {canVolcar && onVolcar && (
                        <button
                            className="w-full text-xs text-muted-foreground hover:text-brand py-1.5 flex items-center justify-center gap-1.5 transition-colors"
                            onClick={() => onVolcar(mealKey)}
                            title="Volcar los macros restantes del día en esta comida y bloquear las demás"
                        >
                            <Download className="w-3.5 h-3.5" /> Volcar macros aquí
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default MealCard;
