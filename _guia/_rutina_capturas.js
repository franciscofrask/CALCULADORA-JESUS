/**
 * La pantalla de Rutina del cliente en movil, tablet y PC, y avisa de lo que se desborda.
 *
 *   TOKEN=<jwt del cliente> node _guia/_rutina_capturas.js
 *
 * Con el Chrome DE VERDAD (channel: 'chrome'): el Chromium de Playwright no pinta PDFs
 * dentro de un <object>, asi que con el no se puede juzgar la caja del visor.
 */
const { chromium } = require('playwright');

const WEB = process.env.WEB || 'http://localhost:3000';
const TOKEN = process.env.TOKEN;
const TAMANOS = [['movil', 390, 844], ['tablet', 820, 1180], ['pc', 1440, 900]];

(async () => {
    if (!TOKEN) { console.error('  falta TOKEN=<jwt del cliente>'); process.exit(1); }
    const nav = await chromium.launch({ channel: 'chrome' });
    for (const [nombre, ancho, alto] of TAMANOS) {
        const p = await nav.newPage({ viewport: { width: ancho, height: alto } });
        await p.goto(WEB);
        await p.evaluate(t => localStorage.setItem('token', t), TOKEN);
        await p.goto(`${WEB}/dashboard/routine`);
        await p.waitForTimeout(9000);
        const m = await p.evaluate(() => {
            const v = window.innerWidth;
            const fuera = [...document.querySelectorAll('*')]
                .filter(e => e.getBoundingClientRect().right > v + 1 && getComputedStyle(e).position !== 'fixed')
                .slice(0, 5).map(e => `${e.tagName}.${String(e.className).slice(0, 34)}`);
            const cortados = [...document.querySelectorAll('[data-testid="semana-rutina-tira"] p[title]')]
                .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
                .map(e => e.getAttribute('title'));
            return { alto: document.documentElement.scrollHeight, seVa: document.documentElement.scrollWidth > v + 2, fuera, cortados };
        });
        console.log(`  ${nombre.padEnd(7)} ${String(ancho).padStart(4)}px · pagina ${m.alto}px`
            + ` · se va a lo ancho: ${m.seVa ? 'SI' : 'no'}`
            + (m.fuera.length ? ` · se salen: ${m.fuera.join(', ')}` : '')
            + (m.cortados.length ? ` · GRUPOS CORTADOS: ${m.cortados.join(' | ')}` : ' · grupos: enteros'));
        await p.screenshot({ path: `_guia/_rutina_${nombre}.png`, fullPage: true });
    }
    await nav.close();
})();
