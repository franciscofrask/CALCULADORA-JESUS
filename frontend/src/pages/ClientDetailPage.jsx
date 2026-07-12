import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { PlanBadge } from './ClientDashboard';
import CoachCheckins from '../components/CoachCheckins';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import {
    ArrowLeft, User, Mail, Phone, Calendar, CreditCard, Dumbbell, Apple,
    FileText, Scale, Target, Zap, Save, Loader2, History, Shield,
    ClipboardList, TrendingUp, Utensils, Activity, ChevronDown, ChevronUp,
    AlertCircle, Calculator, CheckCircle2, Pill, Plus, X, Sparkles, Pencil, Trash2, RotateCcw
} from 'lucide-react';

const USER_ROLES = [
    { value: 'client', label: 'Cliente' },
    { value: 'trainer', label: 'Entrenador' },
    { value: 'admin', label: 'Admin' },
];

const ClientDetailPage = () => {
    const { clientId } = useParams();
    const navigate = useNavigate();
    const { api, user: adminUser, planCatalog } = useAuth();
    // Planes asignables del catálogo (excluye complementos), para el selector de plan.
    const assignablePlans = Object.values(planCatalog || {}).filter(p => p.asignable);
    const [client, setClient] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('resumen');

    // Macros modal
    const [macrosModalOpen, setMacrosModalOpen] = useState(false);
    const [macrosForm, setMacrosForm] = useState({
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        peri: { protein: '', carbs: '' },
        note: '',
        effective_date: new Date().toISOString().slice(0, 10),
    });
    const [savingMacros, setSavingMacros] = useState(false);

    // Routine
    const [generatingRoutine, setGeneratingRoutine] = useState(false);
    const [routineInstructions, setRoutineInstructions] = useState('');
    const [generatedRoutine, setGeneratedRoutine] = useState(null);

    // Calculator tab
    const [calcForm, setCalcForm] = useState({ peso: '', porcentaje_graso: '', sexo: 'hombre', objetivo: 'volumen' });
    const [calcResults, setCalcResults] = useState(null);
    const [calcLoading, setCalcLoading] = useState(false);
    const [calcApplying, setCalcApplying] = useState(false);
    const [calcApplied, setCalcApplied] = useState(false);
    const [calcNote, setCalcNote] = useState('');

    // Suplementos
    const [supProtocol, setSupProtocol] = useState({ actual: [], siguiente: [], siguiente_fecha: '', nota: '' });
    const [supCatalog, setSupCatalog] = useState([]);
    const [supSaving, setSupSaving] = useState(false);
    const [supSuggesting, setSupSuggesting] = useState(false);

    // Visor de dietas (pestaña Nutrición)
    const [selectedDietDate, setSelectedDietDate] = useState(null);
    const [selectedDiet, setSelectedDiet] = useState(null);
    const [dietLoading, setDietLoading] = useState(false);
    const openDiet = async (fecha) => {
        setSelectedDietDate(fecha); setSelectedDiet(null); setDietLoading(true);
        try {
            const r = await api.get(`/admin/clients/${clientId}/diet`, { params: { fecha } });
            setSelectedDiet(r.data);
        } catch {
            toast.error('No se pudo cargar la dieta de esa fecha');
        } finally {
            setDietLoading(false);
        }
    };

    // Asignación de coach
    const [trainers, setTrainers] = useState([]);
    const [assigningTrainer, setAssigningTrainer] = useState(false);
    const changeTrainer = async (value) => {
        setAssigningTrainer(true);
        try {
            const trainerId = value === 'none' ? null : value;
            await api.put(`/admin/clients/${clientId}/trainer`, { trainer_id: trainerId });
            toast.success(trainerId ? 'Coach asignado' : 'Coach quitado');
            fetchClient();
        } catch (e) {
            toast.error(e.response?.data?.detail || 'No se pudo cambiar el coach');
        } finally { setAssigningTrainer(false); }
    };

    useEffect(() => { fetchClient(); }, [clientId]); // eslint-disable-line
    useEffect(() => { api.get('/admin/supplements/catalog').then(r => setSupCatalog(r.data || [])).catch(() => {}); }, []); // eslint-disable-line
    useEffect(() => { api.get('/admin/trainers').then(r => setTrainers(r.data || [])).catch(() => {}); }, []); // eslint-disable-line

    const fetchClient = async () => {
        try {
            const response = await api.get(`/admin/clients/${clientId}`);
            setClient(response.data);
            const sp = response.data.supplement_protocol;
            if (sp) setSupProtocol({ actual: sp.actual || [], siguiente: sp.siguiente || [], siguiente_fecha: sp.siguiente_fecha || '', nota: sp.nota || '' });
            const p = response.data.profile;
            if (p?.macros_training) {
                setMacrosForm({
                    training: { protein: p.macros_training.protein || p.macros_training.proteinas || '', carbs: p.macros_training.carbs || p.macros_training.hidratos || '', fat: p.macros_training.fat || p.macros_training.grasas || '' },
                    rest: { protein: p.macros_rest?.protein || p.macros_rest?.proteinas || '', carbs: p.macros_rest?.carbs || p.macros_rest?.hidratos || '', fat: p.macros_rest?.fat || p.macros_rest?.grasas || '' },
                    peri: { protein: p.macros_periworkout?.protein ?? p.macros_periworkout?.proteinas ?? '', carbs: p.macros_periworkout?.carbs ?? p.macros_periworkout?.hidratos ?? '' },
                    note: '',
                    effective_date: new Date().toISOString().slice(0, 10),
                });
            }
        } catch (error) {
            toast.error('Error al cargar datos del cliente');
            navigate('/admin/clients');
        } finally { setLoading(false); }
    };

    // Editar/eliminar/repetir entradas del historial de macros
    const [editingEntryId, setEditingEntryId] = useState(null);
    const _g = (m, a, b) => { const v = m?.[a] ?? m?.[b]; return v == null ? '' : v; };
    const macroFormFromEntry = (h, opts = {}) => ({
        training: { protein: _g(h.training, 'protein', 'proteinas'), carbs: _g(h.training, 'carbs', 'hidratos'), fat: _g(h.training, 'fat', 'grasas') },
        rest: { protein: _g(h.rest, 'protein', 'proteinas'), carbs: _g(h.rest, 'carbs', 'hidratos'), fat: _g(h.rest, 'fat', 'grasas') },
        peri: { protein: _g(h.peri, 'protein', 'proteinas'), carbs: _g(h.peri, 'carbs', 'hidratos') },
        effective_date: opts.today ? new Date().toISOString().slice(0, 10) : (h.effective_date || new Date().toISOString().slice(0, 10)),
        note: opts.note != null ? opts.note : (h.note || ''),
    });
    const openNewMacros = () => { setEditingEntryId(null); setMacrosModalOpen(true); };
    const openEditEntry = (h) => { setEditingEntryId(h.id); setMacrosForm(macroFormFromEntry(h)); setMacrosModalOpen(true); };
    const openRepeatEntry = (h) => {
        const d = h.effective_date ? new Date(h.effective_date + 'T12:00:00') : new Date(h.created_at);
        setEditingEntryId(null);
        setMacrosForm(macroFormFromEntry(h, { today: true, note: `Repetición de los macros del ${d.toLocaleDateString('es-ES')}` }));
        setMacrosModalOpen(true);
    };
    const deleteMacroEntry = async (h) => {
        if (!window.confirm('¿Eliminar esta entrada del historial de macros? No cambia los macros actuales del cliente.')) return;
        try { await api.delete(`/admin/clients/${clientId}/macro-history/${h.id}`); toast.success('Entrada eliminada'); fetchClient(); }
        catch { toast.error('No se pudo eliminar la entrada'); }
    };

    // Gestión de usuario (rol, plan cortesía, baja lógica) desde la ficha del cliente
    const [savingMgmt, setSavingMgmt] = useState(false);
    const changeUserRole = async (role) => {
        const uid = client?.user?.id; if (!uid) return;
        setSavingMgmt(true);
        try { await api.put(`/admin/users/${uid}`, { role }); toast.success('Rol actualizado'); fetchClient(); }
        catch (e) { toast.error(e?.response?.data?.detail || 'Error al cambiar el rol'); }
        finally { setSavingMgmt(false); }
    };
    const setUserPlan = async (plan, comp) => {
        const uid = client?.user?.id; if (!uid) return;
        try { await api.put(`/admin/users/${uid}`, { plan: plan || null, comp_plan: comp }); toast.success('Plan actualizado'); fetchClient(); }
        catch { toast.error('Error al actualizar el plan'); }
    };
    const toggleUserBaja = async () => {
        const uid = client?.user?.id; if (!uid) return;
        if (client.user.deleted_at) {
            try { await api.post(`/admin/users/${uid}/restore`); toast.success('Usuario reactivado'); fetchClient(); }
            catch { toast.error('No se pudo reactivar'); }
            return;
        }
        if (!window.confirm('¿Dar de baja a este usuario? No podrá entrar, pero los datos se conservan y se puede reactivar.')) return;
        try { await api.delete(`/admin/users/${uid}`); toast.success('Usuario dado de baja'); fetchClient(); }
        catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo dar de baja'); }
    };

    const handleSaveMacros = async () => {
        if (!editingEntryId && !macrosForm.note.trim()) { toast.error('El motivo es obligatorio'); return; }
        setSavingMacros(true);
        try {
            const body = {
                training: { protein: parseFloat(macrosForm.training.protein), carbs: parseFloat(macrosForm.training.carbs), fat: parseFloat(macrosForm.training.fat) },
                rest: { protein: parseFloat(macrosForm.rest.protein), carbs: parseFloat(macrosForm.rest.carbs), fat: parseFloat(macrosForm.rest.fat) },
                peri: { protein: parseFloat(macrosForm.peri.protein) || 0, carbs: parseFloat(macrosForm.peri.carbs) || 0 },
                note: macrosForm.note,
                effective_date: macrosForm.effective_date,
            };
            if (editingEntryId) {
                await api.put(`/admin/clients/${clientId}/macro-history/${editingEntryId}`, body);
                toast.success('Entrada del historial actualizada');
            } else {
                await api.put(`/admin/clients/${clientId}/macros`, body);
                toast.success('Macros actualizados');
            }
            setMacrosModalOpen(false);
            setEditingEntryId(null);
            setMacrosForm(prev => ({ ...prev, note: '' }));
            fetchClient();
        } catch (error) { toast.error('Error al guardar'); }
        finally { setSavingMacros(false); }
    };

    // Calma quiereRepartoDeComidas: coach toggles single-meal mode for this client.
    const handleToggleSingleMeal = async (val) => {
        try {
            await api.put(`/admin/clients/${clientId}`, { single_meal_mode: val });
            toast.success(val ? 'Dieta de comida única activada' : 'Reparto por comidas activado');
            fetchClient();
        } catch (error) { toast.error('Error actualizando estructura de dieta'); }
    };

    const handleGenerateRoutine = async () => {
        setGeneratingRoutine(true);
        try {
            const response = await api.post('/admin/routines/generate', { client_id: clientId, instructions: routineInstructions });
            setGeneratedRoutine(response.data.routine);
            toast.success('Rutina generada con IA');
        } catch (error) { toast.error('Error al generar rutina'); }
        finally { setGeneratingRoutine(false); }
    };

    const handleSaveRoutine = async () => {
        if (!generatedRoutine) return;
        try {
            await api.post(`/admin/routines/save?client_id=${clientId}`, generatedRoutine);
            toast.success('Rutina guardada');
            setGeneratedRoutine(null);
            fetchClient();
        } catch (error) { toast.error('Error al guardar rutina'); }
    };

    // ── Suplementos ──
    const catalogToItem = (c) => ({ catalog_id: c.id, titulo: c.titulo, imagen: c.imagen, enlaces: c.enlaces || [], cuando: c.cuando || '', cuanto: c.cuanto || '', observaciones: c.observaciones || '' });
    const supAdd = (bloque, catId) => {
        const c = supCatalog.find(x => x.id === catId);
        if (!c) return;
        setSupProtocol(prev => ({ ...prev, [bloque]: [...prev[bloque], catalogToItem(c)] }));
    };
    const supRemove = (bloque, idx) => setSupProtocol(prev => ({ ...prev, [bloque]: prev[bloque].filter((_, i) => i !== idx) }));
    const supSuggest = async () => {
        setSupSuggesting(true);
        try {
            const r = await api.post(`/admin/supplements/suggest?client_id=${clientId}`);
            setSupProtocol(prev => ({ ...prev, actual: r.data.actual || [] }));
            toast.success('Protocolo sugerido (revísalo y guarda)');
        } catch (e) { toast.error('Error al sugerir'); }
        finally { setSupSuggesting(false); }
    };
    const supSave = async () => {
        setSupSaving(true);
        try {
            await api.post(`/admin/supplements/save?client_id=${clientId}`, {
                actual: supProtocol.actual, siguiente: supProtocol.siguiente,
                siguiente_fecha: supProtocol.siguiente_fecha || null, nota: supProtocol.nota || null,
            });
            toast.success('Suplementación guardada');
            fetchClient();
        } catch (e) { toast.error('Error al guardar suplementación'); }
        finally { setSupSaving(false); }
    };

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-48 bg-[#111] rounded-xl" /></div></div>;
    if (!client) return <div className="p-6 bg-[#0A0A0A] min-h-screen text-center text-white/50">Cliente no encontrado</div>;

    const { profile, user, routines, reports, payments, macro_history, nutrition_stats } = client;
    const mt = profile?.macros_training;
    const mr = profile?.macros_rest;
    const mp = profile?.macros_periworkout;
    const getV = (m, k1, k2) => Math.round(m?.[k1] || m?.[k2] || 0);
    const activeRoutine = routines?.find(r => r.status === 'active');

    const TAB_CONFIG = [
        { id: 'resumen', label: 'Resumen', icon: User },
        { id: 'macros', label: 'Macros', icon: Apple },
        { id: 'calculadora', label: 'Calculadora', icon: Calculator },
        { id: 'membresia', label: 'Membresía', icon: CreditCard },
        { id: 'cuestionario', label: 'Cuestionario', icon: ClipboardList },
        { id: 'entrenamiento', label: 'Entreno', icon: Dumbbell },
        { id: 'nutricion', label: 'Nutrición', icon: Utensils },
        { id: 'suplementos', label: 'Suplementos', icon: Pill },
        { id: 'seguimiento', label: 'Seguimiento', icon: TrendingUp },
    ];

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="client-detail">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" onClick={() => navigate('/admin/clients')} className="text-white/50 hover:text-white"><ArrowLeft className="w-5 h-5" /></Button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h1 className="text-2xl font-bold text-white truncate" style={{ fontFamily: 'Barlow Condensed' }}>{user?.name?.toUpperCase()}</h1>
                        <PlanBadge plan={profile?.plan} />
                        <Badge className={profile?.status === 'activo' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-red-500/20 text-red-400 border-0'}>{profile?.status}</Badge>
                    </div>
                    <p className="text-white/40 text-sm truncate">{user?.email}</p>
                </div>
            </div>

            {/* 8 Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="overflow-x-auto -mx-4 px-4">
                    <TabsList className="inline-flex w-auto min-w-full bg-[#111] p-1 rounded-xl gap-0.5">
                        {TAB_CONFIG.map(t => (
                            <TabsTrigger key={t.id} value={t.id} className="text-xs px-3 py-2 data-[state=active]:bg-[#FF671F] data-[state=active]:text-white text-white/50 rounded-lg whitespace-nowrap" data-testid={`tab-${t.id}`}>
                                <t.icon className="w-3.5 h-3.5 mr-1.5" />{t.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </div>

                {/* ========== TAB 1: RESUMEN ========== */}
                <TabsContent value="resumen">
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                            <InfoItem icon={User} label="Nombre" value={user?.name} />
                            <InfoItem icon={Mail} label="Email" value={user?.email} />
                            <InfoItem icon={Phone} label="Teléfono" value={user?.phone || '-'} />
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} planName={planCatalog?.[profile?.plan]?.name} />} />
                            <InfoItem icon={Activity} label="Estado" value={profile?.status} />
                            <InfoItem icon={Calendar} label="Semana" value={(() => {
                                const sem = planCatalog?.[profile?.plan]?.ciclo?.semanas;
                                return sem ? `${profile?.week || 1}/${sem}` : `${profile?.week || 1}`;
                            })()} />
                            <InfoItem icon={Dumbbell} label="Entrenador" value={(() => {
                                const trainerId = profile?.trainer_id || null;
                                const trainerName = trainers.find(t => t.id === trainerId)?.name || trainerId;
                                const isCoach = adminUser?.role === 'trainer';
                                // Coach viendo un cliente de otro coach: solo lectura
                                if (isCoach && trainerId && trainerId !== adminUser?.id) return trainerName;
                                // Coach y cliente sin coach: solo puede asignarse a si mismo
                                if (isCoach && !trainerId) return (
                                    <Button size="sm" disabled={assigningTrainer} onClick={() => changeTrainer(adminUser.id)}
                                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-7 px-2" data-testid="assign-me-trainer">
                                        Asignarme
                                    </Button>
                                );
                                // Admin, o el coach actual: puede asignar, traspasar o quitar
                                return (
                                    <select value={trainerId || 'none'} disabled={assigningTrainer} onChange={e => changeTrainer(e.target.value)}
                                        className="bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-1" data-testid="trainer-select">
                                        <option value="none">Sin asignar</option>
                                        {trainerId && !trainers.some(t => t.id === trainerId) && <option value={trainerId}>{trainerName}</option>}
                                        {trainers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                    </select>
                                );
                            })()} />
                            <InfoItem icon={Target} label="Rutina" value={activeRoutine ? `${activeRoutine.days?.filter(d => !d.is_rest).length || 0} días` : 'Sin rutina'} />
                            <InfoItem icon={CreditCard} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            <InfoItem icon={Scale} label="Peso" value={profile?.weight ? `${profile.weight} kg` : '-'} />
                            <InfoItem icon={Target} label="Objetivo" value={profile?.goal || '-'} />
                        </div>
                    </CardContent></Card>
                </TabsContent>

                {/* ========== TAB 2: MACROS ========== */}
                <TabsContent value="macros" className="space-y-4">
                    {mt ? (
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                            <div className="flex items-center justify-between mb-4">
                                <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Macros actuales</p>
                                <div className="flex items-center gap-2">
                                    <Badge className={`border-0 text-[10px] ${profile?.macros_source === 'auto' ? 'bg-green-500/20 text-green-500' : 'bg-yellow-500/20 text-yellow-400'}`}>{profile?.macros_source || 'manual'}</Badge>
                                    <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs" onClick={openNewMacros} data-testid="change-macros-btn">Cambiar macros</Button>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                <MacroGroup title="Entrenamiento" icon={Zap} color="#FF671F" items={[
                                    { label: 'Proteína', value: getV(mt, 'protein', 'proteinas') },
                                    { label: 'Hidratos', value: getV(mt, 'carbs', 'hidratos') },
                                    { label: 'Grasa', value: getV(mt, 'fat', 'grasas') },
                                ]} />
                                <MacroGroup title="Perientreno" icon={Activity} color="#EAB308" items={[
                                    { label: 'Proteína', value: getV(mp, 'protein', 'proteinas') },
                                    { label: 'Hidratos', value: getV(mp, 'carbs', 'hidratos') },
                                ]} />
                                <MacroGroup title="Descanso" icon={Scale} color="#22C55E" items={[
                                    { label: 'Proteína', value: getV(mr, 'protein', 'proteinas') },
                                    { label: 'Hidratos', value: getV(mr, 'carbs', 'hidratos') },
                                    { label: 'Grasa', value: getV(mr, 'fat', 'grasas') },
                                ]} />
                            </div>
                        </CardContent></Card>
                    ) : <EmptyState icon={Apple} message="Sin macros asignados. Usa 'Cambiar macros' para asignar." action={<Button size="sm" className="bg-[#FF671F] text-white mt-2" onClick={openNewMacros}>Asignar macros</Button>} />}

                    {/* Estructura de dieta (Calma quiereRepartoDeComidas) */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-3">Estructura de dieta</p>
                        <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-sm text-white font-medium">{profile?.single_meal_mode ? 'Comida única' : 'Reparto por comidas'}</p>
                                <p className="text-xs text-white/40">{profile?.single_meal_mode ? 'Todo el presupuesto del día en una sola comida, sin reparto.' : 'Reparto estándar en 4 comidas + peri.'}</p>
                            </div>
                            <button
                                onClick={() => handleToggleSingleMeal(!profile?.single_meal_mode)}
                                className={`shrink-0 px-4 py-2 rounded-lg text-xs font-bold transition-all ${profile?.single_meal_mode ? 'bg-[#FF671F] text-white' : 'bg-[#1a1a1a] text-white/60 border border-[#222] hover:text-white'}`}
                            >{profile?.single_meal_mode ? 'Comida única: ON' : 'Activar comida única'}</button>
                        </div>
                    </CardContent></Card>

                    {/* Macro History */}
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><History className="w-4 h-4" />Historial de cambios</CardTitle></CardHeader>
                        <CardContent>{macro_history?.length > 0 ? (
                            <div className="space-y-2">{macro_history.map((h, i) => <MacroHistoryItem key={h.id || i} item={h} onEdit={openEditEntry} onRepeat={openRepeatEntry} onDelete={deleteMacroEntry} />)}</div>
                        ) : <p className="text-white/30 text-sm text-center py-4">Sin cambios registrados</p>}</CardContent>
                    </Card>

                    {/* Macros Modal */}
                    <Dialog open={macrosModalOpen} onOpenChange={(o) => { setMacrosModalOpen(o); if (!o) setEditingEntryId(null); }}>
                        <DialogContent className="bg-[#111] border-[#333] max-w-lg" data-testid="macros-modal">
                            <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">{editingEntryId ? 'Editar entrada del historial' : 'Cambiar macros'}</DialogTitle></DialogHeader>
                            <div className="space-y-4">
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Entrenamiento</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={macrosForm.training.protein} onChange={e => setMacrosForm({...macrosForm, training: {...macrosForm.training, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" data-testid="macro-input-tp" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={macrosForm.training.carbs} onChange={e => setMacrosForm({...macrosForm, training: {...macrosForm.training, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Grasa</Label><Input type="number" value={macrosForm.training.fat} onChange={e => setMacrosForm({...macrosForm, training: {...macrosForm.training, fat: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Descanso</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={macrosForm.rest.protein} onChange={e => setMacrosForm({...macrosForm, rest: {...macrosForm.rest, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={macrosForm.rest.carbs} onChange={e => setMacrosForm({...macrosForm, rest: {...macrosForm.rest, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Grasa</Label><Input type="number" value={macrosForm.rest.fat} onChange={e => setMacrosForm({...macrosForm, rest: {...macrosForm.rest, fat: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Perientreno</p>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={macrosForm.peri.protein} onChange={e => setMacrosForm({...macrosForm, peri: {...macrosForm.peri, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={macrosForm.peri.carbs} onChange={e => setMacrosForm({...macrosForm, peri: {...macrosForm.peri, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Vigente desde</Label>
                                    <Input type="date" value={macrosForm.effective_date} onChange={e => setMacrosForm({...macrosForm, effective_date: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-effective-date" />
                                    <p className="text-[10px] text-white/30 mt-1">Las dietas anteriores a esta fecha conservan los macros previos.</p>
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Motivo del cambio {editingEntryId ? '(opcional)' : '(obligatorio)'}</Label>
                                    <Textarea value={macrosForm.note} onChange={e => setMacrosForm({...macrosForm, note: e.target.value})} placeholder="Ej: Ajuste semanal por pérdida de peso..." className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-note" />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setMacrosModalOpen(false)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                                <Button onClick={handleSaveMacros} disabled={savingMacros} className="bg-[#FF671F] text-white" data-testid="save-macros-btn">{savingMacros ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar</>}</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </TabsContent>

                {/* ========== TAB 3: MEMBRESÍA ========== */}
                <TabsContent value="membresia" className="space-y-4">
                    {/* Gestión de usuario: rol, plan (cortesía) y baja lógica */}
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><Shield className="w-4 h-4" />Gestión de usuario</CardTitle></CardHeader>
                        <CardContent className="space-y-3">
                            {user?.deleted_at && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2">Usuario dado de baja: no puede entrar en la app.</div>}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Rol</Label>
                                    <select value={user?.role || 'client'} onChange={e => changeUserRole(e.target.value)} disabled={savingMgmt} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {USER_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                                    </select>
                                </div>
                                <div><Label className="text-white/60 text-xs">Plan</Label>
                                    <select value={profile?.plan || ''} onChange={e => setUserPlan(e.target.value, !!profile?.comp_plan)} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        <option value="">Sin plan</option>
                                        {['activo', 'legacy', 'especial'].map(estado => {
                                            const grupo = assignablePlans.filter(p => p.estado === estado);
                                            if (!grupo.length) return null;
                                            const gl = { activo: 'Activos', legacy: 'Legacy', especial: 'Especiales' }[estado];
                                            return (
                                                <optgroup key={estado} label={gl}>
                                                    {grupo.map(p => <option key={p.code} value={p.code}>{p.name}</option>)}
                                                </optgroup>
                                            );
                                        })}
                                    </select>
                                </div>
                            </div>
                            <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer select-none">
                                <input type="checkbox" checked={!!profile?.comp_plan} onChange={e => setUserPlan(profile?.plan || '', e.target.checked)} className="accent-[#FF671F] w-4 h-4" />
                                Plan de cortesía (sin pago)
                            </label>
                            <div className="pt-1">
                                {user?.deleted_at
                                    ? <Button onClick={toggleUserBaja} className="bg-green-600 hover:bg-green-700 text-white text-sm"><RotateCcw className="w-4 h-4 mr-1" /> Reactivar usuario</Button>
                                    : <Button onClick={toggleUserBaja} variant="outline" className="bg-transparent border-red-500/40 text-red-400 hover:bg-red-500/10 text-sm"><Trash2 className="w-4 h-4 mr-1" /> Dar de baja (lógica)</Button>}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} />} />
                            <InfoItem icon={CreditCard} label="Precio" value={`${profile?.price || 0}€/ciclo`} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            <InfoItem icon={Calendar} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES') : '-'} />
                        </div>
                    </CardContent></Card>
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Historial de pagos</CardTitle></CardHeader>
                        <CardContent>{payments?.length > 0 ? (
                            <div className="space-y-2">{payments.map(p => (
                                <div key={p.id} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                    <div><p className="text-white text-sm font-medium">{p.amount}€</p><p className="text-white/40 text-xs">{new Date(p.created_at).toLocaleDateString('es-ES')}</p></div>
                                    <Badge className={p.status === 'success' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-red-500/20 text-red-400 border-0'}>{p.status === 'success' ? 'Exitoso' : 'Fallido'}</Badge>
                                </div>
                            ))}</div>
                        ) : <p className="text-white/30 text-sm text-center py-4">Sin pagos registrados</p>}</CardContent>
                    </Card>
                </TabsContent>

                {/* ========== TAB 4: REPORTES ========== */}

                {/* ========== TAB 5: CUESTIONARIO ========== */}
                <TabsContent value="cuestionario">
                    {(profile?.goal || profile?.weight || profile?.equipment?.length) ? (
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                <InfoItem icon={Target} label="Objetivo" value={profile?.goal || '-'} />
                                <InfoItem icon={Scale} label="Peso inicial" value={profile?.weight ? `${profile.weight} kg` : '-'} />
                                <InfoItem icon={User} label="Sexo" value={profile?.sex || '-'} />
                                <InfoItem icon={Activity} label="% Graso" value={profile?.body_fat ? `${profile.body_fat}%` : '-'} />
                                <InfoItem icon={Calendar} label="Edad" value={profile?.age || '-'} />
                                <InfoItem icon={Scale} label="Altura" value={profile?.height ? `${profile.height} cm` : '-'} />
                            </div>
                            {Array.isArray(profile?.equipment) && profile.equipment.length > 0 && (
                                <div className="mt-4"><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Equipamiento</p>
                                    <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{e}</Badge>)}</div>
                                </div>
                            )}
                            {Array.isArray(profile?.injuries) && profile.injuries.length > 0 && (
                                <div className="mt-4"><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones</p>
                                    <div className="flex flex-wrap gap-1.5">{profile.injuries.map((l, i) => <Badge key={i} className="bg-red-500/10 text-red-400 border-0 text-xs">{l}</Badge>)}</div>
                                </div>
                            )}
                        </CardContent></Card>
                    ) : <EmptyState icon={ClipboardList} message="Cuestionario pendiente." />}
                </TabsContent>

                {/* ========== TAB 6: ENTRENAMIENTO ========== */}
                <TabsContent value="entrenamiento" className="space-y-4">
                    {/* Equipment & injuries */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Equipamiento</p>
                                {Array.isArray(profile?.equipment) && profile.equipment.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{e}</Badge>)}</div> : <p className="text-white/30 text-sm">No especificado</p>}
                            </div>
                            <div><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones activas</p>
                                {Array.isArray(profile?.injuries) && profile.injuries.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.injuries.map((l, i) => <Badge key={i} className="bg-red-500/10 text-red-400 border-0 text-xs">{l}</Badge>)}</div> : <p className="text-white/30 text-sm">Sin lesiones</p>}
                            </div>
                        </div>
                    </CardContent></Card>

                    {/* Current routine */}
                    {activeRoutine ? (
                        <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Rutina actual</CardTitle></CardHeader>
                            <CardContent><div className="space-y-2">{activeRoutine.days?.map((d, i) => (
                                <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                    <span className="text-white text-sm font-medium capitalize">{d.day}</span>
                                    {d.is_rest ? <Badge className="bg-purple-500/10 text-purple-400 border-0 text-xs">Descanso</Badge> : <span className="text-white/40 text-xs">{d.exercises?.length || 0} ejercicios</span>}
                                </div>
                            ))}</div>
                            {activeRoutine.trainer_notes && <p className="text-white/30 text-xs mt-3 italic">{activeRoutine.trainer_notes}</p>}
                            </CardContent>
                        </Card>
                    ) : <EmptyState icon={Dumbbell} message="Sin rutina asignada." />}

                    {/* Generate routine */}
                    <Card className="bg-[#111] border-[#FF671F]/20"><CardHeader className="pb-2"><CardTitle className="text-sm text-white uppercase tracking-wider flex items-center gap-2"><Zap className="w-4 h-4 text-[#FF671F]" />Generar rutina con IA</CardTitle></CardHeader>
                        <CardContent className="space-y-3">
                            <Textarea value={routineInstructions} onChange={e => setRoutineInstructions(e.target.value)} placeholder="Instrucciones para la IA..." className="bg-[#0A0A0A] border-[#333] text-white" rows={2} data-testid="routine-instructions" />
                            <Button onClick={handleGenerateRoutine} disabled={generatingRoutine} className="bg-[#FF671F] text-white" data-testid="generate-routine-btn">
                                {generatingRoutine ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Generando...</> : <><Zap className="w-4 h-4 mr-1" />Generar</>}
                            </Button>
                            {generatedRoutine && (
                                <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#333] mt-3">
                                    <ScrollArea className="h-48">{generatedRoutine.days?.map((d, i) => <div key={i} className="mb-2"><p className="text-white text-xs font-bold capitalize">{d.day}</p>{d.is_rest ? <p className="text-white/30 text-xs">Descanso</p> : <ul className="text-white/50 text-xs">{d.exercises?.map((ex, j) => <li key={j}>• {ex.name}: {ex.sets}x{ex.reps}</li>)}</ul>}</div>)}</ScrollArea>
                                    <div className="flex gap-2 mt-3"><Button size="sm" onClick={handleSaveRoutine} className="bg-[#FF671F] text-white" data-testid="save-routine-btn"><Save className="w-3 h-3 mr-1" />Guardar</Button><Button size="sm" variant="outline" onClick={() => setGeneratedRoutine(null)} className="bg-transparent border-[#333] text-white">Descartar</Button></div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ========== TAB: SUPLEMENTOS ========== */}
                <TabsContent value="suplementos" className="space-y-4">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                        <p className="text-xs text-white/40 uppercase tracking-wider">Protocolo de suplementación</p>
                        <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={supSuggest} disabled={supSuggesting} className="bg-transparent border-[#333] text-white" data-testid="suggest-supplements-btn">
                                {supSuggesting ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1 text-[#FF671F]" />}Auto-sugerir
                            </Button>
                            <Button size="sm" onClick={supSave} disabled={supSaving} className="bg-[#FF671F] text-white" data-testid="save-supplements-btn">
                                {supSaving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}Guardar
                            </Button>
                        </div>
                    </div>

                    {[['actual', 'Suplementación actual'], ['siguiente', 'Suplementación siguiente']].map(([bloque, titulo]) => (
                        <Card key={bloque} className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">{titulo}</CardTitle></CardHeader>
                            <CardContent className="space-y-2">
                                {supProtocol[bloque].length === 0 && <p className="text-white/30 text-sm">Sin suplementos.</p>}
                                {supProtocol[bloque].map((it, i) => (
                                    <div key={i} className="flex items-start justify-between gap-2 p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                        <div className="min-w-0">
                                            <p className="text-white text-sm font-medium">{it.titulo}</p>
                                            <p className="text-white/40 text-xs">{[it.cuanto, it.cuando].filter(Boolean).join(' · ')}</p>
                                        </div>
                                        <button onClick={() => supRemove(bloque, i)} className="text-white/30 hover:text-red-400 flex-shrink-0"><X className="w-4 h-4" /></button>
                                    </div>
                                ))}
                                {bloque === 'siguiente' && (
                                    <div className="pt-1">
                                        <Label className="text-white/40 text-xs">A partir del día</Label>
                                        <Input type="date" value={supProtocol.siguiente_fecha || ''} onChange={e => setSupProtocol(p => ({ ...p, siguiente_fecha: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white mt-1 w-full sm:w-48" />
                                    </div>
                                )}
                                <select onChange={e => { if (e.target.value) { supAdd(bloque, e.target.value); e.target.value = ''; } }} defaultValue=""
                                    className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-3 py-2 mt-1">
                                    <option value="">+ Añadir del catálogo…</option>
                                    {supCatalog.map(c => <option key={c.id} value={c.id}>{c.titulo}{c.sexo !== 'ambos' ? ` (${c.sexo})` : ''} - {c.categoria}</option>)}
                                </select>
                            </CardContent>
                        </Card>
                    ))}

                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Nota personal</CardTitle></CardHeader>
                        <CardContent>
                            <Textarea value={supProtocol.nota || ''} onChange={e => setSupProtocol(p => ({ ...p, nota: e.target.value }))} placeholder="Nota para el cliente…" className="bg-[#0A0A0A] border-[#333] text-white" rows={2} />
                        </CardContent>
                    </Card>

                    <p className="text-white/30 text-xs">El catálogo se gestiona en <button onClick={() => navigate('/admin/supplements-catalog')} className="text-[#FF671F] hover:underline">Catálogo de suplementos</button>.</p>
                </TabsContent>

                {/* ========== TAB 7: NUTRICIÓN ========== */}
                <TabsContent value="nutricion" className="space-y-4">
                    {nutrition_stats?.total_diets > 0 ? (<>
                        <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Top 5 alimentos</CardTitle></CardHeader>
                            <CardContent><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">{nutrition_stats.top_foods?.map((f, i) => (
                                <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg">
                                    <span className="text-white text-sm truncate flex-1">{f.nombre}</span>
                                    <Badge className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs ml-2">{f.count}x</Badge>
                                </div>
                            ))}</div></CardContent>
                        </Card>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Card className="bg-[#111] border-[#222] md:col-span-1"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Dietas ({nutrition_stats.total_diets})</CardTitle></CardHeader>
                                <CardContent>
                                    <ScrollArea className="h-[28rem] pr-2">
                                        <div className="space-y-1">{nutrition_stats.diet_dates?.map((d, i) => (
                                            <button key={i} onClick={() => openDiet(d.fecha)}
                                                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left transition-colors ${selectedDietDate === d.fecha ? 'bg-[#FF671F]/15 border border-[#FF671F]/40' : 'bg-[#0A0A0A] border border-transparent hover:bg-[#1a1a1a]'}`}>
                                                <span className="text-white text-sm">{new Date(d.fecha + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                                                <Badge className={d.tipo_dia === 'entrenamiento' ? 'bg-[#FF671F]/10 text-[#FF671F] border-0 text-[10px]' : 'bg-green-500/10 text-green-500 border-0 text-[10px]'}>{d.tipo_dia}</Badge>
                                            </button>
                                        ))}</div>
                                    </ScrollArea>
                                </CardContent>
                            </Card>
                            <Card className="bg-[#111] border-[#222] md:col-span-2"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">{selectedDietDate ? `Dieta del ${new Date(selectedDietDate + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}` : 'Dieta'}</CardTitle></CardHeader>
                                <CardContent>
                                    {dietLoading ? <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-[#FF671F]" /></div>
                                        : selectedDiet ? <DietDetail diet={selectedDiet} />
                                            : <p className="text-white/30 text-sm text-center py-10">Elige una fecha de la lista para ver la dieta de ese día.</p>}
                                </CardContent>
                            </Card>
                        </div>
                    </>) : <EmptyState icon={Utensils} message="Sin datos de nutrición aún." />}
                </TabsContent>

                {/* ========== TAB CALCULADORA ========== */}
                <TabsContent value="calculadora" className="space-y-4">
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5 space-y-4">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Calcular macros - Método JG</p>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs text-white/40 uppercase mb-1">Peso (kg)</label>
                                <input type="number" min="30" max="200" step="0.5"
                                    value={calcForm.peso}
                                    onChange={e => { setCalcForm(f => ({...f, peso: e.target.value})); setCalcResults(null); setCalcApplied(false); }}
                                    placeholder="80"
                                    className="w-full bg-[#0A0A0A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F]"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-white/40 uppercase mb-1">% Graso</label>
                                <input type="number" min="5" max="60" step="0.5"
                                    value={calcForm.porcentaje_graso}
                                    onChange={e => { setCalcForm(f => ({...f, porcentaje_graso: e.target.value})); setCalcResults(null); setCalcApplied(false); }}
                                    placeholder="20"
                                    className="w-full bg-[#0A0A0A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F]"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            {[['hombre','Hombre'],['mujer','Mujer']].map(([v,l]) => (
                                <button key={v} onClick={() => { setCalcForm(f => ({...f, sexo: v})); setCalcResults(null); }}
                                    className={`py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider transition-all ${calcForm.sexo === v ? 'text-white' : 'bg-[#1A1A1A] text-white/40'}`}
                                    style={calcForm.sexo === v ? { backgroundColor: '#FF671F' } : {}}
                                >{l}</button>
                            ))}
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            {[['volumen','Volumen'],['definicion','Definición']].map(([v,l]) => (
                                <button key={v} onClick={() => { setCalcForm(f => ({...f, objetivo: v})); setCalcResults(null); }}
                                    className={`py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider transition-all ${calcForm.objetivo === v ? 'text-white' : 'bg-[#1A1A1A] text-white/40'}`}
                                    style={calcForm.objetivo === v ? { backgroundColor: '#FF671F' } : {}}
                                >{l}</button>
                            ))}
                        </div>
                        <Button onClick={async () => {
                            const peso = parseFloat(calcForm.peso);
                            const bf = parseFloat(calcForm.porcentaje_graso);
                            if (!peso || isNaN(bf)) { toast.error('Rellena peso y % graso'); return; }
                            setCalcLoading(true);
                            try {
                                const res = await api.post('/calculator/targets', { peso, porcentaje_graso: bf, sexo: calcForm.sexo, objetivo: calcForm.objetivo });
                                setCalcResults(res.data);
                                setCalcApplied(false);
                            } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
                            finally { setCalcLoading(false); }
                        }} disabled={calcLoading || !calcForm.peso || !calcForm.porcentaje_graso}
                            className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider disabled:opacity-40">
                            {calcLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Calculator className="w-4 h-4 mr-2" />}
                            {calcLoading ? 'Calculando...' : 'Calcular macros'}
                        </Button>

                        {calcResults && (<>
                            <div className="grid grid-cols-3 gap-2">
                                {[
                                    { label: 'Entreno', m: calcResults.macros.entreno, color: '#FF671F' },
                                    { label: 'Peri', m: { proteina: calcResults.macros.perientreno.proteina, hidratos: calcResults.macros.perientreno.hidratos, grasa: null }, color: '#EAB308' },
                                    { label: 'Descanso', m: calcResults.macros.descanso, color: '#22C55E' },
                                ].map(({ label, m, color }) => (
                                    <div key={label} className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
                                        <p className="text-[10px] font-bold uppercase mb-2" style={{ color }}>{label}</p>
                                        <p className="text-xs text-white/60">P <span className="text-white font-bold">{Math.round(m.proteina)}</span></p>
                                        <p className="text-xs text-white/60">H <span className="text-white font-bold">{Math.round(m.hidratos)}</span></p>
                                        {m.grasa !== null && <p className="text-xs text-white/60">G <span className="text-white font-bold">{Math.round(m.grasa)}</span></p>}
                                    </div>
                                ))}
                            </div>
                            <div>
                                <label className="block text-xs text-white/40 uppercase mb-1">Motivo (obligatorio)</label>
                                <input type="text" value={calcNote}
                                    onChange={e => setCalcNote(e.target.value)}
                                    placeholder="Ej: Inicio de programa, ajuste semana 3..."
                                    className="w-full bg-[#0A0A0A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F]"
                                />
                            </div>
                            <Button onClick={async () => {
                                if (!calcNote.trim()) { toast.error('El motivo es obligatorio'); return; }
                                setCalcApplying(true);
                                try {
                                    await api.post(`/admin/clients/${clientId}/calculator/apply`, {
                                        peso: parseFloat(calcForm.peso),
                                        porcentaje_graso: parseFloat(calcForm.porcentaje_graso),
                                        sexo: calcForm.sexo,
                                        objetivo: calcForm.objetivo,
                                        note: calcNote,
                                    });
                                    setCalcApplied(true);
                                    toast.success(`Macros aplicados a ${client?.user?.name}`);
                                    fetchClient();
                                } catch (err) { toast.error(err.response?.data?.detail || 'Error aplicando'); }
                                finally { setCalcApplying(false); }
                            }} disabled={calcApplying || calcApplied}
                                className={`w-full font-bold uppercase tracking-wider ${calcApplied ? 'bg-green-600 hover:bg-green-600' : 'bg-[#1A1A1A] border border-[#333] hover:border-[#FF671F]'} text-white disabled:opacity-60`}>
                                {calcApplying ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : calcApplied ? <CheckCircle2 className="w-4 h-4 mr-2" /> : null}
                                {calcApplying ? 'Aplicando...' : calcApplied ? 'Aplicado' : `Aplicar a ${client?.user?.name?.split(' ')[0] || 'cliente'}`}
                            </Button>
                        </>)}
                    </CardContent></Card>

                    {/* Historial */}
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                            <History className="w-4 h-4" />Historial de macros
                        </CardTitle>
                    </CardHeader>
                        <CardContent>{macro_history?.length > 0
                            ? <div className="space-y-2">{macro_history.map((h, i) => <MacroHistoryItem key={h.id || i} item={h} />)}</div>
                            : <p className="text-white/30 text-sm text-center py-4">Sin historial</p>}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ========== TAB: SEGUIMIENTO (evolución de peso + check-ins + reportes) ========== */}
                <TabsContent value="seguimiento" className="space-y-4">
                    <WeightEvolution reports={reports} />
                    <CoachCheckins clientId={clientId} />
                    <ReportsFeedbackList initialReports={reports} />
                </TabsContent>
            </Tabs>
        </div>
    );
};

// ========== SUB-COMPONENTS ==========

const InfoItem = ({ icon: Icon, label, value }) => (
    <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 text-[#FF671F] mt-0.5 flex-shrink-0" />
        <div><p className="text-[10px] text-white/40 uppercase tracking-wider">{label}</p><div className="text-white text-sm font-medium">{value}</div></div>
    </div>
);

const MacroGroup = ({ title, icon: Icon, color, items }) => (
    <div className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
        <div className="flex items-center gap-1.5 mb-3"><Icon className="w-3.5 h-3.5" style={{ color }} /><span className="text-xs font-bold uppercase tracking-wider" style={{ color }}>{title}</span></div>
        <div className="space-y-2">{items.map(it => (
            <div key={it.label} className="flex items-center justify-between">
                <span className="text-white/50 text-xs">{it.label}</span>
                <span className="text-white font-bold text-sm" style={{ fontFamily: 'Barlow Condensed' }}>{it.value}g</span>
            </div>
        ))}</div>
    </div>
);

const _mv = (m, keys) => { for (const k of keys) if (m && m[k] != null) return Math.round(m[k]); return 0; };
const _mkcal = (m) => Math.round(_mv(m, ['protein', 'proteinas']) * 4 + _mv(m, ['carbs', 'hidratos']) * 4 + _mv(m, ['fat', 'grasas']) * 9);

const MacroRow = ({ label, color, m, showG = true }) => {
    if (!m) return null;
    const P = _mv(m, ['protein', 'proteinas']), H = _mv(m, ['carbs', 'hidratos']), G = _mv(m, ['fat', 'grasas']);
    return (
        <div className="flex items-center gap-3 py-1">
            <span className="w-24 shrink-0 flex items-center gap-1.5 text-white/50 text-xs uppercase tracking-wide">
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />{label}
            </span>
            <span className="text-orange-400 font-bold text-sm tabular-nums">P {P}</span>
            <span className="text-blue-400 font-bold text-sm tabular-nums">H {H}</span>
            {showG && <span className="text-yellow-400 font-bold text-sm tabular-nums">G {G}</span>}
            <span className="text-white/30 text-xs ml-auto tabular-nums">{_mkcal(m)} kcal</span>
        </div>
    );
};

const MacroHistoryItem = ({ item, onEdit, onRepeat, onDelete }) => {
    const peso = item.peso ?? item.client_weight;
    const peri = item.peri || item.macros_periworkout;
    const hasPeri = peri && (peri.protein || peri.proteinas || peri.carbs || peri.hidratos);
    const fecha = item.effective_date ? item.effective_date + 'T12:00:00' : item.created_at;
    const hasActions = onEdit || onRepeat || onDelete;
    return (
        <div className="p-3.5 bg-[#0A0A0A] rounded-xl border border-[#222]">
            <div className="flex items-center justify-between mb-2.5">
                <span className="text-white text-sm font-semibold">{new Date(fecha).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
                <div className="flex items-center gap-2.5">
                    {peso != null && <span className="text-[#FF671F] font-bold text-base" style={{ fontFamily: 'Barlow Condensed' }}>{peso} kg</span>}
                    {hasActions && (
                        <div className="flex items-center gap-0.5">
                            {onRepeat && <button onClick={() => onRepeat(item)} title="Repetir estos macros (aplicar hoy)" className="p-1 rounded text-white/40 hover:text-[#FF671F] hover:bg-[#FF671F]/10"><RotateCcw className="w-3.5 h-3.5" /></button>}
                            {onEdit && <button onClick={() => onEdit(item)} title="Editar esta entrada" className="p-1 rounded text-white/40 hover:text-white hover:bg-white/10"><Pencil className="w-3.5 h-3.5" /></button>}
                            {onDelete && <button onClick={() => onDelete(item)} title="Eliminar esta entrada" className="p-1 rounded text-white/40 hover:text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></button>}
                        </div>
                    )}
                </div>
            </div>
            <div className="space-y-0.5">
                <MacroRow label="Entreno" color="#FF671F" m={item.training} />
                <MacroRow label="Descanso" color="#22C55E" m={item.rest} />
                {hasPeri && <MacroRow label="Peri" color="#818CF8" m={peri} showG={false} />}
            </div>
            {item.note && item.note !== 'Importado de Calma' && <p className="text-white/40 text-xs italic mt-2">{item.note}</p>}
        </div>
    );
};

const MiniStat = ({ label, value }) => (
    <div className="bg-[#0A0A0A] rounded p-2 border border-[#222]">
        <span className="text-white/40 text-[10px] uppercase">{label}</span>
        <span className="text-white font-bold text-sm ml-1">{value}</span>
    </div>
);

const WeightEvolution = ({ reports }) => {
    const data = (reports || [])
        .filter(r => r.weight != null)
        .map(r => ({ ts: new Date(r.created_at).getTime(), date: new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: '2-digit' }), peso: r.weight }))
        .sort((a, b) => a.ts - b.ts);
    if (!data.length) return null;
    const first = data[0].peso, last = data[data.length - 1].peso;
    const diff = Math.round((last - first) * 10) / 10;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><Scale className="w-4 h-4" />Evolución del peso ({data.length})</CardTitle></CardHeader>
            <CardContent>
                <div className="flex items-center gap-5 mb-3 text-sm">
                    <div><span className="text-white/40 text-xs mr-1">Inicio</span><span className="text-white font-bold">{first} kg</span></div>
                    <div><span className="text-white/40 text-xs mr-1">Actual</span><span className="text-white font-bold">{last} kg</span></div>
                    <div><span className="text-white/40 text-xs mr-1">Cambio</span><span className="text-white font-bold">{diff > 0 ? '+' : ''}{diff} kg</span></div>
                </div>
                <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: -8 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                            <XAxis dataKey="date" tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
                            <YAxis domain={['auto', 'auto']} tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
                            <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #333', borderRadius: 12, color: '#fff' }} labelStyle={{ color: '#fff' }} formatter={(v) => [`${v} kg`, 'Peso']} />
                            <Line type="monotone" dataKey="peso" stroke="#FF671F" strokeWidth={2} dot={{ fill: '#FF671F', r: 2 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};

const MEAL_ORDER = { C1: 1, C2: 2, C3: 3, C4: 4, C5: 5, C6: 6, Intra: 7, Post: 8 };
const MEAL_LABEL = { Intra: 'Intra-entreno', Post: 'Post-entreno', C1: 'Comida 1', C2: 'Comida 2', C3: 'Comida 3', C4: 'Comida 4', C5: 'Comida 5', C6: 'Comida 6' };

// Reportes del cliente con feedback editable por el coach (cierra el circuito de ReportsPage)
const ReportsFeedbackList = ({ initialReports }) => {
    const { api } = useAuth();
    const [reports, setReports] = useState(initialReports || []);
    const [drafts, setDrafts] = useState({});
    const [savingId, setSavingId] = useState(null);
    const [showAll, setShowAll] = useState(false);

    const saveFeedback = async (reportId) => {
        const text = (drafts[reportId] ?? '').trim();
        setSavingId(reportId);
        try {
            await api.put(`/reports/${reportId}/feedback`, { feedback: text });
            setReports(prev => prev.map(r => r.id === reportId ? { ...r, trainer_feedback: text || null } : r));
            setDrafts(prev => { const d = { ...prev }; delete d[reportId]; return d; });
            toast.success('Feedback guardado');
        } catch {
            toast.error('Error guardando el feedback');
        } finally { setSavingId(null); }
    };

    if (!reports.length) return null;
    const visible = showAll ? reports : reports.slice(0, 5);

    return (
        <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Reportes del cliente</p>
                <span className="text-white/25 text-xs">{reports.length} en total</span>
            </div>
            <div className="space-y-3">
                {visible.map(r => {
                    const draft = drafts[r.id] ?? (r.trainer_feedback || '');
                    const dirty = draft !== (r.trainer_feedback || '');
                    return (
                        <div key={r.id} className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]" data-testid={`report-${r.id}`}>
                            <div className="flex items-center gap-3 text-sm">
                                <span className="text-white/40 text-xs">{new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                                {r.weight != null && <span className="text-white font-bold">{r.weight} kg</span>}
                                {r.training_compliance != null && <span className="text-white/40 text-xs">Entreno {r.training_compliance}%</span>}
                                {r.nutrition_compliance != null && <span className="text-white/40 text-xs">Nutrición {r.nutrition_compliance}%</span>}
                            </div>
                            {r.notes && <p className="text-white/50 text-xs mt-1.5">"{r.notes}"</p>}
                            <div className="flex items-end gap-2 mt-2">
                                <Textarea value={draft} onChange={e => setDrafts(prev => ({ ...prev, [r.id]: e.target.value }))}
                                    placeholder="Escribe feedback para el cliente..." rows={1}
                                    className="bg-[#111] border-[#222] text-white text-xs flex-1 min-h-[34px]" />
                                {dirty && (
                                    <Button size="sm" onClick={() => saveFeedback(r.id)} disabled={savingId === r.id}
                                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-8">
                                        {savingId === r.id ? '...' : 'Guardar'}
                                    </Button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
            {reports.length > 5 && (
                <button onClick={() => setShowAll(v => !v)} className="text-[#FF671F] text-xs mt-3 hover:underline">
                    {showAll ? 'Ver menos' : `Ver los ${reports.length}`}
                </button>
            )}
        </CardContent></Card>
    );
};

const DietDetail = ({ diet }) => {
    const comidas = diet?.comidas || {};
    const keys = Object.keys(comidas).sort((a, b) => (MEAL_ORDER[a] || 99) - (MEAL_ORDER[b] || 99));
    const dayTotal = { P: 0, H: 0, G: 0 };
    const meals = keys.map((k) => {
        const foods = comidas[k]?.alimentos || [];
        const mt = { P: 0, H: 0, G: 0 };
        foods.forEach((a) => {
            const e = a.macros_efectivos || {};
            mt.P += e.P || 0; mt.H += e.H || 0; mt.G += e.G || 0;
            dayTotal.P += e.P || 0; dayTotal.H += e.H || 0; dayTotal.G += e.G || 0;
        });
        return { k, foods, mt };
    });
    return (
        <div className="space-y-2.5">
            {meals.map(({ k, foods, mt }) => (
                <div key={k} className="bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-white text-sm font-semibold">{MEAL_LABEL[k] || k}</span>
                        <span className="text-[11px]"><span className="text-orange-400">P{Math.round(mt.P)}</span> <span className="text-blue-400">H{Math.round(mt.H)}</span> <span className="text-yellow-400">G{Math.round(mt.G)}</span></span>
                    </div>
                    <div className="space-y-1">
                        {foods.length ? foods.map((a, i) => {
                            const e = a.macros_efectivos || {};
                            return (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                    <span className="text-white/80 flex-1 min-w-0 truncate">{a.nombre}</span>
                                    <span className="text-white/40 whitespace-nowrap w-12 text-right">{Math.round(a.cantidad_g)} g</span>
                                    <span className="whitespace-nowrap tabular-nums w-24 text-right">
                                        <span className="text-orange-400">P{Math.round(e.P || 0)}</span> <span className="text-blue-400">H{Math.round(e.H || 0)}</span> <span className="text-yellow-400">G{Math.round(e.G || 0)}</span>
                                    </span>
                                </div>
                            );
                        }) : <span className="text-white/30 text-xs">Vacía</span>}
                    </div>
                </div>
            ))}
            <div className="flex items-center justify-between pt-2 border-t border-[#222]">
                <span className="text-white/60 text-sm font-semibold">Total del día</span>
                <span className="text-sm font-bold"><span className="text-orange-400">P{Math.round(dayTotal.P)}</span> · <span className="text-blue-400">H{Math.round(dayTotal.H)}</span> · <span className="text-yellow-400">G{Math.round(dayTotal.G)}</span></span>
            </div>
        </div>
    );
};

const EmptyState = ({ icon: Icon, message, action }) => (
    <Card className="bg-[#111] border-[#222]"><CardContent className="p-8 text-center">
        <Icon className="w-10 h-10 text-white/10 mx-auto mb-3" />
        <p className="text-white/30 text-sm">{message}</p>
        {action}
    </CardContent></Card>
);

export default ClientDetailPage;
