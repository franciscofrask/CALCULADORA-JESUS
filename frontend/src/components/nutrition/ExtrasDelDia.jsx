import React, { useEffect, useState } from 'react';
import { Plus, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Input } from '../ui/input';
import { num1 } from '../../lib/numeros';

/**
 * «EXTRAS DEL DÍA» (apartado 5 y «Extras» del doc de Jesús del 21-08).
 *
 * Lo que el cliente se come FUERA de su dieta -- el cumpleaños, el picoteo -- no tenía
 * dónde apuntarse: o lo metía en una comida (y descuadraba el reparto) o no lo contaba
 * (y la app creía que iba perfecto). Este bloque va debajo de las comidas y del
 * perientreno: los extras CUENTAN EN LLEVAS (los suma TuDietaHoy) y NO TOCAN LA DIETA,
 * y con ellos «Falta» puede quedar en negativo y se dice tal cual. Es lo que hace que
 * el cliente no tenga que mentirle a la app para que le cuadre.
 *
 * El dato vive en el servidor (`extras` en el documento del día): POST
 * /diets/{fecha}/extras calcula los macros de etiqueta al añadir y los guarda en el
 * propio extra; aquí solo se pinta lo que devuelve. El estado lo lleva el padre
 * (TuDietaHoy), que necesita la lista para la cuenta de Llevas: este componente avisa
 * con `onAnadido` / `onQuitado` y no guarda copia propia.
 *
 * El buscador es uno mínimo contra `/calculator/search` (el mismo endpoint del buscador
 * de Nutrición): el de BuildMealModal vive atado al estado de esa pantalla -- categorías,
 * hueco de macros, cantidades sugeridas -- y aquí nada de eso aplica: un extra no cuadra
 * nada, solo se apunta.
 */

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

const lineaMacros = (m) => ['P', 'H', 'G']
    .filter((k) => (m?.[k] || 0) > 0)
    .map((k) => `${num1(m[k])}${k}`)
    .join(' · ') || '0P · 0H · 0G';

const esPorUnidad = (food) => Boolean(food?.por_unidad ?? food?.unidades);

