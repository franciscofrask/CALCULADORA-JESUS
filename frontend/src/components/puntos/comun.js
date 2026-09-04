/**
 * LO QUE COMPARTEN LA LISTA DE PUNTOS, EL DETALLE Y EL COMPARADOR (doc de Jesús del 2-09,
 * «Los puntos de control» y «El comparador»; fase 3, 4-09).
 *
 * Un punto es un reporte: lo que trae fotos, medidas y peso a la vez, y por eso es lo único
 * que se puede comparar. Los tres sitios que lo pintan leen el mismo `GET /reports/puntos`
 * y escriben las mismas fechas, las mismas pastillas y las mismas fotos, así que eso vive
 * aquí una vez y no tres. Nada de esto decide qué punto es cuál: eso lo trae el servidor
 * (nombre, etiquetas, atajos); aquí solo se pinta.
 *
 * Las fotos van con la sesión: se piden con el token y se pintan desde el blob, el mismo
 * camino que `ComparativaCliente` y `TresFotos`. El token no viaja nunca en una URL.
 */
import React, { useEffect, useState } from 'react';
import VisorDeFoto from '../ui/VisorDeFoto';
import usePuntos from '../../hooks/usePuntos';
import { NOMBRE_POSE, ordenarPorPose } from '../../lib/comparativaFotos';

/** Las tres etiquetas de un punto. El pico lo marca el entrenador; las otras dos salen solas. */
export const TEXTO_ETIQUETA = {
    pico_de_forma: 'Pico de forma',
    peso_maximo: 'Peso máximo',
    peso_minimo: 'Peso mínimo',
};

// «2026-07-25» o un ISO con hora: siempre al mediodía local, para que un día no se
// convierta en el anterior al pasar por UTC (trampa conocida de las fechas sin zona).
const _dia = (f) => {
    if (!f) return null;
    const s = String(f);
    const d = new Date(s.length <= 10 ? `${s}T12:00:00` : s);
    return Number.isNaN(d.getTime()) ? null : d;
};

// El año solo cuando no es el de ahora: «25 jul» de hace dos años mentiría con la fecha.
const _conAnio = (d) => d.getFullYear() !== new Date().getFullYear();

/** «25 jul», y «25 jul 2025» si no es de este año. */
export const fechaCorta = (f) => {
    const d = _dia(f);
    if (!d) return '';
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', ...(_conAnio(d) ? { year: 'numeric' } : {}) });
};

/** «25 de julio», y «25 de julio de 2025» si no es de este año. */
export const fechaLarga = (f) => {
    const d = _dia(f);
    if (!d) return '';
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long', ...(_conAnio(d) ? { year: 'numeric' } : {}) });
};

/** Días enteros entre dos fechas, sin signo. */
export const diasEntre = (a, b) => {
    const da = _dia(a), db = _dia(b);
    if (!da || !db) return null;
    return Math.round(Math.abs(db.getTime() - da.getTime()) / 864e5);
};

/** «4 semanas entre los dos puntos», o en días si hay menos de dos semanas. Jesús: ver
 *  −1,6 kg no dice nada si no sabes en cuánto. */
export const tiempoEntre = (a, b) => {
    const dias = diasEntre(a, b);
    if (dias == null) return '';
    if (dias === 0) return 'Los dos puntos son del mismo día';
    if (dias < 14) return `${dias} ${dias === 1 ? 'día' : 'días'} entre los dos puntos`;
    const semanas = Math.round(dias / 7);
    return `${semanas} semanas entre los dos puntos`;
};

/** El rótulo que va encima de cada foto: «Final bloque 2 · Ciclo 3» se queda en
 *  «Final B2 · Ciclo 3» (se pinta en mayúsculas por CSS, como los de la comparativa). */
export const rotuloCorto = (nombre) => String(nombre || '').replace(/\bbloque (\d+)/gi, 'B$1');

/** «Punto del 25 de julio», para hablar de un punto que no es un reporte (el alta, la
 *  vuelta) en las frases de «no lo mediste...». */
