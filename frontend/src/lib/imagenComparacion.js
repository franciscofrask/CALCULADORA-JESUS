/**
 * «GENERAR COMPARACIÓN»: una imagen con las dos fotos, las fechas y lo que ha movido (doc
 * de Jesús del 2-09, fase 3). «La generas tú, cuando quieras. No se comparte sola.»
 *
 * Se dibuja en el navegador, en un canvas, y se entrega como fichero: así no pasa por el
 * servidor, no se guarda en ningún sitio y nadie más la ve si el cliente no la manda. Es
 * la misma imagen tanto para la comparativa de fotos como para el comparador de puntos:
 * quien llama pasa las dos mitades y las filas que quiera debajo.
 *
 * Las fotos llegan como URL de la app (van con el token, como en el visor): se piden con
 * fetch para que el canvas no quede «sucio» y se pueda exportar.
 */

const ANCHO = 1080;          // el ancho de una historia de móvil
const MARGEN = 48;
const NARANJA = '#FF671F';
const VERDE = '#34D399';
const FONDO = '#0B0B0B';
const TEXTO = '#F4F4F4';
const GRIS = '#9A9A9A';

const _cargarImagen = async (url, cabeceras) => {
    if (!url) return null;
    try {
        const r = await fetch(url, { headers: cabeceras || {} });
        if (!r.ok) return null;
        const blob = await r.blob();
        const img = new Image();
        const listo = new Promise((res, rej) => { img.onload = () => res(img); img.onerror = rej; });
        img.src = URL.createObjectURL(blob);
        await listo;
        return img;
    } catch {
        return null;
    }
};

// Dibuja la foto recortada para llenar la caja (como object-fit: cover), o un hueco dicho.
const _foto = (ctx, img, x, y, w, h, textoSiNoHay) => {
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(x, y, w, h);
    if (!img) {
        ctx.fillStyle = GRIS;
        ctx.font = '28px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(textoSiNoHay || 'sin foto', x + w / 2, y + h / 2);
        ctx.textAlign = 'left';
        return;
    }
    const escala = Math.max(w / img.width, h / img.height);
    const dw = img.width * escala, dh = img.height * escala;
    ctx.save();
    ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
    ctx.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    ctx.restore();
};

const _texto = (ctx, t, x, y, { tam = 28, color = TEXTO, peso = 'normal', alinear = 'left' } = {}) => {
    if (t == null || t === '') return;
    ctx.fillStyle = color;
    ctx.font = `${peso} ${tam}px system-ui, -apple-system, sans-serif`;
    ctx.textAlign = alinear;
    ctx.fillText(String(t), x, y);
    ctx.textAlign = 'left';
};

/**
 * @param {object} p
 * @param {{url:string, rotulo:string, fecha:string, peso?:string, objetivo?:string}} p.izquierda
 * @param {{url:string, rotulo:string, fecha:string, peso?:string, objetivo?:string}} p.derecha
 * @param {string} [p.tiempo]  «4 semanas entre los dos puntos»
 * @param {{nombre:string, antes:string, despues:string, diferencia:string}[]} [p.filas]
 * @param {object} [p.cabeceras]  las de la API (Authorization) para bajar las fotos
 * @returns {Promise<Blob>} PNG
 */
export async function generarImagenComparacion({ izquierda, derecha, tiempo = null, filas = [], cabeceras = null }) {
    const [imgI, imgD] = await Promise.all([_cargarImagen(izquierda?.url, cabeceras), _cargarImagen(derecha?.url, cabeceras)]);
    const anchoFoto = (ANCHO - MARGEN * 3) / 2;
    const altoFoto = Math.round(anchoFoto * 4 / 3);
    const altoFilas = filas.length * 44 + (filas.length ? 40 : 0);
    const alto = MARGEN + 70 + altoFoto + 170 + (tiempo ? 50 : 0) + altoFilas + MARGEN + 40;

    const canvas = document.createElement('canvas');
    canvas.width = ANCHO;
    canvas.height = alto;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = FONDO;
    ctx.fillRect(0, 0, ANCHO, alto);

    let y = MARGEN;
    _texto(ctx, '12EN12', MARGEN, y + 28, { tam: 30, color: NARANJA, peso: 'bold' });
    y += 70;

    const xI = MARGEN, xD = MARGEN * 2 + anchoFoto;
    _texto(ctx, (izquierda?.rotulo || '').toUpperCase(), xI, y - 12, { tam: 22, color: GRIS, peso: 'bold' });
    _texto(ctx, (derecha?.rotulo || '').toUpperCase(), xD, y - 12, { tam: 22, color: NARANJA, peso: 'bold' });
    _foto(ctx, imgI, xI, y, anchoFoto, altoFoto, 'sin foto de ese momento');
    _foto(ctx, imgD, xD, y, anchoFoto, altoFoto, 'sin foto de ese momento');
    y += altoFoto + 44;

    for (const [x, lado] of [[xI, izquierda], [xD, derecha]]) {
        _texto(ctx, lado?.fecha, x, y, { tam: 30, peso: 'bold' });
        if (lado?.peso) _texto(ctx, lado.peso, x, y + 40, { tam: 30, peso: 'bold' });
        if (lado?.objetivo) _texto(ctx, lado.objetivo, x, y + 78, { tam: 24, color: GRIS });
    }
    // Aire entre el objetivo de cada foto y la línea del tiempo: pegados se leían como una
    // sola frase (visto en la primera imagen generada, 4-09).
    y += 130;

    if (tiempo) {
        _texto(ctx, tiempo, ANCHO / 2, y, { tam: 26, color: GRIS, alinear: 'center' });
        y += 50;
    }

    if (filas.length) {
        ctx.strokeStyle = '#2A2A2A';
        ctx.beginPath(); ctx.moveTo(MARGEN, y); ctx.lineTo(ANCHO - MARGEN, y); ctx.stroke();
        y += 40;
        for (const f of filas) {
            _texto(ctx, f.nombre, MARGEN, y, { tam: 26, color: GRIS });
            _texto(ctx, f.antes, ANCHO - MARGEN - 300, y, { tam: 26, alinear: 'right' });
            _texto(ctx, f.despues, ANCHO - MARGEN - 150, y, { tam: 26, peso: 'bold', alinear: 'right' });
            // Los colores de Jesús (Francisco, 5-09): verde lo que baja, naranja lo que sube.
            const dif = String(f.diferencia || '');
            const colorDif = dif.startsWith('−') || dif.startsWith('-') ? VERDE : dif.startsWith('+') ? NARANJA : GRIS;
            _texto(ctx, f.diferencia, ANCHO - MARGEN, y, { tam: 26, color: colorDif, alinear: 'right' });
            y += 44;
        }
    }

    return new Promise((res) => canvas.toBlob((b) => res(b), 'image/png'));
}

/** Entrega la imagen al cliente: compartir si el móvil lo permite, si no descargar. */
export async function entregarImagen(blob, nombre = 'comparacion-12en12.png') {
    const fichero = new File([blob], nombre, { type: 'image/png' });
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [fichero] })) {
        try {
            await navigator.share({ files: [fichero], title: 'Mi comparación' });
            return 'compartida';
        } catch {
            // Canceló el compartir: se le deja descargar igual.
        }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return 'descargada';
}
