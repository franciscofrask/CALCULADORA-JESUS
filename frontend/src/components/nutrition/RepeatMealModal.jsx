import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';

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
                    <DialogDescription className="text-gray-400">
                        Copiar a {mealKey && mealInfo[mealKey]?.name}
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto">
                    {!selectedDiet ? (
                        <div className="p-4">
                            {recentDiets.length === 0 ? (
                                <div className="text-center py-8 text-gray-500">
                                    <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin" />
                                    <p>Cargando días recientes...</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {recentDiets.map(diet => (
                                        <button
                                            key={diet.fecha}
                                            className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-xl transition-all"
                                            onClick={() => setSelectedDiet(diet)}
                                            data-testid={`repeat-diet-${diet.fecha}`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="font-semibold text-gray-900">{formatDate(diet.fecha)}</p>
                                                    <p className="text-xs text-gray-500">
                                                        {diet.tipo_dia === 'entrenamiento' ? '🟢 Entreno' : '⚪ Descanso'}, {diet.num_comidas} comidas
                                                    </p>
                                                </div>
                                                <ChevronRight className="w-5 h-5 text-gray-400" />
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="p-4">
                            <button
                                className="flex items-center gap-2 text-sm text-gray-500 mb-4"
                                onClick={() => setSelectedDiet(null)}
                            >
                                <ChevronLeft className="w-4 h-4" /> Volver
                            </button>

                            <h3 className="font-bold text-gray-900 mb-3">
                                Comidas del {formatDate(selectedDiet.fecha)}
                            </h3>

                            <div className="space-y-2">
                                {Object.entries(selectedDiet.comidas_resumen || {}).map(([key, resumen]) => (
                                    <button
                                        key={key}
                                        className="w-full text-left p-3 bg-gray-50 hover:bg-brand-orange/10 rounded-xl transition-all border-2 border-transparent hover:border-brand-orange"
                                        onClick={() => handleCopy(key)}
                                        data-testid={`repeat-meal-${key}`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-gray-900">
                                                    {mealInfo[key]?.name || key}
                                                </p>
                                                <p className="text-xs text-gray-500 truncate max-w-[250px]">
                                                    {resumen}
                                                </p>
                                            </div>
                                            <span className="text-brand-orange text-sm font-semibold">Copiar</span>
                                        </div>
                                    </button>
                                ))}

                                {Object.keys(selectedDiet.comidas_resumen || {}).length === 0 && (
                                    <p className="text-center text-gray-500 py-4">
                                        No hay comidas guardadas este día
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
