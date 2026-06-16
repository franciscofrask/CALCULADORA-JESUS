import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Dumbbell, Clock, Repeat, ChevronRight, ChevronDown, ChevronUp,
    Download, History, Flame, Moon, Play, Timer, Trophy
} from 'lucide-react';

const DAYS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const DAY_LABELS = { lunes: 'L', martes: 'M', 'miércoles': 'X', jueves: 'J', viernes: 'V', 'sábado': 'S', domingo: 'D' };

const RoutinePage = () => {
    const { api, profile } = useAuth();
    const [routine, setRoutine] = useState(null);
    const [routineHistory, setRoutineHistory] = useState([]);
    const [selectedDay, setSelectedDay] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showHistory, setShowHistory] = useState(false);

    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch solo al montar
    useEffect(() => { fetchRoutine(); }, []);

    const fetchRoutine = async () => {
        try {
            const [currentRes, historyRes] = await Promise.all([
                api.get('/routines/current'),
                api.get('/routines/history')
            ]);
            setRoutine(currentRes.data);
            setRoutineHistory(historyRes.data || []);
            const today = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
            setSelectedDay(today);
        } catch (error) {
            console.error('Error fetching routine:', error);
        } finally {
            setLoading(false);
        }
    };

    const getDayData = (day) => routine?.days?.find(d => d.day.toLowerCase() === day);
    const todayName = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
    const dayRoutine = getDayData(selectedDay);

    // Count training vs rest days
    const trainingDays = routine?.days?.filter(d => !d.is_rest).length || 0;
    const totalExercises = routine?.days?.reduce((sum, d) => sum + (d.exercises?.length || 0), 0) || 0;

    if (loading) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/3" />
                    <div className="h-20 bg-[#111] rounded-xl" />
                    <div className="h-64 bg-[#111] rounded-xl" />
                </div>
            </div>
        );
    }

    if (!routine) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="routine-page">
                <h1 className="text-2xl font-bold text-white mb-6" style={{ fontFamily: 'Bebas Neue' }}>MI RUTINA</h1>
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-8 text-center">
                        <div className="w-16 h-16 bg-[#FF671F]/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <Dumbbell className="w-8 h-8 text-[#FF671F]/50" />
                        </div>
                        <h2 className="font-bold text-white text-lg mb-2" style={{ fontFamily: 'Bebas Neue' }}>SIN RUTINA ASIGNADA</h2>
                        <p className="text-white/40 text-sm">Tu entrenador está preparando tu rutina personalizada.</p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="routine-page">
            <div className="max-w-2xl mx-auto space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Bebas Neue' }}>MI RUTINA</h1>
                    <Button
                        variant="ghost" size="sm"
                        className="text-white/40 hover:text-white"
                        onClick={() => setShowHistory(!showHistory)}
                        data-testid="toggle-history-btn"
                    >
                        <History className="w-4 h-4 mr-1.5" />
                        {showHistory ? 'Actual' : 'Historial'}
                    </Button>
                </div>

                {showHistory ? (
                    /* ========== HISTORY VIEW ========== */
                    <div className="space-y-3" data-testid="routine-history">
                        {routineHistory.length > 0 ? routineHistory.map((r, i) => (
                            <Card key={r.id} className={`bg-[#111111] ${i === 0 ? 'border-[#FF671F]/40' : 'border-[#222]'}`}>
                                <CardContent className="p-4 flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-white text-sm">
                                            {new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                                        </p>
                                        <p className="text-xs text-white/40">{r.days?.filter(d => !d.is_rest).length || 0} días de entreno</p>
                                    </div>
                                    {i === 0 && <Badge className="bg-[#FF671F] text-white border-0 text-[10px]">ACTUAL</Badge>}
                                </CardContent>
                            </Card>
                        )) : (
                            <p className="text-center text-white/40 py-8 text-sm">No hay rutinas anteriores.</p>
                        )}
                    </div>
                ) : (
                    /* ========== CURRENT ROUTINE VIEW ========== */
                    <>
                        {/* Week Stats */}
                        <div className="grid grid-cols-3 gap-3">
                            <StatCard value={trainingDays} label="Días entreno" color="#FF671F" icon={Dumbbell} testId="stat-training-days" />
                            <StatCard value={totalExercises} label="Ejercicios" color="#22C55E" icon={Trophy} testId="stat-exercises" />
                            <StatCard value={7 - trainingDays} label="Descanso" color="#8B5CF6" icon={Moon} testId="stat-rest-days" />
                        </div>

                        {/* Day Selector */}
                        <div className="grid grid-cols-7 gap-1.5" data-testid="day-selector">
                            {DAYS_ES.map((day) => {
                                const d = getDayData(day);
                                const isToday = todayName === day;
                                const selected = selectedDay === day;
                                const isRest = d?.is_rest;
                                return (
                                    <button
                                        key={day}
                                        onClick={() => setSelectedDay(day)}
                                        className={`relative flex flex-col items-center py-2.5 rounded-xl transition-all ${
                                            selected
                                                ? 'bg-[#FF671F] text-white shadow-lg shadow-[#FF671F]/20'
                                                : isRest
                                                    ? 'bg-[#111] text-white/30 hover:bg-[#1A1A1A]'
                                                    : 'bg-[#111] text-white/70 hover:bg-[#1A1A1A]'
                                        }`}
                                        data-testid={`day-btn-${day}`}
                                    >
                                        <span className="text-[10px] font-bold uppercase">{DAY_LABELS[day]}</span>
                                        {!isRest && d && (
                                            <span className={`text-[9px] mt-0.5 ${selected ? 'text-white/80' : 'text-white/30'}`}>
                                                {d.exercises?.length || 0}ej
                                            </span>
                                        )}
                                        {isRest && <Moon className={`w-3 h-3 mt-0.5 ${selected ? 'text-white/80' : 'text-white/20'}`} />}
                                        {isToday && (
                                            <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${selected ? 'bg-white' : 'bg-[#FF671F]'}`} />
                                        )}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Day Content */}
                        {dayRoutine ? (
                            dayRoutine.is_rest ? (
                                <Card className="bg-gradient-to-br from-[#8B5CF6]/10 to-[#6D28D9]/5 border-[#8B5CF6]/20">
                                    <CardContent className="p-6 text-center">
                                        <Moon className="w-10 h-10 text-[#8B5CF6]/60 mx-auto mb-3" />
                                        <h3 className="font-bold text-white text-lg mb-1" style={{ fontFamily: 'Bebas Neue' }}>DÍA DE DESCANSO</h3>
                                        <p className="text-white/40 text-sm">Recupera energías. Tu cuerpo crece mientras descansas.</p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="space-y-2.5" data-testid="exercises-list">
                                    {dayRoutine.exercises?.map((exercise, index) => (
                                        <ExerciseCard key={index} exercise={exercise} index={index} />
                                    ))}
                                </div>
                            )
                        ) : (
                            <Card className="bg-[#111111] border-[#222]">
                                <CardContent className="p-6 text-center">
                                    <p className="text-white/40 text-sm">No hay ejercicios programados para este día.</p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Cardio Section */}
                        {dayRoutine && !dayRoutine.is_rest && dayRoutine.cardio && (
                            <Card className="bg-gradient-to-r from-[#FF671F]/10 to-[#EF4444]/5 border-[#FF671F]/20">
                                <CardContent className="p-4 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-[#FF671F]/20 rounded-xl flex items-center justify-center flex-shrink-0">
                                        <Flame className="w-5 h-5 text-[#FF671F]" />
                                    </div>
                                    <div>
                                        <p className="font-bold text-white text-sm uppercase">Cardio &middot; {dayRoutine.cardio.type}</p>
                                        <p className="text-xs text-white/40">{dayRoutine.cardio.duration}{dayRoutine.cardio.notes && ` — ${dayRoutine.cardio.notes}`}</p>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Trainer Notes */}
                        {routine.trainer_notes && (
                            <Card className="bg-[#FF671F]/5 border-[#FF671F]/20">
                                <CardContent className="p-4">
                                    <p className="text-[10px] font-bold text-[#FF671F] uppercase tracking-wider mb-1.5">Notas del entrenador</p>
                                    <p className="text-sm text-white/60 leading-relaxed">{routine.trainer_notes}</p>
                                </CardContent>
                            </Card>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

// =============== SUB-COMPONENTS ===============

const StatCard = ({ value, label, color, icon: Icon, testId }) => (
    <Card className="bg-[#111111] border-[#222]" data-testid={testId}>
        <CardContent className="p-3 text-center">
            <div className="flex items-center justify-center gap-1.5 mb-1">
                <Icon className="w-3.5 h-3.5" style={{ color }} />
                <span className="text-2xl font-bold" style={{ fontFamily: 'Bebas Neue', color }}>{value}</span>
            </div>
            <p className="text-[10px] text-white/40 uppercase tracking-wider">{label}</p>
        </CardContent>
    </Card>
);

const ExerciseCard = ({ exercise, index }) => {
    const [expanded, setExpanded] = useState(false);
    const totalSets = exercise.sets || 0;

    return (
        <Card
            className="bg-[#111111] border-[#222] hover:border-[#FF671F]/30 transition-all"
            data-testid={`exercise-${index}`}
        >
            <CardContent className="p-0">
                <button
                    className="w-full flex items-center gap-3 p-3.5 text-left"
                    onClick={() => setExpanded(!expanded)}
                >
                    {/* Number badge */}
                    <div className="w-9 h-9 bg-[#FF671F]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                        <span className="text-base font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>{index + 1}</span>
                    </div>

                    {/* Name + meta */}
                    <div className="flex-1 min-w-0">
                        <p className="font-semibold text-white text-sm truncate">{exercise.name}</p>
                        <div className="flex items-center gap-3 text-xs text-white/40 mt-0.5">
                            <span className="flex items-center gap-1">
                                <Repeat className="w-3 h-3" />
                                <span className="text-[#FF671F] font-bold">{totalSets}</span> x {exercise.reps}
                            </span>
                            <span className="flex items-center gap-1">
                                <Timer className="w-3 h-3" />
                                {exercise.rest}
                            </span>
                        </div>
                    </div>

                    {/* Expand indicator */}
                    {(exercise.notes || exercise.video_url) && (
                        expanded
                            ? <ChevronUp className="w-4 h-4 text-white/20" />
                            : <ChevronDown className="w-4 h-4 text-white/20" />
                    )}
                </button>

                {expanded && (exercise.notes || exercise.video_url) && (
                    <div className="px-3.5 pb-3.5 pt-0 space-y-2 border-t border-[#1A1A1A] mt-0">
                        {exercise.notes && (
                            <p className="text-xs text-white/30 italic pt-2 pl-12">{exercise.notes}</p>
                        )}
                        {exercise.video_url && (
                            <a href={exercise.video_url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 text-xs text-[#FF671F] hover:underline pl-12 pt-1"
                            >
                                <Play className="w-3 h-3" /> Ver vídeo
                            </a>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default RoutinePage;
