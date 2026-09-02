/**
 * PASO 3 DEL QUINCENAL · TU FEEDBACK Y TUS AJUSTES
 *
 * «Todo lo validado antes del 1 de septiembre», «Las tres pantallas»:
 *
 *     3  TU FEEDBACK Y TUS AJUSTES
 *     Este tercer paso es cosa nuestra.
 *     Recibirás respuesta antes del viernes a las 3, hora de España.
 *
 * ES UN PASO Y NO UN «GRACIAS». Sale en la lista de arriba desde la primera pantalla, así
 * que el cliente sabe desde el principio que después de mandar el reporte pasa algo. Y por
 * eso la frase le da una HORA: el «Ya lo mandaste, lo estamos mirando» de antes no
 * comprometía a nada. Es el mismo cambio que la tarjeta en Hecho.
 *
 * EL DÍA Y LA HORA LOS DICE EL SERVIDOR (`promesa_dia`, de `core/promesa_del_reporte.py`),
 * que es de donde sale también el aviso que le salta al equipo si ese día llega sin
 * contestar. Escribirlos aquí a mano era la forma segura de que un día dijeran cosas
 * distintas.
 */
import React from 'react';
import { CabeceraDePasos, RotuloDelPaso, PASOS_DEL_QUINCENAL, ROTULOS_DEL_QUINCENAL } from './PasosDelMensual';

const ORANGE = '#FF671F';

const QuincenalPaso3 = ({ plazo, promesaDia, titulo = 'Reporte quincenal' }) => (
    <div className="space-y-4" data-testid="quincenal-paso3">
        <CabeceraDePasos paso={3} plazo={plazo} pasos={PASOS_DEL_QUINCENAL} titulo={titulo} />
        <RotuloDelPaso paso={3} rotulos={ROTULOS_DEL_QUINCENAL} />

        <div className="rounded-2xl border p-4 space-y-2"
            style={{ borderColor: `${ORANGE}55`, backgroundColor: `${ORANGE}0D` }}
            data-testid="quincenal-promesa">
            <p className="text-base font-bold text-foreground">
                Este tercer paso es cosa nuestra.
            </p>
            <p className="text-sm text-foreground/80">
                Recibirás respuesta antes del {promesaDia || 'viernes'} a las 3, hora de España.
            </p>
        </div>
    </div>
);

export default QuincenalPaso3;
