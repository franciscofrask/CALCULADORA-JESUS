/**
 * La evolución del peso, una sola gráfica para el cliente y para el entrenador.
 * Punto 4.13 de la revisión del 09-08.
 *
 * Lo que reportó Jesús: «puntos naranjas sobre una cuadrícula. Sin ejes, sin fechas, sin
 * valores, sin línea de unión, sin tooltip».
 *
 * La causa de lo de los ejes es tonta y por eso costaba verla: estaban pintados con
 * `fill: '#ffffff66'` a pelo. En el panel del entrenador el fondo es negro y se leen; en el
 * lado del cliente la tarjeta es BLANCA en tema claro, así que era **texto blanco sobre
 * blanco**. La cuadrícula (`#222`, gris oscuro) y los puntos naranjas sí se veían. De ahí la
 * descripción exacta: la gráfica estaba entera, solo que la mitad era invisible.
 *
 * Aquí los colores salen de las variables del tema, así que se leen en los dos fondos y
 * siguen leyéndose si alguien cambia la paleta.
 *
 * Lo demás que faltaba:
 *
 *   - LA LÍNEA SE CORTABA. Un hueco sin peso partía la línea en trozos y con datos salteados
 *     no quedaba más que la nube de puntos. `connectNulls` la mantiene entera.
 *   - LAS FECHAS SE PISABAN. La etiqueta era «9 ago» sin año, y con dietas desde 2022 hay
 *     cuatro «9 ago» distintos que el eje trata como la misma categoría. Ahora el eje es
 *     numérico por tiempo y las etiquetas llevan año cuando el rango pasa de un año.
 *   - NO SE VEÍA LO QUE IMPORTA. Debajo del título van el peso de partida, el de ahora y el
 *     cambio, que es lo que se mira antes que la curva.
 *
 * EL PESO EN DOS BLOQUES, Y FUERA LA GRÁFICA LARGA (doc de Jesús del 2-09, «Los dos bloques
 * del peso»). Hasta aquí la curva llevaba TODOS los pesajes de la historia, y «18 pesajes de
 * tres años y medio en el ancho de un móvil son una línea que no se lee». Ahora:
 *
 *   - ARRIBA, ESTE CICLO: la curva solo con los pesajes desde `cycle_start`, y tres líneas
 *     (dónde empezó el ciclo, ahora, y los kilos de estas N semanas). Contesta «¿cómo voy?».
 *   - DEBAJO, DESDE QUE ENTRÓ: sin gráfica, en tres líneas. Lo que pesaba al entrar, lo que
 *     pesa hoy y desde cuándo está. «La historia entera sigue estando, pero deja de ser el
 *     primer número que ve.» Solo se pinta si hay pesajes anteriores al ciclo: si toda su
 *     historia cabe en el ciclo no hay nada que contar dos veces.
 */
import React, { useMemo } from 'react';
import {
    CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { kg } from '../lib/pesoValido';

const NARANJA = '#FF671F';
// Del tema, no a pelo: es lo que hacía que en el lado del cliente no se leyeran.
const TENUE = 'hsl(var(--muted-foreground))';
const LINEA_TENUE = 'hsl(var(--border))';

// EL CAMBIO SE LEE CONTRA SU OBJETIVO (doc 23-08, bloque 10). «Cambio +7 kg» en naranja
// de alarma cuando el cliente está en volumen es contarle su progreso al revés: para él
// +7 es la buena noticia. El color solo dice algo si sabe hacia dónde va el cliente:
// verde si el cambio va hacia su objetivo, rojo si va en contra, y neutro si mantiene
// (o si su objetivo no marca dirección, como recomposición).
const OBJETIVO_TEXTO = {
    volumen: 'ganar masa', definicion: 'perder grasa',
    perdida_grasa: 'perder grasa', 'perdida-grasa': 'perder grasa',
    recomposicion: 'recomposición', mantenimiento: 'mantener tu peso',
};
// +1 = el peso debe subir; -1 = debe bajar; 0 = sin dirección (mantener, recomposición
// o sin objetivo en el perfil).
const _direccion = (objetivo) => {
    const o = String(objetivo || '').toLowerCase();
    if (o === 'volumen') return 1;
    if (o === 'definicion' || o.startsWith('perdida')) return -1;
    return 0;
};
const _colorDelCambio = (delta, objetivo) => {
    const dir = _direccion(objetivo);
    if (!delta || !dir) return 'text-foreground';
    return delta * dir > 0 ? 'text-emerald-500' : 'text-red-500';
};

const _fecha = (ts, conAnio) => new Date(ts).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'short', ...(conAnio ? { year: '2-digit' } : {}),
});
// «enero de 2023»: desde cuándo está con nosotros. A esa distancia el día no dice nada.
const _mesYAnio = (ts) => new Date(ts).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
// «+7 kg», «−5,6 kg», «0 kg»: el signo delante y la coma decimal, la misma que escribe el
// campo del peso que va encima en la tarjeta (`kg` de lib/pesoValido).
const _conSigno = (delta) => `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${kg(Math.abs(delta))} kg`;

