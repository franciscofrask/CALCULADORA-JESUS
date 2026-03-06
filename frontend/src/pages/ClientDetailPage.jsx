import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { PlanBadge } from './ClientDashboard';
import { 
    ArrowLeft, User, Mail, Phone, Calendar, 
    CreditCard, Dumbbell, Apple, FileText, MessageCircle,
    Edit2, Save, Scale, Ruler, Target, Zap, Send, Loader2
} from 'lucide-react';

const ClientDetailPage = () => {
    const { clientId } = useParams();
    const navigate = useNavigate();
    const { api } = useAuth();
    const [client, setClient] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('resumen');
    const [editing, setEditing] = useState(false);
    const [generatingRoutine, setGeneratingRoutine] = useState(false);
    const [routineInstructions, setRoutineInstructions] = useState('');
    const [generatedRoutine, setGeneratedRoutine] = useState(null);
    
    const [macrosForm, setMacrosForm] = useState({
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        note: ''
    });

    useEffect(() => {
        fetchClient();
    }, [clientId]);

    const fetchClient = async () => {
        try {
            const response = await api.get(`/admin/clients/${clientId}`);
            setClient(response.data);
            
            // Set macros form with current values
            if (response.data.profile?.macros_training) {
                setMacrosForm({
                    training: {
                        protein: response.data.profile.macros_training.protein || '',
                        carbs: response.data.profile.macros_training.carbs || '',
                        fat: response.data.profile.macros_training.fat || ''
                    },
                    rest: {
                        protein: response.data.profile.macros_rest?.protein || '',
                        carbs: response.data.profile.macros_rest?.carbs || '',
                        fat: response.data.profile.macros_rest?.fat || ''
                    },
                    note: ''
                });
            }
        } catch (error) {
            console.error('Error fetching client:', error);
            toast.error('Error al cargar datos del cliente');
            navigate('/admin/clients');
        } finally {
            setLoading(false);
        }
    };

    const handleSaveMacros = async () => {
        try {
            await api.put(`/admin/clients/${clientId}/macros`, {
                training: {
                    protein: parseFloat(macrosForm.training.protein),
                    carbs: parseFloat(macrosForm.training.carbs),
                    fat: parseFloat(macrosForm.training.fat)
                },
                rest: {
                    protein: parseFloat(macrosForm.rest.protein),
                    carbs: parseFloat(macrosForm.rest.carbs),
                    fat: parseFloat(macrosForm.rest.fat)
                },
                note: macrosForm.note
            });
            toast.success('Macros actualizados correctamente');
            fetchClient();
        } catch (error) {
            toast.error('Error al actualizar macros');
        }
    };

    const handleGenerateRoutine = async () => {
        setGeneratingRoutine(true);
        try {
            const response = await api.post('/admin/routines/generate', {
                client_id: clientId,
                instructions: routineInstructions
            });
            setGeneratedRoutine(response.data.routine);
            toast.success('Rutina generada con IA');
        } catch (error) {
            toast.error('Error al generar rutina');
        } finally {
            setGeneratingRoutine(false);
        }
    };

    const handleSaveRoutine = async () => {
        if (!generatedRoutine) return;
        
        try {
            await api.post(`/admin/routines/save?client_id=${clientId}`, generatedRoutine);
            toast.success('Rutina guardada y enviada al cliente');
            setGeneratedRoutine(null);
            setRoutineInstructions('');
            fetchClient();
        } catch (error) {
            toast.error('Error al guardar rutina');
        }
    };

    if (loading) {
        return (
            <div className="p-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/4"></div>
                    <div className="h-48 bg-muted rounded"></div>
                </div>
            </div>
        );
    }

    if (!client) {
        return (
            <div className="p-6 text-center">
                <p className="text-muted-foreground">Cliente no encontrado</p>
            </div>
        );
    }

    const { profile, user, routines, reports, payments, messages } = client;

    return (
        <div className="p-6 space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => navigate('/admin/clients')}>
                    <ArrowLeft className="w-5 h-5" />
                </Button>
                <div className="flex-1">
                    <div className="flex items-center gap-3">
                        <h1 className="heading-2">{user?.name}</h1>
                        <PlanBadge plan={profile?.plan} />
                        <Badge variant={profile?.status === 'activo' ? 'default' : 'secondary'}>
                            {profile?.status}
                        </Badge>
                    </div>
                    <p className="text-muted-foreground">{user?.email}</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline">
                        <MessageCircle className="w-4 h-4 mr-2" />
                        Mensaje
                    </Button>
                    <Button>
                        <Dumbbell className="w-4 h-4 mr-2" />
                        Nueva Rutina
                    </Button>
                </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-6">
                    <TabsTrigger value="resumen" data-testid="tab-resumen">Resumen</TabsTrigger>
                    <TabsTrigger value="pagos" data-testid="tab-pagos">Pagos</TabsTrigger>
                    <TabsTrigger value="nutricion" data-testid="tab-nutricion">Nutrición</TabsTrigger>
                    <TabsTrigger value="reportes" data-testid="tab-reportes">Reportes</TabsTrigger>
                    <TabsTrigger value="rutinas" data-testid="tab-rutinas">Rutinas</TabsTrigger>
                    <TabsTrigger value="mensajes" data-testid="tab-mensajes">Mensajes</TabsTrigger>
                </TabsList>

                {/* Resumen Tab */}
                <TabsContent value="resumen" className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {/* Personal Info */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <User className="w-5 h-5" />
                                    Datos Personales
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex items-center gap-2">
                                    <Mail className="w-4 h-4 text-muted-foreground" />
                                    <span className="text-sm">{user?.email}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Phone className="w-4 h-4 text-muted-foreground" />
                                    <span className="text-sm">{user?.phone || 'No registrado'}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Calendar className="w-4 h-4 text-muted-foreground" />
                                    <span className="text-sm">
                                        Cliente desde {new Date(profile?.created_at).toLocaleDateString('es-ES')}
                                    </span>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Status */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Target className="w-5 h-5" />
                                    Estado
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Semana</span>
                                    <Badge variant="outline">Semana {profile?.week}</Badge>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Precio</span>
                                    <span className="font-bold">{profile?.price}€</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Próx. pago</span>
                                    <span>{profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES') : 'N/A'}</span>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Physical Data */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Scale className="w-5 h-5" />
                                    Datos Físicos
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Peso</span>
                                    <span className="font-bold">{profile?.weight || '--'} kg</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Altura</span>
                                    <span>{profile?.height || '--'} cm</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Objetivo</span>
                                    <span className="capitalize">{profile?.goal || 'No definido'}</span>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Current Macros */}
                    {profile?.macros_training && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Apple className="w-5 h-5" />
                                    Macros Actuales
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-4 bg-muted/50 rounded-lg">
                                        <p className="text-sm font-semibold mb-2">Día Entrenamiento</p>
                                        <div className="grid grid-cols-3 gap-2 text-center">
                                            <div>
                                                <p className="text-2xl font-bold text-red-500">{Math.round(profile.macros_training.protein)}</p>
                                                <p className="text-xs text-muted-foreground">Proteína</p>
                                            </div>
                                            <div>
                                                <p className="text-2xl font-bold text-amber-500">{Math.round(profile.macros_training.carbs)}</p>
                                                <p className="text-xs text-muted-foreground">Carbos</p>
                                            </div>
                                            <div>
                                                <p className="text-2xl font-bold text-blue-500">{Math.round(profile.macros_training.fat)}</p>
                                                <p className="text-xs text-muted-foreground">Grasas</p>
                                            </div>
                                        </div>
                                        <p className="text-center mt-2 font-semibold">{Math.round(profile.macros_training.calories)} kcal</p>
                                    </div>
                                    <div className="p-4 bg-muted/50 rounded-lg">
                                        <p className="text-sm font-semibold mb-2">Día Descanso</p>
                                        <div className="grid grid-cols-3 gap-2 text-center">
                                            <div>
                                                <p className="text-2xl font-bold text-red-500">{Math.round(profile.macros_rest?.protein || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Proteína</p>
                                            </div>
                                            <div>
                                                <p className="text-2xl font-bold text-amber-500">{Math.round(profile.macros_rest?.carbs || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Carbos</p>
                                            </div>
                                            <div>
                                                <p className="text-2xl font-bold text-blue-500">{Math.round(profile.macros_rest?.fat || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Grasas</p>
                                            </div>
                                        </div>
                                        <p className="text-center mt-2 font-semibold">{Math.round(profile.macros_rest?.calories || 0)} kcal</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Pagos Tab */}
                <TabsContent value="pagos">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Historial de Pagos</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {payments?.length > 0 ? (
                                <div className="space-y-3">
                                    {payments.map((payment) => (
                                        <div key={payment.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                                            <div>
                                                <p className="font-semibold">{payment.amount}€</p>
                                                <p className="text-sm text-muted-foreground">
                                                    {new Date(payment.created_at).toLocaleDateString('es-ES')}
                                                </p>
                                            </div>
                                            <Badge variant={payment.status === 'success' ? 'default' : 'destructive'}>
                                                {payment.status === 'success' ? 'Exitoso' : 'Fallido'}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">Sin pagos registrados</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Nutrición Tab */}
                <TabsContent value="nutricion">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Asignar Macros</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Training Day */}
                                <div className="space-y-4">
                                    <h4 className="font-semibold">Día Entrenamiento</h4>
                                    <div className="grid grid-cols-3 gap-3">
                                        <div>
                                            <Label>Proteína (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.training.protein}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    training: { ...macrosForm.training, protein: e.target.value }
                                                })}
                                                data-testid="training-protein"
                                            />
                                        </div>
                                        <div>
                                            <Label>Carbos (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.training.carbs}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    training: { ...macrosForm.training, carbs: e.target.value }
                                                })}
                                            />
                                        </div>
                                        <div>
                                            <Label>Grasas (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.training.fat}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    training: { ...macrosForm.training, fat: e.target.value }
                                                })}
                                            />
                                        </div>
                                    </div>
                                </div>

                                {/* Rest Day */}
                                <div className="space-y-4">
                                    <h4 className="font-semibold">Día Descanso</h4>
                                    <div className="grid grid-cols-3 gap-3">
                                        <div>
                                            <Label>Proteína (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.rest.protein}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    rest: { ...macrosForm.rest, protein: e.target.value }
                                                })}
                                            />
                                        </div>
                                        <div>
                                            <Label>Carbos (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.rest.carbs}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    rest: { ...macrosForm.rest, carbs: e.target.value }
                                                })}
                                            />
                                        </div>
                                        <div>
                                            <Label>Grasas (g)</Label>
                                            <Input
                                                type="number"
                                                value={macrosForm.rest.fat}
                                                onChange={(e) => setMacrosForm({
                                                    ...macrosForm,
                                                    rest: { ...macrosForm.rest, fat: e.target.value }
                                                })}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <Label>Nota para el cliente (opcional)</Label>
                                <Textarea
                                    value={macrosForm.note}
                                    onChange={(e) => setMacrosForm({ ...macrosForm, note: e.target.value })}
                                    placeholder="Instrucciones o comentarios sobre los nuevos macros..."
                                />
                            </div>

                            <Button onClick={handleSaveMacros} data-testid="save-macros-btn">
                                <Save className="w-4 h-4 mr-2" />
                                Guardar Macros
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Reportes Tab */}
                <TabsContent value="reportes">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Historial de Reportes</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {reports?.length > 0 ? (
                                <div className="space-y-4">
                                    {reports.map((report) => (
                                        <Card key={report.id} className="bg-muted/30">
                                            <CardContent className="p-4">
                                                <div className="flex items-start justify-between mb-3">
                                                    <div>
                                                        <p className="font-semibold">
                                                            {new Date(report.created_at).toLocaleDateString('es-ES', {
                                                                day: 'numeric', month: 'long', year: 'numeric'
                                                            })}
                                                        </p>
                                                        <p className="text-2xl font-bold text-primary">{report.weight} kg</p>
                                                    </div>
                                                </div>
                                                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                                                    <div className="bg-background p-2 rounded">
                                                        <span className="text-muted-foreground">Entreno:</span>
                                                        <span className="font-semibold ml-1">{report.training_compliance}%</span>
                                                    </div>
                                                    <div className="bg-background p-2 rounded">
                                                        <span className="text-muted-foreground">Nutrición:</span>
                                                        <span className="font-semibold ml-1">{report.nutrition_compliance}%</span>
                                                    </div>
                                                    <div className="bg-background p-2 rounded">
                                                        <span className="text-muted-foreground">Sueño:</span>
                                                        <span className="font-semibold ml-1">{report.sleep_quality}/10</span>
                                                    </div>
                                                    <div className="bg-background p-2 rounded">
                                                        <span className="text-muted-foreground">Energía:</span>
                                                        <span className="font-semibold ml-1">{report.energy_level}/10</span>
                                                    </div>
                                                </div>
                                                {report.notes && (
                                                    <p className="mt-3 text-sm text-muted-foreground">{report.notes}</p>
                                                )}
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">Sin reportes</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Rutinas Tab */}
                <TabsContent value="rutinas" className="space-y-4">
                    {/* Generate Routine */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Zap className="w-5 h-5 text-primary" />
                                Generar Rutina con IA
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div>
                                <Label>Instrucciones para la IA</Label>
                                <Textarea
                                    value={routineInstructions}
                                    onChange={(e) => setRoutineInstructions(e.target.value)}
                                    placeholder="Ej: Enfocarse en hipertrofia de tren superior, tiene molestias en rodilla derecha..."
                                    rows={3}
                                    data-testid="routine-instructions"
                                />
                            </div>
                            <Button 
                                onClick={handleGenerateRoutine} 
                                disabled={generatingRoutine}
                                data-testid="generate-routine-btn"
                            >
                                {generatingRoutine ? (
                                    <>
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        Generando con IA...
                                    </>
                                ) : (
                                    <>
                                        <Zap className="w-4 h-4 mr-2" />
                                        Generar Rutina
                                    </>
                                )}
                            </Button>

                            {/* Generated Routine Preview */}
                            {generatedRoutine && (
                                <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                                    <h4 className="font-semibold mb-3">Rutina Generada</h4>
                                    <ScrollArea className="h-64">
                                        {generatedRoutine.days?.map((day, index) => (
                                            <div key={index} className="mb-4">
                                                <p className="font-semibold">{day.day}</p>
                                                {day.is_rest ? (
                                                    <p className="text-sm text-muted-foreground">Día de descanso</p>
                                                ) : (
                                                    <ul className="text-sm space-y-1">
                                                        {day.exercises?.map((ex, i) => (
                                                            <li key={i}>• {ex.name}: {ex.sets}x{ex.reps} ({ex.rest})</li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>
                                        ))}
                                    </ScrollArea>
                                    <div className="flex gap-2 mt-4">
                                        <Button onClick={handleSaveRoutine} data-testid="save-routine-btn">
                                            <Save className="w-4 h-4 mr-2" />
                                            Guardar y Enviar
                                        </Button>
                                        <Button variant="outline" onClick={() => setGeneratedRoutine(null)}>
                                            Descartar
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Routine History */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Historial de Rutinas</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {routines?.length > 0 ? (
                                <div className="space-y-3">
                                    {routines.map((routine) => (
                                        <div key={routine.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                                            <div>
                                                <p className="font-semibold">
                                                    {new Date(routine.created_at).toLocaleDateString('es-ES')}
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {routine.days?.filter(d => !d.is_rest).length || 0} días de entreno
                                                </p>
                                            </div>
                                            <Badge variant={routine.status === 'active' ? 'default' : 'secondary'}>
                                                {routine.status === 'active' ? 'Activa' : 'Anterior'}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">Sin rutinas anteriores</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Mensajes Tab */}
                <TabsContent value="mensajes">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Comunicaciones</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {messages?.length > 0 ? (
                                <ScrollArea className="h-64">
                                    <div className="space-y-3">
                                        {messages.map((msg) => (
                                            <div 
                                                key={msg.id} 
                                                className={`p-3 rounded-lg ${
                                                    msg.sender_id === profile?.user_id 
                                                        ? 'bg-muted/50 ml-8' 
                                                        : 'bg-primary/10 mr-8'
                                                }`}
                                            >
                                                <p className="text-sm">{msg.content}</p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {new Date(msg.created_at).toLocaleString('es-ES')}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </ScrollArea>
                            ) : (
                                <p className="text-center text-muted-foreground py-8">Sin mensajes</p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ClientDetailPage;
