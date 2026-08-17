/**
 * EL CREADOR DE RUTINAS DEL EQUIPO (17-08-2026).
 *
 * Hasta hoy una rutina solo podía nacer de la IA o escribirse a mano dentro de la ficha de
 * UN cliente. Las que Jesús escribe cada mes viven en Drive y se mandan por fuera, así que
 * la app no las conoce y cada asignación empieza de cero.
 *
 * Aquí se escribe una vez, se guarda con su nombre, y desde la ficha de cualquier cliente se
 * elige y se le asigna. Al asignarla se copia: tocarle un ejercicio a un cliente no se lo
 * cambia a los otros veinte que la tienen puesta.
 *
 * QUÉ CABE Y QUÉ NO. Cabe lo que la app ya sabe pintar -- días, ejercicios, series,
 * repeticiones, descanso -- más las notas de ejecución por ejercicio. Lo que Jesús escribe
 * de verdad (semanas con descarga, RIR serie a serie, aproximaciones con porcentajes,
 * descendentes) todavía NO cabe, y es lo primero que hay que ampliar. Esto no lo sustituye:
 * es el sitio donde ponerlo cuando quepa.
 */
import React, { useState } from 'react';
import { Plus, Trash2, X, Save, Loader2, GripVertical } from 'lucide-react';
import { toast } from 'sonner';

const SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const diasEnBlanco = () => SEMANA.map((day) => ({ day, is_rest: true, exercises: [] }));

/** Un ejercicio: lo que se escribe de él y lo que se puede quitar. */
const Ejercicio = ({ ej, onCambio, onQuitar }) => (
    <div className="rounded-lg border border-[#222] bg-[#0A0A0A] p-3 space-y-2">
        <div className="flex items-start gap-2">
            <GripVertical className="w-4 h-4 text-white/20 mt-2 shrink-0" />
            <input
                value={ej.name || ''}
                onChange={(e) => onCambio({ ...ej, name: e.target.value })}
                placeholder="Nombre del ejercicio"
                className="flex-1 bg-transparent text-white text-sm border-b border-[#222] focus:border-[#FF671F] outline-none py-1"
            />
            <button onClick={onQuitar} title="Quitar este ejercicio"
                className="text-white/25 hover:text-red-400 shrink-0 p-1">
                <Trash2 className="w-4 h-4" />
            </button>
        </div>
        <div className="grid grid-cols-3 gap-2 pl-6">
            {[
                { k: 'sets', ph: 'Series', tipo: 'number' },
                { k: 'reps', ph: 'Reps (10-12)' },
                { k: 'rest', ph: 'Descanso (90")' },
            ].map(({ k, ph, tipo }) => (
                <input key={k} type={tipo || 'text'} value={ej[k] ?? ''} placeholder={ph}
                    onChange={(e) => onCambio({
                        ...ej,
                        [k]: tipo === 'number' ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value,
                    })}
                    className="bg-[#111] border border-[#222] rounded px-2 py-1 text-white text-xs placeholder:text-white/25 focus:border-[#FF671F] outline-none" />
            ))}
        </div>
        {/* La ejecución, que es lo que de verdad distingue una rutina de una lista. */}
        <textarea value={ej.notes || ''} rows={2}
            onChange={(e) => onCambio({ ...ej, notes: e.target.value })}
            placeholder="Ejecución y notas: cómo se hace, qué mirar, qué hacer si no llega…"
            className="w-full ml-6 bg-[#111] border border-[#222] rounded px-2 py-1.5 text-white/80 text-xs placeholder:text-white/25 focus:border-[#FF671F] outline-none resize-y"
            style={{ width: 'calc(100% - 1.5rem)' }} />
    </div>
);

