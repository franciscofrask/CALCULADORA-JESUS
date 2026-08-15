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
import { Star, Trash2, Download } from 'lucide-react';

const esDescanso = (t) => t === 'descanso';
const etiqueta = (t) => esDescanso(t) ? 'descanso' : 'entreno';

const TipoDiaBadge = ({ tipo }) => (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${esDescanso(tipo) ? 'bg-muted-foreground/10 text-muted-foreground' : 'bg-brand-orange/10 text-brand-orange'}`}>
        {esDescanso(tipo) ? 'Descanso' : 'Entreno'}
    </span>
);

const FavoritesModal = ({ open, onClose, favorites, onSave, onApply, onDelete, tipoDia = 'entrenamiento', diaVacio = false }) => {
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);
    // Favorita con el panel "adaptar o aplicar como se guardó" desplegado.
    const [confirmId, setConfirmId] = useState(null);

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

    const handleApplyClick = (fav) => {
        const favTipo = fav.tipo_dia || 'entrenamiento';
        if (favTipo === tipoDia) {
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
                        const n = Object.values(fav.comidas || {}).filter(m => (m?.alimentos || []).length > 0).length;
                        const favTipo = fav.tipo_dia || 'entrenamiento';
                        return (
                            <div key={fav.id} className="bg-muted rounded-lg p-2">
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 min-w-0">
                                        {/* El nombre entero al pasar por encima: recortado no
                                            hay manera de distinguir dos favoritas parecidas. */}
                                        <p className="text-sm font-semibold text-foreground truncate" title={fav.name}>{fav.name}</p>
                                        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                                            {n === 1 ? '1 comida' : `${n} comidas`} <TipoDiaBadge tipo={favTipo} />
                                        </p>
                                    </div>
                                    <Button variant="outline" size="sm" className="rounded-full border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white shrink-0"
                                        onClick={() => handleApplyClick(fav)} title="Aplicar a este día" data-testid={`fav-apply-${fav.id}`}>
                                        <Download className="w-4 h-4 mr-1" /> Aplicar
                                    </Button>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-500 shrink-0"
                                        onClick={() => onDelete(fav.id)} title="Eliminar">
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>

                                {/* Tipo de día distinto: adaptar o aplicar como se guardó */}
                                {confirmId === fav.id && (
                                    <div className="mt-2 pt-2 border-t border-border space-y-2" data-testid={`fav-adapt-panel-${fav.id}`}>
                                        <p className="text-xs text-foreground">
                                            Esta favorita se guardó en día de <span className="font-bold">{etiqueta(favTipo)}</span> y
                                            hoy es día de <span className="font-bold">{etiqueta(tipoDia)}</span>.
                                        </p>
                                        <Button size="sm" className="w-full bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full"
                                            onClick={() => { setConfirmId(null); onApply(fav, { adaptar: true }); }}
                                            data-testid={`fav-adapt-${fav.id}`}>
                                            Adaptar a mi día de hoy ({etiqueta(tipoDia)})
                                        </Button>
                                        <p className="text-[11px] text-muted-foreground -mt-1">
                                            {esDescanso(tipoDia)
                                                ? 'El intra/post se quitará porque en descanso no hay periworkout.'
                                                : 'El peri quedará vacío: podrás añadirlo con "Sugiéreme un menú".'}
                                        </p>
                                        <Button size="sm" variant="outline" className="w-full rounded-full"
                                            onClick={() => { setConfirmId(null); onApply(fav, { adaptar: false }); }}>
                                            Aplicar como se guardó (cambia el día a {etiqueta(favTipo)})
                                        </Button>
                                        <button className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
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
