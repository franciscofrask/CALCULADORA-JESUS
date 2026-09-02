/**
 * EL CAMPO DEL PESO («Todo lo validado antes del 1 de septiembre», bloque 4: «El peso. Un
 * solo registro, tres puertas»).
 *
 *     «Abierto todo el año. Es el único sitio donde el peso se escribe.»
 *
 * Antes se escribía DENTRO del cierre del día, al final de once preguntas. Con eso el que
 * no cerraba el día no tenía dónde apuntarlo -- y son la mayoría --, y el que lo apuntaba
 * dejaba el dato enterrado en un formulario que no vuelve a abrir. Ahora vive aquí, en
 * Evolución, que es de donde sale la curva, y las otras dos puertas del bloque 4 traen
 * hasta aquí: la fila «Hoy toca pesarte» de Inicio los días de pesada y el paso 1 del
 * reporte quincenal.
 *
 * LA FECHA DEL PESAJE SIGUE VIVA (punto 34 del doc 24-08). No sale en la maqueta porque la
 * maqueta enseña el campo en reposo, vacío, y en reposo tampoco salía en el cierre: aparece
 * al escribir un peso, y solo si hay más de un día al que fecharlo. Sin ella, el que se
 * pesa por la mañana y lo anota de noche rompe la pareja de días seguidos de la que sale la
 * media semanal.
 */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { revisarPeso, PESO_MIN, PESO_MAX, kg } from '../lib/pesoValido';
import { useConfirm } from './ui/confirm';
import { mensajeDeError } from '../lib/mensajeDeError';

// El día de HOY es el del navegador, no el del servidor: el día vivido es el suyo.
const hoyDelCliente = () => new Date().toLocaleDateString('en-CA');

// Los días a los que puede fechar un pesaje: hoy y los `diasAtras` anteriores. El número lo
// dice el servidor (`peso_dias_atras`), que es el que luego lo acepta o no.
export const diasParaFechar = (hoyIso, diasAtras = 14) => {
    const dias = [];
    for (let i = 0; i <= diasAtras; i++) {
        const d = new Date(`${hoyIso}T12:00:00`);
        d.setDate(d.getDate() - i);
        const etiqueta = i === 0 ? 'Hoy' : i === 1 ? 'Ayer'
            : d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
        dias.push({
            iso: d.toLocaleDateString('en-CA'),
            etiqueta: etiqueta.charAt(0).toUpperCase() + etiqueta.slice(1),
        });
    }
    return dias;
};

const cuando = (iso) => {
    if (!iso) return '';
    const d = new Date(`${String(iso).slice(0, 10)}T12:00:00`);
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
};

/**
 * @param ultimo   {valor, fecha} del último pesaje conocido, para la línea de abajo y para
 *                 medir el salto que canta.
 * @param abrir    llega con el foco puesto: es el que viene de «Hoy toca pesarte», que
 *                 espera escribir sin buscar nada.
 */
const CampoDePeso = ({ api, ultimo = null, diasAtras = 14, abrir = false, onGuardado }) => {
    const [valor, setValor] = useState('');
    const [fecha, setFecha] = useState(hoyDelCliente);
    const [guardando, setGuardando] = useState(false);
    const { confirm } = useConfirm();
    const campo = React.useRef(null);

    useEffect(() => { if (abrir) campo.current?.focus(); }, [abrir]);

    const dias = diasParaFechar(hoyDelCliente(), diasAtras);

    const guardar = async () => {
        const chequeo = revisarPeso(valor, ultimo?.valor);
        if (!chequeo.ok) return toast.error(chequeo.error);
        if (chequeo.confirmar) {
            const sigue = await confirm({
                title: 'Confírmame el peso',
                description: chequeo.confirmar,
                confirmLabel: 'Sí, es correcto', cancelLabel: 'Lo corrijo',
            });
            if (!sigue) return;
        }
        setGuardando(true);
        try {
            await api.post('/clients/me/peso', { valor: chequeo.peso, fecha });
            toast.success('Peso guardado');
            setValor('');
            setFecha(hoyDelCliente());
            onGuardado?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo guardar el peso'));
        } finally {
            setGuardando(false);
        }
    };

    return (
        <div data-testid="campo-de-peso">
            <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                    Tu peso
                </p>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#22C55E]">
                    Siempre abierto
                </span>
            </div>
            <div className="flex gap-2">
                <div className="flex-1 bg-muted rounded-xl px-3 py-2.5 flex items-center justify-between">
                    <input ref={campo} type="number" step="0.1" min={PESO_MIN} max={PESO_MAX}
                        value={valor} onChange={e => setValor(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') guardar(); }}
                        data-testid="peso-valor" placeholder="0,0" aria-label="Tu peso en kilos"
                        className="w-full bg-transparent border-0 p-0 text-sm text-foreground
                            placeholder:text-muted-foreground focus:outline-none" />
                    <span className="text-xs text-muted-foreground font-data pl-2">kg</span>
                </div>
                <button onClick={guardar} disabled={guardando || !valor}
                    data-testid="guardar-peso"
                    className="btn-brand px-5 rounded-xl text-sm font-bold disabled:opacity-60">
                    {guardando ? 'Guardando…' : 'Guardar'}
                </button>
            </div>

            {valor && dias.length > 1 && (
                <div className="mt-2">
                    <label className="text-[11px] text-muted-foreground block mb-1" htmlFor="peso-fecha">
                        ¿De qué día es este peso?
                    </label>
                    <select id="peso-fecha" value={fecha} onChange={e => setFecha(e.target.value)}
                        data-testid="peso-fecha"
                        className="w-full bg-muted border border-border rounded-xl px-3 py-2 text-sm text-foreground">
                        {dias.map(d => <option key={d.iso} value={d.iso}>{d.etiqueta}</option>)}
                    </select>
                </div>
            )}

            <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes.
            </p>
            {ultimo?.valor != null && (
                <p className="text-[11px] text-muted-foreground mt-1" data-testid="peso-ultimo">
                    Último registro: {kg(ultimo.valor)} kg · {cuando(ultimo.fecha)}
                </p>
            )}
        </div>
    );
};

export default CampoDePeso;
