import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Check, X, Pencil, Trash2, Plus, Loader2, ExternalLink, ImageOff } from 'lucide-react';
import CategorySelect from '../components/nutrition/CategorySelect';

const STATUS_META = {
    pending: { label: 'Pendiente', cls: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
    approved: { label: 'Aprobado', cls: 'bg-green-500/15 text-green-400 border-green-500/30' },
    rejected: { label: 'Rechazado', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
};

const r1 = (n) => Math.round(Number(n || 0) * 10) / 10;

// Miniatura de una foto de la sugerencia (descarga el binario autenticado como blob).
const SuggestionPhoto = ({ suggestionId, kind, label }) => {
    const { api } = useAuth();
    const [url, setUrl] = useState(null);
    const [err, setErr] = useState(false);
    useEffect(() => {
        let alive = true; let obj = null;
        api.get(`/calculator/food-suggestions/${suggestionId}/photo/${kind}`, { responseType: 'blob' })
            .then(res => { if (!alive) return; obj = URL.createObjectURL(res.data); setUrl(obj); })
            .catch(() => { if (alive) setErr(true); });
        return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
    }, [api, suggestionId, kind]);

    return (
        <div className="flex flex-col items-center gap-1">
            {err ? (
                <div className="w-24 h-24 rounded-lg bg-[#0A0A0A] border border-[#222] flex items-center justify-center">
                    <ImageOff className="w-5 h-5 text-white/20" />
                </div>
            ) : url ? (
                <a href={url} target="_blank" rel="noopener noreferrer">
                    <img src={url} alt={label} className="w-24 h-24 rounded-lg object-cover border border-[#222]" />
                </a>
            ) : (
                <div className="w-24 h-24 rounded-lg bg-[#0A0A0A] border border-[#222] flex items-center justify-center">
                    <Loader2 className="w-4 h-4 text-white/30 animate-spin" />
                </div>
            )}
            <span className="text-[10px] text-white/40 uppercase tracking-wider">{label}</span>
        </div>
    );
};

// Campos de macros y datos del alimento (compartidos por editar sugerencia y añadir alimento).
const FoodFields = ({ form, set }) => (
    <div className="space-y-3">
        <div>
            <label className="block text-xs font-semibold text-white/50 mb-1">Nombre del alimento</label>
            <input value={form.nombre} onChange={e => set('nombre', e.target.value)}
                className="w-full bg-[#0A0A0A] border border-[#222] text-white text-sm rounded-lg px-3 py-2" />
        </div>
        <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
            <input type="checkbox" checked={!!form.por_unidad} onChange={e => set('por_unidad', e.target.checked)}
                className="w-4 h-4 accent-[#FF671F]" />
            Se toma por unidad
        </label>
        {form.por_unidad && (
            <div>
                <label className="block text-xs font-semibold text-white/50 mb-1">Peso de la unidad (g)</label>
                <input type="number" min="0" step="0.1" value={form.racion} onChange={e => set('racion', e.target.value)}
                    className="w-full bg-[#0A0A0A] border border-[#222] text-white text-sm rounded-lg px-3 py-2" />
            </div>
        )}
        <div>
            <label className="block text-xs font-semibold text-white/50 mb-1">
                Valor nutricional ({form.por_unidad ? 'por unidad' : 'por 100 g'})
            </label>
            <div className="grid grid-cols-3 gap-2">
                {[['proteinas', 'Proteínas'], ['hidratos', 'Hidratos'], ['grasas', 'Grasas']].map(([k, l]) => (
                    <div key={k}>
                        <span className="block text-[10px] text-white/40 mb-1">{l}</span>
                        <input type="number" min="0" step="0.1" value={form[k]} onChange={e => set(k, e.target.value)}
                            className="w-full bg-[#0A0A0A] border border-[#222] text-white text-sm rounded-lg px-2 py-2" />
                    </div>
                ))}
            </div>
        </div>
        <div>
            <label className="block text-xs font-semibold text-white/50 mb-1">Enlace de la fuente</label>
            <input value={form.url || ''} onChange={e => set('url', e.target.value)} placeholder="https://..."
                className="w-full bg-[#0A0A0A] border border-[#222] text-white text-sm rounded-lg px-3 py-2" />
        </div>
        <div>
            <label className="block text-xs font-semibold text-white/50 mb-1">Categorías</label>
            <CategorySelect value={form.categorias || ''} onChange={v => set('categorias', v)} />
            <p className="text-[11px] text-white/30 mt-1">Elige una categoría y añade tantas como necesites.</p>
        </div>
    </div>
);

const emptyFood = { nombre: '', por_unidad: false, racion: 100, proteinas: '', hidratos: '', grasas: '', url: '', categorias: '' };

const AdminFoodSuggestionsPage = () => {
    const { api } = useAuth();
    const [tab, setTab] = useState('pending');   // pending | all
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(null);      // id en proceso

    const [editModal, setEditModal] = useState({ open: false, id: null });
    const [editForm, setEditForm] = useState(emptyFood);
    const [addModal, setAddModal] = useState(false);
    const [addForm, setAddForm] = useState(emptyFood);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = tab === 'pending' ? { status: 'pending' } : {};
            const r = await api.get('/admin/food-suggestions', { params });
            setItems(r.data || []);
        } catch { toast.error('Error cargando las sugerencias'); }
        finally { setLoading(false); }
    }, [api, tab]);

    useEffect(() => { load(); }, [load]);

    const openEdit = (s) => {
        setEditForm({
            nombre: s.food?.nombre || '',
            por_unidad: !!s.food?.por_unidad,
            racion: s.food?.racion ?? 100,
            proteinas: s.food?.proteinas ?? '',
            hidratos: s.food?.hidratos ?? '',
            grasas: s.food?.grasas ?? '',
            url: s.food?.url || '',
            categorias: s.categorias || '',
        });
        setEditModal({ open: true, id: s.id });
    };

    const saveEdit = async () => {
        setSaving(true);
        try {
            await api.put(`/admin/food-suggestions/${editModal.id}`, {
                nombre: editForm.nombre,
                por_unidad: editForm.por_unidad,
                racion: editForm.por_unidad ? Number(editForm.racion) || 1 : 100,
                proteinas: Number(editForm.proteinas) || 0,
                hidratos: Number(editForm.hidratos) || 0,
                grasas: Number(editForm.grasas) || 0,
                url: editForm.url || null,
                categorias: editForm.categorias || null,
            });
            toast.success('Sugerencia actualizada');
            setEditModal({ open: false, id: null });
            load();
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar'); }
        finally { setSaving(false); }
    };

    const approve = async (s) => {
        if (!s.categorias) {
            if (!window.confirm('Este alimento no tiene categorías asignadas. ¿Aprobarlo igualmente?')) return;
        }
        setBusy(s.id);
        try {
            await api.post(`/admin/food-suggestions/${s.id}/approve`);
            toast.success('Alimento aprobado y añadido a la calculadora');
            load();
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo aprobar'); }
        finally { setBusy(null); }
    };

    const reject = async (s) => {
        const motivo = window.prompt('Motivo del rechazo (opcional):', '');
        if (motivo === null) return;
        setBusy(s.id);
        try {
            await api.post(`/admin/food-suggestions/${s.id}/reject`, { motivo });
            toast.success('Sugerencia rechazada');
            load();
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo rechazar'); }
        finally { setBusy(null); }
    };

    const remove = async (s) => {
        if (!window.confirm('¿Eliminar esta sugerencia y sus fotos? No se puede deshacer.')) return;
        setBusy(s.id);
        try {
            await api.delete(`/admin/food-suggestions/${s.id}`);
            setItems(prev => prev.filter(x => x.id !== s.id));
            toast.success('Sugerencia eliminada');
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo eliminar'); }
        finally { setBusy(null); }
    };

    const createFood = async () => {
        if (!addForm.nombre.trim()) return toast.error('Indica el nombre del alimento');
        setSaving(true);
        try {
            await api.post('/admin/foods', {
                nombre: addForm.nombre.trim(),
                por_unidad: addForm.por_unidad,
                racion: addForm.por_unidad ? Number(addForm.racion) || 1 : 100,
                proteinas: Number(addForm.proteinas) || 0,
                hidratos: Number(addForm.hidratos) || 0,
                grasas: Number(addForm.grasas) || 0,
                url: addForm.url || null,
                categorias: addForm.categorias || null,
            });
            toast.success('Alimento añadido a la calculadora');
            setAddModal(false);
            setAddForm(emptyFood);
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo crear el alimento'); }
        finally { setSaving(false); }
    };

    return (
        <div className="p-6 bg-[#0A0A0A] min-h-screen text-white">
            <div className="flex items-center justify-between mb-5 gap-3 flex-wrap">
                <div>
                    <p className="text-xs text-[#FF671F] uppercase tracking-wider mb-1">Administración</p>
                    <h1 className="text-2xl font-bold uppercase">Sugerencias de alimentos</h1>
                    <p className="text-white/40 text-sm">Revisa las propuestas de los clientes y añade alimentos al catálogo.</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex bg-[#111] rounded-lg p-0.5 border border-[#222]">
                        {[{ v: 'pending', l: 'Pendientes' }, { v: 'all', l: 'Todas' }].map(t => (
                            <button key={t.v} onClick={() => setTab(t.v)}
                                className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${tab === t.v ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`}>
                                {t.l}
                            </button>
                        ))}
                    </div>
                    <button onClick={() => { setAddForm(emptyFood); setAddModal(true); }}
                        className="inline-flex items-center gap-1.5 bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors">
                        <Plus className="w-4 h-4" /> Añadir alimento
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center py-20"><Loader2 className="w-7 h-7 text-[#FF671F] animate-spin" /></div>
            ) : items.length === 0 ? (
                <p className="text-white/30 text-sm text-center py-16">
                    {tab === 'pending' ? 'No hay sugerencias pendientes de revisar.' : 'Todavía no hay sugerencias.'}
                </p>
            ) : (
                <div className="space-y-3">
                    {items.map(s => {
                        const st = STATUS_META[s.status] || STATUS_META.pending;
                        const f = s.food || {};
                        const isBusy = busy === s.id;
                        return (
                            <Card key={s.id} className="bg-[#111] border-[#222]">
                                <CardContent className="p-4">
                                    <div className="flex flex-col lg:flex-row gap-4">
                                        {/* Datos */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 flex-wrap mb-1">
                                                <h3 className="text-white font-semibold">{f.nombre || '(sin nombre)'}</h3>
                                                <Badge className={`border text-[10px] uppercase ${st.cls}`}>{st.label}</Badge>
                                            </div>
                                            <p className="text-xs text-white/40 mb-2">
                                                {s.client?.name || 'Cliente'} · {s.client?.email || 'sin email'}
                                                {' · '}
                                                {new Date(s.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}
                                            </p>
                                            <div className="flex flex-wrap gap-1.5 mb-2">
                                                {Number(f.proteinas) > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">{r1(f.proteinas)} proteínas</span>}
                                                {Number(f.hidratos) > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400">{r1(f.hidratos)} hidratos</span>}
                                                {Number(f.grasas) > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">{r1(f.grasas)} grasas</span>}
                                                <span className="text-xs px-2 py-0.5 rounded-full bg-[#0A0A0A] border border-[#222] text-white/50">
                                                    {f.por_unidad ? `por unidad de ${r1(f.racion)}g` : 'por 100 g'}
                                                </span>
                                                <span className="text-xs px-2 py-0.5 rounded-full bg-[#0A0A0A] border border-[#222] text-white/50">
                                                    {f.peso_tipo === 'escurrido' ? 'peso escurrido' : 'peso neto'}
                                                </span>
                                            </div>
                                            {f.url && (
                                                <a href={f.url} target="_blank" rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1 text-xs text-[#FF671F] hover:underline mb-2 break-all">
                                                    <ExternalLink className="w-3 h-3 flex-shrink-0" /> {f.url}
                                                </a>
                                            )}
                                            <p className="text-xs text-white/50">
                                                Categorías: {s.categorias ? <span className="text-white/80">{s.categorias}</span> : <em className="text-white/30">sin asignar</em>}
                                            </p>
                                            {s.admin_notes && <p className="text-xs text-white/40 mt-1">Notas: {s.admin_notes}</p>}
                                        </div>

                                        {/* Fotos (si el cliente las adjuntó) */}
                                        {(s.photos && s.photos.length > 0) ? (
                                            <div className="flex gap-2 flex-shrink-0">
                                                {s.photos.includes('frontal') && <SuggestionPhoto suggestionId={s.id} kind="frontal" label="Frontal" />}
                                                {s.photos.includes('reverso') && <SuggestionPhoto suggestionId={s.id} kind="reverso" label="Reverso" />}
                                            </div>
                                        ) : (
                                            <div className="flex-shrink-0 flex items-center gap-2 text-white/30 text-xs px-3">
                                                <ImageOff className="w-4 h-4" /> Sin fotos
                                            </div>
                                        )}
                                    </div>

                                    {/* Acciones */}
                                    <div className="flex items-center gap-2 flex-wrap mt-3 pt-3 border-t border-[#222]">
                                        <button onClick={() => openEdit(s)} disabled={isBusy}
                                            className="inline-flex items-center gap-1.5 bg-blue-600/90 hover:bg-blue-600 text-white text-xs font-medium rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50">
                                            <Pencil className="w-3.5 h-3.5" /> Editar
                                        </button>
                                        {s.status !== 'approved' && (
                                            <button onClick={() => approve(s)} disabled={isBusy}
                                                className="inline-flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50">
                                                {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Aprobar
                                            </button>
                                        )}
                                        {s.status !== 'rejected' && s.status !== 'approved' && (
                                            <button onClick={() => reject(s)} disabled={isBusy}
                                                className="inline-flex items-center gap-1.5 bg-transparent border border-red-500/40 text-red-400 hover:bg-red-500/10 text-xs font-medium rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50">
                                                <X className="w-3.5 h-3.5" /> Rechazar
                                            </button>
                                        )}
                                        <button onClick={() => remove(s)} disabled={isBusy}
                                            className="inline-flex items-center gap-1.5 text-white/40 hover:text-red-400 text-xs font-medium rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50 ml-auto">
                                            <Trash2 className="w-3.5 h-3.5" /> Eliminar
                                        </button>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Modal editar sugerencia */}
            <Dialog open={editModal.open} onOpenChange={(o) => !o && setEditModal({ open: false, id: null })}>
                <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto bg-[#111] border-[#222] text-white">
                    <DialogHeader><DialogTitle className="text-white">Editar sugerencia</DialogTitle></DialogHeader>
                    <FoodFields form={editForm} set={(k, v) => setEditForm(p => ({ ...p, [k]: v }))} />
                    <button onClick={saveEdit} disabled={saving}
                        className="w-full mt-2 bg-[#FF671F] hover:bg-[#FF671F]/90 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm flex items-center justify-center gap-2">
                        {saving && <Loader2 className="w-4 h-4 animate-spin" />} Guardar cambios
                    </button>
                </DialogContent>
            </Dialog>

            {/* Modal añadir alimento */}
            <Dialog open={addModal} onOpenChange={(o) => !o && setAddModal(false)}>
                <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto bg-[#111] border-[#222] text-white">
                    <DialogHeader><DialogTitle className="text-white">Añadir alimento al catálogo</DialogTitle></DialogHeader>
                    <FoodFields form={addForm} set={(k, v) => setAddForm(p => ({ ...p, [k]: v }))} />
                    <button onClick={createFood} disabled={saving}
                        className="w-full mt-2 bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm flex items-center justify-center gap-2">
                        {saving && <Loader2 className="w-4 h-4 animate-spin" />} Añadir alimento
                    </button>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AdminFoodSuggestionsPage;
