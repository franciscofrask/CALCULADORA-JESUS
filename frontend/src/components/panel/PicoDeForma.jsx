import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import { Loader2, Trophy } from 'lucide-react';
import { mensajeDeError } from '../../lib/mensajeDeError';

/**
 * EL PICO DE FORMA LO MARCA EL ENTRENADOR, AL CONTESTAR EL REPORTE (doc de Jesús del 2-09,
 * fase 3; 4-09).
 *
 * «Uno por ciclo, y lo marcas cuando lo ves, no cuando toca. Lo normal es que caiga al
 * final, pero puede caer antes, y entonces las últimas 4 semanas son de recomposición.»
 * Se marca aquí, en el modal del reporte, con su foto y su peso delante, y se puede mover
 * mientras el ciclo esté abierto: marcar otro reporte del mismo ciclo pisa al anterior.
 * Y el pico NO es el peso mínimo: son dos etiquetas distintas que caen en reportes
 * distintos, por eso las pastillas de abajo son tres y no una.
 *
 * Los datos del punto (a qué ciclo pertenece, qué etiquetas lleva, sus fotos) salen de
 * GET /admin/clients/{id}/puntos, que la lista de reportes pide una vez y comparte con
 * este bloque. Si el reporte no es un punto (un quincenal no lo es), el bloque no se pinta.
 */

// Las tres etiquetas de un punto, con su texto y su color: el pico en naranja, que es la
// que decide el entrenador; las dos del peso en gris, que las pone la báscula sola.
const ETIQUETAS_DEL_PUNTO = {
    pico_de_forma: ['Pico de forma', 'bg-[#FF671F]/20 text-[#FF671F]'],
    peso_maximo: ['Peso máximo', 'bg-white/10 text-white/50'],
    peso_minimo: ['Peso mínimo', 'bg-white/10 text-white/50'],
};

/** Las etiquetas de un punto como pastillas pequeñas (para la fila del reporte), siempre
 *  en el mismo orden (el pico primero) venga como venga la lista del servidor. */
