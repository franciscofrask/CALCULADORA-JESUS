import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Layers, Pencil, RotateCcw, Check, X, FlaskConical, Info } from 'lucide-react';
import { queIncluyeElPlan, ACOMPANAMIENTO_OPTS, FRECUENCIA_CONTACTO_OPTS as FRECUENCIA_OPTS, etiquetaAcompanamiento, etiquetaFrecuencia, etiquetaCalculadora } from '../lib/planAccess';
import { mensajeDeError } from '../lib/mensajeDeError';
import HelpTooltip from '../components/HelpTooltip';

// Los tres valores del fallo 10 del 19-08, tolerando el booleano viejo de un override.
const etiquetaSuplementacion = (v) => {
    if (typeof v === 'string') {
        const s = v.trim().toLowerCase();
        return s === 'guia' || s === 'guía' ? 'La guía'
            : s === 'protocolo' ? 'Protocolo personalizado' : 'Ninguna';
    }
    return v ? 'Protocolo personalizado' : 'Ninguna';
};

// Orden y etiquetas de las categorías (pestañas del catálogo original).
const ESTADOS = [
    { key: 'activo', label: 'Planes activos', hint: 'Se venden hoy' },
    { key: 'legacy', label: 'Planes legacy', hint: 'Ya no se venden; se respetan a quien los tiene' },
    { key: 'especial', label: 'Planes especiales', hint: 'A medida, pactados con Jesús' },
    { key: 'complemento', label: 'Productos complementarios', hint: 'Compra suelta, no es una membresía' },
];

const CALCULADORA_OPTS = [
    { value: 'personalizado', label: 'Personalizado (lo ajusta el entrenador)' },
    { value: 'autogestion', label: 'Autogestión' },
    { value: 'sin_ajuste', label: 'Sin ajuste activo' },
];
const RUTINA_OPTS = [
    { value: 'personalizada', label: 'Personalizada' },
    { value: 'del_mes', label: 'Del mes' },
    { value: 'opcional', label: 'Opcional' },
    { value: 'ninguna', label: 'Ninguna' },
];
const REPORTE_OPTS = ['quincenal', 'mensual', 'semanal'];
const CICLO_OPTS = ['mensual', 'trimestral', 'bimestral', 'semestral', 'unico', 'variable'];

