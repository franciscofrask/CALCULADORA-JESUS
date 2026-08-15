import React from 'react';
import { StatusDot } from './DaySummary';
import { macrosDeVista } from './ModoMacros';
import { seExcede, textoExceso } from '../../lib/exceso';
import { num1, numMedio } from '../../lib/numeros';
import ContadorFamilia from './ContadorFamilia';
import {
    ChevronDown, ChevronUp, Plus, Trash2, Minus, Zap, Wrench, RefreshCw, ArrowUp, Lock, Download
} from 'lucide-react';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

/**
 * EN QUÉ PUNTO ESTÁ ESTA COMIDA, con la palabra que usa el documento del 10-08.
 *
 * «Sin hacer», «Válida» y «Cuadrada» son las suyas, y «Montar» se cambió por «Sin hacer»
 * a petición de Jesús. Van al final de la fila, que es lo que convierte la lista en algo
 * que se va tachando.
 *
 * La app distingue MENOS estados que el documento: `getMealStatus` da por cuadrada todo lo
 * que caiga dentro de ±4 g en los tres macros, y el documento separa «Cuadrada» (clavada)
 * de «Válida» (dentro del margen pero no clavada). Esa distinción se hace aquí, con los
 * mismos números que ya usa el marcador de dentro de la comida, para no inventar un
 * criterio nuevo: clavado es diferencia menor de medio gramo.
 *
 * En el perientreno la grasa no cuenta, igual que en el resto del cálculo.
 */
const estadoDeLaComida = (status, target, served, cuantosAlimentos, esPeri = false) => {
    if (!cuantosAlimentos) return { texto: 'Sin hacer', cls: 'text-muted-foreground' };
    // POR CUÁNTO TE PASAS, no solo que te pasas (Jesús, 13-08): «la app enseña los dos
    // números pero no la diferencia; el cliente tiene que restar». El texto sale de
    // `lib/exceso`, el mismo que usa el chat, para que la app no hable de dos maneras.
    if (status === 'sobra') {
        const cuanto = textoExceso(served, target, { esPeri });
        return { texto: cuanto ? `Te pasas ${cuanto}` : 'Te pasas', cls: 'text-red-500' };
    }
    if (status === 'falta') return { texto: 'Te falta', cls: 'text-amber-600 dark:text-amber-400' };
    const dif = ['P', 'H', 'G'].map(m => Math.abs((target[m] || 0) - (served[m] || 0)));
    const clavada = dif.every(d => d < 0.5);
    return clavada
        ? { texto: 'Cuadrada', cls: 'text-emerald-600 dark:text-emerald-400' }
        : { texto: 'Válida', cls: 'text-emerald-600/70 dark:text-emerald-400/70' };
};

// Los números con coma decimal y sin decimales cuando son cero, en un solo sitio para toda
// la pantalla (Jesús, 15-08, fallo 43: «34.2/37.5g»).
const fmtHalf = numMedio;
const fmt1 = num1;

const macrosLine = (m) => {
    const parts = [
        (m.P || 0) > 0 && `${fmt1(m.P)} g proteína`,
        (m.H || 0) > 0 && `${fmt1(m.H)} g hidratos`,
        (m.G || 0) > 0 && `${fmt1(m.G)} g grasa`,
    ].filter(Boolean);
    return parts.length ? parts.join(' · ') : 'sin macros';
};

