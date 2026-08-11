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
import { queIncluyeElPlan } from '../lib/planAccess';
import {
    User, Mail,
    LogOut, Lock, ChevronRight, Crown,
    TrendingUp, Edit2, Camera, Check,
    Compass, SlidersHorizontal, Bot, Search, Pill, ClipboardCheck, MessageCircle,
    ChevronDown
} from 'lucide-react';

// "Mejorar mi plan" OCULTO (petición 2026-07-06): el checkout de upgrade no existe aún
// (pagos reales pospuestos). Poner a true cuando se habiliten pagos.
//
// OJO SI SE REACTIVA (punto 40 del doc del 07-08): el diálogo de abajo tiene el plan y el
// precio CABLEADOS -- "Gold, 149€/ciclo" -- y decide qué enseñar con `profile.plan !== 'gold'`.
// Ese Gold es el legacy, que desde el 31-07 ya no se contrata, y 149€ no es su precio (450-847
// según antigüedad, y de todos modos el que manda es el del contrato de cada cliente, punto
// 36). Antes de encenderlo hay que sacar las opciones del catálogo, como ya hacen la lista de
// clientes y la conversión de leads. Se queda escrito y apagado en vez de borrado porque el
// día que haya checkout de upgrade la maqueta sirve; el aviso es para que no se encienda tal
// cual y se le ofrezca a un cliente un plan que no existe a un precio que no es.
const UPGRADE_PLAN_UI = false;

