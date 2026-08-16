import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Layers, Pencil, RotateCcw, Check, X } from 'lucide-react';
import { queIncluyeElPlan, ACOMPANAMIENTO_OPTS, FRECUENCIA_CONTACTO_OPTS as FRECUENCIA_OPTS, etiquetaAcompanamiento, etiquetaFrecuencia, etiquetaCalculadora } from '../lib/planAccess';
import { mensajeDeError } from '../lib/mensajeDeError';

// Orden y etiquetas de las categorías (pestañas del catálogo original).
const ESTADOS = [
    { key: 'activo', label: 'Planes activos', hint: 'Se venden hoy' },
    { key: 'legacy', label: 'Planes legacy', hint: 'Ya no se venden; se respetan a quien los tiene' },
    { key: 'especial', label: 'Planes especiales', hint: 'A medida, pactados con el CEO' },
    { key: 'complemento', label: 'Productos complementarios', hint: 'Compra suelta, no es una membresía' },
];

const CALCULADORA_OPTS = [
    { value: 'personalizado', label: 'Personalizado (lo ajusta el entrenador)' },
    { value: 'autogestion', label: 'Autogestión' },
    { value: 'sin_ajuste', label: 'Sin ajuste activo' },
];
const RUTINA_OPTS = [
    { value: 'personalizada', label: 'Personalizada' },
    { value: 'del_mes', label: 'Del mes' },
    { value: 'opcional', label: 'Opcional' },
    { value: 'ninguna', label: 'Ninguna' },
];
const REPORTE_OPTS = ['quincenal', 'mensual', 'semanal'];
const CICLO_OPTS = ['mensual', 'trimestral', 'bimestral', 'semestral', 'unico', 'variable'];

const Dot = ({ on }) => (
    <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full ${on ? 'bg-green-500/20 text-green-500' : 'bg-white/10 text-white/30'}`}>
        {on ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
    </span>
);

const HabRow = ({ label, value }) => (
    <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-white/50">{label}</span>
        <span className="text-white/80 font-medium">{value}</span>
    </div>
);

// Los interruptores de las pantallas nuevas (doc 16-08) y la frase del día. Viven en
// db.app_settings y se tocan aquí para poder apagar una pantalla SIN desplegar.
const PANTALLAS_APP = [
    { clave: 'frase_del_dia', label: 'La frase del día en Inicio' },
    { clave: 't1_inicio_nuevo', label: 'Inicio nuevo (Lo que toca hoy)' },
    { clave: 't2_suplementos', label: 'Suplementos del cliente' },
    { clave: 't3_entreno', label: 'Entreno (rutina y registro)' },
    { clave: 't4_cierre_nuevo', label: 'Cierre del día nuevo' },
    { clave: 't5_diario', label: 'El Diario' },
    { clave: 't6_evolucion', label: 'Evolución completa del cliente' },
    { clave: 't10_avisos_nuevos', label: 'Los avisos nuevos' },
];

const PantallasDeLaApp = () => {
    const { api } = useAuth();
    const [ajustes, setAjustes] = useState(null);
    const [frase, setFrase] = useState('');
    const [guardandoFrase, setGuardandoFrase] = useState(false);

    useEffect(() => {
        api.get('/admin/settings')
            .then((res) => setAjustes(res.data || null))
            .catch(() => toast.error('No se pudieron cargar los ajustes de la app'));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al entrar
    }, []);

    const alternar = async (clave) => {
        const nuevo = !ajustes?.pantallas?.[clave];
        try {
            const res = await api.put('/admin/settings', { pantallas: { [clave]: nuevo } });
            setAjustes(res.data);
        } catch (e) {
            toast.error('No se pudo guardar el cambio');
        }
    };

    const guardarFrase = async () => {
        if (!frase.trim()) return;
        setGuardandoFrase(true);
        try {
            const res = await api.put('/admin/settings', { frase_del_dia: { texto: frase.trim() } });
            setAjustes(res.data);
            setFrase('');
            toast.success('Frase del día guardada');
        } catch (e) {
            toast.error('No se pudo guardar la frase');
        } finally {
            setGuardandoFrase(false);
        }
    };

    if (!ajustes) return null;

    return (
        <Card className="bg-[#111] border-[#2a2a2a]">
            <CardContent className="p-4 space-y-4">
                <div>
                    <h2 className="text-base font-bold text-white">Pantallas de la app</h2>
                    <p className="text-xs text-white/50">Apagar aquí quita la pantalla a todos los clientes al momento, sin desplegar.</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                    {PANTALLAS_APP.map(({ clave, label }) => {
                        const on = !!ajustes.pantallas?.[clave];
                        return (
                            <button
                                key={clave}
                                type="button"
                                onClick={() => alternar(clave)}
                                className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${on ? 'border-green-500/40 bg-green-500/10 text-white' : 'border-[#333] bg-black/30 text-white/60'}`}
                            >
                                <span>{label}</span>
                                <Dot on={on} />
                            </button>
                        );
                    })}
                </div>
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">
                        Frase del día
                        {ajustes.frase_del_dia?.texto ? (
                            <span className="ml-2 text-white/40 normal-case">ahora: «{ajustes.frase_del_dia.texto}» ({ajustes.frase_del_dia.fecha})</span>
                        ) : (
                            <span className="ml-2 text-white/40">todavía no hay ninguna</span>
                        )}
                    </Label>
                    <div className="flex gap-2">
                        <Input
                            value={frase}
                            onChange={(e) => setFrase(e.target.value)}
                            placeholder="El único secreto que tiene esto es no dejarlo."
                            className="bg-black/30 border-[#333] text-white text-sm"
                        />
                        <Button onClick={guardarFrase} disabled={guardandoFrase || !frase.trim()} className="bg-[#FF671F] hover:bg-[#e55b1a] text-white">
                            Guardar
                        </Button>
                    </div>
                    <p className="text-[11px] text-white/40">Si un día no hay frase nueva, el cliente sigue viendo la última.</p>
                </div>
            </CardContent>
        </Card>
    );
};

