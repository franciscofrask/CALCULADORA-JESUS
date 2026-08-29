/**
 * El informe en PDF.
 *
 * El fichero del informe es un TROZO de HTML (asi lo quiere el artifact: sin <html> ni
 * <body>), asi que aqui se envuelve en un documento de verdad, se le fuerza el tema claro
 * -- un PDF en negro se gasta el toner y se lee peor -- y se le añaden las reglas de
 * impresion: que no se parta una ficha por la mitad y que las tablas no se salgan.
 *
 * Uso:  node _guia/_informe_a_pdf.js [fichero.html] [salida.pdf]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ENTRADA = process.argv[2] || path.join(__dirname, '_informe_doc_todo_2808.html');
// AL ESCRITORIO, no a la carpeta del proyecto (Francisco, 28-08): es donde estan los demas
// documentos que se le pasan a Jesus, y ahi no se cuela en el repo.
const ESCRITORIO = path.join(process.env.USERPROFILE || require('os').homedir(), 'Desktop');
const SALIDA = process.argv[3] || path.join(ESCRITORIO, '12EN12 · Lo trabajado el 28 de agosto.pdf');

const IMPRESION = `
<style>
  /* El tema claro, pase lo que pase: el visor de PDF no tiene tema. */
  :root{
    --papel:#FFFFFF; --papel2:#FFFFFF; --tinta:#1A1512; --tinta2:#57504A;
    --tinta3:#8B827B; --linea:#E8E1DA; --linea2:#D6CCC2;
    --acc:#D9451C; --acc-suave:rgba(217,69,28,.09);
    --ok:#177E4B; --ok-suave:rgba(23,126,75,.09);
    --espera:#8A6A18; --espera-suave:rgba(138,106,24,.09);
    --nada:#7A736C; --nada-suave:rgba(122,115,108,.09);
    --sombra:none;
  }
  @page { margin: 14mm 12mm; }
  body { font-size: 10.5pt; }
  .hoja { max-width: none; padding: 0; }
  /* Una ficha no se parte por la mitad, y su cabecera no se queda sola al pie. */
  .punto, .aviso, .datos, table { break-inside: avoid; page-break-inside: avoid; }
  .pcab { break-after: avoid; page-break-after: avoid; }
  h2 { break-after: avoid; page-break-after: avoid; margin-top: 26px; }
  .top { padding-top: 0; }
  /* En papel no hay barra de scroll: la tabla ancha se encoge en vez de cortarse. */
  .scroll { overflow: visible; }
  .mapa { font-size: 9pt; }
  .ficheros { word-break: normal; }
</style>`;

(async () => {
  const trozo = fs.readFileSync(ENTRADA, 'utf8');
  const doc = `<!doctype html><html lang="es"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    </head><body>${trozo}${IMPRESION}</body></html>`;

  const tmp = path.join(__dirname, '_informe_para_imprimir.html');
  fs.writeFileSync(tmp, doc, 'utf8');

  const nav = await chromium.launch();
  const page = await (await nav.newContext({ colorScheme: 'light' })).newPage();
  await page.goto('file:///' + tmp.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
  await page.emulateMedia({ media: 'print', colorScheme: 'light' });
  await page.pdf({
    path: SALIDA,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: `<div style="width:100%;font-size:8px;color:#8B827B;
      font-family:'Segoe UI',sans-serif;padding:0 12mm;display:flex;justify-content:space-between">
      <span>12EN12 · lo trabajado el 28 de agosto de 2026</span>
      <span class="pageNumber"></span>/<span class="totalPages"></span></div>`,
    margin: { top: '14mm', bottom: '16mm', left: '12mm', right: '12mm' },
  });
  await nav.close();
  fs.unlinkSync(tmp);
  const kb = Math.round(fs.statSync(SALIDA).size / 1024);
  console.log(`PDF generado: ${SALIDA}  (${kb} KB)`);
})();
