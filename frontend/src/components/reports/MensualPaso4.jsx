/**
 * PASO 4 DEL MENSUAL · TU PLAN NUEVO Y MI FEEDBACK DIRECTO
 *
 * Documento «El reporte mensual» (1-09-2026). Hasta ahora, al enviar el mensual, el
 * cliente veía una tarjeta con «Reporte enviado» y una línea. El documento convierte eso
 * en un paso del reporte, y con motivo: es donde se le entrega algo.
 *
 * Dos bloques, y la diferencia entre los dos es el tiempo:
 *
 *   YA LO TIENES              su informe, ahora mismo, con el botón para abrirlo.
 *   ANTES DEL PRÓXIMO ...     el programa nuevo, que lo escribe una persona.
 *
 * EL DÍA LO DICE EL SERVIDOR (`promesa_dia`), no está escrito aquí. La promesa se decide
 * en un solo sitio (`core/promesa_del_reporte.py`) y de ahí sale también el aviso que le
 * salta al equipo si ese día llega sin contestar. Escribir el día a mano en esta pantalla
 * era la forma segura de que un día dijeran cosas distintas.
 */
import React from 'react';
import { ArrowRight } from 'lucide-react';
import { CabeceraDelMensual, RotuloDelPaso } from './PasosDelMensual';

const ORANGE = '#FF671F';

const MensualPaso4 = ({ plazo, promesaDia, informeId, onVerInforme }) => {
    const dia = promesaDia || 'viernes';

    return (
        <div className="space-y-4" data-testid="mensual-paso4">
            <CabeceraDelMensual paso={4} plazo={plazo} />
            <RotuloDelPaso paso={4} />

            {/* ── YA LO TIENES ──
                SOLO SI DE VERDAD LO TIENE. El documento del 1-09 lo da por entregado al
                momento («Te lo entrego ya»), pero desde T9 (doc 16-08) el informe no le sale
                al cliente hasta que Jesús lo revisa: se le prometió «con mi feedback», y
                enseñarle antes el montado a secas es entregarle media promesa.

                Las dos cosas no pueden ser verdad a la vez, así que aquí manda el dato: la
                tarjeta sale cuando el informe ya se puede abrir, y no sale cuando no. Lo que
                nunca hace es decirle «ya lo tienes» y dejarle sin nada que pulsar. */}
            {informeId && (
                <div className="rounded-2xl bg-card border border-border p-4 space-y-3"
                    data-testid="paso4-informe">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        Ya lo tienes
                    </p>
                    <p className="text-base font-bold text-foreground">Tu informe del mes</p>
                    <p className="text-sm text-foreground/80">
                        Te lo entrego ya. Es un <b>análisis objetivo</b> que sale de toda la
                        información que has dejado guardada en la calculadora.
                    </p>
                    <p className="text-sm text-foreground/80">
                        Recuerda que <b>cuantos más datos registres, mejores informes recibirás</b> y
                        mejores ajustes, por supuesto.
                    </p>
                    <button type="button" onClick={() => onVerInforme(informeId)}
                        data-testid="paso4-ver-informe"
                        className="inline-flex items-center gap-1.5 text-sm font-bold"
                        style={{ color: ORANGE }}>
                        Ver mi informe
                        <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* ── ANTES DEL PRÓXIMO ... ── */}
            <div className="rounded-2xl border p-4 space-y-3"
                style={{ borderColor: `${ORANGE}55`, backgroundColor: `${ORANGE}0D` }}
                data-testid="paso4-programa">
                <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                    Antes del próximo {dia}
                </p>
                <p className="text-base font-bold text-foreground">Nuevo programa y feedback</p>
                <p className="text-sm text-foreground/80">
                    Analizamos tus respuestas, comparamos fotos y métricas y, a partir de ahí,
                    ajustamos tus macros, revisamos tu plan de suplementos y preparamos la rutina
                    para las próximas 4 semanas.
                </p>
                <p className="text-sm text-foreground/80">
                    Recibirás todo antes del {dia}. Te aviso por aquí.
                </p>
            </div>

            {/* ── Y MIENTRAS TANTO, MÍRATE ── */}
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground px-1">
                Y mientras tanto, mírate
            </p>
        </div>
    );
};

export default MensualPaso4;
