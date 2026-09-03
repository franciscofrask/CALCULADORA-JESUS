/**
 * La línea de la fecha del Inicio, sobre la foto del hero: «jueves, 3 de septiembre · día de
 * descanso». Francisco (3-09): «no se lee bien, casi no se nota».
 *
 * Uso:  node _guia/_capturar_inicio_fecha.js [sufijo]
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const SUFIJO = process.argv[2] || 'antes';

const CARPETA = '_guia/_inicio_fecha_0309';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

(async () => {
    const r = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    });
    const TOKEN = (await r.json()).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    const nav = await chromium.launch();
    for (const [ancho, alto, movil] of [[1280, 900, false], [390, 844, true]]) {
        const ctx = await nav.newContext({ viewport: { width: ancho, height: alto },
            isMobile: movil, hasTouch: movil, deviceScaleFactor: 2 });
        const p = await ctx.newPage();
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => {
            localStorage.clear(); localStorage.setItem('token', t);
            localStorage.setItem('primera-dieta-hecha', '1');
            localStorage.setItem('nutrition-intro-seen', '1');
        }, TOKEN);
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(6000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(800);
        }
        await p.waitForTimeout(1500);
        console.log(`\n── ${ancho} px ──`);
        console.log('   ruta:', await p.evaluate(() => location.pathname));
        const linea = p.locator('[data-testid="inicio-fecha"]').first();
        if (await linea.count()) {
            console.log('   dice :', (await linea.innerText()).replace(/\s+/g, ' ').trim());
            console.log('   css  :', JSON.stringify(await linea.evaluate((e) => {
                const s = getComputedStyle(e);
                return { color: s.color, textShadow: s.textShadow, fontSize: s.fontSize, fontWeight: s.fontWeight };
            })));
        } else console.log('   NO ENCUENTRO la línea de la fecha');
        // La OTRA línea con la misma frase: la de la tarjeta «Tu dieta hoy», que va sobre
        // fondo liso. Sirve de contraste para saber cuál es la que no se lee.
        const enTarjeta = p.locator('[data-testid="hoy-fecha"]').first();
        if (await enTarjeta.count()) {
            console.log('   tarjeta dice :', (await enTarjeta.innerText()).replace(/\s+/g, ' ').trim());
            console.log('   tarjeta css  :', JSON.stringify(await enTarjeta.evaluate((e) => {
                const s = getComputedStyle(e);
                return { color: s.color, textShadow: s.textShadow, fontSize: s.fontSize, fontWeight: s.fontWeight };
            })));
        } else console.log('   (sin tarjeta «Tu dieta hoy» a la vista)');
        await p.screenshot({ path: `${CARPETA}/${ancho}_${SUFIJO}_pantalla.png`, fullPage: true });
        const banner = p.locator('[data-testid="inicio-banner"]').first();
        if (await banner.count()) await banner.screenshot({ path: `${CARPETA}/${ancho}_${SUFIJO}.png` });
        else await p.screenshot({ path: `${CARPETA}/${ancho}_${SUFIJO}.png` });
        await ctx.close();
    }
    await nav.close();
    console.log(`\n   Capturas en ${CARPETA}/`);
})();