const PlanCard = ({ plan, onEdit }) => {
    const h = plan.habilitaciones || {};
    const sem = plan.ciclo?.semanas;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                    <div>
                        <p className="text-white font-bold leading-tight">{plan.name}</p>
                        <p className="text-[11px] text-white/40 font-mono">{plan.code}</p>
                    </div>
                    <div className="flex items-center gap-2">
                        {plan.has_override && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold">editado</span>
                        )}
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-white/60 hover:text-white" onClick={() => onEdit(plan)} data-testid={`edit-plan-${plan.code}`}>
                            <Pencil className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-x-3">
                    <HabRow label="Ciclo" value={sem ? `${sem} sem (${plan.ciclo?.tipo})` : (plan.ciclo?.tipo || '-')} />
                    <HabRow label="Precio" value={plan.precio != null ? `${plan.precio}€` : '-'} />
                </div>
                {plan.precio_nota && <p className="text-[11px] text-white/40 -mt-1">{plan.precio_nota}</p>}

                <div className="border-t border-[#222] pt-2 space-y-1">
                    {/* Con nombre, no con el código de la casilla («personalizado»). */}
                    <HabRow label="Calculadora" value={h.calculadora ? etiquetaCalculadora(h.calculadora) : '-'} />
                    <HabRow label="Rutina" value={h.rutina || '-'} />
                    <HabRow label="Reportes" value={(h.reportes && h.reportes.length) ? h.reportes.join(' + ') : 'ninguno'} />
                    <HabRow label="Acompañamiento" value={etiquetaAcompanamiento(h.acompanamiento)} />
                    <HabRow label="Contacto" value={etiquetaFrecuencia(h.frecuencia_contacto)} />
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Suplementación</span><Dot on={!!h.suplementacion} />
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Harbiz</span><Dot on={!!h.harbiz} />
                    </div>
                    <HabRow label="Responsable" value={plan.responsable || '-'} />
                    {/* Si el «Tu plan incluye» de este plan está escrito a mano o se deriva de
                        las habilitaciones (punto 6.4). */}
                    <HabRow label="Qué incluye" value={plan.que_incluye ? 'escrito' : 'derivado'} />
                </div>
            </CardContent>
        </Card>
    );
};

