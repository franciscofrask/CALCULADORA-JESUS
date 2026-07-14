import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Pill, Plus, Pencil, Trash2, Loader2, Save } from 'lucide-react';
import { suplementoCatLabel, sexoLabel, objetivoLabel } from '../lib/labels';

// Etiqueta legible por campo del catálogo (evita "sueno · ambos · ambos").
const catalogoLabel = (campo, v) =>
    campo === 'categoria' ? suplementoCatLabel(v)
    : campo === 'sexo' ? sexoLabel(v)
    : objetivoLabel(v);

const SEXOS = ['ambos', 'hombre', 'mujer'];
const CATEGORIAS = ['base', 'intra', 'rendimiento', 'quemador', 'salud', 'sueno', 'otro'];
const OBJETIVOS = ['ambos', 'volumen', 'definicion'];

const EMPTY = { titulo: '', imagen: '', enlaces: [], cuando: '', cuanto: '', observaciones: '', sexo: 'ambos', categoria: 'base', objetivo: 'ambos', orden: 0, activo: true };

const SupplementsCatalogPage = () => {
    const { api } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [modal, setModal] = useState({ open: false, item: null });
    const [form, setForm] = useState(EMPTY);
    const [saving, setSaving] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const r = await api.get('/admin/supplements/catalog?include_inactive=true');
            setItems(r.data || []);
        } catch (e) { toast.error('Error al cargar catálogo'); }
        finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []); // eslint-disable-line

    const openNew = () => { setForm(EMPTY); setModal({ open: true, item: null }); };
    const openEdit = (it) => { setForm({ ...EMPTY, ...it, enlaces: it.enlaces || [] }); setModal({ open: true, item: it }); };

    const save = async () => {
        if (!form.titulo.trim()) { toast.error('El título es obligatorio'); return; }
        setSaving(true);
        try {
            const body = { ...form, enlaces: (form.enlaces || []).filter(Boolean) };
            if (modal.item) await api.put(`/admin/supplements/catalog/${modal.item.id}`, body);
            else await api.post('/admin/supplements/catalog', body);
            toast.success('Guardado');
            setModal({ open: false, item: null });
            load();
        } catch (e) { toast.error('Error al guardar'); }
        finally { setSaving(false); }
    };

    const del = async (it) => {
        if (!window.confirm(`¿Desactivar "${it.titulo}"?`)) return;
        try { await api.delete(`/admin/supplements/catalog/${it.id}`); toast.success('Desactivado'); load(); }
        catch (e) { toast.error('Error'); }
    };

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between flex-wrap gap-2">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2" style={{ fontFamily: 'Barlow Condensed' }}>
                    <Pill className="w-6 h-6 text-[#FF671F]" /> CATÁLOGO DE SUPLEMENTOS
                </h1>
                <Button onClick={openNew} className="bg-[#FF671F] text-white"><Plus className="w-4 h-4 mr-1" />Nuevo</Button>
            </div>

            {loading ? (
                <div className="animate-pulse space-y-3"><div className="h-16 bg-[#111] rounded-xl" /><div className="h-16 bg-[#111] rounded-xl" /></div>
            ) : (
                <div className="grid md:grid-cols-2 gap-3">
                    {items.map(it => (
                        <Card key={it.id} className={`bg-[#111] border-[#222] ${!it.activo ? 'opacity-50' : ''}`}><CardContent className="p-4 flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-white font-medium">{it.titulo} {!it.activo && <span className="text-red-400 text-xs">(inactivo)</span>}</p>
                                <p className="text-white/40 text-xs mt-0.5">{suplementoCatLabel(it.categoria)} · {sexoLabel(it.sexo)} · {objetivoLabel(it.objetivo)}</p>
                                <p className="text-white/50 text-xs mt-1">{[it.cuanto, it.cuando].filter(Boolean).join(' · ')}</p>
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                                <button onClick={() => openEdit(it)} className="text-white/40 hover:text-white p-1"><Pencil className="w-4 h-4" /></button>
                                <button onClick={() => del(it)} className="text-white/40 hover:text-red-400 p-1"><Trash2 className="w-4 h-4" /></button>
                            </div>
                        </CardContent></Card>
                    ))}
                    {items.length === 0 && <p className="text-white/40 text-sm">Catálogo vacío. Crea el primer suplemento.</p>}
                </div>
            )}

            <Dialog open={modal.open} onOpenChange={(o) => setModal(m => ({ ...m, open: o }))}>
                <DialogContent className="bg-[#111] border-[#222] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                    <DialogHeader><DialogTitle>{modal.item ? 'Editar' : 'Nuevo'} suplemento</DialogTitle></DialogHeader>
                    <div className="space-y-3">
                        <div><Label className="text-white/60 text-xs">Título *</Label><Input value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                        <div className="grid grid-cols-3 gap-2">
                            {[['sexo', SEXOS], ['categoria', CATEGORIAS], ['objetivo', OBJETIVOS]].map(([k, opts]) => (
                                <div key={k}><Label className="text-white/60 text-xs capitalize">{k}</Label>
                                    <select value={form[k]} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2">
                                        {opts.map(o => <option key={o} value={o}>{catalogoLabel(k, o)}</option>)}
                                    </select>
                                </div>
                            ))}
                        </div>
                        <div><Label className="text-white/60 text-xs">¿Cuándo? (timing)</Label><Input value={form.cuando} onChange={e => setForm(f => ({ ...f, cuando: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                        <div><Label className="text-white/60 text-xs">¿Cuánto? (dosis)</Label><Input value={form.cuanto} onChange={e => setForm(f => ({ ...f, cuanto: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                        <div><Label className="text-white/60 text-xs">Observaciones</Label><Textarea value={form.observaciones || ''} onChange={e => setForm(f => ({ ...f, observaciones: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" rows={2} /></div>
                        <div><Label className="text-white/60 text-xs">Imagen (URL)</Label><Input value={form.imagen || ''} onChange={e => setForm(f => ({ ...f, imagen: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                        <div><Label className="text-white/60 text-xs">Enlaces (uno por línea)</Label><Textarea value={(form.enlaces || []).join('\n')} onChange={e => setForm(f => ({ ...f, enlaces: e.target.value.split('\n') }))} className="bg-[#0A0A0A] border-[#333] text-white" rows={2} /></div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setModal({ open: false, item: null })} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                        <Button onClick={save} disabled={saving} className="bg-[#FF671F] text-white">{saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}Guardar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default SupplementsCatalogPage;