export const enEsePunto = (punto) => (punto?.tipo === 'reporte'
    ? `en el reporte del ${fechaLarga(punto.fecha)}`
    : `el ${fechaLarga(punto?.fecha)}`);

/** Coma decimal y sin decimales cuando son cero: «37», «37,5». */
export const numero = (v, decimales = 1) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return '';
    const factor = 10 ** decimales;
    return String(Math.round(n * factor) / factor).replace('.', ',');
};

/**
 * La diferencia entre los dos valores de una fila, con su signo: «+20», «−1», «0». El
 * signo menos es el de verdad (U+2212), no el guion, como en la gráfica de peso.
 * `signo`: 1 sube, -1 baja, 0 igual; null si falta alguno de los dos.
 */
export const diferencia = (antes, despues, decimales = 1) => {
    const a = Number(antes), b = Number(despues);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    const factor = 10 ** decimales;
    const d = Math.round((b - a) * factor) / factor;
    if (d === 0) return { valor: 0, texto: '0', signo: 0 };
    return { valor: d, texto: `${d > 0 ? '+' : '−'}${numero(Math.abs(d), decimales)}`, signo: Math.sign(d) };
};

// EL COLOR DE LA DIFERENCIA: los de Jesús (doc del 2-09: «verde baja, naranja sube»), que
// Francisco eligió el 5-09 entre las tres reglas que había. Los mismos en la tabla de
// medidas (`EvolucionMedidas`), aquí y en la imagen que se genera. Gris lo que no se mueve.
export const colorDeLaDiferencia = (signo) => (signo > 0 ? 'text-brand' : signo < 0 ? 'text-emerald-500' : 'text-muted-foreground');

/** Un bloque de macros en palabras: «180 g de proteína, 250 g de hidratos, 60 g de grasa».
 *  Las claves son las de `/macros/historial` (proteina/hidratos/grasa), las mismas que
 *  escribe «Tu último ajuste» en ReportsPage. */
export const macrosEnPalabras = (bloque) => {
    if (!bloque) return '';
    return [['proteina', 'proteína'], ['hidratos', 'hidratos'], ['grasa', 'grasa']]
        .filter(([k]) => bloque[k] != null)
        .map(([k, nombre]) => `${bloque[k]} g de ${nombre}`)
        .join(', ');
};

/** Las pastillas de un punto: PICO DE FORMA en naranja (la marca el entrenador), PESO
 *  MÁXIMO y PESO MÍNIMO en gris (salen solas). Sin etiquetas no pinta nada. */
export const Pastillas = ({ etiquetas, className = '' }) => {
    if (!etiquetas?.length) return null;
    return (
        <div className={`flex flex-wrap gap-1.5 ${className}`}>
            {etiquetas.map(e => (
                <span key={e} data-testid={`etiqueta-${e}`}
                    className={e === 'pico_de_forma'
                        ? 'badge-elm'
                        : 'bg-muted text-muted-foreground border border-border font-bold px-2.5 py-0.5 rounded-md text-xs uppercase tracking-wider'}>
                    {TEXTO_ETIQUETA[e] || e}
                </span>
            ))}
        </div>
    );
};

/** La ruta con la que se pide una foto del punto al `api` de la sesión: por su ref a
 *  `/reports/foto/{ref}`, el mismo camino que la comparativa y las tres fotos. La ref de
 *  las de Calma lleva barras (calma/carpeta/fichero), así que se codifica tramo a tramo.
 *
 *  El servidor manda también una `url` firmada al almacén (R2, caduca a los diez minutos).
 *  No se usa a propósito: el `api` mete la cabecera Authorization en todo lo que pide, y
 *  una URL firmada con esa cabecera encima la rechaza el almacén; y sin CORS abierto en
 *  el almacén el navegador tampoco la deja leer para el canvas de la imagen. Por la API
 *  la foto llega siempre y con la sesión. Solo sin ref queda la `url` como último recurso. */
