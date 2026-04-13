import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Separator } from '../components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { PlanBadge } from './ClientDashboard';
import {
    User, Mail, CreditCard,
    LogOut, Bell, Lock, ChevronRight, Crown,
    TrendingUp, Edit2, Camera, Check,
    Scale, Target, Activity, Flame, Zap
} from 'lucide-react';

const PLAN_FEATURES = {
    gold: ['Rutina personalizada semanal', 'Macros individualizados', 'Chat directo con entrenador', 'Reporte quincenal', 'Cardio personalizado', 'Audio de Jesús', 'Suplementación guiada'],
    silver: ['Rutina personalizada semanal', 'Macros individualizados', 'Chat directo con entrenador', 'Reporte mensual'],
    bronze: ['Rutina básica mensual', 'Macros calculados', 'Chat con soporte', 'Reporte mensual'],
    elm: ['Calculadora de macros', 'Chat con soporte']
};

const ProfilePage = () => {
    const navigate = useNavigate();
    const { user, profile, logout, api, refreshProfile } = useAuth();
    const [editing, setEditing] = useState(false);
    const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
    const [formData, setFormData] = useState({ name: user?.name || '', phone: user?.phone || '' });
    const [saving, setSaving] = useState(false);

    // Body data form
    const [bodyData, setBodyData] = useState({
        peso: profile?.weight || '',
        sexo: profile?.sex || 'hombre',
        porcentaje_graso: profile?.body_fat || '',
        objetivo: profile?.goal || 'volumen',
    });
    const [calculatedMacros, setCalculatedMacros] = useState(null);
    const [calculating, setCalculating] = useState(false);
    const [showMacrosResult, setShowMacrosResult] = useState(false);

    useEffect(() => {
        if (profile) {
            setBodyData({
                peso: profile.weight || '',
                sexo: profile.sex || 'hombre',
                porcentaje_graso: profile.body_fat || '',
                objetivo: profile.goal || 'volumen',
            });
            if (profile.macros_training && profile.macros_source === 'auto') {
                setShowMacrosResult(true);
            }
        }
    }, [profile]);

    const handleSave = async () => {
        setSaving(true);
        try {
            toast.success('Perfil actualizado');
            setEditing(false);
        } catch (error) {
            toast.error('Error al actualizar el perfil');
        } finally {
            setSaving(false);
        }
    };

    const handleLogout = () => {
        logout();
        navigate('/auth');
        toast.success('Sesión cerrada');
    };

    const handleCalculateTargets = async () => {
        const { peso, sexo, porcentaje_graso, objetivo } = bodyData;
        if (!peso || !porcentaje_graso) {
            toast.error('Introduce tu peso y % graso');
            return;
        }
        if (peso < 40 || peso > 200) {
            toast.error('Peso debe estar entre 40 y 200 kg');
            return;
        }
        if (porcentaje_graso < 5 || porcentaje_graso > 60) {
            toast.error('% graso debe estar entre 5 y 60');
            return;
        }

        setCalculating(true);
        try {
            const res = await api.post('/calculator/targets/apply', {
                peso: parseFloat(peso),
                sexo,
                porcentaje_graso: parseFloat(porcentaje_graso),
                objetivo,
            });
            setCalculatedMacros(res.data.targets);
            setShowMacrosResult(true);
            await refreshProfile();
            toast.success('Macros calculados y aplicados');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error calculando macros');
        } finally {
            setCalculating(false);
        }
    };

    const currentPlanFeatures = PLAN_FEATURES[profile?.plan] || [];
    const mt = profile?.macros_training;
    const mr = profile?.macros_rest;
    const mp = profile?.macros_periworkout;

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen relative overflow-hidden">
            <div className="relative z-10 space-y-6 max-w-lg mx-auto">
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Bebas Neue' }}>MI PERFIL</h1>

                {/* Profile Card */}
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                            <div className="relative">
                                <Avatar className="w-16 h-16 border-2 border-[#FF671F]">
                                    <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.email}`} />
                                    <AvatarFallback className="text-xl bg-[#FF671F] text-white">
                                        {user?.name?.charAt(0)?.toUpperCase()}
                                    </AvatarFallback>
                                </Avatar>
                            </div>
                            <div className="flex-1">
                                <h2 className="font-bold text-white text-lg">{user?.name?.toUpperCase()}</h2>
                                <p className="text-white/50 text-sm">{user?.email}</p>
                                {profile && <div className="mt-1"><PlanBadge plan={profile.plan} /></div>}
                            </div>
                            <Button
                                variant="ghost" size="icon"
                                className="text-white/50 hover:text-[#FF671F]"
                                onClick={() => setEditing(!editing)}
                                data-testid="edit-profile-btn"
                            >
                                <Edit2 className="w-4 h-4" />
                            </Button>
                        </div>
                        {editing && (
                            <div className="mt-5 space-y-4">
                                <Separator className="bg-[#222]" />
                                <div className="grid gap-3">
                                    <div>
                                        <Label className="text-white/70 text-xs uppercase tracking-wider">Nombre</Label>
                                        <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                                    </div>
                                    <div>
                                        <Label className="text-white/70 text-xs uppercase tracking-wider">Teléfono</Label>
                                        <Input value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} placeholder="+34 612 345 678" className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                                    </div>
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <Button variant="outline" onClick={() => setEditing(false)} className="bg-transparent border-[#333] text-white hover:border-white/50 text-sm">Cancelar</Button>
                                    <Button onClick={handleSave} disabled={saving} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm">{saving ? 'Guardando...' : 'Guardar'}</Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Body Data + Targets Calculator */}
                <Card className="bg-[#111111] border-[#FF671F]/30 overflow-hidden" data-testid="body-data-card">
                    <CardHeader className="pb-3 bg-gradient-to-r from-[#FF671F]/10 to-transparent">
                        <CardTitle className="flex items-center gap-2 text-white text-base uppercase tracking-wider">
                            <Scale className="w-5 h-5 text-[#FF671F]" />
                            Mis Datos Corporales
                        </CardTitle>
                        <p className="text-white/40 text-xs mt-1">Calcula tus macros automáticamente según tu composición</p>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-2">
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="text-white/60 text-xs uppercase tracking-wider">Peso (kg)</Label>
                                <Input
                                    type="number"
                                    value={bodyData.peso}
                                    onChange={(e) => setBodyData({ ...bodyData, peso: e.target.value })}
                                    placeholder="80"
                                    className="bg-[#0A0A0A] border-[#333] text-white mt-1 text-lg font-bold text-center"
                                    data-testid="body-peso-input"
                                />
                            </div>
                            <div>
                                <Label className="text-white/60 text-xs uppercase tracking-wider">% Graso</Label>
                                <Input
                                    type="number"
                                    value={bodyData.porcentaje_graso}
                                    onChange={(e) => setBodyData({ ...bodyData, porcentaje_graso: e.target.value })}
                                    placeholder="20"
                                    className="bg-[#0A0A0A] border-[#333] text-white mt-1 text-lg font-bold text-center"
                                    data-testid="body-bf-input"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="text-white/60 text-xs uppercase tracking-wider">Sexo</Label>
                                <div className="flex gap-2 mt-1">
                                    {['hombre', 'mujer'].map((s) => (
                                        <button
                                            key={s}
                                            onClick={() => setBodyData({ ...bodyData, sexo: s })}
                                            className={`flex-1 py-2.5 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${
                                                bodyData.sexo === s
                                                    ? 'bg-[#FF671F] text-white'
                                                    : 'bg-[#1A1A1A] text-white/40 hover:text-white/70 border border-[#333]'
                                            }`}
                                            data-testid={`body-sexo-${s}`}
                                        >
                                            {s === 'hombre' ? 'H' : 'M'}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <Label className="text-white/60 text-xs uppercase tracking-wider">Objetivo</Label>
                                <div className="flex gap-2 mt-1">
                                    {[{ v: 'volumen', l: 'Vol' }, { v: 'definicion', l: 'Def' }].map(({ v, l }) => (
                                        <button
                                            key={v}
                                            onClick={() => setBodyData({ ...bodyData, objetivo: v })}
                                            className={`flex-1 py-2.5 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${
                                                bodyData.objetivo === v
                                                    ? 'bg-[#FF671F] text-white'
                                                    : 'bg-[#1A1A1A] text-white/40 hover:text-white/70 border border-[#333]'
                                            }`}
                                            data-testid={`body-obj-${v}`}
                                        >
                                            {l}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <Button
                            className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider h-12"
                            onClick={handleCalculateTargets}
                            disabled={calculating}
                            data-testid="calculate-targets-btn"
                        >
                            {calculating ? (
                                <div className="flex items-center gap-2">
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Calculando...
                                </div>
                            ) : (
                                <div className="flex items-center gap-2">
                                    <Target className="w-4 h-4" />
                                    Calcular mis macros
                                </div>
                            )}
                        </Button>

                        {/* Macros Result */}
                        {showMacrosResult && mt && (
                            <div className="space-y-3 pt-2" data-testid="macros-result">
                                <div className="flex items-center justify-between">
                                    <p className="text-xs font-bold text-white/50 uppercase tracking-wider">Tus macros</p>
                                    <span className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${
                                        profile?.macros_source === 'auto'
                                            ? 'bg-green-500/20 text-green-400'
                                            : 'bg-yellow-500/20 text-yellow-400'
                                    }`} data-testid="macros-source-badge">
                                        {profile?.macros_source === 'auto' ? 'Auto' : 'Manual'}
                                    </span>
                                </div>

                                {/* Training day */}
                                <div className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Flame className="w-4 h-4 text-[#FF671F]" />
                                        <span className="text-xs font-bold text-white uppercase tracking-wider">Día Entreno</span>
                                        <span className="ml-auto text-xs text-white/40">{Math.round((mt.protein || mt.proteinas || 0) * 4 + (mt.carbs || mt.hidratos || 0) * 4 + (mt.fat || mt.grasas || 0) * 9)} kcal</span>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2">
                                        <MacroPill label="P" value={mt.protein || mt.proteinas} color="#3B82F6" />
                                        <MacroPill label="H" value={mt.carbs || mt.hidratos} color="#F59E0B" />
                                        <MacroPill label="G" value={mt.fat || mt.grasas} color="#EF4444" />
                                    </div>
                                </div>

                                {/* Periworkout */}
                                {mp && (
                                    <div className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Zap className="w-4 h-4 text-yellow-400" />
                                            <span className="text-xs font-bold text-white uppercase tracking-wider">Perientreno</span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <MacroPill label="P" value={mp.protein || mp.proteinas} color="#3B82F6" />
                                            <MacroPill label="H" value={mp.carbs || mp.hidratos} color="#F59E0B" />
                                        </div>
                                    </div>
                                )}

                                {/* Rest day */}
                                {mr && (
                                    <div className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Activity className="w-4 h-4 text-green-400" />
                                            <span className="text-xs font-bold text-white uppercase tracking-wider">Día Descanso</span>
                                            <span className="ml-auto text-xs text-white/40">{Math.round((mr.protein || mr.proteinas || 0) * 4 + (mr.carbs || mr.hidratos || 0) * 4 + (mr.fat || mr.grasas || 0) * 9)} kcal</span>
                                        </div>
                                        <div className="grid grid-cols-3 gap-2">
                                            <MacroPill label="P" value={mr.protein || mr.proteinas} color="#3B82F6" />
                                            <MacroPill label="H" value={mr.carbs || mr.hidratos} color="#F59E0B" />
                                            <MacroPill label="G" value={mr.fat || mr.grasas} color="#EF4444" />
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Plan Info */}
                {profile && (
                    <Card className="bg-gradient-to-br from-[#FF671F]/10 to-[#FF671F]/5 border-[#FF671F]/30">
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center justify-between">
                                <span className="flex items-center gap-2 text-white uppercase tracking-wider text-base">
                                    <Crown className="w-5 h-5 text-[#FF671F]" />
                                    Mi Plan
                                </span>
                                <PlanBadge plan={profile.plan} />
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-white/50 uppercase tracking-wider">Precio</p>
                                    <p className="text-3xl font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>
                                        {profile.price}<span className="text-sm font-normal text-white/50">/ciclo</span>
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-white/50 uppercase tracking-wider">Próxima renovación</p>
                                    <p className="font-semibold text-white text-sm">
                                        {profile.next_payment
                                            ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })
                                            : 'No definida'}
                                    </p>
                                </div>
                            </div>
                            <Separator className="bg-white/10" />
                            <div>
                                <p className="text-sm font-bold text-white uppercase tracking-wider mb-3">Tu plan incluye:</p>
                                <ul className="space-y-2">
                                    {currentPlanFeatures.map((feature, index) => (
                                        <li key={index} className="flex items-center gap-2 text-sm text-white/80">
                                            <div className="w-5 h-5 rounded bg-[#FF671F]/20 flex items-center justify-center flex-shrink-0">
                                                <Check className="w-3 h-3 text-[#FF671F]" />
                                            </div>
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            {profile.plan !== 'gold' && (
                                <Button
                                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider"
                                    onClick={() => setShowUpgradeDialog(true)}
                                    data-testid="upgrade-btn"
                                >
                                    <TrendingUp className="w-4 h-4 mr-2" /> Mejorar mi plan
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                )}

                {/* Settings */}
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-0">
                        {[
                            { icon: CreditCard, title: 'Método de pago', sub: 'Gestionar tarjeta' },
                            { icon: Bell, title: 'Notificaciones', sub: 'Configurar alertas' },
                            { icon: Lock, title: 'Cambiar contraseña', sub: 'Seguridad de la cuenta' },
                        ].map((item, i) => (
                            <React.Fragment key={item.title}>
                                {i > 0 && <Separator className="bg-[#222]" />}
                                <button
                                    className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                                    onClick={() => toast.info('Funcionalidad próximamente')}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                                            <item.icon className="w-5 h-5 text-[#FF671F]" />
                                        </div>
                                        <div className="text-left">
                                            <p className="font-medium text-white text-sm">{item.title}</p>
                                            <p className="text-xs text-white/50">{item.sub}</p>
                                        </div>
                                    </div>
                                    <ChevronRight className="w-5 h-5 text-white/30" />
                                </button>
                            </React.Fragment>
                        ))}
                    </CardContent>
                </Card>

                {/* Logout */}
                <Button
                    variant="outline"
                    className="w-full bg-transparent border-red-500/50 text-red-500 hover:bg-red-500/10 hover:border-red-500 uppercase tracking-wider"
                    onClick={handleLogout}
                    data-testid="logout-btn"
                >
                    <LogOut className="w-4 h-4 mr-2" /> Cerrar sesión
                </Button>

                {/* Upgrade Dialog */}
                <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
                    <DialogContent className="bg-[#111111] border-[#333]">
                        <DialogHeader>
                            <DialogTitle className="text-white uppercase tracking-wider">Mejorar tu plan</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                            {profile?.plan !== 'gold' && (
                                <Card className="bg-[#0A0A0A] border-[#333] cursor-pointer hover:border-yellow-500 transition-colors" onClick={() => toast.info('Funcionalidad próximamente')}>
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-600 text-black font-bold px-3 py-1 rounded text-sm uppercase">Gold</span>
                                            <span className="font-bold text-white text-xl" style={{ fontFamily: 'Bebas Neue' }}>149/ciclo</span>
                                        </div>
                                        <p className="text-sm text-white/50">Incluye todo: rutina semanal, reporte quincenal, cardio, audio y suplementación.</p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setShowUpgradeDialog(false)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

const MacroPill = ({ label, value, color }) => (
    <div className="bg-[#111] rounded-lg p-2 text-center border border-[#222]">
        <div className="text-xs font-bold uppercase tracking-wider mb-0.5" style={{ color }}>{label}</div>
        <div className="text-white font-bold text-lg" style={{ fontFamily: 'Bebas Neue' }}>{Math.round(value || 0)}g</div>
    </div>
);

export default ProfilePage;
