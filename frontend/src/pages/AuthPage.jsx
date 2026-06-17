import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Mail, Lock, Loader2, Eye, EyeOff } from 'lucide-react';
import BrandArrow from '../components/BrandArrow';

// 12EN12 Logo Component
const Logo12EN12 = ({ size = 'lg' }) => {
    const sizeClasses = {
        sm: 'text-2xl',
        md: 'text-3xl',
        lg: 'text-5xl',
        xl: 'text-6xl'
    };
    const arrowSizes = {
        sm: 'w-5 h-5',
        md: 'w-7 h-7',
        lg: 'w-10 h-10',
        xl: 'w-12 h-12'
    };
    
    return (
        <div className={`flex items-center justify-center ${sizeClasses[size]} font-bold tracking-tight`}>
            <span className="text-white">12</span>
            <span className="text-white">EN</span>
            <span className="text-white">12</span>
            <BrandArrow className="text-brand-orange h-[1em] w-[1em] -ml-0.5" />
        </div>
    );
};

const AuthPage = () => {
    const navigate = useNavigate();
    const { login, register } = useAuth();
    const [loading, setLoading] = useState(false);
    const [isRegister, setIsRegister] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    
    const [formData, setFormData] = useState({ 
        email: '', 
        password: '',
        name: '',
        phone: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        
        try {
            if (isRegister) {
                await register(formData);
                toast.success('¡Cuenta creada! Bienvenido a 12EN12');
                navigate('/onboarding');
            } else {
                const user = await login(formData.email, formData.password);
                toast.success(`¡Bienvenido, ${user.name}!`);
                
                if (user.role === 'admin' || user.role === 'operations') {
                    navigate('/admin');
                } else if (user.role === 'trainer') {
                    navigate('/trainer');
                } else {
                    navigate('/dashboard');
                }
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error de autenticación');
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
                    <Logo12EN12 size="lg" />
                </div>
                
                {/* Title */}
                <h1 className="text-white text-3xl font-bold mb-2 tracking-tight">
                    {isRegister ? 'Registro' : 'Login'}
                </h1>
                <p className="text-white/60 text-sm mb-8">
                    {isRegister ? 'Crea tu cuenta para empezar' : 'Completa tus datos para acceder'}
                </p>
                
                {/* Form */}
                <form onSubmit={handleSubmit} className="w-full space-y-4">
                    {isRegister && (
                        <div className="relative">
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand-orange/20 flex items-center justify-center">
                                <span className="text-brand-orange text-xs">👤</span>
                            </div>
                            <Input
                                type="text"
                                placeholder="Nombre completo"
                                className="pl-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand-orange"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                required={isRegister}
                                data-testid="register-name"
                            />
                        </div>
                    )}
                    
                    <div className="relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand-orange/20 flex items-center justify-center">
                            <Mail className="w-3 h-3 text-brand-orange" />
                        </div>
                        <Input
                            type="email"
                            placeholder="Email"
                            className="pl-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand-orange"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            required
                            data-testid="login-email"
                        />
                    </div>
                    
                    <div className="relative">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand-orange/20 flex items-center justify-center">
                            <Lock className="w-3 h-3 text-brand-orange" />
                        </div>
                        <Input
                            type={showPassword ? "text" : "password"}
                            placeholder="Contraseña"
                            className="pl-12 pr-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand-orange"
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
                    
                    {!isRegister && (
                        <button 
                            type="button"
                            className="text-brand-orange text-sm hover:underline w-full text-right"
                            onClick={() => toast.info('Contacta al administrador para recuperar tu contraseña')}
                        >
                            ¿Olvidaste tu contraseña?
                        </button>
                    )}
                    
                    <Button 
                        type="submit" 
                        className="w-full h-14 bg-brand-orange hover:bg-brand-orange-dark text-white font-bold text-lg rounded-full transition-all duration-200 shadow-lg shadow-brand-orange/30"
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
                        <>¿Ya tienes cuenta? <span className="text-brand-orange font-semibold">Inicia sesión</span></>
                    ) : (
                        <>¿No tienes cuenta? <span className="text-brand-orange font-semibold">Regístrate</span></>
                    )}
                </button>
                
                {/* Footer */}
                <p className="text-white/30 text-xs mt-10 text-center">
                    © 2026 Jesús Gallego · 12EN12 Training System
                </p>
            </div>
        </div>
    );
};

export default AuthPage;