const Globo = ({ active, payload, objetivo }) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload;
    return (
        <div className="rounded-xl border border-border bg-card px-3 py-2 shadow-lg">
            <p className="text-xs text-muted-foreground">{_fecha(p.ts, true)}</p>
            <p className="text-lg font-bold text-foreground leading-tight">
                {kg(p.peso)} <span className="text-xs font-normal text-muted-foreground">kg</span>
            </p>
            {p.delta != null && p.delta !== 0 && (
                // El mismo criterio que el resumen: bajar solo es verde si su objetivo
                // es bajar. Antes bajar era siempre verde y subir siempre naranja.
                <p className={`text-xs font-bold ${_colorDelCambio(p.delta, objetivo)}`}>
                    {_conSigno(p.delta)} desde el anterior
                </p>
            )}
        </div>
    );
};

// La curva de una serie: la de este ciclo, o la entera si no hay ciclo. El eje es de
// TIEMPO y no de categorías, y las etiquetas llevan año solo si el recorrido pasa del año.
const Curva = ({ serie, alto, objetivo }) => {
    const primero = serie[0].peso;
    const conAnio = (serie[serie.length - 1].ts - serie[0].ts) > 330 * 24 * 3600 * 1000;
    return (
        <div className={alto}>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={serie} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={LINEA_TENUE} />
                    {/* Eje de TIEMPO, no de categorías: con dietas desde 2022 había cuatro
                        «9 ago» distintos y el eje los juntaba en uno. */}
                    <XAxis
                        dataKey="ts" type="number" scale="time"
                        domain={['dataMin', 'dataMax']}
                        tickFormatter={(t) => _fecha(t, conAnio)}
                        tick={{ fill: TENUE, fontSize: 11 }}
                        axisLine={false} tickLine={false} minTickGap={32}
                    />
                    <YAxis
                        domain={['auto', 'auto']} width={44} unit=" kg"
                        tick={{ fill: TENUE, fontSize: 11 }}
                        axisLine={false} tickLine={false}
                    />
                    <Tooltip content={<Globo objetivo={objetivo} />} cursor={{ stroke: LINEA_TENUE }} />
                    {/* De dónde salió: la referencia contra la que se lee todo lo demás. */}
                    <ReferenceLine y={primero} stroke={TENUE} strokeDasharray="4 4" />
                    <Line
                        type="monotone" dataKey="peso" stroke={NARANJA} strokeWidth={2}
                        connectNulls
                        dot={{ fill: NARANJA, r: 2.5 }}
                        activeDot={{ r: 5, fill: NARANJA, stroke: 'hsl(var(--card))', strokeWidth: 2 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};

// El rótulo de cada bloque: pequeño en mayúsculas a la izquierda y, a la derecha, el
// cambio con signo. Es lo que Jesús dibujó en la maqueta del 2-09.
const Rotulo = ({ children, derecha = null, derechaClase = 'text-foreground', testid }) => (
    <div className="flex items-baseline justify-between gap-3">
        <p className="caption">{children}</p>
        {derecha != null && (
            <span data-testid={testid} className={`text-sm font-bold tabular-nums ${derechaClase}`}>
                {derecha}
            </span>
        )}
    </div>
);

// Una línea del resumen: la etiqueta a la izquierda y el valor en negrita a la derecha.
// El valor no se parte nunca («junio de 2026» salía en dos líneas en un móvil de 390);
// si falta sitio, la que envuelve es la etiqueta.
const Fila = ({ etiqueta, children }) => (
    <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-muted-foreground">{etiqueta}</span>
        <span className="font-bold text-foreground tabular-nums text-right whitespace-nowrap shrink-0">{children}</span>
    </div>
);

/**
 * `puntos`: [{fecha|date, peso|value}]. Se acepta cualquiera de los dos nombres porque las
 * dos pantallas los traían distintos, y unificarlos aquí es más barato que tocar las dos.
 * `desdeElCiclo`: el `cycle_start` del perfil. `semanasDelCiclo`: su `cycle_total_weeks`,
 * para decir «En estas 12 semanas»; sin él se dice «En este ciclo».
 */
const GraficaDePeso = ({ puntos, alto = 'h-56', conResumen = true, objetivo = null,
                         desdeElCiclo = null, semanasDelCiclo = null }) => {
    const datos = useMemo(() => {
        const limpio = (puntos || [])
            .map(p => {
                const cuando = p.fecha ?? p.date ?? p.ts;
                const kilos = Number(p.peso ?? p.value ?? p.weight);
                const ts = typeof cuando === 'number' ? cuando : new Date(cuando).getTime();
                return Number.isFinite(ts) && Number.isFinite(kilos) && kilos > 0 ? { ts, peso: kilos } : null;
            })
            .filter(Boolean)
            .sort((a, b) => a.ts - b.ts);
        // Un peso por día: dos pesajes el mismo día es una corrección, manda el último.
        // Es la misma regla que las series del backend, y sin ella la curva hace picos que
        // no existieron.
        const porDia = new Map();
        limpio.forEach(p => porDia.set(new Date(p.ts).toLocaleDateString('en-CA'), p)); // dia local, no UTC (bloque F)
        const unicos = [...porDia.values()].sort((a, b) => a.ts - b.ts);
        return unicos.map((p, i) => ({
            ...p,
            delta: i > 0 ? Math.round((p.peso - unicos[i - 1].peso) * 10) / 10 : null,
        }));
    }, [puntos]);

    if (!datos.length) return null;

    // ESTE CICLO ARRIBA; SU HISTORIA ENTERA, DEBAJO Y SIN CURVA (doc de Jesús del 2-09).
    //
    // «Empezaste en 89 · ahora 96 · cambio +7 kg» se calculaba con el primer pesaje de
    // TODA su historia: a un cliente migrado de Calma le juntaba enero de 2023 con hoy,
    // tres años y tres ciclos en un solo número, y encima debajo de «tu objetivo: perder
    // grasa». Lo que le interesa es cómo va en el ciclo que está haciendo, y la curva larga
    // ni siquiera se lee en un móvil.
    //
    // Sin fecha de ciclo se sigue leyendo la historia entera como hasta ahora, con el
    // rótulo «Tu curva»: es mejor que quedarse sin resumen.
    const arranqueCiclo = desdeElCiclo ? new Date(desdeElCiclo).getTime() : null;
    const hayCiclo = arranqueCiclo != null && Number.isFinite(arranqueCiclo);
    const serie = hayCiclo ? datos.filter(p => p.ts >= arranqueCiclo) : datos;
    // Pesajes de ANTES del ciclo: son los que justifican el segundo bloque.
    const anterioresAlCiclo = datos.length - serie.length;

    if (!conResumen) {
        return serie.length >= 2
            ? <div data-testid="grafica-de-peso"><Curva serie={serie} alto={alto} objetivo={objetivo} /></div>
            : null;
    }

    const ultimoDeTodos = datos[datos.length - 1].peso;
    const cambioTotal = Math.round((ultimoDeTodos - datos[0].peso) * 10) / 10;
    // El objetivo del perfil, contado en cristiano. Sin objetivo conocido no se inventa.
    const objetivoTexto = OBJETIVO_TEXTO[String(objetivo || '').toLowerCase()] || null;

    // Las tres líneas del primer bloque, o el texto de «te falta uno» si no hay curva.
    const conCurva = serie.length >= 2;
    const cambio = conCurva ? Math.round((serie[serie.length - 1].peso - serie[0].peso) * 10) / 10 : null;
    const colorCambio = cambio === 0 ? 'text-foreground' : _colorDelCambio(cambio, objetivo);
    const rotuloCiclo = hayCiclo ? 'Este ciclo' : 'Tu curva';
    // «En estas 12 semanas» es la duración del ciclo del perfil (`cycle_total_weeks`); los
    // planes mensuales sin tope no la tienen, y ahí se dice «En este ciclo».
    const etiquetaCambio = !hayCiclo ? 'Desde entonces'
        : semanasDelCiclo ? `En estas ${semanasDelCiclo} semanas` : 'En este ciclo';

    return (
        <div data-testid="grafica-de-peso" className="space-y-4">
            {/* Encima de todo, hacia dónde va: sin esto un +7 no se puede leer, porque no
                es lo mismo en volumen que en definición (doc 23-08, bloque 10). */}
            {objetivoTexto && (
                <p className="text-sm" data-testid="objetivo-del-peso">
                    <span className="text-muted-foreground text-xs mr-1">Tu objetivo:</span>
                    <span className="text-foreground font-bold">{objetivoTexto}</span>
                </p>
            )}

            {/* BLOQUE 1: este ciclo (o su curva entera, si no hay fecha de ciclo). */}
            <div className="space-y-2">
                <Rotulo derecha={conCurva ? _conSigno(cambio) : null} derechaClase={colorCambio}
                        testid="cambio-de-peso">
                    {rotuloCiclo}
                    {conCurva && (
                        <span className="normal-case tracking-normal font-normal">
                            {' '}· {serie.length} pesajes
                        </span>
                    )}
                </Rotulo>
                {conCurva ? (
                    <>
                        <Curva serie={serie} alto={alto} objetivo={objetivo} />
                        <div className="space-y-1.5 pt-1">
                            <Fila etiqueta={hayCiclo ? 'Empezaste el ciclo en' : 'Empezaste en'}>
                                {kg(serie[0].peso)} kg
                            </Fila>
                            <Fila etiqueta="Ahora">{kg(serie[serie.length - 1].peso)} kg</Fila>
                            <Fila etiqueta={etiquetaCambio}>
                                <span className={colorCambio}>{_conSigno(cambio)}</span>
                            </Fila>
                        </div>
                    </>
                ) : (
                    // CON UN SOLO PESAJE NO SE DIBUJA UNA CURVA.
                    // Salía una gráfica con un punto y «empezaste en 75,5 · ahora 75,5 · cambio
                    // 0 kg · 1 pesaje»: una línea recta que no dice nada y que parece un error.
                    // Es la pantalla del premio, la que enseña que el trabajo sirve, y con un
                    // punto enseña lo contrario. Se dice lo que falta para tenerla, que además
                    // es una petición concreta (Jesús, 11-08). Con ciclo pasa lo mismo dentro
                    // del ciclo: su historia de antes está en el bloque de abajo.
                    <div className="surface p-4">
                        {serie.length === 1 ? (
                            <p className="text-sm text-foreground">
                                {anterioresAlCiclo > 0 ? 'Tu primer peso del ciclo' : 'Tu primer peso'}:{' '}
                                <span className="font-bold">{kg(serie[0].peso)} kg</span>
                            </p>
                        ) : (
                            <p className="text-sm text-foreground">Todavía no te has pesado en este ciclo.</p>
                        )}
                        <p className="text-sm text-muted-foreground mt-1">
                            Con dos pesajes te dibujamos tu evolución.{serie.length === 1 ? ' Te falta uno.' : ''}
                        </p>
                    </div>
                )}
            </div>

            {/* BLOQUE 2: desde que entró, en texto y sin gráfica. Solo si hay pesajes de
                antes del ciclo. Sin color en el cambio: es contexto, no es cómo va este
                ciclo, y el verde o el rojo se reservan para lo que se está juzgando.
                Jesús pide también «3 ciclos desde enero de 2023», pero el número de ciclos
                NO existe todavía en los datos: la app no guarda los ciclos anteriores, solo
                el que está en marcha. De momento, solo la fecha. */}
            {hayCiclo && anterioresAlCiclo > 0 && (
                <div className="pt-3 border-t border-border space-y-1.5" data-testid="peso-historia-entera">
                    <Rotulo derecha={_conSigno(cambioTotal)}>Desde que entraste</Rotulo>
                    <Fila etiqueta="Cuando entraste pesabas">{kg(datos[0].peso)} kg</Fila>
                    <Fila etiqueta="Ahora">{kg(ultimoDeTodos)} kg</Fila>
                    <Fila etiqueta="Llevas con nosotros desde">{_mesYAnio(datos[0].ts)}</Fila>
                    {/* AQUÍ VA «Comparar con cualquier punto ›» cuando exista el comparador
                        de pesajes (doc del 2-09: «¿cómo estaba yo en el ciclo 1? ya se
                        contesta en el comparador»). Es de una fase posterior; hasta entonces
                        no se pinta un enlace que no lleva a ningún sitio. */}
                </div>
            )}
        </div>
    );
};

export default GraficaDePeso;
