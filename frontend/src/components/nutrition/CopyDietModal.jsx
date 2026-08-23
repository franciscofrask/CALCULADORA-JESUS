import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

const CopyDietModal = ({
    open,
    onClose,
    copyDate,
    setCopyDate,
    onCopy,
    currentDateFormatted,
}) => {
    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-sm rounded-2xl" data-testid="copy-diet-modal">
                <DialogHeader>
                    <DialogTitle>Copiar dieta</DialogTitle>
                    <DialogDescription className="sr-only">Copia esta dieta a otro día</DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        {/* «Copiar dieta del Hoy a:» no es castellano (punto 4.18). La fecha
                            viene con mayúscula porque a veces es «Hoy» o «Mañana»; dentro de
                            la frase va en minúscula, y en los días de la semana también toca. */}
                        Copiar la dieta de{' '}
                        <span className="font-semibold">
                            {currentDateFormatted ? currentDateFormatted.charAt(0).toLowerCase() + currentDateFormatted.slice(1) : ''}
                        </span> a:
                    </p>
                    <Input
                        type="date"
                        value={copyDate}
                        onChange={(e) => setCopyDate(e.target.value)}
                        min={new Date().toLocaleDateString('en-CA')}
                        className="h-12 rounded-xl"
                        data-testid="copy-date-input"
                    />
                    <div className="flex gap-2">
                        <Button variant="outline" className="flex-1 h-12 rounded-full" onClick={onClose}>
                            Cancelar
                        </Button>
                        <Button
                            className="flex-1 h-12 rounded-full bg-black hover:bg-gray-900"
                            onClick={onCopy}
                            data-testid="copy-confirm-btn"
                        >
                            Copiar
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default CopyDietModal;
