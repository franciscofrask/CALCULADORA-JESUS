import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const DAYS_SHORT = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
const MONTH_NAMES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

const DietCalendar = ({ open, onClose, onSelectDate, api }) => {
    const today = new Date();
    const [year, setYear] = useState(today.getFullYear());
    const [month, setMonth] = useState(today.getMonth() + 1);
    const [calendarData, setCalendarData] = useState({});
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!open) return;
        const fetchCalendar = async () => {
            setLoading(true);
            try {
                const res = await api(`/api/diets/calendar/${year}/${month}`);
                setCalendarData(res.days || {});
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

    const todayStr = today.toISOString().split('T')[0];

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
                    <div className="flex items-center justify-between">
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
                            <div key={d} className="text-center text-xs font-bold text-gray-400 uppercase">{d}</div>
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
                                        const status = getDayStatus(day);
                                        const isComplete = status?.status === 'complete';
                                        const isPartial = status?.status === 'partial';
                                        const hasDiet = isComplete || isPartial;

                                        return (
                                            <button
                                                key={di}
                                                onClick={() => handleDayClick(day)}
                                                className={`relative w-full aspect-square rounded-lg flex items-center justify-center text-sm font-medium transition-all
                                                    ${isToday ? 'ring-2 ring-orange-500' : ''}
                                                    ${isComplete ? 'bg-green-500/20 text-green-600 hover:bg-green-500/30' : ''}
                                                    ${isPartial ? 'bg-orange-500/20 text-orange-600 hover:bg-orange-500/30' : ''}
                                                    ${!hasDiet ? 'text-gray-600 hover:bg-gray-100' : ''}
                                                `}
                                                data-testid={`cal-day-${day}`}
                                            >
                                                {day}
                                                {hasDiet && (
                                                    <span className={`absolute bottom-0.5 w-1.5 h-1.5 rounded-full ${isComplete ? 'bg-green-500' : 'bg-orange-500'}`} />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Legend */}
                    <div className="flex items-center justify-center gap-4 mt-4 pt-3 border-t text-xs text-gray-500">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Completa</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> Parcial</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-300" /> Vacía</span>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default DietCalendar;
