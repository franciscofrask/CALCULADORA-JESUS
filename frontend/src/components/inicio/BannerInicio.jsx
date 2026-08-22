// El hero de la pantalla de Inicio: la foto del mes en BLANCO Y NEGRO va DE FONDO (no
// ocupa un bloque aparte) y el texto del saludo se superpone encima, con un velo oscuro
// para que se lea. La foto va rotando sola: cada mes toca la siguiente de la lista y, al
// llegar al final, vuelve a la primera. Para cambiar las fotos o el orden, reemplaza las
// imágenes de src/assets/inicio o reordena el array FOTOS.
import img5759 from '../../assets/inicio/img_5759_2.jpg';
import img5757 from '../../assets/inicio/img_5757_2.jpg';
import img5755 from '../../assets/inicio/img_5755.jpg';
import img5760 from '../../assets/inicio/img_5760_3.jpg';
import img5765 from '../../assets/inicio/img_5765_2.jpg';

// El orden que pidió Alejandra (21-08): 5759 · 5757 · 5755 · 5760 · 5765, y vuelta a empezar.
const FOTOS = [img5759, img5757, img5755, img5760, img5765];

// Mes de referencia: la primera de la lista (5759) toca en agosto de 2026, y a partir de
// ahí se avanza una cada mes. Para arrancar en otro momento, cambia solo este ancla.
const MES_INICIAL = 2026 * 12 + 7; // agosto 2026 (los meses van de 0 a 11: 7 = agosto)

// La foto que toca este mes: cuenta los meses desde el ancla y da la vuelta al llegar al
// final de la lista. Cambia sola el día 1 de cada mes, sin que nadie tenga que tocar nada.
function fotoDelMes(fecha = new Date()) {
    const meses = fecha.getFullYear() * 12 + fecha.getMonth();
    const i = ((meses - MES_INICIAL) % FOTOS.length + FOTOS.length) % FOTOS.length;
    return FOTOS[i];
}

// Envuelve el saludo del Inicio: la foto de fondo (a sangre, cancelando el padding del
// Inicio con los márgenes negativos) y encima el contenido que se le pase.
const HeroInicio = ({ children }) => (
    <div className="-mx-4 sm:-mx-6 lg:-mx-8 -mt-6 relative overflow-hidden" data-testid="inicio-banner">
        <img
            src={fotoDelMes()}
            alt=""
            aria-hidden="true"
            draggable="false"
            className="absolute inset-0 w-full h-full object-cover grayscale select-none pointer-events-none"
        />
        {/* Velo que oscurece para que el texto blanco se lea y, abajo, FUNDE la foto con el
            fondo de la pantalla para que no haya corte: la imagen se disuelve en el
            contenido en vez de ocupar un bloque con borde. */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/50 to-background" />
        <div className="relative px-4 sm:px-6 lg:px-8 pt-11 pb-10">
            {children}
        </div>
    </div>
);

export default HeroInicio;
