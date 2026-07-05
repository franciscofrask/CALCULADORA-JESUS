import React from 'react';
import { Button } from '../ui/button';
import { X, CalendarDays, Utensils, Gauge, ArrowRight } from 'lucide-react';

// Intro de primera visita a la calculadora de nutrición.
// Explica en 3 pasos qué hacer, para que el usuario no se pierda entre
// tantas opciones. Se muestra una sola vez (flag en localStorage).

const STEPS = [
    {
        icon: CalendarDays,
        title: 'Elige el día',
        desc: 'Marca si es día de entrenamiento o de descanso. Tus macros se ajustan solos a cada tipo de día.',
    },
    {
        icon: Utensils,
        title: 'Prepara tus comidas',
        desc: 'Toca una comida y añade alimentos, o usa "Construir comida" para que la calculadora te guíe paso a paso.',
    },
    {
        icon: Gauge,
        title: 'Sigue tus macros',
        desc: 'Arriba ves cuánta proteína, hidratos y grasa llevas. El objetivo es completar el día sin pasarte.',
    },
];

const NutritionIntro = ({ onClose }) => (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="nutrition-intro">
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={onClose} />
        <div className="relative bg-card rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto animate-slide-up">
            <button onClick={onClose} data-testid="close-intro-btn"
                className="absolute top-3 right-3 w-9 h-9 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                <X className="w-5 h-5" />
            </button>

            <div className="p-6 pb-4 text-center">
                <p className="caption text-brand mb-1">Cómo funciona</p>
                <h2 className="font-heading text-2xl font-bold uppercase text-foreground leading-tight">
                    Prepara tu día en 3 pasos
                </h2>
                <p className="text-muted-foreground text-sm mt-2">
                    No hace falta tocar todo. Con esto te basta para empezar.
                </p>
            </div>

            <div className="px-6 space-y-3">
                {STEPS.map((s, i) => (
                    <div key={s.title} className="flex items-start gap-3 rounded-xl bg-muted/50 p-3.5">
                        <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center flex-shrink-0 relative">
                            <s.icon className="w-5 h-5 text-brand" />
                            <span className="absolute -top-1.5 -left-1.5 w-5 h-5 rounded-full bg-brand text-white text-[11px] font-bold flex items-center justify-center">{i + 1}</span>
                        </div>
                        <div className="min-w-0">
                            <p className="font-bold text-foreground text-sm">{s.title}</p>
                            <p className="text-muted-foreground text-xs mt-0.5 leading-relaxed">{s.desc}</p>
                        </div>
                    </div>
                ))}
            </div>

            <div className="p-6 pt-5">
                <Button onClick={onClose} data-testid="start-intro-btn"
                    className="w-full h-12 rounded-full bg-brand hover:bg-brand/90 text-white font-bold uppercase tracking-wider">
                    Empezar <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
            </div>
        </div>
    </div>
);

export default NutritionIntro;
