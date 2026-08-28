/**
 * ENCOGER LA FOTO EN EL NAVEGADOR, ANTES DE SUBIRLA.
 *
 * «No se pueden cargar imágenes desde escritorio, sale error» (Francisco, 27-08). Y salía:
 * «La imagen pesa 11 MB y el máximo son 4 MB». El tope existe desde que se montaron los
 * adjuntos, pero se mira sobre lo que SUBE el navegador, y una captura de pantalla o una
 * foto de cámara guardada en el ordenador pasa de 4 MB con facilidad. Desde el móvil colaba
 * por poco; desde el escritorio, no.
 *
 * Lo absurdo es que el servidor YA la encoge al guardarla (routes/messages.py, `_encoger`):
 * esos 11 MB acaban siendo unos 250 KB. O sea que se rechazaba una foto que iba a caber.
 *
 * Así que se encoge aquí primero, con la MISMA regla que el servidor -- 1.600 px de lado
 * largo, JPEG al 82 % -- y se sube lo que salga. El tope se queda como red de seguridad
 * para lo que no se pueda encoger.
 *
 * NUNCA REVIENTA LA SUBIDA. Si el navegador no sabe abrir el formato (un HEIC de iPhone
 * fuera de Safari, por ejemplo) se devuelve el fichero original tal cual y decide el
 * servidor, que sí sabe. Es preferible una foto gorda a un cliente que no puede mandar la
 * suya.
 */

//: Los mismos números que `LADO_MAXIMO` y `CALIDAD_JPEG` del servidor. Si cambian allí,
//: cambian aquí: son la misma decisión escrita dos veces porque se aplica en dos sitios.
const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.82;

const cargar = (file) => new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('no se puede abrir')); };
    img.src = url;
});

const aBlob = (canvas, tipo, calidad) => new Promise((resolve) => {
    if (canvas.toBlob) canvas.toBlob(resolve, tipo, calidad);
    else resolve(null);
});

/**
 * Devuelve un File listo para subir: el encogido si se pudo y sale más pequeño, y si no el
 * original. Nunca lanza.
 */
export const encogerImagen = async (file) => {
    if (!file || !file.type?.startsWith('image/')) return file;
    try {
        const img = await cargar(file);
        const lado = Math.max(img.naturalWidth, img.naturalHeight);
        if (!lado) return file;

        const escala = lado > LADO_MAXIMO ? LADO_MAXIMO / lado : 1;
        const ancho = Math.max(1, Math.round(img.naturalWidth * escala));
        const alto = Math.max(1, Math.round(img.naturalHeight * escala));

        const canvas = document.createElement('canvas');
        canvas.width = ancho;
        canvas.height = alto;
        const ctx = canvas.getContext('2d');
        if (!ctx) return file;
        // Fondo blanco: al pasar a JPEG, lo transparente se pintaría de negro y una captura
        // con fondo transparente se volvería ilegible.
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, ancho, alto);
        ctx.drawImage(img, 0, 0, ancho, alto);

        const blob = await aBlob(canvas, 'image/jpeg', CALIDAD_JPEG);
        // Si el «encogido» pesa más que el original -- pasa con imágenes muy planas y ya
        // optimizadas --, se queda el original: el objetivo es ocupar menos, no reprocesar.
        if (!blob || blob.size >= file.size) return file;

        const nombre = (file.name || 'imagen').replace(/\.[^.]+$/, '') + '.jpg';
        return new File([blob], nombre, { type: 'image/jpeg', lastModified: Date.now() });
    } catch (e) {
        console.info('[adjunto] no se pudo encoger en el navegador, se sube tal cual', e?.message || e);
        return file;
    }
};

export default encogerImagen;
