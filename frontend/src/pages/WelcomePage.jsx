import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { Button } from '../components/ui/button';
import { ArrowRight, Compass, Flame } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import BrandArrow from '../components/BrandArrow';

// Pantalla de bienvenida tras completar el cuestionario inicial.
// Le "devuelve" al usuario el resultado de su esfuerzo (sus macros calculados)
// y lo empuja a su primer paso útil: preparar su día de comidas.

const MACRO = { protein: '#FF671F', carbs: '#2196F3', fat: '#FFA500' };

const getP = (m) => m?.protein || m?.proteinas || 0;
const getH = (m) => m?.carbs || m?.hidratos || 0;
const getG = (m) => m?.fat || m?.grasas || 0;
const getKcal = (m) => Math.round(getP(m) * 4 + getH(m) * 4 + getG(m) * 9);

const MacroPill = ({ label, value, color }) => (
    <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-[#222222] bg-card px-4 py-5 flex-1 min-w-[92px]">
        <span className="font-data font-extrabold text-3xl md:text-4xl leading-none" style={{ color }}>{Math.round(value)}</span>
        <span className="text-muted-foreground text-[10px] uppercase font-bold tracking-wider mt-1">g</span>
        <span className="text-xs font-bold uppercase tracking-wide mt-2" style={{ color }}>{label}</span>
    </div>
);

const WelcomePage = () => {
    const navigate = useNavigate();
    const { user, profile } = useAuth();
    const { startTour, skipTour } = useOnboarding();

    const beginTour = () => {
        navigate('/dashboard');
        startTour();
    };

    const exploreSolo = () => {
        skipTour(); // no auto-arrancar el tour en esta carga
        navigate('/dashboard');
    };

    const mt = profile?.macros_training;
    const hasMacros = mt && (getP(mt) > 0);
    const firstName = user?.name?.split(' ')[0] || '';

    return (
        <div className="min-h-screen bg-background relative overflow-hidden flex flex-col" data-testid="welcome-page">
            {/* Glow de marca */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand/10 rounded-full blur-[150px]" />
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-brand/5 rounded-full blur-[120px]" />
            <BrandArrow className="absolute -right-16 -bottom-16 w-[420px] h-[420px] text-brand/[0.04] pointer-events-none" />

            {/* Cabecera */}
            <div className="relative z-10 flex items-center h-16 px-6 md:px-10">
                <Logo12EN12 size="sm" tone="dark" />
            </div>

            <div className="flex-1 flex items-center justify-center p-6 relative z-10">
                <div className="w-full max-w-xl text-center">
                    <p className="caption text-brand mb-2">Todo listo{firstName ? `, ${firstName}` : ''}</p>
                    <h1 className="font-heading font-bold text-4xl md:text-5xl uppercase tracking-tight text-foreground mb-3 leading-none">
                        Tus macros están calculados
                    </h1>
                    <p className="text-muted-foreground mb-8 text-sm md:text-base max-w-md mx-auto">
                        Con tus respuestas armamos tus objetivos personalizados. Estos son tus
                        números para un <span className="text-foreground font-semibold">día de entrenamiento</span>:
                    </p>

                    {hasMacros ? (
                        <>
                            <div className="flex items-center justify-center gap-2 mb-3 text-sm font-bold uppercase tracking-wider" style={{ color: MACRO.protein }}>
                                <Flame className="w-4 h-4" /> {getKcal(mt)} kcal / día
                            </div>
                            <div className="flex gap-3 justify-center mb-10">
                                <MacroPill label="Proteína" value={getP(mt)} color={MACRO.protein} />
                                <MacroPill label="Hidratos" value={getH(mt)} color={MACRO.carbs} />
                                <MacroPill label="Grasa" value={getG(mt)} color={MACRO.fat} />
                            </div>
                        </>
                    ) : (
                        <div className="mb-10 surface p-5 text-sm text-muted-foreground">
                            Estamos terminando de calcular tus macros. Podrás verlos en tu panel en unos instantes.
                        </div>
                    )}

                    <p className="text-muted-foreground mb-5 text-sm">
                        Te hacemos un recorrido rápido por la app para que sepas dónde está
                        cada cosa y cómo preparar tu primer día. Son un par de minutos.
                    </p>

                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <Button onClick={beginTour} data-testid="welcome-start-btn"
                            className="bg-brand hover:bg-brand/90 text-white font-bold uppercase tracking-wider px-8 py-6 text-base">
                            <Compass className="w-5 h-5 mr-2" /> Empezar recorrido guiado
                        </Button>
                        <Button onClick={exploreSolo} variant="ghost"
                            data-testid="welcome-skip-btn"
                            className="text-muted-foreground hover:text-foreground font-semibold px-6 py-6 text-base">
                            Explorar por mi cuenta <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WelcomePage;
