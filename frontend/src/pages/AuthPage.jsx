import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Mail, Lock, User, Phone, ArrowRight, Loader2, ArrowUpRight } from 'lucide-react';

// JG12 Logo Component
const JG12Logo = ({ size = 'lg' }) => {
    const sizeClasses = {
        sm: 'text-2xl',
        md: 'text-3xl',
        lg: 'text-5xl',
        xl: 'text-6xl'
    };
    
    return (
        <div className={`jg-logo ${sizeClasses[size]} flex items-center`}>
            <span className="text-white">JG</span>
            <span className="text-white">12</span>
            <ArrowUpRight className={`text-[#FF671F] ${size === 'lg' ? 'w-10 h-10' : size === 'xl' ? 'w-12 h-12' : 'w-6 h-6'} -ml-1`} strokeWidth={3} />
        </div>
    );
};

const AuthPage = () => {
    const navigate = useNavigate();
    const { login, register } = useAuth();
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('login');
    
    const [loginData, setLoginData] = useState({ email: '', password: '' });
    const [registerData, setRegisterData] = useState({ 
        email: '', 
        password: '', 
        name: '', 
        phone: '' 
    });

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        
        try {
            const user = await login(loginData.email, loginData.password);
            toast.success(`¡Bienvenido, ${user.name}!`);
            
            if (user.role === 'admin' || user.role === 'operations') {
                navigate('/admin');
            } else if (user.role === 'trainer') {
                navigate('/trainer');
            } else {
                navigate('/dashboard');
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al iniciar sesión');
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setLoading(true);
        
        try {
            const user = await register(registerData);
            toast.success('¡Cuenta creada! Bienvenido a 12EN12');
            navigate('/onboarding');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Error al crear cuenta');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Image */}
            <div 
                className="absolute inset-0 bg-cover bg-center opacity-20"
                style={{
                    backgroundImage: `url('https://customer-assets.emergentagent.com/job_language-12/artifacts/jo19y7tj_IMG_5755.jpg')`
                }}
            ></div>
            
            {/* Gradient Overlay */}
            <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/80 to-black"></div>
            
            {/* Orange accent glow */}
            <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-[#FF671F]/20 rounded-full blur-[120px]"></div>
            
            <div className="relative z-10 w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <JG12Logo size="lg" />
                    <p className="text-white/60 mt-2 uppercase tracking-[0.3em] text-sm">Training System</p>
                </div>

                <Card className="bg-[#111111]/90 backdrop-blur-xl border-white/10">
                    <CardHeader className="text-center pb-2">
                        <CardTitle className="heading-3 text-white">
                            {activeTab === 'login' ? 'INICIAR SESIÓN' : 'CREAR CUENTA'}
                        </CardTitle>
                        <CardDescription className="text-white/50">
                            {activeTab === 'login' 
                                ? 'Accede a tu portal de entrenamiento' 
                                : 'Únete al sistema 12EN12'}
                        </CardDescription>
                    </CardHeader>
                    
                    <CardContent>
                        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                            <TabsList className="grid w-full grid-cols-2 mb-6 bg-[#1A1A1A]">
                                <TabsTrigger 
                                    value="login" 
                                    data-testid="login-tab"
                                    className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider font-bold"
                                >
                                    Entrar
                                </TabsTrigger>
                                <TabsTrigger 
                                    value="register" 
                                    data-testid="register-tab"
                                    className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider font-bold"
                                >
                                    Registro
                                </TabsTrigger>
                            </TabsList>
                            
                            <TabsContent value="login">
                                <form onSubmit={handleLogin} className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="login-email" className="text-white/80">Email</Label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="login-email"
                                                data-testid="login-email"
                                                type="email"
                                                placeholder="tu@email.com"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={loginData.email}
                                                onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="login-password" className="text-white/80">Contraseña</Label>
                                        <div className="relative">
                                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="login-password"
                                                data-testid="login-password"
                                                type="password"
                                                placeholder="••••••••"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={loginData.password}
                                                onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <Button 
                                        type="submit" 
                                        className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider py-6"
                                        disabled={loading}
                                        data-testid="login-submit"
                                    >
                                        {loading ? (
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                        ) : (
                                            <ArrowRight className="w-4 h-4 mr-2" />
                                        )}
                                        Entrar
                                    </Button>
                                </form>
                            </TabsContent>
                            
                            <TabsContent value="register">
                                <form onSubmit={handleRegister} className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="register-name" className="text-white/80">Nombre completo</Label>
                                        <div className="relative">
                                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="register-name"
                                                data-testid="register-name"
                                                type="text"
                                                placeholder="Tu nombre"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={registerData.name}
                                                onChange={(e) => setRegisterData({ ...registerData, name: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-email" className="text-white/80">Email</Label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="register-email"
                                                data-testid="register-email"
                                                type="email"
                                                placeholder="tu@email.com"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={registerData.email}
                                                onChange={(e) => setRegisterData({ ...registerData, email: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-phone" className="text-white/80">Teléfono (opcional)</Label>
                                        <div className="relative">
                                            <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="register-phone"
                                                data-testid="register-phone"
                                                type="tel"
                                                placeholder="+34 612 345 678"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={registerData.phone}
                                                onChange={(e) => setRegisterData({ ...registerData, phone: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-password" className="text-white/80">Contraseña</Label>
                                        <div className="relative">
                                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                                            <Input
                                                id="register-password"
                                                data-testid="register-password"
                                                type="password"
                                                placeholder="Mínimo 6 caracteres"
                                                className="pl-10 bg-[#1A1A1A] border-white/10 text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                                value={registerData.password}
                                                onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
                                                required
                                                minLength={6}
                                            />
                                        </div>
                                    </div>
                                    
                                    <Button 
                                        type="submit" 
                                        className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider py-6"
                                        disabled={loading}
                                        data-testid="register-submit"
                                    >
                                        {loading ? (
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                        ) : (
                                            <ArrowRight className="w-4 h-4 mr-2" />
                                        )}
                                        Crear cuenta
                                    </Button>
                                </form>
                            </TabsContent>
                        </Tabs>
                    </CardContent>
                </Card>
                
                <p className="text-center text-white/30 text-sm mt-6 uppercase tracking-wider">
                    © 2024 Jesús Gallego Personal Trainer
                </p>
            </div>
        </div>
    );
};

export default AuthPage;
