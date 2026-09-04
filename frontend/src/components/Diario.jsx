/**
 * EL DIARIO (T5 del doc 16-08), POR MESES DESDE EL DOC DE JESÚS DEL 2-09.
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
 *
 * YA NO ES UNA LISTA SUELTA (doc de Jesús del 2-09): «Con Este mes · Este ciclo · Todo
 * arriba y el mes por encima (agosto · 11 notas de 28 días) pasa a ser lo único de la app
 * que es suyo. Los días sin cerrar salen en gris, sin riña». Tres vistas, las notas
 * agrupadas por mes con su rótulo y, en «Este mes» y «Este ciclo», una fila gris por cada
 * día que pasó sin apuntar nada. En «Todo» no se pintan los huecos: tres años de días
 * vacíos no se leen.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { hoyLocal, aFecha, diaEnEspana } from '../lib/horaEspana';

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

// «Todo» sigue yendo de 20 en 20 con «Ver apuntes anteriores», como siempre.
const POR_PAGINA = 20;
// «Este mes» y «Este ciclo» enseñan el rango ENTERO, y el servidor solo pagina (skip y
// limit, sin filtro de fechas: `GET /diary` en routes/diary.py). Filtrar por mes lo que
// llega de 20 en 20 mentiría: un mes con cierre y entreno a diario son hasta 60 apuntes.
// Así que para esas dos vistas se piden páginas del tope del servidor (LIMITE_MAXIMO) hasta
// que el apunte más viejo cargado queda por detrás del arranque del rango: ahí ya está
// todo lo del rango, venga de la página que venga.
const LOTE_DEL_RANGO = 100;

const VISTAS = [
    { id: 'mes', texto: 'Este mes' },
    { id: 'ciclo', texto: 'Este ciclo' },
    { id: 'todo', texto: 'Todo' },
];

// Aritmética de días sobre 'YYYY-MM-DD', en UTC a propósito: aquí no hay instantes, hay
// días de calendario, y así no se cuela el huso del navegador ni el cambio de hora.
const partesDelDia = (dia) => String(dia).slice(0, 10).split('-').map(Number);
const diaDe = (y, m, d) => new Date(Date.UTC(y, m - 1, d)).toISOString().slice(0, 10);
const diaAnterior = (dia) => { const [y, m, d] = partesDelDia(dia); return diaDe(y, m, d - 1); };
const diasDelMes = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();
const primerDiaDelMes = (dia) => `${String(dia).slice(0, 7)}-01`;
const claveMes = (dia) => String(dia || '').slice(0, 7);
const esDia = (dia) => /^\d{4}-\d{2}-\d{2}$/.test(String(dia || ''));

// «agosto», y «agosto 2025» si no es de este año: en «Todo» se cruzan años, y dos agostos
// seguidos sin año no se distinguen. Sin abreviar; las mayúsculas las pone el CSS.
const nombreDelMes = (clave, hoy) => {
    const [y, m] = clave.split('-').map(Number);
    const nombre = new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('es-ES', { month: 'long', timeZone: 'UTC' });
    return y === Number(hoy.slice(0, 4)) ? nombre : `${nombre} ${y}`;
};

/**
 * LAS NOTAS, POR MESES, y en las vistas con rango los días sin nada entre medias.
 *
 * Devuelve los meses del más nuevo al más viejo, cada uno con sus filas ya en orden: una
 * por apunte (el servidor las manda de la más nueva a la más vieja) y, con rango, una gris
 * por cada día sin apunte. Cada mes lleva su cuenta, «11 notas de 28 días»: las notas son
 * los DÍAS en los que escribió algo (un día con entreno y cierre es un día apuntado, no
 * dos), y los días son los del mes que caen dentro del rango: hasta hoy en el mes en curso,
 * el mes entero en los pasados y, en el primer mes del ciclo, desde el día que arrancó. Es
 * la lectura de Jesús (doc del 2-09): de un vistazo, cuántos días apuntó de los que tuvo.
 *
 * Hoy solo cuenta como fila si tiene algo: el día no ha terminado, y un «no apuntaste
 * nada» de un día a medias sería justo la riña que el doc no quiere. En el número de días
 * sí entra, que es el día que va.
 */
