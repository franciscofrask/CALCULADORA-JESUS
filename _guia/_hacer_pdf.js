const { chromium } = require('C:/Users/Administrador/Desktop/CALCULADORA-JESUS/node_modules/playwright');
const { pathToFileURL } = require('url');

const entrada = process.argv[2];
const salida = process.argv[3];

(async () => {
    const nav = await chromium.launch();
    const p = await (await nav.newContext()).newPage();
    await p.goto(pathToFileURL(entrada).href, { waitUntil: 'networkidle' });
    await p.pdf({
        path: salida,
        format: 'A4',
        printBackground: true,
        margin: { top: '16mm', bottom: '18mm', left: '15mm', right: '15mm' },
        displayHeaderFooter: true,
        headerTemplate: '<div></div>',
        footerTemplate:
            '<div style="width:100%;font-family:Segoe UI,sans-serif;font-size:7pt;color:#7d7365;' +
            'padding:0 15mm;display:flex;justify-content:space-between;">' +
            '<span>12EN12 &middot; parte del 27 de agosto de 2026</span>' +
            '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    });
    await nav.close();
    console.log('PDF ->', salida);
})();
