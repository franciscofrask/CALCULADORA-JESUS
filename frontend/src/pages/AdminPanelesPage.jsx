/**
 * LOS CUATRO PANELES (doc del 19-08, bloque 12): Dirección, Entrenador, Operaciones
 * y Soporte. Dos reglas del doc que mandan en todo el fichero:
 *
 *   - «Cada número lleva a su lista de nombres»: ningún conteo sin su lista desplegable.
 *   - «De cada lista se puede asignar tarea»: checkbox por fila y botón Asignar tarea.
 *
 * El modal de asignar es el compartido de la casa (components/AsignarTarea): ya hace
 * exactamente el POST /admin/tareas con sobre_quienes, y tres formularios distintos
 * acabarían pidiendo cosas distintas. Aquí solo vive la lógica de selección.
 *
 * Cada pestaña carga su endpoint al abrirse (no las cuatro de golpe), y una vez
 * visitada se queda montada oculta para no perder selecciones ni ediciones.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { PlanBadge } from './ClientDashboard';
import AsignarTarea from '../components/AsignarTarea';
import { mensajeDeError } from '../lib/mensajeDeError';
import { toast } from 'sonner';
import {
    Briefcase, Dumbbell, Wrench, Headphones, ChevronRight, ChevronDown,
    Pencil, Check, X, Users, TrendingUp, UserPlus, Receipt, Camera,
    AlertTriangle, ClipboardList, CalendarClock, Phone, RefreshCw,
} from 'lucide-react';

// Dinero en es-ES sin decimales: «4.240 €». Sin número, un guion y a otra cosa.
const eur = (n) => (n === null || n === undefined || isNaN(Number(n)))
    ? '-'
    : `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(Number(n))} €`;

// El estado de una renovación, por color: verde confirmado, ámbar por confirmar,
// azul corregido a mano.
const ESTADO = {
    confirmado:    { texto: 'Confirmado',    clase: 'text-emerald-400', punto: 'bg-emerald-400' },
    por_confirmar: { texto: 'Por confirmar', clase: 'text-amber-400',   punto: 'bg-amber-400' },
    a_mano:        { texto: 'A mano',        clase: 'text-sky-400',     punto: 'bg-sky-400' },
};

const PuntoEstado = ({ estado }) => (
    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${(ESTADO[estado] || {}).punto || 'bg-white/20'}`}
        title={(ESTADO[estado] || {}).texto || estado || ''} />
);

const Cargando = () => <p className="text-white/30 text-sm py-8 text-center">Cargando…</p>;

const Vacio = ({ frase = 'Nada pendiente' }) => (
    <p className="text-white/25 text-xs py-3 text-center">{frase}</p>
);

// Título de sección, con el estilo de la casa.
const Titulo = ({ children }) => (
    <p className="text-xs font-bold text-white/40 uppercase tracking-wider">{children}</p>
);

// Un bloque que no tiene de dónde sacar los datos todavía (sin_conectar del backend).
// Tarjeta apagada con el motivo: nada de inventar números.
const TarjetaApagada = ({ bloque, motivo }) => (
    <Card className="bg-[#0D0D0D] border-[#1A1A1A]">
        <CardContent className="p-4">
            <p className="text-xs font-bold text-white/30 uppercase tracking-wider">{bloque}</p>
            <p className="text-[11px] text-white/30 mt-1 truncate" title={motivo}>{motivo}</p>
        </CardContent>
    </Card>
);

/**
 * LA LISTA DE CLIENTES CON SELECCIÓN. Es EL componente transversal: checkbox por fila,
 * nombre que lleva a la ficha, y el botón «Asignar tarea» que se enciende con la
 * selección. `extra` pinta lo particular de cada lista a la derecha del nombre.
 * `onAsignar` recibe [{id, nombre}] y lo resuelve el modal compartido de la página.
 */
