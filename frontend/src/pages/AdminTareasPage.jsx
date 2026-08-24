/**
 * TAREAS (doc del 19-08, apartado 05).
 *
 * Lo que esta persona tiene hoy, lo vencido, lo que viene, y lo que asignó a otros: «el
 * que la asignó ve lo pendiente y lo que se ha pasado de fecha, sin preguntar a nadie».
 * Las automáticas se generan solas al cargar (salen del calendario y de los datos) y se
 * distinguen por su origen; marcarlas hechas es lo que las apaga.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { CheckCircle2, ClipboardList, Plus, RotateCcw, Trash2 } from 'lucide-react';
import AsignarTarea from '../components/AsignarTarea';
import { useConfirm } from '../components/ui/confirm';
import { mensajeDeError } from '../lib/mensajeDeError';

const Fecha = ({ iso }) => iso
    ? <span>{new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</span>
    : null;

const Tarea = ({ t, onHecha, onIrAlCliente, onBorrar, puedeBorrar, mostrarQuien = false }) => (
    <div className="flex items-start gap-3 py-2.5 border-b border-[#1c1c1c] last:border-0"
        data-testid={`tarea-${t.id}`}>
        <button onClick={() => onHecha(t)} title={t.hecha ? 'Deshacer' : 'Marcar hecha'}
            data-testid={`tarea-hecha-${t.id}`}
            className={`mt-0.5 ${t.hecha ? 'text-emerald-500' : 'text-white/25 hover:text-[#FF671F]'}`}>
            <CheckCircle2 className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
            <p className={`text-sm ${t.hecha ? 'text-white/40 line-through' : 'text-white/90'}`}>{t.que}</p>
            <p className="text-[11px] text-white/35 flex flex-wrap gap-x-2">
                {mostrarQuien && t.a_quien_nombre && <span>para {t.a_quien_nombre}</span>}
                {t.sobre_quien_nombre && (
                    <button className="text-[#FF671F]/80 hover:text-[#FF671F]"
                        onClick={() => onIrAlCliente(t)}>
                        {t.sobre_quien_nombre}
                    </button>
                )}
                {t.para_cuando && <span>para el <Fecha iso={t.para_cuando} /></span>}
                {t.origen !== 'manual' && <span className="text-white/25">· automática</span>}
                {t.creada_por_nombre && t.origen === 'manual' && <span>· la pidió {t.creada_por_nombre}</span>}
                {t.hecha && t.hecha_por_nombre && <span>· la hizo {t.hecha_por_nombre}</span>}
            </p>
        </div>
        {/* BORRAR LA QUE SE ESCRIBIÓ MAL. Hasta ahora lo único que se podía hacer con una
            tarea puesta por error era marcarla hecha, o sea mentir en el registro que luego
            se lee en la ficha del cliente. El botón solo sale donde el backend deja borrar
            (manual y tuya, o admin): pintarlo donde va a dar 403 es peor que no tenerlo. */}
        {puedeBorrar?.(t) && (
            <button onClick={() => onBorrar(t)} title="Borrar la tarea"
                data-testid={`tarea-borrar-${t.id}`}
                className="mt-0.5 text-white/20 hover:text-red-400">
                <Trash2 className="w-4 h-4" />
            </button>
        )}
    </div>
);

const Bloque = ({ titulo, tono, tareas, ...resto }) => {
    if (!tareas?.length) return null;
    return (
        <div>
            <p className={`text-xs uppercase tracking-wider font-bold mb-1 ${tono}`}>
                {titulo} ({tareas.length})
            </p>
            {tareas.map(t => <Tarea key={t.id} t={t} {...resto} />)}
        </div>
    );
};

