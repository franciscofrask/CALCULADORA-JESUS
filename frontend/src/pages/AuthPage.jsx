import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Dumbbell, Mail, Lock, User, Phone, ArrowRight, Loader2 } from 'lucide-react';

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
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1756314354803-be78f7fc5e35?w=1920')] bg-cover bg-center opacity-10"></div>
            
            <div className="relative z-10 w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-primary rounded-2xl mb-4">
                        <Dumbbell className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="heading-1 text-white">12EN12</h1>
                    <p className="text-blue-200 mt-2">Gallego Trainer Internacional</p>
                </div>

                <Card className="card-glass border-white/10">
                    <CardHeader className="text-center pb-2">
                        <CardTitle className="heading-3 text-foreground">
                            {activeTab === 'login' ? 'Iniciar Sesión' : 'Crear Cuenta'}
                        </CardTitle>
                        <CardDescription>
                            {activeTab === 'login' 
                                ? 'Accede a tu portal de entrenamiento' 
                                : 'Únete a la familia 12EN12'}
                        </CardDescription>
                    </CardHeader>
                    
                    <CardContent>
                        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                            <TabsList className="grid w-full grid-cols-2 mb-6">
                                <TabsTrigger value="login" data-testid="login-tab">Entrar</TabsTrigger>
                                <TabsTrigger value="register" data-testid="register-tab">Registrarse</TabsTrigger>
                            </TabsList>
                            
                            <TabsContent value="login">
                                <form onSubmit={handleLogin} className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="login-email">Email</Label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="login-email"
                                                data-testid="login-email"
                                                type="email"
                                                placeholder="tu@email.com"
                                                className="pl-10"
                                                value={loginData.email}
                                                onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="login-password">Contraseña</Label>
                                        <div className="relative">
                                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="login-password"
                                                data-testid="login-password"
                                                type="password"
                                                placeholder="••••••••"
                                                className="pl-10"
                                                value={loginData.password}
                                                onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <Button 
                                        type="submit" 
                                        className="w-full btn-primary"
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
                                        <Label htmlFor="register-name">Nombre completo</Label>
                                        <div className="relative">
                                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="register-name"
                                                data-testid="register-name"
                                                type="text"
                                                placeholder="Tu nombre"
                                                className="pl-10"
                                                value={registerData.name}
                                                onChange={(e) => setRegisterData({ ...registerData, name: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-email">Email</Label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="register-email"
                                                data-testid="register-email"
                                                type="email"
                                                placeholder="tu@email.com"
                                                className="pl-10"
                                                value={registerData.email}
                                                onChange={(e) => setRegisterData({ ...registerData, email: e.target.value })}
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-phone">Teléfono (opcional)</Label>
                                        <div className="relative">
                                            <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="register-phone"
                                                data-testid="register-phone"
                                                type="tel"
                                                placeholder="+34 612 345 678"
                                                className="pl-10"
                                                value={registerData.phone}
                                                onChange={(e) => setRegisterData({ ...registerData, phone: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="register-password">Contraseña</Label>
                                        <div className="relative">
                                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <Input
                                                id="register-password"
                                                data-testid="register-password"
                                                type="password"
                                                placeholder="Mínimo 6 caracteres"
                                                className="pl-10"
                                                value={registerData.password}
                                                onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
                                                required
                                                minLength={6}
                                            />
                                        </div>
                                    </div>
                                    
                                    <Button 
                                        type="submit" 
                                        className="w-full btn-primary"
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
                
                <p className="text-center text-blue-200/60 text-sm mt-6">
                    © 2024 Gallego Trainer Internacional. Todos los derechos reservados.
                </p>
            </div>
        </div>
    );
};

export default AuthPage;