const Dot = ({ on }) => (
    <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full ${on ? 'bg-green-500/20 text-green-500' : 'bg-white/10 text-white/30'}`}>
        {on ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
    </span>
);

const HabRow = ({ label, value }) => (
    <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-white/50">{label}</span>
        <span className="text-white/80 font-medium">{value}</span>
    </div>
);

// Los interruptores de las pantallas nuevas (doc 16-08) y la frase del día. Viven en
// db.app_settings y se tocan aquí para poder apagar una pantalla SIN desplegar.
const PANTALLAS_APP = [
    { clave: 'frase_del_dia', label: 'La frase del día en Inicio', ayuda: 'Muestra una frase del día en la portada de Inicio del cliente.' },
    { clave: 't1_inicio_nuevo', label: 'Inicio nuevo (Lo que toca hoy)', ayuda: 'La portada nueva del cliente: «Lo que toca hoy» (macros, suplementos, entreno) y «Pendiente».' },
    { clave: 't2_suplementos', label: 'Suplementos del cliente', ayuda: 'La pantalla de suplementos del cliente.' },
    { clave: 't3_entreno', label: 'Entreno (rutina y registro)', ayuda: 'Hace visible al cliente la rutina y el registro de sus entrenos.' },
    { clave: 't4_cierre_nuevo', label: 'Cierre del día nuevo', ayuda: 'El nuevo cierre del día del cliente («¿cómo fue hoy?»).' },
    { clave: 't5_diario', label: 'El Diario', ayuda: 'El Diario, dentro de Seguimiento.' },
    { clave: 't6_evolucion', label: 'Evolución completa del cliente', ayuda: 'La Evolución completa del cliente: medidas y fotos.' },
    { clave: 't10_avisos_nuevos', label: 'Los avisos nuevos', ayuda: 'Los avisos nuevos del cliente (la campanita).' },
    // P59 del doc 23-08. OJO: encenderlo manda CORREOS DE VERDAD a todos los clientes
    // con reporte pendiente, entren o no en la app. Nace apagado por eso.
    { clave: 'correos_avisos', label: 'Los avisos del reporte, por correo', ayuda: 'Manda por correo los avisos del reporte (se abre, último día, no nos llegó) y del fin de ciclo, sin esperar a que el cliente entre en la app. Un aviso, un correo: nunca se repite.' },
];

const PantallasDeLaApp = () => {
    const { api } = useAuth();
    const [ajustes, setAjustes] = useState(null);
    const [frase, setFrase] = useState('');
    const [fechaFrase, setFechaFrase] = useState('');
    const [guardandoFrase, setGuardandoFrase] = useState(false);

    useEffect(() => {
        api.get('/admin/settings')
            .then((res) => setAjustes(res.data || null))
            .catch(() => toast.error('No se pudieron cargar los ajustes de la app'));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al entrar
    }, []);

    const alternar = async (clave) => {
        const nuevo = !ajustes?.pantallas?.[clave];
        try {
            const res = await api.put('/admin/settings', { pantallas: { [clave]: nuevo } });
            setAjustes(res.data);
        } catch (e) {
            toast.error('No se pudo guardar el cambio');
        }
    };

    const guardarFrase = async () => {
        if (!frase.trim()) return;
        setGuardandoFrase(true);
        try {
            const res = await api.put('/admin/settings', {
                frase_del_dia: { texto: frase.trim(), ...(fechaFrase ? { fecha: fechaFrase } : {}) },
            });
            setAjustes(res.data);
            setFrase('');
            setFechaFrase('');
            toast.success(fechaFrase ? 'Frase programada' : 'Frase del día guardada');
        } catch (e) {
            toast.error('No se pudo guardar la frase');
        } finally {
            setGuardandoFrase(false);
        }
    };

    if (!ajustes) return null;

    return (
        <Card className="bg-[#111] border-[#2a2a2a]">
            <CardContent className="p-4 space-y-4">
                <div>
                    <h2 className="text-base font-bold text-white">Pantallas de la app</h2>
                    <p className="text-xs text-white/50">Apagar aquí quita la pantalla a todos los clientes al momento, sin desplegar.</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                    {PANTALLAS_APP.map(({ clave, label }) => {
                        const on = !!ajustes.pantallas?.[clave];
                        return (
                            <button
                                key={clave}
                                type="button"
                                onClick={() => alternar(clave)}
                                className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${on ? 'border-green-500/40 bg-green-500/10 text-white' : 'border-[#333] bg-black/30 text-white/60'}`}
                            >
                                <span>{label}</span>
                                <Dot on={on} />
                            </button>
                        );
                    })}
                </div>
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">
                        Frase del día
                        {ajustes.frase_del_dia?.texto ? (
                            <span className="ml-2 text-white/40 normal-case">ahora: «{ajustes.frase_del_dia.texto}» ({ajustes.frase_del_dia.fecha})</span>
                        ) : (
                            <span className="ml-2 text-white/40">todavía no hay ninguna</span>
                        )}
                    </Label>
                    <div className="flex gap-2">
                        <Input
                            value={frase}
                            onChange={(e) => setFrase(e.target.value)}
                            placeholder="El único secreto que tiene esto es no dejarlo."
                            className="bg-black/30 border-[#333] text-white text-sm"
                        />
                        {/* PROGRAMABLE CON UNA SEMANA (doc 19-08): sin fecha entra hoy;
                            con fecha se queda en la cola y sale su día sola. */}
                        <Input
                            type="date"
                            value={fechaFrase}
                            onChange={(e) => setFechaFrase(e.target.value)}
                            min={new Date().toLocaleDateString('en-CA')}
                            max={new Date(Date.now() + 7 * 864e5).toLocaleDateString('en-CA')}
                            className="bg-black/30 border-[#333] text-white text-sm w-40 shrink-0"
                        />
                        <Button onClick={guardarFrase} disabled={guardandoFrase || !frase.trim()} className="bg-[#FF671F] hover:bg-[#e55b1a] text-white">
                            {fechaFrase ? 'Programar' : 'Guardar'}
                        </Button>
                    </div>
                    <p className="text-[11px] text-white/40">Si un día no hay frase nueva, el cliente sigue viendo la última. Con fecha, la frase se programa (hasta una semana) y entra sola su día.</p>
                    {(ajustes.frases_programadas || []).length > 0 && (
                        <div className="space-y-0.5">
                            {ajustes.frases_programadas.map((f) => (
                                <p key={f.fecha} className="text-[11px] text-white/50">
                                    {f.fecha} · «{f.texto}»
                                </p>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

// MI MODO PRUEBAS (solo cuentas marcadas `es_pruebas`): los MISMOS interruptores, pero
// que valen SOLO para esta cuenta. El backend guarda las anulaciones en el usuario y las
// pisa sobre lo global únicamente cuando la petición viene de esta cuenta; nadie más se
// entera. Sirve para recorrer las pantallas nuevas sin cambiárselas a los clientes.
// Los estados por los que un administrador de pruebas puede pasear su propia cuenta.
const ESCENARIOS_CUENTA = [
    { id: 'activo', label: 'Activa y al día', ayuda: 'Cuenta al día con acceso normal. El punto de partida limpio, sin ningún bloqueo.' },
    { id: 'por_vencer', label: 'Por vencer (renovación)', ayuda: 'Tu ciclo acaba en 5 días: verás el aviso «Tu ciclo acaba en una semana» en la campanita y la pantalla de renovar.' },
    { id: 'caducado', label: 'Suscripción caducada', ayuda: 'Suscripción terminada: la pantalla de «tu suscripción ha terminado, renueva o pasa a Mantenimiento».' },
    { id: 'sin_plan', label: 'Sin plan (elige plan)', ayuda: 'Como un registro nuevo sin plan contratado: la pantalla de «elige tu plan».' },
    { id: 'pago_a_medias', label: 'Pago a medias', ayuda: 'Empezaste un pago y no lo terminaste: el estado de pago sin completar.' },
    { id: 'cuestionario_inicial', label: 'Cuestionario sin completar', ayuda: 'Con el cuestionario inicial sin terminar: la app te lleva a completarlo.' },
    { id: 'ajuste_pendiente', label: 'Ajuste de macros pendiente', ayuda: 'Cuestionario hecho pero macros sin ajustar y sin que nadie te los haya puesto: el aviso de «termina de ajustar tus macros».' },
    { id: 'ventana_grasa', label: 'Ventana de % grasa (12 sem)', ayuda: 'Han pasado 12 semanas desde tu último dato: sale la ventana para actualizar tu % de grasa.' },
];
const PLANES_CUENTA = ['nivel1', 'nivel2', 'nivel3', 'elm', 'gold', 'silver', 'bronze', 'mantenimiento'];

const MiModoPruebas = () => {
    const { api, appSettings, refrescarAjustes, profile, refreshProfile } = useAuth();
    const [guardando, setGuardando] = useState(false);
    const [fraseTexto, setFraseTexto] = useState('');
    const [planSel, setPlanSel] = useState('nivel2');
    const pantallas = appSettings?.pantallas || {};
    const escenarioActivo = profile?.pruebas_escenario || null;

    const aplicarEscenario = async (id, plan) => {
        setGuardando(true);
        try {
            await api.post('/settings/mis-pruebas/escenario', { escenario: id, ...(plan ? { plan } : {}) });
            await refreshProfile();
            toast.success('Tu cuenta está en modo de prueba');
        } catch (e) {
            toast.error('No se pudo aplicar el escenario');
        } finally {
            setGuardando(false);
        }
    };

    const restaurarCuenta = async () => {
        setGuardando(true);
        try {
            await api.post('/settings/mis-pruebas/restaurar');
            await refreshProfile();
            toast.success('Tu cuenta vuelve a la normalidad');
        } catch (e) {
            toast.error('No se pudo restaurar');
        } finally {
            setGuardando(false);
        }
    };

    const alternar = async (clave) => {
        const nuevo = !pantallas[clave];
        setGuardando(true);
        try {
            await api.put('/settings/mis-pruebas', { pantallas: { [clave]: nuevo } });
            await refrescarAjustes();
        } catch (e) {
            toast.error('No se pudo guardar el cambio');
        } finally {
            setGuardando(false);
        }
    };

    const guardarFrase = async () => {
        setGuardando(true);
        try {
            await api.put('/settings/mis-pruebas', { frase: fraseTexto.trim() });
            await refrescarAjustes();
            toast.success(fraseTexto.trim() ? 'Tu frase de pruebas guardada' : 'Frase de pruebas quitada');
        } catch (e) {
            toast.error('No se pudo guardar la frase');
        } finally {
            setGuardando(false);
        }
    };

    const limpiar = async () => {
        setGuardando(true);
        try {
            await api.delete('/settings/mis-pruebas');
            await refrescarAjustes();
            setFraseTexto('');
            toast.success('Vuelves a ver lo mismo que todos');
        } catch (e) {
            toast.error('No se pudo reiniciar');
        } finally {
            setGuardando(false);
        }
    };

    return (
        <Card className="bg-[#111] border-[#FF671F]/40">
            <CardContent className="p-4 space-y-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2">
                        <FlaskConical className="w-5 h-5 text-[#FF671F] shrink-0 mt-0.5" />
                        <div>
                            <h2 className="text-base font-bold text-white">Mi modo pruebas <span className="text-[#FF671F]">(solo tú)</span></h2>
                            <p className="text-xs text-white/50">Enciende o apaga las pantallas SOLO para tu cuenta; ningún cliente lo nota. Para verlas, entra en tu propio panel de cliente.</p>
                        </div>
                    </div>
                    <Button variant="ghost" onClick={limpiar} disabled={guardando} className="text-white/60 hover:text-white shrink-0">
                        <RotateCcw className="w-4 h-4 mr-1" /> Reiniciar
                    </Button>
                </div>

                {/* Una línea; el detalle de cada botón va en su «?». */}
                <div className="flex gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2">
                    <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-white/70">Todo esto cambia <span className="text-white/90 font-semibold">solo tu cuenta</span>; nadie más lo nota. Pasa el ratón por el «?» de cada botón para ver qué hace. Para verlo, entra en tu panel de cliente («Usar app»); para volver, «Restaurar mi cuenta».</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                    {PANTALLAS_APP.map(({ clave, label, ayuda }) => {
                        const on = !!pantallas[clave];
                        return (
                            <div key={clave} className="flex items-center gap-1">
                                <button
                                    type="button"
                                    onClick={() => alternar(clave)}
                                    disabled={guardando}
                                    className={`flex-1 min-w-0 flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${on ? 'border-[#FF671F]/50 bg-[#FF671F]/10 text-white' : 'border-[#333] bg-black/30 text-white/60'}`}
                                >
                                    <span>{label}</span>
                                    <Dot on={on} />
                                </button>
                                <HelpTooltip text={ayuda} className="shrink-0" />
                            </div>
                        );
                    })}
                </div>
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Tu frase del día (solo tú)</Label>
                    <div className="flex gap-2">
                        <Input
                            value={fraseTexto}
                            onChange={(e) => setFraseTexto(e.target.value)}
                            placeholder="La que quieras probar en tu Inicio"
                            className="bg-black/30 border-[#333] text-white text-sm"
                        />
                        <Button onClick={guardarFrase} disabled={guardando} className="bg-[#FF671F] hover:bg-[#e55b1a] text-white shrink-0">Guardar</Button>
                    </div>
                    <p className="text-[11px] text-white/40">Vacío y Guardar: quitas tu frase y vuelves a la global. Acuérdate de encender también «La frase del día en Inicio» de arriba.</p>
                </div>

                {/* ESCENARIOS: poner mi propia cuenta en un estado para recorrer esas pantallas
                    (vencimiento, renovación, caducado, cuestionario...) sin crear clientes demo. */}
                <div className="border-t border-[#2a2a2a] pt-4 space-y-2">
                    <div>
                        <h3 className="text-sm font-bold text-white">Poner mi cuenta en un estado</h3>
                        <p className="text-xs text-white/50">Cambia TU cuenta para ver esas pantallas. Guardo una foto antes de tocar; «Restaurar» la deja como estaba. Míralas entrando en tu panel de cliente. El plan y el estado se combinan: aplica el plan y ponle el estado encima. Cada vez que pones un estado, tus avisos de cliente se vacían y se vuelven a calcular, así ves los de ese estado al momento.</p>
                    </div>
                    {escenarioActivo && (
                        <div className="flex items-center justify-between gap-2 rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-3 py-2">
                            <span className="text-xs text-yellow-200">
                                Tu cuenta está en un estado de prueba: <span className="font-bold">{(ESCENARIOS_CUENTA.find(e => e.id === escenarioActivo) || {}).label || escenarioActivo}</span>
                            </span>
                            <Button onClick={restaurarCuenta} disabled={guardando} className="bg-yellow-500 hover:bg-yellow-400 text-black shrink-0 h-8">
                                Restaurar mi cuenta
                            </Button>
                        </div>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {ESCENARIOS_CUENTA.map(({ id, label, ayuda }) => (
                            <div key={id} className="flex items-center gap-1">
                                <button
                                    type="button"
                                    onClick={() => aplicarEscenario(id)}
                                    disabled={guardando}
                                    className={`flex-1 min-w-0 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${escenarioActivo === id ? 'border-[#FF671F]/60 bg-[#FF671F]/10 text-white' : 'border-[#333] bg-black/30 text-white/70 hover:text-white'}`}
                                >
                                    {label}
                                </button>
                                <HelpTooltip text={ayuda} className="shrink-0" />
                            </div>
                        ))}
                    </div>
                    <div className="flex items-center gap-2 pt-1 flex-wrap">
                        <span className="text-xs text-white/60 shrink-0">Plan</span>
                        <HelpTooltip text="Elige un plan y aplícalo de dos formas: «Aplicar plan» deja tu cuenta como un cliente YA asentado en ese plan (cuestionario hecho); «Recién comprado» la deja como alguien que ACABA de comprarlo, con el cuestionario inicial por hacer (la app le fuerza el onboarding)." className="shrink-0" />
                        <select
                            value={planSel}
                            onChange={(e) => setPlanSel(e.target.value)}
                            className="bg-black/30 border border-[#333] rounded-lg text-white text-xs px-2 py-1.5"
                        >
                            {PLANES_CUENTA.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                        <Button onClick={() => aplicarEscenario('cambiar_plan', planSel)} disabled={guardando} className="bg-[#FF671F] hover:bg-[#e55b1a] text-white h-8">
                            Aplicar plan
                        </Button>
                        <Button onClick={() => aplicarEscenario('nuevo_con_plan', planSel)} disabled={guardando} variant="outline" className="border-[#FF671F]/50 text-white hover:bg-[#FF671F]/10 h-8">
                            Recién comprado
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

const PlanCard = ({ plan, onEdit }) => {
    const h = plan.habilitaciones || {};
    const sem = plan.ciclo?.semanas;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                    <div>
                        <p className="text-white font-bold leading-tight">{plan.name}</p>
                        <p className="text-[11px] text-white/40 font-mono">{plan.code}</p>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Que un plan retirado esté abierto a los suyos se tiene que ver
                            desde fuera, sin abrir la ficha: es lo que decide si a un
                            cliente le sale «Seguir igual» al acabar su ciclo. */}
                        {plan.renovable_por_los_suyos && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-semibold">renovable</span>
                        )}
                        {plan.has_override && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold">editado</span>
                        )}
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-white/60 hover:text-white" onClick={() => onEdit(plan)} data-testid={`edit-plan-${plan.code}`}>
                            <Pencil className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-x-3">
                    <HabRow label="Ciclo" value={sem ? `${sem} sem (${plan.ciclo?.tipo})` : (plan.ciclo?.tipo || '-')} />
                    <HabRow label="Precio" value={plan.precio != null ? `${plan.precio}€` : '-'} />
                </div>
                {plan.precio_nota && <p className="text-[11px] text-white/40 -mt-1">{plan.precio_nota}</p>}

                {/* LOS SIETE INTERRUPTORES del doc del 19-08, más lo que ya había. La fila
                    Harbiz se quitó de las 21 fichas: Harbiz muere (fallo 07). */}
                <div className="border-t border-[#222] pt-2 space-y-1">
                    {/* Con nombre, no con el código de la casilla («personalizado»). */}
                    <HabRow label="Calculadora" value={h.calculadora ? etiquetaCalculadora(h.calculadora) : '-'} />
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Edita sus macros</span>
                        <Dot on={h.edita_macros !== undefined ? !!h.edita_macros : h.calculadora !== 'personalizado'} />
                    </div>
                    <HabRow label="Frecuencia de ajuste" value={h.frecuencia_ajuste || 'ninguna'} />
                    <HabRow label="Rutina" value={h.rutina || '-'} />
                    <HabRow label="Reportes" value={(h.reportes && h.reportes.length) ? h.reportes.join(' + ') : 'ninguno'} />
                    <HabRow label="Suplementación" value={etiquetaSuplementacion(h.suplementacion)} />
                    <HabRow label="Feedback" value={h.feedback || 'Ninguno'} />
                    <HabRow label="Canal de contacto" value={h.canal_contacto || 'Ninguno'} />
                    <HabRow label="Videollamadas" value={h.videollamadas || '0'} />
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Grupo privado</span><Dot on={!!h.grupo_privado} />
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Audio de feedback</span><Dot on={!!h.audio_feedback} />
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-white/50">Materiales y recursos</span><Dot on={!!h.materiales_recursos} />
                    </div>
                    <HabRow label="Responsable" value={plan.responsable || '-'} />
                    <HabRow label="Renovación automática"
                        value={plan.renovacion
                            ? (plan.renovacion.automatica ? `Sí · ${plan.renovacion.cada}` : `No · ${plan.renovacion.cada}`)
                            : '-'} />
                    {/* Si el «Tu plan incluye» de este plan está escrito a mano o se deriva de
                        las habilitaciones (punto 6.4). */}
                    <HabRow label="Qué incluye" value={plan.que_incluye ? 'escrito' : 'derivado'} />
                </div>
            </CardContent>
        </Card>
    );
};

const AdminPlansPage = () => {
    const { api, user } = useAuth();
    const [catalog, setCatalog] = useState({});
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null); // plan en edición
    const [form, setForm] = useState(null);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/plans');
            setCatalog(res.data || {});
        } catch (e) {
            toast.error('No se pudo cargar el catálogo de planes');
        } finally {
            setLoading(false);
        }
    }, [api]);

    useEffect(() => { load(); }, [load]);

    const openEdit = (plan) => {
        setEditing(plan);
        setForm({
            name: plan.name || '',
            estado: plan.estado || 'activo',
            // Se enseña, no se manda: el importe no es editable.
            precio: plan.precio ?? 0,
            precio_nota: plan.precio_nota || '',
            renovable_por_los_suyos: !!plan.renovable_por_los_suyos,
            responsable: plan.responsable || '',
            que_incluye: plan.que_incluye || '',
            ciclo_tipo: plan.ciclo?.tipo || 'mensual',
            ciclo_semanas: plan.ciclo?.semanas ?? '',
            calculadora: plan.habilitaciones?.calculadora || 'personalizado',
            // Los interruptores del 19-08. El de editar macros, si el override guardado no
            // lo trae, arranca con lo que era verdad hasta hoy: autogestión sí, coach no.
            edita_macros: plan.habilitaciones?.edita_macros !== undefined
                ? !!plan.habilitaciones.edita_macros
                : plan.habilitaciones?.calculadora !== 'personalizado',
            frecuencia_ajuste: plan.habilitaciones?.frecuencia_ajuste || 'ninguna',
            rutina: plan.habilitaciones?.rutina || 'ninguna',
            reportes: [...(plan.habilitaciones?.reportes || [])],
            // Tres opciones (fallo 10); el booleano viejo de un override se traduce.
            suplementacion: typeof plan.habilitaciones?.suplementacion === 'string'
                ? plan.habilitaciones.suplementacion
                : (plan.habilitaciones?.suplementacion ? 'protocolo' : 'ninguna'),
            feedback: plan.habilitaciones?.feedback || '',
            canal_contacto: plan.habilitaciones?.canal_contacto || '',
            videollamadas: plan.habilitaciones?.videollamadas || '0',
            grupo_privado: !!plan.habilitaciones?.grupo_privado,
            tiempo_respuesta: plan.habilitaciones?.tiempo_respuesta || '',
            audio_feedback: !!plan.habilitaciones?.audio_feedback,
            materiales_recursos: !!plan.habilitaciones?.materiales_recursos,
            renovacion_automatica: !!plan.renovacion?.automatica,
            renovacion_cada: plan.renovacion?.cada || '',
            // Lo que separa a dos planes que por lo demás son idénticos salvo el precio:
            // si hay alguien detrás y cada cuánto le escribe.
            acompanamiento: plan.habilitaciones?.acompanamiento || 'solo_app',
            frecuencia_contacto: plan.habilitaciones?.frecuencia_contacto || 'ninguna',
        });
    };

    const toggleReporte = (r) => setForm(f => ({
        ...f,
        reportes: f.reportes.includes(r) ? f.reportes.filter(x => x !== r) : [...f.reportes, r],
    }));

    const save = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            // `precio` NO viaja: el backend ya no lo acepta (PLAN_EDITABLE_FIELDS) y
            // mandarlo daría la impresión de que se guarda algo.
            const payload = {
                name: form.name.trim(),
                estado: form.estado,
                precio_nota: form.precio_nota,
                // Si el plan deja de ser legacy, el interruptor se apaga con él: un plan
                // que vuelve a venderse no necesita puerta de atrás para los suyos.
                renovable_por_los_suyos: form.estado === 'legacy' && !!form.renovable_por_los_suyos,
                responsable: form.responsable,
                que_incluye: form.que_incluye.trim(),
                ciclo: {
                    tipo: form.ciclo_tipo,
                    semanas: form.ciclo_semanas === '' ? null : parseInt(form.ciclo_semanas, 10),
                },
                habilitaciones: {
                    calculadora: form.calculadora,
                    edita_macros: form.edita_macros,
                    frecuencia_ajuste: form.frecuencia_ajuste,
                    rutina: form.rutina,
                    reportes: form.reportes,
                    suplementacion: form.suplementacion,
                    feedback: form.feedback,
                    canal_contacto: form.canal_contacto,
                    videollamadas: form.videollamadas,
                    grupo_privado: form.grupo_privado,
                    tiempo_respuesta: form.tiempo_respuesta,
                    audio_feedback: form.audio_feedback,
                    materiales_recursos: form.materiales_recursos,
                    acompanamiento: form.acompanamiento,
                    frecuencia_contacto: form.frecuencia_contacto,
                },
                renovacion: {
                    automatica: form.renovacion_automatica,
                    cada: form.renovacion_cada.trim(),
                },
            };
            await api.put(`/admin/plans/${editing.code}`, payload);
            toast.success('Plan actualizado');
            setEditing(null);
            setForm(null);
            load();
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al guardar'));
        } finally {
            setSaving(false);
        }
    };

    const resetPlan = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            await api.delete(`/admin/plans/${editing.code}`);
            toast.success('Plan restaurado a los valores por defecto');
            setEditing(null);
            setForm(null);
            load();
        } catch (e) {
            toast.error('No se pudo restaurar');
        } finally {
            setSaving(false);
        }
    };

    const plans = Object.values(catalog);

    return (
        <div className="p-4 md:p-6 space-y-6">
            <div className="flex items-center gap-3">
                <Layers className="w-6 h-6 text-[#FF671F]" />
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>CATÁLOGO DE PLANES</h1>
                    <p className="text-sm text-white/50">Fuente única de planes, ciclos y habilitaciones. Editar aquí afecta a lo que ve cada usuario.</p>
                </div>
            </div>

            {user?.es_pruebas && <MiModoPruebas />}

            <PantallasDeLaApp />

            {loading ? (
                <div className="flex justify-center py-16"><div className="animate-spin w-7 h-7 border-2 border-[#FF671F] border-t-transparent rounded-full" /></div>
            ) : (
                ESTADOS.map(({ key, label, hint }) => {
                    const grupo = plans.filter(p => p.estado === key);
                    if (!grupo.length) return null;
                    return (
                        <section key={key} className="space-y-3">
                            <div className="flex items-baseline gap-3">
                                <h2 className="text-lg font-bold text-white uppercase tracking-wide">{label}</h2>
                                <span className="text-xs text-white/40">{hint}</span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {grupo.map(p => <PlanCard key={p.code} plan={p} onEdit={openEdit} />)}
                            </div>
                        </section>
                    );
                })
            )}

            {/* Modal de edición */}
            <Dialog open={!!editing} onOpenChange={(o) => { if (!o) { setEditing(null); setForm(null); } }}>
                <DialogContent className="bg-[#0A0A0A] border-[#333] text-white max-w-lg max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Editar plan · {editing?.name}</DialogTitle>
                    </DialogHeader>
                    {form && (
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Nombre</Label>
                                    <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                                <div><Label className="text-white/60 text-xs">Estado</Label>
                                    <select value={form.estado} onChange={e => setForm(f => ({ ...f, estado: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {ESTADOS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                                    </select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Ciclo</Label>
                                    <select value={form.ciclo_tipo} onChange={e => setForm(f => ({ ...f, ciclo_tipo: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {CICLO_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                                    </select>
                                </div>
                                <div><Label className="text-white/60 text-xs">Semanas del ciclo (vacío = indefinido)</Label>
                                    <Input type="number" value={form.ciclo_semanas} onChange={e => setForm(f => ({ ...f, ciclo_semanas: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                            </div>
                            {/* EL IMPORTE SE VE PERO NO SE TOCA (Francisco, 16-08). Lo que
                                se cobra sale del Price de Stripe, no de aquí: escribir otro
                                número cambiaba el escaparate y seguía cobrando lo de
                                siempre. Para cambiarlo de verdad hay que crear el precio en
                                Stripe y tocar el catálogo en el código. */}
                            <div className="grid grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Precio (€)</Label>
                                    <Input type="number" value={form.precio} readOnly disabled data-testid="plan-precio"
                                        className="bg-[#0A0A0A] border-[#282828] text-white/50 mt-1 cursor-not-allowed" />
                                    <p className="text-[11px] text-white/30 mt-1">Lo fija el precio de Stripe. No se edita aquí.</p>
                                </div>
                                <div><Label className="text-white/60 text-xs">Responsable</Label>
                                    <Input value={form.responsable} onChange={e => setForm(f => ({ ...f, responsable: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                                </div>
                            </div>

                            {/* Las opciones de precio del catálogo (mensual, anual...), también
                                de solo lectura: son importes, y valen lo mismo que el de arriba. */}
                            {!!(editing?.precios || []).length && (
                                <div>
                                    <Label className="text-white/60 text-xs">Opciones de precio</Label>
                                    <div className="mt-1 space-y-1" data-testid="plan-precios">
                                        {editing.precios.map((p, i) => (
                                            <div key={i} className="flex items-center justify-between rounded-lg border border-[#282828] bg-[#0A0A0A] px-3 py-2 text-sm">
                                                <span className="text-white/50">{p.label}{p.periodo ? ` · ${p.periodo}` : ''}</span>
                                                <span className="text-white/60 font-medium">{p.importe}€</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            <div><Label className="text-white/60 text-xs">Nota de precio</Label>
                                <Input value={form.precio_nota} onChange={e => setForm(f => ({ ...f, precio_nota: e.target.value }))} className="bg-[#111] border-[#333] text-white mt-1" />
                            </div>

                            {/* REABRIR UN PLAN ANTIGUO PARA LOS SUYOS (Francisco, 16-08).
                                Solo tiene sentido en los que ya no se venden: al cliente que
                                YA lo tiene se le deja renovarlo con lo que incluye hoy y con
                                su precio congelado; para el resto el plan sigue sin existir.
                                Bloqueado si el plan no tiene precio en Stripe, porque
                                entonces la renovación no se podría cobrar. */}
                            {form.estado === 'legacy' && (
                                <div className="border border-[#282828] rounded-lg p-3 bg-[#0A0A0A]">
                                    <button
                                        type="button"
                                        disabled={!editing?.tiene_price_en_stripe}
                                        onClick={() => setForm(f => ({ ...f, renovable_por_los_suyos: !f.renovable_por_los_suyos }))}
                                        data-testid="plan-renovable-por-los-suyos"
                                        className={`w-full flex items-center justify-between gap-3 text-left text-sm ${editing?.tiene_price_en_stripe ? '' : 'opacity-50 cursor-not-allowed'}`}
                                    >
                                        <span className="text-white/80">Dejar que lo renueven los que ya lo tienen</span>
                                        <Dot on={!!form.renovable_por_los_suyos} />
                                    </button>
                                    <p className="text-[11px] text-white/30 mt-1">
                                        {editing?.tiene_price_en_stripe
                                            ? 'No vuelve a la tienda: solo lo verá quien ya esté en este plan, al acabar su ciclo.'
                                            : 'Este plan no tiene precio en Stripe, así que no se le podría cobrar la renovación.'}
                                    </p>
                                </div>
                            )}

                            {/* QUÉ INCLUYE, ESCRITO A MANO (punto 6.4). Lo que se pinta tal cual en
                                «Tu plan incluye» de Mi perfil. Si se deja vacío se siguen derivando
                                las líneas de las habilitaciones, que es lo que les toca a los planes
                                que ya no se venden. */}
                            <div><Label className="text-white/60 text-xs">Qué incluye (una línea por punto)</Label>
                                <textarea value={form.que_incluye} rows={5} data-testid="plan-que-incluye"
                                    onChange={e => setForm(f => ({ ...f, que_incluye: e.target.value }))}
                                    placeholder={'Dieta personalizada y ajustada cada quince días\nRutina de entrenamiento a tu medida\nChat directo con tu entrenador'}
                                    className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-3 py-2 mt-1 resize-y placeholder:text-white/25" />
                                <p className="text-[11px] text-white/30 mt-1">
                                    Se escribe solo para los cuatro que se venden. Vacío = se derivan de las habilitaciones.
                                </p>
                            </div>

                            <div className="border-t border-[#222] pt-3">
                                <p className="text-xs font-bold text-white/70 uppercase tracking-wider mb-2">Habilitaciones</p>
                                <div className="grid grid-cols-2 gap-3">
                                    <div><Label className="text-white/60 text-xs">Calculadora</Label>
                                        <select value={form.calculadora} onChange={e => setForm(f => ({ ...f, calculadora: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {CALCULADORA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Rutina</Label>
                                        <select value={form.rutina} onChange={e => setForm(f => ({ ...f, rutina: e.target.value }))} className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {RUTINA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                </div>
                                {/* Lo que de verdad separa un plan de otro cuando el resto es
                                    igual: si hay alguien detrás y cada cuánto le escribe. */}
                                <div className="grid grid-cols-2 gap-3 mt-3">
                                    <div><Label className="text-white/60 text-xs">Acompañamiento</Label>
                                        <select value={form.acompanamiento} onChange={e => setForm(f => ({ ...f, acompanamiento: e.target.value }))}
                                            data-testid="plan-acompanamiento"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {ACOMPANAMIENTO_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Frecuencia de contacto</Label>
                                        <select value={form.frecuencia_contacto} onChange={e => setForm(f => ({ ...f, frecuencia_contacto: e.target.value }))}
                                            data-testid="plan-frecuencia-contacto"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            {FRECUENCIA_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                </div>
                                <div className="mt-2">
                                    <Label className="text-white/60 text-xs">Reportes</Label>
                                    <div className="flex gap-2 mt-1">
                                        {REPORTE_OPTS.map(r => (
                                            <button key={r} type="button" onClick={() => toggleReporte(r)}
                                                className={`px-3 py-1.5 rounded-lg text-xs capitalize border transition-colors ${form.reportes.includes(r) ? 'bg-[#FF671F] border-[#FF671F] text-white' : 'bg-[#111] border-[#333] text-white/60'}`}>
                                                {r}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                {/* LOS INTERRUPTORES DEL 19-08. La suplementación ya no es un
                                    sí/no: son dos cosas distintas (la guía, igual para todos, y
                                    el protocolo escrito para esa persona). Y Harbiz murió. */}
                                <div className="grid grid-cols-2 gap-3 mt-3">
                                    <div><Label className="text-white/60 text-xs">Suplementación</Label>
                                        <select value={form.suplementacion} onChange={e => setForm(f => ({ ...f, suplementacion: e.target.value }))}
                                            data-testid="plan-suplementacion"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            <option value="ninguna">Ninguna</option>
                                            <option value="guia">La guía</option>
                                            <option value="protocolo">Protocolo personalizado</option>
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Frecuencia de ajuste</Label>
                                        <select value={form.frecuencia_ajuste} onChange={e => setForm(f => ({ ...f, frecuencia_ajuste: e.target.value }))}
                                            data-testid="plan-frecuencia-ajuste"
                                            className="w-full bg-[#111] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                            <option value="ninguna">Ninguna</option>
                                            <option value="mensual">Mensual</option>
                                            <option value="quincenal">Cada dos semanas</option>
                                            <option value="semanal">Semanal</option>
                                            <option value="al_renovar">Al renovar, si lo pide</option>
                                        </select>
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Feedback del entrenador</Label>
                                        <Input value={form.feedback} onChange={e => setForm(f => ({ ...f, feedback: e.target.value }))}
                                            placeholder="Ninguno · Con cada reporte · Semanal" className="bg-[#111] border-[#333] text-white mt-1" />
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Canal de contacto</Label>
                                        <Input value={form.canal_contacto} onChange={e => setForm(f => ({ ...f, canal_contacto: e.target.value }))}
                                            placeholder="Chat de dudas · WhatsApp · Ninguno" className="bg-[#111] border-[#333] text-white mt-1" />
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Videollamadas</Label>
                                        <Input value={form.videollamadas} onChange={e => setForm(f => ({ ...f, videollamadas: e.target.value }))}
                                            placeholder="0 · Una al mes" className="bg-[#111] border-[#333] text-white mt-1" />
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Tiempo de respuesta</Label>
                                        <Input value={form.tiempo_respuesta} onChange={e => setForm(f => ({ ...f, tiempo_respuesta: e.target.value }))}
                                            placeholder="menos de 24 h" className="bg-[#111] border-[#333] text-white mt-1" />
                                    </div>
                                    <div><Label className="text-white/60 text-xs">Renovación · cada</Label>
                                        <Input value={form.renovacion_cada} onChange={e => setForm(f => ({ ...f, renovacion_cada: e.target.value }))}
                                            placeholder="mensual · cada 12 semanas · se recontrata" className="bg-[#111] border-[#333] text-white mt-1" />
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-x-6 gap-y-2 mt-3">
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.edita_macros} onChange={e => setForm(f => ({ ...f, edita_macros: e.target.checked }))}
                                            data-testid="plan-edita-macros" className="accent-[#FF671F] w-4 h-4" />
                                        Puede editar sus macros
                                    </label>
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.grupo_privado} onChange={e => setForm(f => ({ ...f, grupo_privado: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                                        Grupo privado
                                    </label>
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.audio_feedback} onChange={e => setForm(f => ({ ...f, audio_feedback: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                                        Audio de feedback
                                    </label>
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.materiales_recursos} onChange={e => setForm(f => ({ ...f, materiales_recursos: e.target.checked }))} className="accent-[#FF671F] w-4 h-4" />
                                        Materiales y recursos
                                    </label>
                                    <label className="flex items-center gap-2 text-sm text-white/80 cursor-pointer">
                                        <input type="checkbox" checked={form.renovacion_automatica} onChange={e => setForm(f => ({ ...f, renovacion_automatica: e.target.checked }))}
                                            data-testid="plan-renovacion-automatica" className="accent-[#FF671F] w-4 h-4" />
                                        Renovación automática
                                    </label>
                                </div>
                            </div>

                            <div className="border-t border-[#222] pt-2">
                                <p className="text-xs text-white/40 mb-1">Vista previa "tu plan incluye":</p>
                                {/* Lo mismo que verá el cliente: si hay texto escrito manda ese, y
                                    si no, las líneas derivadas. Así se ve al escribirlo. */}
                                <ul className="text-xs text-white/70 list-disc list-inside space-y-0.5" data-testid="plan-que-incluye-preview">
                                    {queIncluyeElPlan({
                                        que_incluye: form.que_incluye,
                                        habilitaciones: {
                                            calculadora: form.calculadora, rutina: form.rutina,
                                            reportes: form.reportes, suplementacion: form.suplementacion,
                                            acompanamiento: form.acompanamiento,
                                            frecuencia_contacto: form.frecuencia_contacto,
                                        },
                                    }).map((x, i) => <li key={i}>{x}</li>)}
                                </ul>
                            </div>
                        </div>
                    )}
                    <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
                        {editing?.has_override
                            ? <Button variant="ghost" className="text-white/50 hover:text-red-400" onClick={resetPlan} disabled={saving}><RotateCcw className="w-4 h-4 mr-1" /> Restaurar por defecto</Button>
                            : <span />}
                        <Button className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" onClick={save} disabled={saving} data-testid="save-plan-btn">
                            {saving ? 'Guardando…' : 'Guardar'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AdminPlansPage;
