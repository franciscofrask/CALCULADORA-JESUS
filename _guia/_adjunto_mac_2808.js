/**
 * EL 500 DEL ADJUNTO MANDADO DESDE UN MAC (28-08).
 *
 * Sube una imagen con el nombre EXACTO que llega de macOS -- con su espacio fino de no
 * separación delante del PM -- y la pide, que es donde reventaba. Y de paso una con el
 * nombre de un iPhone, que es la que sí iba, para ver que no se ha roto.
 *
 * Uso:  node _guia/_adjunto_mac_2808.js
 */
const { chromium } = require('playwright');
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

let malas = 0;
const ok = (b) => { if (!b) malas++; return b ? 'BIEN' : 'MAL '; };

// Un PNG de 1x1 de verdad, para que el servidor no lo rechace por no ser una imagen.
const PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
    'base64');

const NOMBRES = [
    ['captura de Mac', 'Screenshot 2026-08-28 at 6.17.43 PM.png'],
    ['foto de iPhone', 'IMG_4821.png'],
    ['nombre con acento', 'café con leche.png'],
    ['otro alfabeto', '写真.png'],
];

(async () => {
    const nav = await chromium.launch();
    const page = await (await nav.newContext()).newPage();
    const tok = (await (await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    console.log('\n=== EL ADJUNTO DEL CHAT, NOMBRE A NOMBRE ===\n');

    for (const [que, nombre] of NOMBRES) {
        const sub = await page.request.post(`${API}/api/messages/adjunto`, {
            headers: cab,
            multipart: { file: { name: nombre, mimeType: 'image/png', buffer: PNG } },
        });
        if (!sub.ok()) {
            console.log(`${que.padEnd(18)} no se pudo subir (${sub.status()})   ${ok(false)}`);
            continue;
        }
        const id = (await sub.json()).id;
        const ver = await page.request.get(`${API}/api/messages/adjunto/${id}`, { headers: cab });
        const cd = ver.headers()['content-disposition'] || '(sin cabecera)';
        console.log(`${que.padEnd(18)} ${ver.status()}   ${ok(ver.status() === 200)}`);
        console.log(`   nombre subido:  ${JSON.stringify(nombre)}`);
        console.log(`   Content-Disposition: ${cd}`);
        if (ver.status() === 200) {
            const bytes = (await ver.body()).length;
            console.log(`   y la imagen llega entera: ${bytes} bytes   ${ok(bytes === PNG.length)}`);
        }
        console.log('');
    }

    await nav.close();
    console.log(`${malas ? malas + ' MAL' : 'todo BIEN'}`);
    process.exit(malas ? 1 : 0);
})();
