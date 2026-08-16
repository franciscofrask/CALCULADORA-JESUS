/**
 * LOS AVISOS DEL EQUIPO: la lista de la campana y la tarjeta de las ventas.
 *
 * `avisar_al_equipo` llevaba meses escribiendo en `db.notifications` avisos que no pintaba
 * NADIE: la campana del panel solo sumaba leads nuevos y mensajes sin leer. Entre lo que se
 * estaba perdiendo hay dos cosas que son dinero, las dos del reporte mensual: el cliente que
 * marca la rutina del mes (57 euros) y el que pide que le cuenten el plan de arriba.
 *
 * Por eso lo de arriba del todo no es lo más reciente, es lo que es una venta, y por eso las
 * ventas salen ADEMÁS en una tarjeta del panel: una petición de compra que solo se ve
 * abriendo un desplegable depende de que a alguien se le ocurra abrirlo.
 *
 * Cada uno ve LO SUYO: el destinatario lo filtra el backend, aquí no se elige nada.
 */
import React from 'react';
import { AlertTriangle, ChevronRight, Loader2, ShoppingBag } from 'lucide-react';

/** "14:32" si es de hoy, "Ayer", y si no el día. Igual que en la campana del cliente. */
export const cuandoFue = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    const dias = Math.floor((new Date() - d) / 86400000);
    if (dias === 0) return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    if (dias === 1) return 'Ayer';
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
};

const Aviso = ({ aviso, onAbrir }) => {
    const nuevo = !aviso.read;
    return (
        <button
            type="button"
            onClick={() => onAbrir(aviso)}
            data-testid={`aviso-equipo-${aviso.type}`}
            className={`w-full text-left px-4 py-3 border-t border-[#1A1A1A] hover:bg-white/5 transition-colors ${
                aviso.dinero && nuevo ? 'bg-[#FF671F]/10' : ''}`}
        >
            <div className="flex items-start gap-2">
                {aviso.dinero && (
                    <span className="mt-0.5 shrink-0 text-[9px] font-bold uppercase tracking-wider bg-[#FF671F] text-white rounded px-1.5 py-0.5">
                        Venta
                    </span>
                )}
                <div className="min-w-0 flex-1">
                    <p className={`text-sm leading-tight ${nuevo ? 'text-white font-semibold' : 'text-white/50'}`}>
                        {aviso.etiqueta || aviso.title}
                    </p>
                    {aviso.client_name && (
                        <p className="text-xs text-[#FF671F] mt-0.5 truncate">{aviso.client_name}</p>
                    )}
                    {aviso.message && (
                        <p className="text-[11px] text-white/40 mt-1 leading-snug">{aviso.message}</p>
                    )}
                    <p className="text-[10px] text-white/30 mt-1">{cuandoFue(aviso.created_at)}</p>
                </div>
                {aviso.link && <ChevronRight className="w-4 h-4 text-white/20 shrink-0 mt-0.5" />}
            </div>
        </button>
    );
};

/** La lista que va dentro de la campana del panel. */
export const AvisosDelEquipo = ({ estado, onAbrir, onMarcarTodos }) => {
    const { items, cargando, error } = estado;

    if (cargando) {
        return (
            <p className="px-4 py-3 text-white/30 text-xs border-t border-[#1A1A1A] flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" /> Cargando avisos...
            </p>
        );
    }
    if (error) {
        return (
            <p className="px-4 py-3 text-white/40 text-xs border-t border-[#1A1A1A]">
                No hemos podido traer los avisos. Vuelve a abrir la campana en un momento.
            </p>
        );
    }
    if (!items.length) return null;

    const ventas = items.filter(a => a.dinero && !a.read);
    const resto = items.filter(a => !(a.dinero && !a.read));
    const sinLeer = items.filter(a => !a.read).length;

    return (
        <div data-testid="avisos-equipo">
            {ventas.length > 0 && (
                <>
                    <p className="px-4 py-2 text-[10px] font-bold uppercase tracking-wider border-t border-[#222] bg-[#FF671F]/15 text-[#FF671F] flex items-center gap-1.5">
                        <AlertTriangle className="w-3 h-3" />
                        Piden comprar ({ventas.length})
                    </p>
                    {ventas.map(a => <Aviso key={a.id} aviso={a} onAbrir={onAbrir} />)}
                </>
            )}
            {resto.length > 0 && (
                <>
                    <p className="px-4 py-2 text-[10px] font-bold text-white/40 uppercase tracking-wider border-t border-[#222]">
                        Del equipo
                    </p>
                    {resto.map(a => <Aviso key={a.id} aviso={a} onAbrir={onAbrir} />)}
                </>
            )}
            {sinLeer > 0 && (
                <button type="button" onClick={onMarcarTodos} data-testid="avisos-equipo-leer-todo"
                    className="w-full px-4 py-2.5 text-[11px] text-white/40 hover:text-white border-t border-[#222] text-center">
                    Marcar todos como leídos
                </button>
            )}
        </div>
    );
};

/**
 * La tarjeta de las peticiones de compra, encima de los KPIs y con la misma pinta que
 * "Piden que les llamemos": es gente esperando respuesta a un "quiero comprar". Desaparece
 * sola cuando no hay ninguna sin atender.
 */
export const PeticionesDeCompra = ({ estado, onAbrir, onAtendida }) => {
    const ventas = (estado.items || []).filter(a => a.dinero && !a.read);
    if (!ventas.length) return null;
    return (
        <div className="rounded-xl border border-[#FF671F]/40 bg-[#FF671F]/10 p-5"
            data-testid="peticiones-de-compra">
            <div className="flex items-center gap-2 mb-3">
                <ShoppingBag className="w-4 h-4 text-[#FF671F]" />
                <span className="text-sm font-bold text-white uppercase tracking-wider">
                    Piden comprar
                </span>
                <span className="bg-[#FF671F] text-white text-xs font-bold rounded px-2 py-0.5">
                    {ventas.length}
                </span>
                <span className="text-[11px] text-white/40 ml-auto hidden sm:block">
                    Nadie les ha contestado todavía
                </span>
            </div>
            <div className="space-y-2">
                {ventas.map(a => (
                    <div key={a.id}
                        className="flex flex-wrap items-center gap-2 bg-black/30 rounded-lg px-3 py-2.5">
                        <button type="button" onClick={() => onAbrir(a)}
                            className="min-w-0 flex-1 text-left"
                            data-testid={`peticion-compra-${a.type}`}>
                            <p className="text-white text-sm font-semibold leading-tight">
                                {a.etiqueta || a.title}
                            </p>
                            <p className="text-[11px] text-white/50 mt-0.5">
                                {[a.client_name, cuandoFue(a.created_at)].filter(Boolean).join(' · ')}
                            </p>
                        </button>
                        <button type="button" onClick={() => onAtendida(a)}
                            className="text-[11px] text-white/40 hover:text-white border border-white/15 rounded-lg px-2.5 py-1.5">
                            Atendida
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default AvisosDelEquipo;