const agruparPorMes = ({ entradas, desde, hoy, hayMas }) => {
    const porDia = new Map();
    for (const e of entradas) {
        // Sin fecha legible no hay dónde colocarla. El servidor siempre la manda (el `dia`
        // del cierre o la `fecha` del entreno), así que esto es un candado, no un caso.
        if (!esDia(e.fecha)) continue;
        if (desde && e.fecha < desde) continue;
        if (!porDia.has(e.fecha)) porDia.set(e.fecha, []);
        porDia.get(e.fecha).push(e);
    }
    const meses = new Map();
    const mesDe = (dia) => {
        const clave = claveMes(dia);
        if (!meses.has(clave)) meses.set(clave, { clave, notas: 0, dias: 0, filas: [] });
        return meses.get(clave);
    };
    const filasDe = (mes, apuntes) => apuntes.forEach((e, i) => (
        mes.filas.push({ tipo: 'entrada', entrada: e, key: `${e.tipo}-${e.fecha}-${i}` })
    ));

    if (desde) {
        // Día a día desde hoy hasta el arranque del rango. Se arranca en el apunte más
        // nuevo si va por delante de hoy (el día del servidor y el del reloj del cliente
        // no siempre coinciden): un apunte de hoy no se puede quedar fuera de «Este mes».
        let dia = [...porDia.keys()].reduce((max, f) => (f > max ? f : max), hoy);
        for (; dia >= desde; dia = diaAnterior(dia)) {
            const mes = mesDe(dia);
            mes.dias += 1;
            const apuntes = porDia.get(dia);
            if (apuntes) {
                mes.notas += 1;
                filasDe(mes, apuntes);
            } else if (dia < hoy) {
                mes.filas.push({ tipo: 'vacio', fecha: dia, key: `vacio-${dia}` });
            }
        }
    } else {
        for (const [dia, apuntes] of porDia) {
            const mes = mesDe(dia);
            mes.notas += 1;
            filasDe(mes, apuntes);
        }
        for (const mes of meses.values()) {
            const [y, m] = mes.clave.split('-').map(Number);
            mes.dias = mes.clave === claveMes(hoy) ? Number(hoy.slice(8, 10)) : diasDelMes(y, m);
        }
    }
    const lista = [...meses.values()].sort((a, b) => b.clave.localeCompare(a.clave));
    // En «Todo» la página de 20 corta donde corta: del mes más viejo cargado no se sabe
    // aún cuántas notas tiene, y una cuenta a medias sería mentir. Va sin cuenta hasta que
    // se traen las anteriores.
    if (!desde && hayMas && lista.length) lista[lista.length - 1].incompleto = true;
    return lista;
};

