import { toast } from 'sonner';

/**
 * ABRIR LA RUTINA DEL CLIENTE, QUE EN EL IPHONE NO ABRÍA (vídeo de Jesús del 27-08).
 *
 * Lo vive en directo, minuto 6:06: «tarda en abrirse, estoy tocando y no abre. No sé por qué.
 * Toco y no abre. No abre la rutina». Y no salía ni aviso.
 *
 * LA CAUSA. El fichero se pide con el token -- el visor del navegador no lo manda, así que hay
 * que bajarlo como blob -- y hasta hoy se hacía así, en tres pantallas distintas:
 *
 *     const r = await api.get('/routines/pdf', { responseType: 'blob' });
 *     window.open(URL.createObjectURL(...), '_blank');
 *
 * El `window.open` va DESPUÉS del `await`, y para entonces el navegador ya no lo cuenta como
 * gesto del usuario: **Safari del iPhone lo bloquea, y en silencio**. El `catch` no salta
 * porque la petición fue bien; lo único que pasa es que no pasa nada.
 *
 * EL ARREGLO. La pestaña se abre DENTRO del toque, vacía, y se le pone el fichero cuando
 * llega. Así el navegador ve que la abrió el usuario y no la bloquea.
 *
 * Vive aquí y no en cada pantalla porque el fallo estaba copiado en tres sitios (el Inicio,
 * Entreno y Rutina) y arreglar dos de tres no arregla nada.
 */
export const abrirRutinaPdf = async (api) => {
    // Primero la ventana, todavía dentro del gesto. Si el navegador la bloquea igual (un
    // bloqueador de ventanas de verdad), `ventana` viene a null y se intenta por lo directo.
    const ventana = window.open('', '_blank');
    try {
        const r = await api.get('/routines/pdf', { responseType: 'blob' });
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
        if (ventana && !ventana.closed) ventana.location.href = url;
        else window.open(url, '_blank');
        return true;
    } catch (e) {
        // La ventana en blanco no se queda ahí puesta: si no hay fichero que enseñar, se
        // cierra y se dice lo que pasa, que era justo lo que faltaba.
        if (ventana && !ventana.closed) ventana.close();
        console.error('[rutina] no se pudo abrir el PDF', e?.response?.status || e);
        toast.error('No hemos podido abrir tu rutina. Inténtalo en un momento.');
        return false;
    }
};
