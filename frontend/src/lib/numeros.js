/**
 * LOS NÚMEROS, ESCRITOS COMO LOS ESCRIBE UNA PERSONA.
 *
 * Jesús, 15-08-2026 (fallo 43): «34.2/37.5g», «17.8/10g», «sobran 7.8g». Punto en vez de
 * coma, y decimales que muchas veces son cero. En español la coma es el separador decimal,
 * y «30 g» se lee mejor que «30.0g».
 *
 * Cada pantalla de Nutrición tenía su propio `fmt1` con el mismo `toFixed(1)` dentro, así
 * que la coma había que ponerla en siete sitios o no se ponía en ninguno. Aquí está una vez.
 *
 * `redondeo` es el múltiplo al que se ajusta antes de escribir: 0,1 para lo servido y 0,5
 * para los objetivos (así lo hacía Calma con `stepRedondeo`).
 */

/** Un número con coma decimal y sin decimales cuando son cero: 30, 34,2. */
export const num = (valor, redondeo = 0.1) => {
    const n = Number(valor) || 0;
    const paso = redondeo > 0 ? redondeo : 0.1;
    const r = Math.round(n / paso) * paso;
    // El round por el paso deja colas de coma flotante (7.800000000000001): se corta a los
    // decimales que el paso puede producir.
    const decimales = paso >= 1 ? 0 : String(paso).split('.')[1].length;
    const texto = Number(r.toFixed(decimales)).toString();
    return texto.replace('.', ',');
};

/** Lo servido y lo que falta o sobra: un decimal. */
export const num1 = (valor) => num(valor, 0.1);

/** Los objetivos: al medio gramo, como Calma. */
export const numMedio = (valor) => num(valor, 0.5);

/** Enteros (los totales del día): sin decimales y sin coma que poner. */
export const num0 = (valor) => num(valor, 1);

/**
 * Los mismos redondeos, pero en NÚMERO, para que las cuentas cuadren con lo escrito.
 *
 * «54/63,5 g · faltan 9,3 g» (17-08-2026): el objetivo se escribe al medio gramo y el
 * restante salía del valor exacto, así que la resta que hace el cliente no le daba. Quien
 * escriba una diferencia al lado de dos cifras redondeadas tiene que restar ESAS.
 */
export const alMedio = (valor) => Math.round((Number(valor) || 0) / 0.5) * 0.5;
export const alDecima = (valor) => Math.round((Number(valor) || 0) / 0.1) * 0.1;
