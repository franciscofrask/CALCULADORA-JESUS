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
    ArrowRight, UserPlus, Trash2, X, Search, Filter
} from 'lucide-react';

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

const getStatusObj = (id) => STATUSES.find(s => s.id === id) || STATUSES[0];
const getSourceObj = (id) => SOURCES.find(s => s.id === id) || SOURCES[5];

const LeadsPage = () => {
    const { api } = useAuth();
    const [leads, setLeads] = useState([]);
    const [loading, setLoading] = useState(true);
    const [view, setView] = useState('kanban');
    const [search, setSearch] = useState('');

    // Modals
    const [newLeadOpen, setNewLeadOpen] = useState(false);
    const [detailLead, setDetailLead] = useState(null);
    const [convertLead, setConvertLead] = useState(null);
    const [convertPlan, setConvertPlan] = useState('gold');

    // New lead form
    const [newLead, setNewLead] = useState({ name: '', email: '', phone: '', source: 'instagram', notes: '' });

    const fetchLeads = useCallback(async () => {
        try {
            const res = await api.get('/leads');
            setLeads(res.data.leads || []);
        } catch (e) { toast.error('Error cargando leads'); }
        finally { setLoading(false); }
    }, [api]);

    useEffect(() => { fetchLeads(); }, [fetchLeads]);

    const handleCreateLead = async () => {
        if (!newLead.name.trim()) { toast.error('Nombre es obligatorio'); return; }
        try {
            await api.post('/leads', newLead);
            toast.success('Lead creado');
            setNewLeadOpen(false);
            setNewLead({ name: '', email: '', phone: '', source: 'instagram', notes: '' });
            fetchLeads();
        } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
    };

    const handleUpdateStatus = async (leadId, newStatus) => {
        try {
            await api.put(`/leads/${leadId}`, { status: newStatus });
            setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: newStatus } : l));
            if (detailLead?.id === leadId) setDetailLead(prev => ({ ...prev, status: newStatus }));
        } catch (e) { toast.error('Error actualizando estado'); }
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
            const res = await api.post(`/leads/${convertLead.id}/convert`, { plan: convertPlan });
            toast.success(res.data.message);
            setConvertLead(null);
            setDetailLead(null);
            fetchLeads();
        } catch (e) { toast.error(e.response?.data?.detail || 'Error convirtiendo'); }
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
                    <p className="text-white/40 text-sm">{leads.length} prospectos</p>
                </div>
                <div className="flex items-center gap-2">
                    {/* View toggle */}
                    <div className="flex bg-[#111] rounded-lg p-0.5 border border-[#222]">
                        <button onClick={() => setView('kanban')} className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${view === 'kanban' ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`} data-testid="view-kanban"><LayoutGrid className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setView('tabla')} className={`px-3 py-1.5 rounded text-xs font-bold uppercase transition-all ${view === 'tabla' ? 'bg-[#FF671F] text-white' : 'text-white/40 hover:text-white'}`} data-testid="view-tabla"><List className="w-3.5 h-3.5" /></button>
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
                            <div key={status.id} className="flex-shrink-0 w-64" data-testid={`kanban-col-${status.id}`}>
                                <div className="flex items-center gap-2 mb-3 px-1">
                                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: status.color }} />
                                    <span className="text-xs font-bold text-white uppercase tracking-wider">{status.label}</span>
                                    <Badge className="bg-white/5 text-white/50 border-0 text-[10px] ml-auto">{columnLeads.length}</Badge>
                                </div>
                                <div className="space-y-2 min-h-[100px]">
                                    {columnLeads.map(lead => <KanbanCard key={lead.id} lead={lead} onClick={() => setDetailLead(lead)} />)}
                                    {columnLeads.length === 0 && <div className="border border-dashed border-[#222] rounded-xl p-6 text-center text-white/20 text-xs">Sin leads</div>}
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
                                        {['Nombre', 'Email', 'Teléfono', 'Origen', 'Estado', 'Fecha', 'Notas'].map(h => (
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
                                                <td className="px-4 py-3 text-white/30 text-xs">{new Date(lead.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</td>
                                                <td className="px-4 py-3 text-white/30 text-xs truncate max-w-[150px]">{lead.notes || '-'}</td>
                                            </tr>
                                        );
                                    })}
                                    {filtered.length === 0 && <tr><td colSpan={7} className="text-center text-white/30 py-8">Sin leads</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
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

                            {/* Notes */}
                            <div>
                                <Label className="text-white/40 text-xs">Notas</Label>
                                <Textarea defaultValue={detailLead.notes || ''} onBlur={e => handleUpdateNotes(detailLead.id, e.target.value)} className="bg-[#0A0A0A] border-[#333] text-white mt-1" rows={3} data-testid="lead-notes" placeholder="Escribe notas sobre este prospecto..." />
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

            {/* ========== CONVERT MODAL ========== */}
            <Dialog open={!!convertLead} onOpenChange={o => !o && setConvertLead(null)}>
                {convertLead && (
                    <DialogContent className="bg-[#111] border-[#333]" data-testid="convert-modal">
                        <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">Convertir a cliente</DialogTitle></DialogHeader>
                        <div className="space-y-3">
                            <p className="text-white/60 text-sm">Se creará una cuenta para <span className="text-white font-semibold">{convertLead.name}</span> ({convertLead.email})</p>
                            <div><Label className="text-white/60 text-xs">Plan</Label>
                                <div className="flex gap-2 mt-1">{['gold', 'silver', 'bronze', 'elm'].map(p => (
                                    <button key={p} onClick={() => setConvertPlan(p)} className={`px-4 py-2 rounded-lg text-xs font-bold uppercase transition-all ${convertPlan === p ? 'bg-[#FF671F] text-white' : 'bg-[#1A1A1A] text-white/40 border border-[#333]'}`} data-testid={`plan-${p}`}>{p}</button>
                                ))}</div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConvertLead(null)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                            <Button onClick={handleConvert} className="bg-green-600 hover:bg-green-700 text-white" data-testid="confirm-convert"><UserPlus className="w-4 h-4 mr-1" />Convertir</Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </div>
    );
};

// ========== KANBAN CARD ==========
const KanbanCard = ({ lead, onClick }) => {
    const src = getSourceObj(lead.source);
    const SrcIcon = src.icon;
    return (
        <Card className="bg-[#111] border-[#222] cursor-pointer hover:border-[#FF671F]/40 transition-all" onClick={onClick} data-testid={`kanban-card-${lead.id}`}>
            <CardContent className="p-3">
                <p className="text-white text-sm font-medium truncate">{lead.name}</p>
                <div className="flex items-center gap-3 mt-1.5 text-white/40 text-xs">
                    {lead.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{lead.phone}</span>}
                    <span className="flex items-center gap-1 ml-auto"><SrcIcon className="w-3 h-3" />{src.label}</span>
                </div>
                <p className="text-white/20 text-[10px] mt-1.5">{new Date(lead.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</p>
            </CardContent>
        </Card>
    );
};

export default LeadsPage;
