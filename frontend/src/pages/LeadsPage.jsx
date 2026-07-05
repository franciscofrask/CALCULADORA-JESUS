import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import {
    Plus, LayoutGrid, List, Phone, Mail, Calendar,
    Instagram, Globe, Users, MessageCircle, ChevronRight,
    ArrowRight, UserPlus, Trash2, X, Search, Filter, BarChart3
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as ChartTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const STATUSES = [
    { id: 'nuevo', label: 'Nuevo', color: '#3B82F6', bg: 'bg-blue-500/10 text-blue-400' },
    { id: 'contactado', label: 'Contactado', color: '#8B5CF6', bg: 'bg-purple-500/10 text-purple-400' },
    { id: 'llamada_agendada', label: 'Llamada agendada', color: '#F59E0B', bg: 'bg-yellow-500/10 text-yellow-400' },
    { id: 'propuesta_enviada', label: 'Propuesta enviada', color: '#FF671F', bg: 'bg-[#FF671F]/10 text-[#FF671F]' },
    { id: 'convertido', label: 'Convertido', color: '#22C55E', bg: 'bg-green-500/10 text-green-400' },
    { id: 'descartado', label: 'Descartado', color: '#6B7280', bg: 'bg-gray-500/10 text-muted-foreground' },
];

const SOURCES = [
    { id: 'instagram', label: 'Instagram', icon: Instagram },
    { id: 'web', label: 'Web', icon: Globe },
    { id: 'referido', label: 'Referido', icon: Users },
    { id: 'ghl', label: 'GoHighLevel', icon: MessageCircle },
    { id: 'whatsapp', label: 'WhatsApp', icon: Phone },
    { id: 'otro', label: 'Otro', icon: Plus },
];

const DISCARD_REASONS = [
    { id: 'precio', label: 'Precio' },
    { id: 'no_responde', label: 'No responde' },
    { id: 'no_interesado', label: 'No interesado' },
    { id: 'competencia', label: 'Se fue con otro' },
    { id: 'no_encaja', label: 'No encaja' },
    { id: 'otro', label: 'Otro' },
];
const discardLabel = (id) => DISCARD_REASONS.find(r => r.id === id)?.label || id;

const getStatusObj = (id) => STATUSES.find(s => s.id === id) || STATUSES[0];
const getSourceObj = (id) => SOURCES.find(s => s.id === id) || SOURCES[5];

// Seguimiento vencido: tiene fecha pasada y el lead sigue vivo
const isOverdue = (lead) => {
    if (!lead.next_action_date) return false;
    if (['convertido', 'descartado'].includes(lead.status)) return false;
    return lead.next_action_date < new Date().toISOString().slice(0, 10);
};

const LeadsPage = () => {
    const { api } = useAuth();
    const [leads, setLeads] = useState([]);
    const [staff, setStaff] = useState([]);
    const [loading, setLoading] = useState(true);
    const [view, setView] = useState('kanban');
    const [search, setSearch] = useState('');

    const staffName = (id) => staff.find(u => u.id === id)?.name || null;

    // Modals
    const [newLeadOpen, setNewLeadOpen] = useState(false);
    const [detailLead, setDetailLead] = useState(null);
    const [convertLead, setConvertLead] = useState(null);
    const [convertPlan, setConvertPlan] = useState('gold');
    const [convertTrainer, setConvertTrainer] = useState('');
    const [convertResult, setConvertResult] = useState(null);

    // New lead form
    const [newLead, setNewLead] = useState({ name: '', email: '', phone: '', source: 'instagram', notes: '', assigned_to: '' });

    const fetchLeads = useCallback(async () => {
        try {
            const res = await api.get('/leads');
            setLeads(res.data.leads || []);
        } catch (e) { toast.error('Error cargando leads'); }
        finally { setLoading(false); }
    }, [api]);

    useEffect(() => { fetchLeads(); }, [fetchLeads]);
    useEffect(() => {
        api.get('/admin/users', { params: { staff: true } }).then(r => setStaff(r.data || [])).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Metricas (se cargan al entrar en esa vista)
    const [metrics, setMetrics] = useState(null);
    useEffect(() => {
        if (view !== 'metricas') return;
        api.get('/leads/stats/metrics').then(r => setMetrics(r.data)).catch(() => toast.error('Error cargando métricas'));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [view, leads]);

    // Actualizacion generica de un campo del lead (responsable, seguimiento...)
    const handleUpdateField = async (leadId, field, value) => {
        try {
            const res = await api.put(`/leads/${leadId}`, { [field]: value });
            setLeads(prev => prev.map(l => l.id === leadId ? res.data : l));
            if (detailLead?.id === leadId) setDetailLead(res.data);
        } catch (e) { toast.error(e.response?.data?.detail || 'Error actualizando'); }
    };

    // Drag & drop del kanban (API nativa HTML5)
    const [draggingId, setDraggingId] = useState(null);
    const [dragOverCol, setDragOverCol] = useState(null);
    const handleDrop = (e, statusId) => {
        e.preventDefault();
        setDragOverCol(null);
        const leadId = e.dataTransfer.getData('text/plain') || draggingId;
        setDraggingId(null);
        const lead = leads.find(l => l.id === leadId);
        if (!lead || lead.status === statusId) return;
        handleUpdateStatus(leadId, statusId);
    };

    // Historial de interacciones
    const [activityText, setActivityText] = useState('');
    const handleAddActivity = async () => {
        if (!activityText.trim() || !detailLead) return;
        try {
            const res = await api.post(`/leads/${detailLead.id}/activity`, { text: activityText.trim() });
            const addEntry = (l) => ({ ...l, activity: [...(l.activity || []), res.data] });
            setDetailLead(addEntry);
            setLeads(prev => prev.map(l => l.id === detailLead.id ? addEntry(l) : l));
            setActivityText('');
        } catch (e) { toast.error(e.response?.data?.detail || 'Error guardando la nota'); }
    };
    const handleDeleteActivity = async (entryId) => {
        if (!detailLead) return;
        try {
            await api.delete(`/leads/${detailLead.id}/activity/${entryId}`);
            const rmEntry = (l) => ({ ...l, activity: (l.activity || []).filter(a => a.id !== entryId) });
            setDetailLead(rmEntry);
            setLeads(prev => prev.map(l => l.id === detailLead.id ? rmEntry(l) : l));
        } catch (e) { toast.error('Error borrando la nota'); }
    };

    const handleCreateLead = async () => {
        if (!newLead.name.trim()) { toast.error('Nombre es obligatorio'); return; }
        try {
            await api.post('/leads', { ...newLead, assigned_to: newLead.assigned_to || null });
            toast.success('Lead creado');
            setNewLeadOpen(false);
            setNewLead({ name: '', email: '', phone: '', source: 'instagram', notes: '', assigned_to: '' });
            fetchLeads();
        } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
    };

    // Descarte con motivo
    const [discardLead, setDiscardLead] = useState(null);
    const [discardReason, setDiscardReason] = useState('no_responde');
    const [discardNote, setDiscardNote] = useState('');

    const handleUpdateStatus = async (leadId, newStatus) => {
        // Descartar pide motivo antes de aplicar
        if (newStatus === 'descartado') {
            const lead = leads.find(l => l.id === leadId);
            if (lead) { setDiscardReason('no_responde'); setDiscardNote(''); setDiscardLead(lead); }
            return;
        }
        try {
            const res = await api.put(`/leads/${leadId}`, { status: newStatus });
            setLeads(prev => prev.map(l => l.id === leadId ? res.data : l));
            if (detailLead?.id === leadId) setDetailLead(res.data);
        } catch (e) { toast.error('Error actualizando estado'); }
    };

    const handleConfirmDiscard = async () => {
        if (!discardLead) return;
        try {
            const res = await api.put(`/leads/${discardLead.id}`, { status: 'descartado', discard_reason: discardReason });
            let updated = res.data;
            if (discardNote.trim()) {
                const noteRes = await api.post(`/leads/${discardLead.id}/activity`, { text: discardNote.trim() });
                updated = { ...updated, activity: [...(updated.activity || []), noteRes.data] };
            }
            setLeads(prev => prev.map(l => l.id === discardLead.id ? updated : l));
            if (detailLead?.id === discardLead.id) setDetailLead(updated);
            setDiscardLead(null);
            toast.success('Lead descartado');
        } catch (e) { toast.error(e.response?.data?.detail || 'Error descartando'); }
    };

    const handleUpdateNotes = async (leadId, notes) => {
        try {
            await api.put(`/leads/${leadId}`, { notes });
            setLeads(prev => prev.map(l => l.id === leadId ? { ...l, notes } : l));
        } catch (e) { toast.error('Error guardando notas'); }
    };

    const handleConvert = async () => {
        if (!convertLead) return;
        try {
            const res = await api.post(`/leads/${convertLead.id}/convert`, { plan: convertPlan, trainer_id: convertTrainer || null });
            toast.success(res.data.message);
            setConvertResult(res.data);
            setDetailLead(null);
            fetchLeads();
        } catch (e) { toast.error(e.response?.data?.detail || 'Error convirtiendo'); }
    };

    const closeConvert = () => { setConvertLead(null); setConvertResult(null); setConvertTrainer(''); };

    const copyWelcomeMessage = () => {
        if (!convertResult) return;
        const firstName = (convertResult.name || '').split(' ')[0] || 'campeón/a';
        const msg = `Hola ${firstName}! Ya tienes tu cuenta lista en 12EN12.\n\n` +
            `Entra en: ${window.location.origin}\n` +
            `Usuario: ${convertResult.email}\n` +
            `Contraseña temporal: ${convertResult.temp_password}\n\n` +
            `Cámbiala en cuanto entres (Perfil > Contraseña). Cualquier duda me escribes. A por ello!`;
        navigator.clipboard.writeText(msg)
            .then(() => toast.success('Mensaje copiado, listo para pegar en WhatsApp'))
            .catch(() => toast.error('No se pudo copiar'));
    };

    const handleDelete = async (leadId) => {
        try {
            await api.delete(`/leads/${leadId}`);
            toast.success('Lead eliminado');
            setDetailLead(null);
            fetchLeads();
        } catch (e) { toast.error('Error eliminando'); }
    };

    const filtered = leads.filter(l =>
        !search || l.name?.toLowerCase().includes(search.toLowerCase()) ||
        l.email?.toLowerCase().includes(search.toLowerCase()) ||
        l.phone?.includes(search)
    );

    // Counts by status
    const counts = {};
    STATUSES.forEach(s => { counts[s.id] = filtered.filter(l => l.status === s.id).length; });

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="leads-page">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>LEADS</h1>
                    <p className="text-white/40 text-sm">
                        {leads.length} prospectos
                        {leads.filter(isOverdue).length > 0 && <span className="text-red-400 font-medium"> · {leads.filter(isOverdue).length} seguimientos vencidos</span>}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {/* View toggle */}
                    <div className="flex bg-[#111] rounded-lg p-0.5 border border-[#222]">
                        <button onClick={() => setView('kanban')} className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${view === 'kanban' ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`} data-testid="view-kanban"><LayoutGrid className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setView('tabla')} className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${view === 'tabla' ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`} data-testid="view-tabla"><List className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setView('metricas')} className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${view === 'metricas' ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`} data-testid="view-metricas"><BarChart3 className="w-3.5 h-3.5" /></button>
                    </div>
                    <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" onClick={() => setNewLeadOpen(true)} data-testid="add-lead-btn"><Plus className="w-4 h-4 mr-1" />Nuevo lead</Button>
                </div>
            </div>

            {/* Search */}
            <div className="relative max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar por nombre, email, teléfono..." className="pl-9 bg-[#111] border-[#222] text-white" data-testid="lead-search" />
            </div>

            {/* ========== KANBAN VIEW ========== */}
            {view === 'kanban' && (
                <div className="flex gap-3 overflow-x-auto pb-4" data-testid="kanban-board">
                    {STATUSES.map(status => {
                        const columnLeads = filtered.filter(l => l.status === status.id);
                        return (
                            <div key={status.id} className="flex-shrink-0 w-64" data-testid={`kanban-col-${status.id}`}
                                onDragOver={e => { e.preventDefault(); if (dragOverCol !== status.id) setDragOverCol(status.id); }}
                                onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setDragOverCol(null); }}
                                onDrop={e => handleDrop(e, status.id)}>
                                <div className="flex items-center gap-2 mb-3 px-1">
                                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: status.color }} />
                                    <span className="text-xs font-bold text-white uppercase tracking-wider">{status.label}</span>
                                    <Badge className="bg-white/5 text-white/50 border-0 text-[10px] ml-auto">{columnLeads.length}</Badge>
                                </div>
                                <div className={`space-y-2 min-h-[100px] rounded-xl transition-all ${dragOverCol === status.id && draggingId ? 'ring-1 ring-[#FF671F]/60 bg-[#FF671F]/5' : ''}`}>
                                    {columnLeads.map(lead => (
                                        <KanbanCard key={lead.id} lead={lead} assignedName={staffName(lead.assigned_to)} onClick={() => setDetailLead(lead)}
                                            dragging={draggingId === lead.id}
                                            onDragStart={e => { e.dataTransfer.setData('text/plain', lead.id); e.dataTransfer.effectAllowed = 'move'; setDraggingId(lead.id); }}
                                            onDragEnd={() => { setDraggingId(null); setDragOverCol(null); }} />
                                    ))}
                                    {columnLeads.length === 0 && <div className="border border-dashed border-[#222] rounded-xl p-6 text-center text-white/20 text-xs">{dragOverCol === status.id && draggingId ? 'Suelta aquí' : 'Sin leads'}</div>}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* ========== TABLE VIEW ========== */}
            {view === 'tabla' && (
                <Card className="bg-[#111] border-[#222] overflow-hidden" data-testid="leads-table">
                    <CardContent className="p-0">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-[#222]">
                                        {['Nombre', 'Email', 'Teléfono', 'Origen', 'Estado', 'Asignado', 'Seguimiento', 'Fecha', 'Notas'].map(h => (
                                            <th key={h} className="text-left text-[10px] text-white/40 uppercase tracking-wider px-4 py-3">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {filtered.map(lead => {
                                        const st = getStatusObj(lead.status);
                                        const src = getSourceObj(lead.source);
                                        return (
                                            <tr key={lead.id} className="border-b border-[#1A1A1A] hover:bg-white/5 cursor-pointer" onClick={() => setDetailLead(lead)} data-testid={`table-row-${lead.id}`}>
                                                <td className="px-4 py-3 text-white text-sm font-medium">{lead.name}</td>
                                                <td className="px-4 py-3 text-white/50 text-sm">{lead.email || '-'}</td>
                                                <td className="px-4 py-3 text-white/50 text-sm">{lead.phone || '-'}</td>
                                                <td className="px-4 py-3"><Badge className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-[10px]">{src.label}</Badge></td>
                                                <td className="px-4 py-3">
                                                    <select value={lead.status} onChange={e => { e.stopPropagation(); handleUpdateStatus(lead.id, e.target.value); }} onClick={e => e.stopPropagation()} className="bg-[#0A0A0A] border border-[#333] text-white text-xs rounded px-2 py-1" data-testid={`status-select-${lead.id}`}>
                                                        {STATUSES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                                                    </select>
                                                </td>
                                                <td className="px-4 py-3 text-white/50 text-xs">{staffName(lead.assigned_to) || <span className="text-white/25">Sin asignar</span>}</td>
                                                <td className={`px-4 py-3 text-xs ${isOverdue(lead) ? 'text-red-400 font-bold' : 'text-white/50'}`}>
                                                    {lead.next_action_date ? new Date(lead.next_action_date + 'T00:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'}
                                                    {isOverdue(lead) && ' ⚠'}
                                                </td>
                                                <td className="px-4 py-3 text-white/30 text-xs">{new Date(lead.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</td>
                                                <td className="px-4 py-3 text-white/30 text-xs truncate max-w-[150px]">{lead.notes || '-'}</td>
                                            </tr>
                                        );
                                    })}
                                    {filtered.length === 0 && <tr><td colSpan={9} className="text-center text-white/30 py-8">Sin leads</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ========== METRICS VIEW ========== */}
            {view === 'metricas' && metrics && (
                <div className="space-y-4" data-testid="leads-metrics">
                    {/* KPIs */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                            { label: 'Leads totales', value: metrics.total },
                            { label: 'Convertidos', value: metrics.converted },
                            { label: 'Tasa de conversión', value: `${metrics.conversion_rate}%` },
                            { label: 'Días hasta convertir', value: metrics.avg_days_to_convert != null ? metrics.avg_days_to_convert : '-' },
                        ].map(kpi => (
                            <Card key={kpi.label} className="bg-[#111] border-[#222]"><CardContent className="p-4">
                                <p className="text-white/40 text-[10px] uppercase tracking-wider">{kpi.label}</p>
                                <p className="text-white text-2xl font-bold mt-1" style={{ fontFamily: 'Barlow Condensed' }}>{kpi.value}</p>
                            </CardContent></Card>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* Embudo por estado */}
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-4">
                            <p className="text-white/40 text-xs uppercase tracking-wider mb-3">Embudo por estado</p>
                            <div className="space-y-2">
                                {STATUSES.map(s => {
                                    const n = metrics.by_status?.[s.id] || 0;
                                    const pct = metrics.total ? (n / metrics.total) * 100 : 0;
                                    return (
                                        <div key={s.id}>
                                            <div className="flex justify-between text-xs mb-0.5">
                                                <span className="text-white/60">{s.label}</span>
                                                <span className="text-white/40">{n}</span>
                                            </div>
                                            <div className="h-2 bg-[#0A0A0A] rounded-full overflow-hidden">
                                                <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: s.color }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent></Card>

                        {/* Por origen */}
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-4">
                            <p className="text-white/40 text-xs uppercase tracking-wider mb-3">Conversión por origen</p>
                            <div className="space-y-2.5">
                                {Object.entries(metrics.by_source || {}).sort((a, b) => b[1].total - a[1].total).map(([src, d]) => {
                                    const rate = d.total ? Math.round((d.convertidos / d.total) * 100) : 0;
                                    return (
                                        <div key={src} className="flex items-center gap-3">
                                            <span className="text-white/60 text-xs w-24 truncate">{getSourceObj(src).label}</span>
                                            <div className="flex-1 h-2 bg-[#0A0A0A] rounded-full overflow-hidden">
                                                <div className="h-full bg-[#FF671F] rounded-full" style={{ width: `${rate}%` }} />
                                            </div>
                                            <span className="text-white/40 text-xs w-28 text-right">{d.convertidos}/{d.total} · {rate}%</span>
                                        </div>
                                    );
                                })}
                                {Object.keys(metrics.by_source || {}).length === 0 && <p className="text-white/20 text-xs">Sin datos</p>}
                            </div>
                        </CardContent></Card>

                        {/* Motivos de descarte */}
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-4">
                            <p className="text-white/40 text-xs uppercase tracking-wider mb-3">Por qué se pierden (motivos de descarte)</p>
                            <div className="space-y-2.5">
                                {Object.entries(metrics.discard_reasons || {}).sort((a, b) => b[1] - a[1]).map(([reason, n]) => {
                                    const totalDesc = Object.values(metrics.discard_reasons || {}).reduce((a, b) => a + b, 0);
                                    const pct = totalDesc ? Math.round((n / totalDesc) * 100) : 0;
                                    return (
                                        <div key={reason} className="flex items-center gap-3">
                                            <span className="text-white/60 text-xs w-24 truncate">{reason === 'sin_motivo' ? 'Sin motivo' : discardLabel(reason)}</span>
                                            <div className="flex-1 h-2 bg-[#0A0A0A] rounded-full overflow-hidden">
                                                <div className="h-full bg-red-500/70 rounded-full" style={{ width: `${pct}%` }} />
                                            </div>
                                            <span className="text-white/40 text-xs w-16 text-right">{n} · {pct}%</span>
                                        </div>
                                    );
                                })}
                                {Object.keys(metrics.discard_reasons || {}).length === 0 && <p className="text-white/20 text-xs">Ningún lead descartado todavía</p>}
                            </div>
                        </CardContent></Card>

                        {/* Leads por semana */}
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-4">
                            <p className="text-white/40 text-xs uppercase tracking-wider mb-3">Leads nuevos por semana</p>
                            {metrics.weekly?.length > 0 ? (
                                <ResponsiveContainer width="100%" height={160}>
                                    <BarChart data={metrics.weekly}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                                        <XAxis dataKey="week" tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
                                        <YAxis allowDecimals={false} tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} width={24} />
                                        <ChartTooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8 }} labelStyle={{ color: '#fff' }} itemStyle={{ color: '#FF671F' }} />
                                        <Bar dataKey="count" name="Leads" fill="#FF671F" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : <p className="text-white/20 text-xs">Sin datos</p>}
                        </CardContent></Card>
                    </div>
                </div>
            )}

            {/* ========== NEW LEAD MODAL ========== */}
            <Dialog open={newLeadOpen} onOpenChange={setNewLeadOpen}>
                <DialogContent className="bg-[#111] border-[#333]" data-testid="new-lead-modal">
                    <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">Nuevo lead</DialogTitle></DialogHeader>
                    <div className="space-y-3">
                        <div><Label className="text-white/60 text-xs">Nombre *</Label><Input value={newLead.name} onChange={e => setNewLead({...newLead, name: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white" data-testid="new-lead-name" /></div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><Label className="text-white/60 text-xs">Email</Label><Input value={newLead.email} onChange={e => setNewLead({...newLead, email: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white" data-testid="new-lead-email" /></div>
                            <div><Label className="text-white/60 text-xs">Teléfono</Label><Input value={newLead.phone} onChange={e => setNewLead({...newLead, phone: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                        </div>
                        <div><Label className="text-white/60 text-xs">Origen</Label>
                            <div className="flex gap-1.5 mt-1 flex-wrap">{SOURCES.map(s => (
                                <button key={s.id} onClick={() => setNewLead({...newLead, source: s.id})} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${newLead.source === s.id ? 'bg-[#FF671F] text-white' : 'bg-[#1A1A1A] text-white/40 border border-[#333]'}`}>{s.label}</button>
                            ))}</div>
                        </div>
                        <div><Label className="text-white/60 text-xs">Asignado a</Label>
                            <select value={newLead.assigned_to} onChange={e => setNewLead({...newLead, assigned_to: e.target.value})}
                                className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1" data-testid="new-lead-assigned">
                                <option value="">Sin asignar</option>
                                {staff.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                            </select>
                        </div>
                        <div><Label className="text-white/60 text-xs">Notas</Label><Textarea value={newLead.notes} onChange={e => setNewLead({...newLead, notes: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white" rows={2} /></div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setNewLeadOpen(false)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                        <Button onClick={handleCreateLead} className="bg-[#FF671F] text-white" data-testid="save-new-lead"><Plus className="w-4 h-4 mr-1" />Crear</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ========== DETAIL MODAL ========== */}
            <Dialog open={!!detailLead} onOpenChange={o => !o && setDetailLead(null)}>
                {detailLead && (
                    <DialogContent className="bg-[#111] border-[#333] max-w-lg" data-testid="lead-detail-modal">
                        <DialogHeader>
                            <DialogTitle className="text-white flex items-center gap-2">
                                {detailLead.name}
                                <Badge className={getStatusObj(detailLead.status).bg + ' border-0 text-xs'}>{getStatusObj(detailLead.status).label}</Badge>
                                {detailLead.status === 'descartado' && detailLead.discard_reason && (
                                    <Badge className="bg-red-500/10 text-red-400 border-0 text-xs">{discardLabel(detailLead.discard_reason)}</Badge>
                                )}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div className="flex items-center gap-2 text-white/60 text-sm"><Mail className="w-3.5 h-3.5" />{detailLead.email || '-'}</div>
                                <div className="flex items-center gap-2 text-white/60 text-sm"><Phone className="w-3.5 h-3.5" />{detailLead.phone || '-'}</div>
                                <div className="flex items-center gap-2 text-white/60 text-sm"><Calendar className="w-3.5 h-3.5" />{new Date(detailLead.created_at).toLocaleDateString('es-ES')}</div>
                                <div className="flex items-center gap-2 text-white/60 text-sm"><Badge className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{getSourceObj(detailLead.source).label}</Badge></div>
                            </div>

                            {/* Status change */}
                            <div>
                                <Label className="text-white/40 text-xs">Mover a:</Label>
                                <div className="flex gap-1.5 mt-1.5 flex-wrap">{STATUSES.filter(s => s.id !== detailLead.status).map(s => (
                                    <button key={s.id} onClick={() => handleUpdateStatus(detailLead.id, s.id)} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[#1A1A1A] text-white/60 border border-[#333] hover:border-[#FF671F] transition-all" data-testid={`move-to-${s.id}`}>
                                        <span className="w-2 h-2 rounded-full inline-block mr-1.5" style={{ backgroundColor: s.color }} />{s.label}
                                    </button>
                                ))}</div>
                            </div>

                            {/* Responsable y seguimiento */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-white/40 text-xs">Asignado a</Label>
                                    <select value={detailLead.assigned_to || ''} onChange={e => handleUpdateField(detailLead.id, 'assigned_to', e.target.value || null)}
                                        className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1" data-testid="lead-assigned-to">
                                        <option value="">Sin asignar</option>
                                        {staff.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <Label className="text-white/40 text-xs">Próximo contacto</Label>
                                    <input type="date" value={detailLead.next_action_date || ''} onChange={e => handleUpdateField(detailLead.id, 'next_action_date', e.target.value || null)}
                                        className={`w-full bg-[#0A0A0A] border rounded-lg px-2 py-2 mt-1 text-sm ${isOverdue(detailLead) ? 'border-red-500/60 text-red-400' : 'border-[#333] text-white'}`} data-testid="lead-next-action" />
                                    {isOverdue(detailLead) && <p className="text-red-400 text-[10px] mt-1">Seguimiento vencido</p>}
                                </div>
                            </div>

                            {/* Notes */}
                            <div>
                                <Label className="text-white/40 text-xs">Notas</Label>
                                <Textarea defaultValue={detailLead.notes || ''} onBlur={e => handleUpdateNotes(detailLead.id, e.target.value)} className="bg-[#0A0A0A] border-[#333] text-white mt-1" rows={3} data-testid="lead-notes" placeholder="Escribe notas sobre este prospecto..." />
                            </div>

                            {/* Historial de interacciones */}
                            <div>
                                <Label className="text-white/40 text-xs">Historial</Label>
                                <div className="flex gap-2 mt-1">
                                    <Input value={activityText} onChange={e => setActivityText(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleAddActivity()}
                                        placeholder="Registrar interacción: 'le llamé, quedamos en...'"
                                        className="bg-[#0A0A0A] border-[#333] text-white text-sm" data-testid="activity-input" />
                                    <Button size="sm" onClick={handleAddActivity} disabled={!activityText.trim()} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" data-testid="activity-add">
                                        <Plus className="w-4 h-4" />
                                    </Button>
                                </div>
                                <div className="mt-2 space-y-1.5 max-h-44 overflow-y-auto pr-1" data-testid="activity-timeline">
                                    {[...(detailLead.activity || [])].reverse().map(entry => (
                                        <div key={entry.id} className="group flex items-start gap-2 bg-[#0A0A0A] border border-[#222] rounded-lg px-3 py-2">
                                            <div className="flex-1 min-w-0">
                                                <p className={`text-xs ${entry.type === 'sistema' ? 'text-white/40 italic' : 'text-white/80'}`}>{entry.text}</p>
                                                <p className="text-[10px] text-white/25 mt-0.5">
                                                    {entry.author} · {new Date(entry.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })} {new Date(entry.created_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                                                </p>
                                            </div>
                                            {entry.type === 'nota' && (
                                                <button onClick={() => handleDeleteActivity(entry.id)} className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400 transition-all" title="Borrar nota">
                                                    <X className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                    {(detailLead.activity || []).length === 0 && <p className="text-white/20 text-xs py-2">Sin interacciones registradas todavía</p>}
                                </div>
                            </div>
                        </div>
                        <DialogFooter className="flex justify-between">
                            <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={() => handleDelete(detailLead.id)}><Trash2 className="w-3.5 h-3.5 mr-1" />Eliminar</Button>
                            <div className="flex gap-2">
                                {detailLead.status !== 'convertido' && detailLead.email && (
                                    <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => setConvertLead(detailLead)} data-testid="convert-btn"><UserPlus className="w-3.5 h-3.5 mr-1" />Convertir a cliente</Button>
                                )}
                                <Button variant="outline" size="sm" onClick={() => setDetailLead(null)} className="bg-transparent border-[#333] text-white">Cerrar</Button>
                            </div>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>

            {/* ========== DISCARD MODAL ========== */}
            <Dialog open={!!discardLead} onOpenChange={o => !o && setDiscardLead(null)}>
                {discardLead && (
                    <DialogContent className="bg-[#111] border-[#333]" data-testid="discard-modal">
                        <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">Descartar lead</DialogTitle></DialogHeader>
                        <div className="space-y-3">
                            <p className="text-white/60 text-sm">¿Por qué se descarta a <span className="text-white font-semibold">{discardLead.name || discardLead.email}</span>?</p>
                            <div className="flex gap-1.5 flex-wrap">{DISCARD_REASONS.map(r => (
                                <button key={r.id} onClick={() => setDiscardReason(r.id)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${discardReason === r.id ? 'bg-[#FF671F] text-white' : 'bg-[#1A1A1A] text-white/40 border border-[#333]'}`}
                                    data-testid={`discard-reason-${r.id}`}>{r.label}</button>
                            ))}</div>
                            <div>
                                <Label className="text-white/60 text-xs">Detalle (opcional)</Label>
                                <Textarea value={discardNote} onChange={e => setDiscardNote(e.target.value)} className="bg-[#0A0A0A] border-[#333] text-white mt-1" rows={2} placeholder="Ej: le pareció caro el plan Gold, retomar en enero..." />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setDiscardLead(null)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                            <Button onClick={handleConfirmDiscard} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-discard">Descartar</Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>

            {/* ========== CONVERT MODAL ========== */}
            <Dialog open={!!convertLead} onOpenChange={o => !o && closeConvert()}>
                {convertLead && !convertResult && (
                    <DialogContent className="bg-[#111] border-[#333]" data-testid="convert-modal">
                        <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">Convertir a cliente</DialogTitle></DialogHeader>
                        <div className="space-y-3">
                            <p className="text-white/60 text-sm">Se creará una cuenta para <span className="text-white font-semibold">{convertLead.name}</span> ({convertLead.email})</p>
                            <div><Label className="text-white/60 text-xs">Plan</Label>
                                <div className="flex gap-2 mt-1">{['gold', 'silver', 'bronze', 'elm'].map(p => (
                                    <button key={p} onClick={() => setConvertPlan(p)} className={`px-4 py-2 rounded-lg text-xs font-bold uppercase transition-all ${convertPlan === p ? 'bg-[#FF671F] text-white' : 'bg-[#1A1A1A] text-white/40 border border-[#333]'}`} data-testid={`plan-${p}`}>{p}</button>
                                ))}</div>
                            </div>
                            <div><Label className="text-white/60 text-xs">Coach</Label>
                                <select value={convertTrainer} onChange={e => setConvertTrainer(e.target.value)}
                                    className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1" data-testid="convert-trainer">
                                    <option value="">Sin asignar (asignar después)</option>
                                    {staff.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                                </select>
                            </div>
                            <p className="text-white/30 text-xs">Se generará una contraseña temporal segura; la verás en el siguiente paso junto al mensaje de bienvenida.</p>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={closeConvert} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                            <Button onClick={handleConvert} className="bg-green-600 hover:bg-green-700 text-white" data-testid="confirm-convert"><UserPlus className="w-4 h-4 mr-1" />Convertir</Button>
                        </DialogFooter>
                    </DialogContent>
                )}
                {convertLead && convertResult && (
                    <DialogContent className="bg-[#111] border-[#333]" data-testid="convert-result-modal">
                        <DialogHeader><DialogTitle className="text-white uppercase tracking-wider flex items-center gap-2">
                            <UserPlus className="w-4 h-4 text-green-500" />Cliente creado
                        </DialogTitle></DialogHeader>
                        <div className="space-y-3">
                            <p className="text-white/60 text-sm"><span className="text-white font-semibold">{convertResult.name || convertResult.email}</span> ya es cliente (plan {convertResult.plan}{convertResult.trainer_name ? `, coach ${convertResult.trainer_name}` : ', sin coach'}).</p>
                            <div className="bg-[#0A0A0A] border border-[#333] rounded-xl p-4 space-y-2">
                                <div className="flex justify-between text-sm"><span className="text-white/40">Usuario</span><span className="text-white font-mono">{convertResult.email}</span></div>
                                <div className="flex justify-between text-sm"><span className="text-white/40">Contraseña temporal</span><span className="text-[#FF671F] font-mono font-bold" data-testid="temp-password">{convertResult.temp_password}</span></div>
                            </div>
                            <p className="text-yellow-400/80 text-xs">Esta contraseña solo se muestra ahora: cópiala o envía el mensaje antes de cerrar. Recomiéndale cambiarla al entrar.</p>
                        </div>
                        <DialogFooter>
                            <Button onClick={copyWelcomeMessage} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" data-testid="copy-welcome"><MessageCircle className="w-4 h-4 mr-1" />Copiar mensaje de bienvenida</Button>
                            <Button variant="outline" onClick={closeConvert} className="bg-transparent border-[#333] text-white">Cerrar</Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </div>
    );
};

// ========== KANBAN CARD ==========
const KanbanCard = ({ lead, onClick, assignedName, dragging, onDragStart, onDragEnd }) => {
    const src = getSourceObj(lead.source);
    const SrcIcon = src.icon;
    const overdue = isOverdue(lead);
    return (
        <Card draggable onDragStart={onDragStart} onDragEnd={onDragEnd}
            className={`bg-[#111] cursor-grab active:cursor-grabbing transition-all ${dragging ? 'opacity-40' : ''} ${overdue ? 'border-red-500/50 hover:border-red-400' : 'border-[#222] hover:border-[#FF671F]/40'}`} onClick={onClick} data-testid={`kanban-card-${lead.id}`}>
            <CardContent className="p-3">
                <div className="flex items-center gap-2">
                    <p className="text-white text-sm font-medium truncate flex-1">{lead.name || lead.email || 'Sin nombre'}</p>
                    {lead.status === 'descartado' && lead.discard_reason && (
                        <span className="text-[9px] text-red-400/70 bg-red-500/10 rounded px-1.5 py-0.5 flex-shrink-0">{discardLabel(lead.discard_reason)}</span>
                    )}
                </div>
                <div className="flex items-center gap-3 mt-1.5 text-white/40 text-xs">
                    {lead.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{lead.phone}</span>}
                    <span className="flex items-center gap-1 ml-auto"><SrcIcon className="w-3 h-3" />{src.label}</span>
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                    <p className="text-white/20 text-[10px]">{new Date(lead.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</p>
                    {assignedName && <span className="flex items-center gap-1 text-[10px] text-white/40"><Users className="w-3 h-3" />{assignedName}</span>}
                    {lead.next_action_date && (
                        <span className={`flex items-center gap-1 text-[10px] ml-auto ${overdue ? 'text-red-400 font-bold' : 'text-white/40'}`}>
                            <Calendar className="w-3 h-3" />{new Date(lead.next_action_date + 'T00:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
                        </span>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default LeadsPage;