const ExtrasDelDia = ({ api, fecha, extras = [], onAnadido, onQuitado }) => {
    const [abierto, setAbierto] = useState(false);
    const [query, setQuery] = useState('');
    const [resultados, setResultados] = useState([]);
    const [buscando, setBuscando] = useState(false);
    const [elegido, setElegido] = useState(null);
    const [cantidad, setCantidad] = useState('');
    const [guardando, setGuardando] = useState(false);
    const [quitando, setQuitando] = useState(null);

    // Búsqueda con su respiro (300 ms, como el resto de buscadores de la casa).
    useEffect(() => {
        if (!abierto || elegido) return undefined;
        const texto = query.trim();
        if (texto.length < 2) { setResultados([]); setBuscando(false); return undefined; }
        setBuscando(true);
        const t = setTimeout(() => {
            api.get('/calculator/search', { params: { q: texto, limit: 30 } })
                .then((r) => { setResultados(r.data?.alimentos || []); setBuscando(false); })
                .catch((err) => {
                    console.error('[extras] no se pudo buscar en el catálogo', err);
                    setResultados([]); setBuscando(false);
                });
        }, 300);
        return () => clearTimeout(t);
    }, [query, abierto, elegido, api]);

    const cerrar = () => {
        setAbierto(false); setQuery(''); setResultados([]);
        setElegido(null); setCantidad(''); setGuardando(false);
    };

    const elegir = (food) => {
        setElegido(food);
        // Un arranque razonable que el cliente corrige: 1 unidad, o 100 g.
        setCantidad(esPorUnidad(food) ? '1' : '100');
    };

    const anadir = async () => {
        const valor = parseFloat(String(cantidad).replace(',', '.'));
        if (!valor || valor <= 0) {
            toast.error('Dime cuánto ha sido.');
            return;
        }
        setGuardando(true);
        try {
            const cuerpo = esPorUnidad(elegido)
                ? { alimento_id: elegido.id, unidades: valor }
                : { alimento_id: elegido.id, cantidad_g: valor };
            const r = await api.post(`/diets/${fecha}/extras`, cuerpo);
            onAnadido?.(r.data.extra);
            cerrar();
        } catch (err) {
            console.error('[extras] no se pudo apuntar el extra', err);
            toast.error('No se pudo apuntar el extra. Prueba otra vez.');
            setGuardando(false);
        }
    };

    const quitar = async (extra) => {
        setQuitando(extra.id);
        try {
            await api.delete(`/diets/${fecha}/extras/${extra.id}`);
            onQuitado?.(extra.id);
        } catch (err) {
            console.error('[extras] no se pudo quitar el extra', err);
            toast.error('No se pudo quitar el extra. Prueba otra vez.');
        } finally {
            setQuitando(null);
        }
    };

    return (
        <section className="space-y-3" data-testid="extras-del-dia">
            <p className="caption">Extras del día</p>

            {extras.length === 0 && (
                <p className="text-sm text-muted-foreground">
                    ¿Te has comido algo que no estaba en tu dieta? Apúntalo aquí:
                    cuenta en Llevas y no toca tu dieta.
                </p>
            )}

            {extras.map((e) => (
                <div key={e.id} data-testid={`extra-${e.id}`}
                    className="surface p-3.5 sm:p-4 flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                        <p className="font-bold text-sm text-foreground">{e.nombre}</p>
                        <p className="text-sm text-muted-foreground font-data">
                            {e.cantidad_texto || `${num1(e.cantidad_g)} g`} · {lineaMacros(e.macros)}
                        </p>
                    </div>
                    <button onClick={() => quitar(e)} disabled={quitando === e.id}
                        aria-label={`Quitar ${e.nombre} de los extras`} data-testid={`quitar-extra-${e.id}`}
                        className="flex-shrink-0 p-2 -m-1 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40">
                        <Trash2 className="w-5 h-5" />
                    </button>
                </div>
            ))}

            <button onClick={() => setAbierto(true)} data-testid="anadir-extra"
                className="surface surface-hover w-full p-3.5 sm:p-4 flex items-center gap-3 text-left group">
                <div className="w-9 h-9 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Plus className="w-4 h-4 text-brand" />
                </div>
                <p className="font-bold text-sm text-foreground">Añadir un extra</p>
            </button>

            <Dialog open={abierto} onOpenChange={(o) => !o && cerrar()}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden">
                    <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                        {/* Sin X propia: la trae el DialogContent y cierra por onOpenChange (había dos) */}
                        <DialogTitle className="text-white">Añadir un extra</DialogTitle>
                        <DialogDescription className="sr-only">
                            Busca el alimento que te has comido fuera de tu dieta y di cuánto ha sido
                        </DialogDescription>
                    </DialogHeader>

                    {!elegido ? (
                        <>
                            <div className="p-4 bg-card flex-shrink-0 border-b">
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                                    <Input autoFocus placeholder="¿Qué te has comido?" value={query}
                                        onChange={(ev) => setQuery(ev.target.value)}
                                        className="pl-10 h-12 rounded-xl bg-muted border-0" data-testid="buscar-extra-input" />
                                </div>
                            </div>
                            <div className="flex-1 min-h-0 overflow-y-auto bg-muted">
                                {buscando ? (
                                    <div className="flex items-center justify-center py-12">
                                        <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-orange border-t-transparent" />
                                    </div>
                                ) : resultados.length === 0 ? (
                                    <p className="text-center py-12 text-muted-foreground text-sm px-6">
                                        {query.trim().length < 2
                                            ? 'Escribe para buscar en el catálogo.'
                                            : 'No hay nada con ese nombre. Prueba con otro.'}
                                    </p>
                                ) : (
                                    <div className="p-4 space-y-2">
                                        {resultados.map((food) => (
                                            <button key={food.id} onClick={() => elegir(food)}
                                                data-testid={`resultado-extra-${food.id}`}
                                                className="w-full text-left p-4 bg-card rounded-xl shadow-sm hover:shadow-md transition-all active:scale-[0.98]">
                                                <p className="font-semibold text-foreground">{food.nombre}</p>
                                                <p className="text-xs text-muted-foreground mt-0.5 font-data">
                                                    {['P', 'H', 'G'].map((k, i) => {
                                                        const v = [food.proteinas, food.hidratos, food.grasas][i] || 0;
                                                        return v > 0 ? (
                                                            <span key={k} className="mr-2" style={{ color: MACRO[k] }}>
                                                                {num1(v)}{k}
                                                            </span>
                                                        ) : null;
                                                    })}
                                                    <span>por {esPorUnidad(food) ? 'unidad' : '100 g'}</span>
                                                </p>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="p-4 bg-card space-y-4">
                            <div>
                                <p className="font-bold text-foreground">{elegido.nombre}</p>
                                <button onClick={() => { setElegido(null); setCantidad(''); }}
                                    className="text-sm text-brand font-semibold mt-0.5">
                                    Cambiar de alimento
                                </button>
                            </div>
                            <div>
                                <label className="text-sm font-semibold text-foreground block mb-1.5" htmlFor="cantidad-extra">
                                    {esPorUnidad(elegido)
                                        ? `¿Cuántas unidades? (una son ${num1(elegido.racion || 100)} g)`
                                        : '¿Cuántos gramos?'}
                                </label>
                                <Input id="cantidad-extra" type="number" inputMode="decimal" min="0"
                                    step={esPorUnidad(elegido) ? '0.5' : '5'} value={cantidad}
                                    onChange={(ev) => setCantidad(ev.target.value)}
                                    className="h-12 rounded-xl bg-muted border-0 text-lg font-data"
                                    data-testid="cantidad-extra-input" />
                            </div>
                            <button onClick={anadir} disabled={guardando} data-testid="confirmar-extra"
                                className="w-full h-12 rounded-xl bg-brand text-white font-bold text-sm disabled:opacity-60 transition-opacity">
                                {guardando ? 'Apuntando...' : 'Apuntarlo'}
                            </button>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </section>
    );
};

export default ExtrasDelDia;
