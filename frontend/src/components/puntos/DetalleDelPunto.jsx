/**
 * UN PUNTO DE CONTROL, ABIERTO (doc de Jesús del 2-09, «Los puntos de control»; fase 3,
 * 4-09). La pantalla «Final bloque 2 · Ciclo 3 / 25 de julio» de su maqueta.
 *
 * Contesta «¿cómo estaba yo entonces?»: su foto de ese día, LOS MACROS QUE LLEVABA
 * ENTONCES, sus medidas y su grasa. La regla de Jesús para lo que falte: «cuando falta algo
 * se dice (no lo mediste en este reporte), nunca un hueco». Por eso cada bloque está
 * siempre, con su dato o con su frase.
 *
 * Los macros aquí se CONSULTAN, no se estudian: «el macro es un dato del momento y cuelga
 * de un punto». La tabla con los catorce ajustes vive en Mis macros y aquí no se pinta
 * ninguna lista. Se escriben en palabras, como «Tu último ajuste» de ReportsPage.
 *
 * Todo lo que se enseña viene en el propio punto de `GET /reports/puntos` (peso, medidas,
 * grasa, macros vigentes ese día, fotos, etiquetas): aquí no se pide nada más que las
 * fotos, por su blob y con la sesión.
 */
import React from 'react';
import { ChevronLeft } from 'lucide-react';
import { kg } from '../../lib/pesoValido';
import { MEDIDAS, valorAnterior } from '../../lib/medidas';
import {
    FotoDelPunto, Pastillas, fechaLarga, macrosEnPalabras, numero, pieDeFoto, useUrlDeFoto,
} from './comun';

const Bloque = ({ titulo, testid, children }) => (
    <div className="bg-card border border-border rounded-2xl p-4 space-y-2" data-testid={testid}>
        <p className="caption">{titulo}</p>
        {children}
    </div>
);

const Falta = ({ children }) => <p className="text-sm text-muted-foreground">{children}</p>;

/** Una miniatura del punto: se baja con la sesión y al tocarla se ve entera. */
const Miniatura = ({ api, punto, foto }) => {
    const url = useUrlDeFoto(api, foto);
    return (
        <FotoDelPunto url={url} pie={pieDeFoto(punto, foto)} alt={`Tu foto del ${fechaLarga(punto.fecha)}`}
            testid={`foto-punto-${foto.id}`} />
    );
};

const DetalleDelPunto = ({ api, punto, alVolver, alComparar }) => {
    const medidas = MEDIDAS
        .map(({ key, label }) => ({ key, label, valor: valorAnterior(punto.medidas, key) }))
        .filter(m => m.valor != null);
    const macros = punto.macros || null;
    const entreno = macrosEnPalabras(macros?.entreno);
    const descanso = macrosEnPalabras(macros?.descanso);
    const peri = macrosEnPalabras(macros?.peri);
    const fotos = punto.fotos || [];

    return (
        <div className="space-y-4" data-testid="detalle-del-punto">
            <button type="button" onClick={alVolver} data-testid="volver-a-puntos"
                className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground">
                <ChevronLeft className="w-4 h-4" /> Tus puntos de control
            </button>

            <div>
                <p className="text-lg font-bold text-foreground leading-tight">{punto.nombre}</p>
                <p className="text-[15px] text-muted-foreground">
                    {fechaLarga(punto.fecha)}
                    {punto.aproximado && <span className="text-xs"> · aproximado</span>}
                </p>
                {punto.nombre_secundario && (
                    <p className="text-sm italic text-muted-foreground">{punto.nombre_secundario}</p>
                )}
            </div>

            {/* La tarjeta de arriba de la maqueta: PICO DE FORMA · Máxima definición · 80 kg. */}
            <div className="bg-card border border-border rounded-2xl p-4 space-y-2" data-testid="punto-resumen">
                <Pastillas etiquetas={punto.etiquetas} />
                <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm text-foreground">{punto.objetivo_nombre || 'Sin objetivo apuntado'}</span>
                    {punto.peso != null ? (
                        <span className="text-2xl font-bold text-foreground tabular-nums whitespace-nowrap">
                            {kg(punto.peso)} <span className="text-sm font-normal text-muted-foreground">kg</span>
                        </span>
                    ) : (
                        <span className="text-xs text-muted-foreground">sin peso apuntado</span>
                    )}
                </div>
            </div>

            <Bloque titulo="Tus fotos de ese día" testid="punto-fotos">
                {fotos.length ? (
                    <div className="grid grid-cols-3 gap-2">
                        {fotos.map(f => <Miniatura key={f.id} api={api} punto={punto} foto={f} />)}
                    </div>
                ) : (
                    <Falta>No subiste fotos en este reporte.</Falta>
                )}
            </Bloque>

            <Bloque titulo="Los macros que llevabas entonces" testid="punto-macros">
                {macros && (entreno || descanso || peri) ? (
                    <div className="text-sm text-muted-foreground space-y-0.5">
                        {entreno && <p><span className="text-foreground font-medium">Entreno:</span> {entreno}</p>}
                        {peri && <p><span className="text-foreground font-medium">Perientreno:</span> {peri}</p>}
                        {descanso && <p><span className="text-foreground font-medium">Descanso:</span> {descanso}</p>}
                        {macros.fecha && (
                            <p className="text-xs pt-1">Son los del ajuste del {fechaLarga(macros.fecha)}, el que tenías ese día.</p>
                        )}
                    </div>
                ) : (
                    <Falta>No tenemos apuntados los macros que llevabas entonces.</Falta>
                )}
            </Bloque>

            <Bloque titulo="Tus medidas" testid="punto-medidas">
                {medidas.length ? (
                    <div className="space-y-1">
                        {medidas.map(m => (
                            <div key={m.key} className="flex items-baseline justify-between gap-3 text-sm">
                                <span className="text-foreground/80">{m.label}</span>
                                <span className="font-bold text-foreground tabular-nums whitespace-nowrap">{numero(m.valor)} cm</span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <Falta>No las mediste en este reporte.</Falta>
                )}
            </Bloque>

            <Bloque titulo="Tu porcentaje de grasa" testid="punto-grasa">
                {punto.grasa != null ? (
                    <p className="text-2xl font-bold text-foreground tabular-nums">
                        {numero(punto.grasa)} <span className="text-sm font-normal text-muted-foreground">%</span>
                    </p>
                ) : (
                    <Falta>No lo mediste en este reporte.</Falta>
                )}
            </Bloque>

            <button type="button" onClick={alComparar} data-testid="comparar-este-punto"
                className="text-sm font-bold text-brand hover:underline">
                Comparar este punto con otro ›
            </button>
        </div>
    );
};

export default DetalleDelPunto;
