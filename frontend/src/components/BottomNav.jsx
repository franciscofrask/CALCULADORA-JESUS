/**
 * LA BARRA DE ABAJO DEL DOC DEL 21-08: INICIO · MI SEMANA · RUTINA · MÁS.
 *
 * Es la barra que llevan todos los mockups del documento. Vive detrás del interruptor
 * `t1_inicio_nuevo` -- el mismo del Inicio nuevo, para que el lunes se encienda todo
 * junto --: con él apagado, ClientLayout sigue pintando la barra de siempre (Inicio ·
 * Nutrición · Seguimiento · Perfil) y este componente ni se monta.
 *
 * «Más» abre una hoja con el resto de entradas del menú lateral. Aquí no se decide qué
 * ve cada plan: `items` es la MISMA lista que la barra lateral, ya filtrada por
 * capacidades en ClientLayout (can(cap) sobre NAV_ITEMS), así que la hoja enseña
 * exactamente lo que enseñaría el menú y no hay dos sitios donde mantener los candados.
 * Por lo mismo, «Rutina» solo sale si la lista la trae (cap `rutina` + interruptor
 * t3_entreno, que ya vienen resueltos).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Home, CalendarRange, Dumbbell, Menu, X } from 'lucide-react';

// testids ASCII-estables, el mismo criterio que ClientDashboard.
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-');

const BottomNav = ({ items = [], unread = 0, fichaPendiente = false }) => {
    const location = useLocation();
    const [hojaAbierta, setHojaAbierta] = useState(false);

    // Navegar cierra la hoja: si no, al volver atrás seguiría tapando la pantalla.
    useEffect(() => { setHojaAbierta(false); }, [location.pathname]);

    const tieneRutina = items.some(i => i.path === '/dashboard/routine');
    // SIN PLAN, SOLO EL INICIO (29-08). «Mi semana» se pone aquí a mano -- no viene en
    // `items` --, así que el recorte del menú lateral no la alcanzaba y en el teléfono
    // seguía saliendo una pestaña que rebota al Inicio. Se detecta por lo que llega: si al
    // layout solo le queda el Inicio, es que este cliente no tiene acceso.
    const soloInicio = !items.some(i => i.path !== '/dashboard' && i.path !== '/dashboard/profile');
    const principales = useMemo(() => ([
        { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
        // La página existe desde el rediseño del 21-08; esta es su primera puerta.
        ...(soloInicio ? [] : [{ path: '/dashboard/semana', icon: CalendarRange, label: 'Mi semana' }]),
        ...(tieneRutina ? [{ path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' }] : []),
    ]), [tieneRutina, soloInicio]);

    // La hoja: todo lo del menú lateral que no está ya en la barra. Inicio y Rutina se
    // quitan por ruta; «Mi semana» no viene en la lista (no tiene entrada lateral).
    const enLaBarra = new Set(principales.map(i => i.path));
    const delCajon = items.filter(i => !enLaBarra.has(i.path));

    // «Más» se enciende cuando la pantalla abierta es una de las suyas, igual que
    // cualquier otra pestaña: un botón que nunca se marca parece que no lleva a nada.
    const masActivo = delCajon.some(i => location.pathname.startsWith(i.path));

    const clasePestana = (activa) =>
        `flex flex-col items-center justify-center flex-1 min-w-0 gap-1 px-0.5 transition-colors ${activa ? 'text-brand' : 'text-white/55'}`;

    return (
        <>
            {/* La hoja de «Más», por encima de la barra y por debajo de los modales. */}
            {hojaAbierta && (
                <div className="lg:hidden fixed inset-0 z-[60]" data-testid="bottomnav-hoja">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setHojaAbierta(false)} />
                    <div className="absolute bottom-16 left-0 right-0 bg-card border-t border-border rounded-t-2xl shadow-xl max-h-[65vh] overflow-y-auto animate-slide-up pb-[env(safe-area-inset-bottom)]">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                            <p className="font-bold text-foreground uppercase tracking-wider text-sm">Más</p>
                            <button onClick={() => setHojaAbierta(false)} data-testid="bottomnav-hoja-cerrar"
                                className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="p-2 grid grid-cols-1">
                            {delCajon.map(item => (
                                <NavLink key={item.path} to={item.path} end={item.end}
                                    data-testid={`bottomnav-mas-${slug(item.label)}`}
                                    className={({ isActive }) => `flex items-center gap-3 px-3.5 py-3 rounded-xl transition-colors ${isActive ? 'bg-brand/10 text-brand font-semibold' : 'text-foreground hover:bg-muted'}`}>
                                    <span className="relative flex-shrink-0">
                                        <item.icon className="w-5 h-5" strokeWidth={2} />
                                        {item.path.includes('messages') && unread > 0 && (
                                            <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-brand text-white text-[10px] rounded-full flex items-center justify-center font-bold">{unread}</span>
                                        )}
                                        {/* Algo pendiente en la ficha (punto 111): el aviso
                                            de macros provisionales se fue de la pantalla de
                                            comer a Mi perfil, y esto es lo que lo dice. */}
                                        {item.path.includes('profile') && fichaPendiente && (
                                            <span data-testid="punto-ficha-pendiente-hoja"
                                                className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-pasado rounded-full" />
                                        )}
                                    </span>
                                    <span className="text-sm">{item.label}</span>
                                </NavLink>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-ink border-t border-white/10" data-testid="mobile-bottom-nav">
                <div className="flex items-stretch h-16">
                    {principales.map(item => (
                        <NavLink key={item.path} to={item.path} end={item.end}
                            className={({ isActive }) => clasePestana(isActive)}
                            data-testid={`bottomnav-${slug(item.label)}`}>
                            {({ isActive }) => (<>
                                <item.icon className="w-[22px] h-[22px] flex-shrink-0" strokeWidth={isActive ? 2.5 : 2} />
                                <span className={`text-[10px] max-w-full truncate ${isActive ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </>)}
                        </NavLink>
                    ))}
                    <button type="button" onClick={() => setHojaAbierta(a => !a)}
                        className={clasePestana(masActivo || hojaAbierta)} data-testid="bottomnav-mas">
                        <span className="relative">
                            <Menu className="w-[22px] h-[22px] flex-shrink-0" strokeWidth={masActivo ? 2.5 : 2} />
                            {unread > 0 && <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-brand rounded-full" />}
                            {/* Mi perfil vive dentro de «Más», así que sin esto el punto
                                de la ficha no se vería nunca sin abrir la hoja. */}
                            {!unread && fichaPendiente && <span data-testid="punto-ficha-pendiente-mas" className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-pasado rounded-full" />}
                        </span>
                        <span className={`text-[10px] max-w-full truncate ${masActivo ? 'font-bold' : 'font-medium'}`}>Más</span>
                    </button>
                </div>
            </nav>
        </>
    );
};

export default BottomNav;
