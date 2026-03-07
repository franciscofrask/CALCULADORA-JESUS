import React, { useState } from 'react';
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
    User, Mail, Phone, CreditCard, 
    LogOut, Bell, Lock, ChevronRight, Crown, 
    TrendingUp, Edit2, Camera, Star, Check
} from 'lucide-react';

const PLAN_FEATURES = {
    gold: [
        'Rutina personalizada semanal',
        'Macros individualizados',
        'Chat directo con entrenador',
        'Reporte quincenal',
        'Cardio personalizado',
        'Audio de Jesús',
        'Suplementación guiada'
    ],
    silver: [
        'Rutina personalizada semanal',
        'Macros individualizados',
        'Chat directo con entrenador',
        'Reporte mensual'
    ],
    bronze: [
        'Rutina básica mensual',
        'Macros calculados',
        'Chat con soporte',
        'Reporte mensual'
    ],
    elm: [
        'Calculadora de macros',
        'Chat con soporte'
    ]
};

const ProfilePage = () => {
    const navigate = useNavigate();
    const { user, profile, logout } = useAuth();
    const [editing, setEditing] = useState(false);
    const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
    const [formData, setFormData] = useState({
        name: user?.name || '',
        phone: user?.phone || ''
    });
    const [saving, setSaving] = useState(false);

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

    const currentPlanFeatures = PLAN_FEATURES[profile?.plan] || [];

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen relative overflow-hidden">
            {/* Background */}
            <div 
                className="absolute inset-0 bg-cover bg-center opacity-5"
                style={{
                    backgroundImage: `url('https://customer-assets.emergentagent.com/job_language-12/artifacts/3l0g25yy_IMG_5760.jpeg')`
                }}
            ></div>
            
            <div className="relative z-10 space-y-6">
                <h1 className="heading-2 text-white">MI PERFIL</h1>

                {/* Profile Card */}
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                            <div className="relative">
                                <Avatar className="w-20 h-20 border-2 border-[#FF671F]">
                                    <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.email}`} />
                                    <AvatarFallback className="text-2xl bg-[#FF671F] text-white">
                                        {user?.name?.charAt(0)?.toUpperCase()}
                                    </AvatarFallback>
                                </Avatar>
                                <Button 
                                    size="icon" 
                                    className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-[#222] border border-[#333] hover:bg-[#FF671F]"
                                >
                                    <Camera className="w-4 h-4 text-white" />
                                </Button>
                            </div>
                            <div className="flex-1">
                                <h2 className="heading-3 text-white">{user?.name?.toUpperCase()}</h2>
                                <p className="text-white/50 text-sm">{user?.email}</p>
                                {profile && (
                                    <div className="mt-2">
                                        <PlanBadge plan={profile.plan} />
                                    </div>
                                )}
                            </div>
                            <Button 
                                variant="ghost" 
                                size="icon"
                                className="text-white/50 hover:text-[#FF671F]"
                                onClick={() => setEditing(!editing)}
                            >
                                <Edit2 className="w-4 h-4" />
                            </Button>
                        </div>

                        {editing && (
                            <div className="mt-6 space-y-4">
                                <Separator className="bg-[#222]" />
                                <div className="grid gap-4">
                                    <div>
                                        <Label className="text-white/70">Nombre</Label>
                                        <Input
                                            value={formData.name}
                                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                            className="bg-[#0A0A0A] border-[#333] text-white"
                                        />
                                    </div>
                                    <div>
                                        <Label className="text-white/70">Teléfono</Label>
                                        <Input
                                            value={formData.phone}
                                            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                            placeholder="+34 612 345 678"
                                            className="bg-[#0A0A0A] border-[#333] text-white"
                                        />
                                    </div>
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <Button variant="outline" onClick={() => setEditing(false)} className="bg-transparent border-[#333] text-white hover:border-white/50">
                                        Cancelar
                                    </Button>
                                    <Button onClick={handleSave} disabled={saving} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white">
                                        {saving ? 'Guardando...' : 'Guardar'}
                                    </Button>
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
                                <span className="flex items-center gap-2 text-white uppercase tracking-wider">
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
                                        {profile.price}€
                                        <span className="text-sm font-normal text-white/50">/ciclo</span>
                                    </p>
                                </div>
                                <div>
                                    <p className="text-sm text-white/50 uppercase tracking-wider">Próxima renovación</p>
                                    <p className="font-semibold text-white">
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
                                            <div className="w-5 h-5 rounded bg-[#FF671F]/20 flex items-center justify-center">
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
                                    <TrendingUp className="w-4 h-4 mr-2" />
                                    Mejorar mi plan
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                )}

                {/* Settings */}
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-0">
                        <button 
                            className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                            onClick={() => toast.info('Funcionalidad próximamente')}
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                                    <CreditCard className="w-5 h-5 text-[#FF671F]" />
                                </div>
                                <div className="text-left">
                                    <p className="font-medium text-white">Método de pago</p>
                                    <p className="text-sm text-white/50">Gestionar tarjeta</p>
                                </div>
                            </div>
                            <ChevronRight className="w-5 h-5 text-white/30" />
                        </button>
                        
                        <Separator className="bg-[#222]" />
                        
                        <button 
                            className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                            onClick={() => toast.info('Funcionalidad próximamente')}
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                                    <Bell className="w-5 h-5 text-[#FF671F]" />
                                </div>
                                <div className="text-left">
                                    <p className="font-medium text-white">Notificaciones</p>
                                    <p className="text-sm text-white/50">Configurar alertas</p>
                                </div>
                            </div>
                            <ChevronRight className="w-5 h-5 text-white/30" />
                        </button>
                        
                        <Separator className="bg-[#222]" />
                        
                        <button 
                            className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                            onClick={() => toast.info('Funcionalidad próximamente')}
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-[#1A1A1A] rounded-lg flex items-center justify-center">
                                    <Lock className="w-5 h-5 text-[#FF671F]" />
                                </div>
                                <div className="text-left">
                                    <p className="font-medium text-white">Cambiar contraseña</p>
                                    <p className="text-sm text-white/50">Seguridad de la cuenta</p>
                                </div>
                            </div>
                            <ChevronRight className="w-5 h-5 text-white/30" />
                        </button>
                    </CardContent>
                </Card>

                {/* Logout */}
                <Button 
                    variant="outline" 
                    className="w-full bg-transparent border-red-500/50 text-red-500 hover:bg-red-500/10 hover:border-red-500 uppercase tracking-wider"
                    onClick={handleLogout}
                    data-testid="logout-btn"
                >
                    <LogOut className="w-4 h-4 mr-2" />
                    Cerrar sesión
                </Button>

                {/* Upgrade Dialog */}
                <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
                    <DialogContent className="bg-[#111111] border-[#333]">
                        <DialogHeader>
                            <DialogTitle className="text-white uppercase tracking-wider">Mejorar tu plan</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                            {profile?.plan !== 'gold' && (
                                <Card 
                                    className="bg-[#0A0A0A] border-[#333] cursor-pointer hover:border-yellow-500 transition-colors" 
                                    onClick={() => toast.info('Funcionalidad próximamente')}
                                >
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-600 text-black font-bold px-3 py-1 rounded text-sm uppercase">
                                                Gold
                                            </span>
                                            <span className="font-bold text-white text-xl" style={{ fontFamily: 'Bebas Neue' }}>149€/ciclo</span>
                                        </div>
                                        <p className="text-sm text-white/50">
                                            Incluye todo: rutina semanal, reporte quincenal, cardio, audio y suplementación.
                                        </p>
                                    </CardContent>
                                </Card>
                            )}
                            {(profile?.plan === 'bronze' || profile?.plan === 'elm') && (
                                <Card 
                                    className="bg-[#0A0A0A] border-[#333] cursor-pointer hover:border-gray-400 transition-colors" 
                                    onClick={() => toast.info('Funcionalidad próximamente')}
                                >
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="bg-gradient-to-r from-gray-300 via-gray-200 to-gray-400 text-black font-bold px-3 py-1 rounded text-sm uppercase">
                                                Silver
                                            </span>
                                            <span className="font-bold text-white text-xl" style={{ fontFamily: 'Bebas Neue' }}>99€/ciclo</span>
                                        </div>
                                        <p className="text-sm text-white/50">
                                            Rutina semanal, macros y chat con entrenador.
                                        </p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setShowUpgradeDialog(false)} className="bg-transparent border-[#333] text-white">
                                Cancelar
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default ProfilePage;
