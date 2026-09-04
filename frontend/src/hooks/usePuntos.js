/**
 * LOS PUNTOS DE EVOLUCIÓN, PEDIDOS UNA VEZ Y COMPARTIDOS (doc de Jesús del 2-09, fase 3;
 * Francisco, 4-09).
 *
 * GET /reports/puntos trae todo lo que necesitan los selectores de Evolución de una vez: los
 * ciclos del cuaderno, las fotos con su ciclo y su marca (inicio | final), las tomas de
 * medidas por las tres puertas (reporte, suelta, alta), los puntos de control, y los cuatro
 * atajos de cada cosa (mi primera · inicio de este ciclo · fin del ciclo anterior · hoy).
 *
 * En la pantalla lo usan varios componentes a la vez (la comparativa de fotos, las medidas,
 * el comparador de puntos), y cada uno lo pediría por su cuenta. Aquí se pide UNA vez por
 * instancia de `api` y se comparte: la primera que lo necesita lanza la petición y las demás
 * se enganchan a la misma promesa. La caja va atada al `api` porque ese objeto cambia con el
 * token y con «actuar como», y con un cliente distinto hay que volver a pedir.
 *
 * `activo: false` deja el hook sin hacer nada: es para el mismo componente cuando lo usa el
 * panel del entrenador (tono admin), que no es un cliente y no tiene /reports/puntos.
 */
import { useCallback, useEffect, useState } from 'react';

const RUTA = '/reports/puntos';

// Una caja por instancia de `api`: {datos, error, promesa, oyentes}.
const cajas = new WeakMap();

const _caja = (api) => {
    let c = cajas.get(api);
    if (!c) {
        c = { datos: null, error: null, promesa: null, oyentes: new Set() };
        cajas.set(api, c);
    }
    return c;
};

const _pedir = (c, api) => {
    if (c.promesa) return c.promesa;
    c.error = null;
    c.promesa = api.get(RUTA)
        .then(r => { c.datos = r?.data || null; })
        .catch(e => {
            c.error = e;
            console.error('No se pudieron cargar los puntos de Evolución:', e);
        })
        .finally(() => {
            c.promesa = null;
            c.oyentes.forEach(fn => fn());
        });
    return c.promesa;
};

/**
 * @param {object|null} api   el cliente axios de la sesión (useAuth().api)
 * @param {{activo?: boolean}} [opciones]
 * @returns {{datos: object|null, cargando: boolean, error: any, recargar: function}}
 */
export default function usePuntos(api, { activo = true } = {}) {
    const [, repintar] = useState(0);

    useEffect(() => {
        if (!api || !activo) return undefined;
        const c = _caja(api);
        const oyente = () => repintar(n => n + 1);
        c.oyentes.add(oyente);
        if (!c.datos && !c.promesa) _pedir(c, api);
        return () => { c.oyentes.delete(oyente); };
    }, [api, activo]);

    // Para después de subir fotos o apuntar medidas: se vuelve a pedir y todos los que
    // escuchan se repintan con lo nuevo.
    const recargar = useCallback(() => {
        if (!api) return Promise.resolve();
        return _pedir(_caja(api), api);
    }, [api]);

    const c = api && activo ? _caja(api) : null;
    return {
        datos: c?.datos || null,
        cargando: Boolean(c && !c.datos && !c.error),
        error: c?.error || null,
        recargar,
    };
}
