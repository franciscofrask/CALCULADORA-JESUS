import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Mail, Lock, Loader2, Eye, EyeOff } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import { dejarDestino, leerDestino } from '../lib/navegacion';
import { mensajeDeError } from '../lib/mensajeDeError';

// Aquí había una copia del logo hecha a mano, con la flecha colgando por encima del suelo de
// las letras. Se usa el de siempre (14-08-2026): así el logo es uno solo y se arregla en un
// sitio. `tone="dark"` porque esta pantalla es negra siempre, no sigue al tema.

const AuthPage = () => {
    const navigate = useNavigate();
    const { login, register } = useAuth();
    const [loading, setLoading] = useState(false);
    const [isRegister, setIsRegister] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    
    // Solo lo imprescindible para tener cuenta.
    const [formData, setFormData] = useState({ email: '', password: '' });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        
        try {
            if (isRegister) {
                // El que acaba de crear la cuenta no tiene plan: va a elegirlo. Esto ya lo
                // intentaba el navigate de abajo, pero PublicRoute se le adelantaba y le
                // soltaba en el panel (ver lib/navegacion); dejando el destino, manda este.
                // Si viene del test ya hay uno puesto y es el mismo, así que no se pisa.
                if (!leerDestino()) dejarDestino('/planes');
                await register(formData);
                toast.success('¡Cuenta creada! Bienvenido a 12EN12');
                navigate('/onboarding');
            } else {
                const user = await login(formData.email, formData.password);
                toast.success(`¡Bienvenido, ${user.name}!`);
                
                if (user.role === 'admin' || user.role === 'trainer') {
                    navigate('/admin');
                } else {
                    navigate('/dashboard');
                }
            }
        } catch (error) {
            toast.error(mensajeDeError(error, 'Error de autenticación'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-6 relative overflow-hidden">
            {/* Background Image - Gohan Dark */}
            <div 
                className="absolute inset-0 opacity-[0.15]"
                style={{
                    backgroundImage: `url('/gohan-dark.png')`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat'
                }}
            />
            
            {/* Content */}
            <div className="relative z-10 w-full max-w-sm flex flex-col items-center">
                {/* Logo */}
                <div className="mb-10">
                    <Logo12EN12 size="lg" tone="dark" />
                </div>
                
                {/* Title */}
                {/* «Login» era la única palabra en inglés que le quedaba a la app. Y el
                    subtítulo del acceso sobraba: hay dos campos y un botón, se ve solo
                    (Jesús, 11-08). En el registro sí se mantiene, que ahí dice algo. */}
                <h1 className="text-white text-3xl font-bold mb-2 tracking-tight">
                    {isRegister ? 'Registro' : 'Entrar'}
                </h1>
                {isRegister && (
                    <p className="text-white/60 text-sm mb-8">Crea tu cuenta para empezar</p>
                )}
                {!isRegister && <div className="mb-8" />}
                
                {/* Form */}
                <form onSubmit={handleSubmit} className="w-full space-y-4">
                    {/* Ni nombre ni teléfono: crear cuenta es correo y contraseña.
                        Pedirle el teléfono a quien viene a por un dato gratis espanta a
                        la mitad. El nombre se pide después, con algo suyo ya delante, y
                        el teléfono al comprar, que es cuando hace falta llamar. */}

                    <div className="relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand/20 flex items-center justify-center">
                            <Mail className="w-3 h-3 text-brand" />
                        </div>
                        <Input
                            type="email"
                            placeholder="Email"
                            className="pl-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            required
                            data-testid="login-email"
                        />
                    </div>
                    
                    <div className="relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand/20 flex items-center justify-center">
                            <Lock className="w-3 h-3 text-brand" />
                        </div>
                        <Input
                            type={showPassword ? "text" : "password"}
                            placeholder="Contraseña"
                            className="pl-12 pr-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            required
                            minLength={6}
                            data-testid="login-password"
                        />
                        <button
                            type="button"
                            className="absolute right-4 top-1/2 -translate-y-1/2 text-white/40 hover:text-white transition-colors"
                            onClick={() => setShowPassword(!showPassword)}
                            data-testid="toggle-password"
                        >
                            {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                        </button>
                    </div>
                    
                    {/* Este botón existía y lo único que hacía era decirle que escribiera
                        a su entrenador por WhatsApp. Ahora lleva a recuperarla por correo:
                        con el registro abierto hay gente sin entrenador a quien escribir. */}
                    {!isRegister && (
                        <button
                            type="button"
                            className="text-brand text-sm hover:underline w-full text-right"
                            onClick={() => navigate('/recuperar')}
                            data-testid="login-olvidada"
                        >
                            ¿Olvidaste tu contraseña?
                        </button>
                    )}
                    
                    <Button 
                        type="submit" 
                        className="w-full h-14 bg-brand hover:bg-brand-dark text-white font-bold text-lg rounded-full transition-all duration-200 shadow-lg shadow-brand/30"
                        disabled={loading}
                        data-testid="login-submit"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            isRegister ? 'Crear cuenta' : 'Entrar'
                        )}
                    </Button>
                </form>
                
                {/* Toggle */}
                <button
                    type="button"
                    className="mt-6 text-white/60 text-sm hover:text-white transition-colors"
                    onClick={() => setIsRegister(!isRegister)}
                >
                    {isRegister ? (
                        <>¿Ya tienes cuenta? <span className="text-brand font-semibold">Inicia sesión</span></>
                    ) : (
                        <>¿No tienes cuenta? <span className="text-brand font-semibold">Regístrate</span></>
                    )}
                </button>
                
                {/* Footer */}
                <p className="text-white/30 text-xs mt-10 text-center">
                    © 2026 12EN12 Training System
                </p>
            </div>
        </div>
    );
};

export default AuthPage;
