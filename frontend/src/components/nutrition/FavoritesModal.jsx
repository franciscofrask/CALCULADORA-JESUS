/**
 * FavoritesModal - Dietas favoritas (Calma guardarFavorita / favoritas).
 * Guardar el día actual como plantilla con nombre, listarlas, aplicarlas a la fecha, borrar.
 * Si la favorita se guardó en otro tipo de día, ofrece adaptarla al día actual
 * (entreno<->descanso) o aplicarla como se guardó (cambia el tipo de día).
 */
import React, { useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Star, Trash2, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { ListaDeAlimentos } from './FavoritasDeComida';

const NOMBRE_COMIDA = {
    C1: 'Comida 1', C2: 'Comida 2', C3: 'Comida 3', C4: 'Comida 4',
    C5: 'Comida 5', C6: 'Comida 6', Intra: 'Intra', Post: 'Post',
};

/** Lo que lleva un día guardado, comida a comida. Sin abrirlo no había forma de saberlo. */
const DetalleDelDia = ({ comidas }) => {
    const conAlgo = Object.entries(comidas || {})
        .filter(([, m]) => (m?.alimentos || []).length > 0);
    if (!conAlgo.length) {
        return <p className="mt-2 pt-2 border-t border-border text-xs text-muted-foreground">
            Esta favorita no tiene comidas guardadas.
        </p>;
    }
    return (
        <div className="mt-2 pt-2 border-t border-border space-y-2">
            {conAlgo.map(([clave, m]) => (
                <div key={clave}>
                    <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
                        {NOMBRE_COMIDA[clave] || clave}
                    </p>
                    <ListaDeAlimentos alimentos={m.alimentos} />
                </div>
            ))}
        </div>
    );
};

const esDescanso = (t) => t === 'descanso';
const etiqueta = (t) => esDescanso(t) ? 'descanso' : 'entreno';

// EL AVISO DICE EL NÚMERO (doc de Jesús 3-09, detalle 1): «tus 3 comidas» y no «esas
// comidas», que es lo que hace parar. Y en singular, «1 comida».
//
// El intra y el post no son comidas (regla del 31-08), así que no entran en la cuenta. Pero
// un día que solo tenga el peri montado NO está vacío y diría «ya tiene 0 comidas», que es
// falso: en ese caso se les llama por su nombre.
const loQueHayEnElDia = (comidas, peri) => {
    if (comidas > 0) return comidas === 1 ? '1 comida' : `${comidas} comidas`;
    const p = peri || [];
    if (p.length === 2) return 'el intra y el post';
    if (p.length === 1) return p[0] === 'Intra' ? 'el intra' : 'el post';
    return 'comidas';
};

const TipoDiaBadge = ({ tipo }) => (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${esDescanso(tipo) ? 'bg-muted-foreground/10 text-muted-foreground' : 'bg-brand-orange/10 text-brand-orange'}`}>
        {esDescanso(tipo) ? 'Descanso' : 'Entreno'}
    </span>
);

const FavoritesModal = ({ open, onClose, favorites, onSave, onApply, onDelete, tipoDia = 'entrenamiento', diaVacio = false, comidasDelDia = 0, periDelDia = [] }) => {
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);
    // Favorita con el panel "adaptar o aplicar como se guardó" desplegado.
    const [confirmId, setConfirmId] = useState(null);
    // Favorita desplegada para ver lo que lleva dentro, comida a comida.
    const [detalleId, setDetalleId] = useState(null);

    // DOS FAVORITAS CON EL MISMO NOMBRE NO SIRVEN DE NADA (Jesús, 15-08, fallo 35): «dos
    // "dieta nueva", una de 4 comidas y otra de 6, sin fecha ni macros que las distingan».
    // Se pide otro nombre en vez de guardarla y dejar el lío para luego.
    const nombreRepetido = (n) => (favorites || []).some(
        f => (f.name || '').trim().toLowerCase() === n.toLowerCase());

    const handleSave = async () => {
        const n = name.trim();
        if (!n) return;
        if (nombreRepetido(n)) {
            toast.error(`Ya tienes una favorita que se llama "${n}". Ponle otro nombre para distinguirlas.`);
            return;
        }
        setSaving(true);
        await onSave(n);
        setSaving(false);
        setName('');
    };

    // SE PREGUNTA TAMBIÉN CUANDO EL DÍA YA TIENE COMIDAS (revisión del 2-09).
    //
    // Aquí solo se miraba el tipo de día, así que aplicar una favorita sobre un día ya
    // montado se llevaba por delante el trabajo hecho sin una sola pregunta: es la forma
    // más fácil de perder una tarde, y no se puede deshacer. El dato para saberlo ya
    // llegaba (`diaVacio`) y no se usaba.
    //
    // Se aplica directo solo cuando no hay nada que perder: día vacío Y el mismo tipo.
    const handleApplyClick = (fav) => {
        const favTipo = fav.tipo_dia || 'entrenamiento';
        if (favTipo === tipoDia && diaVacio) {
            onApply(fav);
            return;
        }
        setConfirmId(prev => prev === fav.id ? null : fav.id);
    };

    return (
        <Dialog open={open} onOpenChange={() => { setConfirmId(null); onClose(); }}>
            <DialogContent className="max-w-md bg-card">
                <DialogHeader>
                    <DialogTitle className="text-lg font-bold text-foreground flex items-center gap-2">
                        <Star className="w-5 h-5 text-brand-orange" /> Dietas favoritas
                    </DialogTitle>
                    <DialogDescription className="sr-only">Guarda y reutiliza días como plantillas</DialogDescription>
                </DialogHeader>

                {/* Guardar el día actual */}
                <div className="flex gap-2">
                    <Input
                        placeholder="Nombre (ej. Día alto en hidratos)"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
                    />
                    <Button
                        className="bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full shrink-0"
                        onClick={handleSave}
                        disabled={!name.trim() || saving || diaVacio}
                    >
                        Guardar
                    </Button>
                </div>
                {/* DICE LO QUE GUARDA, Y NO DEJA GUARDAR UN DÍA VACÍO.
                    Ponía «guarda la comida actual del día» y lo que guarda es el DÍA ENTERO;
                    además dejaba guardar uno sin nada, que luego aparece en la lista como
                    favorita de cero comidas (Jesús, 11-08). */}
                <p className="text-xs text-muted-foreground -mt-2">
                    {diaVacio
                        ? 'Este día no tiene comidas todavía: monta algo y podrás guardarlo.'
                        : 'Guarda este día entero para repetirlo cuando quieras.'}
                </p>

                {/* Lista */}
                <div className="max-h-72 overflow-auto -mx-1 px-1 space-y-1">
                    {(!favorites || favorites.length === 0) ? (
                        <p className="text-sm text-muted-foreground text-center py-6">Todavía no tienes favoritas.</p>
                    ) : favorites.map(fav => {
                        // EL INTRA Y EL POST NO SON COMIDAS (31-08-2026). Esto contaba todas
                        // las claves con alimentos, peri incluido, así que un día de TRES
                        // comidas con intra y post salía en la lista como «5 comidas» -- y con
                        // una Comida 4 fantasma de las de antes del 29-08, como «6». Un cliente
                        // lo reportó: guarda su día de tres y la favorita dice otra cosa.
                        // El peri va detrás y por su nombre, que es como se llama en la app.
                        const conAlgo = Object.entries(fav.comidas || {})
                            .filter(([, m]) => (m?.alimentos || []).length > 0)
                            .map(([k]) => k);
                        const n = conAlgo.filter(k => /^C\d+$/.test(k)).length;
                        const peri = conAlgo.filter(k => k === 'Intra' || k === 'Post');
                        const favTipo = fav.tipo_dia || 'entrenamiento';
                        return (
                            <div key={fav.id} className="bg-muted rounded-lg p-2">
                                <div className="flex items-center gap-2">
                                    {/* El nombre abre el detalle: hasta ahora, para saber qué
                                        llevaba un día guardado había que aplicarlo. */}
                                    <button className="flex-1 min-w-0 text-left"
                                        onClick={() => setDetalleId(prev => prev === fav.id ? null : fav.id)}
                                        data-testid={`fav-ver-${fav.id}`}>
                                        {/* El nombre entero al pasar por encima: recortado no
                                            hay manera de distinguir dos favoritas parecidas. */}
                                        <p className="text-sm font-semibold text-foreground truncate flex items-center gap-1" title={fav.name}>
                                            {fav.name}
                                            {detalleId === fav.id ? <ChevronUp className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                                                : <ChevronDown className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
                                        </p>
                                        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                                            {n === 1 ? '1 comida' : `${n} comidas`}
                                            {peri.length > 0 && ` + ${peri.join(' y ')}`}
                                            {' '}<TipoDiaBadge tipo={favTipo} />
                                        </p>
                                    </button>
                                    <Button variant="outline" size="sm" className="rounded-full border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white shrink-0"
                                        onClick={() => handleApplyClick(fav)} title="Aplicar a este día" data-testid={`fav-apply-${fav.id}`}>
                                        <Download className="w-4 h-4 mr-1" /> Aplicar
                                    </Button>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-500 shrink-0"
                                        onClick={() => onDelete(fav.id)} title="Eliminar">
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>

                                {detalleId === fav.id && <DetalleDelDia comidas={fav.comidas} />}

                                {/* EL AVISO DE ANTES DE APLICAR (doc de Jesús 3-09).
                                    Dos condiciones, cada una con su frase, siempre antes de
                                    los botones y en este orden: PRIMERO LO QUE SE PIERDE,
                                    DESPUÉS EL TIPO DE DÍA. Las dos frases van juntas, una
                                    detrás de otra, no separadas. */}
                                {confirmId === fav.id && (
                                    <div className="mt-2 pt-2 border-t border-border space-y-2" data-testid={`fav-adapt-panel-${fav.id}`}>
                                        {(!diaVacio || favTipo !== tipoDia) && (
                                            <p className="text-xs text-foreground">
                                                {!diaVacio && (
                                                    <span className="block" data-testid={`fav-reemplaza-${fav.id}`}>
                                                        Este día ya tiene {loQueHayEnElDia(comidasDelDia, periDelDia)}. Al
                                                        aplicar la favorita se borran y se quedan las de la favorita.
                                                    </span>
                                                )}
                                                {favTipo !== tipoDia && (
                                                    <span className="block" data-testid={`fav-tipo-${fav.id}`}>
                                                        Esta favorita es de día de {etiqueta(favTipo)}; hoy tienes {etiqueta(tipoDia)}.
                                                    </span>
                                                )}
                                            </p>
                                        )}
                                        {favTipo !== tipoDia ? (
                                            <>
                                                <Button size="sm" className="w-full bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full"
                                                    onClick={() => { setConfirmId(null); onApply(fav, { adaptar: true }); }}
                                                    data-testid={`fav-adapt-${fav.id}`}>
                                                    Aplicar y adaptar a mi día de hoy
                                                </Button>
                                                {/* LA LÍNEA GRIS CAMBIA CON EL SENTIDO (detalle 2). De entreno
                                                    a descanso el peri se quita; de descanso a entreno se añade
                                                    VACÍO, con sus macros y sin alimentos: la app no se inventa
                                                    qué meter dentro, lo rellena el cliente. */}
                                                <p className="text-[11px] text-muted-foreground -mt-1">
                                                    {esDescanso(tipoDia)
                                                        ? 'el intra y el post se quitan'
                                                        : 'se añaden el intra y el post, que tendrás que rellenar'}
                                                </p>
                                                <Button size="sm" variant="outline" className="w-full rounded-full"
                                                    onClick={() => { setConfirmId(null); onApply(fav, { adaptar: false }); }}>
                                                    Aplicar como se guardó (pasa el día a {etiqueta(favTipo)})
                                                </Button>
                                            </>
                                        ) : (
                                            /* Mismo tipo de día: solo se pregunta por lo que se pierde. */
                                            <Button size="sm" className="w-full bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full"
                                                onClick={() => { setConfirmId(null); onApply(fav); }}
                                                data-testid={`fav-reemplazar-${fav.id}`}>
                                                Aplicar
                                            </Button>
                                        )}
                                        {/* Cancelar es un ENLACE en gris, sin caja (detalle 4). Cierra el
                                            aviso y deja la lista de favoritas abierta (detalle 5). */}
                                        <button className="block text-left text-xs text-muted-foreground underline hover:text-foreground"
                                            onClick={() => setConfirmId(null)}>
                                            Cancelar
                                        </button>
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

export default FavoritesModal;
