import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Check, ArrowRight, Loader2, Star } from 'lucide-react';
import BrandArrow from '../components/BrandArrow';

const PLANS = [
    {
        id: 'gold',
        name: 'Gold',
        price: 149,
        badgeClass: 'bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-600 text-foreground',
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
        badgeClass: 'bg-gradient-to-r from-gray-300 via-gray-200 to-gray-400 text-foreground',
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
        badgeClass: 'bg-gradient-to-r from-orange-700 via-orange-600 to-orange-800 text-white',
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
        badgeClass: 'bg-[#FF671F] text-white',
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
            toast.success('¡Bienvenido a JG12! Tu plan ha sido activado');
            navigate('/dashboard');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al activar el plan');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background p-4 md:p-8 relative overflow-hidden">
            {/* Background glow */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#FF671F]/10 rounded-full blur-[150px]"></div>
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[#FF671F]/5 rounded-full blur-[120px]"></div>
            
            <div className="max-w-5xl mx-auto relative z-10">
                {/* Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center text-5xl mb-4" style={{ fontFamily: 'Barlow Condensed' }}>
                        <span className="text-foreground">JG</span>
                        <span className="text-foreground">12</span>
                        <BrandArrow className="text-[#FF671F] h-[1em] w-[1em] -ml-0.5" />
                    </div>
                    <h1 className="heading-1 text-foreground mb-2">ELIGE TU PLAN</h1>
                    <p className="text-foreground/60 uppercase tracking-wider text-sm">
                        Selecciona el plan que mejor se adapte a tus objetivos
                    </p>
                </div>

                {/* Plans Grid */}
                <div className="grid md:grid-cols-2 gap-4 mb-8">
                    {PLANS.map((plan) => (
                        <Card 
                            key={plan.id}
                            className={`bg-card border-2 cursor-pointer transition-all duration-300 ${
                                selectedPlan === plan.id 
                                    ? 'border-[#FF671F] scale-[1.02]' 
                                    : 'border-[#222222] hover:border-white/30'
                            } ${plan.recommended ? 'ring-1 ring-[#FF671F]/30' : ''}`}
                            onClick={() => setSelectedPlan(plan.id)}
                            data-testid={`plan-${plan.id}`}
                        >
                            <CardHeader className="pb-3">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <span className={`${plan.badgeClass} font-bold px-3 py-1 rounded text-sm uppercase tracking-wider`}>
                                            {plan.name}
                                        </span>
                                        {plan.recommended && (
                                            <Badge className="ml-2 bg-[#FF671F]/20 text-[#FF671F] border-0 text-xs">
                                                <Star className="w-3 h-3 mr-1 fill-[#FF671F]" />
                                                Recomendado
                                            </Badge>
                                        )}
                                    </div>
                                    {selectedPlan === plan.id && (
                                        <div className="w-6 h-6 bg-[#FF671F] rounded flex items-center justify-center">
                                            <Check className="w-4 h-4 text-foreground" />
                                        </div>
                                    )}
                                </div>
                                <CardTitle className="mt-4">
                                    <span className="text-5xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {plan.price}
                                    </span>
                                    <span className="text-foreground/50 text-lg ml-1">€/ciclo</span>
                                </CardTitle>
                                <p className="text-sm text-foreground/50">{plan.description}</p>
                            </CardHeader>
                            <CardContent>
                                <ul className="space-y-2">
                                    {plan.features.map((feature, index) => (
                                        <li key={index} className="flex items-center gap-2 text-sm text-foreground/80">
                                            <div className="w-5 h-5 bg-[#FF671F]/20 rounded flex items-center justify-center flex-shrink-0">
                                                <Check className="w-3 h-3 text-[#FF671F]" />
                                            </div>
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
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider px-10 py-6 text-lg"
                        onClick={handleSelectPlan}
                        disabled={!selectedPlan || loading}
                        data-testid="confirm-plan-btn"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        ) : (
                            <ArrowRight className="w-5 h-5 mr-2" />
                        )}
                        {loading ? 'Activando...' : 'Continuar'}
                    </Button>
                    <p className="text-foreground/30 text-sm mt-4 uppercase tracking-wider">
                        Pago simulado para demostración
                    </p>
                </div>
            </div>
        </div>
    );
};

export default OnboardingPage;
