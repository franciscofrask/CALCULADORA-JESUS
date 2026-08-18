/**
 * EL TEXTO QUE SE LE ENSEÑA A UNA PERSONA CUANDO ALGO FALLA.
 *
 * En esta casa el error nunca es técnico: al usuario, una frase que entienda; el detalle,
 * a la consola. Pero por toda la app estaba escrito así:
 *
 *     toast.error(e.response?.data?.detail || 'No se pudo guardar')
 *
 * y eso da por hecho que `detail` es una cadena. Cuando el backend rechaza un dato por su
 * tipo, FastAPI NO manda una cadena: manda la lista de errores de validación, que son
 * objetos `{type, loc, msg, input, ctx, url}`. Ese array acaba dentro del aviso, React
 * intenta pintar un objeto como texto y **se cae la pantalla entera**. Le pasó al
 * cuestionario del alta: el cliente terminaba de contestar, pulsaba «Calcular mis macros»
 * y se quedaba mirando una pantalla en blanco con una traza.
 *
 * Aquí se devuelve SIEMPRE una cadena. Y si el error trae detalle técnico, se escribe en la
 * consola, que es donde sirve de algo.
 */

// CÓMO SE LLAMAN LAS COSAS PARA QUIEN LAS ESCRIBE. El campo se llama `height` en la base y
// «tu altura» en la pantalla, y lo que hay que enseñarle es lo segundo: «Revisa el campo
// height» no le dice a nadie dónde tiene que volver. Y con el rango puesto, que es lo que de
// verdad le desatasca: sabe qué esperábamos.
const COMO_SE_LLAMA = {
    height: ['tu altura', 'en centímetros, entre 120 y 230'],
    weight: ['tu peso', 'en kilos, entre 25 y 300'],
    body_fat: ['tu porcentaje de grasa', 'entre 3 y 70'],
    birthdate: ['tu fecha de nacimiento', null],
    email: ['tu email', null],
    phone: ['tu teléfono', null],
    goal: ['tu objetivo', null],
    peso_maximo: ['tu peso máximo', 'en kilos'],
    peso_minimo: ['tu peso más bajo', 'en kilos'],
    peso_mejor_momento: ['tu peso en tu mejor momento', 'en kilos'],
};

/** Un aviso de validación de FastAPI, pasado a algo que se pueda leer. */
function _deLaValidacion(lista) {
    const primero = lista.find((e) => e && (e.msg || e.loc));
    if (!primero) return null;
    // `loc` es ['body', 'campo']: al usuario le vale saber QUÉ dato no le hemos aceptado.
    const campo = Array.isArray(primero.loc) ? primero.loc[primero.loc.length - 1] : null;
    if (!campo || typeof campo !== 'string') {
        return 'Hay algún dato que no hemos podido guardar. Revísalo y vuelve a intentarlo.';
    }
    const [nombre, pista] = COMO_SE_LLAMA[campo] || [null, null];
    if (!nombre) return `Revisa el dato «${campo}»: no hemos podido guardarlo así.`;
    return pista
        ? `Revisa ${nombre}: la esperamos ${pista}.`
        : `Revisa ${nombre}: no hemos podido guardarlo así.`;
}

/**
 * @param {unknown} error   lo que soltó axios (o un fetch, o un throw)
 * @param {string} porDefecto  qué decir cuando no se sabe nada más
 * @returns {string} siempre una cadena, nunca un objeto
 */
export function mensajeDeError(error, porDefecto = 'No se ha podido completar. Inténtalo otra vez.') {
    const detalle = error?.response?.data?.detail ?? error?.data?.detail ?? error?.detail;

    if (typeof detalle === 'string' && detalle.trim()) return detalle;

    if (Array.isArray(detalle)) {
        console.error('[error del servidor]', detalle);
        return _deLaValidacion(detalle) || porDefecto;
    }

    if (detalle && typeof detalle === 'object') {
        console.error('[error del servidor]', detalle);
        return typeof detalle.msg === 'string' ? detalle.msg : porDefecto;
    }

    // Sin respuesta del servidor: se ha caído la conexión, no es culpa de lo que escribió.
    if (error && error.request && !error.response) {
        console.error('[sin respuesta del servidor]', error.message || error);
        return 'No hemos podido conectar. Comprueba tu conexión y vuelve a intentarlo.';
    }

    if (error) console.error('[error]', error);
    return porDefecto;
}

export default mensajeDeError;
