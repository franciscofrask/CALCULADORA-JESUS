import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
import { fraseDeLoQueFalta } from '../lib/datosDudosos';
import { useConfirm } from '../components/ui/confirm';
import {
    User, Mail,
    LogOut, Lock, ChevronRight, Crown,
    TrendingUp, Edit2, Camera, Check,
    Compass, SlidersHorizontal, Bot, Search, Pill, ClipboardCheck, MessageCircle,
    ChevronDown, Bell
} from 'lucide-react';
import { mensajeDeError } from '../lib/mensajeDeError';

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

// Los cuatro grupos de «Avisos y recordatorios» (doc «El día», 31-08). Un rótulo pequeño y
// sus filas debajo: siete interruptores seguidos, sin agrupar, se leen como una lista de la
// compra y no como cuatro decisiones distintas.
const GrupoDeAvisos = ({ titulo, children }) => (
    <div>
        <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/40 mb-1">{titulo}</p>
        <div className="divide-y divide-border">{children}</div>
    </div>
);

// Una fila con su interruptor. A nivel de módulo y no dentro de la pantalla por lo de
// siempre: definida dentro, cada render crea un componente nuevo y React remonta la fila en
// vez de actualizarla.
const FilaDeAviso = ({ titulo, ayuda, valor, guardando, onCambiar, testId }) => (
    <div className="flex items-center justify-between gap-4 py-2.5">
        <div className="min-w-0">
            <p className="text-base lg:text-sm text-foreground">{titulo}</p>
            {ayuda && <p className="text-sm lg:text-xs text-foreground/50 mt-0.5">{ayuda}</p>}
        </div>
        <button
            type="button"
            role="switch"
            aria-checked={!!valor}
            aria-label={titulo}
            disabled={guardando}
            onClick={() => onCambiar(!valor)}
            data-testid={testId}
            className={`relative w-12 h-7 rounded-full transition-colors shrink-0 disabled:opacity-50 ${valor ? 'bg-[#FF671F]' : 'bg-muted'}`}
        >
            <span className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-all ${valor ? 'left-6' : 'left-1'}`} />
        </button>
    </div>
);

const ProfilePage = () => {
    const navigate = useNavigate();
    const { user, profile, logout, api, refreshUser, refreshProfile, myPlan, planUnpaid, can, planCatalog, pantalla } = useAuth();
    const { startTour, available: recorridoDisponible } = useOnboarding();
    const [editing, setEditing] = useState(false);
    const [verIncluye, setVerIncluye] = useState(false);
    const [showUpgradeDialog, setShowUpgradeDialog] = useState(false);
    // La baja (P56 del doc 23-08): antes era un clic y fuera, sin pregunta ni alternativa.
    // Ahora cada motivo tiene su salida, y el equipo se entera al momento.
    const [bajaAbierta, setBajaAbierta] = useState(false);
    const [motivoBaja, setMotivoBaja] = useState('');
    const [detalleBaja, setDetalleBaja] = useState('');
    const [pidiendoBaja, setPidiendoBaja] = useState(null);   // qué salida está en vuelo

    // El precio de Mantenimiento sale del catálogo, no de un número escrito aquí.
    const mantenimiento = planCatalog?.mantenimiento;

    // Registra la intención (motivo + salida) y avisa al equipo al momento. `salida`:
    // 'baja' (se va de verdad), 'mantenimiento' (sigue barato), 'aplazar' (le escribimos),
    // 'revision' (su entrenador le revisa el plan antes de irse).
    const responderBaja = async (salida) => {
        setPidiendoBaja(salida);
        try {
            const r = await api.post('/billing/no-renovar', {
                motivo: motivoBaja,
                detalle: detalleBaja.trim() || undefined,
                salida,
            });
            if (salida === 'mantenimiento') {
                // La intención ya está registrada; de aquí, directo al pago del plan barato.
                const c = await api.post('/billing/checkout-session', {
                    plan: 'mantenimiento',
                    success_path: '/dashboard?renovado=ok',
                    cancel_path: '/dashboard/profile',
                });
                if (c.data?.checkout_url) { window.location.href = c.data.checkout_url; return; }
            }
            toast.success(r.data?.mensaje || 'Hecho. Sigues teniendo acceso hasta el final de tu ciclo.');
            setBajaAbierta(false);
            setMotivoBaja('');
            setDetalleBaja('');
            refreshProfile();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo registrar. Inténtalo en un momento.'));
        } finally {
            setPidiendoBaja(null);
        }
    };
    const [formData, setFormData] = useState({
        name: user?.name || '', phone: user?.phone || '',
        email_contacto: profile?.email_contacto || '',
        email_preferido: profile?.email_preferido || 'contacto',
    });
    const [saving, setSaving] = useState(false);

    // El perfil llega después que el usuario (son dos peticiones), así que los dos correos se
    // siembran cuando aparece. Sin esto, abrir «editar» antes de que cargue enseñaba el campo
    // vacío y guardarlo le borraba el correo de contacto.
    useEffect(() => {
        if (!profile) return;
        setFormData(f => ({
            ...f,
            email_contacto: f.email_contacto || profile.email_contacto || '',
            email_preferido: f.email_preferido || profile.email_preferido || 'contacto',
        }));
    }, [profile]);

    const handleSave = async () => {
        if (!formData.name.trim()) { toast.error('El nombre no puede estar vacío'); return; }
        const contacto = (formData.email_contacto || '').trim().toLowerCase();
        if (contacto && !/\S+@\S+\.\S+/.test(contacto)) {
            toast.error('Ese email de contacto no parece un email'); return;
        }
        setSaving(true);
        try {
            await api.put('/auth/me', { name: formData.name.trim(), phone: formData.phone });
            // Los dos correos viven en el perfil del cliente, no en la cuenta: el de la
            // cuenta es el de acceso y no se toca desde aquí.
            await api.put('/clients/profile', {
                email_contacto: contacto || null,
                email_preferido: contacto ? (formData.email_preferido || 'contacto') : 'acceso',
            });
            await refreshUser();
            if (refreshProfile) await refreshProfile();
            toast.success('Perfil actualizado');
            setEditing(false);
        } catch (error) {
            toast.error(mensajeDeError(error, 'Error al actualizar el perfil'));
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
            toast.error(mensajeDeError(error, 'Error al cambiar la contraseña'));
        } finally {
            setChangingPwd(false);
        }
    };

    // Preferencias de avisos. El fallo se traga a propósito: no poder leerlas no es algo
    // que el cliente tenga que arreglar, y la fila simplemente no aparece.
    const { confirm } = useConfirm();
    const [prefAvisos, setPrefAvisos] = useState(null);
    const [guardandoPref, setGuardandoPref] = useState(false);
    useEffect(() => {
        let vivo = true;
        api.get('/notifications/preferencias')
            .then(({ data }) => { if (vivo) setPrefAvisos(data); })
            .catch((e) => console.warn('No se han podido leer las preferencias de avisos', e));
        return () => { vivo = false; };
    }, [api]);

    // Vale para los siete y para la hora (doc «El día», 31-08). Responde al toque y no al
    // servidor: si el guardado falla, vuelve a como estaba y se dice.
    const guardarPref = async (cambio) => {
        const antes = prefAvisos;
        setPrefAvisos({ ...prefAvisos, ...cambio });
        setGuardandoPref(true);
        try {
            const { data } = await api.put('/notifications/preferencias', cambio);
            setPrefAvisos(data);
        } catch (error) {
            setPrefAvisos(antes);
            console.error('Error al guardar la preferencia de avisos', error);
            toast.error('No se ha podido guardar. Inténtalo otra vez.');
        } finally {
            setGuardandoPref(false);
        }
    };

    // APAGAR EL CIERRE DEL DÍA SE PREGUNTA ANTES (doc «El día», 31-08). «Al apagarlo hay que
    // decirle lo que se lleva, porque si no parece gratis.» El texto es suyo, literal.
    //
    // Y la segunda línea no es adorno: «sin ella el interruptor parece una puerta de un solo
    // sentido, y hay gente que no lo toca por miedo a no poder deshacerlo».
    //
    // Encenderlo NO pregunta: volver atrás no le quita nada.
    const cambiarCierreDelDia = async (valor) => {
        if (!valor && !await confirm({
            title: 'Rellenar el cierre del día',
            description: 'Si lo apagas, no podrás registrar tus datos del día, pero deberás '
                + 'rellenar las preguntas del reporte quincenal y del reporte mensual para '
                + 'poder recibir tus ajustes.\n\nPuedes volver a activarlo cuando quieras.',
            confirmLabel: 'Apagarlo',
            cancelLabel: 'Dejarlo como está',
        })) return;
        await guardarPref({ cierre_dia: valor });
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
    //
    // Y SOLO LAS FECHAS QUE EL SERVIDOR DA POR BUENAS (P50 del doc 23-08): `renovacion.*`
    // llega ya filtrado (una «renovación» a años vista es una membresía importada de Calma,
    // no una renovación). El `next_payment` crudo del perfil ya no entra en la cascada,
    // porque era justo por donde se colaba el «1 de febrero de 2030».
    const fechaDeRenovacion = profile?.renovacion?.fecha
        || profile?.renovacion?.proximo_cobro
        || null;

    // La fecha se pinta como dia LOCAL, no pasando el ISO a new Date(): '2026-09-22' se
    // interpreta como medianoche UTC y en husos por detras de Greenwich salia «21 de
    // septiembre», un dia antes del real (regla de la casa: el dia es el del navegador).
    const pintaFecha = (iso, opciones) => {
        const [a, m, d] = String(iso).slice(0, 10).split('-').map(Number);
        if (!a || !m || !d) return '';
        return new Date(a, m - 1, d).toLocaleDateString('es-ES', opciones);
    };

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-background min-h-screen relative overflow-hidden">
            <div className="relative z-10 space-y-6 max-w-lg mx-auto">
                <h1 className="text-2xl font-bold text-foreground tracking-tight" style={{ fontFamily: 'Barlow Condensed' }} data-testid="profile-heading">MI PERFIL</h1>

                {/* LOS DATOS QUE FALTAN O QUE NO PUEDEN SER, AQUÍ (punto 111 del artifact
                    del 25-08). Esto vivía en la pantalla de Nutrición, encima de las
                    comidas, y ocupaba tres líneas: «es un problema de ficha metido en la
                    pantalla de comer». Aquí es donde se arregla, así que aquí se dice; en
                    el menú queda un punto naranja para que se vea sin entrar.

                    No se recalcula nada ni se cambia ningún número: los macros siguen
                    siendo los suyos, solo que salieron de un perfil con huecos o con datos
                    imposibles (edad 5, estatura de 1 cm de la importación de Calma). */}
                {(profile?.datos_dudosos || []).length > 0 && (
                    <div className="rounded-xl border border-pasado/40 bg-pasado/5 px-4 py-3"
                        data-testid="macros-provisionales">
                        <p className="text-sm text-foreground">
                            <span className="font-bold text-pasado">Macros provisionales</span>{' '}
                            {fraseDeLoQueFalta(profile.datos_dudosos)}
                        </p>
                        <Link to="/questionnaire?completar=1"
                            className="inline-block mt-2 text-sm font-bold text-pasado underline">
                            Completar mis datos
                        </Link>
                    </div>
                )}

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
                                    {/* LOS DOS CORREOS. El de acceso es con el que entra y con el que
                                        cruzan sus pagos: ese no se cambia desde aquí. El otro es el que
                                        dio en el alta, y en esa pantalla se le prometió que le
                                        escribiríamos ahí «salvo que nos digas lo contrario». Esto es
                                        decirlo. */}
                                    <div>
                                        <Label className="text-foreground/70 text-xs uppercase tracking-wider">Email de contacto</Label>
                                        <Input type="email" value={formData.email_contacto}
                                            onChange={(e) => setFormData({ ...formData, email_contacto: e.target.value })}
                                            placeholder="Uno que revises a diario"
                                            data-testid="email-contacto"
                                            className="bg-background border-input text-foreground mt-1" />
                                        <p className="text-foreground/40 text-xs mt-1.5">
                                            Entras siempre con <b className="text-foreground/60">{user?.email}</b>, y ahí
                                            te llega el enlace si olvidas la contraseña. Eso no cambia.
                                        </p>
                                    </div>
                                    {formData.email_contacto?.trim() && (
                                        <div>
                                            <Label className="text-foreground/70 text-xs uppercase tracking-wider">¿A cuál te escribimos?</Label>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1.5">
                                                {[['contacto', formData.email_contacto], ['acceso', user?.email]].map(([cual, dir]) => (
                                                    <button key={cual} type="button"
                                                        data-testid={`email-preferido-${cual}`}
                                                        onClick={() => setFormData({ ...formData, email_preferido: cual })}
                                                        className={`px-3 py-2 rounded-xl border-2 text-sm text-left truncate transition-all ${
                                                            (formData.email_preferido || 'contacto') === cual
                                                                ? 'border-[#FF671F] bg-[#FF671F]/10 text-foreground'
                                                                : 'border-input text-foreground/70 hover:border-white/30'}`}>
                                                        {dir}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <Button variant="outline" onClick={() => setEditing(false)} className="bg-transparent border-input text-foreground hover:border-white/50 text-sm">Cancelar</Button>
                                    <Button onClick={handleSave} disabled={saving} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm">{saving ? 'Guardando...' : 'Guardar'}</Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* SIN PLAN: checkout a medias O cuenta recién creada que volvió atrás
                    desde /planes (bug del 20-08: no tenía ningún camino para volver a
                    verlos). La misma tarjeta para los dos, con el texto de su caso. */}
                {profile && (planUnpaid || !profile.plan) && (
                    <Card className="bg-card border-[#FF671F]/30">
                        <CardContent className="p-6 flex flex-col sm:flex-row sm:items-center gap-4">
                            <div className="flex-1">
                                <p className="font-bold text-foreground uppercase tracking-wider text-sm mb-1">Sin plan activo</p>
                                <p className="text-sm text-foreground/60">
                                    {planUnpaid
                                        ? 'El pago de tu plan no llegó a completarse. Elige un plan para terminar la compra.'
                                        : 'Todavía no tienes plan. Mira los planes y elige el tuyo para desbloquear la app entera.'}
                                </p>
                            </div>
                            <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider"
                                onClick={() => navigate('/planes')} data-testid="finish-checkout-btn">
                                {planUnpaid ? 'Elegir plan' : 'Ver los planes'}
                            </Button>
                        </CardContent>
                    </Card>
                )}

                {/* Plan Info. Sin plan no hay tarjeta de plan: aquí vivía el bug del
                    «No quiero renovar» saliéndole a quien no tiene nada que renovar. */}
                {profile && !planUnpaid && profile.plan && (
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
                                            : <>{profile.precio_ciclo ? `${profile.precio_ciclo}€` : '-'}<span className="text-sm font-normal text-foreground/50">
                                                {/* «/mes» o «/ciclo» lo dice el catálogo por el
                                                    ciclo del plan (P51): El Lunes Empiezo y
                                                    Mantenimiento son mensuales y aquí salían
                                                    como «/ciclo». */}
                                                /{profile.precio_periodo === 'mes' ? 'mes' : 'ciclo'}</span></>}
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
                                            {pintaFecha(fechaDeRenovacion, { day: 'numeric', month: 'long', year: 'numeric' })}
                                        </p>
                                    </div>
                                )}
                            </div>
                            {/* «Estás en la semana 7» (la pantalla Mi plan del doc 19-08).
                                LAS DOS MITADES DE LA FRASE, DEL MISMO SITIO (24-08). El «de
                                12» salía del catálogo (`myPlan`) y la semana la cuenta el
                                servidor con core/cycle, que busca el plan sin resolver
                                alias: a un perfil migrado escrito «CalMa» no le encontraba
                                el ciclo, así que la semana crecía sin dar la vuelta y aquí
                                se leía «Estás en la semana 63 de 12». `cycle_total_weeks`
                                es el total con el que se calculó ESA semana, así que los dos
                                números no pueden contradecirse. */}
                            {profile.week && (
                                <p className="text-sm text-foreground/60" data-testid="perfil-semana">
                                    Estás en la semana {profile.week}
                                    {profile.cycle_total_weeks ? ` de ${profile.cycle_total_weeks}` : ''}
                                </p>
                            )}
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

                            {/* EL «NO QUIERO RENOVAR» (doc 19-08, «Mi plan y la baja»):
                                «abajo, en pequeño y sin botón naranja. No se esconde, pero
                                tampoco se invita.» Hoy el cliente no tenía por dónde darse
                                de baja: solo existía el botón del equipo en el panel. */}
                            {!profile.no_renovar ? (
                                <p className="text-center pt-1">
                                    <button type="button" onClick={() => setBajaAbierta(true)}
                                        data-testid="no-quiero-renovar"
                                        className="text-xs text-foreground/40 hover:text-foreground/70 underline underline-offset-2">
                                        No quiero renovar
                                    </button>
                                </p>
                            ) : (
                                <p className="text-xs text-foreground/50 text-center pt-1" data-testid="baja-pedida">
                                    Ya nos dijiste que no quieres renovar: no se te vuelve a cobrar y
                                    tienes acceso hasta el final de tu ciclo.
                                </p>
                            )}
                        </CardContent>
                    </Card>
                )}

                {/* LA BAJA CON SUS CUATRO MOTIVOS Y UNA SALIDA PARA CADA UNO (P56 del doc
                    23-08). Antes era un clic y fuera: sin pregunta, sin alternativa y sin
                    que el equipo se enterase. Ahora el motivo abre su salida (Mantenimiento
                    si es caro, aplazar si no hay tiempo, revisión del plan si no ve
                    resultados, texto libre si es otra cosa) y TODO lo que se confirme queda
                    registrado y avisa al equipo al momento. */}
                <Dialog open={bajaAbierta} onOpenChange={(o) => { setBajaAbierta(o); if (!o) { setMotivoBaja(''); setDetalleBaja(''); } }}>
                    <DialogContent className="bg-card border-border max-w-md">
                        <DialogHeader>
                            <DialogTitle className="text-foreground">¿Por qué no quieres renovar?</DialogTitle>
                        </DialogHeader>
                        <p className="text-sm text-muted-foreground -mt-1">
                            Pase lo que pase, sigues teniendo acceso hasta el final de tu ciclo
                            {fechaDeRenovacion ? ` (el ${pintaFecha(fechaDeRenovacion, { day: 'numeric', month: 'long' })})` : ''}.
                        </p>
                        <div className="space-y-2">
                            {[['caro', 'Es caro'],
                              ['sin_tiempo', 'No tengo tiempo ahora'],
                              ['sin_resultados', 'No estoy viendo resultados'],
                              ['otra', 'Otra cosa']].map(([clave, texto]) => (
                                <button key={clave} type="button"
                                    onClick={() => { setMotivoBaja(clave); setDetalleBaja(''); }}
                                    data-testid={`baja-motivo-${clave}`}
                                    className={`w-full text-left px-4 py-2.5 rounded-lg border text-sm transition-colors ${
                                        motivoBaja === clave
                                            ? 'border-[#FF671F] bg-[#FF671F]/10 text-foreground'
                                            : 'border-border text-foreground/70 hover:border-foreground/30'}`}>
                                    {texto}
                                </button>
                            ))}
                        </div>

                        {/* La salida de cada motivo. */}
                        {motivoBaja === 'caro' && (
                            <div className="rounded-lg border border-[#FF671F]/30 bg-[#FF671F]/5 p-4 space-y-3" data-testid="baja-salida-caro">
                                <p className="text-sm text-foreground/80">
                                    Antes de irte: tienes <b>Mantenimiento</b>
                                    {mantenimiento?.precio ? <> por <b>{Math.round(mantenimiento.precio)} €/mes</b></> : null}.
                                    Te quedas con la app, tus números y tus datos, y puedes volver
                                    al programa cuando quieras.
                                </p>
                                <Button onClick={() => responderBaja('mantenimiento')} disabled={!!pidiendoBaja}
                                    data-testid="baja-salida-mantenimiento"
                                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold">
                                    {pidiendoBaja === 'mantenimiento' ? 'Un momento…' : 'Pasarme a Mantenimiento'}
                                </Button>
                            </div>
                        )}
                        {motivoBaja === 'sin_tiempo' && (
                            <div className="rounded-lg border border-[#FF671F]/30 bg-[#FF671F]/5 p-4 space-y-3" data-testid="baja-salida-sin-tiempo">
                                <p className="text-sm text-foreground/80">
                                    No hace falta decidirlo hoy. Lo aplazamos, te escribimos
                                    nosotros en unos días y lo ves con calma.
                                </p>
                                <Button onClick={() => responderBaja('aplazar')} disabled={!!pidiendoBaja}
                                    data-testid="baja-salida-aplazar"
                                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold">
                                    {pidiendoBaja === 'aplazar' ? 'Un momento…' : 'Aplazarlo, escribidme'}
                                </Button>
                            </div>
                        )}
                        {motivoBaja === 'sin_resultados' && (
                            <div className="rounded-lg border border-[#FF671F]/30 bg-[#FF671F]/5 p-4 space-y-3" data-testid="baja-salida-sin-resultados">
                                <p className="text-sm text-foreground/80">
                                    Antes de irte, {profile?.entrenador?.nombre ? 'tu entrenador' : 'el equipo'} puede
                                    revisar tu plan y proponerte cambios. Le avisamos ahora mismo.
                                </p>
                                <Button onClick={() => responderBaja('revision')} disabled={!!pidiendoBaja}
                                    data-testid="baja-salida-revision"
                                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold">
                                    {pidiendoBaja === 'revision' ? 'Un momento…' : 'Que revisen mi plan'}
                                </Button>
                            </div>
                        )}
                        {motivoBaja === 'otra' && (
                            <div className="space-y-2" data-testid="baja-salida-otra">
                                <Label className="text-foreground/70 text-xs uppercase tracking-wider">Cuéntanos qué pasa</Label>
                                <textarea value={detalleBaja} onChange={(e) => setDetalleBaja(e.target.value)}
                                    rows={3} maxLength={500}
                                    data-testid="baja-detalle"
                                    placeholder="Con tus palabras: nos llega al equipo tal cual"
                                    className="w-full rounded-lg bg-background border border-input text-foreground text-sm p-3 resize-none focus:outline-none focus:border-[#FF671F]" />
                            </div>
                        )}

                        <DialogFooter>
                            <Button onClick={() => responderBaja('baja')}
                                disabled={!motivoBaja || !!pidiendoBaja || (motivoBaja === 'otra' && !detalleBaja.trim())}
                                data-testid="baja-confirmar"
                                variant={motivoBaja && motivoBaja !== 'otra' ? 'outline' : 'default'}
                                className={motivoBaja && motivoBaja !== 'otra'
                                    ? 'bg-transparent border-input text-foreground/70 hover:text-foreground'
                                    : 'bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold'}>
                                {pidiendoBaja === 'baja' ? 'Un momento…'
                                    : motivoBaja && motivoBaja !== 'otra' ? 'Seguir con la baja' : 'Confirmar la baja'}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

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
                            // El asistente solo si su interruptor está encendido, y nace
                            // apagado (Francisco, 26-08). Ver ClientDashboard.
                            pantalla('t7_asistente') && { icon: Bot, title: 'Asistente IA', sub: 'Monta la comida hablando', path: '/dashboard/chatbot' },
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

                {/* AVISOS Y RECORDATORIOS (doc «El día», 31-08). Hasta hoy era UN interruptor
                    -- «Recordarme cerrar el día · cada día a las 20:00» -- y el documento pide
                    siete en cuatro grupos, más el selector de hora.

                    LA REGLA QUE LO SOSTIENE TODO: «lo que interrumpe sí, lo que informa no».
                    La fila de pendientes del Inicio NO es un aviso, es el estado de su cuenta:
                    la app diciéndole «tienes esto abierto». Si se apagara, abre la app un
                    miércoles y no sabe que tiene un reporte esperando. Por eso ninguno de estos
                    interruptores la toca, y por eso el último grupo lo dice con todas las
                    letras: con esa línea puede apagarlo todo sin quedarse a ciegas.

                    Y no hay interruptor de notificaciones del móvil porque no hay
                    notificaciones: «un interruptor que no hace nada enseña que la configuración
                    miente». Cuando existan, se añade. */}
                {prefAvisos && (
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-foreground text-base">AVISOS Y RECORDATORIOS</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-2 space-y-5">
                            {/* ── El cierre del día ────────────────────────────────────
                                LOS DOS SON DISTINTOS Y HOY ERAN UNO. «Rellenar el cierre»
                                apagado quita la fila para siempre y ese cliente cae en la
                                versión del reporte que no pide datos diarios; «Recordármelo»
                                apagado la deja salir pero sin la escalada de los 2, 4 y 7
                                días. Es para el que sí quiere rellenarlo pero no quiere que se
                                lo recuerden cuando falla, y hoy no podía elegir eso. */}
                            <GrupoDeAvisos titulo="El cierre del día">
                                <FilaDeAviso
                                    titulo="Rellenar el cierre del día"
                                    testId="aviso-cierre-dia"
                                    valor={prefAvisos.cierre_dia}
                                    guardando={guardandoPref}
                                    onCambiar={cambiarCierreDelDia} />
                                {prefAvisos.cierre_dia && (
                                    <>
                                        <div className="flex items-center justify-between gap-4 py-2">
                                            <p className="text-base lg:text-sm text-foreground">A qué hora me sale</p>
                                            <select
                                                value={prefAvisos.hora_cierre}
                                                disabled={guardandoPref}
                                                onChange={(e) => guardarPref({ hora_cierre: Number(e.target.value) })}
                                                data-testid="aviso-hora-cierre"
                                                className="bg-muted border border-border rounded-lg text-foreground text-sm px-3 py-2 disabled:opacity-50"
                                            >
                                                {/* De las 17:00 en adelante y nada más: «puedes
                                                    activarla a cualquier hora A PARTIR de las
                                                    17:00». Antes no, que no se puede cerrar un
                                                    día que todavía no ha pasado. */}
                                                {[17, 18, 19, 20, 21, 22, 23].map(h => (
                                                    <option key={h} value={h}>{h}:00</option>
                                                ))}
                                            </select>
                                        </div>
                                        <FilaDeAviso
                                            titulo="Recordármelo si me lo salto"
                                            testId="aviso-recordar-cierre"
                                            valor={prefAvisos.recordar_cierre}
                                            guardando={guardandoPref}
                                            onCambiar={(v) => guardarPref({ recordar_cierre: v })} />
                                        {/* Su frase, literal. Y es la que explica que la ventana
                                            de la mañana no es un mecanismo aparte: es la misma. */}
                                        <p className="text-sm lg:text-xs text-foreground/50">
                                            Puedes activarla a cualquier hora a partir de las 17:00.
                                            Permanecerá activa hasta las 15:00 del día siguiente.
                                        </p>
                                    </>
                                )}
                            </GrupoDeAvisos>

                            {/* ── Los reportes ─────────────────────────────────────────
                                El quincenal y el mensual NO se pueden desactivar: son los que
                                hacen su ajuste. Aquí solo se apaga el recordatorio, y se dice. */}
                            <GrupoDeAvisos titulo="Los reportes">
                                <FilaDeAviso
                                    titulo="Recordatorio del reporte quincenal"
                                    testId="aviso-quincenal"
                                    valor={prefAvisos.recordatorio_quincenal}
                                    guardando={guardandoPref}
                                    onCambiar={(v) => guardarPref({ recordatorio_quincenal: v })} />
                                <FilaDeAviso
                                    titulo="Recordatorio del reporte mensual"
                                    testId="aviso-mensual"
                                    valor={prefAvisos.recordatorio_mensual}
                                    guardando={guardandoPref}
                                    onCambiar={(v) => guardarPref({ recordatorio_mensual: v })} />
                                <p className="text-sm lg:text-xs text-foreground/50">
                                    El quincenal y el mensual no se pueden desactivar: son los que
                                    hacen tu ajuste. Aquí solo apagas los recordatorios.
                                </p>
                            </GrupoDeAvisos>

                            {/* ── El peso ──────────────────────────────────────────── */}
                            <GrupoDeAvisos titulo="El peso">
                                <FilaDeAviso
                                    titulo="Recordatorio de los días de pesada"
                                    testId="aviso-peso"
                                    valor={prefAvisos.recordatorio_peso}
                                    guardando={guardandoPref}
                                    onCambiar={(v) => guardarPref({ recordatorio_peso: v })} />
                            </GrupoDeAvisos>

                            {/* ── Cómo te aviso ────────────────────────────────────────
                                LA LÍNEA DE ABAJO ES LA QUE SOSTIENE TODO EL APARTADO. Sin ella,
                                apagarlo todo se lee como quedarse a ciegas. */}
                            <GrupoDeAvisos titulo="Cómo te aviso">
                                <FilaDeAviso
                                    titulo="Avisos en la app"
                                    testId="aviso-en-la-app"
                                    valor={prefAvisos.avisos_en_la_app}
                                    guardando={guardandoPref}
                                    onCambiar={(v) => guardarPref({ avisos_en_la_app: v })} />
                                <FilaDeAviso
                                    titulo="Por correo"
                                    testId="aviso-por-correo"
                                    valor={prefAvisos.por_correo}
                                    guardando={guardandoPref}
                                    onCambiar={(v) => guardarPref({ por_correo: v })} />
                                <p className="text-sm lg:text-xs text-foreground/50">
                                    Lo que tengas pendiente seguirá saliendo en Inicio. Aquí solo
                                    apagas los avisos.
                                </p>
                            </GrupoDeAvisos>
                        </CardContent>
                    </Card>
                )}

                {/* Settings */}
                <Card className="bg-card border-border">
                    <CardContent className="p-0">
                        {[
                            { icon: Lock, title: 'Cambiar contraseña', sub: 'Seguridad de la cuenta', onClick: () => setShowPasswordDialog(true) },
                            // El recorrido de la primera vez (doc 21-08, apartado 23): quien
                            // lo saltó no lo vuelve a ver solo, así que esta fila es su única
                            // puerta de vuelta. En el teléfono es una fila más de ajustes; en
                            // escritorio sigue siendo el botón de debajo.
                            ...(recorridoDisponible ? [{
                                icon: Compass, title: 'Ver el recorrido', sub: 'Las cinco ideas del método, en un minuto', soloMovil: true,
                                onClick: () => { navigate('/dashboard'); startTour(); },
                            }] : []),
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

                {/* Ver el recorrido. En el teléfono es una fila más de la tarjeta de
                    arriba; aquí se queda para escritorio. */}
                {recorridoDisponible && (
                    <Button
                        variant="outline"
                        className="hidden lg:inline-flex w-full bg-transparent border-brand/40 text-brand hover:bg-brand/10 hover:border-brand uppercase tracking-wider"
                        onClick={() => { navigate('/dashboard'); startTour(); }}
                        data-testid="replay-tour-btn"
                    >
                        <Compass className="w-4 h-4 mr-2" /> Ver el recorrido
                    </Button>
                )}

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
