import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { plural } from '../lib/labels';
import {
    Dumbbell, Repeat, ChevronDown, ChevronUp, History,
    Flame, Moon, Play, Timer, Trophy, ChevronRight, FileText, Check
} from 'lucide-react';

const DAYS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const DAY_LABELS = { lunes: 'L', martes: 'M', 'miércoles': 'X', jueves: 'J', viernes: 'V', 'sábado': 'S', domingo: 'D' };
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

// Fuera del componente a propósito, por lo mismo que el marco de RecuperarPage (13-08):
// definido dentro, cada render creaba una función nueva y React remontaba la página entera
// en vez de actualizarla. Aquí no hay ningún campo que escribir, así que no se pierde el
// foco, pero ExerciseCard sí perdía su useState: al cambiar de día se cerraban todos los
// ejercicios que tuvieras desplegados, y el animate-fade-in se relanzaba solo.
// No usa nada del ámbito del componente, así que sube tal cual.
const Wrap = ({ children }) => (
    <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto animate-fade-in" data-testid="routine-page">{children}</div>
);

// ─────────────────────────────────────────────────────────────────────────────
// LA SEMANA DE LA RUTINA (tarea 7.1 del 21-08, apartados 12 y 19 del doc de Jesús).
// Con el reparto que puso el entrenador al subir el PDF y los días que eligió el
// cliente en su alta, esto dice «Rutina #2 · Semana 3 de 8 · 4 días», pinta la tira de
// lunes a domingo con el grupo o el descanso, y el «Hoy · jueves · Empuje» con MARCAR.
// El descanso es un estado, no un fallo: «Hoy no entrenas», sin rojo y sin pedir nada.
// A nivel de módulo por lo mismo que Wrap: definido dentro se remonta en cada render.
// ─────────────────────────────────────────────────────────────────────────────
const SemanaDeRutina = ({ semana, abrirPdf, tienePdf, onMarcarHoy, onSiLoHice, onRecuperar, marcando }) => {
    // El selector del día para recuperar: null = cerrado.
    const [eligiendoDia, setEligiendoDia] = useState(false);
    if (!semana?.hay) return null;

    const { numero, semanas, semana_actual, dias_de_entreno, dias, hoy, pendiente, puede_marcar } = semana;
    const cab = [
        numero ? `Rutina #${numero}` : 'Tu rutina',
        semana_actual ? (semanas ? `Semana ${Math.min(semana_actual, semanas)} de ${semanas}` : `Semana ${semana_actual}`) : null,
        plural(dias_de_entreno, 'día'),
    ].filter(Boolean).join(' · ');

    // Los días de descanso donde aún se puede recuperar: de hoy en adelante.
    const diasParaRecuperar = dias.filter(d => !d.entrena && d.fecha >= hoy.fecha);

    return (
        <div className="space-y-3 max-w-2xl" data-testid="semana-rutina">
            {/* Cabecera: qué rutina es, por qué semana va y el PDF a un toque. */}
            <div className="surface p-4 flex items-center justify-between gap-3 flex-wrap">
                <p className="font-bold text-foreground text-sm" data-testid="semana-rutina-cabecera">{cab}</p>
                {tienePdf && (
                    <button onClick={abrirPdf} data-testid="semana-rutina-pdf"
                        className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline underline-offset-4">
                        <FileText className="w-4 h-4" /> Abrir el PDF
                    </button>
                )}
            </div>

            {/* La tira de la semana: L a D con el grupo o la luna del descanso. */}
            <div className="grid grid-cols-7 gap-1.5" data-testid="semana-rutina-tira">
                {dias.map(d => (
                    <div key={d.fecha} data-testid={`semana-dia-${d.fecha}`}
                        className={`rounded-xl border px-1 py-2 text-center min-w-0
                            ${d.hoy ? 'border-brand bg-brand/10' : 'border-border bg-card'}`}>
                        <p className={`text-[10px] font-bold uppercase ${d.hoy ? 'text-brand' : 'text-muted-foreground'}`}>
                            {DAY_LABELS[d.dia]}
                        </p>
                        <div className="mt-1 h-8 flex flex-col items-center justify-center">
                            {d.entrena ? (
                                <>
                                    <p className="text-[9px] font-semibold text-foreground leading-tight truncate w-full px-0.5"
                                        title={d.grupo}>{d.grupo}</p>
                                    {d.hecho ? <Check className="w-3 h-3 text-emerald-500 mt-0.5" />
                                        : d.recuperado_en ? <span className="text-[8px] text-muted-foreground">→ otro día</span>
                                        : null}
                                </>
                            ) : (
                                <Moon className="w-3.5 h-3.5 text-muted-foreground/60" />
                            )}
                        </div>
                        {d.recuperacion && <p className="text-[8px] text-brand font-semibold">recup.</p>}
                    </div>
                ))}
            </div>

            {/* Hoy: el grupo con su MARCAR, o el descanso dicho en paz. */}
            {hoy.entrena ? (
                <div className="surface p-4 flex items-center justify-between gap-3" data-testid="semana-rutina-hoy">
                    <div>
                        <p className="caption">Hoy · {hoy.dia}</p>
                        <p className="font-heading text-xl font-bold uppercase text-foreground leading-tight">{hoy.grupo}</p>
                    </div>
                    {puede_marcar && (hoy.hecho ? (
                        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-500">
                            <Check className="w-4 h-4" /> Hecho
                        </span>
                    ) : (
                        <button onClick={() => onMarcarHoy(hoy)} disabled={marcando} data-testid="semana-rutina-marcar"
                            className="btn-brand px-5 py-2.5 font-bold text-sm disabled:opacity-60">
                            Marcar
                        </button>
                    ))}
                </div>
            ) : (
                <div className="surface p-4 flex items-center gap-3" data-testid="semana-rutina-hoy">
                    <Moon className="w-5 h-5 text-violet-400 flex-shrink-0" />
                    <div>
                        <p className="caption">Descanso</p>
                        <p className="font-semibold text-foreground text-sm">Hoy no entrenas.</p>
                    </div>
                </div>
            )}

            {/* El que se dejó: se pregunta, no se riñe. «No se puede mover. Si se ha
                perdido, se recupera otro día» (decisión del apartado 12). */}
            {pendiente && (
                <div className="surface border-brand/30 p-4 space-y-3" data-testid="semana-rutina-pendiente">
                    <p className="text-sm text-foreground">
                        El {pendiente.dia} te dejaste <span className="font-bold">{pendiente.grupo}</span>.
                    </p>
                    {eligiendoDia ? (
                        <div className="space-y-2">
                            <p className="text-xs text-muted-foreground">¿Qué día de descanso lo recuperas?</p>
                            <div className="flex gap-2 flex-wrap">
                                {diasParaRecuperar.map(d => (
                                    <button key={d.fecha} disabled={marcando}
                                        onClick={() => { setEligiendoDia(false); onRecuperar(pendiente, d); }}
                                        data-testid={`semana-recuperar-${d.fecha}`}
                                        className="px-3 py-2 rounded-xl border border-border bg-card text-sm font-semibold text-foreground hover:border-brand/50 capitalize disabled:opacity-60">
                                        {d.dia}
                                    </button>
                                ))}
                                <button onClick={() => setEligiendoDia(false)}
                                    className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground">
                                    Atrás
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex gap-2 flex-wrap">
                            <button onClick={() => onSiLoHice(pendiente)} disabled={marcando} data-testid="semana-si-lo-hice"
                                className="px-4 py-2 rounded-xl border border-emerald-500/50 text-emerald-500 text-sm font-bold hover:bg-emerald-500/10 disabled:opacity-60">
                                Sí lo hice
                            </button>
                            {diasParaRecuperar.length > 0 && (
                                <button onClick={() => setEligiendoDia(true)} disabled={marcando} data-testid="semana-recuperar-otro-dia"
                                    className="px-4 py-2 rounded-xl border border-border text-foreground text-sm font-bold hover:border-brand/50 disabled:opacity-60">
                                    Recuperarlo otro día
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

const RoutinePage = () => {
    const { api } = useAuth();
    const [routine, setRoutine] = useState(null);
    const [routineHistory, setRoutineHistory] = useState([]);
    const [selectedDay, setSelectedDay] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showHistory, setShowHistory] = useState(false);
    // La rutina en PDF que sube su entrenador (la de EntrenoPage). Hasta ahora esta
    // pantalla ni preguntaba por ella: el cliente con PDF y sin rutina estructurada leía
    // «Sin rutina asignada» teniendo su rutina subida. Se pide aparte del Promise.all a
    // propósito: si /routines/current falla, el PDF se enseña igual.
    const [pdfInfo, setPdfInfo] = useState(null);
    useEffect(() => {
        api.get('/routines/pdf/info').then(r => setPdfInfo(r.data?.hay ? r.data : null)).catch(() => {});
    }, [api]);

    // La semana de la rutina (7.1 del 21-08): reparto del PDF + días del cliente. Se
    // pide aparte de /routines/current por lo mismo que el PDF: una no tapa a la otra.
    const [semana, setSemana] = useState(null);
    const [marcando, setMarcando] = useState(false);
    const cargarSemana = React.useCallback(() => {
        // Con el «hoy» del reloj del cliente (bloque F, 23-08).
        api.get(`/routines/semana?hoy_cliente=${new Date().toLocaleDateString('en-CA')}`)
            .then(r => setSemana(r.data?.hay ? r.data : null)).catch(() => {});
    }, [api]);
    useEffect(() => { cargarSemana(); }, [cargarSemana]);

    // MARCAR el entreno de hoy: el check de T3, por el endpoint de siempre
    // (workout_logs). Marcar aquí y en la pantalla de Entreno escriben la misma fila.
    const marcarHoy = async (hoy) => {
        setMarcando(true);
        try {
            await api.post('/workout-logs', {
                hecho: true, tipo: 'entreno', estrellas: null, nota: null,
                pesos: [], compartida: false, dia_rutina: hoy.grupo || null,
            });
            toast.success('Entreno marcado.');
            cargarSemana();
        } catch { toast.error('No hemos podido marcar tu entreno. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // «Sí lo hice»: el día de esta semana que se quedó sin marcar.
    const siLoHice = async (pendiente) => {
        setMarcando(true);
        try {
            await api.post('/routines/semana/hecho', { fecha: pendiente.fecha, grupo: pendiente.grupo, hoy: new Date().toLocaleDateString('en-CA') });
            toast.success('Apuntado.');
            cargarSemana();
        } catch { toast.error('No hemos podido apuntarlo. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // «Recuperarlo otro día»: no se mueve, se recupera en un día de descanso.
    const recuperar = async (pendiente, dia) => {
        setMarcando(true);
        try {
            await api.post('/routines/semana/recuperar', { fecha_original: pendiente.fecha, fecha: dia.fecha, hoy: new Date().toLocaleDateString('en-CA') });
            toast.success(`${pendiente.grupo} pasa al ${dia.dia}.`);
            cargarSemana();
        } catch { toast.error('No hemos podido apuntar la recuperación. Inténtalo en un momento.'); }
        finally { setMarcando(false); }
    };

    // Se abre vía blob porque el visor del navegador no manda el token (mismo camino que
    // EntrenoPage).
    const abrirPdf = async () => {
        try {
            const r = await api.get('/routines/pdf', { responseType: 'blob' });
            window.open(URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })), '_blank');
        } catch { toast.error('No hemos podido abrir tu rutina. Inténtalo en un momento.'); }
    };

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

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-4">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-20 bg-muted rounded-2xl" />
            <div className="h-64 bg-muted rounded-2xl" />
        </div></Wrap>;
    }

    if (!routine) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6" data-testid="routine-heading">Mi rutina</h1>
            {pdfInfo && semana?.hay ? (
                /* Con PDF y con la semana montada (reparto + días del cliente): la
                   pantalla completa del apartado 12: cabecera, tira, hoy y lo pendiente. */
                <SemanaDeRutina semana={semana} abrirPdf={abrirPdf} tienePdf
                    onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                    marcando={marcando} />
            ) : pdfInfo ? (
                /* Sin rutina estructurada pero CON PDF: esa ES su rutina, no un «sin
                   rutina asignada». Se enseña con su botón para abrirla. */
                <div className="surface p-10 text-center" data-testid="routine-content">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <FileText className="w-8 h-8 text-brand/60" />
                    </div>
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Tu rutina, en PDF</h2>
                    <p className="text-muted-foreground text-sm mb-6">
                        Tu entrenador te la ha preparado el {new Date(pdfInfo.uploaded_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })}.
                    </p>
                    <button onClick={abrirPdf} data-testid="routine-pdf-btn" className="btn-brand inline-flex items-center gap-2">
                        Abrir mi rutina <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
            ) : (
                <div className="surface p-10 text-center" data-testid="routine-content">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Dumbbell className="w-8 h-8 text-brand/60" />
                    </div>
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Sin rutina asignada</h2>
                    <p className="text-muted-foreground text-sm">Tu entrenador está preparando tu rutina personalizada.</p>
                </div>
            )}
        </Wrap>;
    }

    return (
        <Wrap>
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="routine-heading">Mi rutina</h1>
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
                                <p className="text-xs text-muted-foreground">{plural(r.days?.filter(d => !d.is_rest).length || 0, 'día')} de entreno</p>
                            </div>
                            {i === 0 && <span className="badge-elm">Actual</span>}
                        </div>
                    )) : <p className="text-center text-muted-foreground py-10 text-sm">No hay rutinas anteriores.</p>}
                </div>
            ) : (
                <div className="space-y-5">
                    {/* La semana (7.1 del 21-08): también con rutina estructurada, que
                        es la que pone los grupos si el PDF no trae reparto. */}
                    <SemanaDeRutina semana={semana} abrirPdf={abrirPdf} tienePdf={!!pdfInfo}
                        onMarcarHoy={marcarHoy} onSiLoHice={siLoHice} onRecuperar={recuperar}
                        marcando={marcando} />

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
                                        <p className="text-xs text-muted-foreground">{dayRoutine.cardio.duration}{dayRoutine.cardio.notes && ` - ${dayRoutine.cardio.notes}`}</p>
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

                    {/* Si además hay PDF, la estructurada manda y el PDF queda de enlace
                        secundario (mismo patrón que el botón de EntrenoPage). */}
                    {pdfInfo && (
                        <button onClick={abrirPdf} data-testid="routine-pdf-link"
                            className="w-full max-w-2xl flex items-center justify-between p-4 bg-card border border-border rounded-2xl hover:border-white/30 transition-colors">
                            <span className="flex items-center gap-2 font-bold text-foreground text-sm">
                                <FileText className="w-4 h-4 text-brand" /> Tu rutina en PDF
                            </span>
                            <ChevronRight className="w-4 h-4 text-foreground/40" />
                        </button>
                    )}
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
