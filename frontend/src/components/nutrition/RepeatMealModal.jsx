import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';

// El intra y el post son comidas de otra naturaleza: no se mezclan con las normales
// ni entre ellas. Un intra solo se repite desde otro intra, y un post desde otro post.
const esPeri = (k) => ['Intra', 'Post'].includes(k);

const RepeatMealModal = ({
    open,
    mealKey,
    onClose,
    recentDiets,
    mealInfo,
    formatDate,
    onCopyMeal,
}) => {
    const [selectedDiet, setSelectedDiet] = useState(null);

    const handleClose = () => {
        setSelectedDiet(null);
        onClose();
    };

    const handleCopy = (sourceMealKey) => {
        onCopyMeal(sourceMealKey, selectedDiet);
        setSelectedDiet(null);
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
            <DialogContent className="max-w-md max-h-[85vh] flex flex-col p-0 gap-0 overflow-hidden" data-testid="repeat-meal-modal">
                <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                    <DialogTitle className="text-white">Repetir de otro día</DialogTitle>
                    <DialogDescription className="text-muted-foreground">
                        Copiar a {mealKey && mealInfo[mealKey]?.name}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto">
                    {!selectedDiet ? (
                        <div className="p-4">
                            {recentDiets.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin" />
                                    <p>Cargando días recientes...</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {/* SE LEE QUÉ HABÍA EN ESA COMIDA, SIN ENTRAR.
                                        Aquí solo ponía «lun, 10 ago · 🟢 Entreno, 4 comidas» y
                                        había que abrir día por día hasta dar con el bueno. Lo
                                        que se busca al repetir no es una fecha: es una comida
                                        concreta que ya sabes que te gustó.
                                        El dato ya venía en la respuesta (`comidas_resumen`), pero
                                        solo se usaba DESPUÉS de elegir el día. Jesús, 11-08:
                                        siendo el camino más usado, es donde más se nota cada
                                        clic de más.
                                        Los días donde esa comida está vacía se quedan sin la
                                        línea, que es la señal de que ahí no hay nada que copiar. */}
                                    {recentDiets.map(diet => {
                                        const loQueHabia = (diet.comidas_resumen || {})[mealKey];
                                        return (
                                            <button
                                                key={diet.fecha}
                                                className="w-full text-left p-3 bg-muted hover:bg-muted rounded-xl transition-all"
                                                onClick={() => setSelectedDiet(diet)}
                                                data-testid={`repeat-diet-${diet.fecha}`}
                                            >
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="min-w-0">
                                                        <p className="font-semibold text-foreground">{formatDate(diet.fecha)}</p>
                                                        {loQueHabia ? (
                                                            <p className="text-sm text-foreground/80 mt-0.5">{loQueHabia}</p>
                                                        ) : (
                                                            <p className="text-sm text-muted-foreground/70 mt-0.5">Sin nada en esta comida</p>
                                                        )}
                                                        <p className="text-xs text-muted-foreground mt-0.5">
                                                            {diet.tipo_dia === 'entrenamiento' ? '🟢 Entreno' : '⚪ Descanso'}, {diet.num_comidas} {diet.num_comidas === 1 ? 'comida' : 'comidas'}
                                                        </p>
                                                    </div>
                                                    <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="p-4">
                            <button
                                className="flex items-center gap-2 text-sm text-muted-foreground mb-4"
                                onClick={() => setSelectedDiet(null)}
                            >
                                <ChevronLeft className="w-4 h-4" /> Volver
                            </button>

                            <h3 className="font-bold text-foreground mb-3">
                                Comidas del {formatDate(selectedDiet.fecha)}
                            </h3>

                            <div className="space-y-2">
                                {Object.entries(selectedDiet.comidas_resumen || {})
                                    // NO SE PUEDE COPIAR CUALQUIER COMIDA AQUÍ (Francisco, 25-08).
                                    // Estando en el Intra ofrecía copiar la Comida 1, 2, 3 o 4:
                                    // un desayuno no es un intra, y un intra -MAP con hidrato
                                    // rápido, sin grasa- no es una comida normal. En el peri solo
                                    // se ofrece ESE mismo peri de otros días, y en una comida
                                    // normal, solo comidas normales.
                                    .filter(([key]) => (esPeri(mealKey) ? key === mealKey : !esPeri(key)))
                                    .map(([key, resumen]) => (
                                    <button
                                        key={key}
                                        className="w-full text-left p-3 bg-muted hover:bg-brand-orange/10 rounded-xl transition-all border-2 border-transparent hover:border-brand-orange"
                                        onClick={() => handleCopy(key)}
                                        data-testid={`repeat-meal-${key}`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-foreground">
                                                    {mealInfo[key]?.name || key}
                                                </p>
                                                <p className="text-xs text-muted-foreground truncate max-w-[250px]">
                                                    {resumen}
                                                </p>
                                            </div>
                                            <span className="text-brand-orange text-sm font-semibold">Copiar</span>
                                        </div>
                                    </button>
                                ))}

                                {Object.keys(selectedDiet.comidas_resumen || {})
                                    .filter(key => (esPeri(mealKey) ? key === mealKey : !esPeri(key)))
                                    .length === 0 && (
                                    <p className="text-center text-muted-foreground py-4">
                                        {esPeri(mealKey)
                                            ? `Ese día no tiene ${mealInfo[mealKey]?.name || mealKey} guardado`
                                            : 'No hay comidas guardadas este día'}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex-shrink-0 p-4 border-t">
                    <Button
                        variant="outline"
                        className="w-full rounded-full"
                        onClick={handleClose}
                        data-testid="repeat-cancel-btn"
                    >
                        Cancelar
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default RepeatMealModal;
