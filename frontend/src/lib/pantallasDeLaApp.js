/**
 * LOS INTERRUPTORES DE LA APP, EN UN SOLO SITIO.
 *
 * La lista estaba dentro de la pantalla de Planes, que es donde nacieron (doc 16-08). Al
 * sacarlos a su propia pantalla de Ajustes (punto 64) la lista pasa a leerse desde dos
 * sitios -- Ajustes, que los enciende para TODOS, y «Mi modo pruebas», que los enciende
 * solo para tu cuenta -- así que vive aquí para que no puedan discrepar: si un día se
 * añade una pantalla nueva, aparece en los dos a la vez o no aparece en ninguno.
 *
 * Lo que guardan estas claves está en `db.app_settings`, y se tocan desde la app para
 * poder apagar una pantalla SIN desplegar.
 */
export const PANTALLAS_APP = [
    { clave: 'frase_del_dia', label: 'La frase del día en Inicio', ayuda: 'Muestra una frase del día en la portada de Inicio del cliente.' },
    { clave: 't1_inicio_nuevo', label: 'Inicio nuevo (Lo que toca hoy)', ayuda: 'La portada nueva del cliente: «Lo que toca hoy» (macros, suplementos, entreno) y «Pendiente».' },
    { clave: 't2_suplementos', label: 'Suplementos del cliente', ayuda: 'La pantalla de suplementos del cliente.' },
    { clave: 't3_entreno', label: 'Entreno (rutina y registro)', ayuda: 'Hace visible al cliente la rutina y el registro de sus entrenos.' },
    { clave: 't4_cierre_nuevo', label: 'Cierre del día nuevo', ayuda: 'El nuevo cierre del día del cliente («¿cómo fue hoy?»).' },
    { clave: 't5_diario', label: 'El Diario', ayuda: 'El Diario, dentro de Seguimiento.' },
    { clave: 't6_evolucion', label: 'Evolución completa del cliente', ayuda: 'La Evolución completa del cliente: medidas y fotos.' },
    { clave: 't10_avisos_nuevos', label: 'Los avisos nuevos', ayuda: 'Los avisos nuevos del cliente (la campanita).' },
    // P59 del doc 23-08. OJO: encenderlo manda CORREOS DE VERDAD a todos los clientes
    // con reporte pendiente, entren o no en la app. Nace apagado por eso.
    { clave: 'correos_avisos', label: 'Los avisos del reporte, por correo', ayuda: 'Manda por correo los avisos del reporte (se abre, último día, no nos llegó) y del fin de ciclo, sin esperar a que el cliente entre en la app. Un aviso, un correo: nunca se repite.' },
];

//: El que manda correos de verdad. Se avisa aparte antes de encenderlo.
export const MANDA_CORREOS = 'correos_avisos';

export default PANTALLAS_APP;