// «AGOSTO · 11 NOTAS DE 22 DÍAS», el rótulo de la maqueta.
const tituloDelMes = (mes, hoy) => {
    const nombre = nombreDelMes(mes.clave, hoy);
    if (mes.incompleto) return nombre;
    return `${nombre} · ${mes.notas} ${mes.notas === 1 ? 'nota' : 'notas'} de ${mes.dias} ${mes.dias === 1 ? 'día' : 'días'}`;
};

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
                entreno no la lleva, porque esa nota es la respuesta a una pregunta nuestra.
                Cada marca con su color (doc de Jesús del 2-09, «compartida o privada»):
                «con las dos puestas se sabe de un vistazo qué has visto tú». Los literales
                son los de siempre. */}
            {(entrada.texto || entrada.estrellas) && (
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-2 flex-wrap">
                    {entrada.estrellas ? <span>{estrellas(entrada.estrellas)}</span> : null}
                    <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                        entrada.compartida
                            ? 'bg-brand/10 text-brand border-brand/30'
                            : 'bg-muted text-muted-foreground border-border'}`}>
                        {marca}
                    </span>
                </p>
            )}
        </li>
    );
};

// El día que pasó sin nota: en gris y con el borde discontinuo, «sin riña» (Jesús, doc del
// 2-09). Dice lo que pasó y nada más: ni pide ni recuerda.
const DiaSinNota = ({ fecha }) => (
    <li className="rounded-2xl border border-dashed border-border px-4 py-2.5 text-[13px] text-muted-foreground"
        data-testid="diario-dia-vacio">
        {fechaLarga(fecha)} · no apuntaste nada
    </li>
);

const Diario = ({ api, cycleStart }) => {
    // El arranque del ciclo, para «Este ciclo». Sale del perfil del contexto (el mismo
    // `profile.cycle_start` que usa la gráfica de peso en esta pantalla); la prop lo pisa
    // si algún día se monta el Diario con otro perfil delante.
    const { profile } = useAuth();
    const arranqueCiclo = cycleStart ?? profile?.cycle_start ?? null;
    const [vista, setVista] = useState('mes');
    const [entradas, setEntradas] = useState([]);
    const [hayMas, setHayMas] = useState(false);
    const [cargando, setCargando] = useState(true);
    const [cargandoMas, setCargandoMas] = useState(false);
    const [error, setError] = useState(false);
    const [faltanApuntes, setFaltanApuntes] = useState(false);

    // Lo cargado, fuera del estado, para que las peticiones encadenadas lean lo último y
    // no una foto vieja; y una cola para que dos vistas pedidas seguidas no pidan a la vez
    // las mismas páginas y las dupliquen.
    const cargado = useRef({ entradas: [], hayMas: true });
    const cola = useRef(Promise.resolve());

    const hoy = hoyLocal();
    // «Este ciclo» arranca el día en que empezó el ciclo. `cycle_start` llega unas veces
    // como día suelto («2026-08-17», las fichas arregladas desde el origen) y otras como
    // instante ISO (las que escribe la renovación, un lunes a las 00:00 de España). El día
    // suelto se usa tal cual; el instante se pasa al día DE ESPAÑA, no al del reloj del
    // cliente: el arranque del ciclo es un día del calendario del negocio (core/cycle.py
    // cuenta en hora de Madrid), y pasado al reloj de alguien al oeste de España las 00:00
    // del lunes caen en su domingo. Medido el 4-09 desde Argentina: el diario enseñaba
    // el ciclo arrancando un día antes. Sin arranque no hay ciclo que enseñar, y el chip
    // no sale.
    const diaDelCiclo = !arranqueCiclo ? null
        : esDia(arranqueCiclo) ? String(arranqueCiclo).slice(0, 10)
            : (aFecha(arranqueCiclo) ? diaEnEspana(aFecha(arranqueCiclo)) : null);
    const desde = vista === 'mes' ? primerDiaDelMes(hoy) : vista === 'ciclo' ? diaDelCiclo : null;
    const vistas = diaDelCiclo ? VISTAS : VISTAS.filter(v => v.id !== 'ciclo');

    // Una página más, pegada a lo que ya hay. Devuelve si el servidor guarda más.
    const unaPaginaMas = useCallback(async (limit) => {
        const { entradas: lista } = cargado.current;
        const { data } = await api.get('/diary', { params: { skip: lista.length, limit } });
        const nuevas = data?.entradas || [];
        const todas = [...lista, ...nuevas];
        const quedan = !!data?.hay_mas && nuevas.length > 0;
        cargado.current = { entradas: todas, hayMas: quedan };
        setEntradas(todas);
        setHayMas(quedan);
        return quedan;
    }, [api]);

    const encolar = useCallback((trabajo) => {
        const envuelto = async () => {
            setCargandoMas(true);
            try {
                await trabajo();
                setError(false);
                setFaltanApuntes(false);
            } catch (e) {
                // Al cliente, una frase; el detalle a la consola (regla de la casa). Si ya
                // hay algo cargado se enseña, y se dice que falta parte.
                console.error('No se pudo cargar el diario:', e?.response?.data || e);
                if (cargado.current.entradas.length === 0) setError(true); else setFaltanApuntes(true);
            } finally {
                setCargandoMas(false);
                setCargando(false);
            }
        };
        cola.current = cola.current.then(envuelto, envuelto);
    }, []);

    // Con rango, se traen páginas hasta que el apunte más viejo cargado queda por detrás de
    // `desde`; sin rango («Todo»), la primera página y ya.
    useEffect(() => {
        encolar(async () => {
            const cubierto = () => {
                const lista = cargado.current.entradas;
                return lista.length > 0 && (!desde || (lista[lista.length - 1].fecha || '') < desde);
            };
            let quedan = cargado.current.hayMas;
            while (quedan && !cubierto()) quedan = await unaPaginaMas(desde ? LOTE_DEL_RANGO : POR_PAGINA);
        });
    }, [encolar, unaPaginaMas, desde]);

    const cargarMas = () => encolar(() => unaPaginaMas(POR_PAGINA));

    const meses = useMemo(() => agruparPorMes({ entradas, desde, hoy, hayMas }), [entradas, desde, hoy, hayMas]);
    const nadaEscrito = entradas.length === 0 && !hayMas;

    return (
        <div className="space-y-3" data-testid="diario">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center">
                    <BookOpen className="w-5 h-5 text-brand" />
                </div>
                <div>
                    <p className="text-lg font-bold text-foreground">Tu diario</p>
                    <p className="text-[15px] text-muted-foreground">Lo has ido apuntando cada día</p>
                </div>
            </div>

            {/* Las tres vistas del doc del 2-09. Los chips son los de los momentos de la
                biblioteca de menús: el activo en naranja, el resto en gris. */}
            <div className="flex flex-wrap gap-1.5">
                {vistas.map(v => (
                    <button key={v.id} type="button" onClick={() => setVista(v.id)} aria-pressed={vista === v.id}
                        data-testid={`diario-vista-${v.id}`}
                        className={`px-2.5 py-1 text-xs font-bold rounded-full border transition-colors ${
                            vista === v.id ? 'bg-brand text-white border-brand' : 'bg-muted text-muted-foreground border-border'}`}>
                        {v.texto}
                    </button>
                ))}
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
            ) : nadaEscrito ? (
                <div className="bg-card border border-border rounded-2xl p-8 text-center">
                    <p className="text-sm text-muted-foreground">
                        Aquí caerá lo que vayas apuntando en el cierre del día y en tus entrenos.
                    </p>
                </div>
            ) : (
                <>
                    {meses.map(mes => (
                        <section key={mes.clave} className="space-y-2" data-testid="diario-mes">
                            <p className="caption pt-1">{tituloDelMes(mes, hoy)}</p>
                            <ul className="space-y-2">
                                {mes.filas.map(f => (f.tipo === 'vacio'
                                    ? <DiaSinNota key={f.key} fecha={f.fecha} />
                                    : <Entrada key={f.key} entrada={f.entrada} />))}
                            </ul>
                        </section>
                    ))}
                    {meses.length === 0 && (
                        <div className="bg-card border border-border rounded-2xl p-8 text-center">
                            <p className="text-sm text-muted-foreground">Todavía no hay nada que enseñar aquí.</p>
                        </div>
                    )}
                    {faltanApuntes && (
                        <p className="text-xs text-muted-foreground text-center">
                            No hemos podido traer todos tus apuntes. Inténtalo en un rato.
                        </p>
                    )}
                    {vista !== 'todo' && cargandoMas && (
                        <p className="text-xs text-muted-foreground text-center">Cargando...</p>
                    )}
                    {/* «Ver apuntes anteriores» solo en «Todo»: en las otras dos vistas ya
                        está todo lo del rango. */}
                    {vista === 'todo' && hayMas && (
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
