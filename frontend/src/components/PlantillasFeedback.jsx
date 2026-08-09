/**
 * Los cuatro mensajes plantilla del informe (punto 4.1 de la revisión del 09-08).
 *
 * El coach escribe el feedback de cada reporte a mano, uno por uno, y son cuatro cosas las
 * que dice casi siempre: que va bien, que toca subir hidratos, que no se mueve o que se ha
 * ido para atrás. Cuatro botones que lo escriben por él y que luego puede tocar.
 *
 * OJO CON LOS TEXTOS: los de abajo son míos. Jesús nombra los cuatro mensajes en su
 * revisión ("va bien y se sigue", "toca subir hidrato", "no se mueve", "se ha ido para
 * atrás") pero no los transcribe, y no están en el documento de textos del 06-08. Lo que hay
 * aquí es una redacción de arranque en su registro -- tuteo, directo, sin adornos -- para
 * que el botón exista. **Cuando dé los suyos se cambian aquí y ya**: viven en un solo sitio
 * justo por eso.
 *
 * No pisan lo escrito: si ya hay texto, se añade debajo. Borrar sin querer el comentario que
 * llevas dos minutos escribiendo por pulsar una plantilla sería peor que no tenerlas.
 */
import React from 'react';

export const PLANTILLAS_FEEDBACK = [
    {
        id: 'va_bien',
        etiqueta: 'Va bien, se sigue',
        texto: 'Vas bien. El peso se está moviendo al ritmo que buscamos, así que no tocamos '
            + 'nada: seguimos con los mismos macros otra quincena. Lo que estás haciendo '
            + 'funciona, y cuando algo funciona no se cambia.',
    },
    {
        id: 'subir_hc',
        etiqueta: 'Toca subir hidratos',
        texto: 'Te subo los hidratos. Llevas un tiempo cumpliendo y el cuerpo ya se ha '
            + 'adaptado a lo que come, así que le damos un poco más para que siga '
            + 'respondiendo. Sube solo lo que te pongo, ni un gramo más, y me cuentas en el '
            + 'próximo reporte cómo lo llevas.',
    },
    {
        id: 'no_se_mueve',
        etiqueta: 'No se mueve',
        texto: 'El peso lleva dos semanas parado. Antes de tocar los macros quiero descartar '
            + 'lo de siempre: pésate en ayunas y en las mismas condiciones, y dime con '
            + 'sinceridad si estás cumpliendo la dieta entre semana y el fin de semana '
            + 'igual. Si el registro está bien hecho, en el próximo ajuste lo movemos.',
    },
    {
        id: 'atras',
        etiqueta: 'Se ha ido para atrás',
        texto: 'Hemos perdido terreno respecto al mes pasado. No pasa nada y no es para '
            + 'agobiarse, pero hay que saber por qué: cuéntame qué ha cambiado estas '
            + 'semanas (viajes, cenas fuera, entrenos que se han caído, dormir mal). Con eso '
            + 'decido si el problema es el plan o es la adherencia, que se arreglan de '
            + 'maneras distintas.',
    },
];

/**
 * Los cuatro botones. `onInsertar` recibe el texto de la plantilla ya combinado con lo que
 * hubiera escrito: el que llama solo tiene que guardarlo en su estado.
 */
const PlantillasFeedback = ({ actual = '', onInsertar, testid = 'plantillas-feedback' }) => {
    const insertar = (texto) => {
        const previo = (actual || '').trim();
        onInsertar(previo ? `${previo}\n\n${texto}` : texto);
    };

    return (
        <div className="mt-1.5" data-testid={testid}>
            <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">
                O empieza por una de estas
            </p>
            <div className="flex flex-wrap gap-1.5">
                {PLANTILLAS_FEEDBACK.map(p => (
                    <button key={p.id} type="button" onClick={() => insertar(p.texto)}
                        title={p.texto} data-testid={`plantilla-${p.id}`}
                        className="text-[11px] px-2.5 py-1.5 rounded-lg bg-[#0A0A0A] border border-[#333] text-white/70 hover:border-[#FF671F]/60 hover:text-white transition-colors">
                        {p.etiqueta}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default PlantillasFeedback;