const AdminTareasPage = () => {
    const { api, user } = useAuth();
    const { confirm } = useConfirm();
    const navigate = useNavigate();
    const [datos, setDatos] = useState(null);
    const [modal, setModal] = useState(false);
    const [verHechas, setVerHechas] = useState(false);

    const cargar = useCallback(() => {
        api.get('/admin/tareas').then(r => setDatos(r.data)).catch(e =>
            toast.error(mensajeDeError(e, 'No se pudieron cargar las tareas')));
    }, [api]);

    useEffect(() => { cargar(); }, [cargar]);

    const marcar = async (t) => {
        try {
            await api.put(`/admin/tareas/${t.id}/hecha`, { hecha: !t.hecha });
            cargar();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo marcar'));
        }
    };
    // Las mismas reglas que el endpoint (routes/tareas.py): las automáticas no se borran
    // -- el sistema las volvería a crear -- y una manual solo la borra quien la escribió,
    // salvo que seas admin.
    const puedeBorrar = (t) => t.origen === 'manual'
        && (t.creada_por === user?.id || user?.role === 'admin');
    const borrar = async (t) => {
        if (!await confirm({
            title: '¿Borrar esta tarea?',
            description: 'Desaparece de la lista de quien la tenía. Si ya se hizo, márcala hecha en vez de borrarla.',
            confirmLabel: 'Borrar', danger: true,
        })) return;
        try {
            await api.delete(`/admin/tareas/${t.id}`);
            toast.success('Tarea borrada');
            cargar();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo borrar la tarea'));
        }
    };
    const irAlCliente = (t) => t.sobre_quien && navigate(`/admin/clients/${t.sobre_quien}`);
    const props = { onHecha: marcar, onIrAlCliente: irAlCliente, onBorrar: borrar, puedeBorrar };

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2 text-white flex items-center gap-2">
                        <ClipboardList className="w-6 h-6 text-[#FF671F]" />TAREAS
                    </h1>
                    <p className="text-white/50 text-sm">
                        Lo tuyo de hoy, lo vencido y lo que asignaste. Las automáticas salen del
                        calendario y de los datos.
                    </p>
                </div>
                <Button onClick={() => setModal(true)} data-testid="nueva-tarea"
                    className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold">
                    <Plus className="w-4 h-4 mr-1" /> Nueva tarea
                </Button>
            </div>

            {!datos ? (
                <div className="p-8 text-center">
                    <div className="animate-spin w-8 h-8 border-2 border-[#FF671F] border-t-transparent rounded-full mx-auto" />
                </div>
            ) : (
                <div className="grid lg:grid-cols-2 gap-6 items-start">
                    <Card className="bg-[#111] border-[#222]">
                        <CardContent className="p-4 space-y-4" data-testid="mis-tareas">
                            <p className="text-white font-bold" style={{ fontFamily: 'Barlow Condensed' }}>MIS TAREAS</p>
                            <Bloque titulo="Vencidas" tono="text-red-400" tareas={datos.vencidas} {...props} />
                            <Bloque titulo="Para hoy" tono="text-[#FF671F]" tareas={datos.hoy} {...props} />
                            <Bloque titulo="Lo que viene" tono="text-white/40" tareas={datos.proximas} {...props} />
                            {!datos.vencidas?.length && !datos.hoy?.length && !datos.proximas?.length && (
                                <p className="text-white/40 text-sm">Nada pendiente. Bien.</p>
                            )}
                            <button onClick={() => setVerHechas(v => !v)}
                                className="text-xs text-white/40 hover:text-white flex items-center gap-1">
                                <RotateCcw className="w-3 h-3" /> {verHechas ? 'Ocultar hechas' : `Hechas recientes (${datos.hechas?.length || 0})`}
                            </button>
                            {verHechas && datos.hechas?.map(t => <Tarea key={t.id} t={t} {...props} />)}
                        </CardContent>
                    </Card>

                    <Card className="bg-[#111] border-[#222]">
                        <CardContent className="p-4 space-y-4" data-testid="tareas-asignadas">
                            <p className="text-white font-bold" style={{ fontFamily: 'Barlow Condensed' }}>LAS QUE ASIGNÉ</p>
                            <Bloque titulo="Pasadas de fecha" tono="text-red-400"
                                tareas={datos.asignadas?.vencidas} mostrarQuien {...props} />
                            <Bloque titulo="Pendientes" tono="text-white/40"
                                tareas={[...(datos.asignadas?.hoy || []), ...(datos.asignadas?.proximas || [])]}
                                mostrarQuien {...props} />
                            {!datos.asignadas?.vencidas?.length && !datos.asignadas?.hoy?.length
                                && !datos.asignadas?.proximas?.length && (
                                <p className="text-white/40 text-sm">No has asignado nada que siga pendiente.</p>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            <AsignarTarea abierto={modal} onClose={() => setModal(false)} sobre={[]} onCreada={cargar} />
        </div>
    );
};

export default AdminTareasPage;
