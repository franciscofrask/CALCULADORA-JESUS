/**
 * EL ARTIFACT, DESPIEZADO PARA EL WORD.
 *
 * Recorre el artifact ya montado (`_repaso_suyo.html`) EN ORDEN y saca dos cosas:
 *
 *   · lo que es texto -- titulos, pies, veredictos, frases -- a un JSON, para que en el Word
 *     sea texto de verdad: se busca, se copia y se lee en el movil,
 *   · y lo que es MAQUETA suya -- los telefonos con las pantallas -- a una imagen, porque eso
 *     es HTML y CSS de la app y en Word no hay forma de reproducirlo.
 *
 * Asi el Word lleva lo mismo que el artifact y en el mismo orden, sin ser un monton de
 * pantallazos ilegibles ni un texto sin las pantallas.
 *
 * Uso:  node _guia/_word_extraer.js
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const FUENTE = 'file:///C:/Users/Administrador/Desktop/CALCULADORA-JESUS/_guia/_repaso_suyo.html';
const CARPETA = '_guia/_word_capturas';
const SALIDA = '_guia/_word_items.json';

if (fs.existsSync(CARPETA)) fs.rmSync(CARPETA, { recursive: true, force: true });
fs.mkdirSync(CARPETA, { recursive: true });

(async () => {
    const nav = await chromium.launch();
    const p = await (await nav.newContext({
        viewport: { width: 1180, height: 1400 }, deviceScaleFactor: 2,
    })).newPage();
    await p.goto(FUENTE, { waitUntil: 'load' });
    await p.waitForTimeout(4000);

    // Se marcan los trozos que hay que fotografiar, para poder localizarlos despues.
    const items = await p.evaluate(() => {
        const fuera = [];
        let n = 0;
        const texto = (el) => (el?.innerText || '').replace(/\s+\n/g, '\n').trim();

        const marcar = (el) => {
            const id = `foto-${++n}`;
            el.setAttribute('data-foto', id);
            return id;
        };

        // Nuestra tarjeta, en piezas: el veredicto va como TEXTO en el Word.
        // DE QUE PUNTO ES CADA TARJETA, para poder comprobarlo despues. No reordena nada:
        // el orden del DOM ya es el bueno. Sirve para cazar una tarjeta que se hubiera
        // quedado colgando del punto de al lado, que es un fallo facil de no ver.
        const anclaDe = (el) => {
            const titulos = [...document.querySelectorAll('h3, h4')];
            let mejor = null;
            for (const t of titulos) {
                if (t.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) mejor = t;
            }
            return mejor ? (mejor.innerText || '').trim() : null;
        };

        const nuestra = (el) => ({
            tipo: 'veredicto',
            ancla: anclaDe(el),
            estado: texto(el.querySelector('.chip')),
            clase: [...el.classList].find(c => ['ok', 'matiz', 'mal', 'despues', 'gris'].includes(c)) || '',
            nota: texto(el.querySelector('.nota')),
            frases: [...el.querySelectorAll('.frases li')].map(li => ({
                se_ve: li.classList.contains('si'),
                frase: (li.childNodes[0]?.textContent || '').trim(),
                porque: texto(li.querySelector('.por')),
            })),
            donde: texto(el.querySelector('.donde')),
            forzada: texto(el.querySelector('.forzada')),
            // La captura ya viene incrustada en el artifact: se saca de ahi.
            imagen: el.querySelector('figure img')?.getAttribute('src') || null,
        });

        // ── 1 · El documento de Jesus, con su HTML ──
        const env = document.querySelector('.env');
        if (env) {
            fuera.push({ tipo: 'documento', titulo: texto(env.querySelector('.cab h1')),
                         eti: texto(env.querySelector('.cab .eti')),
                         bajadas: [...env.querySelectorAll('.cab .baj')].map(texto) });
            // OJO CON EL ORDEN. En las comparaciones, el `.fi` ENVUELVE a su `<h3>`, asi que
            // `querySelectorAll` devuelve primero el padre y la maqueta salia antes que el
            // titulo del punto. Se emite el titulo al llegar al `.fi` y se marca ese h3 para
            // no repetirlo cuando le toque su turno.
            const yaPuestos = new Set();
            const sel = '.parte, h2, p.sub, h3, .fi, .tira > .uno, .f, .nuestro, .lst, .pieg';
            for (const el of env.querySelectorAll(sel)) {
                if (el.matches('.parte')) {
                    fuera.push({ tipo: 'bloque', texto: texto(el) });
                } else if (el.matches('h2')) {
                    fuera.push({ tipo: 'seccion', texto: texto(el) });
                } else if (el.matches('p.sub')) {
                    fuera.push({ tipo: 'sub', texto: texto(el) });
                } else if (el.matches('h3')) {
                    if (!yaPuestos.has(el)) fuera.push({ tipo: 'punto', texto: texto(el) });
                } else if (el.matches('.fi')) {
                    // Comparacion: «Como esta hoy» contra «Como queda».
                    const h3 = el.querySelector('h3');
                    if (h3) { yaPuestos.add(h3); fuera.push({ tipo: 'punto', texto: texto(h3) }); }
                    fuera.push({ tipo: 'maqueta', foto: marcar(el),
                                 pie: texto(el.querySelector('.exp')) });
                } else if (el.matches('.uno')) {
                    fuera.push({ tipo: 'maqueta', foto: marcar(el),
                                 rot: texto(el.querySelector('.rot')),
                                 pie: texto(el.querySelector('.exp')) });
                } else if (el.matches('.f')) {
                    fuera.push({ tipo: 'calendario', texto: texto(el) });
                } else if (el.matches('.lst')) {
                    fuera.push({ tipo: 'lista', texto: texto(el) });
                } else if (el.matches('.pieg')) {
                    fuera.push({ tipo: 'pie', texto: texto(el) });
                } else if (el.matches('.nuestro')) {
                    fuera.push(nuestra(el));
                }
            }
        }

        // ── 2 · Los otros dos documentos y la revision de Nutricion ──
        for (const doc of document.querySelectorAll('.otrodoc')) {
            fuera.push({ tipo: 'documento', titulo: texto(doc.querySelector('h1')),
                         eti: texto(doc.querySelector('.eti')),
                         bajadas: [...doc.querySelectorAll('.baj')].map(texto) });
            for (const el of doc.querySelectorAll('.bloque > h3, .punto-otro, ul.menores > li, .bloque > .suyo-pie')) {
                if (el.matches('h3')) {
                    fuera.push({ tipo: 'seccion', texto: texto(el) });
                } else if (el.matches('li')) {
                    fuera.push({ tipo: 'menor', texto: texto(el) });
                } else if (el.matches('.suyo-pie')) {
                    fuera.push({ tipo: 'sub', texto: texto(el) });
                } else {
                    // Un hallazgo o un punto de los documentos transcritos.
                    const card = el.querySelector('.nuestro');
                    fuera.push({
                        tipo: 'punto', texto: texto(el.querySelector('h4')),
                        pie: texto(el.querySelector('.suyo-pie')),
                        medida: texto(el.querySelector('.medida')),
                        maqueta_texto: [...el.querySelectorAll('.suyo-maqueta li')].map(li => li.innerText.trim()),
                    });
                    if (card) fuera.push(nuestra(card));
                }
            }
        }
        // ── LAS TARJETAS QUE CAYERON UN PUNTO MAS ABAJO ──
        // Nuestra tarjeta se mete en el HTML de Jesus por posicion en el texto, y en unos
        // pocos puntos el navegador acaba colgandola del punto SIGUIENTE. Se detectan
        // comparando con su ancla -- el titulo que tienen justo encima en la pagina -- y se
        // devuelven al final del bloque al que pertenecen. Las demas no se tocan: el orden
        // del DOM ya es el bueno, y dos maquetas seguidas son el «hoy» y el «como queda»
        // del mismo punto, no un desorden.
        for (let i = fuera.length - 1; i >= 0; i--) {
            const v = fuera[i];
            if (v.tipo !== 'veredicto' || !v.ancla) continue;
            let j = -1;
            for (let k = i - 1; k >= 0; k--) if (fuera[k].tipo === 'punto') { j = k; break; }
            if (j < 0 || fuera[j].texto === v.ancla) continue;
            fuera.splice(i, 1);
            fuera.splice(j, 0, v);   // justo antes del punto ajeno = al final del suyo
        }
        return fuera;
    });

    // Las fotos de sus maquetas, una por una.
    let fotos = 0;
    for (const it of items) {
        if (!it.foto) continue;
        const el = p.locator(`[data-foto="${it.foto}"]`).first();
        try {
            await el.scrollIntoViewIfNeeded();
            await p.waitForTimeout(120);
            await el.screenshot({ path: path.join(CARPETA, `${it.foto}.png`) });
            fotos++;
        } catch (e) {
            it.foto = null;
        }
    }

    // Y las nuestras, que vienen incrustadas: se sacan a fichero.
    let nuestras = 0;
    for (const [i, it] of items.entries()) {
        if (!it.imagen || !it.imagen.startsWith('data:image')) { it.imagen = null; continue; }
        const datos = Buffer.from(it.imagen.split(',')[1], 'base64');
        const nombre = `nuestra-${i}.jpg`;
        fs.writeFileSync(path.join(CARPETA, nombre), datos);
        it.imagen = nombre;
        nuestras++;
    }

    fs.writeFileSync(SALIDA, JSON.stringify(items, null, 1), 'utf8');
    const cuenta = items.reduce((a, x) => (a[x.tipo] = (a[x.tipo] || 0) + 1, a), {});
    console.log(`${items.length} piezas · ${fotos} maquetas suyas · ${nuestras} capturas nuestras`);
    console.log(JSON.stringify(cuenta));
    await nav.close();
})();
