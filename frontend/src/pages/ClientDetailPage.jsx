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
import {
    ArrowLeft, User, Mail, Phone, Calendar, CreditCard, Dumbbell, Apple,
    FileText, Scale, Target, Zap, Save, Loader2, History, Shield,
    ClipboardList, TrendingUp, Utensils, Activity, ChevronDown, ChevronUp,
    AlertCircle
} from 'lucide-react';

const ClientDetailPage = () => {
    const { clientId } = useParams();
    const navigate = useNavigate();
    const { api, user: adminUser } = useAuth();
    const [client, setClient] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('resumen');

    // Macros modal
    const [macrosModalOpen, setMacrosModalOpen] = useState(false);
    const [macrosForm, setMacrosForm] = useState({
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        peri: { protein: '', carbs: '' },
        note: ''
    });
    const [savingMacros, setSavingMacros] = useState(false);

    // Routine
    const [generatingRoutine, setGeneratingRoutine] = useState(false);
    const [routineInstructions, setRoutineInstructions] = useState('');
    const [generatedRoutine, setGeneratedRoutine] = useState(null);

    useEffect(() => { fetchClient(); }, [clientId]); // eslint-disable-line

    const fetchClient = async () => {
        try {
            const response = await api.get(`/admin/clients/${clientId}`);
            setClient(response.data);
            const p = response.data.profile;
            if (p?.macros_training) {
                setMacrosForm({
                    training: { protein: p.macros_training.protein || p.macros_training.proteinas || '', carbs: p.macros_training.carbs || p.macros_training.hidratos || '', fat: p.macros_training.fat || p.macros_training.grasas || '' },
                    rest: { protein: p.macros_rest?.protein || p.macros_rest?.proteinas || '', carbs: p.macros_rest?.carbs || p.macros_rest?.hidratos || '', fat: p.macros_rest?.fat || p.macros_rest?.grasas || '' },
                    peri: { protein: p.macros_periworkout?.protein || p.macros_periworkout?.proteinas || '', carbs: p.macros_periworkout?.carbs || p.macros_periworkout?.hidratos || '' },
                    note: ''
                });
            }
        } catch (error) {
            toast.error('Error al cargar datos del cliente');
            navigate('/admin/clients');
        } finally { setLoading(false); }
    };

    const handleSaveMacros = async () => {
        if (!macrosForm.note.trim()) { toast.error('El motivo es obligatorio'); return; }
        setSavingMacros(true);
        try {
            await api.put(`/admin/clients/${clientId}/macros`, {
                training: { protein: parseFloat(macrosForm.training.protein), carbs: parseFloat(macrosForm.training.carbs), fat: parseFloat(macrosForm.training.fat) },
                rest: { protein: parseFloat(macrosForm.rest.protein), carbs: parseFloat(macrosForm.rest.carbs), fat: parseFloat(macrosForm.rest.fat) },
                note: macrosForm.note
            });
            toast.success('Macros actualizados');
            setMacrosModalOpen(false);
            setMacrosForm(prev => ({ ...prev, note: '' }));
            fetchClient();
        } catch (error) { toast.error('Error al actualizar macros'); }
        finally { setSavingMacros(false); }
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
        { id: 'membresia', label: 'Membresía', icon: CreditCard },
        { id: 'reportes', label: 'Reportes', icon: FileText },
        { id: 'cuestionario', label: 'Cuestionario', icon: ClipboardList },
        { id: 'entrenamiento', label: 'Entreno', icon: Dumbbell },
        { id: 'nutricion', label: 'Nutrición', icon: Utensils },
        { id: 'seguimiento', label: 'Seguimiento', icon: TrendingUp },
    ];

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="client-detail">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" onClick={() => navigate('/admin/clients')} className="text-white/50 hover:text-white"><ArrowLeft className="w-5 h-5" /></Button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h1 className="text-2xl font-bold text-white truncate" style={{ fontFamily: 'Bebas Neue' }}>{user?.name?.toUpperCase()}</h1>
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
                            <InfoItem icon={Phone} label="Teléfono" value={user?.phone || '—'} />
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} />} />
                            <InfoItem icon={Activity} label="Estado" value={profile?.status} />
                            <InfoItem icon={Calendar} label="Semana" value={`${profile?.week || 1}/4`} />
                            <InfoItem icon={Dumbbell} label="Entrenador" value={profile?.trainer_id || 'Sin asignar'} />
                            <InfoItem icon={Target} label="Rutina" value={activeRoutine ? `${activeRoutine.days?.filter(d => !d.is_rest).length || 0} días` : 'Sin rutina'} />
                            <InfoItem icon={CreditCard} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '—'} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '—'} />
                            <InfoItem icon={Scale} label="Peso" value={profile?.weight ? `${profile.weight} kg` : '—'} />
                            <InfoItem icon={Target} label="Objetivo" value={profile?.goal || '—'} />
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
                                    <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs" onClick={() => setMacrosModalOpen(true)} data-testid="change-macros-btn">Cambiar macros</Button>
                                </div>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
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
                    ) : <EmptyState icon={Apple} message="Sin macros asignados. Usa 'Cambiar macros' para asignar." action={<Button size="sm" className="bg-[#FF671F] text-white mt-2" onClick={() => setMacrosModalOpen(true)}>Asignar macros</Button>} />}

                    {/* Macro History */}
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><History className="w-4 h-4" />Historial de cambios</CardTitle></CardHeader>
                        <CardContent>{macro_history?.length > 0 ? (
                            <div className="space-y-2">{macro_history.map((h, i) => <MacroHistoryItem key={h.id || i} item={h} />)}</div>
                        ) : <p className="text-white/30 text-sm text-center py-4">Sin cambios registrados</p>}</CardContent>
                    </Card>

                    {/* Macros Modal */}
                    <Dialog open={macrosModalOpen} onOpenChange={setMacrosModalOpen}>
                        <DialogContent className="bg-[#111] border-[#333] max-w-lg" data-testid="macros-modal">
                            <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">Cambiar macros</DialogTitle></DialogHeader>
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
                                    <Label className="text-white/60 text-xs">Motivo del cambio (obligatorio)</Label>
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
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} />} />
                            <InfoItem icon={CreditCard} label="Precio" value={`${profile?.price || 0}€/ciclo`} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '—'} />
                            <InfoItem icon={Calendar} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES') : '—'} />
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
                <TabsContent value="reportes">
                    {reports?.length > 0 ? (
                        <div className="space-y-3">{reports.map(r => (
                            <Card key={r.id} className="bg-[#111] border-[#222]"><CardContent className="p-4">
                                <div className="flex items-center justify-between mb-2">
                                    <p className="text-white text-sm font-bold">{new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</p>
                                    <span className="text-[#FF671F] font-bold text-lg" style={{ fontFamily: 'Bebas Neue' }}>{r.weight} kg</span>
                                </div>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                    <MiniStat label="Entreno" value={`${r.training_compliance}%`} />
                                    <MiniStat label="Nutrición" value={`${r.nutrition_compliance}%`} />
                                    <MiniStat label="Sueño" value={`${r.sleep_quality}/10`} />
                                    <MiniStat label="Energía" value={`${r.energy_level}/10`} />
                                </div>
                                {r.notes && <p className="text-white/30 text-xs mt-2 italic">{r.notes}</p>}
                            </CardContent></Card>
                        ))}</div>
                    ) : <EmptyState icon={FileText} message="Sin reportes aún." />}
                </TabsContent>

                {/* ========== TAB 5: CUESTIONARIO ========== */}
                <TabsContent value="cuestionario">
                    {(profile?.goal || profile?.weight || profile?.equipment?.length) ? (
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                <InfoItem icon={Target} label="Objetivo" value={profile?.goal || '—'} />
                                <InfoItem icon={Scale} label="Peso inicial" value={profile?.weight ? `${profile.weight} kg` : '—'} />
                                <InfoItem icon={User} label="Sexo" value={profile?.sex || '—'} />
                                <InfoItem icon={Activity} label="% Graso" value={profile?.body_fat ? `${profile.body_fat}%` : '—'} />
                                <InfoItem icon={Calendar} label="Edad" value={profile?.age || '—'} />
                                <InfoItem icon={Scale} label="Altura" value={profile?.height ? `${profile.height} cm` : '—'} />
                            </div>
                            {profile?.equipment?.length > 0 && (
                                <div className="mt-4"><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Equipamiento</p>
                                    <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{e}</Badge>)}</div>
                                </div>
                            )}
                            {profile?.injuries?.length > 0 && (
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
                                {profile?.equipment?.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{e}</Badge>)}</div> : <p className="text-white/30 text-sm">No especificado</p>}
                            </div>
                            <div><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones activas</p>
                                {profile?.injuries?.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.injuries.map((l, i) => <Badge key={i} className="bg-red-500/10 text-red-400 border-0 text-xs">{l}</Badge>)}</div> : <p className="text-white/30 text-sm">Sin lesiones</p>}
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

                {/* ========== TAB 7: NUTRICIÓN ========== */}
                <TabsContent value="nutricion" className="space-y-4">
                    {nutrition_stats?.total_diets > 0 ? (<>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Top 5 alimentos</CardTitle></CardHeader>
                                <CardContent><div className="space-y-2">{nutrition_stats.top_foods?.map((f, i) => (
                                    <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg">
                                        <span className="text-white text-sm truncate flex-1">{f.nombre}</span>
                                        <Badge className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs ml-2">{f.count}x</Badge>
                                    </div>
                                ))}</div></CardContent>
                            </Card>
                            <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Dietas recientes ({nutrition_stats.total_diets})</CardTitle></CardHeader>
                                <CardContent><div className="space-y-2">{nutrition_stats.recent_diets?.map((d, i) => (
                                    <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg">
                                        <span className="text-white text-sm">{new Date(d.fecha + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</span>
                                        <Badge className={d.tipo_dia === 'entrenamiento' ? 'bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs' : 'bg-green-500/10 text-green-500 border-0 text-xs'}>{d.tipo_dia}</Badge>
                                    </div>
                                ))}</div></CardContent>
                            </Card>
                        </div>
                    </>) : <EmptyState icon={Utensils} message="Sin datos de nutrición aún." />}
                </TabsContent>

                {/* ========== TAB 8: SEGUIMIENTO ========== */}
                <TabsContent value="seguimiento">
                    {reports?.length > 0 ? (
                        <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Evolución de peso</CardTitle></CardHeader>
                            <CardContent>
                                <div className="flex items-end gap-1 h-40">
                                    {reports.slice().reverse().map((r, i) => {
                                        const weights = reports.map(r2 => r2.weight);
                                        const minW = Math.min(...weights) - 2;
                                        const maxW = Math.max(...weights) + 2;
                                        const range = maxW - minW || 1;
                                        const pct = ((r.weight - minW) / range) * 100;
                                        return (
                                            <div key={i} className="flex-1 flex flex-col items-center gap-1">
                                                <span className="text-[10px] text-white/50">{r.weight}</span>
                                                <div className="w-full bg-[#1A1A1A] rounded-t" style={{ height: `${Math.max(pct, 10)}%` }}>
                                                    <div className="w-full h-full bg-[#FF671F] rounded-t" />
                                                </div>
                                                <span className="text-[9px] text-white/30">{new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                                <p className="text-center text-white/20 text-xs mt-3">Placeholder para fotos de progreso</p>
                            </CardContent>
                        </Card>
                    ) : <EmptyState icon={TrendingUp} message="Se completará con los check-ins del cliente." />}
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
                <span className="text-white font-bold text-sm" style={{ fontFamily: 'Bebas Neue' }}>{it.value}g</span>
            </div>
        ))}</div>
    </div>
);

const MacroHistoryItem = ({ item }) => (
    <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
        <div className="flex items-center justify-between mb-1">
            <span className="text-white/40 text-xs">{new Date(item.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
            <span className="text-white/30 text-[10px]">{item.changed_by || 'admin'}</span>
        </div>
        {item.note && <p className="text-white/60 text-xs italic mb-1">{item.note}</p>}
        <div className="text-[10px] text-white/30">
            E: P={Math.round(item.training?.protein || item.training?.proteinas || 0)} H={Math.round(item.training?.carbs || item.training?.hidratos || 0)} G={Math.round(item.training?.fat || item.training?.grasas || 0)}
            {' · '}D: P={Math.round(item.rest?.protein || item.rest?.proteinas || 0)} H={Math.round(item.rest?.carbs || item.rest?.hidratos || 0)} G={Math.round(item.rest?.fat || item.rest?.grasas || 0)}
        </div>
    </div>
);

const MiniStat = ({ label, value }) => (
    <div className="bg-[#0A0A0A] rounded p-2 border border-[#222]">
        <span className="text-white/40 text-[10px] uppercase">{label}</span>
        <span className="text-white font-bold text-sm ml-1">{value}</span>
    </div>
);

const EmptyState = ({ icon: Icon, message, action }) => (
    <Card className="bg-[#111] border-[#222]"><CardContent className="p-8 text-center">
        <Icon className="w-10 h-10 text-white/10 mx-auto mb-3" />
        <p className="text-white/30 text-sm">{message}</p>
        {action}
    </CardContent></Card>
);

export default ClientDetailPage;