const EditorDeRutina = ({ api, rutina, onGuardada, onCerrar }) => {
    const [nombre, setNombre] = useState(rutina?.nombre || '');
    const [descripcion, setDescripcion] = useState(rutina?.descripcion || '');
    const [objetivo, setObjetivo] = useState(rutina?.objetivo || '');
    const [nivel, setNivel] = useState(rutina?.nivel || '');
    const [notas, setNotas] = useState(rutina?.trainer_notes || '');
    const [dias, setDias] = useState(() => {
        const base = diasEnBlanco();
        (rutina?.days || []).forEach((d) => {
            const i = SEMANA.indexOf(d.day);
            if (i >= 0) base[i] = { ...d, exercises: d.exercises || [] };
        });
        return base;
    });
    const [guardando, setGuardando] = useState(false);

    const tocarDia = (i, cambio) => setDias((ds) => ds.map((d, j) => (j === i ? { ...d, ...cambio } : d)));

    const anadirEjercicio = (i) => tocarDia(i, {
        is_rest: false,
        exercises: [...(dias[i].exercises || []), { name: '', sets: 3, reps: '', rest: '' }],
    });

    const diasConEjercicios = dias.filter((d) => (d.exercises || []).length > 0).length;
    const totalEjercicios = dias.reduce((n, d) => n + (d.exercises || []).length, 0);

    const guardar = () => {
        if (!nombre.trim()) return toast.error('Ponle un nombre a la rutina');
        if (!totalEjercicios) return toast.error('Añade al menos un ejercicio');
        const sinNombre = dias.some((d) => (d.exercises || []).some((e) => !String(e.name || '').trim()));
        if (sinNombre) return toast.error('Hay un ejercicio sin nombre');

        setGuardando(true);
        api.post('/admin/routines/biblioteca', {
            id: rutina?.id, nombre, descripcion, objetivo, nivel,
            trainer_notes: notas,
            days: dias.map((d) => ({ ...d, is_rest: (d.exercises || []).length === 0 })),
        })
            .then((r) => {
                toast.success(rutina?.id ? 'Rutina actualizada' : 'Rutina guardada en la biblioteca');
                onGuardada?.(r.data);
            })
            .catch((e) => toast.error(e?.response?.data?.detail || 'No hemos podido guardarla. Inténtalo de nuevo.'))
            .finally(() => setGuardando(false));
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-start justify-center overflow-y-auto p-4">
            <div className="bg-[#111] border border-[#222] rounded-xl w-full max-w-3xl my-4">
                <div className="flex items-center justify-between gap-3 p-4 border-b border-[#222] sticky top-0 bg-[#111] rounded-t-xl">
                    <div>
                        <p className="text-white font-semibold">{rutina?.id ? 'Editar rutina' : 'Rutina nueva'}</p>
                        <p className="text-white/40 text-xs">
                            {diasConEjercicios} {diasConEjercicios === 1 ? 'día' : 'días'} de entreno · {totalEjercicios} ejercicios
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button onClick={guardar} disabled={guardando} data-testid="guardar-rutina-biblioteca"
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg flex items-center gap-2">
                            {guardando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            Guardar
                        </button>
                        <button onClick={onCerrar} className="text-white/40 hover:text-white p-2"><X className="w-5 h-5" /></button>
                    </div>
                </div>

                <div className="p-4 space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input value={nombre} onChange={(e) => setNombre(e.target.value)}
                            placeholder="Nombre (p. ej. «Rutina del mes · Hombre · marzo»)"
                            data-testid="nombre-rutina"
                            className="sm:col-span-2 bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2 text-white text-sm placeholder:text-white/25 focus:border-[#FF671F] outline-none" />
                        <select value={objetivo} onChange={(e) => setObjetivo(e.target.value)}
                            className="bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2 text-white text-sm focus:border-[#FF671F] outline-none">
                            <option value="">Para cualquier objetivo</option>
                            <option value="volumen">Volumen</option>
                            <option value="definicion">Definición</option>
                        </select>
                        <select value={nivel} onChange={(e) => setNivel(e.target.value)}
                            className="bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2 text-white text-sm focus:border-[#FF671F] outline-none">
                            <option value="">Para cualquier nivel</option>
                            <option value="principiante">Principiante</option>
                            <option value="intermedio">Intermedio</option>
                            <option value="avanzado">Avanzado</option>
                        </select>
                        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)}
                            placeholder="Para quién es, en una línea"
                            className="sm:col-span-2 bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2 text-white text-sm placeholder:text-white/25 focus:border-[#FF671F] outline-none" />
                    </div>

                    {dias.map((d, i) => (
                        <div key={d.day} className="rounded-lg border border-[#222] p-3">
                            <div className="flex items-center justify-between gap-2 mb-2">
                                <p className="text-white text-sm font-semibold">{d.day}</p>
                                <div className="flex items-center gap-2">
                                    {(d.exercises || []).length === 0 && (
                                        <span className="text-purple-400 text-xs">Descanso</span>
                                    )}
                                    <button onClick={() => anadirEjercicio(i)}
                                        className="text-[#FF671F] hover:underline text-xs font-semibold flex items-center gap-1">
                                        <Plus className="w-3 h-3" /> ejercicio
                                    </button>
                                </div>
                            </div>
                            <div className="space-y-2">
                                {(d.exercises || []).map((ej, j) => (
                                    <Ejercicio key={j} ej={ej}
                                        onCambio={(nuevo) => tocarDia(i, {
                                            exercises: d.exercises.map((x, k) => (k === j ? nuevo : x)),
                                        })}
                                        onQuitar={() => tocarDia(i, {
                                            exercises: d.exercises.filter((_, k) => k !== j),
                                        })} />
                                ))}
                            </div>
                        </div>
                    ))}

                    <textarea value={notas} onChange={(e) => setNotas(e.target.value)} rows={3}
                        placeholder="Notas generales de la rutina, para el cliente"
                        className="w-full bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2 text-white/80 text-sm placeholder:text-white/25 focus:border-[#FF671F] outline-none resize-y" />
                </div>
            </div>
        </div>
    );
};

export default EditorDeRutina;
