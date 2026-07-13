import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Check, ArrowRight, ArrowLeft, Loader2, Star } from 'lucide-react';
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

    // Retorno de Stripe Checkout: ?checkout=success&session_id=...  /  ?checkout=canceled
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const checkout = params.get('checkout');
        if (checkout === 'success') {
            const sessionId = params.get('session_id');
            setLoading(true);
            (async () => {
                try {
                    if (sessionId) {
                        await api.post('/billing/checkout-session/sync', { session_id: sessionId });
                    }
                    await refreshProfile();
                    toast.success('¡Pago confirmado! Tu plan está activo');
                    navigate('/dashboard', { replace: true });
                } catch (error) {
                    toast.error('No pudimos confirmar el pago. Si te cobraron, recarga en unos segundos.');
                    setLoading(false);
                }
            })();
        } else if (checkout === 'canceled') {
            toast.info('Checkout cancelado. Puedes elegir un plan cuando quieras.');
            window.history.replaceState({}, '', '/onboarding');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- correr solo al montar
    }, []);

    const handleSelectPlan = async () => {
        if (!selectedPlan) {
            toast.error('Selecciona un plan para continuar');
            return;
        }

        setLoading(true);
        try {
            const res = await api.post('/billing/checkout-session', { plan: selectedPlan });
            // Redirige a la página de pago de Stripe (test mode).
            window.location.href = res.data.checkout_url;
        } catch (error) {
            // Los errores de configuración del servidor (5xx) no se enseñan en crudo al usuario
            const status = error.response?.status || 0;
            const detail = error.response?.data?.detail;
            toast.error(status >= 500 || !detail ? 'No se pudo iniciar el pago. Inténtalo en un momento.' : detail);
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background p-4 md:p-8 relative overflow-hidden">
            {/* Background glow */}
            <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#FF671F]/10 rounded-full blur-[150px]"></div>
            <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[#FF671F]/5 rounded-full blur-[120px]"></div>
            
            <div className="max-w-5xl mx-auto relative z-10">
                {/* Volver */}
                <button onClick={() => navigate('/dashboard')}
                    className="inline-flex items-center gap-1.5 text-foreground/60 hover:text-foreground text-sm mb-6 transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Volver
                </button>
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
                        {loading ? 'Redirigiendo...' : 'Ir a pagar'}
                    </Button>
                    <p className="text-foreground/30 text-sm mt-4 uppercase tracking-wider">
                        Pago seguro con Stripe · Modo prueba
                    </p>
                </div>
            </div>
        </div>
    );
};

export default OnboardingPage;
