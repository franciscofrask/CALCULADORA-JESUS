/**
 * EL PUNTO DE «ESTO ESTÁ ENCENDIDO».
 *
 * Estaba dentro de la pantalla de Planes. Al llevarse los interruptores a Ajustes (punto 64)
 * hacía falta en los dos sitios, y un punto de encendido copiado dos veces acaba siendo dos
 * puntos distintos. Es lo único que se comparte: el verde con el tic y el gris con la equis.
 */
import React from 'react';
import { Check, X } from 'lucide-react';

const PuntoEncendido = ({ on }) => (
    <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full ${on ? 'bg-green-500/20 text-green-500' : 'bg-white/10 text-white/30'}`}>
        {on ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
    </span>
);

export default PuntoEncendido;
