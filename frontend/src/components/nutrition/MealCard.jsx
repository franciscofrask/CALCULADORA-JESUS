import React from 'react';
import { StatusDot } from './DaySummary';
import { margenDe, seExcede } from '../../lib/exceso';
import { leerMacro } from '../../lib/estadoDelMacro';
import { num0, num1, numMedio, alMedio, alDecima } from '../../lib/numeros';
import { TOPE_GRAMOS } from '../../lib/cantidades';
import ContadorFamilia from './ContadorFamilia';
import MenuDeLaPantalla from './MenuDeLaPantalla';
import {
    ChevronDown, ChevronUp, Plus, Trash2, Minus, Zap, Wrench, RefreshCw, ArrowUp, ArrowUpDown, Lock, Download, Star
} from 'lucide-react';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

/**
 * EN QUÉ PUNTO ESTÁ ESTA COMIDA, con la palabra que usa el documento del 10-08.
 *
 * «Sin hacer» y «Cuadrada» son las suyas, y «Montar» se cambió por «Sin hacer»
 * a petición de Jesús. Van al final de la fila, que es lo que convierte la lista en algo
 * que se va tachando.
 *
 * TRES ESTADOS, LOS MISMOS QUE EN NUTRICIÓN (Francisco, 17-08): por debajo del margen
 * «Te falta», por encima «Te pasas», y dentro «Cuadrada». Se quita «Válida».
 *
 * Estaba separado «Cuadrada» (clavada, menos de medio gramo) de «Válida» (dentro del
 * margen pero no clavada), siguiendo el documento del 10-08. En la pantalla eso se leía
 * como que había dos varas: una comida con 10,5 g de grasa sobre 10 salía «Válida» y
 * parecía peor que otra idéntica, cuando el método la da por buena igual. El margen es
 * ±4 g y es el mismo en todas partes; si algo cae dentro, cuadra.
 *
 * En el perientreno la grasa no cuenta, igual que en el resto del cálculo.
 */
const NOMBRE_MACRO = { P: 'proteína', H: 'hidratos', G: 'grasa' };
const enumerar = (p) => (p.length <= 1 ? p.join('') : `${p.slice(0, -1).join(', ')} y ${p[p.length - 1]}`);

const estadoDeLaComida = (status, target, served, cuantosAlimentos, esPeri = false, bloqueada = false) => {
    // Con el volcado puesto, las demás comidas quedan con objetivo = servido y salían
    // como «Cuadrada» en verde mientras el día decía «te falta» (punto 11 del 23-08:
    // «una de las dos cosas está mal»). La que mentía era el verde: bloqueada no es
    // cuadrada, es que ya no juega.
    if (bloqueada) return { texto: 'bloqueada', color: null };
    // SIN CREAR, EN NARANJA (punto 117). Le falta todo, así que cae del mismo lado que
    // cualquier macro fuera de margen: «lo que te pide algo se ve, lo que ya está se apaga».
    if (!cuantosAlimentos) return { texto: 'sin crear', color: 'pasado' };

    const claves = esPeri ? ['P', 'H'] : ['P', 'H', 'G'];
    // EL MARGEN DE CADA MACRO ES EL DE LA COMIDA (`margenDe`), no los 4 g planos del día.
    // El artifact dice que el margen es «el mismo de la parte 2», pero aquí eso mordería:
    // 4 g sobre los 9 de proteína que pide un intra son casi la mitad, y ya pasó una vez
    // que la pantalla decía «Comida cuadrada. Pulsa Guardar» sobre un «5 / 9». El margen
    // proporcional es el mismo criterio con el que `getMealStatus` decide el estado, así
    // que la palabra y el color no pueden contradecirlo. Ver lib/exceso.
    const desvios = claves.map((k) => ({ k, d: (served[k] || 0) - (target[k] || 0) }));
    const fuera = desvios.filter((x) => Math.abs(x.d) >= margenDe(target[x.k]));

    // POR CUÁNTO Y DE QUÉ, no solo que te pasas (Jesús, 13-08): «la app enseña los dos
    // números pero no la diferencia; el cliente tiene que restar».
    if (status === 'sobra') {
        const sobran = fuera.filter((x) => x.d > 0 && seExcede(x.k, served[x.k], target[x.k]));
        return {
            texto: sobran.length
                ? `sobran ${enumerar(sobran.map((x) => `${num0(x.d)} de ${NOMBRE_MACRO[x.k]}`))}`
                : 'sobran',
            color: 'pasado',
        };
    }
    if (status === 'falta') {
        const faltan = fuera.filter((x) => x.d < 0);
        return {
            texto: faltan.length
                ? `faltan ${enumerar(faltan.map((x) => `${num0(-x.d)} de ${NOMBRE_MACRO[x.k]}`))}`
                : 'faltan',
            color: 'pasado',
        };
    }
    // Cuadrada. Si clava, se dice y ya; si baila dentro del margen, se dice cuánto, con las
    // palabras de la parte 2: «válido +2».
    const mayor = desvios.map((x) => ({ ...x, d: Math.round(x.d) }))
        .sort((a, b) => Math.abs(b.d) - Math.abs(a.d))[0];
    if (!mayor || mayor.d === 0) return { texto: 'cuadrada', color: 'ok' };
    return { texto: `válido ${mayor.d > 0 ? '+' : '−'}${Math.abs(mayor.d)}`, color: 'ok' };
};

