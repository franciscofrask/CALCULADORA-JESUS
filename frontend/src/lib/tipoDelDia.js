/**
 * ENTRENO O DESCANSO, CUANDO NADIE LO HA DICHO TODAVÍA.
 *
 * La app abría TODOS los días en «Entreno», y eso no era un valor por defecto cualquiera:
 * en el cliente que miró Jesús son 60 g de hidratos y 45 de perientreno de más un domingo.
 * Medido en producción el 09-08 sobre las 14.027 dietas guardadas, **14.025 dicen
 * «entrenamiento» y 2 dicen «descanso»**: prácticamente nadie lo marca nunca, así que casi
 * todo el mundo comía de día de entreno todos los días, incluidos los domingos.
 *
 * Aquel día se dejó apuntado que cuál debía ser la regla automática era una decisión que no
 * me tocaba a mí. Ya está tomada:
 *
 *     «Los días sábado y domingo por defecto son de descanso» (Francisco, 3-09-2026).
 *
 * ES SOLO UN VALOR POR DEFECTO, no un candado: el selector de Entreno/Descanso sigue ahí y
 * el día que él lo toque manda su decisión. Y solo se aplica al día que NO tiene nada
 * guardado; a un día ya configurado no se le toca el tipo, que fue el fallo 01 de la
 * revisión de Nutrición del 1-09.
 *
 * EL GEMELO DEL SERVIDOR es `core/tipo_del_dia.py`, que es el que usa el asistente cuando
 * monta un día por el chat. Si algún día cambia la regla, son los dos a la vez.
 */

//: Los días de la semana que se abren en descanso. `getDay()`: 0 domingo ... 6 sábado.
export const DIAS_QUE_ABREN_EN_DESCANSO = [6, 0];

/**
 * El tipo con el que abrir una fecha «AAAA-MM-DD».
 *
 * OJO CON LA FECHA. `new Date('2026-09-05')` se lee como UTC y en un huso por detrás de
 * Greenwich devuelve el día ANTERIOR: un sábado se convertiría en viernes y abriría en
 * entreno. Por eso se parte la cadena y se construye la fecha con sus tres números, que sí
 * es local. Es la trampa de siempre con las fechas sin zona.
 */
export const tipoPorDefecto = (fechaISO) => {
    const trozos = String(fechaISO || '').split('-').map(Number);
    if (trozos.length !== 3 || trozos.some((n) => !Number.isFinite(n))) return 'entrenamiento';
    const [anio, mes, dia] = trozos;
    const diaDeLaSemana = new Date(anio, mes - 1, dia).getDay();
    return DIAS_QUE_ABREN_EN_DESCANSO.includes(diaDeLaSemana) ? 'descanso' : 'entrenamiento';
};
