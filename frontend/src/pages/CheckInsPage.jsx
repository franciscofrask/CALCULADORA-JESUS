import React from 'react';
import { ClipboardList } from 'lucide-react';

const CheckInsPage = () => {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
            <div className="w-16 h-16 rounded-full bg-brand/10 flex items-center justify-center">
                <ClipboardList className="w-8 h-8 text-brand-orange" />
            </div>
            <h2 className="text-xl font-bold text-foreground">Check-ins</h2>
            <p className="text-muted-foreground text-sm max-w-xs">
                Aquí registrarás tu progreso diario, semanal y mensual. Próximamente disponible.
            </p>
        </div>
    );
};

export default CheckInsPage;
