import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
    Dumbbell, Repeat, ChevronDown, ChevronUp, History,
    Flame, Moon, Play, Timer, Trophy, ChevronRight
} from 'lucide-react';

const DAYS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const DAY_LABELS = { lunes: 'L', martes: 'M', 'miércoles': 'X', jueves: 'J', viernes: 'V', 'sábado': 'S', domingo: 'D' };
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

const RoutinePage = () => {
    const { api } = useAuth();
    const [routine, setRoutine] = useState(null);
    const [routineHistory, setRoutineHistory] = useState([]);
    const [selectedDay, setSelectedDay] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showHistory, setShowHistory] = useState(false);

    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    const trainingDays = routine?.days?.filter(d => !d.is_rest).length || 0;
    const totalExercises = routine?.days?.reduce((sum, d) => sum + (d.exercises?.length || 0), 0) || 0;

    const Wrap = ({ children }) => (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto animate-fade-in" data-testid="routine-page">{children}</div>
    );

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-4">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-20 bg-muted rounded-2xl" />
            <div className="h-64 bg-muted rounded-2xl" />
        </div></Wrap>;
    }

    if (!routine) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6">Mi rutina</h1>
            <div className="surface p-10 text-center">
                <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Dumbbell className="w-8 h-8 text-brand/60" />
                </div>
                <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Sin rutina asignada</h2>
                <p className="text-muted-foreground text-sm">Tu entrenador está preparando tu rutina personalizada.</p>
            </div>
        </Wrap>;
    }

    return (
        <Wrap>
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none">Mi rutina</h1>
                <button onClick={() => setShowHistory(!showHistory)} data-testid="toggle-history-btn"
                    className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground px-3 py-2 rounded-lg hover:bg-muted transition-colors">
                    <History className="w-4 h-4" /> {showHistory ? 'Actual' : 'Historial'}
                </button>
            </div>

            {showHistory ? (
                <div className="space-y-3 max-w-2xl" data-testid="routine-history">
                    {routineHistory.length > 0 ? routineHistory.map((r, i) => (
                        <div key={r.id} className={`surface p-4 flex items-center justify-between ${i === 0 ? 'border-brand/40' : ''}`}>
                            <div>
                                <p className="font-semibold text-foreground text-sm">{new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
                                <p className="text-xs text-muted-foreground">{r.days?.filter(d => !d.is_rest).length || 0} días de entreno</p>
                            </div>
                            {i === 0 && <span className="badge-elm">Actual</span>}
                        </div>
                    )) : <p className="text-center text-muted-foreground py-10 text-sm">No hay rutinas anteriores.</p>}
                </div>
            ) : (
                <div className="space-y-5">
                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-3 sm:gap-4 max-w-2xl">
                        <StatCard value={trainingDays} label="Días entreno" color={MACRO_O} icon={Dumbbell} testId="stat-training-days" />
                        <StatCard value={totalExercises} label="Ejercicios" color="#16A34A" icon={Trophy} testId="stat-exercises" />
                        <StatCard value={7 - trainingDays} label="Descanso" color="#7C3AED" icon={Moon} testId="stat-rest-days" />
                    </div>

                    {/* Day selector + detail */}
                    <div className="grid lg:grid-cols-12 gap-5 items-start">
                        {/* Selector: horizontal en móvil, vertical en desktop */}
                        <div className="lg:col-span-4">
                            <p className="caption mb-2 hidden lg:block">Días</p>
                            <div className="grid grid-cols-7 lg:grid-cols-1 gap-1.5 lg:gap-2" data-testid="day-selector">
                                {DAYS_ES.map((day) => {
                                    const d = getDayData(day);
                                    const isToday = todayName === day;
                                    const selected = selectedDay === day;
                                    const isRest = d?.is_rest;
                                    return (
                                        <button key={day} onClick={() => setSelectedDay(day)} data-testid={`day-btn-${slug(day)}`}
                                            className={`relative rounded-xl transition-all border
                                                flex flex-col items-center py-2.5 lg:flex-row lg:items-center lg:justify-between lg:px-4 lg:py-3
                                                ${selected ? 'bg-brand text-white border-brand shadow-sm' : 'bg-card border-border hover:border-border'}`}>
                                            {/* Mobile */}
                                            <span className={`lg:hidden text-[11px] font-bold uppercase ${selected ? 'text-white' : 'text-foreground'}`}>{DAY_LABELS[day]}</span>
                                            <span className="lg:hidden text-[9px] mt-0.5">
                                                {isRest ? <Moon className={`w-3 h-3 ${selected ? 'text-white/80' : 'text-muted-foreground'}`} /> : <span className={selected ? 'text-white/80 font-data' : 'text-muted-foreground font-data'}>{d?.exercises?.length || 0}</span>}
                                            </span>
                                            {/* Desktop */}
                                            <span className="hidden lg:flex items-center gap-2">
                                                <span className={`text-sm font-semibold capitalize ${selected ? 'text-white' : 'text-foreground'}`}>{day}</span>
                                                {isToday && <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${selected ? 'bg-white/20 text-white' : 'bg-brand/10 text-brand'}`}>Hoy</span>}
                                            </span>
                                            <span className="hidden lg:flex items-center gap-1 text-xs">
                                                {isRest
                                                    ? <span className={`flex items-center gap-1 ${selected ? 'text-white/80' : 'text-muted-foreground'}`}><Moon className="w-3.5 h-3.5" /> Descanso</span>
                                                    : <span className={`font-data ${selected ? 'text-white/90' : 'text-muted-foreground'}`}>{d?.exercises?.length || 0} ej</span>}
                                            </span>
                                            {isToday && <span className={`lg:hidden absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${selected ? 'bg-card' : 'bg-brand'}`} />}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Detail */}
                        <div className="lg:col-span-8 space-y-3">
                            {dayRoutine ? (
                                dayRoutine.is_rest ? (
                                    <div className="surface p-8 text-center">
                                        <Moon className="w-10 h-10 text-violet-400 mx-auto mb-3" />
                                        <h3 className="font-heading text-xl font-bold uppercase text-foreground mb-1">Día de descanso</h3>
                                        <p className="text-muted-foreground text-sm">Recupera energías. Tu cuerpo crece mientras descansas.</p>
                                    </div>
                                ) : (
                                    <div className="space-y-3" data-testid="exercises-list">
                                        {dayRoutine.exercises?.map((exercise, index) => (
                                            <ExerciseCard key={index} exercise={exercise} index={index} />
                                        ))}
                                    </div>
                                )
                            ) : (
                                <div className="surface p-8 text-center"><p className="text-muted-foreground text-sm">No hay ejercicios programados para este día.</p></div>
                            )}

                            {dayRoutine && !dayRoutine.is_rest && dayRoutine.cardio && (
                                <div className="surface bg-brand/[0.04] border-brand/20 p-4 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-brand/15 rounded-xl flex items-center justify-center flex-shrink-0">
                                        <Flame className="w-5 h-5 text-brand" />
                                    </div>
                                    <div>
                                        <p className="font-bold text-foreground text-sm uppercase">Cardio · {dayRoutine.cardio.type}</p>
                                        <p className="text-xs text-muted-foreground">{dayRoutine.cardio.duration}{dayRoutine.cardio.notes && ` — ${dayRoutine.cardio.notes}`}</p>
                                    </div>
                                </div>
                            )}

                            {routine.trainer_notes && (
                                <div className="surface bg-brand/[0.04] border-brand/20 p-4">
                                    <p className="text-[11px] font-bold text-brand uppercase tracking-wider mb-1.5">Notas del entrenador</p>
                                    <p className="text-sm text-muted-foreground leading-relaxed">{routine.trainer_notes}</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </Wrap>
    );
};

const MACRO_O = '#FF671F';

const StatCard = ({ value, label, color, icon: Icon, testId }) => (
    <div className="surface p-4 text-center" data-testid={testId}>
        <div className="flex items-center justify-center gap-1.5 mb-1">
            <Icon className="w-4 h-4" style={{ color }} />
            <span className="font-heading text-3xl font-bold" style={{ color }}>{value}</span>
        </div>
        <p className="text-[11px] text-muted-foreground uppercase tracking-wider font-semibold">{label}</p>
    </div>
);

const ExerciseCard = ({ exercise, index }) => {
    const [expanded, setExpanded] = useState(false);
    const totalSets = exercise.sets || 0;
    return (
        <div className="surface surface-hover overflow-hidden" data-testid={`exercise-${index}`}>
            <button className="w-full flex items-center gap-3 p-4 text-left" onClick={() => setExpanded(!expanded)}>
                <div className="w-10 h-10 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                    <span className="font-heading text-lg font-bold text-brand">{index + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-foreground text-sm">{exercise.name}</p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <span className="flex items-center gap-1"><Repeat className="w-3.5 h-3.5" /><span className="text-brand font-bold font-data">{totalSets}</span> × {exercise.reps}</span>
                        <span className="flex items-center gap-1"><Timer className="w-3.5 h-3.5" /> {exercise.rest}</span>
                    </div>
                </div>
                {(exercise.notes || exercise.video_url) && (expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />)}
            </button>
            {expanded && (exercise.notes || exercise.video_url) && (
                <div className="px-4 pb-4 pt-0 space-y-2 border-t border-border">
                    {exercise.notes && <p className="text-xs text-muted-foreground italic pt-3 pl-13" style={{ paddingLeft: '3.25rem' }}>{exercise.notes}</p>}
                    {exercise.video_url && (
                        <a href={exercise.video_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs text-brand hover:underline pt-1 font-semibold">
                            <Play className="w-3 h-3" /> Ver vídeo
                        </a>
                    )}
                </div>
            )}
        </div>
    );
};

export default RoutinePage;