// Version corta para movil: en la fila del ingrediente los macros comparten linea con los
// controles y "47.4g proteina · 26.6g hidratos" no cabe; "47.4P · 26.6H" si.
const macrosLineCorta = (m) => {
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

// ===== Tab =====
// Pestañas de verdad: solo el punto de estado y el nombre, y una línea naranja bajo la
// abierta. Las cajas con los macros dentro pesaban tanto como el detalle que abrían.
export const MealTab = ({ mealKey, mealInfo, getMealStatus, isLocked, selected, onSelect }) => {
    const info = mealInfo[mealKey];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const status = getMealStatus(mealKey);
    return (
        <button onClick={onSelect} data-testid={`meal-tab-${mealKey}`} role="tab" aria-selected={selected}
            className={`flex items-center gap-2 whitespace-nowrap px-3 py-2.5 -mb-px border-b-2 transition-colors ${
                selected
                    ? 'border-brand text-foreground font-semibold'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
            } ${isLocked ? 'opacity-60' : ''}`}>
            <StatusDot status={status} className="flex-shrink-0" />
            {isPeri && <Zap className="w-3.5 h-3.5 flex-shrink-0 text-brand" />}
            <span className="text-sm">{info.name}</span>
            {isLocked && <Lock className="w-3 h-3 flex-shrink-0 text-amber-500" />}
        </button>
    );
};

// ===== Macro progress block =====
const MealProgressBars = ({ mealKey, getMealTarget, calculateMealMacros, hasFoods }) => {
    // EN EL TELÉFONO, EL ESTADO VA DETRÁS DE «VER DETALLES». Los «Cuadrado», «Válido» y
    // «faltan 12g» de cada macro son tres avisos por comida y cinco comidas por pantalla:
    // en 390 px eso es media pantalla diciendo en palabras lo que la resta de al lado ya
    // dice. No se quitan -- cuando hace falta, hacen falta --, se piden.
    //
    // En escritorio salen siempre, como hasta ahora: esa vista no se ha rediseñado todavía.
    const [verDetalles, setVerDetalles] = React.useState(false);
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';

    // `key` para saber DE QUÉ macro se habla: pasarse de proteína no se pinta en rojo
    // (Jesús, 13-08). El «sobran X g» se sigue diciendo -- el dato no se esconde --, pero
    // en el color de siempre, porque no es un fallo que haya que corregir.
    const macroState = (servedVal, tgtVal, key) => {
        if (!(servedVal > 0)) return { label: null, cls: '', over: false };
        const r = tgtVal - servedVal;
        if (Math.round(r) === 0) return { label: 'Cuadrado', cls: 'text-emerald-600 dark:text-emerald-400', over: false };
        if (Math.abs(r) < 4) return { label: 'Válido', cls: 'text-amber-500', over: false };
        if (r > 0) return { label: `faltan ${fmt1(r)} g`, cls: 'text-red-500', over: false };
        const enRojo = seExcede(key, servedVal, tgtVal, { esPeri: isPeri });
        return { label: `sobran ${fmt1(-r)} g`,
                 cls: enRojo ? 'text-red-500' : 'text-muted-foreground', over: enRojo };
    };

    const bars = [
        { label: 'P', name: 'Proteína', val: served.P, tgt: target.P, color: MACRO.P, st: macroState(served.P, target.P, 'P') },
        { label: 'H', name: 'Hidratos', val: served.H, tgt: target.H, color: MACRO.H, st: macroState(served.H, target.H, 'H') },
    ];
    if (!isPeri) bars.push({ label: 'G', name: 'Grasas', val: served.G, tgt: target.G, color: MACRO.G, st: macroState(served.G, target.G, 'G') });

    // Sin barras: los tres macros en una sola linea (servido/objetivo + cuanto falta
    // o sobra). El color del texto ya dice como va cada uno.
    return (
        <>
            {/* EL BLOQUE ENTERO DE P/H/G VA DETRÁS DE «VER DETALLES» EN EL TELÉFONO, tal cual
                estaba, sin quitarle nada: los tres macros con lo servido, lo objetivo y el
                «Cuadrado» o «faltan 12g» de cada uno. Ocupaba una franja permanente en cada
                una de las cinco comidas, y arriba del todo ya está lo que le queda del día.
                Cuando lo necesita -- mientras monta esa comida -- lo pide. */}
            <div className={`bg-muted/50 rounded-xl px-3 py-2.5 flex-wrap items-center gap-x-5 gap-y-1.5 ${verDetalles ? 'flex' : 'hidden lg:flex'}`}
                data-testid={`meal-progress-${mealKey}`}>
                {bars.map(({ label, name, val, tgt, color, st }) => (
                    <div key={label} className="flex items-center gap-1.5 whitespace-nowrap">
                        <span className="w-2.5 h-2.5 lg:w-2 lg:h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                        <span className="text-[15px] lg:text-[11px] font-bold hidden sm:inline" style={{ color }}>{name}</span>
                        <span className="text-[15px] lg:text-[11px] font-bold sm:hidden" style={{ color }}>{label}</span>
                        <span className={`font-data text-[15px] lg:text-[11px] ${hasFoods && st.over ? 'text-red-500 font-bold' : 'text-muted-foreground'}`}>{fmt1(val)}/{fmtHalf(tgt)} g</span>
                        {hasFoods && st.label && <span className={`font-data text-[15px] lg:text-[11px] font-semibold ${st.cls}`}>{st.label}</span>}
                    </div>
                ))}
            </div>
            <button onClick={() => setVerDetalles(v => !v)} data-testid={`ver-detalles-${mealKey}`}
                className="lg:hidden text-[14px] text-muted-foreground hover:text-foreground underline underline-offset-2 self-start">
                {verDetalles ? 'ocultar detalles' : 'ver detalles'}
            </button>
        </>
    );
};

// ===== Ingredient row =====
const IngredientRow = ({ food, idx, mealKey, isLocked, isEditing, increment,
    moveFoodUp, removeFood, updateFoodQuantity, updateFoodQuantityDirect,
    setEditingQuantity, formatFoodQuantity, modoMacros = 'metodo',
    esPorUnidad, pesoUnidad, acumFamilias }) => {
    const macros = macrosDeVista(food, modoMacros);
    // Los alimentos por unidades se escriben en unidades ("2 huevos"), no en gramos.
    const porUnidad = esPorUnidad ? esPorUnidad(food) : false;
    const peso = pesoUnidad ? pesoUnidad(food) : 100;
    const valorEditable = porUnidad
        ? Math.round(((food.cantidad_g || 0) / peso) * 2) / 2
        : (food.cantidad_g || 0);
    return (
        // Todo el alimento en una linea: prioridad, nombre + macros, cantidad y eliminar.
        // El nombre se recorta con puntos suspensivos (completo en el title) para que
        // la lista del dia no se dispare a lo alto.
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-xl border border-border bg-muted/40 px-2 py-1.5">
            {/* Nombre + macros. Los alimentos de marca tienen ficha propia: el nombre abre su
                enlace, igual que en el buscador de alimentos (naranja = tiene ficha).

                En movil ocupa SU PROPIA LINEA (order-1 + w-full). En una sola linea no cabia:
                los controles fijos (prioridad 32 + stepper 129 + papelera 36 = 197 px) se
                comen casi toda la fila de 335 px de un movil, dejaban 92 px para el texto y
                el nombre del alimento se quedaba en una letra o desaparecia del todo, asi que
                no habia forma de saber que llevaba la comida. Desde sm vuelve a la linea unica. */}
            <div className="order-1 w-full min-w-0 sm:order-2 sm:w-auto sm:flex-1">
                {/* El nombre del alimento, a 17 px: es lo que la persona lee para saber qué
                    lleva su comida, y estaba en 14, por debajo del texto normal. */}
                {food.url ? (
                    <a href={food.url} target="_blank" rel="noopener noreferrer"
                        className="block text-[17px] lg:text-sm font-semibold text-brand underline underline-offset-2 truncate"
                        title={`${food.nombre} (abre la ficha del producto)`}>
                        {food.nombre}
                    </a>
                ) : (
                    <span className="block text-[17px] lg:text-sm font-semibold text-foreground truncate" title={food.nombre}>{food.nombre}</span>
                )}
                {/* Lo que llevas hoy de su familia, si es de las que se calibran. Jesús,
                    13-08: «un contador en la línea del alimento desde el primer gramo».
                    Va debajo del nombre y no en su propia fila: en un móvil de 335 px la
                    fila ya está repartida al milímetro (ver el comentario de arriba). */}
                <ContadorFamilia bloque={food.bloque} gramos={acumFamilias?.[food.bloque]?.gramos} />
            </div>

            {/* Macros: en movil comparten linea con los controles, para no gastar una fila
                entera. En sm van justo detras del nombre, como siempre. */}
            <span className="order-3 flex-1 min-w-0 truncate text-[14px] lg:text-[11px] text-muted-foreground font-data sm:hidden"
                title={macrosLine(macros)}>{macrosLineCorta(macros)}</span>
            <span className="hidden sm:inline order-3 text-[14px] lg:text-[11px] text-muted-foreground font-data whitespace-nowrap flex-shrink-0"
                title={macrosLine(macros)}>{macrosLine(macros)}</span>

            {/* Reorder (prioridad) */}
            <button
                className="order-2 sm:order-1 flex flex-col items-center justify-center h-9 w-7 rounded-lg text-muted-foreground hover:text-brand hover:bg-brand/10 disabled:opacity-20 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors flex-shrink-0"
                disabled={idx === 0 || isLocked} onClick={() => moveFoodUp(mealKey, idx)} title="Subir prioridad"
                data-testid={`reorder-${mealKey}-${idx}`}
            >
                <ArrowUp className="w-4 h-4" strokeWidth={2.5} />
                <span className="text-[9px] font-data leading-none mt-0.5">{idx + 1}</span>
            </button>

            {/* Cantidad (gramos) - stepper conectado. En movil se pega a la derecha (ml-auto),
                con la prioridad a la izquierda y el nombre encima. */}
            <div className="order-3 ml-auto sm:ml-0 inline-flex items-stretch h-9 rounded-lg border border-border bg-card overflow-hidden flex-shrink-0"
                title={porUnidad ? `Cantidad en unidades · 1 ud = ${num1(peso)} g` : 'Cantidad en gramos'}>
                <button className="px-2 flex items-center text-foreground hover:bg-brand hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground transition-colors" disabled={isLocked} onClick={() => updateFoodQuantity(mealKey, idx, -increment)}
                    aria-label={porUnidad ? 'Menos unidades' : 'Menos gramos'}>
                    <Minus className="w-3.5 h-3.5" />
                </button>
                {isEditing ? (
                    <input type="number" defaultValue={valorEditable} autoFocus
                        step={porUnidad ? '0.5' : '1'} min="0"
                        aria-label={porUnidad ? 'Unidades' : 'Gramos'}
                        className="w-14 text-center text-sm font-bold font-data bg-transparent border-x border-border text-foreground focus:outline-none"
                        onBlur={(e) => updateFoodQuantityDirect(mealKey, idx, e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') updateFoodQuantityDirect(mealKey, idx, e.target.value); if (e.key === 'Escape') setEditingQuantity({ mealKey: null, foodIndex: null }); }} />
                ) : (
                    <button className="min-w-[60px] px-2 text-sm font-bold font-data text-center text-foreground border-x border-border hover:text-brand disabled:opacity-50 transition-colors whitespace-nowrap" disabled={isLocked}
                        onClick={() => !isLocked && setEditingQuantity({ mealKey, foodIndex: idx })} data-testid={`qty-${mealKey}-${idx}`}>
                        {formatFoodQuantity ? formatFoodQuantity(food) : `${num1(food.cantidad_g || 0)} g`}
                        {/* A CUÁNTO EQUIVALE LA UNIDAD, AL LADO (Jesús, 15-08, fallo 46): «1 ud»
                            no dice cuánto pesa, y de ahí salía que el mismo alimento valiera una
                            cosa pulsándolo y otra escribiéndolo. La calculadora de ahora la pone
                            siempre en la propia línea. */}
                        {porUnidad && (
                            <span className="ml-1 text-[10px] font-normal text-muted-foreground">({num1(peso)} g)</span>
                        )}
                    </button>
                )}
                <button className="px-2 flex items-center text-foreground hover:bg-brand hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground transition-colors" disabled={isLocked} onClick={() => updateFoodQuantity(mealKey, idx, increment)}
                    aria-label={porUnidad ? 'Más unidades' : 'Más gramos'}>
                    <Plus className="w-3.5 h-3.5" />
                </button>
            </div>

            {/* Eliminar */}
            <button className="order-4 h-9 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10 disabled:opacity-30 transition-colors flex-shrink-0" disabled={isLocked} onClick={() => removeFood(mealKey, idx)} aria-label="Eliminar alimento" data-testid={`remove-${mealKey}-${idx}`}>
                <Trash2 className="w-4 h-4" />
            </button>
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
    clearMeal, formatFoodQuantity, esPorUnidad, pesoUnidad,
    isLocked = false, canVolcar = false, onVolcar, onCuadrar,
    mealMode = 'auto', setMealMode, forceExpanded = false, denso = false,
    // Solo cambia lo que pone en la LISTA de ingredientes. Los totales de la comida,
    // su estado y las cantidades siguen siendo del metodo, pase lo que pase.
    modoMacros = 'metodo',
    // Lo que lleva el DIA de cada familia que se calibra, para el contador de la linea del
    // alimento. Viene de `mealCardProps` y es el mismo para todas las comidas: desde el
    // 13-08 el tramo lo decide el total del dia, no la comida (ver `ContadorFamilia`).
    acumFamilias = null,
}) => {
    const isExpanded = forceExpanded ? true : expandedMeals[mealKey];
    const target = getMealTarget(mealKey);
    const foods = mealsData[mealKey]?.alimentos || [];
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';
    const info = mealInfo[mealKey];
    const status = getMealStatus(mealKey);
    // En qué punto está la comida, con su frase. Se calcula aquí arriba porque el titular
    // del teléfono depende de ella: cuando la comida se pasa, el texto es largo («Te pasas
    // 29 g de hidratos y 12 g de grasa») y OCUPA EL SITIO DEL NOMBRE en vez de pelearse con
    // él. Francisco, 13-08: «ese texto tapa el título de Comida 1, Comida 2... haz que lo
    // reemplace si se pasa». Los otros estados son cortos («Válida», «Te falta») y caben al
    // lado, así que esos no se tocan.
    const estado = estadoDeLaComida(status, target, calculateMealMacros(mealKey), foods.length, isPeri);
    const excesoTapaElNombre = status === 'sobra' && foods.length > 0;

    const HeaderInner = (
        <>
            <div className="flex items-center gap-3 min-w-0">
                <div className={`${denso ? 'w-9 h-9 text-sm' : 'w-12 h-12 text-lg'} rounded-xl flex items-center justify-center flex-shrink-0 font-heading font-bold ${isPeri ? 'bg-brand/10 text-brand' : 'bg-muted text-foreground'}`}>
                    {isPeri ? <Zap className={denso ? 'w-4 h-4' : 'w-5 h-5'} /> : info.shortName}
                </div>
                {/* EL TEXTO, MÁS GRANDE. Esta fila es lo que el cliente recorre de arriba
                    abajo para saber qué le queda por hacer, y el objetivo -- los tres
                    números que decide todo lo demás -- iba en 12 px, más pequeño que
                    cualquier otra cosa de la pantalla. El nombre sube a 20 px y el objetivo
                    a 15, que es el tamaño del texto normal. */}
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className={`font-heading font-bold uppercase tracking-wide text-foreground truncate ${denso ? 'text-xl lg:text-base' : 'text-2xl lg:text-lg'} ${excesoTapaElNombre ? 'hidden lg:block' : ''}`}>{info.name}</h3>
                        {/* El punto de color, solo en escritorio: en el teléfono el estado se
                            pide con «ver detalles», dentro de la comida. */}
                        <StatusDot status={status} className="hidden lg:inline-block flex-shrink-0" />
                        {isLocked && <Lock className="w-4 h-4 text-amber-500 flex-shrink-0" />}
                    </div>
                    {/* En el teléfono los números bajan al pie de la tarjeta, no van pegados
                        al nombre: así la fila de arriba queda con lo que se recorre de un
                        vistazo -- la comida y en qué punto está -- y el objetivo, que es lo
                        que se lee cuando ya te has parado en esa comida, queda debajo. */}
                    <p className="hidden lg:block text-xs text-muted-foreground font-data mt-0.5">
                        Objetivo: {isPeri ? `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H` : `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H · ${fmtHalf(target.G)}G`}
                    </p>
                </div>
            </div>

            {/* CÓMO VA ESTA COMIDA, CON SU PALABRA (documento del 10-08, pantalla 9): la
                lista se lee de arriba abajo como algo que se va tachando, y para eso cada
                fila tiene que decir en qué punto está. Solo en el teléfono: en escritorio
                está el punto de color de siempre. */}
            {/* Cuando se pasa, este texto ES el titular de la fila: se le deja encoger
                (`min-w-0` y sin `flex-shrink-0`) y alinearse a la izquierda, en el hueco
                que deja el nombre escondido. En los demás estados se queda como estaba,
                a la derecha y sin encoger. */}
            <span className={`lg:hidden text-[15px] font-bold text-right ${estado.cls} ${
                excesoTapaElNombre ? 'min-w-0 flex-1 text-left' : 'flex-shrink-0 ml-auto'}`}
                data-testid={`estado-comida-${mealKey}`}>
                {estado.texto}
            </span>
            {/* Con el día entero desplegado el modo va aquí, en pequeño: la banda de
                "Modo de cálculo" repetida seis veces no cabía, pero esconderla dejaba
                sin Automático/Manual a las comidas que aún no tienen alimentos. */}
            {denso && !isPeri && !isLocked && setMealMode && (
                <div className="inline-flex rounded-lg bg-muted p-0.5 flex-shrink-0" title="Automático ajusta las cantidades a tus macros; manual las deja como las pongas">
                    <button className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-colors ${mealMode !== 'manual' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}
                        onClick={() => setMealMode(mealKey, 'auto')} data-testid={`mode-auto-${mealKey}`}>Automático</button>
                    <button className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-colors ${mealMode === 'manual' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}
                        onClick={() => setMealMode(mealKey, 'manual')} data-testid={`mode-manual-${mealKey}`}>Manual</button>
                </div>
            )}
            {!forceExpanded && (isExpanded ? <ChevronUp className="w-5 h-5 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="w-5 h-5 text-muted-foreground flex-shrink-0" />)}
        </>
    );

    return (
        <div className={`surface overflow-hidden ${isPeri ? 'border-l-4 border-l-brand' : ''} ${isLocked ? 'opacity-70' : ''} ${!forceExpanded && !isExpanded ? 'surface-hover' : ''}`} data-testid={`meal-card-${mealKey}`}>
            {/* Header */}
            {forceExpanded ? (
                <div className={`${denso ? 'p-3 sm:p-3.5' : 'p-4 sm:p-5'} flex items-center justify-between gap-3 border-b border-border`}>{HeaderInner}</div>
            ) : (
                <button className="w-full text-left p-3.5 sm:p-4 pb-1.5 flex items-center justify-between gap-3"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}>
                    {HeaderInner}
                </button>
            )}
            {/* EL OBJETIVO, AL PIE DE LA TARJETA (teléfono). Arriba queda la comida y su
                estado, que es lo que se recorre de un vistazo; los números, que son lo que
                se lee cuando ya te has parado en esa comida, van debajo y a todo el ancho. */}
            {!forceExpanded && (
                <p className="lg:hidden px-3.5 sm:px-4 pb-3 text-[17px] font-data text-foreground/70"
                    data-testid={`objetivo-${mealKey}`}>
                    {isPeri ? `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H` : `${fmtHalf(target.P)}P · ${fmtHalf(target.H)}H · ${fmtHalf(target.G)}G`}
                </p>
            )}

            {isExpanded && (
                <div className={forceExpanded ? (denso ? 'p-3 sm:p-3.5 space-y-3' : 'p-4 sm:p-5 space-y-4') : 'px-3.5 sm:px-4 pb-4 pt-1 space-y-3'}>
                    {/* Modo de cálculo. En denso no va aquí: está en la cabecera de la comida. */}
                    {!isPeri && !isLocked && setMealMode && !denso && (
                        <div className="flex items-center justify-between gap-3 rounded-xl bg-muted/50 px-3.5 py-3">
                            {/* Sin la explicación debajo del rótulo en el teléfono: «Automático»
                                y «Manual» están ahí al lado y se entienden solos, y la frase se
                                repetía en cada comida que se abriera. En escritorio se queda. */}
                            <div className="min-w-0">
                                <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Modo de cálculo</p>
                                <p className="hidden lg:block text-[11px] text-muted-foreground/80 mt-0.5">{mealMode === 'manual' ? 'Cantidad libre, sin autoajuste' : 'Ajusta cantidades a tus macros'}</p>
                            </div>
                            <div className="inline-flex rounded-lg bg-card p-0.5 border border-border flex-shrink-0">
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode !== 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'auto')} data-testid={`mode-auto-${mealKey}`}>Automático</button>
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode === 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'manual')} data-testid={`mode-manual-${mealKey}`}>Manual</button>
                            </div>
                        </div>
                    )}

                    {/* Siempre los del metodo: el switch solo cambia la lista de abajo. */}
                    <MealProgressBars mealKey={mealKey} getMealTarget={getMealTarget}
                        calculateMealMacros={calculateMealMacros} hasFoods={foods.length > 0} />

                    {isLocked && (
                        <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/25 rounded-xl px-3 py-2">
                            <Lock className="w-3.5 h-3.5 shrink-0" />
                            <span>Bloqueada - los macros del día están volcados en otra comida. Quita el volcado para editar.</span>
                        </div>
                    )}

                    {/* Empty states. En denso (día entero desplegado) las tres maneras de
                        empezar caben en una sola fila: el bloque alto repetido seis veces
                        convertía la pantalla en un pasillo de botones naranjas. */}
                    {foods.length === 0 && !isPeri && !isLocked && (
                        denso ? (
                            // Mismas tres opciones y con su nombre entero; solo cambia que caben
                            // en una fila, con "Sugiéreme un menú" del doble de ancho porque es
                            // la principal. En móvil pasan a dos filas para no recortar el texto.
                            <div className="grid grid-cols-2 sm:grid-cols-[2fr_1fr_1fr] gap-2">
                                <button className="btn-brand h-11 col-span-2 sm:col-span-1 flex items-center justify-center gap-2 text-sm uppercase tracking-wide"
                                    onClick={() => loadMenuOptions(mealKey)} data-testid={`menu-options-${mealKey}`}>
                                    <Zap className="w-4 h-4" /> Sugiéreme un menú
                                </button>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'normal' })} data-testid={`build-meal-${mealKey}`}>
                                    <Wrench className="w-4 h-4" /> Lo hago yo
                                </button>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                    <RefreshCw className="w-4 h-4" /> Repetir
                                </button>
                            </div>
                        ) : (
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
                        )
                    )}
                    {/* Peri (Intra/Post): sugeridor de biblioteca (solo menús Peri, separados
                        server-side por tipo_comida) + constructor manual */}
                    {foods.length === 0 && isPeri && !isLocked && (
                        <div className={denso ? 'grid grid-cols-1 sm:grid-cols-2 gap-2' : 'space-y-2'}>
                            <button className={`btn-brand flex items-center justify-center gap-2 uppercase tracking-wide ${denso ? 'h-11 text-sm' : 'w-full h-12'}`}
                                onClick={() => loadMenuOptions(mealKey)} data-testid={`menu-options-${mealKey}`}>
                                <Zap className={denso ? 'w-4 h-4' : 'w-5 h-5'} /> Sugiéreme un menú
                            </button>
                            <button className={`rounded-xl bg-brand/10 border border-brand text-brand font-semibold hover:bg-brand hover:text-white transition-colors flex items-center justify-center gap-1.5 ${denso ? 'h-11 text-sm' : 'w-full h-11'}`}
                                onClick={() => setBuildMealModal({ open: true, mealKey, mode: mealKey === 'Intra' ? 'intra' : 'post' })}>
                                <Zap className="w-4 h-4" /> Construir {mealKey === 'Intra' ? 'Intra' : 'Post'}
                            </button>
                        </div>
                    )}

                    {/* Ingredients */}
                    {foods.length > 0 && (
                        <div className="space-y-3">
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <p className="caption">Ingredientes</p>
                                    <span className="text-[11px] text-muted-foreground">↑ = prioridad · −/+ = gramos</span>
                                </div>
                                <div className="space-y-1.5">
                                    {foods.map((food, idx) => (
                                        <IngredientRow key={idx} food={food} idx={idx} mealKey={mealKey} isLocked={isLocked}
                                            isEditing={editingQuantity.mealKey === mealKey && editingQuantity.foodIndex === idx}
                                            increment={getQuantityIncrement(food)}
                                            moveFoodUp={moveFoodUp} removeFood={removeFood}
                                            updateFoodQuantity={updateFoodQuantity} updateFoodQuantityDirect={updateFoodQuantityDirect}
                                            setEditingQuantity={setEditingQuantity} formatFoodQuantity={formatFoodQuantity}
                                            modoMacros={modoMacros} esPorUnidad={esPorUnidad} pesoUnidad={pesoUnidad}
                                            acumFamilias={acumFamilias} />
                                    ))}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button className="flex-1 py-2.5 rounded-xl border border-dashed border-border text-brand font-semibold text-sm hover:bg-brand/5 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-1.5 transition-colors" disabled={isLocked} onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}>
                                    <Plus className="w-4 h-4" /> Añadir ingrediente
                                </button>
                                {!isLocked && onCuadrar && <button className="text-xs font-semibold text-brand border border-brand rounded-xl px-3 py-2.5 hover:bg-brand hover:text-white transition-colors" onClick={() => onCuadrar(mealKey)} title="Ajustar las cantidades a tus macros sin pasarse (respetando el mínimo de cada alimento)">Cuadrar</button>}
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
