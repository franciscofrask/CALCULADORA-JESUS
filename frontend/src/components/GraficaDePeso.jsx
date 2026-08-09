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
 */
import React, { useMemo } from 'react';
import {
    CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

const NARANJA = '#FF671F';
// Del tema, no a pelo: es lo que hacía que en el lado del cliente no se leyeran.
const TENUE = 'hsl(var(--muted-foreground))';
const LINEA_TENUE = 'hsl(var(--border))';

const _fecha = (ts, conAnio) => new Date(ts).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'short', ...(conAnio ? { year: '2-digit' } : {}),
});

const Globo = ({ active, payload, conAnio }) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload;
    return (
        <div className="rounded-xl border border-border bg-card px-3 py-2 shadow-lg">
            <p className="text-xs text-muted-foreground">{_fecha(p.ts, true)}</p>
            <p className="text-lg font-bold text-foreground leading-tight">
                {p.peso} <span className="text-xs font-normal text-muted-foreground">kg</span>
            </p>
            {p.delta != null && p.delta !== 0 && (
                <p className={`text-xs font-bold ${p.delta < 0 ? 'text-emerald-500' : 'text-brand'}`}>
                    {p.delta > 0 ? '+' : ''}{p.delta} kg desde el anterior
                </p>
            )}
        </div>
    );
};

/**
 * `puntos`: [{fecha|date, peso|value}]. Se acepta cualquiera de los dos nombres porque las
 * dos pantallas los traían distintos, y unificarlos aquí es más barato que tocar las dos.
 */
const GraficaDePeso = ({ puntos, alto = 'h-56', conResumen = true }) => {
    const datos = useMemo(() => {
        const limpio = (puntos || [])
            .map(p => {
                const cuando = p.fecha ?? p.date ?? p.ts;
                const kg = Number(p.peso ?? p.value ?? p.weight);
                const ts = typeof cuando === 'number' ? cuando : new Date(cuando).getTime();
                return Number.isFinite(ts) && Number.isFinite(kg) && kg > 0 ? { ts, peso: kg } : null;
            })
            .filter(Boolean)
            .sort((a, b) => a.ts - b.ts);
        // Un peso por día: dos pesajes el mismo día es una corrección, manda el último.
        // Es la misma regla que las series del backend, y sin ella la curva hace picos que
        // no existieron.
        const porDia = new Map();
        limpio.forEach(p => porDia.set(new Date(p.ts).toISOString().slice(0, 10), p));
        const unicos = [...porDia.values()].sort((a, b) => a.ts - b.ts);
        return unicos.map((p, i) => ({
            ...p,
            delta: i > 0 ? Math.round((p.peso - unicos[i - 1].peso) * 10) / 10 : null,
        }));
    }, [puntos]);

    if (!datos.length) return null;

    const primero = datos[0].peso;
    const ultimo = datos[datos.length - 1].peso;
    const cambio = Math.round((ultimo - primero) * 10) / 10;
    // Más de un año de recorrido: las etiquetas necesitan el año o se repiten.
    const conAnio = (datos[datos.length - 1].ts - datos[0].ts) > 330 * 24 * 3600 * 1000;

    return (
        <div data-testid="grafica-de-peso">
            {conResumen && (
                <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 mb-3 text-sm">
                    <div>
                        <span className="text-muted-foreground text-xs mr-1">Empezaste en</span>
                        <span className="text-foreground font-bold">{primero} kg</span>
                    </div>
                    <div>
                        <span className="text-muted-foreground text-xs mr-1">Ahora</span>
                        <span className="text-foreground font-bold">{ultimo} kg</span>
                    </div>
                    <div>
                        <span className="text-muted-foreground text-xs mr-1">Cambio</span>
                        <span className={`font-bold ${cambio < 0 ? 'text-emerald-500' : cambio > 0 ? 'text-brand' : 'text-foreground'}`}>
                            {cambio > 0 ? '+' : ''}{cambio} kg
                        </span>
                    </div>
                    <span className="text-muted-foreground text-xs">
                        {datos.length} {datos.length === 1 ? 'pesaje' : 'pesajes'}
                    </span>
                </div>
            )}
            <div className={alto}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
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
                        <Tooltip content={<Globo conAnio={conAnio} />} cursor={{ stroke: LINEA_TENUE }} />
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
        </div>
    );
};

export default GraficaDePeso;