const ListaSeleccionable = ({ titulo, sub, items, extra, vacio, onAsignar, icono: Icono, color = '#FF671F', maxAlto = 'max-h-72' }) => {
    const navigate = useNavigate();
    const [sel, setSel] = useState(() => new Set());
    const lista = items || [];
    const toggle = (id) => setSel(prev => {
        const s = new Set(prev);
        if (s.has(id)) s.delete(id); else s.add(id);
        return s;
    });
    const elegidos = lista.filter(c => sel.has(c.client_id));
    const asignar = () => {
        onAsignar(elegidos.map(c => ({ id: c.client_id, nombre: c.name })));
        setSel(new Set());
    };
    return (
        <div className="bg-[#0A0A0A] rounded-xl border border-[#222] p-3">
            <div className="flex items-center gap-2 mb-1">
                {Icono && <Icono className="w-4 h-4" style={{ color }} />}
                <span className="text-sm font-bold text-white">{titulo}</span>
                <span className="ml-auto text-sm font-bold" style={{ color }}>{lista.length}</span>
            </div>
            {sub && <p className="text-[10px] text-white/30 mb-2">{sub}</p>}
            <div className={`space-y-0.5 overflow-y-auto ${maxAlto}`}>
                {lista.length === 0 && <Vacio frase={vacio} />}
                {lista.map(c => (
                    <div key={c.client_id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5">
                        <input type="checkbox" checked={sel.has(c.client_id)} onChange={() => toggle(c.client_id)}
                            className="accent-[#FF671F] flex-shrink-0 cursor-pointer" />
                        <button onClick={() => navigate(`/admin/clients/${c.client_id}`)}
                            className="flex-1 min-w-0 flex items-center gap-2 text-left">
                            {/* EL NOMBRE MANDA, EL CHIP CEDE (24-08). El nombre era lo único
                                elástico de la fila -- el chip, el extra y la flecha entran fijos --
                                así que el chip se metía con su ancho entero («EL LUNES EMPIEZO»
                                mide 154 px, y es el plan de la mitad de la gente) y en las columnas
                                estrechas el nombre se quedaba en dos letras: «J...», «F...».
                                Ahora el chip cede dos veces: no pasa de la mitad del hueco Y suelta
                                lo que haga falta antes de que el nombre baje de 6,5rem. El suelo va
                                en la fila y no en la rejilla a propósito: esta lista la pintan las
                                cuatro pestañas y no puede depender de en cuántas columnas la metan.
                                Medido de 360 a 1920 px: el peor sitio deja 111 px de nombre (antes,
                                12) y en ninguno se desborda la tarjeta. */}
                            <span className="flex-1 min-w-[6.5rem] truncate text-sm text-white/80" title={c.name}>{c.name}</span>
                            {/* El plan entero al pasar el ratón, pero sin el «(legacy)»: el chip lo
                                quita porque es info interna (ClientDashboard, PlanBadge) y el globo
                                no puede colarlo por la puerta de atrás. */}
                            <span className="min-w-0 max-w-[50%] [&>span]:block [&>span]:truncate"
                                title={(c.plan_nombre || '').replace(/\s*\(legacy\)/i, '').trim()}>
                                <PlanBadge plan={c.plan} planName={c.plan_nombre} />
                            </span>
                        </button>
                        {extra && <span className="flex-shrink-0">{extra(c)}</span>}
                        <ChevronRight className="w-3.5 h-3.5 text-white/20 flex-shrink-0" />
                    </div>
                ))}
            </div>
            {lista.length > 0 && (
                <div className="mt-2 pt-2 border-t border-[#1A1A1A] flex justify-end">
                    <Button size="sm" variant="outline" disabled={elegidos.length === 0} onClick={asignar}
                        className="border-[#333] text-white/70 hover:bg-white/5 hover:text-white text-xs h-7">
                        <ClipboardList className="w-3.5 h-3.5 mr-1" />
                        Asignar tarea{elegidos.length > 0 ? ` (${elegidos.length})` : ''}
                    </Button>
                </div>
            )}
        </div>
    );
};

// Una lista de tareas (no de clientes): sin checkbox, que aquí no se asigna nada.
const ListaTareas = ({ tareas, vacio = 'Nada pendiente' }) => (
    <div className="space-y-0.5 max-h-72 overflow-y-auto">
        {(!tareas || tareas.length === 0) && <Vacio frase={vacio} />}
        {(tareas || []).map((t, i) => (
            <div key={t.id || i} className="px-2 py-1.5 rounded-lg hover:bg-white/5">
                <p className="text-sm text-white/80">{t.que}</p>
                <p className="text-[11px] text-white/40">
                    {t.sobre_quien_nombre ? `Sobre ${t.sobre_quien_nombre}` : ''}
                    {t.sobre_quien_nombre && t.para_cuando ? ' · ' : ''}
                    {t.para_cuando ? `para el ${t.para_cuando}` : ''}
                </p>
            </div>
        ))}
    </div>
);

// El número gordo de Dirección: tarjeta grande que al pincharla despliega su lista.
const NumeroGordo = ({ etiqueta, valor, detalle, icono: Icono, color = '#FF671F', abierto, onToggle, desplegable = true }) => (
    <button onClick={desplegable ? onToggle : undefined}
        className={`bg-[#111111] border rounded-xl p-5 text-left w-full transition-colors
            ${abierto ? 'border-[#FF671F]/50' : 'border-[#222]'} ${desplegable ? 'hover:bg-white/5 cursor-pointer' : 'cursor-default'}`}>
        <div className="flex items-center gap-2">
            {Icono && <Icono className="w-4 h-4" style={{ color }} />}
            <Titulo>{etiqueta}</Titulo>
            {desplegable && (abierto
                ? <ChevronDown className="w-4 h-4 text-white/30 ml-auto" />
                : <ChevronRight className="w-4 h-4 text-white/30 ml-auto" />)}
        </div>
        <p className="text-3xl font-bold text-white mt-2 tabular-nums">{valor}</p>
        {detalle && <p className="text-[11px] text-white/40 mt-1">{detalle}</p>}
    </button>
);

// El importe previsto de una renovación, con su lapicito: se corrige a mano, y con
// «auto» se vuelve al calculado (importe null en el PUT).
const ImporteEditable = ({ cliente, api, onGuardado }) => {
    const [editando, setEditando] = useState(false);
    const [valor, setValor] = useState('');
    const [guardando, setGuardando] = useState(false);
    const guardar = async (importe) => {
        setGuardando(true);
        try {
            await api.put(`/admin/paneles/direccion/prevision/${cliente.client_id}`, { importe });
            setEditando(false);
            onGuardado();
        } catch (e) {
            console.error('[prevision] no se pudo guardar el importe', e);
            toast.error(mensajeDeError(e, 'No se pudo guardar el importe.'));
        } finally {
            setGuardando(false);
        }
    };
    if (!editando) {
        return (
            <span className="flex items-center gap-1">
                <span className="text-xs text-white/70 tabular-nums">{eur(cliente.importe)}</span>
                <button onClick={() => { setValor(cliente.importe ?? ''); setEditando(true); }}
                    className="text-white/25 hover:text-white/70" title="Corregir el importe a mano">
                    <Pencil className="w-3 h-3" />
                </button>
            </span>
        );
    }
    return (
        <span className="flex items-center gap-1">
            <Input type="number" value={valor} onChange={e => setValor(e.target.value)} autoFocus
                onKeyDown={e => { if (e.key === 'Enter') guardar(valor === '' ? null : Number(valor)); if (e.key === 'Escape') setEditando(false); }}
                className="bg-[#0A0A0A] border-[#333] text-white h-6 w-20 text-xs px-1" />
            <button onClick={() => guardar(valor === '' ? null : Number(valor))} disabled={guardando}
                className="text-emerald-400 hover:text-emerald-300" title="Guardar">
                <Check className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => guardar(null)} disabled={guardando}
                className="text-[10px] text-white/40 hover:text-white/70 uppercase" title="Volver al importe automático">
                auto
            </button>
            <button onClick={() => setEditando(false)} className="text-white/40 hover:text-white/70" title="Cancelar">
                <X className="w-3.5 h-3.5" />
            </button>
        </span>
    );
};

