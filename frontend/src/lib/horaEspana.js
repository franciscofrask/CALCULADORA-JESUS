/**
 * LA HORA DE ESPAÑA EN EL FRONT (doc del 16-08, regla 1: «Todo en hora de España. Nada en
 * UTC»).
 *
 * El backend ya tiene su `core/tiempo.py`; esto es el mismo criterio del lado del
 * navegador. Importa porque lo que se pinta no es «una hora»: es «ayer, 21:40» y «te
 * quedan 2 días», y las dos cosas cambian de valor según dónde esté el reloj de quien
 * mira. Fiarse de la zona del aparato funcionaba mientras todos los clientes estaban en
 * España; el plazo de un reporte se anuncia «a las 18:00 h España» y tiene que decir lo
 * mismo desde Canarias o desde Dubái.
 *
 * Las fechas llegan de Mongo en ISO UTC. Las viejas (importadas) a veces vienen sin zona:
 * se asumen UTC, que es como escribe todo el backend.
 */
const ZONA = 'Europe/Madrid';

const partes = (fecha, opciones) => Object.fromEntries(
    new Intl.DateTimeFormat('es-ES', { timeZone: ZONA, ...opciones })
        .formatToParts(fecha)
        .map((p) => [p.type, p.value]),
);

/** Un ISO (o Date) a Date. Devuelve null si no se entiende: quien pinta ya sabe vivir sin ello. */
export function aFecha(valor) {
    if (!valor) return null;
    if (valor instanceof Date) return Number.isNaN(valor.getTime()) ? null : valor;
    let texto = String(valor).trim().replace(' ', 'T');
    if (!/(Z|[+-]\d{2}:?\d{2})$/.test(texto)) texto += 'Z';
    const d = new Date(texto);
    return Number.isNaN(d.getTime()) ? null : d;
}

/** El día de esa fecha PARA EL CLIENTE: 'YYYY-MM-DD' en hora de España. */
export function diaEnEspana(fecha) {
    const p = partes(fecha, { year: 'numeric', month: '2-digit', day: '2-digit' });
    return `${p.year}-${p.month}-${p.day}`;
}

/** '21:40' en hora de España. */
export function horaEnEspana(fecha) {
    const p = partes(fecha, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    return `${p.hour}:${p.minute}`;
}

export const hoyEnEspana = () => diaEnEspana(new Date());

const numeroDeDia = (dia) => Math.floor(Date.parse(`${dia}T00:00:00Z`) / 86400000);

/** Días enteros entre ese día y hoy, en España. Positivo = ya pasó. */
export function diasDesdeHoy(dia) {
    return numeroDeDia(hoyEnEspana()) - numeroDeDia(dia);
}

/** 'jueves, 20 de agosto' (la cabecera de Inicio; la mayúscula la pone el CSS). */
export function fechaLargaDeHoy() {
    const p = partes(new Date(), { weekday: 'long', day: 'numeric', month: 'long' });
    return `${p.weekday}, ${p.day} de ${p.month}`;
}

/**
 * «ayer, 21:40». Lo que sustituye a la palabra «pendiente» en el cierre del día: la fecha
 * y la hora del último registro dicen si se lleva al día mejor que una etiqueta.
 */
export function etiquetaMomento(valor) {
    const d = aFecha(valor);
    if (!d) return '';
    const dias = diasDesdeHoy(diaEnEspana(d));
    const hora = horaEnEspana(d);
    if (dias <= 0) return `hoy, ${hora}`;
    if (dias === 1) return `ayer, ${hora}`;
    const p = partes(d, { day: 'numeric', month: 'long' });
    return `${p.day} de ${p.month}, ${hora}`;
}

/**
 * El plazo de un reporte: «Hasta el lunes 24 a las 18:00 h España · te quedan 2 días».
 *
 * La hora sale del plazo de verdad, no escrita a mano: cuando la ventana se mueva a las
 * 18:00 de España (T7 y T8) esta línea lo dirá sola. `pasado` es lo que hace desaparecer
 * la línea de Inicio en cuanto se cierra.
 */
export function textoPlazo(valor) {
    const d = aFecha(valor);
    if (!d) return null;
    const pasado = d.getTime() <= Date.now();
    const p = partes(d, { weekday: 'long', day: 'numeric' });
    const dias = -diasDesdeHoy(diaEnEspana(d));
    const cola = dias > 1 ? ` · te quedan ${dias} días`
        : dias === 1 ? ' · te queda 1 día'
        : ' · hoy es el último día';
    return {
        pasado,
        dias,
        texto: `Hasta el ${p.weekday} ${p.day} a las ${horaEnEspana(d)} h España${pasado ? '' : cola}`,
    };
}
