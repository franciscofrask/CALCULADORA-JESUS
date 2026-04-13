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
                    <p className="text-sm text-gray-600">
                        Copiar dieta del <span className="font-semibold">{currentDateFormatted}</span> a:
                    </p>
                    <Input
                        type="date"
                        value={copyDate}
                        onChange={(e) => setCopyDate(e.target.value)}
                        min={new Date().toISOString().split('T')[0]}
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
