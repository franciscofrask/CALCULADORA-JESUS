import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { toast } from 'sonner';
import { Save, Loader2, Target } from 'lucide-react';
import { OBJETIVOS, definicionDelObjetivo, objetivoVisible, normalizarObjetivo } from '../../lib/objetivos';
import { mensajeDeError } from '../../lib/mensajeDeError';

/**
 * EL OBJETIVO DEL CLIENTE, PUESTO POR EL ENTRENADOR (doc de Jesús del 2-09, fase 2;
 * decisión de Francisco del 4-09).
 *
 * Hasta hoy la ficha pintaba `goal` a secas, que salía del cuestionario de alta y el cliente
 * reescribía cada mes desde el reporte. Jesús: «los objetivos los pones tú, no él», con una
 * lista cerrada de seis para poder comparar después. Y dos niveles: el DEL CICLO, que se pone
 * al abrirlo, y el ACTUAL, que se pone en cada feedback y matiza al otro. «Tonificación con
 * foco glúteo» son dos campos, el objetivo y el foco, para no fabricar un objetivo por zona.
 *
 * Mientras el entrenador no haya puesto ninguno (`objetivo_actual` a null), el actual se
 * enseña con el `goal` viejo traducido y marcado «sin confirmar»: guardar tal cual lo
 * confirma. Si no hay ciclo abierto, el servidor devuelve 409 con su frase para el objetivo
 * del ciclo, y aquí se guarda igual lo demás: el actual y el foco no dependen del ciclo.
 */
const SELECT = 'w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1 disabled:opacity-40';

const desdeElPerfil = (profile, ciclo) => ({
    objetivo_ciclo: normalizarObjetivo(ciclo?.objetivo) || '',
    objetivo_actual: objetivoVisible(profile) || '',
    foco: profile?.foco || '',
});

