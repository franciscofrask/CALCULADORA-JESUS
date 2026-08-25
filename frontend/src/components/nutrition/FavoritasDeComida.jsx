/**
 * FAVORITAS DE UNA COMIDA (Francisco, 25-08).
 *
 * La favorita de siempre es el DÍA entero: para guardar «mi desayuno de siempre» había que
 * guardar el día completo y luego borrar lo que sobraba. Se notaba en los datos: de las
 * 1.245 favoritas de producción, 72 tenían una sola comida con alimentos.
 *
 * Aquí se guarda y se aplica UNA comida. Una favorita de la Comida 2 se puede poner en la 3
 * sin problema: el nombre de origen se enseña solo para orientar, no para atar.
 */
import React, { useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Star, Trash2, Download, ChevronDown, ChevronUp } from 'lucide-react';

const resumenMacros = (m) => {
    if (!m) return null;
    const n = (v) => Math.round(Number(v) || 0);
    return `${n(m.P)}P · ${n(m.H)}H${m.G ? ` · ${n(m.G)}G` : ''}`;
};

/** La cantidad como se ve en la dieta: «2 ud (72 g)» si va por unidades, si no «200 g». */
export const cantidadDeAlimento = (a) => {
    const g = Math.round(Number(a?.cantidad_g) || 0);
    const racion = Number(a?.racion) || 0;
    if (a?.unidades && racion > 0) {
        const uds = g / racion;
        const texto = Number.isInteger(uds) ? uds : Math.round(uds * 10) / 10;
        return `${texto} ud (${g} g)`;
    }
    return `${g} g`;
};

/** Lo que lleva dentro una favorita, para poder mirarla antes de ponerla.
 *  Sin separador propio: lo pone quien la usa, que unas veces va suelta y otras
 *  repetida una vez por comida (ver `DetalleDelDia` en FavoritesModal). */
export const ListaDeAlimentos = ({ alimentos }) => (
    <ul className="space-y-1">
        {(alimentos || []).map((a, i) => (
            <li key={i} className="flex items-baseline justify-between gap-3 text-xs">
                <span className="text-foreground truncate" title={a.nombre}>{a.nombre}</span>
                <span className="text-muted-foreground shrink-0 tabular-nums">{cantidadDeAlimento(a)}</span>
            </li>
        ))}
        {!(alimentos || []).length && (
            <li className="text-xs text-muted-foreground">Esta favorita no tiene alimentos guardados.</li>
        )}
    </ul>
);

const esPeri = (k) => ['Intra', 'Post'].includes(k);

/**
 * UNA FAVORITA NO VALE PARA CUALQUIER COMIDA (Francisco, 25-08).
 *
 * El intra y el post son otra cosa: un desayuno no se puede poner de post, y un post -whey
 * con crema de arroz, sin grasa- no es una comida normal. Así que en el peri solo salen las
 * de ESE peri, y en una comida normal solo las de comidas normales.
 */
const valeAqui = (fav, mealKey) => {
    const origen = fav.comida_origen;
    if (!origen) return !esPeri(mealKey);   // las viejas, sin origen, son de comida normal
    return esPeri(mealKey) ? origen === mealKey : !esPeri(origen);
};

const FavoritasDeComida = ({
    open, onClose, mealKey, mealLabel, favorites, comidaLlena,
    onSave, onApply, onDelete,
}) => {
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);
    // Favorita desplegada para ver lo que lleva dentro.
    const [abierta, setAbierta] = useState(null);

    const delSitio = (favorites || []).filter(f => valeAqui(f, mealKey));

    // Mismo criterio que en las favoritas de día: dos con el mismo nombre no sirven de nada.
    const nombreRepetido = (n) => (favorites || []).some(
        f => (f.name || '').trim().toLowerCase() === n.toLowerCase());

    const guardar = async () => {
        const n = name.trim();
        if (!n) return;
        if (nombreRepetido(n)) {
            toast.error(`Ya tienes una comida favorita que se llama "${n}". Ponle otro nombre.`);
            return;
        }
        setSaving(true);
        await onSave(n);
        setSaving(false);
        setName('');
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-md bg-card">
                <DialogHeader>
                    <DialogTitle className="text-lg font-bold text-foreground flex items-center gap-2">
                        <Star className="w-5 h-5 text-brand-orange" /> Comidas favoritas
                    </DialogTitle>
                    <DialogDescription className="sr-only">
                        Guarda esta comida y reutilízala en cualquier otra
                    </DialogDescription>
                </DialogHeader>

                <div className="flex gap-2">
                    <Input
                        placeholder="Nombre (ej. Mi desayuno de siempre)"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') guardar(); }}
                        disabled={!comidaLlena}
                    />
                    <Button
                        className="bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full shrink-0"
                        onClick={guardar}
                        disabled={!name.trim() || saving || !comidaLlena}
                        data-testid="guardar-comida-favorita"
                    >
                        Guardar
                    </Button>
                </div>
                <p className="text-xs text-muted-foreground -mt-2">
                    {comidaLlena
                        ? `Guarda ${mealLabel} tal como está para repetirla cuando quieras.`
                        : `${mealLabel} está vacía: ponle algo y podrás guardarla.`}
                </p>

                <div className="max-h-72 overflow-auto -mx-1 px-1 space-y-1">
                    {delSitio.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-6">
                            {(favorites || []).length
                                ? `Ninguna de tus comidas guardadas sirve para ${mealLabel}.`
                                : 'Todavía no tienes comidas guardadas.'}
                        </p>
                    ) : delSitio.map(fav => {
                        const cuantos = (fav.alimentos || []).length;
                        const macros = resumenMacros(fav.macros_snapshot);
                        // Solo se avisa del origen si NO es esta misma comida: dentro de la
                        // suya el dato sobra y solo hace ruido.
                        const deOtra = fav.comida_origen && fav.comida_origen !== mealKey;
                        const desplegada = abierta === fav.id;
                        return (
                            <div key={fav.id} className="bg-muted rounded-lg p-2">
                                <div className="flex items-center gap-2">
                                    {/* El nombre abre el detalle: antes había que ponerla
                                        para saber qué llevaba dentro. */}
                                    <button className="flex-1 min-w-0 text-left"
                                        onClick={() => setAbierta(desplegada ? null : fav.id)}
                                        data-testid={`fav-comida-ver-${fav.id}`}>
                                        <p className="text-sm font-semibold text-foreground truncate flex items-center gap-1" title={fav.name}>
                                            {fav.name}
                                            {desplegada ? <ChevronUp className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                                                : <ChevronDown className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {cuantos === 1 ? '1 alimento' : `${cuantos} alimentos`}
                                            {macros ? ` · ${macros}` : ''}
                                            {deOtra ? ` · de ${fav.comida_origen}` : ''}
                                        </p>
                                    </button>
                                    <Button variant="outline" size="sm"
                                        className="rounded-full border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white shrink-0"
                                        onClick={() => onApply(fav)} title={`Poner en ${mealLabel}`}
                                        data-testid={`fav-comida-apply-${fav.id}`}>
                                        <Download className="w-4 h-4 mr-1" /> Poner aquí
                                    </Button>
                                    <Button variant="ghost" size="icon"
                                        className="h-8 w-8 text-muted-foreground hover:text-red-500 shrink-0"
                                        onClick={() => onDelete(fav.id)} title="Eliminar">
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>
                                {desplegada && (
                                    <div className="mt-2 pt-2 border-t border-border">
                                        <ListaDeAlimentos alimentos={fav.alimentos} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default FavoritasDeComida;
