/**
 * DayNavigation - Navegación entre días
 */
import React from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { Button } from '../ui/button';

export const DayNavigation = ({ 
    selectedDate, 
    onPrevDay, 
    onNextDay, 
    onOpenCalendar 
}) => {
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const selectedDateObj = new Date(dateStr);
        selectedDateObj.setHours(0, 0, 0, 0);
        
        if (selectedDateObj.getTime() === today.getTime()) {
            return 'Hoy';
        }
        
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        if (selectedDateObj.getTime() === yesterday.getTime()) {
            return 'Ayer';
        }
        
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        if (selectedDateObj.getTime() === tomorrow.getTime()) {
            return 'Mañana';
        }
        
        return date.toLocaleDateString('es-ES', { 
            weekday: 'short', 
            day: 'numeric', 
            month: 'short' 
        });
    };

    return (
        <div className="flex items-center justify-between bg-zinc-800/50 rounded-xl p-2">
            <Button 
                variant="ghost" 
                size="sm" 
                onClick={onPrevDay}
                className="text-zinc-400 hover:text-white"
                data-testid="prev-day-btn"
            >
                <ChevronLeft size={20} />
            </Button>
            
            <button 
                onClick={onOpenCalendar}
                className="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-zinc-700/50 transition-colors"
                data-testid="open-calendar-btn"
            >
                <Calendar size={16} className="text-orange-500" />
                <span className="font-medium text-white">
                    {formatDate(selectedDate)}
                </span>
            </button>
            
            <Button 
                variant="ghost" 
                size="sm" 
                onClick={onNextDay}
                className="text-zinc-400 hover:text-white"
                data-testid="next-day-btn"
            >
                <ChevronRight size={20} />
            </Button>
        </div>
    );
};

export default DayNavigation;
