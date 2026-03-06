import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
    Dumbbell, Crown, Star, Zap, Check, ChevronRight, 
    ArrowRight, Loader2
} from 'lucide-react';

const PLANS = [
    {
        id: 'gold',
        name: 'Gold',
        price: 149,
        badge: 'badge-gold',
        description: 'El plan más completo para resultados máximos',
        features: [
            'Rutina personalizada semanal',
            'Macros 100% individualizados',
            'Chat directo con tu entrenador',
            'Reporte quincenal con feedback',
            'Cardio personalizado',
            'Audio motivacional de Jesús',
            'Guía de suplementación'
        ],
        recommended: true
    },
    {
        id: 'silver',
        name: 'Silver',
        price: 99,
        badge: 'badge-silver',
        description: 'Balance perfecto entre servicio y precio',
        features: [
            'Rutina personalizada semanal',
            'Macros individualizados',
            'Chat directo con tu entrenador',
            'Reporte mensual'
        ],
        recommended: false
    },
    {
        id: 'bronze',
        name: 'Bronze',
        price: 69,
        badge: 'badge-bronze',
        description: 'Ideal para empezar tu transformación',
        features: [
            'Rutina básica mensual',
            'Macros calculados',
            'Chat con soporte',
            'Reporte mensual'
        ],
        recommended: false
    },
    {
        id: 'elm',
        name: 'ELM',
        price: 39,
        badge: 'badge-elm',
        description: 'Solo macros, para quienes ya tienen rutina',
        features: [
            'Acceso a calculadora de macros',
            'Macros personalizados',
            'Chat con soporte'
        ],
        recommended: false
    }
];

const OnboardingPage = () => {
    const navigate = useNavigate();
    const { api, refreshProfile } = useAuth();
    const [selectedPlan, setSelectedPlan] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSelectPlan = async () => {
        if (!selectedPlan) {
            toast.error('Selecciona un plan para continuar');
            return;
        }

        setLoading(true);
        try {
            await api.post('/clients/profile', { plan: selectedPlan });
            await refreshProfile();
            toast.success('¡Bienvenido a 12EN12! Tu plan ha sido activado');
            navigate('/dashboard');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al activar el plan');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-4 md:p-8">
            <div className="max-w-4xl mx-auto">
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-primary rounded-2xl mb-4">
                        <Dumbbell className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="heading-1 text-white mb-2">Elige tu plan</h1>
                    <p className="text-blue-200">
                        Selecciona el plan que mejor se adapte a tus objetivos
                    </p>
                </div>

                {/* Plans Grid */}
                <div className="grid md:grid-cols-2 gap-4 mb-8">
                    {PLANS.map((plan) => (
                        <Card 
                            key={plan.id}
                            className={`cursor-pointer transition-all duration-300 ${
                                selectedPlan === plan.id 
                                    ? 'ring-2 ring-primary scale-[1.02]' 
                                    : 'hover:scale-[1.01]'
                            } ${plan.recommended ? 'border-primary/50' : ''}`}
                            onClick={() => setSelectedPlan(plan.id)}
                            data-testid={`plan-${plan.id}`}
                        >
                            <CardHeader className="pb-2">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <span className={plan.badge}>{plan.name}</span>
                                        {plan.recommended && (
                                            <Badge variant="secondary" className="ml-2 text-xs">
                                                <Star className="w-3 h-3 mr-1" />
                                                Recomendado
                                            </Badge>
                                        )}
                                    </div>
                                    {selectedPlan === plan.id && (
                                        <div className="w-6 h-6 bg-primary rounded-full flex items-center justify-center">
                                            <Check className="w-4 h-4 text-white" />
                                        </div>
                                    )}
                                </div>
                                <CardTitle className="mt-3">
                                    <span className="text-4xl font-black">{plan.price}</span>
                                    <span className="text-muted-foreground">€/ciclo</span>
                                </CardTitle>
                                <p className="text-sm text-muted-foreground">{plan.description}</p>
                            </CardHeader>
                            <CardContent>
                                <ul className="space-y-2">
                                    {plan.features.map((feature, index) => (
                                        <li key={index} className="flex items-center gap-2 text-sm">
                                            <Check className="w-4 h-4 text-secondary flex-shrink-0" />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* CTA */}
                <div className="text-center">
                    <Button 
                        className="btn-primary px-8 py-6 text-lg"
                        onClick={handleSelectPlan}
                        disabled={!selectedPlan || loading}
                        data-testid="confirm-plan-btn"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        ) : (
                            <ArrowRight className="w-5 h-5 mr-2" />
                        )}
                        {loading ? 'Activando...' : 'Continuar con el plan'}
                    </Button>
                    <p className="text-blue-200/60 text-sm mt-4">
                        Pago mockeado para demostración
                    </p>
                </div>
            </div>
        </div>
    );
};

export default OnboardingPage;
