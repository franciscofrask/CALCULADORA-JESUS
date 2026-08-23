/**
 * El registro del entreno del día (T3 del doc 16-08).
 *
 * Se entra desde la línea «Lo que toca hoy» de Inicio. Aquí no se planifica nada: la
 * rutina se ve en /dashboard/routine y esto es lo que HIZO, que hasta ahora no se
 * guardaba en ninguna parte y por eso ningún conteo de entrenos era fiable.
 *
 * Lo que escriba aquí va a su Diario (T5) y la línea de Inicio pasa a «✓ hecho».
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Loader2, Plus, Star, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";

const Card = ({ className = '', children }) => (
    <div className={`bg-card border border-border rounded-2xl ${className}`}>{children}</div>
);

// «Jueves, 20 de agosto», como en el documento.
const fechaLarga = (iso) => {
    const d = iso ? new Date(`${iso}T12:00:00`) : new Date();
    const texto = d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
    return texto.charAt(0).toUpperCase() + texto.slice(1);
};

const filaVacia = () => ({ ejercicio: '', reps: '', peso_kg: '' });

const EntrenoPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();

    const [cargando, setCargando] = useState(true);
    const [guardando, setGuardando] = useState(false);
    // ¿Hay rutina en PDF subida por su entrenador? El botón solo sale si existe.
    const [hayPdf, setHayPdf] = useState(false);
    useEffect(() => {
        api.get('/routines/pdf/info').then(r => setHayPdf(!!r.data?.hay)).catch(() => {});
    }, [api]);
    const [dia, setDia] = useState(null);
    const [hecho, setHecho] = useState(null);
    const [estrellas, setEstrellas] = useState(0);
    const [nota, setNota] = useState('');
    const [pesos, setPesos] = useState([filaVacia()]);
    const [compartida, setCompartida] = useState(false);

    const cargar = useCallback(async () => {
        try {
            // Con el día del RELOJ DEL CLIENTE (bloque F, 23-08): registra SU hoy.
            const { data } = await api.get(`/workout-logs/hoy?fecha=${new Date().toLocaleDateString('en-CA')}`);
            setDia(data || null);
            const log = data?.log;
            if (log) {
                setHecho(!!log.hecho);
                setEstrellas(log.estrellas || 0);
                setNota(log.nota || '');
                setCompartida(!!log.compartida);
            }
            // Los pesos de la última vez que le tocó esta misma rutina: la tabla empieza
            // donde la dejó, que es justo para lo que sirve («de dónde partir»).
            const previos = data?.pesos_referencia || [];
            setPesos(previos.length
                ? previos.map(p => ({
                    ejercicio: p.ejercicio || '',
                    reps: p.reps ?? '',
                    peso_kg: p.peso_kg ?? '',
                }))
                : [filaVacia()]);
        } catch (err) {
            console.error('No se pudo cargar el entreno de hoy:', err?.response?.data || err);
            toast.error('No hemos podido cargar tu entreno de hoy. Inténtalo en un momento.');
        } finally {
            setCargando(false);
        }
    }, [api]);

    useEffect(() => { cargar(); }, [cargar]);

    const cambiarFila = (i, campo, valor) => {
        setPesos(prev => prev.map((f, n) => (n === i ? { ...f, [campo]: valor } : f)));
    };

    const guardar = async () => {
        if (hecho === null) {
            return toast.error('Dinos si lo has completado.');
        }
        setGuardando(true);
        try {
            await api.post('/workout-logs', {
                // Su día (bloque F): el entreno de las 00:30 de su reloj es de SU hoy.
                fecha: new Date().toLocaleDateString('en-CA'),
                hecho,
                tipo: dia?.tipo || 'entreno',
                estrellas: estrellas > 0 ? estrellas : null,
                nota: nota.trim() || null,
                // Las filas a medias no se guardan: una fila sin ejercicio no dice nada, y
                // el peso sin número tampoco sirve de referencia.
                pesos: pesos
                    .filter(f => (f.ejercicio || '').trim())
                    .map(f => ({
                        ejercicio: f.ejercicio.trim(),
                        reps: f.reps === '' ? null : parseInt(f.reps, 10),
                        peso_kg: f.peso_kg === '' ? null : parseFloat(String(f.peso_kg).replace(',', '.')),
                    })),
                compartida,
                dia_rutina: dia?.dia_rutina || null,
            });
            toast.success('Entreno guardado.');
            navigate('/dashboard');
        } catch (err) {
            console.error('No se pudo guardar el entreno:', err?.response?.data || err);
            toast.error('No hemos podido guardar tu entreno. Inténtalo en un momento.');
        } finally {
            setGuardando(false);
        }
    };

    if (cargando) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[760px] mx-auto">
                <div className="animate-pulse space-y-4">
                    <div className="h-20 bg-muted rounded-2xl" />
                    <div className="h-64 bg-muted rounded-2xl" />
                </div>
            </div>
        );
    }

    const cabecera = dia?.dia_rutina || 'Entreno de hoy';
    const semana = dia?.semana;
    const numero = dia?.numero_rutina;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[760px] mx-auto space-y-5 animate-fade-in" data-testid="entreno-page">
            <button onClick={() => navigate('/dashboard')} data-testid="entreno-volver"
                className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground">
                <ChevronLeft className="w-4 h-4" /> Inicio
            </button>

            <header>
                <p className="text-sm text-muted-foreground">{fechaLarga(dia?.fecha)}</p>
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none mt-1"
                    data-testid="entreno-heading">
                    {cabecera}
                </h1>
                {(semana || numero) && (
                    <p className="text-sm text-muted-foreground mt-1.5" data-testid="entreno-subtitulo">
                        {semana ? `Semana ${semana}` : ''}{semana && numero ? ' · ' : ''}{numero ? `rutina ${numero}` : ''}
                    </p>
                )}
            </header>

            {/* «Ver la rutina» y, si su entrenador la subió, el PDF (bloque 11, doc
                19-08). Solo sale si existe: ofrecer una descarga que no existe es peor
                que no ofrecerla. Se abre vía blob porque el visor no manda el token. */}
            <button onClick={() => navigate('/dashboard/routine')} data-testid="entreno-ver-rutina"
                className="w-full flex items-center justify-between p-4 bg-card border border-border rounded-2xl hover:border-white/30 transition-colors">
                <span className="font-bold text-foreground">Ver la rutina</span>
                <ChevronRight className="w-4 h-4 text-foreground/40" />
            </button>
            {hayPdf && (
                <button data-testid="entreno-pdf-rutina"
                    onClick={async () => {
                        try {
                            const r = await api.get('/routines/pdf', { responseType: 'blob' });
                            window.open(URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' })), '_blank');
                        } catch { toast.error('No hemos podido abrir tu rutina. Inténtalo en un momento.'); }
                    }}
                    className="w-full flex items-center justify-between p-4 bg-card border border-border rounded-2xl hover:border-white/30 transition-colors">
                    <span className="font-bold text-foreground">Tu rutina en PDF</span>
                    <ChevronRight className="w-4 h-4 text-foreground/40" />
                </button>
            )}

            <Card className="p-5 space-y-6">
                {/* ¿Lo has completado? */}
                <div>
                    <span className="text-sm text-foreground/70 mb-2 block">¿Lo has completado?</span>
                    <div className="grid grid-cols-2 gap-2">
                        {[{ v: true, l: 'Hecho' }, { v: false, l: 'No hecho' }].map(({ v, l }) => {
                            const activo = hecho === v;
                            const tono = activo
                                ? (v ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400' : 'border-brand bg-brand/10 text-brand')
                                : 'border-border bg-muted text-foreground/50 hover:border-white/30';
                            return (
                                <button key={l} type="button" onClick={() => setHecho(v)}
                                    data-testid={`entreno-${v ? 'hecho' : 'no-hecho'}`}
                                    className={`py-3 rounded-xl border font-bold text-sm transition-all ${tono}`}>
                                    {l}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Sensaciones */}
                <div>
                    <span className="text-sm text-foreground/70 block">Sensaciones</span>
                    <p className="text-[11px] text-foreground/40 mt-0.5 mb-2">Cómo te has sentido entrenando</p>
                    <div className="flex gap-1.5">
                        {[1, 2, 3, 4, 5].map(v => (
                            <button key={v} type="button" onClick={() => setEstrellas(v === estrellas ? 0 : v)}
                                data-testid={`entreno-estrella-${v}`} aria-label={`${v} de 5`}
                                className="p-1.5 rounded-lg hover:bg-muted transition-colors">
                                <Star className={`w-7 h-7 ${v <= estrellas ? 'text-[#FF671F] fill-[#FF671F]' : 'text-foreground/25'}`} />
                            </button>
                        ))}
                    </div>
                </div>

                {/* Algo que destacar */}
                <div>
                    <span className="text-sm text-foreground/70 mb-2 block">Algo que destacar</span>
                    <textarea rows={3} value={nota} onChange={e => setNota(e.target.value)}
                        data-testid="entreno-nota"
                        placeholder="Lo que quieras acordarte de este entreno."
                        className={inputCls + ' resize-none'} />
                </div>

                {/* Pesos de referencia */}
                <div>
                    <span className="text-sm text-foreground/70 block">Pesos de referencia</span>
                    <p className="text-[11px] text-foreground/40 mt-0.5 mb-2">
                        Opcional. Para que sepas de dónde partir en futuras rutinas.
                    </p>
                    <div className="grid grid-cols-[1fr_64px_84px_32px] gap-2 mb-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/40">ejercicio</span>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/40">reps</span>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/40">última serie</span>
                        <span />
                    </div>
                    <div className="space-y-2">
                        {pesos.map((f, i) => (
                            <div key={i} className="grid grid-cols-[1fr_64px_84px_32px] gap-2 items-center">
                                <input value={f.ejercicio} list="entreno-ejercicios"
                                    onChange={e => cambiarFila(i, 'ejercicio', e.target.value)}
                                    data-testid={`entreno-ejercicio-${i}`}
                                    className={inputCls} />
                                <input type="number" min="0" inputMode="numeric" value={f.reps}
                                    onChange={e => cambiarFila(i, 'reps', e.target.value)}
                                    data-testid={`entreno-reps-${i}`}
                                    className={inputCls} />
                                <input type="number" min="0" step="0.5" inputMode="decimal" value={f.peso_kg}
                                    onChange={e => cambiarFila(i, 'peso_kg', e.target.value)}
                                    data-testid={`entreno-peso-${i}`}
                                    placeholder="kg"
                                    className={inputCls} />
                                <button type="button" onClick={() => setPesos(prev => (prev.length > 1 ? prev.filter((_, n) => n !== i) : [filaVacia()]))}
                                    aria-label="Quitar la fila"
                                    className="w-8 h-8 rounded-lg flex items-center justify-center text-foreground/30 hover:text-foreground hover:bg-muted transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                    {/* Los ejercicios del día, para escribir el nombre sin teclearlo entero. */}
                    <datalist id="entreno-ejercicios">
                        {(dia?.ejercicios || []).map(n => <option key={n} value={n} />)}
                    </datalist>
                    <button type="button" onClick={() => setPesos(prev => [...prev, filaVacia()])}
                        data-testid="entreno-anadir-ejercicio"
                        className="mt-3 flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline underline-offset-4">
                        <Plus className="w-4 h-4" /> Añadir ejercicio
                    </button>
                </div>

                {/* Compartir con nosotros */}
                <label className="flex items-center gap-3 cursor-pointer">
                    <input type="checkbox" checked={compartida} onChange={e => setCompartida(e.target.checked)}
                        data-testid="entreno-compartir"
                        className="w-4 h-4 accent-[#FF671F]" />
                    <span className="text-sm text-foreground/80">Compartir con nosotros</span>
                </label>

                <button onClick={guardar} disabled={guardando} data-testid="entreno-guardar"
                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                    {guardando && <Loader2 className="w-4 h-4 animate-spin" />} Guardar
                </button>
            </Card>
        </div>
    );
};

export default EntrenoPage;
