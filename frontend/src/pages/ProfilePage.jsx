import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Separator } from '../components/ui/separator';
import { Switch } from '../components/ui/switch';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { PlanBadge } from './ClientDashboard';
import { 
    User, Mail, Phone, CreditCard, Calendar, 
    LogOut, Bell, Lock, ChevronRight, Crown, 
    TrendingUp, Shield, Edit2, Camera
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
    const { user, profile, logout, api, updateProfile } = useAuth();
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
            // Update user profile (in a real app, this would be an API call)
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
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in space-y-6">
            <h1 className="heading-2">Mi Perfil</h1>

            {/* Profile Card */}
            <Card>
                <CardContent className="p-6">
                    <div className="flex items-center gap-4">
                        <div className="relative">
                            <Avatar className="w-20 h-20">
                                <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.email}`} />
                                <AvatarFallback className="text-2xl">
                                    {user?.name?.charAt(0)?.toUpperCase()}
                                </AvatarFallback>
                            </Avatar>
                            <Button 
                                size="icon" 
                                variant="secondary"
                                className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full"
                            >
                                <Camera className="w-4 h-4" />
                            </Button>
                        </div>
                        <div className="flex-1">
                            <h2 className="heading-3">{user?.name}</h2>
                            <p className="text-muted-foreground text-sm">{user?.email}</p>
                            {profile && (
                                <div className="mt-2">
                                    <PlanBadge plan={profile.plan} />
                                </div>
                            )}
                        </div>
                        <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => setEditing(!editing)}
                        >
                            <Edit2 className="w-4 h-4" />
                        </Button>
                    </div>

                    {editing && (
                        <div className="mt-6 space-y-4">
                            <Separator />
                            <div className="grid gap-4">
                                <div>
                                    <Label>Nombre</Label>
                                    <Input
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <Label>Teléfono</Label>
                                    <Input
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        placeholder="+34 612 345 678"
                                    />
                                </div>
                            </div>
                            <div className="flex gap-2 justify-end">
                                <Button variant="outline" onClick={() => setEditing(false)}>
                                    Cancelar
                                </Button>
                                <Button onClick={handleSave} disabled={saving}>
                                    {saving ? 'Guardando...' : 'Guardar'}
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Plan Info */}
            {profile && (
                <Card className="bg-gradient-to-br from-primary/5 to-secondary/5 border-primary/20">
                    <CardHeader className="pb-2">
                        <CardTitle className="flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <Crown className="w-5 h-5 text-primary" />
                                Mi Plan
                            </span>
                            <PlanBadge plan={profile.plan} />
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-sm text-muted-foreground">Precio</p>
                                <p className="text-2xl font-bold">{profile.price}€<span className="text-sm font-normal text-muted-foreground">/ciclo</span></p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Próxima renovación</p>
                                <p className="font-semibold">
                                    {profile.next_payment 
                                        ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })
                                        : 'No definida'}
                                </p>
                            </div>
                        </div>

                        <Separator />

                        <div>
                            <p className="text-sm font-semibold mb-2">Tu plan incluye:</p>
                            <ul className="space-y-2">
                                {currentPlanFeatures.map((feature, index) => (
                                    <li key={index} className="flex items-center gap-2 text-sm">
                                        <div className="w-5 h-5 rounded-full bg-secondary/20 flex items-center justify-center">
                                            <span className="text-secondary text-xs">✓</span>
                                        </div>
                                        {feature}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        {profile.plan !== 'gold' && (
                            <Button 
                                className="w-full btn-secondary"
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
            <Card>
                <CardContent className="p-0">
                    <button 
                        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                        onClick={() => toast.info('Funcionalidad próximamente')}
                    >
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                <CreditCard className="w-5 h-5" />
                            </div>
                            <div className="text-left">
                                <p className="font-medium">Método de pago</p>
                                <p className="text-sm text-muted-foreground">Gestionar tarjeta</p>
                            </div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    </button>
                    
                    <Separator />
                    
                    <button 
                        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                        onClick={() => toast.info('Funcionalidad próximamente')}
                    >
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                <Bell className="w-5 h-5" />
                            </div>
                            <div className="text-left">
                                <p className="font-medium">Notificaciones</p>
                                <p className="text-sm text-muted-foreground">Configurar alertas</p>
                            </div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    </button>
                    
                    <Separator />
                    
                    <button 
                        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                        onClick={() => toast.info('Funcionalidad próximamente')}
                    >
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                <Lock className="w-5 h-5" />
                            </div>
                            <div className="text-left">
                                <p className="font-medium">Cambiar contraseña</p>
                                <p className="text-sm text-muted-foreground">Seguridad de la cuenta</p>
                            </div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    </button>
                </CardContent>
            </Card>

            {/* Logout */}
            <Button 
                variant="outline" 
                className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={handleLogout}
                data-testid="logout-btn"
            >
                <LogOut className="w-4 h-4 mr-2" />
                Cerrar sesión
            </Button>

            {/* Upgrade Dialog */}
            <Dialog open={showUpgradeDialog} onOpenChange={setShowUpgradeDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Mejorar tu plan</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        {profile?.plan !== 'gold' && (
                            <Card className="cursor-pointer hover:border-yellow-500 transition-colors" onClick={() => toast.info('Funcionalidad próximamente')}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="badge-gold">GOLD</span>
                                        <span className="font-bold">149€/ciclo</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        Incluye todo: rutina semanal, reporte quincenal, cardio, audio y suplementación.
                                    </p>
                                </CardContent>
                            </Card>
                        )}
                        {(profile?.plan === 'bronze' || profile?.plan === 'elm') && (
                            <Card className="cursor-pointer hover:border-gray-500 transition-colors" onClick={() => toast.info('Funcionalidad próximamente')}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="badge-silver">SILVER</span>
                                        <span className="font-bold">99€/ciclo</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        Rutina semanal, macros y chat con entrenador.
                                    </p>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowUpgradeDialog(false)}>
                            Cancelar
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default ProfilePage;
