import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { useConfirm } from '../components/ui/confirm';
import { Utensils, Plus, Pencil, Trash2, Loader2, Save, X } from 'lucide-react';
import { mensajeDeError } from '../lib/mensajeDeError';

const MOMENTOS = ['desayuno', 'comida', 'merienda', 'cena'];
const ROLES = ['proteina', 'hidrato', 'grasa'];
const ROL_LABEL = { proteina: 'Proteína', hidrato: 'Hidratos', grasa: 'Grasa' };

// Coma decimal, y sin decimales cuando son cero: 1 · 0,7 · 2,5.
const coma = (n) => String(Math.round(Number(n) * 100) / 100).replace('.', ',');

// La proporción de un item: un número entre 0 y 1, o "ajuste" (el alimento que cierra la
// grasa). Devuelve null si no es ninguna de las dos cosas.
const leerProporcion = (v) => {
    const txt = String(v ?? '').trim().toLowerCase().replace(',', '.');
    if (txt === 'ajuste') return 'ajuste';
    const n = Number(txt);
    return Number.isFinite(n) && n > 0 && n <= 1 ? n : null;
};

// UNA ETIQUETA «NUEVO» QUE SIGNIFIQUE ALGO (#68 del informe del 15-08).
// Salía en todos los menús porque miraba `origen === 'custom'`, y los 153 del recetario se
// importaron con ese origen. Nuevo es lo de este mes; lo demás es el catálogo.
const DIAS_QUE_ES_NUEVO = 30;
const esReciente = (it) => {
    const t = new Date(it?.created_at || 0).getTime();
    return Number.isFinite(t) && t > 0 && (Date.now() - t) < DIAS_QUE_ES_NUEVO * 86400000;
};

const EMPTY_ITEM = { rol: 'proteina', alimento_id: null, buscar: '', categoria: '', proporcion: '1.0', macros: null };
const EMPTY = { nombre: '', momento: 'comida', min_kcal: 300, max_kcal: 700, tags: [], items: [{ ...EMPTY_ITEM }] };

