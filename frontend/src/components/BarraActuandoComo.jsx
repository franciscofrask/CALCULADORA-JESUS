/**
 * La barra de «estás dentro de la cuenta de X». Punto 4.11 de la revisión del 09-08.
 *
 * Jesús pidió poder entrar en la calculadora de un cliente «con un aviso de que estás
 * actuando como su entrenador», y el aviso no es un detalle de cortesía: sin él, el
 * entrenador está viendo una pantalla idéntica a la suya con los datos de otra persona. Lo
 * que se toque ahí lo va a leer el cliente en su móvil.
 *
 * Por eso va arriba del todo, fija, en naranja y ocupando el ancho: tiene que ser imposible
 * no verla, y tiene que llevar la salida encima. Un modo del que no se sabe salir es peor que
 * no tener el modo.
 */
import React from 'react';
import { LogOut, UserCog } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const BarraActuandoComo = () => {
    const { actuandoComo, dejarDeActuar } = useAuth();
    if (!actuandoComo?.userId) return null;

    return (
        <div className="sticky top-0 z-[70] bg-[#FF671F] text-white shadow-lg" data-testid="barra-actuando-como">
            <div className="max-w-[1200px] mx-auto px-4 py-2 flex items-center gap-3 flex-wrap">
                <UserCog className="w-4 h-4 flex-shrink-0" />
                <p className="text-sm font-bold min-w-0">
                    Estás en la cuenta de {actuandoComo.nombre}
                </p>
                <span className="text-xs text-white/80 hidden sm:inline">
                    Lo que guardes aquí lo verá {actuandoComo.nombre} en su app, con tu nombre.
                </span>
                <button onClick={dejarDeActuar} data-testid="dejar-de-actuar"
                    className="ml-auto flex items-center gap-1.5 bg-white/15 hover:bg-white/25 rounded-full px-3 py-1 text-xs font-bold transition-colors">
                    <LogOut className="w-3.5 h-3.5" /> Salir de su cuenta
                </button>
            </div>
        </div>
    );
};

export default BarraActuandoComo;
