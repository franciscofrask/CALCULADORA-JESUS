/**
 * A dónde iba el usuario cuando le mandamos a identificarse.
 *
 * Lo deja puesto quien le manda a /auth (hoy solo el test de nivel) y lo consume el
 * PublicRoute de App.js una sola vez, justo al entrar.
 *
 * Por qué hace falta: el que llega de Instagram, hace el test y se registra acababa en
 * el panel sin haber visto un precio. AuthPage navega a /onboarding -> /planes, pero en
 * cuanto el registro guarda el token `isAuthenticated` pasa a true y PublicRoute -- que
 * envuelve /auth para echar de allí al que ya ha entrado -- redirige a /dashboard ANTES,
 * ganándole la carrera. El resultado del test seguía guardado, pero nunca llegaba a la
 * pantalla que lo usa. Se perdía la venta entera.
 *
 * Va en sessionStorage: es de esta visita, no para siempre, y sobrevive al registro
 * porque es la misma pestaña.
 */
export const DESTINO_TRAS_ENTRAR = 'destino_tras_entrar';

export const dejarDestino = (ruta) => {
    try { sessionStorage.setItem(DESTINO_TRAS_ENTRAR, ruta); } catch { /* modo privado */ }
};

/**
 * Lo lee SIN borrarlo, a propósito.
 *
 * Se consulta desde el render de PublicRoute, y ese render ocurre dos veces seguidas al
 * entrar. Si la lectura borrase, la primera vuelta mandaría a /planes y la segunda -- ya
 * sin destino -- mandaría al panel pisando a la primera, que es exactamente el fallo que
 * esto venía a arreglar. Leer es leer: el que llega al destino lo limpia (limpiarDestino).
 */
export const leerDestino = () => {
    try { return sessionStorage.getItem(DESTINO_TRAS_ENTRAR); } catch { return null; }
};

export const limpiarDestino = () => {
    try { sessionStorage.removeItem(DESTINO_TRAS_ENTRAR); } catch { /* modo privado */ }
};