const ObjetivoDelCliente = ({ api, clientId, profile, ciclo, onGuardado }) => {
    const [form, setForm] = useState(() => desdeElPerfil(profile, ciclo));
    const [guardando, setGuardando] = useState(false);
    // La frase del 409: se queda a la vista hasta que la ficha se recargue con un ciclo.
    const [sinCiclo, setSinCiclo] = useState(null);

    const objetivoActualGuardado = normalizarObjetivo(profile?.objetivo_actual) || '';
    const objetivoCicloGuardado = normalizarObjetivo(ciclo?.objetivo) || '';
    const sinConfirmar = !objetivoActualGuardado && !!form.objetivo_actual;

    // Cuando la ficha se recarga (tras guardar, o al cambiar de cliente) el formulario vuelve
    // a lo guardado: si no, lo que se ve y lo que hay se separan sin avisar.
    useEffect(() => {
        setForm(desdeElPerfil(profile, ciclo));
        if (ciclo) setSinCiclo(null);
    }, [clientId, objetivoActualGuardado, objetivoCicloGuardado, profile?.foco, ciclo]); // eslint-disable-line react-hooks/exhaustive-deps

    const tocado = form.objetivo_ciclo !== objetivoCicloGuardado
        || form.objetivo_actual !== objetivoActualGuardado
        || (form.foco || '').trim() !== (profile?.foco || '');

    const guardar = async () => {
        // El actual solo viaja si hay uno: el servidor no admite quitarlo (un objetivo vacío
        // está fuera de la lista), y el foco vacío sí significa quitarlo.
        const body = { foco: (form.foco || '').trim() };
        if (form.objetivo_actual) body.objetivo_actual = form.objetivo_actual;
        // El del ciclo solo viaja si se ha puesto y si el servidor no ha dicho ya que no hay
        // ciclo: mandarlo otra vez sería tropezar con el mismo 409.
        const mandaCiclo = !!form.objetivo_ciclo && !sinCiclo && form.objetivo_ciclo !== objetivoCicloGuardado;
        setGuardando(true);
        try {
            try {
                await api.put(`/admin/clients/${clientId}/objetivo`, mandaCiclo ? { ...body, objetivo_ciclo: form.objetivo_ciclo } : body);
                toast.success('Objetivo guardado');
            } catch (e) {
                if (e?.response?.status !== 409 || !mandaCiclo) throw e;
                // Sin ciclo abierto: se enseña su frase y se guarda lo que sí se puede.
                setSinCiclo(mensajeDeError(e, 'No hay un ciclo abierto: el objetivo del ciclo se pone al abrirlo.'));
                await api.put(`/admin/clients/${clientId}/objetivo`, body);
                toast.success('Objetivo actual y foco guardados', { description: 'El del ciclo se queda para cuando haya ciclo.' });
            }
            onGuardado?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo guardar el objetivo'));
        } finally { setGuardando(false); }
    };

    const definicionCiclo = definicionDelObjetivo(form.objetivo_ciclo);

    return (
        <div className="mt-5 pt-5 border-t border-[#222]" data-testid="objetivo-del-cliente">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-[#FF671F]" /> Objetivo
                </p>
                <div className="flex items-center gap-2">
                    {sinConfirmar && <Badge className="border-0 text-[10px] bg-[#FF671F]/20 text-[#FF671F]" data-testid="objetivo-sin-confirmar">sin confirmar</Badge>}
                    {tocado && !sinConfirmar && <Badge className="border-0 text-[10px] bg-[#FF671F]/20 text-[#FF671F]">sin guardar</Badge>}
                    <Button size="sm" onClick={guardar} disabled={guardando || (!tocado && !sinConfirmar)}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs disabled:opacity-40" data-testid="guardar-objetivo">
                        {guardando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><Save className="w-3.5 h-3.5 mr-1" />Guardar objetivo</>}
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <Label className="text-white/60 text-xs">Objetivo del ciclo</Label>
                    <select value={form.objetivo_ciclo} disabled={!!sinCiclo} data-testid="objetivo-ciclo"
                        onChange={e => setForm(f => ({ ...f, objetivo_ciclo: e.target.value }))} className={SELECT}>
                        <option value="">Sin poner</option>
                        {OBJETIVOS.map(o => <option key={o.clave} value={o.clave}>{o.nombre}</option>)}
                    </select>
                    {definicionCiclo && <p className="text-[11px] text-white/40 mt-1" data-testid="objetivo-ciclo-definicion">{definicionCiclo}</p>}
                </div>
                <div>
                    <Label className="text-white/60 text-xs">Objetivo actual</Label>
                    <select value={form.objetivo_actual} data-testid="objetivo-actual"
                        onChange={e => setForm(f => ({ ...f, objetivo_actual: e.target.value }))} className={SELECT}>
                        <option value="">Sin poner</option>
                        {OBJETIVOS.map(o => <option key={o.clave} value={o.clave}>{o.nombre}</option>)}
                    </select>
                    {sinConfirmar && <p className="text-[11px] text-white/40 mt-1">Viene de su cuestionario. Guarda para confirmarlo.</p>}
                </div>
                <div>
                    <Label className="text-white/60 text-xs">Foco</Label>
                    <Input value={form.foco} onChange={e => setForm(f => ({ ...f, foco: e.target.value }))}
                        placeholder="glúteo, brazos..." maxLength={60} data-testid="objetivo-foco"
                        className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                </div>
            </div>

            {sinCiclo && <p className="text-[11px] text-[#FF671F] mt-2" data-testid="objetivo-sin-ciclo">{sinCiclo}</p>}
            {ciclo?.bloque != null && ciclo?.semana != null && (
                <p className="text-[10px] text-white/30 mt-2" data-testid="objetivo-bloque">
                    Va por el bloque {ciclo.bloque} · semana {ciclo.semana}{ciclo.semanas ? ` de ${ciclo.semanas}` : ''}
                </p>
            )}
        </div>
    );
};

export default ObjetivoDelCliente;
