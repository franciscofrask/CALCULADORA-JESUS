/**
 * FavoritesModal — Dietas favoritas (Calma guardarFavorita / favoritas).
 * Guardar el día actual como plantilla con nombre, listarlas, aplicarlas a la fecha, borrar.
 */
import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Star, Trash2, Download } from 'lucide-react';

const FavoritesModal = ({ open, onClose, favorites, onSave, onApply, onDelete }) => {
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);

    const handleSave = async () => {
        const n = name.trim();
        if (!n) return;
        setSaving(true);
        await onSave(n);
        setSaving(false);
        setName('');
    };

    return (
        <Dialog open={open} onOpenChange={() => onClose()}>
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
                        disabled={!name.trim() || saving}
                    >
                        Guardar
                    </Button>
                </div>
                <p className="text-xs text-muted-foreground -mt-2">Guarda la comida actual del día como plantilla reutilizable.</p>

                {/* Lista */}
                <div className="max-h-72 overflow-auto -mx-1 px-1 space-y-1">
                    {(!favorites || favorites.length === 0) ? (
                        <p className="text-sm text-muted-foreground text-center py-6">Todavía no tienes favoritas.</p>
                    ) : favorites.map(fav => {
                        const n = Object.values(fav.comidas || {}).filter(m => (m?.alimentos || []).length > 0).length;
                        return (
                            <div key={fav.id} className="flex items-center gap-2 bg-muted rounded-lg p-2">
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-foreground truncate">{fav.name}</p>
                                    <p className="text-xs text-muted-foreground">{n} comida(s) · {fav.tipo_dia}</p>
                                </div>
                                <Button variant="outline" size="sm" className="rounded-full border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white shrink-0"
                                    onClick={() => onApply(fav)} title="Aplicar a este día">
                                    <Download className="w-4 h-4 mr-1" /> Aplicar
                                </Button>
                                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-500 shrink-0"
                                    onClick={() => onDelete(fav.id)} title="Eliminar">
                                    <Trash2 className="w-4 h-4" />
                                </Button>
                            </div>
                        );
                    })}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default FavoritesModal;