const ProfilePage = () => {
    const navigate = useNavigate();
    const { user, profile, logout, api, refreshUser, myPlan, planUnpaid, can } = useAuth();
    const { startTour } = useOnboarding();
    const [editing, setEditing] = useState(false);
    const [verIncluye, setVerIncluye] = useState(false);
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

    // «Tu plan incluye»: el texto que escribió el equipo para su plan (punto 6.4) y, si no lo
    // hay, las líneas que se derivan de las habilitaciones, que es lo que había.
    const currentPlanFeatures = queIncluyeElPlan(myPlan);

    // SIN FECHA DE RENOVACIÓN NO SE ENSEÑA LA ETIQUETA.
    // Ponía «RENOVACIÓN · No definida», que es un hueco de la base de datos en la cara de
    // alguien que paga 149 €. Jesús, 11-08: «si hay fecha, se pone la fecha; si no la hay, no
    // se enseña la etiqueta». Callar dice menos que decir que no se sabe.
    const fechaDeRenovacion = profile?.renovacion?.fecha
        || profile?.renovacion?.proximo_cobro
        || profile?.next_payment
        || null;

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-background min-h-screen relative overflow-hidden">
            <div className="relative z-10 space-y-6 max-w-lg mx-auto">
                <h1 className="text-2xl font-bold text-foreground tracking-tight" style={{ fontFamily: 'Barlow Condensed' }} data-testid="profile-heading">MI PERFIL</h1>

                {/* Profile Card */}
                <Card className="bg-card border-border">
                    <CardContent className="p-6">
                        <div className="flex items-center gap-4">
                            <div className="relative">
                                {/* SU INICIAL, NO UN MUÑECO (punto 4.18). Salía un dibujo de
                                    mujer para todo el mundo: el avatar lo generaba
                                    api.dicebear.com a partir de una semilla, y el dibujo que
                                    toque es cosa suya.
                                    Y había algo peor que el dibujo: la semilla era EL CORREO
                                    DEL CLIENTE, así que cada vez que alguien abría su perfil
                                    se mandaba su dirección a un servicio de fuera. Para un
                                    avatar por defecto. Con la inicial no sale nada de aquí, no
                                    depende de que un tercero esté vivo y no hay que pedir
                                    permiso a nadie. */}
                                <Avatar className="w-16 h-16 border-2 border-[#FF671F]">
                                    <AvatarFallback className="text-xl bg-[#FF671F] text-white">
                                        {user?.name?.charAt(0)?.toUpperCase() || '?'}
                                    </AvatarFallback>
                                </Avatar>
                            </div>
                            {/* `min-w-0` y `truncate`, que si no el correo manda.
                                Un flex hijo no encoge por debajo de su contenido salvo que se
                                le diga, así que «clientedemo@test.com» fijaba el ancho de esta
                                columna y empujaba el lápiz de editar FUERA de la pantalla: a
                                320 px el botón no existía para el cliente. Medido el 10-08. */}
                            <div className="flex-1 min-w-0">
                                <h2 className="font-bold text-foreground text-lg truncate">{user?.name?.toUpperCase()}</h2>
                                <p className="text-foreground/50 text-sm truncate">{user?.email}</p>
                                {profile && <div className="mt-1"><PlanBadge plan={planUnpaid ? null : profile.plan} /></div>}
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

                {/* Checkout iniciado pero no pagado: ofrecer terminar la compra */}
                {profile && planUnpaid && (
                    <Card className="bg-card border-[#FF671F]/30">
                        <CardContent className="p-6 flex flex-col sm:flex-row sm:items-center gap-4">
                            <div className="flex-1">
                                <p className="font-bold text-foreground uppercase tracking-wider text-sm mb-1">Sin plan activo</p>
                                <p className="text-sm text-foreground/60">El pago de tu plan no llegó a completarse. Elige un plan para terminar la compra.</p>
                            </div>
                            <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider"
                                onClick={() => navigate('/onboarding')} data-testid="finish-checkout-btn">
                                Elegir plan
                            </Button>
                        </CardContent>
                    </Card>
                )}

                {/* Plan Info (un checkout sin pagar no cuenta como plan contratado) */}
                {profile && !planUnpaid && (
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
                                    {/* EL PRECIO LO RESUELVE EL SERVIDOR (punto 2.4c). Aquí se
                                        pintaba `profile.price` en crudo, y ese campo llegó a cero
                                        en los 168 perfiles que vinieron de Calma: a un cliente de
                                        pago, sin cortesía marcada, se le decía «0 €/ciclo». Y es
                                        lo primero que ve quien recibe acceso. */}
                                    <p className="text-3xl font-bold text-[#FF671F]" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {profile.precio_cortesia
                                            ? <>Cortesía</>
                                            : <>{profile.precio_ciclo ? `${profile.precio_ciclo}€` : '-'}<span className="text-sm font-normal text-foreground/50">/ciclo</span></>}
                                    </p>
                                    {profile.precio_cortesia && (
                                        <p className="text-xs text-foreground/50 mt-1">Tu plan no tiene cobro asociado.</p>
                                    )}
                                    {/* La nota de precio del catálogo (un rango general del plan) solo se
                                        muestra si el cliente no tiene un precio propio, para no dar dos cifras
                                        contradictorias (p.ej. "149€/ciclo" y "450-847€/trimestre"). */}
                                    {!profile.precio_cortesia && !profile.precio_ciclo && myPlan?.precio_nota && (
                                        <p className="text-xs text-foreground/50 mt-1">{myPlan.precio_nota}</p>
                                    )}
                                </div>
                                {/* Punto 2.4d: aquí ponía «No definida» a un cliente cuya
                                    membresía había vencido una semana antes, porque solo miraba
                                    `next_payment` -- el próximo COBRO --, y los migrados de
                                    Calma no tienen ninguno. Ahora se dice lo que se sabe, si ya
                                    pasó se dice que pasó, y si no hay fecha no se enseña nada.
                                    «Próxima renovación» ocupa dos líneas en 390 px y descuadra
                                    la columna frente al precio: en el teléfono, «Renovación». */}
                                {fechaDeRenovacion && (
                                    <div>
                                        <p className="text-sm text-foreground/50 uppercase tracking-wider">
                                            {profile.renovacion?.vencida ? 'Tu plan venció' : (
                                                <>
                                                    <span className="lg:hidden">Renovación</span>
                                                    <span className="hidden lg:inline">Próxima renovación</span>
                                                </>
                                            )}
                                        </p>
                                        <p className={`font-semibold text-sm ${profile.renovacion?.vencida ? 'text-amber-500' : 'text-foreground'}`}
                                            data-testid="perfil-renovacion">
                                            {new Date(fechaDeRenovacion).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                                        </p>
                                    </div>
                                )}
                            </div>
                            <Separator className="bg-white/10" />
                            <div>
                                {/* LO QUE INCLUYE EL PLAN, EN EL TELÉFONO DETRÁS DE UNA LÍNEA.
                                    Son seis líneas fijas que no cambian nunca y que se leen una
                                    vez, el día que se contrata: 250 px de los 1.742 de esta
                                    pantalla ocupados por algo que ya se sabe. En escritorio se
                                    quedan a la vista, que ahí no estorban. */}
                                <button type="button" onClick={() => setVerIncluye(v => !v)}
                                    data-testid="ver-que-incluye"
                                    className="lg:hidden w-full flex items-center justify-between text-left">
                                    <span className="text-base font-bold text-foreground uppercase tracking-wider">Tu plan incluye</span>
                                    <ChevronDown className={`w-5 h-5 text-foreground/40 transition-transform ${verIncluye ? 'rotate-180' : ''}`} />
                                </button>
                                <p className="hidden lg:block text-sm font-bold text-foreground uppercase tracking-wider mb-3">Tu plan incluye:</p>
                                <ul className={`space-y-2 lg:block ${verIncluye ? 'mt-3' : 'hidden'}`}>
                                    {currentPlanFeatures.map((feature, index) => (
                                        <li key={index} className="flex items-center gap-2 text-[15px] lg:text-sm text-foreground/80">
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

                {/* TODO LO DEMÁS, CON SU NOMBRE.
                    La barra de abajo bajó a cuatro (Inicio · Nutrición · Seguimiento ·
                    Perfil) y de Inicio se fueron los ocho accesos rápidos. Lo que dejó de
                    tener puerta aterriza aquí, que es donde el propio documento pone «Mis
                    macros»: «de la pestaña Perfil, abajo a la derecha».
                    Cada entrada respeta las capacidades del plan, igual que antes: al que
                    no tiene suplementación no se le enseña Suplementos, y al plan sin
                    entrenador no se le enseña el Chat. */}
                <Card className="bg-card border-border lg:hidden">
                    <CardContent className="p-0">
                        {[
                            { icon: SlidersHorizontal, title: 'Mis macros', sub: 'Tus números y por qué son esos', path: '/dashboard/macro-calculator' },
                            { icon: Bot, title: 'Asistente IA', sub: 'Monta la comida hablando', path: '/dashboard/chatbot' },
                            { icon: Search, title: 'Alimentos', sub: 'Buscador del catálogo', path: '/dashboard/foods' },
                            can('suplementacion') && { icon: Pill, title: 'Suplementos', sub: 'Tu protocolo', path: '/dashboard/supplements' },
                            // Aquí había una fila de «Check-ins». Se va: desde el 10-08 la
                            // puerta de eso es Seguimiento, que está en la barra de abajo, y
                            // dentro tiene su tarjeta de «Hoy». Dos puertas a lo mismo, una de
                            // ellas con el nombre viejo, es justo lo que había que quitar.
                            can('chat') && { icon: MessageCircle, title: 'Chat', sub: 'Escríbenos cuando quieras', path: '/dashboard/messages' },
                        ].filter(Boolean).map((item, i) => (
                            <React.Fragment key={item.title}>
                                {i > 0 && <Separator className="bg-border" />}
                                <button
                                    className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
                                    onClick={() => navigate(item.path)}
                                    data-testid={`ir-a-${item.path.split('/').pop()}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                            <item.icon className="w-5 h-5 text-[#FF671F]" />
                                        </div>
                                        <div className="text-left">
                                            {/* En el teléfono el texto sube un escalón: estas
                                                filas son ahora la puerta de media app y se leían
                                                en 14 y 12 px. En escritorio se quedan igual. */}
                                            <p className="font-medium text-foreground text-base lg:text-sm">{item.title}</p>
                                            <p className="text-sm lg:text-xs text-foreground/50">{item.sub}</p>
                                        </div>
                                    </div>
                                    <ChevronRight className="w-5 h-5 text-foreground/30" />
                                </button>
                            </React.Fragment>
                        ))}
                    </CardContent>
                </Card>

                {/* Settings */}
                <Card className="bg-card border-border">
                    <CardContent className="p-0">
                        {[
                            { icon: Lock, title: 'Cambiar contraseña', sub: 'Seguridad de la cuenta', onClick: () => setShowPasswordDialog(true) },
                            // El recorrido guiado era un botón suelto de ancho completo debajo,
                            // con el mismo peso visual que «Cerrar sesión». Es una fila más de
                            // ajustes, y aquí se lee mejor. En escritorio sigue siendo el botón
                            // de siempre, que es donde estaba.
                            { icon: Compass, title: 'Repetir recorrido guiado', sub: 'Te volvemos a enseñar la app', soloMovil: true,
                                onClick: () => { navigate('/dashboard'); startTour(); } },
                        ].map((item, i) => (
                            <React.Fragment key={item.title}>
                                {i > 0 && <Separator className={`bg-border ${item.soloMovil ? 'lg:hidden' : ''}`} />}
                                <button
                                    className={`w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors ${item.soloMovil ? 'lg:hidden' : ''}`}
                                    onClick={item.onClick}
                                    data-testid={`setting-${i}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                                            <item.icon className="w-5 h-5 text-[#FF671F]" />
                                        </div>
                                        <div className="text-left">
                                            {/* En el teléfono el texto sube un escalón: estas
                                                filas son ahora la puerta de media app y se leían
                                                en 14 y 12 px. En escritorio se quedan igual. */}
                                            <p className="font-medium text-foreground text-base lg:text-sm">{item.title}</p>
                                            <p className="text-sm lg:text-xs text-foreground/50">{item.sub}</p>
                                        </div>
                                    </div>
                                    <ChevronRight className="w-5 h-5 text-foreground/30" />
                                </button>
                            </React.Fragment>
                        ))}
                    </CardContent>
                </Card>

                {/* Repetir recorrido guiado. En el teléfono es una fila más de la tarjeta de
                    arriba; aquí se queda para escritorio, tal cual estaba. */}
                <Button
                    variant="outline"
                    className="hidden lg:inline-flex w-full bg-transparent border-brand/40 text-brand hover:bg-brand/10 hover:border-brand uppercase tracking-wider"
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
