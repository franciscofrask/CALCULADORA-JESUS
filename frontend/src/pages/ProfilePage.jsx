import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Separator } from '../components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { PlanBadge } from './ClientDashboard';
import { habilitacionesToList } from '../lib/planAccess';
import {
    User, Mail,
    LogOut, Lock, ChevronRight, Crown,
    TrendingUp, Edit2, Camera, Check,
    Compass
} from 'lucide-react';

// "Mejorar mi plan" OCULTO (petición 2026-07-06): el checkout de upgrade no existe aún
// (pagos reales pospuestos). Poner a true cuando se habiliten pagos.
const UPGRADE_PLAN_UI = false;

const ProfilePage = () => {
    const navigate = useNavigate();
    const { user, profile, logout, api, refreshUser, myPlan } = useAuth();
    const { startTour } = useOnboarding();
    const [editing, setEditing] = useState(false);
    const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
    const [formData, setFormData] = useState({ name: user?.name || '', phone: user?.phone || '' });
    const [saving, setSaving] = useState(false);

    const handleSave = async () => {
        if (!formData.name.trim()) { toast.error('El nombre no puede estar vacío'); return; }
        setSaving(true);
        try {
            await api.put('/auth/me', { name: formData.name.trim(), phone: formData.phone });
            await refreshUser();
            toast.success('Perfil actualizado');
            setEditing(false);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al actualizar el perfil');
        } finally {
            setSaving(false);
        }
    };

    // Cambio de contraseña
    const [showPasswordDialog, setShowPasswordDialog] = useState(false);
    const [pwdForm, setPwdForm] = useState({ current: '', next: '', confirm: '' });
    const [changingPwd, setChangingPwd] = useState(false);
    const handleChangePassword = async () => {
        if (pwdForm.next.length < 8) { toast.error('La nueva contraseña debe tener al menos 8 caracteres'); return; }
        if (pwdForm.next !== pwdForm.confirm) { toast.error('Las contraseñas nuevas no coinciden'); return; }
        setChangingPwd(true);
        try {
            await api.post('/auth/change-password', { current_password: pwdForm.current, new_password: pwdForm.next });
            toast.success('Contraseña cambiada');
            setShowPasswordDialog(false);
            setPwdForm({ current: '', next: '', confirm: '' });
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al cambiar la contraseña');
        } finally {
            setChangingPwd(false);
        }
    };

    const handleLogout = () => {
        logout();
        navigate('/auth');
        toast.success('Sesión cerrada');
    };

    // "Tu plan incluye" derivado del catálogo del backend (habilitaciones del plan).
    const currentPlanFeatures = habilitacionesToList(myPlan?.habilitaciones);

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-background min-h-screen relative overflow-hidden">
            <div className="relative z-10 space-y-6 max-w-lg mx-auto">
                <h1 className="text-2xl font-bold text-foreground tracking-tight" style={{ fontFamily: 'Barlow Condensed' }} data-testid="profile-heading">MI PERFIL</h1>

                {/* Profile Card */}
                <Card className="bg-card border-border">
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
                                <h2 className="font-bold text-foreground text-lg">{user?.name?.toUpperCase()}</h2>
                                <p className="text-foreground/50 text-sm">{user?.email}</p>
                                {profile && <div className="mt-1"><PlanBadge plan={profile.plan} /></div>}
                            </div>
                            <Button
                                variant="ghost" size="icon"
                                className="text-muted-foreground hover:text-brand"
                                onClick={() => setEditing(!editing)}
                                data-testid="edit-profile-btn"
                            >
                                <Edit2 className="w-4 h-4" />
                            </Button>
                        </div>
                        {editing && (
                            <div className="mt-5 space-y-4">
                                <Separator className="bg-border" />
                                <div className="grid gap-3">
                                    <div>
                                        <Label className="text-foreground/70 text-xs uppercase tracking-wider">Nombre</Label>
                                        <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="bg-background border-input text-foreground mt-1" />
                                    </div>
                                    <div>
                                        <Label className="text-foreground/70 text-xs uppercase tracking-wider">Teléfono</Label>
                                        <Input value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} placeholder="+34 612 345 678" className="bg-background border-input text-foreground mt-1" />
                                    </div>
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <Button variant="outline" onClick={() => setEditing(false)} className="bg-transparent border-input text-foreground hover:border-white/50 text-sm">Cancelar</Button>
                                    <Button onClick={handleSave} disabled={saving} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm">{saving ? 'Guardando...' : 'Guardar'}</Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Plan Info */}
                {profile && (
                    <Card className="bg-gradient-to-br from-[#FF671F]/10 to-[#FF671F]/5 border-[#FF671F]/30">
                        <CardHeader className="pb-2">
                            <CardTitle className="flex items-center justify-between">
                                <span className="flex items-center gap-2 text-foreground uppercase tracking-wider text-base">
                                    <Crown className="w-5 h-5 text-[#FF671F]" />
                                    Mi Plan
                                </span>
                                <PlanBadge plan={profile.plan} planName={myPlan?.name} />
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-sm text-foreground/50 uppercase tracking-wider">Precio</p>
                                    <p className="text-3xl font-bold text-[#FF671F]" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {profile.price != null ? `${profile.price}€` : '-'}<span className="text-sm font-normal text-foreground/50">/ciclo</span>
                                    </p>
                                    {myPlan?.precio_nota && (
                                        <p className="text-xs text-foreground/50 mt-1">{myPlan.precio_nota}</p>
                                    )}
                                </div>
                                <div>
                                    <p className="text-sm text-foreground/50 uppercase tracking-wider">Próxima renovación</p>
                                    <p className="font-semibold text-foreground text-sm">
                                        {profile.next_payment
                                            ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })
                                            : 'No definida'}
                                    </p>
                                </div>
                            </div>
                            <Separator className="bg-white/10" />
                            <div>
                                <p className="text-sm font-bold text-foreground uppercase tracking-wider mb-3">Tu plan incluye:</p>
                                <ul className="space-y-2">
                                    {currentPlanFeatures.map((feature, index) => (
                                        <li key={index} className="flex items-center gap-2 text-sm text-foreground/80">
                                            <div className="w-5 h-5 rounded bg-[#FF671F]/20 flex items-center justify-center flex-shrink-0">
                                                <Check className="w-3 h-3 text-[#FF671F]" />
                                            </div>
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            {UPGRADE_PLAN_UI && profile.plan !== 'gold' && (
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
                <Card className="bg-card border-border">
                    <CardContent className="p-0">
                        {[
                            { icon: Lock, title: 'Cambiar contraseña', sub: 'Seguridad de la cuenta', onClick: () => setShowPasswordDialog(true) },
                        ].map((item, i) => (
                            <React.Fragment key={item.title}>
                                {i > 0 && <Separator className="bg-border" />}
                                <button
                                    className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                                    onClick={item.onClick}
                                    data-testid={`setting-${i}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                            <item.icon className="w-5 h-5 text-[#FF671F]" />
                                        </div>
                                        <div className="text-left">
                                            <p className="font-medium text-foreground text-sm">{item.title}</p>
                                            <p className="text-xs text-foreground/50">{item.sub}</p>
                                        </div>
                                    </div>
                                    <ChevronRight className="w-5 h-5 text-foreground/30" />
                                </button>
                            </React.Fragment>
                        ))}
                    </CardContent>
                </Card>

                {/* Repetir recorrido guiado */}
                <Button
                    variant="outline"
                    className="w-full bg-transparent border-brand/40 text-brand hover:bg-brand/10 hover:border-brand uppercase tracking-wider"
                    onClick={() => { navigate('/dashboard'); startTour(); }}
                    data-testid="replay-tour-btn"
                >
                    <Compass className="w-4 h-4 mr-2" /> Repetir recorrido guiado
                </Button>

                {/* Logout */}
                <Button
                    variant="outline"
                    className="w-full bg-transparent border-red-500/50 text-red-500 hover:bg-red-500/10 hover:border-red-500 uppercase tracking-wider"
                    onClick={handleLogout}
                    data-testid="logout-btn"
                >
                    <LogOut className="w-4 h-4 mr-2" /> Cerrar sesión
                </Button>

                {/* Change Password Dialog */}
                <Dialog open={showPasswordDialog} onOpenChange={o => { setShowPasswordDialog(o); if (!o) setPwdForm({ current: '', next: '', confirm: '' }); }}>
                    <DialogContent className="bg-card border-input" data-testid="change-password-dialog">
                        <DialogHeader>
                            <DialogTitle className="text-foreground uppercase tracking-wider">Cambiar contraseña</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-3">
                            <div>
                                <Label className="text-foreground/60 text-xs">Contraseña actual</Label>
                                <Input type="password" value={pwdForm.current} onChange={e => setPwdForm({ ...pwdForm, current: e.target.value })} className="bg-background border-input text-foreground mt-1" data-testid="pwd-current" />
                            </div>
                            <div>
                                <Label className="text-foreground/60 text-xs">Nueva contraseña (mínimo 8 caracteres)</Label>
                                <Input type="password" value={pwdForm.next} onChange={e => setPwdForm({ ...pwdForm, next: e.target.value })} className="bg-background border-input text-foreground mt-1" data-testid="pwd-new" />
                            </div>
                            <div>
                                <Label className="text-foreground/60 text-xs">Repite la nueva contraseña</Label>
                                <Input type="password" value={pwdForm.confirm} onChange={e => setPwdForm({ ...pwdForm, confirm: e.target.value })} className="bg-background border-input text-foreground mt-1" data-testid="pwd-confirm" />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setShowPasswordDialog(false)} className="bg-transparent border-input text-foreground">Cancelar</Button>
                            <Button onClick={handleChangePassword} disabled={changingPwd || !pwdForm.current || !pwdForm.next || !pwdForm.confirm} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" data-testid="pwd-save">
                                {changingPwd ? 'Guardando...' : 'Cambiar contraseña'}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Upgrade Dialog */}
                <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
                    <DialogContent className="bg-card border-input">
                        <DialogHeader>
                            <DialogTitle className="text-foreground uppercase tracking-wider">Mejorar tu plan</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                            {profile?.plan !== 'gold' && (
                                <Card className="bg-background border-input cursor-pointer hover:border-yellow-500 transition-colors" onClick={() => toast.info('Funcionalidad próximamente')}>
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-600 text-foreground font-bold px-3 py-1 rounded text-sm uppercase">Gold</span>
                                            <span className="font-bold text-foreground text-xl" style={{ fontFamily: 'Barlow Condensed' }}>149€/ciclo</span>
                                        </div>
                                        <p className="text-sm text-foreground/50">Incluye todo: rutina semanal, reporte quincenal, cardio, audio y suplementación.</p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setShowUpgradeDialog(false)} className="bg-transparent border-input text-foreground">Cancelar</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default ProfilePage;
