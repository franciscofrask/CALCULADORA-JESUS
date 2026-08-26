/**
 * Convierte un HTML local en PDF con el Chrome de verdad.
 *
 *   node _guia/_hacer_pdf.js entrada.html "salida.pdf"
 */
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const path = require('path');

const entrada = process.argv[2];
const salida = process.argv[3];

(async () => {
    if (!entrada || !salida) {
        console.error('  uso: node _guia/_hacer_pdf.js entrada.html salida.pdf');
        process.exit(1);
    }
    const nav = await chromium.launch({ channel: 'chrome' });
    const p = await nav.newPage();
    await p.goto(pathToFileURL(path.resolve(entrada)).href);
    await p.waitForTimeout(1500);
    await p.pdf({
        path: salida,
        format: 'A4',
        printBackground: true,
        margin: { top: '18mm', bottom: '16mm', left: '16mm', right: '16mm' },
    });
    await nav.close();
    console.log('  PDF:', salida);
})();