const AdminPlansPage = () => {
    const { api } = useAuth();
    const [catalog, setCatalog] = useState({});
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null); // plan en edición
    const [form, setForm] = useState(null);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/plans');
            setCatalog(res.data || {});
        } catch (e) {
            toast.error('No se pudo cargar el catálogo de planes');
        } finally {
            setLoading(false);
        }
    }, [api]);

    useEffect(() => { load(); }, [load]);

    const openEdit = (plan) => {
        setEditing(plan);
        setForm({
            name: plan.name || '',
            estado: plan.estado || 'activo',
            precio: plan.precio ?? 0,
            precio_nota: plan.precio_nota || '',
            responsable: plan.responsable || '',
            que_incluye: plan.que_incluye || '',
            ciclo_tipo: plan.ciclo?.tipo || 'mensual',
            ciclo_semanas: plan.ciclo?.semanas ?? '',
            calculadora: plan.habilitaciones?.calculadora || 'personalizado',
            rutina: plan.habilitaciones?.rutina || 'ninguna',
            reportes: [...(plan.habilitaciones?.reportes || [])],
            suplementacion: !!plan.habilitaciones?.suplementacion,
            harbiz: !!plan.habilitaciones?.harbiz,
            // Lo que separa a dos planes que por lo demás son idénticos salvo el precio:
            // si hay alguien detrás y cada cuánto le escribe.
            acompanamiento: plan.habilitaciones?.acompanamiento || 'solo_app',
            frecuencia_contacto: plan.habilitaciones?.frecuencia_contacto || 'ninguna',
        });
    };

    const toggleReporte = (r) => setForm(f => ({
        ...f,
        reportes: f.reportes.includes(r) ? f.reportes.filter(x => x !== r) : [...f.reportes, r],
    }));

    const save = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            const payload = {
                name: form.name.trim(),
                estado: form.estado,
                precio: parseFloat(form.precio) || 0,
                precio_nota: form.precio_nota,
                responsable: form.responsable,
                que_incluye: form.que_incluye.trim(),
                ciclo: {
                    tipo: form.ciclo_tipo,
                    semanas: form.ciclo_semanas === '' ? null : parseInt(form.ciclo_semanas, 10),
                },
                habilitaciones: {
                    calculadora: form.calculadora,
                    rutina: form.rutina,
                    reportes: form.reportes,
                    suplementacion: form.suplementacion,
                    harbiz: form.harbiz,
                    acompanamiento: form.acompanamiento,
                    frecuencia_contacto: form.frecuencia_contacto,
                },
            };
            await api.put(`/admin/plans/${editing.code}`, payload);
            toast.success('Plan actualizado');
            setEditing(null);
            setForm(null);
            load();
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al guardar'));
        } finally {
            setSaving(false);
        }
    };

    const resetPlan = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            await api.delete(`/admin/plans/${editing.code}`);
            toast.success('Plan restaurado a los valores por defecto');
            setEditing(null);
            setForm(null);
            load();
        } catch (e) {
            toast.error('No se pudo restaurar');
        } finally {
            setSaving(false);
        }
    };

    const plans = Object.values(catalog);

    return (
        <div className="p-4 md:p-6 space-y-6">
            <div className="flex items-center gap-3">
                <Layers className="w-6 h-6 text-[#FF671F]" />
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>CATÁLOGO DE PLANES</h1>
                    <p className="text-sm text-white/50">Fuente única de planes, ciclos y habilitaciones. Editar aquí afecta a lo que ve cada usuario.</p>
                </div>
            </div>

            <PantallasDeLaApp />

            {loading ? (
                <div className="flex justify-center py-16"><div className="animate-spin w-7 h-7 border-2 border-[#FF671F] border-t-transparent rounded-full" /></div>
            ) : (
                ESTADOS.map(({ key, label, hint }) => {
                    const grupo = plans.filter(p => p.estado === key);
                    if (!grupo.length) return null;
                    return (
                        <section key={key} className="space-y-3">
                            <div className="flex items-baseline gap-3">
                                <h2 className="text-lg font-bold text-white uppercase tracking-wide">{label}</h2>
                                <span className="text-xs text-white/40">{hint}</span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {grupo.map(p => <PlanCard key={p.code} plan={p} onEdit={openEdit} />)}
                            </div>
                        </section>
                    );
                })
            )}

            {/* Modal de edición */}
            <Dialog open={!!editing} onOpenChange={(o) => { if (!o) { setEditing(null); setForm(null); } }}>
                <DialogContent className="bg-[#0A0A0A] border-[#333] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Editar plan · {editing?.name}</DialogTitle>
                    </DialogHeader>
                    {form && (
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Nombre</Label>
                                    <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                                <div><Label className="text-white/60 text-xs">Estado</Label>
                                    <select value={form.estado} onChange={e => setForm(f => ({ ...f, estado: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {ESTADOS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                                    </select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Ciclo</Label>
                                    <select value={form.ciclo_tipo} onChange={e => setForm(f => ({ ...f, ciclo_tipo: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {CICLO_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                                    </select>
                                </div>
                                <div><Label className="text-white/60 text-xs">Semanas del ciclo (vacío = indefinido)</Label>
                                    <Input type="number" value={form.ciclo_semanas} onChange={e => setForm(f => ({ ...f, ciclo_semanas: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Precio (€)</Label>
                                    <Input type="number" value={form.precio} onChange={e => setForm(f => ({ ...f, precio: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                                <div><Label className="text-white/60 text-xs">Responsable</Label>
                                    <Input value={form.responsable} onChange={e => setForm(f => ({ ...f, responsable: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                            </div>
                            <div><Label className="text-white/60 text-xs">Nota de precio</Label>
                                <Input value={form.precio_nota} onChange={e => setForm(f => ({ ...f, precio_nota: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                            </div>

                            {/* QUÉ INCLUYE, ESCRITO A MANO (punto 6.4). Lo que se pinta tal cual en
                                «Tu plan incluye» de Mi perfil. Si se deja vacío se siguen derivando
                                las líneas de las habilitaciones, que es lo que les toca a los planes
                                que ya no se venden. */}
                            <div><Label className="text-white/60 text-xs">Qué incluye (una línea por punto)</Label>
                                <textarea value={form.que_incluye} rows={5} data-testid="plan-que-incluye"
                                    onChange={e => setForm(f => ({ ...f, que_incluye: e.target.value }))}
                                    placeholder={'Dieta personalizada y ajustada cada quince días\nRutina de entrenamiento a tu medida\nChat directo con tu entrenador'}
                                    className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-3 py-2 mt-1 resize-y placeholder:text-white/25" />
                                <p className="text-[11px] text-white/30 mt-1">
                                    Se escribe solo para los cuatro que se venden. Vacío = se derivan de las habilitaciones.
                                </p>
                            </div>

                            <div className="border-t border-[#222] pt-3">
                                <p className="text-xs font-bold text-white/70 uppercase tracking-wider mb-2">Habilitaciones</p>
                                <div className="grid grid-cols-2 gap-3">
                                    <div><Label className="text-white/60 text-xs">Calculadora</Label>
                                        <select value={form.calculadora} onChange={e => setForm(f => ({ ...f, calculadora: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {CALCULADORA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Rutina</Label>
                                        <select value={form.rutina} onChange={e => setForm(f => ({ ...f, rutina: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {RUTINA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                </div>
                                {/* Lo que de verdad separa un plan de otro cuando el resto es
                                    igual: si hay alguien detrás y cada cuánto le escribe. */}
                                <div className="grid grid-cols-2 gap-3 mt-3">
                                    <div><Label className="text-white/60 text-xs">Acompañamiento</Label>
                                        <select value={form.acompanamiento} onChange={e => setForm(f => ({ ...f, acompanamiento: e.target.value }))}
                                            data-testid="plan-acompanamiento"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {ACOMPANAMIENTO_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Frecuencia de contacto</Label>
                                        <select value={form.frecuencia_contacto} onChange={e => setForm(f => ({ ...f, frecuencia_contacto: e.target.value }))}
                                            data-testid="plan-frecuencia-contacto"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {FRECUENCIA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                </div>
                                <div className="mt-2">
                                    <Label className="text-white/60 text-xs">Reportes</Label>
                                    <div className="flex gap-2 mt-1">
                                        {REPORTE_OPTS.map(r => (
                                            <button key={r} type="button" onClick={() => toggleReporte(r)}
                                                className={`px-3 py-1.5 rounded-lg text-xs capitalize border transition-colors ${form.reportes.includes(r) ? 'bg-[#FF671F] border-[#FF671F] text-white' : 'bg-[#111] border-[#333] text-white/60'}`}>
                                                {r}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="flex gap-6 mt-3">
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.suplementacion} onChange={e => setForm(f => ({ ...f, suplementacion: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                                        Suplementación
                                    </label>
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.harbiz} onChange={e => setForm(f => ({ ...f, harbiz: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                                        Harbiz
                                    </label>
                                </div>
                            </div>

                            <div className="border-t border-[#222] pt-2">
                                <p className="text-xs text-white/40 mb-1">Vista previa "tu plan incluye":</p>
                                {/* Lo mismo que verá el cliente: si hay texto escrito manda ese, y
                                    si no, las líneas derivadas. Así se ve al escribirlo. */}
                                <ul className="text-xs text-white/70 list-disc list-inside space-y-0.5" data-testid="plan-que-incluye-preview">
                                    {queIncluyeElPlan({
                                        que_incluye: form.que_incluye,
                                        habilitaciones: {
                                            calculadora: form.calculadora, rutina: form.rutina,
                                            reportes: form.reportes, suplementacion: form.suplementacion,
                                            harbiz: form.harbiz, acompanamiento: form.acompanamiento,
                                            frecuencia_contacto: form.frecuencia_contacto,
                                        },
                                    }).map((x, i) => <li key={i}>{x}</li>)}
                                </ul>
                            </div>
                        </div>
                    )}
                    <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
                        {editing?.has_override
                            ? <Button variant="ghost" className="text-white/50 hover:text-red-400" onClick={resetPlan} disabled={saving}><RotateCcw className="w-4 h-4 mr-1" /> Restaurar por defecto</Button>
                            : <span />}
                        <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" onClick={save} disabled={saving} data-testid="save-plan-btn">
                            {saving ? 'Guardando…' : 'Guardar'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AdminPlansPage;
