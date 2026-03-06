import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
    Dumbbell, Play, Clock, Repeat, ChevronRight, 
    Calendar, Download, History, Flame, Moon
} from 'lucide-react';

const DAYS_ORDER = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

const RoutinePage = () => {
    const { api, profile } = useAuth();
    const [routine, setRoutine] = useState(null);
    const [routineHistory, setRoutineHistory] = useState([]);
    const [selectedDay, setSelectedDay] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('current');

    useEffect(() => {
        fetchRoutine();
    }, []);

    const fetchRoutine = async () => {
        try {
            const [currentRes, historyRes] = await Promise.all([
                api.get('/routines/current'),
                api.get('/routines/history')
            ]);
            setRoutine(currentRes.data);
            setRoutineHistory(historyRes.data || []);
            
            // Set today as default selected day
            const today = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
            setSelectedDay(today);
        } catch (error) {
            console.error('Error fetching routine:', error);
        } finally {
            setLoading(false);
        }
    };

    const getCurrentDayRoutine = () => {
        if (!routine?.days) return null;
        return routine.days.find(d => d.day.toLowerCase() === selectedDay);
    };

    const planHasCardio = profile?.plan === 'gold' || profile?.plan === 'premium';
    const dayRoutine = getCurrentDayRoutine();

    if (loading) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/3"></div>
                    <div className="h-32 bg-muted rounded"></div>
                    <div className="h-24 bg-muted rounded"></div>
                </div>
            </div>
        );
    }

    if (!routine) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in">
                <h1 className="heading-2 mb-6">Mi Rutina</h1>
                <Card className="bg-muted/50">
                    <CardContent className="p-8 text-center">
                        <Dumbbell className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                        <h2 className="heading-3 mb-2">Sin rutina asignada</h2>
                        <p className="text-muted-foreground mb-4">
                            Tu entrenador está preparando tu rutina personalizada.
                        </p>
                        {profile?.plan === 'bronze' && (
                            <Button variant="outline" className="mt-2">
                                Contratar rutina del mes
                            </Button>
                        )}
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in">
            <div className="flex items-center justify-between mb-6">
                <h1 className="heading-2">Mi Rutina</h1>
                <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    PDF
                </Button>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="current" data-testid="current-routine-tab">
                        <Calendar className="w-4 h-4 mr-2" />
                        Actual
                    </TabsTrigger>
                    <TabsTrigger value="history" data-testid="history-routine-tab">
                        <History className="w-4 h-4 mr-2" />
                        Historial
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="current" className="space-y-4">
                    {/* Day Selector */}
                    <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4 md:mx-0 md:px-0">
                        {DAYS_ORDER.map((day) => {
                            const dayData = routine.days?.find(d => d.day.toLowerCase() === day);
                            const isToday = new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase() === day;
                            const isRest = dayData?.is_rest;
                            
                            return (
                                <Button
                                    key={day}
                                    variant={selectedDay === day ? 'default' : 'outline'}
                                    size="sm"
                                    className={`flex-shrink-0 capitalize ${isRest ? 'opacity-60' : ''}`}
                                    onClick={() => setSelectedDay(day)}
                                    data-testid={`day-${day}`}
                                >
                                    {day.slice(0, 3)}
                                    {isToday && <span className="ml-1 w-1.5 h-1.5 bg-secondary rounded-full"></span>}
                                </Button>
                            );
                        })}
                    </div>

                    {/* Day Content */}
                    {dayRoutine ? (
                        dayRoutine.is_rest ? (
                            <Card className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border-indigo-500/20">
                                <CardContent className="p-6 text-center">
                                    <Moon className="w-12 h-12 text-indigo-400 mx-auto mb-4" />
                                    <h3 className="heading-3 mb-2">Día de Descanso</h3>
                                    <p className="text-muted-foreground">
                                        Recupera energías. Tu cuerpo crece mientras descansas.
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="space-y-4">
                                {/* Stats */}
                                <div className="grid grid-cols-3 gap-3">
                                    <Card className="bg-primary/5">
                                        <CardContent className="p-3 text-center">
                                            <p className="stat-number text-primary">{dayRoutine.exercises?.length || 0}</p>
                                            <p className="text-xs text-muted-foreground">Ejercicios</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-secondary/5">
                                        <CardContent className="p-3 text-center">
                                            <p className="stat-number text-secondary">
                                                {dayRoutine.exercises?.reduce((sum, e) => sum + (e.sets || 0), 0) || 0}
                                            </p>
                                            <p className="text-xs text-muted-foreground">Series</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-accent/5">
                                        <CardContent className="p-3 text-center">
                                            <p className="stat-number text-accent">~45</p>
                                            <p className="text-xs text-muted-foreground">Min</p>
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Exercises List */}
                                <div className="space-y-3">
                                    {dayRoutine.exercises?.map((exercise, index) => (
                                        <Card key={index} className="exercise-card" data-testid={`exercise-${index}`}>
                                            <div className="flex items-center gap-4">
                                                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                                    <span className="font-bold text-primary">{index + 1}</span>
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <h4 className="font-semibold truncate">{exercise.name}</h4>
                                                    <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                                                        <span className="flex items-center gap-1">
                                                            <Repeat className="w-3 h-3" />
                                                            {exercise.sets} x {exercise.reps}
                                                        </span>
                                                        <span className="flex items-center gap-1">
                                                            <Clock className="w-3 h-3" />
                                                            {exercise.rest}
                                                        </span>
                                                    </div>
                                                </div>
                                                {exercise.video_url && (
                                                    <Button variant="ghost" size="icon" asChild>
                                                        <a href={exercise.video_url} target="_blank" rel="noopener noreferrer">
                                                            <Play className="w-4 h-4" />
                                                        </a>
                                                    </Button>
                                                )}
                                            </div>
                                            {exercise.notes && (
                                                <p className="text-sm text-muted-foreground mt-3 pl-14">
                                                    {exercise.notes}
                                                </p>
                                            )}
                                        </Card>
                                    ))}
                                </div>

                                {/* Cardio Section (Gold+ only) */}
                                {planHasCardio && dayRoutine.cardio && (
                                    <Card className="bg-gradient-to-r from-orange-500/10 to-red-500/10 border-orange-500/20">
                                        <CardContent className="p-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
                                                    <Flame className="w-5 h-5 text-orange-500" />
                                                </div>
                                                <div>
                                                    <h4 className="font-semibold">Cardio - {dayRoutine.cardio.type}</h4>
                                                    <p className="text-sm text-muted-foreground">
                                                        {dayRoutine.cardio.duration}
                                                        {dayRoutine.cardio.notes && ` • ${dayRoutine.cardio.notes}`}
                                                    </p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}
                            </div>
                        )
                    ) : (
                        <Card className="bg-muted/50">
                            <CardContent className="p-6 text-center">
                                <p className="text-muted-foreground">
                                    No hay ejercicios programados para este día.
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Trainer Notes */}
                    {routine.trainer_notes && (
                        <Card className="bg-blue-500/5 border-blue-500/20">
                            <CardContent className="p-4">
                                <h4 className="font-semibold text-sm mb-2">Notas del entrenador</h4>
                                <p className="text-sm text-muted-foreground">{routine.trainer_notes}</p>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="history">
                    <ScrollArea className="h-[60vh]">
                        <div className="space-y-3">
                            {routineHistory.length > 0 ? (
                                routineHistory.map((r, index) => (
                                    <Card key={r.id} className={index === 0 ? 'border-primary/50' : ''}>
                                        <CardContent className="p-4">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="font-semibold">
                                                        {new Date(r.created_at).toLocaleDateString('es-ES', {
                                                            day: 'numeric',
                                                            month: 'long',
                                                            year: 'numeric'
                                                        })}
                                                    </p>
                                                    <p className="text-sm text-muted-foreground">
                                                        {r.days?.filter(d => !d.is_rest).length || 0} días de entrenamiento
                                                    </p>
                                                </div>
                                                {index === 0 && (
                                                    <Badge variant="default">Actual</Badge>
                                                )}
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))
                            ) : (
                                <p className="text-center text-muted-foreground py-8">
                                    No hay rutinas anteriores.
                                </p>
                            )}
                        </div>
                    </ScrollArea>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default RoutinePage;