export const rutaDeFoto = (foto) => {
    const ref = foto?.ref || foto?.id;
    if (ref) return `/reports/foto/${String(ref).split('/').map(encodeURIComponent).join('/')}`;
    const url = foto?.url;
    if (!url) return null;
    return /^https?:\/\//i.test(url) ? url : url.replace(/^\/api(?=\/)/, '');
};

/** La foto, bajada con la sesión y convertida en una URL de blob (o null mientras llega o
 *  si no hay foto). La URL se libera al cambiar de foto o al desmontar. */
export const useUrlDeFoto = (api, foto) => {
    const [url, setUrl] = useState(null);
    const ruta = rutaDeFoto(foto);
    useEffect(() => {
        if (!ruta) { setUrl(null); return undefined; }
        let vivo = true;
        let creada = null;
        api.get(ruta, { responseType: 'blob' })
            .then(r => {
                if (!vivo) return;
                creada = URL.createObjectURL(r.data);
                setUrl(creada);
            })
            .catch((e) => { console.error('No se pudo cargar una foto del punto:', e); });
        return () => {
            vivo = false;
            setUrl(null);
            if (creada) URL.revokeObjectURL(creada);
        };
    }, [api, ruta]);
    return url;
};

/** Una foto ya cargada, en su hueco de 3/4, que al tocarla se ve entera en el visor con su
 *  pie (fecha y ángulo). Mientras no hay URL, el hueco vacío. */
export const FotoDelPunto = ({ url, pie = null, alt = 'Tu foto', testid = 'foto-del-punto', className = 'aspect-[3/4]' }) => {
    const [ampliada, setAmpliada] = useState(false);
    if (!url) return <div className={`${className} w-full rounded-xl bg-muted`} />;
    return (
        <>
            <button type="button" onClick={() => setAmpliada(true)} data-testid={testid}
                aria-label={pie ? `Ver la foto de ${pie} en grande` : 'Ver la foto en grande'}
                className={`${className} w-full rounded-xl overflow-hidden bg-muted block active:opacity-80 transition-opacity`}>
                <img src={url} alt="" className="w-full h-full object-cover" />
            </button>
            {ampliada && <VisorDeFoto url={url} alt={alt} pie={pie} alCerrar={() => setAmpliada(false)} />}
        </>
    );
};

/** El pie de una foto: «25 de julio · de frente». */
export const pieDeFoto = (punto, foto) => {
    const angulo = NOMBRE_POSE[foto?.pose];
    return `${fechaLarga(punto?.fecha)}${angulo ? ` · ${angulo}` : ''}`;
};

/** La foto que manda de un punto: de frente si la hay, si no de perfil, si no de espalda. */
export const fotoPrincipal = (punto) => ordenarPorPose(punto?.fotos || [])[0] || null;

/** La foto de un punto con un ángulo dado, o null si no la tiene. Sin ángulo, la principal. */
export const fotoDelAngulo = (punto, pose) => {
    if (!pose) return fotoPrincipal(punto);
    return (punto?.fotos || []).find(f => f.pose === pose) || null;
};

/**
 * `GET /reports/puntos`, por el hook compartido de la pantalla (`hooks/usePuntos`: una sola
 * petición por sesión, que la comparten la comparativa de fotos, las medidas y esto).
 * Devuelve `{datos, error}`: `datos` es la respuesta entera (ciclos, puntos, atajos) o null
 * mientras llega; `error` la frase para el cliente si falló. El detalle técnico ya lo deja
 * el hook en consola, nunca en la pantalla.
 */
export const useDatosDePuntos = (api) => {
    const { datos, error } = usePuntos(api);
    return {
        datos,
        error: error ? 'No hemos podido cargar tus puntos de control. Vuelve a intentarlo en un momento.' : null,
    };
};

/** Los puntos del más antiguo al de hoy, que es como van en toda la pantalla (la gráfica,
 *  la tabla de medidas y esta lista miran el tiempo en la misma dirección). */
export const puntosEnOrden = (datos) => [...(datos?.puntos || [])]
    .filter(p => p && p.id != null)
    .sort((a, b) => String(a.fecha || '').localeCompare(String(b.fecha || '')));
