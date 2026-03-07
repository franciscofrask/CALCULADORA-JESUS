import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
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
            <div className="p-4 md:p-6 pb-24 md:pb-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/3"></div>
                    <div className="h-32 bg-[#111] rounded"></div>
                </div>
            </div>
        );
    }

    if (!routine) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen relative overflow-hidden">
                {/* Background */}
                <div 
                    className="absolute inset-0 bg-cover bg-center opacity-10"
                    style={{
                        backgroundImage: `url('https://customer-assets.emergentagent.com/job_language-12/artifacts/i7mzn5tb_IMG_5765.jpeg')`
                    }}
                ></div>
                <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/90 to-[#0A0A0A]/70"></div>
                
                <div className="relative z-10">
                    <h1 className="heading-2 text-white mb-6">MI RUTINA</h1>
                    <Card className="bg-[#111111]/90 backdrop-blur border-[#333]">
                        <CardContent className="p-8 text-center">
                            <Dumbbell className="w-16 h-16 text-[#FF671F]/50 mx-auto mb-4" />
                            <h2 className="heading-3 text-white mb-2">SIN RUTINA ASIGNADA</h2>
                            <p className="text-white/50 mb-6">
                                Tu entrenador está preparando tu rutina personalizada.
                            </p>
                            {profile?.plan === 'bronze' && (
                                <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white uppercase tracking-wider">
                                    Contratar rutina del mes
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen relative overflow-hidden">
            {/* Background */}
            <div 
                className="absolute inset-0 bg-cover bg-center opacity-5"
                style={{
                    backgroundImage: `url('https://customer-assets.emergentagent.com/job_language-12/artifacts/i7mzn5tb_IMG_5765.jpeg')`
                }}
            ></div>
            
            <div className="relative z-10">
                <div className="flex items-center justify-between mb-6">
                    <h1 className="heading-2 text-white">MI RUTINA</h1>
                    <Button variant="outline" size="sm" className="bg-transparent border-[#333] text-white hover:border-[#FF671F]">
                        <Download className="w-4 h-4 mr-2" />
                        PDF
                    </Button>
                </div>

                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                    <TabsList className="grid w-full grid-cols-2 bg-[#111111]">
                        <TabsTrigger 
                            value="current" 
                            data-testid="current-routine-tab"
                            className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider"
                        >
                            <Calendar className="w-4 h-4 mr-2" />
                            Actual
                        </TabsTrigger>
                        <TabsTrigger 
                            value="history" 
                            data-testid="history-routine-tab"
                            className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider"
                        >
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
                                        className={`flex-shrink-0 capitalize ${
                                            selectedDay === day 
                                                ? 'bg-[#FF671F] text-white border-[#FF671F]' 
                                                : 'bg-transparent border-[#333] text-white/70 hover:border-[#FF671F]'
                                        } ${isRest ? 'opacity-60' : ''}`}
                                        onClick={() => setSelectedDay(day)}
                                        data-testid={`day-${day}`}
                                    >
                                        {day.slice(0, 3)}
                                        {isToday && <span className="ml-1 w-2 h-2 bg-green-500 rounded-full"></span>}
                                    </Button>
                                );
                            })}
                        </div>

                        {/* Day Content */}
                        {dayRoutine ? (
                            dayRoutine.is_rest ? (
                                <Card className="bg-gradient-to-br from-indigo-900/30 to-purple-900/30 border-indigo-500/20">
                                    <CardContent className="p-8 text-center">
                                        <Moon className="w-16 h-16 text-indigo-400 mx-auto mb-4" />
                                        <h3 className="heading-3 text-white mb-2">DÍA DE DESCANSO</h3>
                                        <p className="text-white/50">
                                            Recupera energías. Tu cuerpo crece mientras descansas.
                                        </p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="space-y-4">
                                    {/* Stats */}
                                    <div className="grid grid-cols-3 gap-3">
                                        <Card className="bg-[#111111] border-[#222]">
                                            <CardContent className="p-3 text-center">
                                                <p className="text-3xl font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>
                                                    {dayRoutine.exercises?.length || 0}
                                                </p>
                                                <p className="text-xs text-white/50 uppercase tracking-wider">Ejercicios</p>
                                            </CardContent>
                                        </Card>
                                        <Card className="bg-[#111111] border-[#222]">
                                            <CardContent className="p-3 text-center">
                                                <p className="text-3xl font-bold text-green-500" style={{ fontFamily: 'Bebas Neue' }}>
                                                    {dayRoutine.exercises?.reduce((sum, e) => sum + (e.sets || 0), 0) || 0}
                                                </p>
                                                <p className="text-xs text-white/50 uppercase tracking-wider">Series</p>
                                            </CardContent>
                                        </Card>
                                        <Card className="bg-[#111111] border-[#222]">
                                            <CardContent className="p-3 text-center">
                                                <p className="text-3xl font-bold text-yellow-500" style={{ fontFamily: 'Bebas Neue' }}>
                                                    ~45
                                                </p>
                                                <p className="text-xs text-white/50 uppercase tracking-wider">Min</p>
                                            </CardContent>
                                        </Card>
                                    </div>

                                    {/* Exercises List */}
                                    <div className="space-y-3">
                                        {dayRoutine.exercises?.map((exercise, index) => (
                                            <Card 
                                                key={index} 
                                                className="bg-[#111111] border-[#222] hover:border-[#FF671F]/50 transition-all"
                                                data-testid={`exercise-${index}`}
                                            >
                                                <CardContent className="p-4">
                                                    <div className="flex items-center gap-4">
                                                        <div className="w-12 h-12 bg-[#FF671F]/20 rounded-lg flex items-center justify-center flex-shrink-0">
                                                            <span className="text-xl font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>
                                                                {index + 1}
                                                            </span>
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <h4 className="font-semibold text-white truncate">{exercise.name}</h4>
                                                            <div className="flex items-center gap-4 text-sm text-white/50 mt-1">
                                                                <span className="flex items-center gap-1">
                                                                    <Repeat className="w-3 h-3" />
                                                                    <span className="text-[#FF671F] font-bold">{exercise.sets}</span> x {exercise.reps}
                                                                </span>
                                                                <span className="flex items-center gap-1">
                                                                    <Clock className="w-3 h-3" />
                                                                    {exercise.rest}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        {exercise.video_url && (
                                                            <Button variant="ghost" size="icon" className="text-[#FF671F]" asChild>
                                                                <a href={exercise.video_url} target="_blank" rel="noopener noreferrer">
                                                                    <Play className="w-5 h-5" />
                                                                </a>
                                                            </Button>
                                                        )}
                                                    </div>
                                                    {exercise.notes && (
                                                        <p className="text-sm text-white/40 mt-3 pl-16 italic">
                                                            {exercise.notes}
                                                        </p>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>

                                    {/* Cardio Section (Gold+ only) */}
                                    {planHasCardio && dayRoutine.cardio && (
                                        <Card className="bg-gradient-to-r from-orange-900/30 to-red-900/30 border-orange-500/20">
                                            <CardContent className="p-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-12 h-12 bg-orange-500/20 rounded-lg flex items-center justify-center">
                                                        <Flame className="w-6 h-6 text-orange-500" />
                                                    </div>
                                                    <div>
                                                        <h4 className="font-bold text-white uppercase">Cardio - {dayRoutine.cardio.type}</h4>
                                                        <p className="text-sm text-white/50">
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
                            <Card className="bg-[#111111] border-[#222]">
                                <CardContent className="p-6 text-center">
                                    <p className="text-white/50">
                                        No hay ejercicios programados para este día.
                                    </p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Trainer Notes */}
                        {routine.trainer_notes && (
                            <Card className="bg-[#FF671F]/10 border-[#FF671F]/30">
                                <CardContent className="p-4">
                                    <h4 className="font-bold text-[#FF671F] text-sm uppercase tracking-wider mb-2">Notas del entrenador</h4>
                                    <p className="text-sm text-white/70">{routine.trainer_notes}</p>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    <TabsContent value="history">
                        <ScrollArea className="h-[60vh]">
                            <div className="space-y-3">
                                {routineHistory.length > 0 ? (
                                    routineHistory.map((r, index) => (
                                        <Card key={r.id} className={`bg-[#111111] ${index === 0 ? 'border-[#FF671F]/50' : 'border-[#222]'}`}>
                                            <CardContent className="p-4">
                                                <div className="flex items-center justify-between">
                                                    <div>
                                                        <p className="font-semibold text-white">
                                                            {new Date(r.created_at).toLocaleDateString('es-ES', {
                                                                day: 'numeric',
                                                                month: 'long',
                                                                year: 'numeric'
                                                            })}
                                                        </p>
                                                        <p className="text-sm text-white/50">
                                                            {r.days?.filter(d => !d.is_rest).length || 0} días de entrenamiento
                                                        </p>
                                                    </div>
                                                    {index === 0 && (
                                                        <Badge className="bg-[#FF671F] text-white border-0">Actual</Badge>
                                                    )}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))
                                ) : (
                                    <p className="text-center text-white/50 py-8">
                                        No hay rutinas anteriores.
                                    </p>
                                )}
                            </div>
                        </ScrollArea>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
};

export default RoutinePage;
