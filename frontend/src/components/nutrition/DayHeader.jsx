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
import ConfigSection from './ConfigSection';
import { DayDetailTable, StatusDot } from './DaySummary';
import { leerMacro, claseDelMacro, fondoDelMacro, llevaPunto } from '../../lib/estadoDelMacro';


const DayHeader = ({
    // fecha
    currentDate, formatDate, changeDate, setCalendarOpen, diaSinMarcar,
    // tipo de día y configuración
    tipoDia, handleSetTipoDia,
    numComidas, setNumComidas, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri, singleMeal,
    configExpanded, setConfigExpanded,
    // macros
    dayMacros, dayTarget, servedPeriP, servedPeriH, servedPeriG = 0, totalPeriP, totalPeriH,
    // detalle
    summaryExpanded, setSummaryExpanded,
    mealOrder, mealInfo, calculateMealMacros, getMealStatus,
}) => {
    // La parte de las COMIDAS: al día se le quita el peri, que lleva su propia cuenta
    // (el chip de abajo y las filas del detalle). De aquí sale el ESTADO del día.
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

    // LOS NÚMEROS GRANDES ENSEÑAN EL DÍA ENTERO, PERI INCLUIDO (doc 21-08, apartado 11):
    // arriba un solo objetivo y un solo servido, con el perientreno dentro, en los cuatro
    // modos de peri. El reparto interno no cambia: `val`/`tgt` siguen siendo los de las
    // comidas y de ahí sale el estado (el mismo criterio que getDayStatus); `valDia`/`tgtDia`
    // son solo lo que se pinta. El chip del perientreno sigue debajo con su propia cuenta.
    //
    // LA GRASA VA SIN EL PERI, Y ESE ERA EL DESCUADRE DEL PUNTO 178 (27-08): «el mismo día,
    // la grasa dice 40 aquí y 41 en Nutrición».
    // Aquí ponía `valDia: dayMacros.G`, que SÍ lleva la grasa del intra y del post, y lo
    // comparaba contra `tgtDia: tgtG`, que NO la lleva (en el método el objetivo del peri no
    // tiene grasa). Creado y objetivo medían cosas distintas en la misma columna. Y el Inicio
    // no tenía el fallo: allí lo montado sale de `servido_comidas`, que el servidor cuenta
    // sin el peri. Dos pantallas, dos números, y el bueno era el del Inicio.
    // La línea de arriba decía «en grasa día y comidas coinciden: el peri no lleva grasa»:
    // es una suposición, y en producción hay 27 días guardados que la desmienten (batidos
    // con 2 a 4 g de grasa en el intra o el post). `mainG` ya era el número bueno -- de él
    // sale el estado del día -- y solo se pintaba el otro.
    const macros = [
        { key: 'P', label: 'Proteína', val: mainP, tgt: tgtP || 0, valDia: dayMacros.P, tgtDia: dayTarget.P_total ?? 0 },
        { key: 'H', label: 'Hidratos', val: mainH, tgt: tgtH || 0, valDia: dayMacros.H, tgtDia: dayTarget.H_total ?? 0 },
        { key: 'G', label: 'Grasa', val: mainG, tgt: tgtG || 0, valDia: mainG, tgtDia: tgtG || 0 },
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
                        {/* Sin `capitalize`: desde la parte 6 la fecha es «Jueves, 27 de
                            agosto» y esa clase pone mayúscula en CADA palabra («27 De
                            Agosto»). La primera letra ya la pone `formatDate`, que es la
                            única que va en mayúscula. */}
                        <span className="font-heading font-bold text-lg text-foreground truncate">{formatDate(currentDate)}</span>
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
                    {/* La frase «¿Este día entrenas o descansas?» se quitó (punto 8 del doc
                        del 23-08: fuera, y nada en su lugar). El aviso de día sin marcar
                        sigue siendo el aro naranja del conmutador, en el sitio donde se
                        actúa (punto 4.17). */}

                    {/* AQUÍ IBAN LOS DISTINTIVOS «CUADRADO» Y «TE PASAS», y se han ido con
                        el titular (Francisco, 26-08). Existían porque el titular era solo de
                        móvil y en escritorio había que decir el estado del día de alguna
                        manera. Ahora lo dicen los tres puntos y las tres palabras, en los dos
                        tamaños, así que esto era el mismo dato otra vez y con otro rojo. */}
                </div>

                {/* El resumen de la configuración se ha ido al «···» de la cabecera
                    (punto 113: «se queda, dentro del ···»). Estaba aquí en escritorio y en
                    otro botón gemelo debajo de los números en el móvil: dos sitios para el
                    mismo botón, y ninguno de los dos era donde están las demás acciones. */}
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
                return (
                    <div className="mt-5" data-testid="dia-resumen">
                        {/* UN SOLO NÚMERO Y SIEMPRE EL MISMO: LO QUE LLEVAS CREADO
                            (puntos 105 a 107 del artifact del 25-08).

                            «Inicio es cómo vas. Nutrición es lo que llevas creado. Cada
                            pantalla enseña un solo número y siempre el mismo.»

                            Hasta hoy este bloque cambiaba de criterio SOLO, y de dos maneras
                            a la vez. El titular rotaba entre cuatro frases -- «Día cuadrado»,
                            «Hoy tienes que comer», «Te has pasado», «Te queda por comer hoy»
                            -- y, peor, EL NÚMERO cambiaba con él: era lo que FALTA mientras
                            ibas a medias y pasaba a ser lo SERVIDO al cuadrar o al pasarte.
                            El mismo hueco, dos magnitudes distintas, y nadie te decía cuál
                            estabas mirando. Y en escritorio no era ninguna de las dos: eran
                            tres barras de 1 px con «Te faltan N de X», un tercer criterio.

                            Ahora es siempre lo creado, en los dos tamaños, y el estado lo
                            dicen el punto, la palabra y la barra, con el mismo motor y el
                            mismo margen de 4 g que el Inicio (lib/estadoDelMacro): «el color,
                            el margen de 4 y las palabras son los mismos de la parte 2». */}
                        <div className="grid grid-cols-3 gap-3 max-w-md">
                            {macros.map(({ key, label, valDia, tgtDia }) => {
                                const creado = Math.round(valDia);
                                const lectura = leerMacro({ vista: 'dieta', hay: valDia, objetivo: tgtDia });
                                return (
                                    // Centrado dentro de su columna, como en Inicio: los tres
                                    // números tienen anchos distintos (235, 60) y alineados a
                                    // la izquierda el bloque se ve descolgado.
                                    <div key={key} className="text-center" data-testid={`dia-${key}`}>
                                        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center justify-center gap-1">
                                            {label}
                                            {llevaPunto(lectura.color) && (
                                                <span data-testid={`dia-punto-${key}`}
                                                    className={`w-1.5 h-1.5 rounded-full ${fondoDelMacro(lectura.color)}`} />
                                            )}
                                        </p>
                                        <p className="numero-grande font-data leading-none text-[34px] sm:text-[40px] mt-1.5 text-foreground">
                                            {creado}
                                        </p>
                                        <p data-testid={`dia-palabra-${key}`}
                                            className={`text-xs mt-1 ${claseDelMacro(lectura.color)}`}>
                                            {lectura.palabra}
                                        </p>
                                        {lectura.barra && (
                                            <div className="h-1 rounded-full bg-muted mt-1.5 overflow-hidden">
                                                <div data-testid={`dia-barra-${key}`}
                                                    className={`h-full rounded-full ${fondoDelMacro(lectura.barra.color)}`}
                                                    style={{ width: `${lectura.barra.largo}%` }} />
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                        <p className="text-xs text-muted-foreground mt-3 max-w-md text-center"
                            data-testid="dia-pie">
                            Lo que llevas creado
                        </p>
                        {/* AQUÍ IBA «YA TIENES CUBIERTOS LOS HIDRATOS Y LA GRASA», y se ha
                            ido (punto 109): «los dos números ya salen en verde y con cuadrado
                            debajo. Es decirlo dos veces».

                            Nació cuando arriba solo se decía lo que falta y no lo que ya está
                            («saber lo que ya está cubierto evita ponerse a buscar proteína
                            cuando lo que falta son hidratos», Jesús, 11-08). Desde que cada
                            macro lleva su punto y su palabra, eso ya está dicho donde se mira. */}

                    </div>
                );
            })()}

            {/* AQUÍ IBAN LAS TRES BARRAS DE ESCRITORIO, y se han ido (puntos 105 a 107).
                Decían «Te faltan 94 de 120», o sea LO QUE FALTA, mientras los números del
                teléfono decían unas veces lo que falta y otras lo servido: tres criterios
                para el mismo dato en la misma pantalla, según el tamaño de la ventana y
                según cómo fuera el día. Ahora el bloque de números de arriba es el mismo en
                los dos tamaños y dice siempre lo mismo: lo que llevas creado. */}

            {/* OBJETIVOS PROVISIONALES (tarea 1.4). Los macros del día se calcularon con un
                perfil con huecos o con datos imposibles (edad 5, estatura de 1 cm de la
                importación de Calma): no se recalcula nada ni se cambia ningún número, solo
                se rotula y se empuja a la pantalla de completar que ya existe. Rótulo
                discreto, no un aviso: los objetivos siguen siendo los suyos. */}
            {/* AQUÍ IBA «Macros provisionales · nos falta tu altura y revisa tu edad...»,
                y se ha ido a Mi perfil (punto 111): «es un problema de ficha metido en la
                pantalla de comer, y ocupa tres líneas». En el menú queda un punto naranja
                (ClientDashboard, `fichaPendiente`) para que se vea que hay algo pendiente
                sin tener que entrar a mirar. Los números que enseña esta pantalla siguen
                siendo los suyos: lo que hacía falta era arreglarlos donde se arreglan. */}

            {/* La configuración desplegada. Ahora la abre el «···» de la cabecera (punto
                113), así que necesita su propia forma de cerrarse: antes se cerraba con el
                mismo botón que la abría, y ese botón ya no está aquí. */}
            {configExpanded && (
                <div className="mt-3" data-testid="config-section">
                    <div className="flex flex-col sm:flex-row sm:items-end gap-4">
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
                    <button onClick={() => setConfigExpanded(false)} data-testid="cerrar-config"
                        className="mt-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors">
                        Listo
                    </button>
                </div>
            )}

            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
                {/* AQUÍ IBA «perientreno 38/40P · 52/50H», y se ha ido (punto 110): «el peri
                    está en la lista de comidas». Tenía su propio contador porque los números
                    de arriba llevan el peri dentro y no se veía cuánto de eso era suyo; ahora
                    el intra y el post son dos filas más de la lista, con su objetivo al lado
                    y su estado, como cualquier comida. */}
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
