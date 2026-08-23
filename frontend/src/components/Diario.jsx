/**
 * EL DIARIO (T5 del doc 16-08).
 *
 * "Solo lectura. Cae todo lo que escribe: las notas del día y lo del entreno."
 *
 * Dos tipos de entrada y nada más: las del entreno (con estrellas y peso) y las del día.
 * Cada una con su marca, que es lo que decide quién la lee: "🔒 Solo para ti" o
 * "Compartida". La marca no es decoración, es la promesa que se le hizo al escribirla; el
 * filtro de verdad está en el servidor (`routes/diary.py`), que al equipo solo le manda las
 * compartidas.
 *
 * Vive DENTRO de Seguimiento: no es una pestaña nueva del menú (el doc lo dice dos veces).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { BookOpen } from 'lucide-react';

// «Jueves, 20 de agosto», la fecha tal y como la escribe el doc.
const fechaLarga = (iso) => {
    if (!iso) return '';
    const d = new Date(`${iso}T12:00:00`);
    if (isNaN(d)) return iso;
    const texto = d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
    return texto.charAt(0).toUpperCase() + texto.slice(1);
};

// «★★★★☆»: las cinco siempre, para que se lea de un vistazo cuántas se puso.
const estrellas = (n) => '★'.repeat(n) + '☆'.repeat(Math.max(0, 5 - n));

const POR_PAGINA = 20;

const Entrada = ({ entrada }) => {
    const marca = entrada.compartida ? 'Compartida' : '🔒 Solo para ti';
    return (
        <li className="bg-card border border-border rounded-2xl p-4" data-testid={`diario-${entrada.tipo}`}>
            {/* La fecha, tal y como la escribe el doc: «Jueves, 20 de agosto · entreno».
                Sin mayúsculas: ahí se lee una fecha, no una etiqueta de sección.
                La entrada del día lleva su apellido igual que la del entreno (P78, doc
                23-08): «cierre del día», el mismo nombre que en el historial de check-ins,
                que decía «DIARIO» y se confundía con esta pestaña. */}
            <p className="text-sm font-bold text-foreground">
                {fechaLarga(entrada.fecha)}{entrada.tipo === 'entreno' ? ' · entreno' : ' · cierre del día'}
            </p>
            {entrada.texto && (
                <p className="text-[15px] text-foreground/80 mt-1.5 whitespace-pre-line">{entrada.texto}</p>
            )}
            {/* La nota de entreno del cierre (P80): quien no tiene rutina apunta ahí su
                entreno, y esto también es «lo del entreno» que cae al diario. */}
            {entrada.entreno_nota && (
                <p className="text-[15px] text-foreground/80 mt-1.5 whitespace-pre-line">
                    <span className="text-xs uppercase tracking-wider font-bold text-muted-foreground mr-2">Entreno</span>
                    {entrada.entreno_nota}
                </p>
            )}
            {/* El peso destacado va en su renglón: la línea de debajo es la del doc y dice
                las estrellas y la marca, ni una cosa más. */}
            {entrada.peso_destacado && (
                <p className="text-[13px] text-muted-foreground mt-1">{entrada.peso_destacado}</p>
            )}
            {/* La marca habla de la nota personal: una entrada que solo trae la nota de
                entreno no la lleva, porque esa nota es la respuesta a una pregunta nuestra. */}
            {(entrada.texto || entrada.estrellas) && (
                <p className="text-xs text-muted-foreground mt-2">
                    {entrada.estrellas ? `${estrellas(entrada.estrellas)} · ` : ''}{marca}
                </p>
            )}
        </li>
    );
};

const Diario = ({ api }) => {
    const [entradas, setEntradas] = useState([]);
    const [hayMas, setHayMas] = useState(false);
    const [cargando, setCargando] = useState(true);
    const [cargandoMas, setCargandoMas] = useState(false);
    const [error, setError] = useState(false);

    const cargar = useCallback(async () => {
        try {
            const { data } = await api.get('/diary', { params: { skip: 0, limit: POR_PAGINA } });
            setEntradas(data?.entradas || []);
            setHayMas(!!data?.hay_mas);
        } catch (e) {
            // Al cliente, una frase; el detalle a la consola (regla de la casa).
            console.error('No se pudo cargar el diario:', e?.response?.data || e);
            setError(true);
        } finally {
            setCargando(false);
        }
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    const cargarMas = async () => {
        setCargandoMas(true);
        try {
            const { data } = await api.get('/diary', { params: { skip: entradas.length, limit: POR_PAGINA } });
            setEntradas(prev => [...prev, ...(data?.entradas || [])]);
            setHayMas(!!data?.hay_mas);
        } catch (e) {
            console.error('No se pudieron cargar más apuntes del diario:', e?.response?.data || e);
        } finally {
            setCargandoMas(false);
        }
    };

    return (
        <div className="space-y-3" data-testid="diario">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center">
                    <BookOpen className="w-5 h-5 text-brand" />
                </div>
                <div>
                    <p className="text-lg font-bold text-foreground">Tu diario</p>
                    <p className="text-[15px] text-muted-foreground">Todo lo que has ido apuntando</p>
                </div>
            </div>

            {cargando ? (
                <div className="animate-pulse space-y-3">
                    <div className="h-24 bg-card rounded-2xl" />
                    <div className="h-24 bg-card rounded-2xl" />
                </div>
            ) : error ? (
                <div className="bg-card border border-border rounded-2xl p-8 text-center">
                    <p className="text-sm text-muted-foreground">Ahora mismo no podemos enseñarte tu diario. Inténtalo en un rato.</p>
                </div>
            ) : entradas.length === 0 ? (
                <div className="bg-card border border-border rounded-2xl p-8 text-center">
                    <p className="text-sm text-muted-foreground">
                        Aquí caerá lo que vayas apuntando en el cierre del día y en tus entrenos.
                    </p>
                </div>
            ) : (
                <>
                    <ul className="space-y-3">
                        {entradas.map((e, i) => <Entrada key={`${e.tipo}-${e.fecha}-${i}`} entrada={e} />)}
                    </ul>
                    {hayMas && (
                        <button onClick={cargarMas} disabled={cargandoMas} data-testid="diario-cargar-mas"
                            className="w-full py-3 rounded-2xl border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50">
                            {cargandoMas ? 'Cargando...' : 'Ver apuntes anteriores'}
                        </button>
                    )}
                </>
            )}
        </div>
    );
};

export default Diario;
