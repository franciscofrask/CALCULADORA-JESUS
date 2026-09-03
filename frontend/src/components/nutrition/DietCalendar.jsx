import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const DAYS_SHORT = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
const MONTH_NAMES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

/**
 * `abierto` es el dia que se esta mirando en Nutricion, para poder marcarlo (1-09-2026).
 *
 * Aqui solo se resaltaba HOY, asi que quien estaba en el 15 de agosto y abria el calendario
 * para saltar a otro dia no tenia nada que le dijera de donde venia. Y el calendario se abre
 * justo para eso: para moverse.
 */
const DietCalendar = ({ open, onClose, onSelectDate, api, abierto = null }) => {
    const today = new Date();
    // Y se abre por el MES DEL DIA ABIERTO, no por el de hoy: si estas en agosto y abres el
    // calendario, lo que quieres ver es agosto.
    const deLoAbierto = abierto ? new Date(`${abierto}T12:00:00`) : today;
    const [year, setYear] = useState(deLoAbierto.getFullYear());
    const [month, setMonth] = useState(deLoAbierto.getMonth() + 1);
    const [calendarData, setCalendarData] = useState({});
    const [macroChangeDates, setMacroChangeDates] = useState([]);
    const [loading, setLoading] = useState(false);

    // Cada vez que se abre, al mes del dia que se esta mirando: si no, el que vuelve a
    // abrirlo se encuentra el mes que dejo la vez anterior.
    useEffect(() => {
        if (!open || !abierto) return;
        const d = new Date(`${abierto}T12:00:00`);
        setYear(d.getFullYear());
        setMonth(d.getMonth() + 1);
    }, [open, abierto]);

    useEffect(() => {
        if (!open) return;
        const fetchCalendar = async () => {
            setLoading(true);
            try {
                const res = await api(`/api/diets/calendar/${year}/${month}`);
                setCalendarData(res.days || {});
                setMacroChangeDates(res.macro_change_dates || []);
            } catch (err) {
                console.error('Error loading calendar:', err);
            }
            setLoading(false);
        };
        fetchCalendar();
    }, [open, year, month, api]);

    const prevMonth = () => {
        if (month === 1) { setMonth(12); setYear(y => y - 1); }
        else setMonth(m => m - 1);
    };
    const nextMonth = () => {
        if (month === 12) { setMonth(1); setYear(y => y + 1); }
        else setMonth(m => m + 1);
    };

    // Build calendar grid
    const firstDay = new Date(year, month - 1, 1);
    const daysInMonth = new Date(year, month, 0).getDate();
    let startDow = firstDay.getDay();
    startDow = startDow === 0 ? 6 : startDow - 1; // Monday = 0

    const weeks = [];
    let currentWeek = new Array(startDow).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
        currentWeek.push(d);
        if (currentWeek.length === 7) { weeks.push(currentWeek); currentWeek = []; }
    }
    if (currentWeek.length > 0) {
        while (currentWeek.length < 7) currentWeek.push(null);
        weeks.push(currentWeek);
    }

    // El dia LOCAL del cliente, no el UTC (bloque F, 23-08).
    const todayStr = today.toLocaleDateString('en-CA');

    const getDayStatus = (day) => {
        if (!day) return null;
        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        return calendarData[dateStr] || null;
    };

    const handleDayClick = (day) => {
        if (!day) return;
        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        onSelectDate(dateStr);
        onClose();
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-sm rounded-2xl p-0 gap-0 overflow-hidden" data-testid="diet-calendar-modal">
                <DialogHeader className="bg-[#1a1a2e] p-4">
                    {/* SITIO PARA LA «X» (1-09-2026). El boton de cerrar del dialogo va en
                        `absolute right-4 top-4` y caia JUSTO ENCIMA de la esquina de la
                        flecha de mes siguiente: al ir a avanzar de mes por ahi, se cerraba
                        el calendario. Medido: la flecha ocupa 38x38 y la X sus 17x17 de
                        arriba a la derecha, por encima. Con este hueco a la derecha la
                        flecha se aparta y cada boton tiene lo suyo. */}
                    <div className="flex items-center justify-between pr-9">
                        <Button variant="ghost" size="icon" onClick={prevMonth} className="text-white hover:bg-white/10">
                            <ChevronLeft className="w-5 h-5" />
                        </Button>
                        <DialogTitle className="text-white text-base font-bold uppercase tracking-wider">
                            {MONTH_NAMES[month - 1]} {year}
                        </DialogTitle>
                        <Button variant="ghost" size="icon" onClick={nextMonth} className="text-white hover:bg-white/10">
                            <ChevronRight className="w-5 h-5" />
                        </Button>
                    </div>
                </DialogHeader>

                <div className="p-4">
                    {/* Day headers */}
                    <div className="grid grid-cols-7 gap-1 mb-2">
                        {DAYS_SHORT.map(d => (
                            <div key={d} className="text-center text-xs font-bold text-muted-foreground uppercase">{d}</div>
                        ))}
                    </div>

                    {/* Calendar grid */}
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <div className="animate-spin rounded-full h-6 w-6 border-2 border-orange-500 border-t-transparent" />
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {weeks.map((week, wi) => (
                                <div key={wi} className="grid grid-cols-7 gap-1">
                                    {week.map((day, di) => {
                                        if (!day) return <div key={di} />;
                                        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                                        const isToday = dateStr === todayStr;
                                        const esElAbierto = dateStr === abierto;
                                        const status = getDayStatus(day);
                                        const hasDiet = status?.status === 'complete' || status?.status === 'partial';
                                        // EL NARANJA ES SOLO PARA LO QUE ESTÁ MAL, NO PARA
                                        // LO QUE ESTÁ A MEDIAS (3-09-2026).
                                        //
                                        // Aquí se pintaba de naranja TODO día con algo
                                        // dentro y sin la marca de cuadrado, así que el día
                                        // recién empezado salía con el mismo aviso que el
                                        // que se pasa 70 g. Es lo que le salía a Gonzalo
                                        // «a todos de naranja», y va contra la regla escrita
                                        // de la casa (`lib/estadoDelMacro.js`): «ir corto no
                                        // es un error, es que todavía no has terminado».
                                        //
                                        // Ahora un día solo se juzga cuando está entero, y
                                        // el que está a medias va en gris, como en Mi
                                        // semana, que dice «1 de 4 comidas» sin color.
                                        const estaEntero = status?.status === 'complete';
                                        const isCuadrado = estaEntero && status?.is_cuadrado === true;
                                        const isPartial = estaEntero && status?.is_cuadrado === false;
                                        const aMedias = hasDiet && !estaEntero;
                                        const isMacroChange = macroChangeDates.includes(dateStr);

                                        return (
                                            <button
                                                key={di}
                                                onClick={() => handleDayClick(day)}
                                                // EL DIA ABIERTO VA RELLENO, HOY VA CON ARO.
                                                // Son dos cosas distintas y tienen que
                                                // distinguirse cuando coinciden: el aro dice
                                                // «hoy» y el relleno dice «estas aqui».
                                                className={`relative w-full aspect-square rounded-lg flex items-center justify-center text-sm font-medium transition-all
                                                    ${esElAbierto ? 'bg-brand text-white font-bold' : ''}
                                                    ${isToday ? 'ring-2 ring-orange-500' : ''}
                                                    ${!isToday && isMacroChange ? 'ring-2 ring-blue-400' : ''}
                                                    ${!esElAbierto && isCuadrado ? 'bg-green-500/20 text-green-600 hover:bg-green-500/30' : ''}
                                                    ${!esElAbierto && isPartial ? 'bg-orange-500/20 text-orange-600 hover:bg-orange-500/30' : ''}
                                                    ${!esElAbierto && aMedias ? 'bg-muted text-foreground/70 hover:bg-muted/70' : ''}
                                                    ${!esElAbierto && !hasDiet ? 'text-muted-foreground hover:bg-muted' : ''}
                                                `}
                                                title={isMacroChange ? 'Cambio de macros desde este día' : undefined}
                                                aria-current={esElAbierto ? 'date' : undefined}
                                                data-testid={`cal-day-${day}`}
                                            >
                                                {day}
                                                {isMacroChange && (
                                                    <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-blue-400" />
                                                )}
                                                {hasDiet && (
                                                    <span className={`absolute bottom-0.5 w-1.5 h-1.5 rounded-full ${
                                                        isCuadrado ? 'bg-green-500'
                                                            : isPartial ? 'bg-orange-500'
                                                                : 'bg-muted-foreground/50'}`} />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Legend */}
                    <div className="flex items-center justify-center gap-4 mt-4 pt-3 border-t text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Cuadrada</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> Sin cuadrar</span>
                        {/* La leyenda dice lo que se ve: el día a medias tiene su punto y no
                            es «sin dieta», que era como se leía al no estar nombrado. */}
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-muted-foreground/50" /> A medias</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-muted" /> Sin dieta</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-400" /> Cambio macros</span>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default DietCalendar;