export const EtiquetasDelPunto = ({ punto }) => {
    const etiquetas = Object.keys(ETIQUETAS_DEL_PUNTO).filter(e => (punto?.etiquetas || []).includes(e));
    if (!etiquetas.length) return null;
    return (
        <>
            {etiquetas.map(e => (
                <span key={e} data-testid={`etiqueta-${e}`}
                    className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded font-semibold whitespace-nowrap ${ETIQUETAS_DEL_PUNTO[e][1]}`}>
                    {ETIQUETAS_DEL_PUNTO[e][0]}
                </span>
            ))}
        </>
    );
};

// El punto de un reporte, por su id. Devuelve null si el reporte no es un punto.
export const puntoDelReporte = (puntos, reportId) =>
    (puntos?.puntos || []).find(p => p.report_id === reportId) || null;

// «3 de septiembre»: la fecha del otro reporte, para decir dónde está el pico ahora. Un día
// pelado (AAAA-MM-DD) se lleva al mediodía para que la zona horaria no lo mueva de día.
const fechaLarga = (f) => {
    if (!f) return '';
    const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(f) ? `${f}T12:00:00` : f);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
};

// La foto del reporte, de frente si la hay. Se baja por la API por su id, como el resto de
// fotos de la ficha, y se suelta al cerrar el modal. La `url` que trae el punto es un enlace
// firmado que caduca a los diez minutos: vale de respaldo, no de primera opción.
const FotoDelPunto = ({ api, foto }) => {
    const [src, setSrc] = useState(null);
    useEffect(() => {
        if (!foto?.id) { setSrc(foto?.url || null); return undefined; }
        let alive = true;
        let objeto = null;
        api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' })
            .then(r => { objeto = URL.createObjectURL(r.data); if (alive) setSrc(objeto); })
            .catch(() => { if (alive) setSrc(foto?.url || null); });
        return () => { alive = false; if (objeto) URL.revokeObjectURL(objeto); };
    }, [api, foto?.id, foto?.url]);
    if (!foto) return null;
    return src
        ? <img src={src} alt={foto.pose || 'Foto del reporte'} data-testid="pico-foto"
            className="w-12 h-16 object-cover rounded-md border border-[#222] bg-[#0A0A0A] flex-shrink-0" />
        : <div className="w-12 h-16 rounded-md border border-[#222] bg-[#0A0A0A] animate-pulse flex-shrink-0" />;
};

const PicoDeForma = ({ api, reporte, puntos, onCambio }) => {
    const [trabajando, setTrabajando] = useState(false);
    // La frase del 409 (ciclo cerrado, reporte sin ciclo...): se queda a la vista con el
    // botón apagado hasta que se abra otro reporte.
    const [bloqueo, setBloqueo] = useState(null);
    useEffect(() => { setBloqueo(null); }, [reporte?.id]);

    const punto = puntoDelReporte(puntos, reporte?.id);
    if (!punto) return null;

    // El ciclo del punto, SOLO por su id: el servidor manda también los tramos de antes del
    // cuaderno (`tramo:1`, aproximados) con el mismo número que un ciclo de verdad, así que
    // buscar por número casaría mal. Sin id, el reporte es de antes del cuaderno.
    const ciclos = puntos?.ciclos || [];
    const cicloId = punto.ciclo_id || reporte.ciclo_id || null;
    const ciclo = ciclos.find(c => c.id === cicloId) || null;
    const numero = ciclo?.numero ?? punto.ciclo_numero ?? reporte.ciclo_numero ?? null;
    const delCiclo = numero != null ? `del ciclo ${numero}` : 'de su ciclo';
    const esElPico = (punto.etiquetas || []).includes('pico_de_forma') || (!!ciclo && ciclo.pico_de_forma === reporte.id);
    // Otro reporte del mismo ciclo lleva el pico: se dice dónde está y que marcar aquí lo mueve.
    const otroId = ciclo?.pico_de_forma && ciclo.pico_de_forma !== reporte.id ? ciclo.pico_de_forma : null;
    const otro = otroId ? puntoDelReporte(puntos, otroId) : null;
    const cerrado = !!ciclo && ciclo.abierto === false;
    const peso = punto.peso ?? reporte.weight ?? null;
    const fotos = punto.fotos || [];
    const foto = fotos.find(f => /frente|front/i.test(f.pose || '')) || fotos[0] || null;

    const cambiar = async (quitar) => {
        setTrabajando(true);
        try {
            if (quitar) {
                await api.delete(`/admin/reports/${reporte.id}/pico-de-forma`);
                toast.success('Marca quitada');
            } else {
                await api.put(`/admin/reports/${reporte.id}/pico-de-forma`);
                toast.success('Pico de forma marcado');
            }
            setBloqueo(null);
            onCambio?.();
        } catch (e) {
            if (e?.response?.status === 409) {
                setBloqueo(mensajeDeError(e, 'Ahora mismo no se puede mover el pico de forma de este ciclo.'));
            } else {
                toast.error(mensajeDeError(e, quitar ? 'No se pudo quitar la marca' : 'No se pudo marcar el pico de forma'));
            }
        } finally { setTrabajando(false); }
    };

    let frase;
    let boton = null;
    if (!cicloId) {
        frase = 'Este reporte es anterior al cuaderno de ciclos y no se puede marcar.';
    } else if (cerrado) {
        // Con el ciclo cerrado el pico se enseña pero ya no se toca (Jesús: «se puede
        // mover mientras el ciclo esté abierto»): sin botón, para no tropezar con el 409.
        frase = esElPico
            ? `Este reporte es el pico de forma ${delCiclo}.`
            : `${numero != null ? `El ciclo ${numero}` : 'Este ciclo'} ya está cerrado: su pico de forma no se mueve.`;
    } else if (esElPico) {
        frase = `Este reporte es el pico de forma ${delCiclo}`;
        boton = (
            <Button size="sm" variant="outline" onClick={() => cambiar(true)} disabled={trabajando || !!bloqueo}
                data-testid="quitar-pico" className="bg-transparent border-[#333] text-white h-7 text-xs hover:bg-white/5">
                {trabajando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Quitar la marca'}
            </Button>
        );
    } else {
        frase = `Marca este reporte como el pico de forma ${delCiclo}`;
        boton = (
            <Button size="sm" onClick={() => cambiar(false)} disabled={trabajando || !!bloqueo}
                data-testid="marcar-pico" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white h-7 text-xs disabled:opacity-40">
                {trabajando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Marcar como pico de forma'}
            </Button>
        );
    }

    return (
        <div className="bg-[#0A0A0A] rounded-lg p-3 border border-[#222] space-y-2" data-testid="pico-de-forma">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
                    <Trophy className="w-3.5 h-3.5 text-[#FF671F]" /> Pico de forma
                </p>
                {punto.nombre && <span className="text-white/30 text-[10px] uppercase tracking-wider" data-testid="pico-punto">{punto.nombre}</span>}
            </div>
            {/* En estrecho (el móvil del entrenador) el botón baja de línea en vez de
                estrujar la frase en una columna de tres palabras. */}
            <div className="flex flex-wrap items-center gap-3">
                <FotoDelPunto api={api} foto={foto} />
                <div className="flex-1 min-w-[14rem] space-y-1">
                    <p className={`text-sm ${esElPico ? 'text-[#FF671F] font-semibold' : 'text-white/70'}`} data-testid="pico-frase">{frase}</p>
                    {peso != null && (
                        <p className="text-xs text-white/50">Peso <b className="text-white">{peso} kg</b>{foto ? '' : ' · sin foto'}</p>
                    )}
                    {otro && !cerrado && (
                        <p className="text-[11px] text-white/40" data-testid="pico-en-otro">
                            El pico de este ciclo está en el reporte del {fechaLarga(otro.fecha) || 'otro día'}. Si lo marcas aquí, se mueve.
                        </p>
                    )}
                    {bloqueo && <p className="text-[11px] text-[#FF671F]" data-testid="pico-bloqueo">{bloqueo}</p>}
                </div>
                {boton}
            </div>
        </div>
    );
};

export default PicoDeForma;
