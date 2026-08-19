/**
 * EL FORMULARIO DE ASIGNAR TAREA (doc del 19-08, apartado 05).
 *
 *     «Cuatro campos y ninguno más: a quién, qué, para cuándo, sobre quién.
 *      "Sobre quién" se rellena solo si la abriste desde una ficha.»
 *
 * Es UN componente porque el botón sale de tres sitios -- la ficha de un cliente, una
 * lista a varios de golpe, y suelto desde el panel -- y tres formularios distintos
 * acabarían pidiendo cosas distintas.
 *
 * Props:
 *   abierto / onClose     el modal
 *   sobre                 [{id, nombre}] · los clientes sobre los que va (0, 1 o varios)
 *   onCreada              callback tras crear (para refrescar listas)
 */
import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { toast } from 'sonner';
import { mensajeDeError } from '../lib/mensajeDeError';

const AsignarTarea = ({ abierto, onClose, sobre = [], onCreada }) => {
    const { api, user } = useAuth();
    const [equipo, setEquipo] = useState([]);
    const [aQuien, setAQuien] = useState('');
    const [que, setQue] = useState('');
    const [paraCuando, setParaCuando] = useState('');
    const [guardando, setGuardando] = useState(false);

    useEffect(() => {
        if (!abierto) return;
        api.get('/admin/tareas/equipo')
            .then(r => {
                setEquipo(r.data || []);
                // Por defecto, uno mismo: la mitad de las tareas son «me lo apunto yo».
                if (!aQuien && (r.data || []).some(u => u.id === user?.id)) setAQuien(user.id);
            })
            .catch(() => setEquipo([]));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [abierto]);

    const guardar = async () => {
        if (!aQuien || !que.trim()) {
            toast.error('Faltan el quién o el qué.');
            return;
        }
        setGuardando(true);
        try {
            const r = await api.post('/admin/tareas', {
                a_quien: aQuien,
                que: que.trim(),
                para_cuando: paraCuando || null,
                sobre_quienes: sobre.map(s => s.id),
            });
            const n = r.data?.creadas || 1;
            toast.success(n > 1 ? `${n} tareas asignadas` : 'Tarea asignada');
            setQue(''); setParaCuando('');
            onCreada?.();
            onClose?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo asignar la tarea'));
        } finally {
            setGuardando(false);
        }
    };

    return (
        <Dialog open={abierto} onOpenChange={(v) => !v && onClose?.()}>
            <DialogContent className="bg-[#111] border-[#333] text-white max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-white" style={{ fontFamily: 'Barlow Condensed' }}>
                        ASIGNAR TAREA
                    </DialogTitle>
                </DialogHeader>
                <div className="space-y-3">
                    <div>
                        <Label className="text-white/60 text-xs uppercase tracking-wider">A quién</Label>
                        <select value={aQuien} onChange={e => setAQuien(e.target.value)}
                            data-testid="tarea-a-quien"
                            className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                            <option value="">Elegir…</option>
                            {equipo.map(u => (
                                <option key={u.id} value={u.id}>
                                    {u.name}{u.id === user?.id ? ' (yo)' : ''}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <Label className="text-white/60 text-xs uppercase tracking-wider">Qué</Label>
                        <Input value={que} onChange={e => setQue(e.target.value)}
                            placeholder="Contactar para renovación"
                            data-testid="tarea-que"
                            className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                    </div>
                    <div>
                        <Label className="text-white/60 text-xs uppercase tracking-wider">Para cuándo</Label>
                        <Input type="date" value={paraCuando} onChange={e => setParaCuando(e.target.value)}
                            data-testid="tarea-para-cuando"
                            className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                        <p className="text-[11px] text-white/30 mt-1">Sin fecha, cuenta como para hoy.</p>
                    </div>
                    <div>
                        <Label className="text-white/60 text-xs uppercase tracking-wider">Sobre quién</Label>
                        <p className="text-sm text-white/80 mt-1" data-testid="tarea-sobre-quien">
                            {sobre.length === 0 && <span className="text-white/40">Nadie: es una tarea suelta.</span>}
                            {sobre.length === 1 && sobre[0].nombre}
                            {sobre.length > 1 && `${sobre.length} clientes: ${sobre.slice(0, 3).map(s => s.nombre).join(', ')}${sobre.length > 3 ? '…' : ''}`}
                        </p>
                        {sobre.length > 1 && (
                            <p className="text-[11px] text-white/30 mt-0.5">
                                Se crea una tarea por cliente: cada una se marca hecha por su cuenta.
                            </p>
                        )}
                    </div>
                </div>
                <DialogFooter>
                    <Button onClick={guardar} disabled={guardando} data-testid="tarea-asignar-btn"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold">
                        {guardando ? 'Asignando…' : 'Asignar'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

export default AsignarTarea;