// El punto de color que va delante de la palabra del estado (punto 116).
const PuntoDeEstado = ({ color }) => (color ? (
    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${color === 'ok' ? 'bg-ok' : 'bg-pasado'}`} />
) : null);

const claseDelEstado = (color) => (color === 'ok' ? 'text-ok' : color === 'pasado' ? 'text-pasado' : 'text-muted-foreground');

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
/**
 * LOS NÚMEROS DE LA COMIDA, SIEMPRE Y CON EL FORMATO DE LA CASA (puntos 120 a 122 del
 * artifact del 26-08).
 *
 * «Esto ya lo calcula la app. Está escondido detrás de un "ver detalles" en gris.»
 *
 * Y lo estaba de verdad: en el teléfono el bloque nacía cerrado, así que para saber qué le
 * faltaba a la comida había que pedirlo. Lo que enseñaba era además otro formato -- «54/63,5
 * g» con un chip al lado --, distinto del de Inicio y del de la cabecera de esta pantalla.
 * Ahora es el mismo de siempre: número, punto, palabra y barra.
 *
 * AQUÍ SÍ VAN DECIMALES (punto 121). Es la pantalla donde se afina, y el gramo importa: se
 * pide `vista: 'comida'` a lib/estadoDelMacro, que no redondea y que por debajo de 1 g dice
 * «cuadrado» (punto 122). El margen sigue siendo el proporcional de `lib/exceso`, el mismo
 * con el que la comida decide su estado, para no tener dos varas en la misma tarjeta.
 */
const MealProgressBars = ({ mealKey, getMealTarget, calculateMealMacros, hasFoods }) => {
    const target = getMealTarget(mealKey);
    const served = calculateMealMacros(mealKey);
    const isPeri = mealKey === 'Intra' || mealKey === 'Post';

    const claves = isPeri ? ['P', 'H'] : ['P', 'H', 'G'];
    const NOMBRE = { P: 'Proteína', H: 'Hidratos', G: 'Grasa' };

    return (
        <div className="grid grid-cols-3 gap-3" data-testid={`meal-progress-${mealKey}`}>
            {claves.map((k) => {
                // LO QUE FALTA SE CUENTA CONTRA EL OBJETIVO QUE SE ESTÁ VIENDO (17-08-2026).
                // La línea decía «54/63,5 g · faltan 9,3 g», y 54 + 9,3 son 63,3, no 63,5:
                // el objetivo se enseña redondeado al medio gramo (como en Calma) y el
                // restante salía del valor exacto. Se cuenta contra lo que lee.
                const meta = alMedio(target[k] || 0);
                const tiene = alDecima(served[k] || 0);
                const lectura = leerMacro({ vista: 'comida', hay: tiene, objetivo: meta, margen: margenDe(meta) });
                return (
                    <div key={k} className="text-center" data-testid={`comida-macro-${mealKey}-${k}`}>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center justify-center gap-1">
                            {NOMBRE[k]}
                            {hasFoods && lectura.color && (
                                <span className={`w-1.5 h-1.5 rounded-full ${lectura.color === 'ok' ? 'bg-ok' : 'bg-pasado'}`} />
                            )}
                        </p>
                        <p className="numero-grande font-data leading-none text-[26px] sm:text-[30px] mt-1.5 text-foreground">
                            {fmt1(tiene)}
                        </p>
                        {hasFoods && (
                            <p data-testid={`comida-palabra-${mealKey}-${k}`}
                                className={`text-xs mt-1 ${lectura.color === 'ok' ? 'text-ok font-medium'
                                    : lectura.color === 'pasado' ? 'text-pasado font-medium' : 'text-muted-foreground'}`}>
                                {lectura.palabra}
                            </p>
                        )}
                        {hasFoods && lectura.barra && (
                            <div className="h-1 rounded-full bg-muted mt-1.5 overflow-hidden">
                                <div className={`h-full rounded-full ${lectura.barra.color === 'ok' ? 'bg-ok' : 'bg-pasado'}`}
                                    style={{ width: `${lectura.barra.largo}%` }} />
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

// ===== Ingredient row =====
const IngredientRow = ({ food, idx, mealKey, isLocked, isEditing, increment,
    moveFoodUp, removeFood, updateFoodQuantity, updateFoodQuantityDirect,
    setEditingQuantity, formatFoodQuantity,
    esPorUnidad, pesoUnidad, acumFamilias, ordenando = false }) => {
    // Los del método, que son los que la app cuenta. Hasta el 26-08 aquí se podía
    // enseñar en su lugar lo que dice la etiqueta (Método / Reales), y hacía falta un
    // aviso al principio de la pantalla explicando que lo que se veía no era lo que
    // contaba. Punto 112: fuera las dos cosas.
    const macros = food?.macros_efectivos || {};
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
                {/* Hasta dos líneas en vez de «Pan Wasa fibre…» (punto 12 del 23-08:
                    los nombres cortados no se leen). En escritorio sigue a una. */}
                {food.url ? (
                    <a href={food.url} target="_blank" rel="noopener noreferrer"
                        className="block text-[17px] lg:text-sm font-semibold text-brand underline underline-offset-2 break-words line-clamp-2 lg:line-clamp-1"
                        title={`${food.nombre} (abre la ficha del producto)`}>
                        {food.nombre}
                    </a>
                ) : (
                    <span className="block text-[17px] lg:text-sm font-semibold text-foreground break-words line-clamp-2 lg:line-clamp-1" title={food.nombre}>{food.nombre}</span>
                )}
                {/* Lo que llevas hoy de su familia, si es de las que se calibran. Jesús,
                    13-08: «un contador en la línea del alimento desde el primer gramo».
                    Va debajo del nombre y no en su propia fila: en un móvil de 335 px la
                    fila ya está repartida al milímetro (ver el comentario de arriba). */}
                <ContadorFamilia bloque={food.bloque} gramos={acumFamilias?.[food.bloque]?.gramos}
                    proteinaCuenta={food.proteina_cuenta !== false} />
            </div>

            {/* Macros: en movil comparten linea con los controles, para no gastar una fila
                entera. En sm van justo detras del nombre, como siempre. */}
            <span className="order-3 flex-1 min-w-0 truncate text-[14px] lg:text-[11px] text-muted-foreground font-data sm:hidden"
                title={macrosLine(macros)}>{macrosLineCorta(macros)}</span>
            <span className="hidden sm:inline order-3 text-[14px] lg:text-[11px] text-muted-foreground font-data whitespace-nowrap flex-shrink-0"
                title={macrosLine(macros)}>{macrosLine(macros)}</span>

            {/* SUBIR, SOLO MIENTRAS SE ORDENA (punto 126). Estaba siempre, y en el móvil le
                quitaba a cada alimento el ancho que su nombre necesita: «Fiambre de pechuga
                de pavo de buena calidad (más del 85 %)» caía a dos líneas.

                Y ya no se llama «prioridad» (punto 127): la palabra hacía pensar que Cuadrar
                reparte por ese orden, y no es verdad; esto solo coloca el alimento más
                arriba. Fuera también el número de debajo -- la posición ya se ve porque el
                alimento está ahí --, y con él se va el motivo por el que la flecha del
                primero no parecía apagada: el número seguía a plena luz debajo (punto 128). */}
            {ordenando && (
                <button
                    className="order-2 sm:order-1 flex items-center justify-center h-9 w-7 rounded-lg text-muted-foreground hover:text-brand hover:bg-brand/10 disabled:opacity-25 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors flex-shrink-0"
                    disabled={idx === 0 || isLocked} onClick={() => moveFoodUp(mealKey, idx)}
                    title={idx === 0 ? 'Ya está el primero' : 'Subirlo'}
                    data-testid={`reorder-${mealKey}-${idx}`}
                >
                    <ArrowUp className="w-4 h-4" strokeWidth={2.5} />
                </button>
            )}

            {/* Cantidad (gramos) - stepper conectado. En movil se pega a la derecha (ml-auto),
                con la prioridad a la izquierda y el nombre encima. */}
            <div className="order-3 ml-auto sm:ml-0 inline-flex items-stretch h-9 rounded-lg border border-border bg-card overflow-hidden flex-shrink-0"
                title={porUnidad ? `Cantidad en unidades · 1 ud = ${num1(peso)} g` : 'Cantidad en gramos'}>
                <button className="px-2 flex items-center text-foreground hover:bg-brand hover:text-white disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-foreground transition-colors" disabled={isLocked} onClick={() => updateFoodQuantity(mealKey, idx, -increment)}
                    aria-label={porUnidad ? 'Menos unidades' : 'Menos gramos'}>
                    <Minus className="w-3.5 h-3.5" />
                </button>
                {isEditing ? (
                    // Con techo: el campo no tenía `max`, así que la flecha de subir no
                    // paraba nunca. El techo es el tope duro, en la unidad del campo; lo que
                    // es mucho para ESTE alimento se avisa aparte, sin cortar.
                    <input type="number" defaultValue={valorEditable} autoFocus
                        step={porUnidad ? '0.5' : '1'} min="0"
                        max={porUnidad ? Math.floor(TOPE_GRAMOS / (peso || 100)) : TOPE_GRAMOS}
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
                            siempre en la propia línea.

                            Y ES EL TOTAL, NO LO QUE PESA UNA (16-08-2026). Con una unidad daba
                            igual, pero con cinco cucharadas de aceite esta línea ponía «5 ud
                            (10 g)» mientras el chat, para la misma comida, ponía «5 ud (50 g)».
                            Quien miraba Nutrición entendía que tenía 10 g de aceite teniendo 50.
                            Lo que le importa al cliente es cuánto se come en total. */}
                        {porUnidad && (
                            <span className="ml-1 text-[10px] font-normal text-muted-foreground">({num1(Math.round(food.cantidad_g || 0))} g)</span>
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
    // Lo que lleva el DIA de cada familia que se calibra, para el contador de la linea del
    // alimento. Viene de `mealCardProps` y es el mismo para todas las comidas: desde el
    // 13-08 el tramo lo decide el total del dia, no la comida (ver `ContadorFamilia`).
    acumFamilias = null,
    // Abre las favoritas DE ESTA COMIDA (25-08). Si no llega, los botones no se pintan:
    // la tarjeta se usa tambien desde sitios que no tienen ese modal.
    abrirFavoritasDeComida = null,
}) => {
    // ORDENANDO (punto 126): las flechas de subir solo salen cuando se pide.
    const [ordenando, setOrdenando] = React.useState(false);
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
    // reemplace si se pasa». Los otros estados son cortos («Cuadrada», «Te falta») y caben al
    // lado, así que esos no se tocan.
    const estado = estadoDeLaComida(status, target, calculateMealMacros(mealKey), foods.length, isPeri, isLocked);

    // SIN LETRAS Y SIN DECIMALES (punto 115): «52,5P · 10H · 15G» pasa a «53 · 10 · 15».
    // La grasa del peri no cuenta en el método, así que ahí son dos números.
    const lineaObjetivo = isPeri
        ? `${num0(target.P)} · ${num0(target.H)}`
        : `${num0(target.P)} · ${num0(target.H)} · ${num0(target.G)}`;

    // LO QUE TE PIDE ALGO SE VE, LO QUE YA ESTÁ SE APAGA (punto 117, «como en Inicio»).
    // La comida sin crear va en naranja entera -- borde y fondo --, y la que ya está
    // cuadrada baja de intensidad: la lista se recorre buscando lo que falta por hacer.
    const sinCrear = !isLocked && !isPeri && foods.length === 0;
    const yaEsta = !isLocked && estado.color === 'ok';

    // ── LA PUERTA DEL AUTOAJUSTE (Jesús, doc 21-08, apartado 14) ─────────────────────
    //
    // En Automático, tocar una cantidad puede hacer que la app la cambie sola: el cruce
    // de tramo de una familia calibrada (doc 57, F3) recuadra la comida y deja, por
    // ejemplo, las almendras en 20 g cuando el cliente escribió 40. El toast decía QUE
    // se hizo, pero no DONDE se decide lo que él quería. Aquí se apunta la cantidad
    // pedida al tocar; si después la comida vuelve con otra cantidad en ese alimento,
    // sale un recuadro pegado al ingrediente que SE QUEDA hasta que el cliente decida.
    // El botón hace las DOS cosas: pasa la comida a Manual y repone su cantidad.
    //
    // El reajuste en sí vive en NutritionPage (anotarCalibracion -> cuadrarComida
    // silencioso); esta tarjeta es quien recibe el gesto y quien pinta el ingrediente,
    // así que la puerta se monta aquí sin tocar el cálculo ni el reparto.
    const idDe = (f) => f?.alimento_id ?? f?.id ?? f?._id ?? f?.nombre;
    const [ajusteAuto, setAjusteAuto] = React.useState(null);   // { foodId, pedida, ajustada } en gramos
    const peticionPendiente = React.useRef(null);               // { foodId, gramos, confirmada }

    // La cantidad como la lee el cliente: en unidades si el alimento va por unidades.
    const fmtCant = (food, g) => {
        if (esPorUnidad && esPorUnidad(food)) {
            const peso = (pesoUnidad ? pesoUnidad(food) : 100) || 100;
            return `${num1(Math.round((g / peso) * 2) / 2)} ud (${num1(g)} g)`;
        }
        return `${num1(g)} g`;
    };

    // Se apunta lo pedido. Si toca otra cantidad antes de decidir, el recuadro pasa al
    // ingrediente nuevo (se limpia aquí y, si el nuevo gesto también se ajusta, vuelve
    // a salir en él). En Manual no hay autoajuste, así que no hay nada que vigilar.
    const anotarPeticion = (food, gramosPedidos) => {
        setAjusteAuto(null);
        if (mealMode === 'manual' || isPeri || isLocked || !setMealMode || !(gramosPedidos > 0)) {
            peticionPendiente.current = null;
            return;
        }
        peticionPendiente.current = { foodId: idDe(food), gramos: Math.round(gramosPedidos), confirmada: false };
    };

    const updateFoodQuantityVigilada = (mk, idx, delta) => {
        const f = foods[idx];
        if (f) anotarPeticion(f, (f.cantidad_g || 0) + delta);
        updateFoodQuantity(mk, idx, delta);
    };

    const updateFoodQuantityDirectVigilada = (mk, idx, valor) => {
        const f = foods[idx];
        if (f) {
            const n = parseFloat(String(valor).replace(',', '.'));
            const gramos = Number.isFinite(n)
                ? (esPorUnidad && esPorUnidad(f) ? n * ((pesoUnidad ? pesoUnidad(f) : 100) || 100) : n)
                : 0;
            anotarPeticion(f, gramos);
        }
        updateFoodQuantityDirect(mk, idx, valor);
    };

    // La vigilancia: primero hay que VER la cantidad pedida puesta (si no entró tal
    // cual -- tope, mínimo, valor rechazado -- no hay autoajuste que contar); si después
    // cambia sin que el cliente la haya tocado, ese es el reajuste y sale el recuadro.
    React.useEffect(() => {
        const p = peticionPendiente.current;
        if (!p) return;
        const f = foods.find(x => idDe(x) === p.foodId);
        if (!f) { peticionPendiente.current = null; return; }
        const q = Math.round(f.cantidad_g || 0);
        if (!p.confirmada) {
            if (Math.abs(q - p.gramos) < 1) p.confirmada = true;
            else peticionPendiente.current = null;
            return;
        }
        if (Math.abs(q - p.gramos) >= 1) {
            setAjusteAuto({ foodId: p.foodId, pedida: p.gramos, ajustada: q });
            peticionPendiente.current = null;
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- se vigila la lista de alimentos
    }, [foods]);

    // El cliente quiere SU cantidad: la comida pasa a Manual (ahí nadie se la toca) y se
    // repone lo que escribió. Las dos cosas del botón, tal cual las pidió Jesús.
    const quererLaPedida = (food) => {
        if (!ajusteAuto) return;
        const idxActual = foods.findIndex(x => idDe(x) === ajusteAuto.foodId);
        setAjusteAuto(null);
        if (idxActual < 0) return;
        setMealMode(mealKey, 'manual');
        const valor = esPorUnidad && esPorUnidad(food)
            ? String(Math.round((ajusteAuto.pedida / ((pesoUnidad ? pesoUnidad(food) : 100) || 100)) * 2) / 2)
            : String(ajusteAuto.pedida);
        updateFoodQuantityDirect(mealKey, idxActual, valor);
    };

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
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        {/* TODAS CON SU NOMBRE, SIEMPRE (punto 114). Pasaban dos cosas y las
                            dos las contaba él: el nombre se cortaba en el móvil («COMID…»)
                            porque iba a 24 px en mayúsculas compitiendo en la misma línea con
                            el estado y con Automático/Manual; y cuando la comida se pasaba
                            DESAPARECÍA del móvil, porque el texto largo del exceso le quitaba
                            el sitio a propósito, y quedaba solo el cuadrito «C1». Ahora el
                            nombre tiene su línea entera y el estado se ha bajado a la de los
                            números, así que ya no compiten. */}
                        <h3 className={`font-heading font-bold uppercase tracking-wide text-foreground truncate ${denso ? 'text-base' : 'text-[17px] lg:text-lg'}`}>{info.name}</h3>
                        {/* Bloqueada por el volcado: el candado, que no es un estado sino que
                            esa comida ya no juega (ver estadoDeLaComida). */}
                        {isLocked && <Lock className="w-4 h-4 text-amber-500 flex-shrink-0" />}
                    </div>
                    {/* EL OBJETIVO Y EL ESTADO, EN LA MISMA LÍNEA (puntos 115 y 116). Los
                        números, sin letras y sin decimales: «53 · 10 · 15», que el orden ya
                        está escrito arriba. Y el estado con su punto y su palabra, en el
                        vocabulario de la parte 2. */}
                    {/* APILADOS EN EL MÓVIL, en la misma línea a partir de `sm`. Un exceso de
                        dos macros («sobran 264 de hidratos y 40 de grasa») no cabe al lado de
                        nada en 390 px: compartiendo línea aplastaba el objetivo hasta dejarlo
                        en «Objetivo…», que es el mismo problema del nombre una fila más
                        arriba. Cada uno en su línea cabe entero y no se corta ninguno. */}
                    <div className="flex flex-col items-start gap-0.5 mt-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
                        <p className="text-xs text-muted-foreground font-data" data-testid={`objetivo-${mealKey}`}>
                            <span className="mr-1.5">Objetivo</span>
                            {lineaObjetivo}
                        </p>
                        {/* CON LA COMIDA ABIERTA, EL ESTADO NO SE REPITE (punto 120). Dentro
                            están los tres macros uno a uno, con su palabra y su barra: decir
                            además «faltan 20 de proteína» aquí arriba es contar lo mismo dos
                            veces, y peor, porque lo resume. Cerrada sí: ahí es lo único que
                            dice en qué punto está esa comida. */}
                        {!isPeri && !isExpanded && (
                            <span className={`text-xs font-bold flex items-start gap-1.5 sm:text-right ${claseDelEstado(estado.color)}`}
                                data-testid={`estado-comida-${mealKey}`}>
                                <span className="mt-1"><PuntoDeEstado color={estado.color} /></span>
                                {estado.texto}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* El estado ya no vive aquí: se ha bajado a la línea del objetivo, junto al
                nombre, y es el mismo en móvil y en escritorio (punto 116). Estaba suelto en
                esta fila y por eso el nombre se quedaba sin sitio. */}
            {/* Con el día entero desplegado el modo va aquí, en pequeño: la banda de
                "Modo de cálculo" repetida seis veces no cabía, pero esconderla dejaba
                sin Automático/Manual a las comidas que aún no tienen alimentos. */}
            {denso && !isPeri && !isLocked && setMealMode && (
                <div className="inline-flex rounded-lg bg-muted p-0.5 flex-shrink-0" title="Automático: yo te ajusto las cantidades. Manual: las pones tú y lo compensas en el día">
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
        <div className={`surface overflow-hidden ${isPeri ? 'border-l-4 border-l-brand' : ''} ${isLocked ? 'opacity-70' : ''} ${!forceExpanded && !isExpanded ? 'surface-hover' : ''} ${sinCrear ? 'ring-1 ring-pasado/40 bg-pasado/5' : ''} ${yaEsta && !isExpanded ? 'opacity-70' : ''}`} data-testid={`meal-card-${mealKey}`}>
            {/* Header */}
            {forceExpanded ? (
                <div className={`${denso ? 'p-3 sm:p-3.5' : 'p-4 sm:p-5'} flex items-center justify-between gap-3 border-b border-border`}>{HeaderInner}</div>
            ) : (
                <button className="w-full text-left p-3.5 sm:p-4 pb-1.5 flex items-center justify-between gap-3"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}>
                    {HeaderInner}
                </button>
            )}
            {/* Aquí iba OTRA VEZ el objetivo, solo para el teléfono y a 17 px. Ahora está en
                la línea de debajo del nombre, con el estado al lado y en los dos tamaños, así
                que esto era el mismo dato dos veces en la misma tarjeta.
                La palabra «Objetivo» delante se queda (Francisco, 17-08): son el objetivo y
                no lo que lleva puesto, y sin decirlo dos comidas con los mismos números se
                veían idénticas y una decía «te pasas» y la otra «cuadrada». */}

            {isExpanded && (
                <div className={forceExpanded ? (denso ? 'p-3 sm:p-3.5 space-y-3' : 'p-4 sm:p-5 space-y-4') : 'px-3.5 sm:px-4 pb-4 pt-1 space-y-3'}>
                    {/* Modo de cálculo. En denso no va aquí: está en la cabecera de la comida. */}
                    {/* Los números primero, que es a lo que se entra: a mover gramos hasta que
                        cuadre. Los controles van debajo. */}
                    <MealProgressBars mealKey={mealKey} getMealTarget={getMealTarget}
                        calculateMealMacros={calculateMealMacros} hasFoods={foods.length > 0} />

                    {/* «AJUSTE DE CANTIDADES», NO «MODO DE CÁLCULO» (punto 124 del 26-08).
                        Y la etiqueta encima con los dos botones debajo, como Entreno/Descanso.

                        Debajo iba una frase que decía lo único que hay que entender -- «Yo te
                        ajusto las cantidades» -- y estaba escondida en `lg`: en el móvil no se
                        veía nunca. La tapaban dos palabras de jerga. Ahora la jerga se va y la
                        frase se queda, en los dos tamaños. */}
                    {!isPeri && !isLocked && setMealMode && !denso && (
                        <div className="rounded-xl bg-muted/50 px-3.5 py-3">
                            <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Ajuste de cantidades</p>
                            <div className="inline-flex rounded-lg bg-card p-0.5 border border-border mt-1.5">
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode !== 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'auto')} data-testid={`mode-auto-${mealKey}`}>Automático</button>
                                <button className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${mealMode === 'manual' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'manual')} data-testid={`mode-manual-${mealKey}`}>Manual</button>
                            </div>
                            <p className="text-[11px] text-muted-foreground/80 mt-1.5" data-testid={`ajuste-explicacion-${mealKey}`}>
                                {mealMode === 'manual' ? 'Las pones tú y lo compensas en el día' : 'Yo te ajusto las cantidades'}
                            </p>
                        </div>
                    )}

                    {isLocked && (
                        <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/25 rounded-xl px-3 py-2">
                            <Lock className="w-3.5 h-3.5 shrink-0" />
                            <span>Bloqueada: los macros del día están volcados en otra comida. Deshaz el volcado para editarla.</span>
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
                            <div className={`grid gap-2 ${abrirFavoritasDeComida ? 'grid-cols-3' : 'grid-cols-2'}`}>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'normal' })} data-testid={`build-meal-${mealKey}`}>
                                    <Wrench className="w-4 h-4" /> Lo hago yo
                                </button>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                    <RefreshCw className="w-4 h-4" /> Repetir
                                </button>
                                {/* Traer una comida guardada, sin arrastrar el día entero. */}
                                {abrirFavoritasDeComida && (
                                    <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                        onClick={() => abrirFavoritasDeComida(mealKey)} data-testid={`fav-comida-vacia-${mealKey}`}>
                                        <Star className="w-4 h-4" /> Favoritas
                                    </button>
                                )}
                            </div>
                        </div>
                        )
                    )}
                    {/* EL INTRA Y EL POST NO SE COMPORTAN IGUAL (Francisco, 25-08).
                        En los dos se ha quitado el botón de menús: la biblioteca son comidas
                        de clientes y en el peri no pinta nada.
                        - INTRA: «Prepárame el intra» abre el constructor con sus categorías
                          ya puestas, así que la lista sale sola y en el orden del método
                          (MAP primero, luego la ciclodextrina). Ahí sí prepara.
                        - POST: se monta como una comida normal. Tenía el mismo botón y era
                          mentira: el post abre sin categorías y lo primero que salía era
                          «Selecciona una categoría arriba», o sea el buscador de siempre.
                          Antes que prometer lo que no hace, se llama por su nombre.
                        «Lo hago yo» abre igualmente en modo post, que es lo que hace valer
                        sus reglas (universo de la categoría 25 y sin objetivo de grasa). */}
                    {foods.length === 0 && isPeri && !isLocked && (
                        mealKey === 'Intra' ? (
                            <div className="space-y-2">
                                <button className={`btn-brand flex items-center justify-center gap-2 uppercase tracking-wide ${denso ? 'h-11 text-sm w-full' : 'w-full h-12'}`}
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'intra' })}
                                    data-testid={`build-peri-${mealKey}`}>
                                    <Zap className={denso ? 'w-4 h-4' : 'w-5 h-5'} /> Prepárame el intra
                                </button>
                                <div className={`grid gap-2 ${abrirFavoritasDeComida ? 'grid-cols-2' : 'grid-cols-1'}`}>
                                    <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                        onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                        <RefreshCw className="w-4 h-4" /> Repetir
                                    </button>
                                    {abrirFavoritasDeComida && (
                                        <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                            onClick={() => abrirFavoritasDeComida(mealKey)} data-testid={`fav-comida-vacia-${mealKey}`}>
                                            <Star className="w-4 h-4" /> Favoritas
                                        </button>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className={`grid gap-2 ${abrirFavoritasDeComida ? 'grid-cols-3' : 'grid-cols-2'}`}>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'post' })}
                                    data-testid={`build-meal-${mealKey}`}>
                                    <Wrench className="w-4 h-4" /> Lo hago yo
                                </button>
                                <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                    onClick={() => openRepeatModal(mealKey)} data-testid={`repeat-meal-${mealKey}`}>
                                    <RefreshCw className="w-4 h-4" /> Repetir
                                </button>
                                {abrirFavoritasDeComida && (
                                    <button className="btn-outline-brand h-11 flex items-center justify-center gap-1.5 text-sm"
                                        onClick={() => abrirFavoritasDeComida(mealKey)} data-testid={`fav-comida-vacia-${mealKey}`}>
                                        <Star className="w-4 h-4" /> Favoritas
                                    </button>
                                )}
                            </div>
                        )
                    )}

                    {/* Ingredients */}
                    {foods.length > 0 && (
                        <div className="space-y-3">
                            <div>
                                {/* «−/+ = gramos» Y YA (punto 127). Ponía «↑ = prioridad», y
                                    prioridad hace pensar que Cuadrar reparte por ese orden. No
                                    es verdad: la flecha solo coloca el alimento más arriba. */}
                                <div className="flex items-center justify-between mb-2">
                                    <p className="caption">Ingredientes</p>
                                    <span className="text-[11px] text-muted-foreground">−/+ = gramos</span>
                                </div>
                                {/* ORDENANDO (punto 126): las flechas solo aparecen cuando se
                                    pide, y mientras tanto hay una barra que dice qué está
                                    pasando y cómo salir. Así cada alimento recupera el ancho
                                    que ocupaba la flecha, que es lo que hacía que «Fiambre de
                                    pechuga de pavo de buena calidad (más del 85 %)» cayera a
                                    dos líneas. */}
                                {ordenando && (
                                    <div className="flex items-center justify-between gap-3 rounded-xl bg-brand/10 border border-brand/40 px-3 py-2 mb-2"
                                        data-testid={`ordenando-${mealKey}`}>
                                        <span className="text-xs font-bold text-brand">Ordena los alimentos</span>
                                        <button onClick={() => setOrdenando(false)} data-testid={`ordenar-listo-${mealKey}`}
                                            className="text-xs font-bold text-brand hover:underline">Listo</button>
                                    </div>
                                )}
                                <div className="space-y-1.5">
                                    {foods.map((food, idx) => (
                                        <React.Fragment key={idx}>
                                            <IngredientRow food={food} idx={idx} mealKey={mealKey} isLocked={isLocked}
                                                isEditing={editingQuantity.mealKey === mealKey && editingQuantity.foodIndex === idx}
                                                increment={getQuantityIncrement(food)}
                                                moveFoodUp={moveFoodUp} removeFood={removeFood}
                                                updateFoodQuantity={updateFoodQuantityVigilada} updateFoodQuantityDirect={updateFoodQuantityDirectVigilada}
                                                setEditingQuantity={setEditingQuantity} formatFoodQuantity={formatFoodQuantity}
                                                esPorUnidad={esPorUnidad} pesoUnidad={pesoUnidad}
                                                acumFamilias={acumFamilias} ordenando={ordenando} />
                                            {/* LA PUERTA: el recuadro del autoajuste, pegado al ingrediente tocado.
                                                No es un toast: se queda hasta que el cliente decida, con los números
                                                reales de lo que pidió y lo que la app dejó (doc 21-08, apartado 14). */}
                                            {ajusteAuto && idDe(food) === ajusteAuto.foodId && (
                                                <div className="rounded-xl border border-border bg-muted/50 px-3 py-2.5 space-y-2"
                                                    data-testid={`ajuste-auto-${mealKey}-${idx}`}>
                                                    <p className="text-[13px] leading-snug text-foreground">
                                                        Te he ajustado {food.nombre} a <span className="font-bold">{fmtCant(food, ajusteAuto.ajustada)}</span> para
                                                        que la comida cuadre. Si quieres los {fmtCant(food, ajusteAuto.pedida)}, lo compensas en el resto del día.
                                                    </p>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <button className="btn-brand px-3 py-1.5 text-xs rounded-lg"
                                                            onClick={() => quererLaPedida(food)}
                                                            data-testid={`ajuste-auto-quiero-${mealKey}`}>
                                                            Los quiero en {fmtCant(food, ajusteAuto.pedida)}
                                                        </button>
                                                        <button className="px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                                                            onClick={() => setAjusteAuto(null)}
                                                            data-testid={`ajuste-auto-dejar-${mealKey}`}>
                                                            Dejarlo en {fmtCant(food, ajusteAuto.ajustada)}
                                                        </button>
                                                    </div>
                                                </div>
                                            )}
                                        </React.Fragment>
                                    ))}
                                </div>
                            </div>
                            {/* CUADRAR, ANCHO Y EXPLICADO (punto 125). Era un botón pequeño
                                perdido entre otros cuatro, y lo que hace lo contaba un
                                `title`: en el móvil no hay ratón, así que ningún cliente lo
                                había leído nunca. La frase baja debajo del botón, visible.
                                (La que él escribe no existía: la de antes hablaba de mínimos.) */}
                            {!isLocked && onCuadrar && (
                                <div>
                                    <button onClick={() => onCuadrar(mealKey)} data-testid={`cuadrar-${mealKey}`}
                                        className="btn-brand w-full py-3 rounded-xl text-sm font-bold">
                                        Cuadrar
                                    </button>
                                    <p className="text-xs text-muted-foreground text-center mt-1.5">
                                        Te ajusto las cantidades sin pasarme de tus macros.
                                    </p>
                                </div>
                            )}
                            {/* Y LO DEMÁS, DENTRO DEL «···» (punto 126). Estaban los cinco a la
                                vista -- Automático/Manual, ver detalles, Cuadrar, la estrella y
                                Vaciar -- compitiendo con lo único que se viene a hacer aquí. */}
                            <div className="flex items-center gap-2">
                                <button className="flex-1 py-2.5 rounded-xl border border-dashed border-border text-brand font-semibold text-sm hover:bg-brand/5 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-1.5 transition-colors" disabled={isLocked} onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}>
                                    <Plus className="w-4 h-4" /> Añadir ingrediente
                                </button>
                                {!isLocked && (
                                    <MenuDeLaPantalla etiqueta="Más opciones de esta comida" opciones={[
                                        foods.length > 1 && { id: `ordenar-${mealKey}`, texto: 'Ordenar los alimentos',
                                            icono: ArrowUpDown, al: () => setOrdenando(true) },
                                        // Guardar SOLO esta comida (25-08). Antes había que
                                        // guardar el día entero y borrar lo que sobraba.
                                        abrirFavoritasDeComida && { id: `fav-${mealKey}`, texto: 'Guardar como favorita',
                                            icono: Star, al: () => abrirFavoritasDeComida(mealKey) },
                                        { id: `vaciar-${mealKey}`, texto: 'Vaciar la comida', icono: Trash2,
                                            peligro: true, al: () => clearMeal(mealKey) },
                                    ]} />
                                )}
                            </div>
                        </div>
                    )}

                    {canVolcar && onVolcar && (
                        /* El botón dice QUÉ HACE (punto 10 del 23-08: «no dice qué hace»):
                           el tooltip no existe en el teléfono, así que la explicación va
                           debajo, visible. */
                        <div className="py-1.5">
                            <button
                                className="w-full text-xs text-muted-foreground hover:text-brand flex items-center justify-center gap-1.5 transition-colors"
                                onClick={() => onVolcar(mealKey)}
                            >
                                <Download className="w-3.5 h-3.5" /> Volcar los macros aquí
                            </button>
                            <p className="text-[11px] text-muted-foreground/70 text-center mt-0.5">
                                Mete en esta comida todo lo que te queda del día y bloquea las demás.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default MealCard;