/* ============================== DIRECCIÓN ============================== */

const PanelDireccion = ({ api, onAsignar }) => {
    const [datos, setDatos] = useState(null);
    const [error, setError] = useState(false);
    const [abierto, setAbierto] = useState(null); // qué número gordo está desplegado

    const cargar = useCallback(() => {
        api.get('/admin/paneles/direccion')
            .then(r => { setDatos(r.data); setError(false); })
            .catch(e => { console.error('[paneles/direccion]', e); setError(true); });
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    if (error) return <p className="text-white/40 text-sm py-8 text-center">No hemos podido cargar el panel de Dirección. Recarga la página.</p>;
    if (!datos) return <Cargando />;

    const entra = datos.entra_esta_semana || {};
    const cartera = datos.cartera || {};
    const ab = datos.altas_bajas || {};
    const toggle = (k) => setAbierto(prev => (prev === k ? null : k));
    const delta = cartera.delta_semana;

    return (
        <div className="space-y-4">
            {/* Los cuatro números gordos. Cada uno despliega su lista debajo. */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <NumeroGordo etiqueta="Entra esta semana" icono={Receipt} color="#FF671F"
                    valor={eur((entra.confirmado || 0) + (entra.por_confirmar || 0))}
                    detalle={`${eur(entra.confirmado)} confirmado · ${eur(entra.por_confirmar)} por confirmar`}
                    abierto={abierto === 'entra'} onToggle={() => toggle('entra')} />
                <NumeroGordo etiqueta="Cartera activa" icono={Users} color="#0EA5E9"
                    valor={cartera.activos ?? '-'}
                    detalle={[
                        // El criterio (20-08): la cartera son los que PAGAN. Los con
                        // acceso a 0 EUR se dicen aquí, no se suman.
                        cartera.con_acceso != null && cartera.con_acceso !== cartera.activos
                            ? `pagando, de ${cartera.con_acceso} con acceso` : null,
                        delta === null || delta === undefined ? 'sin comparación semanal todavía'
                            : `${delta > 0 ? '+' : ''}${delta} esta semana`,
                    ].filter(Boolean).join(' · ')}
                    desplegable={false}
                    abierto={false} onToggle={() => {}} />
                <NumeroGordo etiqueta="Altas y bajas" icono={UserPlus} color="#22C55E"
                    valor={`+${ab.altas || 0} / -${ab.bajas || 0}`}
                    detalle="Esta semana"
                    abierto={abierto === 'altasbajas'} onToggle={() => toggle('altasbajas')} />
                <NumeroGordo etiqueta="Factura al mes" icono={TrendingUp} color="#EAB308"
                    valor={eur(datos.factura_mes)}
                    detalle={`${datos.a_cero || 0} activos a cero`}
                    abierto={abierto === 'factura'} onToggle={() => toggle('factura')} />
            </div>

            {/* La lista del número pinchado. */}
            {abierto === 'entra' && (
                <ListaSeleccionable titulo="Entra esta semana" icono={Receipt}
                    sub="Verde confirmado, ámbar por confirmar, azul corregido a mano"
                    items={entra.clientes} vacio="Nadie esta semana" onAsignar={onAsignar}
                    extra={(c) => (
                        <span className="flex items-center gap-2">
                            <span className="text-[10px] text-white/40">{c.fecha_label || c.fecha}</span>
                            <span className={`text-xs tabular-nums font-bold ${(ESTADO[c.estado] || {}).clase || 'text-white/60'}`}>{eur(c.importe)}</span>
                            <PuntoEstado estado={c.estado} />
                        </span>
                    )} />
            )}
            {abierto === 'altasbajas' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <ListaSeleccionable titulo="Altas" icono={UserPlus} color="#22C55E"
                        items={ab.altas_clientes} vacio="Ninguna esta semana" onAsignar={onAsignar} />
                    <ListaSeleccionable titulo="Bajas" icono={Users} color="#EF4444"
                        items={ab.bajas_clientes} vacio="Ninguna esta semana" onAsignar={onAsignar} />
                </div>
            )}
            {abierto === 'factura' && (
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-5">
                        <Titulo>Reparto por plan</Titulo>
                        <div className="mt-3 space-y-0.5">
                            {(datos.reparto_por_plan || []).length === 0 && <Vacio frase="Sin datos de reparto" />}
                            {(datos.reparto_por_plan || []).map(p => (
                                <div key={p.plan} className="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-white/5">
                                    <span className="flex-1 min-w-0 truncate text-sm text-white/80">{p.nombre || p.plan}</span>
                                    <span className="text-xs text-white/40 tabular-nums">{p.n} clientes</span>
                                    <span className="text-sm font-bold text-white tabular-nums w-24 text-right">{eur(p.eur_mes)}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* La previsión de las cuatro semanas que vienen, con el importe editable. */}
            <Card className="bg-[#111111] border-[#222]">
                <CardContent className="p-5">
                    <Titulo>Previsión de renovaciones (4 semanas)</Titulo>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-3">
                        {(datos.prevision || []).map((sem, i) => (
                            <div key={i} className="bg-[#0A0A0A] rounded-xl border border-[#222] p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-bold text-white/60">{sem.etiqueta}</span>
                                    <span className="text-sm font-bold text-[#FF671F] tabular-nums">{eur(sem.total)}</span>
                                </div>
                                <ListaPrevision clientes={sem.clientes} api={api} recargar={cargar} onAsignar={onAsignar} />
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {/* DE DÓNDE VIENEN LOS QUE ENTRAN: los leads de las últimas 4 semanas por
                    origen. Si GHL no manda, sale cero y se dice desde cuándo: un cero que
                    se explica vale; un cero mudo parece que no entra nadie. */}
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-4">
                        <Titulo>De dónde vienen los que entran</Titulo>
                        {(datos.origenes?.total || 0) > 0 ? (
                            <div className="mt-2 space-y-1">
                                {datos.origenes.por_origen.map(o => (
                                    <div key={o.origen} className="flex items-center justify-between text-sm">
                                        <span className="text-white/70 capitalize">{o.origen}</span>
                                        <span className="text-white font-bold tabular-nums">{o.n}</span>
                                    </div>
                                ))}
                                <p className="text-[10px] text-white/30 pt-1">Últimas 4 semanas</p>
                            </div>
                        ) : (
                            <p className="text-xs text-white/40 mt-2">
                                Sin leads en 4 semanas.
                                {datos.origenes?.ultimo_lead
                                    ? ` El último llegó el ${new Date(datos.origenes.ultimo_lead).toLocaleDateString('es-ES')}: GHL no está mandando.`
                                    : ' GHL no está mandando.'}
                            </p>
                        )}
                    </CardContent>
                </Card>
                {(datos.sin_conectar || []).map((b, i) => <TarjetaApagada key={i} bloque={b.bloque} motivo={b.motivo} />)}
            </div>
        </div>
    );
};

// Las filas de una semana de previsión: nombre, importe con lapicito, estado y
// la misma selección para asignar tarea que en el resto de listas.
const ListaPrevision = ({ clientes, api, recargar, onAsignar }) => {
    const navigate = useNavigate();
    const [sel, setSel] = useState(() => new Set());
    const lista = clientes || [];
    const toggle = (id) => setSel(prev => {
        const s = new Set(prev);
        if (s.has(id)) s.delete(id); else s.add(id);
        return s;
    });
    const elegidos = lista.filter(c => sel.has(c.client_id));
    return (
        <div>
            <div className="space-y-0.5 max-h-56 overflow-y-auto">
                {lista.length === 0 && <Vacio frase="Nadie esta semana" />}
                {lista.map(c => (
                    <div key={c.client_id} className="flex items-center gap-2 px-1 py-1 rounded-lg hover:bg-white/5">
                        <input type="checkbox" checked={sel.has(c.client_id)} onChange={() => toggle(c.client_id)}
                            className="accent-[#FF671F] flex-shrink-0 cursor-pointer" />
                        <button onClick={() => navigate(`/admin/clients/${c.client_id}`)}
                            className="flex-1 min-w-0 truncate text-left text-xs text-white/80 hover:text-white">
                            {c.name}
                        </button>
                        <ImporteEditable cliente={c} api={api} onGuardado={recargar} />
                        <PuntoEstado estado={c.estado} />
                    </div>
                ))}
            </div>
            {lista.length > 0 && (
                <div className="mt-2 pt-2 border-t border-[#1A1A1A] flex justify-end">
                    <Button size="sm" variant="outline" disabled={elegidos.length === 0}
                        onClick={() => { onAsignar(elegidos.map(c => ({ id: c.client_id, nombre: c.name }))); setSel(new Set()); }}
                        className="border-[#333] text-white/70 hover:bg-white/5 hover:text-white text-[10px] h-6 px-2">
                        Asignar tarea{elegidos.length > 0 ? ` (${elegidos.length})` : ''}
                    </Button>
                </div>
            )}
        </div>
    );
};

/* ============================== ENTRENADOR ============================== */

const PanelEntrenador = ({ api, user, onAsignar, irAOperaciones }) => {
    const [datos, setDatos] = useState(null);
    const [error, setError] = useState(false);
    const [trainerId, setTrainerId] = useState('');
    const esAdmin = user?.role === 'admin';

    useEffect(() => {
        setDatos(null);
        const params = trainerId ? { trainer_id: trainerId } : {};
        api.get('/admin/paneles/entrenador', { params })
            .then(r => { setDatos(r.data); setError(false); })
            .catch(e => { console.error('[paneles/entrenador]', e); setError(true); });
    }, [api, trainerId]);

    if (error) return <p className="text-white/40 text-sm py-8 text-center">No hemos podido cargar el panel del entrenador. Recarga la página.</p>;
    if (!datos) return <Cargando />;

    const rep = datos.reporte || {};
    const todoVacio = ['mandados', 'les_toca', 'aplazados'].every(k => !(rep[k] || []).length)
        && !(datos.macros_por_entregar || []).length && !(datos.fotos_nuevas || []).length
        && !(datos.cayendo || []).length;

    return (
        <div className="space-y-4">
            {esAdmin && (datos.equipo || []).length > 0 && (
                <div className="flex items-center gap-3">
                    <Titulo>Entrenador</Titulo>
                    <select value={trainerId || datos.trainer?.id || ''} onChange={e => setTrainerId(e.target.value)}
                        className="bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-1.5">
                        {(datos.equipo || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                </div>
            )}

            {(datos.sin_asignar || 0) > 0 && todoVacio && (
                <Card className="bg-[#111111] border-amber-500/30">
                    <CardContent className="p-4 flex items-center gap-3">
                        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                        <p className="text-sm text-white/70 flex-1">
                            Este panel se llena cuando los clientes tengan entrenador asignado: hay {datos.sin_asignar} sin asignar.
                        </p>
                        {esAdmin && irAOperaciones && (
                            <Button size="sm" variant="outline" onClick={irAOperaciones}
                                className="border-[#333] text-white/70 hover:bg-white/5 hover:text-white text-xs h-7">
                                Ir a Operaciones
                            </Button>
                        )}
                    </CardContent>
                </Card>
            )}

            <Card className="bg-[#111111] border-[#222]">
                <CardContent className="p-5">
                    <Titulo>El reporte semanal</Titulo>
                    {/* Dos columnas hasta 2xl, igual que en Operaciones y por lo mismo (el porqué,
                        con las medidas, está en el comentario de PanelOperaciones): a un tercio de
                        pantalla el nombre se quedaba en una letra. Aquí importa más todavía, que
                        el entrenador solo ve ESTA pestaña. */}
                    <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4 mt-3">
                        <ListaSeleccionable titulo="Lo han mandado" icono={ClipboardList} color="#22C55E"
                            sub="Por revisar y contestar" items={rep.mandados} onAsignar={onAsignar} />
                        <ListaSeleccionable titulo="Les toca" icono={CalendarClock} color="#EAB308"
                            sub="Aún no lo han mandado" items={rep.les_toca} onAsignar={onAsignar} />
                        <ListaSeleccionable titulo="Aplazados" icono={CalendarClock} color="#A855F7"
                            sub="Pidieron aplazarlo: han avisado" items={rep.aplazados} onAsignar={onAsignar}
                            extra={(c) => (
                                <span className="flex items-center gap-2">
                                    {c.seguidos >= 2 && <span className="text-[9px] text-red-400 font-bold uppercase">{c.seguidos} seguidos</span>}
                                    {c.aplazado_hasta && <span className="text-[10px] text-white/40">{c.aplazado_hasta}</span>}
                                </span>
                            )} />
                    </div>
                </CardContent>
            </Card>

            {/* Dos columnas hasta 2xl: mismo motivo que arriba. */}
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
                <ListaSeleccionable titulo="Macros por entregar" icono={ClipboardList} color="#FF671F"
                    sub="Mandaron reporte y esperan sus macros" items={datos.macros_por_entregar} onAsignar={onAsignar}
                    extra={(c) => c.reporte_el ? <span className="text-[10px] text-white/40">desde el {c.reporte_el}</span> : null} />
                {/* «SIN MIRAR» ERA MENTIRA: nadie apunta quién ha visto una foto. El dato son
                    las fotos con `uploaded_at` de los últimos 7 días (routes/paneles.py), así
                    que la lista no se vacía al repasarlas, se vacía sola a la semana. El
                    rótulo dice ahora lo que hay; marcar quién las ha mirado sería otra cosa. */}
                <ListaSeleccionable titulo="Fotos nuevas" icono={Camera} color="#0EA5E9"
                    sub="Subidas en los últimos 7 días" items={datos.fotos_nuevas} onAsignar={onAsignar}
                    extra={(c) => (
                        <span className="text-[10px] text-white/40 tabular-nums">
                            {c.n_fotos ? `${c.n_fotos} fotos` : ''}{c.ultima ? ` · ${c.ultima}` : ''}
                        </span>
                    )} />
                <ListaSeleccionable titulo="Se están cayendo" icono={AlertTriangle} color="#EF4444"
                    sub="Señales de abandono" items={datos.cayendo} onAsignar={onAsignar}
                    extra={(c) => c.motivo ? <span className="text-[10px] text-white/40 truncate max-w-[10rem]" title={c.motivo}>{c.motivo}</span> : null} />
            </div>
        </div>
    );
};

/* ============================== OPERACIONES ============================== */

const PanelOperaciones = ({ api, onAsignar }) => {
    const [datos, setDatos] = useState(null);
    const [error, setError] = useState(false);
    const [hechas, setHechas] = useState('');
    const [total, setTotal] = useState('');
    const [guardandoLista, setGuardandoLista] = useState(false);

    useEffect(() => {
        api.get('/admin/paneles/operaciones')
            .then(r => {
                setDatos(r.data);
                setError(false);
                const lf = r.data?.lista_francisco || {};
                setHechas(lf.hechas ?? '');
                setTotal(lf.total ?? '');
            })
            .catch(e => { console.error('[paneles/operaciones]', e); setError(true); });
    }, [api]);

    const guardarLista = async () => {
        setGuardandoLista(true);
        try {
            await api.put('/admin/paneles/operaciones/lista', {
                hechas: hechas === '' ? null : Number(hechas),
                total: total === '' ? null : Number(total),
            });
            toast.success('Lista guardada');
        } catch (e) {
            console.error('[paneles/operaciones/lista]', e);
            toast.error(mensajeDeError(e, 'No se pudo guardar la lista.'));
        } finally {
            setGuardandoLista(false);
        }
    };

    if (error) return <p className="text-white/40 text-sm py-8 text-center">No hemos podido cargar el panel de Operaciones. Recarga la página.</p>;
    if (!datos) return <Cargando />;

    const sinRellenar = (datos.lista_francisco?.hechas ?? null) === null && (datos.lista_francisco?.total ?? null) === null && hechas === '' && total === '';

    return (
        <div className="space-y-4">
            {/* «Lo que está bloqueado esperando una decisión de Jesús» va arriba del todo: lo dice el doc. */}
            <Card className="bg-[#111111] border-[#FF671F]/30">
                <CardContent className="p-5">
                    <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-[#FF671F]" />
                        <Titulo>Esperando una decisión de Jesús</Titulo>
                        <span className="ml-auto text-sm font-bold text-[#FF671F]">{(datos.esperando_a_jesus || []).length}</span>
                    </div>
                    <div className="mt-2">
                        <ListaTareas tareas={datos.esperando_a_jesus} vacio="Nada bloqueado" />
                    </div>
                </CardContent>
            </Card>

            {/* DOS COLUMNAS HASTA 2XL (24-08). Con tres, medido en pantalla: a 1440 px la
                tarjeta se queda en 361 px y al nombre le sobran 85; a 1280, 58; a 1100, 28.
                No hay recorte de chip que salve un tercio de pantalla con checkbox, nombre,
                plan, tipo, hora y flecha en la misma línea. En dos columnas el nombre pasa
                de 85 a 214 px a 1440, y las cuatro listas quedan en un 2x2 en vez de 3+1.
                La misma regla va en las dos rejillas de Entrenador, que son iguales de
                estrechas: si se cambia aquí, se cambia allí. */}
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
                <ListaSeleccionable titulo="Cierra hoy" icono={CalendarClock} color="#EF4444"
                    sub="Plazos que vencen hoy" items={datos.cierra_hoy} onAsignar={onAsignar} vacio="Nada cierra hoy"
                    extra={(c) => {
                        // Solo la hora: el día ya lo dice el título («cierra HOY») y el ISO
                        // entero aplastaba el nombre.
                        let hora = '';
                        try {
                            hora = new Date(c.cierra).toLocaleTimeString('es-ES',
                                { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });
                        } catch { /* sin hora, se queda el tipo solo */ }
                        return <span className="text-[10px] text-white/40">{c.tipo}{hora ? ` · ${hora}` : ''}</span>;
                    }} />
                {/* P64: solo cuentan los clientes cuyo plan LLEVA entrenador (el filtro
                    vive en el backend): a los de ELM o Mantenimiento no les falta nadie. */}
                <ListaSeleccionable titulo="Sin entrenador" icono={Users} color="#EAB308"
                    sub="Su plan lleva entrenador y no tienen a nadie asignado"
                    items={datos.sin_entrenador?.clientes} onAsignar={onAsignar} />
                <ListaSeleccionable titulo="Sin datos" icono={AlertTriangle} color="#A855F7"
                    sub="Les falta algo para poder trabajar" items={datos.sin_datos?.clientes} onAsignar={onAsignar}
                    extra={(c) => c.falta ? <span className="text-[10px] text-white/40 truncate max-w-[9rem]" title={c.falta}>{c.falta}</span> : null} />
                {/* Datos IMPOSIBLES (tarea 1.4): valores que la API no dejaría escribir
                    (edad 5, estatura 1 cm) y que entraron por la importación de Calma.
                    Lista aparte de «Sin datos»: aquello es lo que falta; esto es lo que
                    está mal y hay que corregir con el cliente delante. Sus macros se
                    rotulan «Provisionales» hasta que se arregle. */}
                <ListaSeleccionable titulo="Datos imposibles" icono={AlertTriangle} color="#EF4444"
                    sub="Valores fuera de rango en su ficha" items={datos.datos_imposibles?.clientes}
                    onAsignar={onAsignar} vacio="Ninguno"
                    extra={(c) => c.imposible ? <span className="text-[10px] text-white/40 truncate max-w-[9rem]" title={c.imposible}>{c.imposible}</span> : null} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-5">
                        <Titulo>Tareas vencidas por persona</Titulo>
                        <div className="mt-2 space-y-3">
                            {(datos.tareas_vencidas || []).length === 0 && <Vacio frase="Nadie con tareas vencidas" />}
                            {(datos.tareas_vencidas || []).map((p, i) => (
                                <div key={p.a_quien || i} className="bg-[#0A0A0A] rounded-xl border border-[#222] p-3">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm font-bold text-white">{p.a_quien_nombre || 'Sin nombre'}</span>
                                        <span className="ml-auto text-sm font-bold text-red-400">{p.n}</span>
                                    </div>
                                    <ListaTareas tareas={p.tareas} vacio="Ninguna" />
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#111111] border-[#222]">
                    <CardContent className="p-5">
                        <Titulo>La lista de Francisco</Titulo>
                        {sinRellenar && <p className="text-[11px] text-white/40 mt-1">Sin rellenar todavía.</p>}
                        <div className="flex items-center gap-2 mt-3">
                            <Input type="number" value={hechas} onChange={e => setHechas(e.target.value)} placeholder="Hechas"
                                className="bg-[#0A0A0A] border-[#333] text-white h-8 w-24 text-sm" />
                            <span className="text-white/40 text-sm">de</span>
                            <Input type="number" value={total} onChange={e => setTotal(e.target.value)} placeholder="Total"
                                className="bg-[#0A0A0A] border-[#333] text-white h-8 w-24 text-sm" />
                            <Button size="sm" onClick={guardarLista} disabled={guardandoLista}
                                className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-8">
                                {guardandoLista ? 'Guardando…' : 'Guardar'}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

/* ============================== SOPORTE ============================== */

const PanelSoporte = ({ api, onAsignar }) => {
    const [datos, setDatos] = useState(null);
    const [misTareas, setMisTareas] = useState(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        api.get('/admin/paneles/soporte')
            .then(r => { setDatos(r.data); setError(false); })
            .catch(e => { console.error('[paneles/soporte]', e); setError(true); });
        // Mis tareas de hoy: el endpoint devuelve los grupos en la raíz (vencidas, hoy,
        // próximas), pero se lee con red por si algún día vienen bajo `mias`.
        api.get('/admin/tareas')
            .then(r => setMisTareas(r.data?.mias || r.data || null))
            .catch(e => { console.error('[tareas mias]', e); setMisTareas(null); });
    }, [api]);

    if (error) return <p className="text-white/40 text-sm py-8 text-center">No hemos podido cargar el panel de Soporte. Recarga la página.</p>;
    if (!datos) return <Cargando />;

    const tareasHoy = [...(misTareas?.vencidas || []), ...(misTareas?.hoy || [])];

    return (
        <div className="space-y-4">
            <Card className="bg-[#111111] border-[#222]">
                <CardContent className="p-5">
                    <div className="flex items-center gap-2">
                        <ClipboardList className="w-4 h-4 text-[#FF671F]" />
                        <Titulo>Mis tareas de hoy</Titulo>
                        <span className="ml-auto text-sm font-bold text-[#FF671F]">{tareasHoy.length}</span>
                    </div>
                    <div className="mt-2 space-y-0.5 max-h-72 overflow-y-auto">
                        {tareasHoy.length === 0 && <Vacio frase="Nada para hoy" />}
                        {tareasHoy.map((t, i) => (
                            <div key={t.id || i} className="px-2 py-1.5 rounded-lg hover:bg-white/5 flex items-center gap-2">
                                <span className="flex-1 min-w-0">
                                    <span className="block text-sm text-white/80 truncate">{t.que}</span>
                                    {t.sobre_quien_nombre && <span className="block text-[11px] text-white/40">Sobre {t.sobre_quien_nombre}</span>}
                                </span>
                                {(misTareas?.vencidas || []).includes(t)
                                    ? <span className="text-[9px] text-red-400 font-bold uppercase">vencida</span>
                                    : <span className="text-[10px] text-white/40">hoy</span>}
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            <ListaSeleccionable titulo="Renovaciones por contactar" icono={RefreshCw} color="#FF671F"
                sub="Verde confirmado, ámbar por confirmar, azul corregido a mano"
                items={datos.renovacion} onAsignar={onAsignar} vacio="Nadie esta semana"
                extra={(c) => (
                    <span className="flex items-center gap-2">
                        {c.telefono && (
                            <a href={`tel:${c.telefono}`} onClick={e => e.stopPropagation()}
                                className="text-white/40 hover:text-white" title={c.telefono}>
                                <Phone className="w-3.5 h-3.5" />
                            </a>
                        )}
                        <span className="text-[10px] text-white/40">
                            {c.fecha_label || c.fecha}{c.semana ? ` · semana ${c.semana}/${c.semanas_ciclo}` : ''}
                        </span>
                        <span className={`text-xs tabular-nums font-bold ${(ESTADO[c.estado] || {}).clase || 'text-white/60'}`}>{eur(c.importe)}</span>
                        <PuntoEstado estado={c.estado} />
                    </span>
                )} />

            {/* «Sin contactar» NO SE PINTA (doc 21-08). El dato solo cuenta el chat interno
                y el webhook de GHL: ni el feedback de reportes ni los ajustes de macros
                cuentan como contacto, así que el «177 · nunca» era falso. Fuera hasta que
                el contacto se pueda registrar; el backend sigue mandando `sin_contactar`. */}
            <ListaSeleccionable titulo="Problemas de pago" icono={AlertTriangle} color="#EF4444"
                sub="Cobros fallidos o pagos parados" items={datos.problemas_pago} onAsignar={onAsignar}
                extra={(c) => c.motivo ? <span className="text-[10px] text-white/40 truncate max-w-[10rem]" title={c.motivo}>{c.motivo}</span> : null} />

            {(datos.sin_conectar || []).length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    {datos.sin_conectar.map((b, i) => <TarjetaApagada key={i} bloque={b.bloque} motivo={b.motivo} />)}
                </div>
            )}
        </div>
    );
};

/* ============================== LA PÁGINA ============================== */

const PESTANAS = [
    { key: 'direccion',   label: 'Dirección',   icono: Briefcase },
    { key: 'entrenador',  label: 'Entrenador',  icono: Dumbbell },
    { key: 'operaciones', label: 'Operaciones', icono: Wrench },
    { key: 'soporte',     label: 'Soporte',     icono: Headphones },
];

const AdminPanelesPage = () => {
    const { api, user } = useAuth();
    const esTrainer = user?.role === 'trainer';
    // El entrenador solo ve SU panel; el admin, las cuatro con Dirección primero.
    const pestanas = esTrainer ? PESTANAS.filter(p => p.key === 'entrenador') : PESTANAS;
    const [activa, setActiva] = useState(esTrainer ? 'entrenador' : 'direccion');
    // Las visitadas se quedan montadas (ocultas) para no perder selecciones ni ediciones,
    // pero ninguna carga hasta que se abre: cada pestaña pide su endpoint al montarse.
    const [visitadas, setVisitadas] = useState(() => new Set([esTrainer ? 'entrenador' : 'direccion']));
    const abrir = (key) => {
        setActiva(key);
        setVisitadas(prev => new Set(prev).add(key));
    };
    // El modal de asignar tarea: UNO para toda la página. Cada lista manda aquí
    // su selección como [{id, nombre}].
    const [tareaSobre, setTareaSobre] = useState(null);
    const onAsignar = useCallback((sobre) => setTareaSobre(sobre), []);
    const irAOperaciones = useCallback(() => abrir('operaciones'), []); // eslint-disable-line react-hooks/exhaustive-deps

    const paneles = {
        direccion:   <PanelDireccion api={api} onAsignar={onAsignar} />,
        entrenador:  <PanelEntrenador api={api} user={user} onAsignar={onAsignar} irAOperaciones={esTrainer ? null : irAOperaciones} />,
        operaciones: <PanelOperaciones api={api} onAsignar={onAsignar} />,
        soporte:     <PanelSoporte api={api} onAsignar={onAsignar} />,
    };

    return (
        <div className="p-4 md:p-6 space-y-4" data-testid="admin-paneles">
            <div className="flex items-center gap-2 flex-wrap">
                {pestanas.map(p => (
                    <button key={p.key} onClick={() => abrir(p.key)} data-testid={`panel-tab-${p.key}`}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-colors
                            ${activa === p.key
                                ? 'bg-[#FF671F] text-white'
                                : 'bg-[#111111] border border-[#222] text-white/50 hover:bg-white/5 hover:text-white'}`}>
                        <p.icono className="w-4 h-4" />
                        {p.label}
                    </button>
                ))}
            </div>

            {pestanas.map(p => visitadas.has(p.key) && (
                <div key={p.key} className={activa === p.key ? '' : 'hidden'}>
                    {paneles[p.key]}
                </div>
            ))}

            <AsignarTarea abierto={!!tareaSobre} sobre={tareaSobre || []}
                onClose={() => setTareaSobre(null)} />
        </div>
    );
};

export default AdminPanelesPage;
