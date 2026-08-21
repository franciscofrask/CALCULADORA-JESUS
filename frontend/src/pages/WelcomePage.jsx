import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { ArrowRight, Flame } from 'lucide-react';
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

// UNA FECHA «2026-08-24» ES UN DÍA, NO UN INSTANTE. `new Date('2026-08-24')` la lee como
// medianoche en Londres, y al pintarla en la hora del navegador puede retroceder al día
// anterior: la pantalla decía «lunes 23» con el 24 guardado. Se parte a mano y no se
// convierte nada.
const MESES_DEL_ANO = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
    'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const diaDelMes = (iso) => {
    const [, mes, dia] = String(iso).slice(0, 10).split('-');
    return `${Number(dia)} de ${MESES_DEL_ANO[Number(mes) - 1] || ''}`.trim();
};

const MacroPill = ({ label, value, color }) => (
    <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-[#222222] bg-card px-4 py-5 flex-1 min-w-[92px]">
        <span className="font-data font-extrabold text-3xl md:text-4xl leading-none" style={{ color }}>{Math.round(value)}</span>
        <span className="text-muted-foreground text-[10px] uppercase font-bold tracking-wider mt-1">g</span>
        <span className="text-xs font-bold uppercase tracking-wide mt-2" style={{ color }}>{label}</span>
    </div>
);

const WelcomePage = () => {
    const navigate = useNavigate();
    const { user, profile, api, refreshProfile } = useAuth();

    // LA VUELTA DE LA PASARELA (19-08). El ajuste a medida de 87 € manda aquí con
    // `?ajuste=ok&session_id=...`, y aquí no lo miraba nadie: el cliente pagaba, Stripe
    // cobraba y su ficha se quedaba en «iniciado» -- sin la cola del lunes, sin aviso al
    // equipo y sin abrirle el cuestionario completo. En local no hay webhook que lo salve,
    // y en producción tampoco se puede depender solo de él: por eso existe esta llamada.
    // Comprobado pagando de verdad en el entorno de prueba de Stripe.
    const [avisandoDelPago, setAvisandoDelPago] = React.useState(false);
    React.useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const sesion = params.get('session_id');
        if (!sesion) return;
        setAvisandoDelPago(true);
        api.post('/billing/checkout-session/sync', { session_id: sesion })
            .then(() => refreshProfile && refreshProfile())
            .catch((e) => console.error('[pago] no se pudo confirmar la sesión', e))
            .finally(() => {
                setAvisandoDelPago(false);
                // La dirección se limpia para que recargar no vuelva a lanzar la confirmación.
                window.history.replaceState({}, '', window.location.pathname);
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Al entrar en el Inicio, el recorrido de la primera vez sale solo (doc 21-08,
    // apartado 23): esta pantalla ya no lo ofrece ni lo salta, solo deja pasar.
    const entrar = () => navigate('/dashboard');

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
                <Logo12EN12 size="sm" />
            </div>

            <div className="flex-1 flex items-center justify-center p-6 relative z-10">
                <div className="w-full max-w-xl text-center">
                    {/* Mientras se confirma el pago, que sepa que estamos en ello: si no, ve
                        su pantalla de siempre y no sabe si su dinero ha llegado. */}
                    {avisandoDelPago && (
                        <p className="caption text-brand mb-2" data-testid="confirmando-pago">
                            Confirmando tu pago...
                        </p>
                    )}
                    {!avisandoDelPago && profile?.ajuste_a_medida?.cobrado && (
                        <p className="caption text-brand mb-2" data-testid="ajuste-pagado">
                            Tu ajuste a medida está pagado. Lo preparamos para el lunes
                            {profile.ajuste_a_medida.para_el_lunes
                                ? ` ${diaDelMes(profile.ajuste_a_medida.para_el_lunes)}`
                                : ''}.
                        </p>
                    )}
                    <p className="caption text-brand mb-2">Todo listo{firstName ? `, ${firstName}` : ''}</p>
                    <h1 className="font-heading font-bold text-4xl md:text-5xl uppercase tracking-tight text-foreground mb-3 leading-none">
                        Tus macros están calculados
                    </h1>
                    <p className="text-muted-foreground mb-8 text-sm md:text-base max-w-md mx-auto">
                        {/* «Armamos» así es de Argentina y en España se lee raro; y
                            «personalizados» es palabra de folleto que sobra cuando ya le estás
                            enseñando sus tres números (Jesús, 11-08). */}
                        Con tus respuestas hemos montado tus objetivos. Estos son tus
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

                    <div className="flex justify-center">
                        <Button onClick={entrar} data-testid="welcome-skip-btn"
                            className="bg-brand hover:bg-brand/90 text-white font-bold uppercase tracking-wider px-8 py-6 text-base">
                            Entrar <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WelcomePage;
