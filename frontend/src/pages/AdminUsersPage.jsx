import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Search, Pencil, UserX, RotateCcw, Loader2, Shield, KeyRound } from 'lucide-react';

const ROLES = [
    { value: 'client', label: 'Cliente' },
    { value: 'trainer', label: 'Entrenador' },
    { value: 'admin', label: 'Admin' },
];
const ROLE_LABEL = Object.fromEntries(ROLES.map(r => [r.value, r.label]));
const STAFF_ROLES = ROLES.filter(r => r.value !== 'client');  // esta lista es solo equipo (admin/coach)
const PLAN_COLORS = { gold: '#EAB308', silver: '#9CA3AF', bronze: '#C2410C', elm: '#FF671F' };
const ESTADO_GRUPO = { activo: 'Activos', legacy: 'Legacy', especial: 'Especiales' };
const EMPTY_EDIT = { name: '', email: '', phone: '', role: 'client', plan: '', comp_plan: false };

const AdminUsersPage = () => {
    const { api, user: me, planCatalog } = useAuth();
    const assignablePlans = Object.values(planCatalog || {}).filter(p => p.asignable);
    const planName = (code) => planCatalog?.[code]?.name || code;
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [q, setQ] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [showDeleted, setShowDeleted] = useState(false);
    const [modal, setModal] = useState({ open: false, user: null });
    const [form, setForm] = useState(EMPTY_EDIT);
    const [saving, setSaving] = useState(false);

    // Pestaña Equipo | Actividad (registro de auditoría)
    const [tab, setTab] = useState('equipo');
    const [auditEntries, setAuditEntries] = useState([]);
    useEffect(() => {
        if (tab !== 'actividad') return;
        api.get('/admin/audit').then(r => setAuditEntries(r.data.entries || [])).catch(() => toast.error('Error cargando la actividad'));
    }, [tab, api]);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = { staff: true };  // solo equipo (admin/coach)
            if (q.trim()) params.q = q.trim();
            if (roleFilter) params.role = roleFilter;
            if (showDeleted) params.include_deleted = true;
            const r = await api.get('/admin/users', { params });
            setUsers(r.data || []);
        } catch { toast.error('Error al cargar usuarios'); }
        finally { setLoading(false); }
    }, [api, q, roleFilter, showDeleted]);

    useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

    const openEdit = (u) => {
        setForm({ name: u.name || '', email: u.email || '', phone: u.phone || '', role: u.role || 'client', plan: u.plan || '', comp_plan: !!u.comp_plan });
        setModal({ open: true, user: u });
    };

    const save = async () => {
        setSaving(true);
        try {
            await api.put(`/admin/users/${modal.user.id}`, {
                name: form.name, email: form.email, phone: form.phone,
                role: form.role, plan: form.plan || null, comp_plan: form.comp_plan,
            });
            toast.success('Usuario actualizado');
            setModal({ open: false, user: null });
            load();
        } catch (e) { toast.error(e?.response?.data?.detail || 'Error al guardar'); }
        finally { setSaving(false); }
    };

    const softDelete = async (u) => {
        if (!window.confirm(`¿Dar de baja a ${u.name || u.email}? No podrá entrar, pero los datos se conservan y se puede reactivar.`)) return;
        try { await api.delete(`/admin/users/${u.id}`); toast.success('Usuario dado de baja'); load(); }
        catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo dar de baja'); }
    };
    const restore = async (u) => {
        try { await api.post(`/admin/users/${u.id}/restore`); toast.success('Usuario reactivado'); load(); }
        catch { toast.error('No se pudo reactivar'); }
    };

    // Restablecer contraseña: genera una temporal y la muestra una sola vez
    const [resetResult, setResetResult] = useState(null);
    const resetPassword = async (u) => {
        if (!window.confirm(`¿Generar una contraseña nueva para ${u.name || u.email}? La actual dejará de funcionar.`)) return;
        try {
            const r = await api.post(`/admin/users/${u.id}/reset-password`);
            setResetResult({ user: u, temp_password: r.data.temp_password });
        } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo restablecer'); }
    };
    const copyResetPassword = () => {
        if (!resetResult) return;
        navigator.clipboard.writeText(resetResult.temp_password)
            .then(() => toast.success('Contraseña copiada'))
            .catch(() => toast.error('No se pudo copiar'));
    };

    return (
        <div className="p-6 bg-[#0A0A0A] min-h-screen text-white">
            <div className="flex items-center justify-between mb-5">
                <div>
                    <p className="text-xs text-[#FF671F] uppercase tracking-wider mb-1">Administración</p>
                    <h1 className="text-2xl font-bold uppercase">Usuarios</h1>
                    <p className="text-white/40 text-sm">Equipo: admins y coaches. Los clientes se gestionan desde su ficha.</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex bg-[#111] rounded-lg p-0.5 border border-[#222]">
                        {[{ v: 'equipo', l: 'Equipo' }, { v: 'actividad', l: 'Actividad' }].map(t => (
                            <button key={t.v} onClick={() => setTab(t.v)}
                                className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${tab === t.v ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`}
                                data-testid={`users-tab-${t.v}`}>
                                {t.l}
                            </button>
                        ))}
                    </div>
                    <Badge className="bg-[#111] border border-[#222] text-white/60">{users.length}</Badge>
                </div>
            </div>

            {tab === 'actividad' && (
                <Card className="bg-[#111] border-[#222]">
                    <CardContent className="p-0">
                        {auditEntries.length === 0 ? (
                            <p className="text-white/30 text-sm text-center py-10">Sin actividad registrada todavía. Aquí quedará quién cambió macros, coaches, roles, contraseñas y leads.</p>
                        ) : (
                            <div className="divide-y divide-[#1a1a1a]">
                                {auditEntries.map(e => (
                                    <div key={e.id} className="flex items-start gap-3 px-4 py-3">
                                        <Badge className="bg-[#0A0A0A] border border-[#333] text-white/60 text-[10px] uppercase flex-shrink-0 mt-0.5">{e.action}</Badge>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-white/80">{e.detail}</p>
                                            <p className="text-[11px] text-white/30 mt-0.5">
                                                {e.actor_name} · {new Date(e.created_at).toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {tab === 'equipo' && (<>
            <div className="flex flex-col sm:flex-row gap-3 mb-4">
                <div className="relative flex-1">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                    <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Buscar por nombre o email..."
                        className="pl-9 bg-[#111] border-[#222] text-white" />
                </div>
                <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
                    className="bg-[#111] border border-[#222] text-white text-sm rounded-lg px-3 py-2">
                    <option value="">Todo el equipo</option>
                    {STAFF_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <button onClick={() => setShowDeleted(v => !v)}
                    className={`px-3 py-2 rounded-lg text-sm font-semibold border transition-colors ${showDeleted ? 'bg-[#FF671F] text-white border-[#FF671F]' : 'bg-[#111] text-white/60 border-[#222] hover:text-white'}`}>
                    Mostrar bajas
                </button>
            </div>

            {loading ? (
                <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-[#FF671F]" /></div>
            ) : (
                <Card className="bg-[#111] border-[#222]">
                    <CardContent className="p-0">
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-white/40 text-xs uppercase border-b border-[#222]">
                                        <th className="px-4 py-3">Nombre</th>
                                        <th className="px-4 py-3">Email</th>
                                        <th className="px-4 py-3">Rol</th>
                                        <th className="px-4 py-3">Plan</th>
                                        <th className="px-4 py-3">Estado</th>
                                        <th className="px-4 py-3 text-right">Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(u => (
                                        <tr key={u.id} className={`border-b border-[#1a1a1a] ${u.deleted ? 'opacity-50' : ''}`}>
                                            <td className="px-4 py-3 font-medium">{u.name || '-'}</td>
                                            <td className="px-4 py-3 text-white/60">{u.email}</td>
                                            <td className="px-4 py-3"><Badge className="bg-[#0A0A0A] border border-[#333] text-white/70">{ROLE_LABEL[u.role] || u.role}</Badge></td>
                                            <td className="px-4 py-3">
                                                {u.plan ? <span className="font-semibold" style={{ color: PLAN_COLORS[u.plan] || '#FF671F' }}>{planName(u.plan)}{u.comp_plan && <span className="text-white/30 text-xs ml-1">(cortesía)</span>}</span> : <span className="text-white/30">-</span>}
                                            </td>
                                            <td className="px-4 py-3">{u.deleted ? <Badge className="bg-red-500/15 text-red-400 border-0">Baja</Badge> : <Badge className="bg-green-500/15 text-green-500 border-0">Activo</Badge>}</td>
                                            <td className="px-4 py-3">
                                                <div className="flex items-center justify-end gap-1">
                                                    <button onClick={() => openEdit(u)} title="Editar" className="p-1.5 rounded text-white/40 hover:text-white hover:bg-white/10"><Pencil className="w-4 h-4" /></button>
                                                    {!u.deleted && <button onClick={() => resetPassword(u)} title="Restablecer contraseña" className="p-1.5 rounded text-white/40 hover:text-yellow-400 hover:bg-yellow-500/10" data-testid={`reset-pwd-${u.id}`}><KeyRound className="w-4 h-4" /></button>}
                                                    {u.deleted
                                                        ? <button onClick={() => restore(u)} title="Reactivar" className="p-1.5 rounded text-white/40 hover:text-green-400 hover:bg-green-500/10"><RotateCcw className="w-4 h-4" /></button>
                                                        : <button onClick={() => softDelete(u)} title="Baja lógica" disabled={u.id === me?.id} className="p-1.5 rounded text-white/40 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-30 disabled:cursor-not-allowed"><UserX className="w-4 h-4" /></button>}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                    {users.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-white/30">Sin usuarios</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}
            </>)}

            <Dialog open={!!resetResult} onOpenChange={(o) => !o && setResetResult(null)}>
                {resetResult && (
                    <DialogContent className="bg-[#111] border-[#333] max-w-md text-white" data-testid="reset-pwd-dialog">
                        <DialogHeader><DialogTitle className="uppercase tracking-wider flex items-center gap-2"><KeyRound className="w-5 h-5 text-yellow-400" /> Contraseña restablecida</DialogTitle></DialogHeader>
                        <div className="space-y-3">
                            <p className="text-white/60 text-sm">Nueva contraseña temporal de <span className="text-white font-semibold">{resetResult.user.name || resetResult.user.email}</span>:</p>
                            <div className="bg-[#0A0A0A] border border-[#333] rounded-xl p-4 text-center">
                                <span className="text-[#FF671F] font-mono font-bold text-lg" data-testid="reset-temp-password">{resetResult.temp_password}</span>
                            </div>
                            <p className="text-yellow-400/80 text-xs">Solo se muestra ahora: cópiala y pásasela por WhatsApp. Recomiéndale cambiarla al entrar (Perfil, Cambiar contraseña).</p>
                        </div>
                        <DialogFooter>
                            <Button onClick={copyResetPassword} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white">Copiar</Button>
                            <Button variant="outline" onClick={() => setResetResult(null)} className="bg-transparent border-[#333] text-white">Cerrar</Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>

            <Dialog open={modal.open} onOpenChange={(o) => !o && setModal({ open: false, user: null })}>
                <DialogContent className="bg-[#111] border-[#333] max-w-md text-white">
                    <DialogHeader><DialogTitle className="uppercase tracking-wider flex items-center gap-2"><Shield className="w-5 h-5 text-[#FF671F]" /> Editar usuario</DialogTitle></DialogHeader>
                    <div className="space-y-3">
                        <div><Label className="text-white/60 text-xs">Nombre</Label><Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white mt-1" /></div>
                        <div><Label className="text-white/60 text-xs">Email</Label><Input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white mt-1" /></div>
                        <div><Label className="text-white/60 text-xs">Teléfono</Label><Input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white mt-1" /></div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><Label className="text-white/60 text-xs">Rol</Label>
                                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                    {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                                </select>
                            </div>
                            <div><Label className="text-white/60 text-xs">Plan</Label>
                                <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                    <option value="">Sin plan</option>
                                    {['activo', 'legacy', 'especial'].map(estado => {
                                        const grupo = assignablePlans.filter(p => p.estado === estado);
                                        if (!grupo.length) return null;
                                        return (
                                            <optgroup key={estado} label={ESTADO_GRUPO[estado]}>
                                                {grupo.map(p => <option key={p.code} value={p.code}>{p.name}</option>)}
                                            </optgroup>
                                        );
                                    })}
                                </select>
                            </div>
                        </div>
                        <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer select-none">
                            <input type="checkbox" checked={form.comp_plan} onChange={e => setForm(f => ({ ...f, comp_plan: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                            Plan de cortesía (sin pago)
                        </label>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setModal({ open: false, user: null })} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                        <Button onClick={save} disabled={saving} className="bg-[#FF671F] text-white">{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Guardar'}</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AdminUsersPage;
