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
    currentDate, formatDate, changeDate, setCalendarOpen,
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
    const tgtP = dayTarget.P_entreno ?? dayTarget.P_total;
    const tgtH = dayTarget.H_entreno ?? dayTarget.H_total;
    const tgtG = dayTarget.G_entreno ?? dayTarget.G_total;
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
                <div className="flex items-center gap-2 min-w-0">
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

                    <div className="inline-flex rounded-xl bg-muted p-0.5 ml-1 flex-shrink-0">
                        <button data-testid="tipo-dia-entrenamiento" onClick={() => handleSetTipoDia('entrenamiento')}
                            className={`px-3 h-8 rounded-lg text-xs font-bold transition-colors ${tipoDia === 'entrenamiento' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}>
                            Entreno
                        </button>
                        <button data-testid="tipo-dia-descanso" onClick={() => handleSetTipoDia('descanso')}
                            className={`px-3 h-8 rounded-lg text-xs font-bold transition-colors ${tipoDia === 'descanso' ? 'bg-brand text-white' : 'text-muted-foreground hover:text-foreground'}`}>
                            Descanso
                        </button>
                    </div>

                    {dayStatus === 'cuadrado' && <span className="px-2 py-0.5 bg-emerald-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Cuadrado</span>}
                    {dayStatus === 'sobra' && <span className="px-2 py-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wide">Te pasas</span>}
                </div>

                <button onClick={() => setConfigExpanded(!configExpanded)} data-testid="toggle-config"
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    title="Cambiar comidas, horario de entreno o perientreno">
                    {resumenConfig({ numComidas, tipoDia, momentoEntreno, opcionPeri })}
                    {configExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
            </div>

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

            {/* Macros del día: siempre los del método, que es lo que reparte el día */}
            <div className="mt-5 max-w-2xl space-y-2">
                {macros.map(({ key, label, val, tgt, color }) => {
                    const over = tgt > 0 && val > tgt + 4;
                    return (
                        <div key={key} className="flex items-center gap-3">
                            <span className="text-[13px] text-muted-foreground w-[64px] flex-shrink-0">{label}</span>
                            <span className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                                <span className="block h-full rounded-full transition-all duration-300"
                                    style={{ width: `${tgt > 0 ? Math.min((val / tgt) * 100, 100) : 0}%`, backgroundColor: over ? '#EF4444' : color }} />
                            </span>
                            <span className={`font-data text-[13px] text-right w-[92px] flex-shrink-0 ${over ? 'text-red-500 font-bold' : 'text-foreground'}`}>
                                {val.toFixed(0)} <span className="text-muted-foreground">/ {tgt.toFixed(0)}</span>
                            </span>
                        </div>
                    );
                })}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                {hayPeri && (
                    <span className="text-[11px] text-muted-foreground font-data">
                        peri {servedPeriP.toFixed(0)}/{totalPeriP.toFixed(0)}P · {servedPeriH.toFixed(0)}/{totalPeriH.toFixed(0)}H
                    </span>
                )}
                <button onClick={() => setSummaryExpanded(!summaryExpanded)}
                    className="text-[11px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                    {summaryExpanded ? 'ocultar detalle' : 'ver detalle'}
                    {summaryExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>

                {/* Cómo va cada comida, de un vistazo y sin bajar: en la vista de todo
                    seguido es lo único que dice el estado del día sin recorrerlo entero. */}
                <span className="flex items-center gap-2.5 flex-wrap ml-auto">
                    {mealOrder.map((mealKey) => (
                        <span key={mealKey} className="flex items-center gap-1">
                            <StatusDot status={getMealStatus(mealKey)} />
                            <span className="text-[11px] text-muted-foreground">{mealInfo[mealKey].shortName}</span>
                        </span>
                    ))}
                </span>
            </div>

            {summaryExpanded && (
                <div className="mt-3 max-w-2xl">
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
