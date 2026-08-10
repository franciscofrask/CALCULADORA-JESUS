/**
 * DayHeader - La cabecera del día.
 *
 * Antes eran tres bloques con marco: el resumen del día, una tarjeta con la fecha y el
 * tipo de día, y otra con tres desplegables siempre desplegados. Tres cajas para decir
 * cuatro cosas, y las tres compitiendo por la atención antes de llegar a las comidas,
 * que es a lo que se viene.
 *
 * Ahora es una sola zona sin marcos, separada por líneas finas:
 *   - la fecha y el tipo de día en una línea,
 *   - la configuración resumida en texto ("4 comidas · tras comida 2 · intra + post"),
 *     que se despliega solo cuando se quiere cambiar algo,
 *   - los tres macros del día en filas con su nombre completo,
 *   - el peri y el detalle por comida, en pequeño.
 */
import React from 'react';
import { Calendar, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import ConfigSection, { MOMENTO_OPTIONS, PERI_OPTIONS } from './ConfigSection';
import { DayDetailTable, StatusDot } from './DaySummary';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

// "4 comidas · tras comida 2 · intra + post": lo que hay configurado, en una línea, para
// no tener tres desplegables ocupando sitio cuando casi nunca se tocan.
const resumenConfig = ({ numComidas, tipoDia, momentoEntreno, opcionPeri }) => {
    const partes = [numComidas === 1 ? 'comida única' : `${numComidas} comidas`];
    if (tipoDia === 'entrenamiento' && numComidas !== 1) {
        partes.push(momentoEntreno === 0
            ? 'en ayunas'
            : (MOMENTO_OPTIONS.find(o => o.value === momentoEntreno)?.label || '').replace('Después de Comida', 'tras comida'));
        partes.push((PERI_OPTIONS.find(o => o.value === opcionPeri)?.label || '').toLowerCase());
    }
    return partes.filter(Boolean).join(' · ');
};

const DayHeader = ({
    // fecha
    currentDate, formatDate, changeDate, setCalendarOpen, diaSinMarcar,
    // tipo de día y configuración
    tipoDia, handleSetTipoDia,
    numComidas, setNumComidas, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri, singleMeal,
    configExpanded, setConfigExpanded,
    // macros
    dayMacros, dayTarget, servedPeriP, servedPeriH, servedPeriG = 0, totalPeriP, totalPeriH,
    getDayStatus,
    // detalle
    summaryExpanded, setSummaryExpanded,
    mealOrder, mealInfo, calculateMealMacros, getMealStatus,
}) => {
    // El peri lleva su propia cuenta: ni el total del día ni su objetivo lo incluyen.
    const mainP = dayMacros.P - servedPeriP;
    const mainH = dayMacros.H - servedPeriH;
    const mainG = dayMacros.G - servedPeriG;
    // Objetivo de las COMIDAS = total del día menos el peri que se cuenta aparte. No vale
    // usar P_entreno: en `sin_peri` (y en `solo_intra`) parte del presupuesto de perientreno
    // se reparte ENTRE LAS COMIDAS, así que los objetivos por comida suman más que los macros
    // de entreno. La cabecera pedía de menos justo ese peri repartido (30 P y 16 H en el caso
    // que lo destapó): con las cuatro comidas cuadradas el día decía "te pasas", y como nunca
    // quedaba UNA sola comida sin cuadrar tampoco aparecía "Volcar macros aquí".
    const tgtP = (dayTarget.P_total ?? 0) - (totalPeriP || 0);
    const tgtH = (dayTarget.H_total ?? 0) - (totalPeriH || 0);
    const tgtG = dayTarget.G_total ?? 0;   // el objetivo del peri no lleva grasa
    const dayStatus = getDayStatus();
    const hayPeri = tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri';

    const macros = [
        { key: 'P', label: 'Proteína', val: mainP, tgt: tgtP || 0, color: MACRO.P },
        { key: 'H', label: 'Hidratos', val: mainH, tgt: tgtH || 0, color: MACRO.H },
        { key: 'G', label: 'Grasa', val: mainG, tgt: tgtG || 0, color: MACRO.G },
    ];

    return (
        <section data-testid="day-summary" className="mt-4">
            {/* Fecha, tipo de día y configuración resumida */}
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
                {/* `flex-wrap`, y no es cosmética: sin ella esta fila no parte nunca, y el
                    aviso de «¿Este día entrenas o descansas?» -- que lleva `w-full` para
                    caer a su línea -- se salía por la derecha de la pantalla en 390 px. Se
                    leía «¿Este día entrenas o descansa... Tus macro... cambian.», cortado.
                    Justo el aviso que existe para que no se coma 60 g de hidratos de más. */}
                <div className="flex flex-wrap items-center gap-2 min-w-0">
                    <button onClick={() => changeDate(-1)} aria-label="Día anterior"
                        className="w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-brand hover:bg-brand/10 transition-colors flex-shrink-0">
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <button onClick={() => setCalendarOpen(true)} data-testid="open-calendar-btn"
                        className="flex items-center gap-2 min-w-0 h-9 px-2 rounded-xl hover:bg-muted/60 transition-colors">
                        <Calendar className="w-4 h-4 text-brand flex-shrink-0" />
                        <span className="font-heading font-bold text-lg text-foreground capitalize truncate">{formatDate(currentDate)}</span>
                    </button>
                    <button onClick={() => changeDate(1)} aria-label="Día siguiente"
                        className="w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-brand hover:bg-brand/10 transition-colors flex-shrink-0">
                        <ChevronRight className="w-5 h-5" />
                    </button>

                    {/* Si nadie ha dicho qué día es, el selector se marca (punto 4.17): la app
                        abre en «Entreno» porque hay que abrir en algo, pero en un día de
                        descanso eso son 60 g de hidratos y 45 de perientreno de más. Medido en
                        producción: de 14.027 días guardados, 2 dicen descanso. */}
                    <div className={`inline-flex rounded-xl bg-muted p-0.5 ml-1 flex-shrink-0 ${diaSinMarcar ? 'ring-2 ring-brand ring-offset-2 ring-offset-background' : ''}`}>
                        <button data-testid="tipo-dia-entrenamiento" onClick={() => handleSetTipoDia('entrenamiento')}
                            className={`px-3 h-8 rounded-lg text-xs font-bold transition-colors ${tipoDia === 'entrenamiento' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}>
                            Entreno
                        </button>
                        <button data-testid="tipo-dia-descanso" onClick={() => handleSetTipoDia('descanso')}
                            className={`px-3 h-8 rounded-lg text-xs font-bold transition-colors ${tipoDia === 'descanso' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}>
                            Descanso
                        </button>
                    </div>
                    {/* El aviso, solo en escritorio. En el teléfono la frase ocupaba dos
                        líneas enteras justo debajo del conmutador, que es lo que la propia
                        frase te manda mirar. El aviso NO se pierde: el conmutador se queda
                        con su aro naranja mientras el día esté sin marcar, que es la misma
                        señal en el sitio donde se actúa (punto 4.17). */}
                    {diaSinMarcar && (
                        <p className="hidden lg:block text-xs text-brand font-semibold w-full sm:w-auto" data-testid="dia-sin-marcar">
                            ¿Este día entrenas o descansas? Tus macros cambian.
                        </p>
                    )}

                    {dayStatus === 'cuadrado' && <span className="px-2 py-0.5 bg-emerald-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Cuadrado</span>}
                    {dayStatus === 'sobra' && <span className="px-2 py-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Te pasas</span>}
                </div>

            </div>

            {/* LO QUE LE QUEDA POR COMER, no lo que lleva (documento del 10-08, pantallas
                8, 9 y 10). «Es la pregunta real a las diez de la noche. Nadie abre la app
                para saber lo que ya se ha comido.»

                Aquí había tres barras con «120 / 190», que obligan a restar de cabeza tres
                veces para saber lo único que hace falta saber. Ahora el número grande es lo
                que falta, y debajo, pequeño, sigue estando de cuánto era el total, que es lo
                que da la referencia.

                Tres estados, con su titular, que es lo que el documento echaba en falta:
                la app no distinguía «sin empezar» de «a medias» ni de «terminado». */}
            {(() => {
                const nadaPuesto = macros.every(m => m.val === 0);
                const pasado = macros.some(m => m.tgt > 0 && m.val > m.tgt + 4);
                const cuadrado = !nadaPuesto && macros.every(m => m.tgt > 0 && Math.abs(m.tgt - m.val) < 4);
                const titular = cuadrado ? 'Día cuadrado'
                    : nadaPuesto ? 'Hoy tienes que comer'
                    : pasado ? 'Te has pasado' : 'Te queda por comer';
                return (
                    <div className="mt-5" data-testid="dia-resumen">
                        <p className={`text-sm font-bold ${cuadrado ? 'text-emerald-600 dark:text-emerald-400' : pasado ? 'text-red-500' : 'text-muted-foreground'}`}
                            data-testid="dia-titular">{titular}</p>
                        <div className="grid grid-cols-3 gap-3 max-w-md mt-2">
                            {macros.map(({ key, label, val, tgt, color }) => {
                                const over = tgt > 0 && val > tgt + 4;
                                // Cuadrado o pasado, el número que importa es el total, no un
                                // «te quedan 0» repetido tres veces.
                                const grande = (cuadrado || over) ? Math.round(val) : Math.max(0, Math.round(tgt - val));
                                return (
                                    // Centrado dentro de su columna, como en Inicio: los tres
                                    // números tienen anchos distintos (235, 60) y alineados a
                                    // la izquierda el bloque se ve descolgado.
                                    <div key={key} className="text-center" data-testid={`dia-${key}`}>
                                        <p className="font-data font-bold leading-none text-foreground text-[30px] sm:text-[34px]">{grande}</p>
                                        <p className="text-sm font-bold mt-1" style={{ color: over ? '#EF4444' : color }}>{label}</p>
                                        <p className="text-xs text-muted-foreground font-data">
                                            {cuadrado || over ? `de ${tgt.toFixed(0)}` : `de ${tgt.toFixed(0)} en total`}
                                        </p>
                                    </div>
                                );
                            })}
                        </div>
                        {/* LA CONFIGURACIÓN DEL DÍA, DEBAJO DE LOS NÚMEROS y en una línea
                            (documento del 10-08, pantalla 9): «se toca una vez al mes;
                            verla, se ve siempre». Estaba arriba, al lado de la fecha,
                            compitiendo por el sitio con el conmutador de entreno. */}
                        <button onClick={() => setConfigExpanded(!configExpanded)} data-testid="toggle-config"
                            className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                            title="Cambiar comidas, horario de entreno o perientreno">
                            {resumenConfig({ numComidas, tipoDia, momentoEntreno, opcionPeri })}
                            {configExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                        {/* Y se despliega JUSTO DEBAJO del botón que lo abre. Antes el panel
                            salía arriba del todo y el botón estaba en otra parte: se pulsaba
                            y no parecía que hubiera pasado nada. */}
                        {configExpanded && (
                            <div className="flex flex-col sm:flex-row sm:items-end gap-4 mt-3" data-testid="config-section">
                                <ConfigSection
                                    inline
                                    tipoDia={tipoDia}
                                    momentoEntreno={momentoEntreno}
                                    setMomentoEntreno={setMomentoEntreno}
                                    opcionPeri={opcionPeri}
                                    setOpcionPeri={setOpcionPeri}
                                    numComidas={numComidas}
                                    setNumComidas={setNumComidas}
                                    singleMeal={singleMeal}
                                />
                            </div>
                        )}
                    </div>
                );
            })()}

            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                {/* «Perientreno», nunca «peri» (punto 4.18): el bloque se llamaba de tres
                    maneras distintas por la app y el abreviado no lo entiende nadie que no
                    lleve meses aquí. */}
                {hayPeri && (
                    <span className="text-[11px] text-muted-foreground font-data">
                        perientreno {servedPeriP.toFixed(0)}/{totalPeriP.toFixed(0)}P · {servedPeriH.toFixed(0)}/{totalPeriH.toFixed(0)}H
                    </span>
                )}
                {/* «Ver detalle» y su tabla, fuera del teléfono. Lo que despliega es el
                    reparto del día comida a comida, y en móvil eso mismo está justo debajo:
                    la lista de comidas con su objetivo. Era la tercera vez que se decía lo
                    mismo en la misma pantalla. En escritorio se queda, donde la tabla se lee
                    de un vistazo y no obliga a bajar. */}
                <button onClick={() => setSummaryExpanded(!summaryExpanded)}
                    className="hidden lg:flex text-[11px] text-muted-foreground hover:text-foreground transition-colors items-center gap-1">
                    {summaryExpanded ? 'ocultar detalle' : 'ver detalle'}
                    {summaryExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>

                {/* Cómo va cada comida, de un vistazo y sin bajar: en la vista de todo
                    seguido es lo único que dice el estado del día sin recorrerlo entero. */}
                {/* Los puntos de C1 · Intra · C2... tampoco salen en el teléfono: ahí las
                    comidas están unas líneas más abajo, cada una con su estado y su nombre
                    completo, así que esto era el mismo dato dos veces y en abreviado. En
                    escritorio sí vale, porque con la vista de todo seguido es lo único que
                    dice cómo va el día sin recorrerlo entero. */}
                <span className="hidden lg:flex items-center gap-2.5 flex-wrap ml-auto">
                    {mealOrder.map((mealKey) => (
                        <span key={mealKey} className="flex items-center gap-1">
                            <StatusDot status={getMealStatus(mealKey)} />
                            <span className="text-[11px] text-muted-foreground">{mealInfo[mealKey].shortName}</span>
                        </span>
                    ))}
                </span>
            </div>

            {summaryExpanded && (
                <div className="mt-3 max-w-2xl hidden lg:block">
                    <DayDetailTable
                        mealOrder={mealOrder} mealInfo={mealInfo} calculateMealMacros={calculateMealMacros}
                        tipoDia={tipoDia} opcionPeri={opcionPeri}
                        mainP={mainP} mainH={mainH} mainG={mainG}
                        tgtP={tgtP} tgtH={tgtH} tgtG={tgtG}
                        totalPeriP={totalPeriP} totalPeriH={totalPeriH}
                    />
                </div>
            )}
        </section>
    );
};

export default DayHeader;