// Buscador de alimentos (autocompletado contra /calculator/search). Al elegir uno, guarda
// el id y el nombre; la categoría la resuelve el backend a partir del id.
function FoodPicker({ api, nombre, onPick }) {
    const [q, setQ] = useState(nombre || '');
    const [results, setResults] = useState([]);
    const [open, setOpen] = useState(false);
    const [searching, setSearching] = useState(false);
    const boxRef = useRef(null);

    useEffect(() => { setQ(nombre || ''); }, [nombre]);

    useEffect(() => {
        if (!open) return;
        const term = q.trim();
        if (term.length < 2) { setResults([]); return; }
        let cancelled = false;
        const t = setTimeout(async () => {
            setSearching(true);
            try {
                const r = await api.get(`/calculator/search?q=${encodeURIComponent(term)}&limit=12`);
                if (!cancelled) setResults(r.data?.alimentos || []);
            } catch { if (!cancelled) setResults([]); }
            finally { if (!cancelled) setSearching(false); }
        }, 300);
        return () => { cancelled = true; clearTimeout(t); };
    }, [q, open]); // eslint-disable-line

    useEffect(() => {
        const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', onDoc);
        return () => document.removeEventListener('mousedown', onDoc);
    }, []);

    return (
        <div className="relative" ref={boxRef}>
            <Input
                value={q}
                onChange={e => { setQ(e.target.value); setOpen(true); }}
                onFocus={() => setOpen(true)}
                className="bg-[#0A0A0A] border-[#333] text-white text-xs h-9"
                placeholder="Buscar alimento..."
            />
            {open && q.trim().length >= 2 && (
                <div className="absolute z-50 left-0 right-0 mt-1 bg-[#111] border border-[#333] rounded-lg max-h-52 overflow-auto shadow-xl">
                    {searching && <div className="px-2 py-1.5 text-[11px] text-white/40">Buscando...</div>}
                    {!searching && results.length === 0 && <div className="px-2 py-1.5 text-[11px] text-white/40">Sin resultados</div>}
                    {results.map(f => (
                        <button key={f.id} type="button"
                            onClick={() => { onPick(f); setOpen(false); }}
                            className="w-full text-left px-2 py-1.5 text-xs text-white hover:bg-[#FF671F]/20 truncate">
                            {f.nombre}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

const AdminMenusPage = () => {
    const { api } = useAuth();
    const { confirm } = useConfirm();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filtro, setFiltro] = useState('todos');
    const [modal, setModal] = useState({ open: false, item: null });
    const [form, setForm] = useState(EMPTY);
    const [saving, setSaving] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const r = await api.get('/admin/menu-templates');
            setItems(r.data?.templates || []);
        } catch (e) { toast.error('Error al cargar los menús'); }
        finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []); // eslint-disable-line

    const openNew = () => { setForm({ ...EMPTY, items: [{ ...EMPTY_ITEM }] }); setModal({ open: true, item: null }); };
    const openEdit = async (it) => {
        let full = it;
        try { const r = await api.get(`/admin/menu-templates/${it.id}`); if (r.data) full = r.data; } catch { /* usa lo cargado */ }
        setForm({
            ...EMPTY, ...full,
            tags: full.tags || [],
            items: (full.items || []).map(x => ({ rol: x.rol || 'proteina', alimento_id: x.alimento_id ?? null, buscar: x.buscar || '', categoria: x.categoria || '', proporcion: String(x.proporcion ?? '1.0'), macros: x.macros || null })),
        });
        setModal({ open: true, item: it });
    };

    // EL REPARTO POR MACRO, RECALCULADO EN CADA TECLA (#59).
    // La proporción es la parte del macro que cubre ese alimento, así que los de un mismo
    // rol suman 1. Antes no se comprobaba nada: dos hidratos con 1 cada uno, o un 99, se
    // guardaban sin una palabra. Los items en «ajuste» no entran en la suma (no reparten:
    // cierran lo que falte de grasa).
    const repartos = useMemo(() => ROLES.map(rol => {
        const suyos = (form.items || []).filter(it => it.rol === rol && (it.buscar || '').trim());
        const malo = suyos.find(it => leerProporcion(it.proporcion) === null);
        const numeros = suyos
            .map(it => leerProporcion(it.proporcion))
            .filter(p => typeof p === 'number');
        const suma = numeros.reduce((a, b) => a + b, 0);
        return {
            rol: ROL_LABEL[rol], n: numeros.length, suma,
            invalida: malo ? (malo.buscar || 'ese alimento') : null,
            descuadra: numeros.length > 0 && Math.abs(suma - 1) > 0.01,
        };
    }).filter(r => r.n > 0 || r.invalida), [form.items]);

    // ---- edición de items ----
    const setItem = (idx, field, val) => setForm(f => ({ ...f, items: f.items.map((it, i) => i === idx ? { ...it, [field]: val } : it) }));
    const pickFood = (idx, food) => setForm(f => ({ ...f, items: f.items.map((it, i) => i === idx ? { ...it, alimento_id: food.id, buscar: food.nombre, macros: { P: Math.round(food.proteinas || 0), H: Math.round(food.hidratos || 0), G: Math.round(food.grasas || 0) } } : it) }));
    const addItem = () => setForm(f => ({ ...f, items: [...f.items, { ...EMPTY_ITEM }] }));
    const removeItem = (idx) => setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));

    const save = async () => {
        if (!form.nombre.trim()) { toast.error('El nombre es obligatorio'); return; }
        const validos = (form.items || []).filter(it => it.buscar.trim());
        if (validos.length === 0) { toast.error('Añade al menos un alimento'); return; }
        // LAS PROPORCIONES TIENEN QUE SUMAR (#59 del informe del 15-08).
        // Una fuera de rango no se guarda: no significa nada y el servidor la rechaza igual.
        const fuera = repartos.find(r => r.invalida);
        if (fuera) {
            toast.error(`La proporción de ${fuera.invalida} no vale: va de 0 a 1 (1 = ese `
                + 'alimento cubre todo el macro). También vale «ajuste» para la grasa.');
            return;
        }
        // Que un macro sume 2,0 sí puede ser a propósito mientras se está montando el menú,
        // así que se avisa con lo que pasaría y se deja decidir. El arroz y los champiñones
        // con 1 cada uno son el ejemplo de Jesús: para cubrir su parte harían falta medio
        // kilo de champiñones.
        const descuadres = repartos.filter(r => r.descuadra);
        if (descuadres.length && !await confirm({
            title: 'Las proporciones no suman 1',
            description: descuadres.map(r => `${r.rol}: suman ${coma(r.suma)} entre ${r.n} `
                + `${r.n === 1 ? 'alimento' : 'alimentos'}`).join(' · ')
                + '. Cada macro se reparte entre sus alimentos y ese reparto suma 1. Tal y como '
                + 'está, la ficha no dice qué parte cubre cada uno.',
            confirmLabel: 'Guardar igual', cancelLabel: 'Lo reviso',
        })) return;
        setSaving(true);
        try {
            const body = {
                nombre: form.nombre.trim(),
                momento: form.momento,
                tags: (form.tags || []).map(t => t.trim()).filter(Boolean),
                items: validos.map(it => ({
                    rol: it.rol,
                    alimento_id: it.alimento_id ?? null,
                    buscar: it.buscar.trim(),
                    categoria: (it.categoria || '').trim(),
                    proporcion: it.proporcion, // el backend acepta número o "ajuste"
                })),
            };
            if (modal.item) await api.put(`/admin/menu-templates/${modal.item.id}`, body);
            else await api.post('/admin/menu-templates', body);
            toast.success(modal.item ? 'Menú actualizado' : 'Menú creado');
            setModal({ open: false, item: null });
            load();
        } catch (e) { toast.error(mensajeDeError(e, 'Error al guardar')); }
        finally { setSaving(false); }
    };

    const del = async (it) => {
        if (!await confirm({
            title: `¿Borrar el menú "${it.nombre}"?`,
            description: 'Desaparece del listado y deja de proponerse a los clientes.',
            confirmLabel: 'Borrar', danger: true,
        })) return;
        try { await api.delete(`/admin/menu-templates/${it.id}`); toast.success('Menú borrado'); load(); }
        catch (e) { toast.error('Error al borrar'); }
    };

    // UN ORDEN, Y SIEMPRE EL MISMO (#68: «con el filtro en TODOS las dieciséis primeras
    // fichas son cenas: no hay orden ni por tipo ni por nombre»). El servidor las devuelve
    // ordenadas por (momento, id) y «cena» es la primera por alfabeto. Aquí van por el orden
    // del día -- desayuno, comida, merienda, cena -- y dentro de cada uno por nombre.
    const mostrados = useMemo(() => {
        const lista = filtro === 'todos' ? [...items] : items.filter(i => i.momento === filtro);
        return lista.sort((a, b) => {
            const d = MOMENTOS.indexOf(a.momento) - MOMENTOS.indexOf(b.momento);
            return d !== 0 ? d : (a.nombre || '').localeCompare(b.nombre || '', 'es');
        });
    }, [items, filtro]);
    const cuenta = (m) => (m === 'todos' ? items.length : items.filter(i => i.momento === m).length);

    // 153 FILAS SON 99 RECETAS.
    //
    // «En el panel del equipo hay 163 y el cliente ve 99. ¿Dónde se quedan los otros 64?»
    // (Jesús, 11-08). No se queda ninguno: los platos principales están guardados dos veces,
    // una como comida y otra como cena, así que 54 recetas cuentan por dos. La pantalla del
    // cliente las junta por nombre y por eso enseña 99. Aquí se veían las filas sin decir
    // que lo eran, y parecía que faltaban menús. Se dice.
    const recetas = new Set(items.map(i => (i.nombre || '').trim().toLowerCase()).filter(Boolean)).size;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2" style={{ fontFamily: 'Barlow Condensed' }}>
                        <Utensils className="w-6 h-6 text-[#FF671F]" /> MENÚS PREESTABLECIDOS
                    </h1>
                    {/* EL TÍTULO CUENTA LO MISMO QUE LAS PESTAÑAS (#67 del 15-08: «30 + 56 +
                        17 + 56 = 159, y arriba pone 103 recetas»). Las pestañas cuentan
                        fichas, así que el número de delante son fichas; las recetas van
                        detrás, explicadas. */}
                    {!loading && items.length > 0 && (
                        <p className="text-white/40 text-sm mt-1">
                            {items.length} {items.length === 1 ? 'ficha' : 'fichas'}
                            {items.length !== recetas
                                ? ` · ${recetas} recetas distintas: las que valen para comida y para cena están guardadas dos veces`
                                : ''}
                        </p>
                    )}
                </div>
                <Button onClick={openNew} className="bg-[#FF671F] text-white"><Plus className="w-4 h-4 mr-1" />Nuevo menú</Button>
            </div>

            {/* Filtro por momento */}
            <div className="flex flex-wrap gap-1.5">
                {['todos', ...MOMENTOS].map(m => (
                    <button key={m} onClick={() => setFiltro(m)}
                        className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide transition-colors ${filtro === m ? 'bg-[#FF671F] text-white' : 'bg-[#111] text-white/50 border border-[#222] hover:text-white'}`}>
                        {m} ({cuenta(m)})
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="animate-pulse space-y-3"><div className="h-16 bg-[#111] rounded-xl" /><div className="h-16 bg-[#111] rounded-xl" /></div>
            ) : (
                <div className="grid md:grid-cols-2 gap-3">
                    {mostrados.map(it => (
                        <Card key={it.id} className="bg-[#111] border-[#222]"><CardContent className="p-4 flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-white font-medium flex items-center gap-2">
                                    {it.nombre}
                                    {esReciente(it) && <span className="text-[9px] bg-[#FF671F]/20 text-[#FF671F] px-1.5 py-0.5 rounded uppercase font-bold">nuevo</span>}
                                </p>
                                <p className="text-white/40 text-xs mt-0.5 capitalize">{it.momento} · {(it.items || []).length} alimentos</p>
                                <p className="text-white/50 text-xs mt-1 truncate">{(it.items || []).map(x => x.buscar).join(', ')}</p>
                            </div>
                            <div className="flex gap-1 flex-shrink-0">
                                <button onClick={() => openEdit(it)} className="text-white/40 hover:text-white p-1"><Pencil className="w-4 h-4" /></button>
                                <button onClick={() => del(it)} className="text-white/40 hover:text-red-400 p-1"><Trash2 className="w-4 h-4" /></button>
                            </div>
                        </CardContent></Card>
                    ))}
                    {mostrados.length === 0 && <p className="text-white/40 text-sm">No hay menús en este momento. Crea el primero.</p>}
                </div>
            )}

            <Dialog open={modal.open} onOpenChange={(o) => setModal(m => ({ ...m, open: o }))}>
                <DialogContent className="bg-[#111] border-[#222] text-white max-w-xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader><DialogTitle>{modal.item ? 'Editar' : 'Nuevo'} menú</DialogTitle></DialogHeader>
                    <div className="space-y-3">
                        <div><Label className="text-white/60 text-xs">Nombre *</Label>
                            <Input value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white" placeholder="Ej. Pollo con arroz y ensalada" /></div>
                        <div><Label className="text-white/60 text-xs">Momento</Label>
                            <select value={form.momento} onChange={e => setForm(f => ({ ...f, momento: e.target.value }))} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 capitalize">
                                {MOMENTOS.map(o => <option key={o} value={o}>{o}</option>)}
                            </select></div>
                        <div><Label className="text-white/60 text-xs">Tags (separadas por coma)</Label>
                            <Input value={(form.tags || []).join(', ')} onChange={e => setForm(f => ({ ...f, tags: e.target.value.split(',') }))} className="bg-[#0A0A0A] border-[#333] text-white" placeholder="clasico, rapido" /></div>

                        {/* Items */}
                        <div>
                            <Label className="text-white/60 text-xs">Alimentos del menú</Label>
                            <div className="space-y-1.5 mt-1">
                                <div className="grid grid-cols-12 gap-1.5 text-[10px] text-white/30 uppercase tracking-wide px-1">
                                    <span className="col-span-3">Rol</span><span className="col-span-6">Alimento</span><span className="col-span-2">Prop.</span><span className="col-span-1"></span>
                                </div>
                                {form.items.map((it, idx) => (
                                    <div key={idx}>
                                        <div className="grid grid-cols-12 gap-1.5 items-center">
                                            <select value={it.rol} onChange={e => setItem(idx, 'rol', e.target.value)} className="col-span-3 bg-[#0A0A0A] border border-[#333] text-white text-xs rounded-lg px-1.5 py-2 capitalize">
                                                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                                            </select>
                                            <div className="col-span-6">
                                                <FoodPicker api={api} nombre={it.buscar} onPick={(f) => pickFood(idx, f)} />
                                            </div>
                                            {/* En rojo en cuanto deja de ser una proporción: se ve
                                                al escribirlo, no al guardar (#59). */}
                                            <Input value={it.proporcion} onChange={e => setItem(idx, 'proporcion', e.target.value)}
                                                className={`col-span-2 bg-[#0A0A0A] text-white text-xs h-9 ${leerProporcion(it.proporcion) === null && (it.buscar || '').trim() ? 'border-red-500' : 'border-[#333]'}`}
                                                placeholder="1" title="De 0 a 1, o «ajuste»" />
                                            <button onClick={() => removeItem(idx)} className="col-span-1 text-white/30 hover:text-red-400 flex justify-center"><X className="w-4 h-4" /></button>
                                        </div>
                                        {it.macros && (
                                            <div className="text-[10px] text-white/40 mt-0.5 pl-[26%]">
                                                por 100g: <span className="text-orange-400">P{it.macros.P}</span> · <span className="text-blue-400">H{it.macros.H}</span> · <span className="text-yellow-400">G{it.macros.G}</span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                            <button onClick={addItem} className="mt-2 text-xs font-semibold text-[#FF671F] hover:underline flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> Añadir alimento</button>

                            {/* EL REPARTO, A LA VISTA MIENTRAS SE EDITA (#59). Aquí no había
                                nada: la única forma de saber que los hidratos sumaban 2 era
                                sumarlos a mano. */}
                            {repartos.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
                                    {repartos.map(r => (
                                        <span key={r.rol} className={r.invalida || r.descuadra ? 'text-red-400' : 'text-white/40'}>
                                            {r.rol}: {coma(r.suma)} de 1
                                            {r.descuadra && ' · no cuadra'}
                                            {r.invalida && ' · hay una proporción que no vale'}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {(() => {
                                // LOS MACROS DEL MENÚ SE MUEVEN AL EDITAR (#59: «no se
                                // recalculan»). Sumaban los 100 g de cada alimento a pelo, así
                                // que cambiar una proporción no movía el número y parecía que
                                // la pantalla se había quedado colgada. Cada alimento entra por
                                // su parte; el de «ajuste» entra entero, que es lo que hace.
                                const tot = form.items.reduce((a, it) => {
                                    if (!it.macros) return a;
                                    const p = leerProporcion(it.proporcion);
                                    const f = typeof p === 'number' ? p : 1;
                                    return { P: a.P + it.macros.P * f, H: a.H + it.macros.H * f, G: a.G + it.macros.G * f };
                                }, { P: 0, H: 0, G: 0 });
                                return (
                                    <div className="mt-2 pt-2 border-t border-[#222] text-xs text-white/50 flex items-center justify-between gap-2">
                                        <span>Macros del menú <span className="text-white/30">(guía: 100 g de cada alimento por su proporción)</span></span>
                                        <span className="font-semibold whitespace-nowrap"><span className="text-orange-400">P{coma(tot.P)}</span> · <span className="text-blue-400">H{coma(tot.H)}</span> · <span className="text-yellow-400">G{coma(tot.G)}</span></span>
                                    </div>
                                );
                            })()}
                            <p className="text-[10px] text-white/30 mt-1.5">Busca y elige el alimento. Proporción: la parte de ese macro que cubre, de 0 a 1 (los alimentos de un mismo rol suman 1), o <b>ajuste</b> para la grasa. Las cantidades se autoajustan a los macros del cliente.</p>
                        </div>
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

export default AdminMenusPage;
