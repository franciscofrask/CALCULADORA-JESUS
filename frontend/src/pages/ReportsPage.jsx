import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Slider } from '../components/ui/slider';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { 
    FileText, TrendingUp, Camera, Scale, Ruler, 
    Activity, Moon, Zap, Brain, Send, ChevronRight, 
    Calendar, Image as ImageIcon
} from 'lucide-react';

const ReportsPage = () => {
    const { api, profile } = useAuth();
    const [reports, setReports] = useState([]);
    const [evolution, setEvolution] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [activeTab, setActiveTab] = useState('form');
    
    const [reportData, setReportData] = useState({
        weight: '',
        measurements: {
            chest: '',
            waist: '',
            hip: '',
            arm: '',
            thigh: ''
        },
        training_compliance: 80,
        nutrition_compliance: 80,
        sleep_quality: 7,
        energy_level: 7,
        stress_level: 5,
        notes: ''
    });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [reportsRes, evolutionRes] = await Promise.all([
                api.get('/reports'),
                api.get('/reports/evolution')
            ]);
            setReports(reportsRes.data);
            setEvolution(evolutionRes.data);
        } catch (error) {
            console.error('Error fetching reports:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!reportData.weight) {
            toast.error('El peso es obligatorio');
            return;
        }
        
        setSubmitting(true);
        try {
            const payload = {
                weight: parseFloat(reportData.weight),
                measurements: Object.fromEntries(
                    Object.entries(reportData.measurements)
                        .filter(([_, v]) => v)
                        .map(([k, v]) => [k, parseFloat(v)])
                ),
                training_compliance: reportData.training_compliance,
                nutrition_compliance: reportData.nutrition_compliance,
                sleep_quality: reportData.sleep_quality,
                energy_level: reportData.energy_level,
                stress_level: reportData.stress_level,
                notes: reportData.notes || null
            };
            
            await api.post('/reports', payload);
            toast.success('Reporte enviado correctamente');
            fetchData();
            setActiveTab('history');
            
            // Reset form
            setReportData({
                weight: '',
                measurements: { chest: '', waist: '', hip: '', arm: '', thigh: '' },
                training_compliance: 80,
                nutrition_compliance: 80,
                sleep_quality: 7,
                energy_level: 7,
                stress_level: 5,
                notes: ''
            });
        } catch (error) {
            toast.error('Error al enviar el reporte');
        } finally {
            setSubmitting(false);
        }
    };

    const weightData = evolution?.weight?.map(w => ({
        date: new Date(w.date).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }),
        peso: w.value
    })) || [];

    if (loading) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/3"></div>
                    <div className="h-48 bg-muted rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in space-y-6">
            <h1 className="heading-2">Mis Reportes</h1>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="form" data-testid="report-form-tab">
                        <FileText className="w-4 h-4 mr-2" />
                        Nuevo
                    </TabsTrigger>
                    <TabsTrigger value="evolution" data-testid="evolution-tab">
                        <TrendingUp className="w-4 h-4 mr-2" />
                        Evolución
                    </TabsTrigger>
                    <TabsTrigger value="history" data-testid="history-tab">
                        <Calendar className="w-4 h-4 mr-2" />
                        Historial
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="form" className="space-y-4">
                    <form onSubmit={handleSubmit} className="space-y-6">
                        {/* Weight */}
                        <Card>
                            <CardContent className="p-4">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                                        <Scale className="w-5 h-5 text-primary" />
                                    </div>
                                    <div>
                                        <Label className="font-semibold">Peso actual *</Label>
                                        <p className="text-xs text-muted-foreground">En ayunas, sin ropa</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={reportData.weight}
                                        onChange={(e) => setReportData({ ...reportData, weight: e.target.value })}
                                        placeholder="75.5"
                                        className="text-2xl font-bold h-14"
                                        data-testid="weight-input"
                                    />
                                    <span className="text-xl text-muted-foreground">kg</span>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Measurements */}
                        <Card>
                            <CardContent className="p-4">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center">
                                        <Ruler className="w-5 h-5 text-secondary" />
                                    </div>
                                    <div>
                                        <Label className="font-semibold">Medidas (cm)</Label>
                                        <p className="text-xs text-muted-foreground">Opcional</p>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    {[
                                        { key: 'chest', label: 'Pecho' },
                                        { key: 'waist', label: 'Cintura' },
                                        { key: 'hip', label: 'Cadera' },
                                        { key: 'arm', label: 'Brazo' },
                                        { key: 'thigh', label: 'Muslo' }
                                    ].map(({ key, label }) => (
                                        <div key={key}>
                                            <Label className="text-xs">{label}</Label>
                                            <Input
                                                type="number"
                                                step="0.1"
                                                value={reportData.measurements[key]}
                                                onChange={(e) => setReportData({
                                                    ...reportData,
                                                    measurements: { ...reportData.measurements, [key]: e.target.value }
                                                })}
                                                placeholder="--"
                                            />
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Compliance Sliders */}
                        <Card>
                            <CardContent className="p-4 space-y-6">
                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <Label className="flex items-center gap-2">
                                            <Activity className="w-4 h-4 text-primary" />
                                            Cumplimiento entrenamiento
                                        </Label>
                                        <span className="font-bold text-primary">{reportData.training_compliance}%</span>
                                    </div>
                                    <Slider
                                        value={[reportData.training_compliance]}
                                        onValueChange={([v]) => setReportData({ ...reportData, training_compliance: v })}
                                        max={100}
                                        step={5}
                                        data-testid="training-compliance-slider"
                                    />
                                </div>

                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <Label className="flex items-center gap-2">
                                            <Activity className="w-4 h-4 text-secondary" />
                                            Cumplimiento nutrición
                                        </Label>
                                        <span className="font-bold text-secondary">{reportData.nutrition_compliance}%</span>
                                    </div>
                                    <Slider
                                        value={[reportData.nutrition_compliance]}
                                        onValueChange={([v]) => setReportData({ ...reportData, nutrition_compliance: v })}
                                        max={100}
                                        step={5}
                                    />
                                </div>

                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <Label className="flex items-center gap-2">
                                            <Moon className="w-4 h-4 text-indigo-500" />
                                            Calidad del sueño
                                        </Label>
                                        <span className="font-bold text-indigo-500">{reportData.sleep_quality}/10</span>
                                    </div>
                                    <Slider
                                        value={[reportData.sleep_quality]}
                                        onValueChange={([v]) => setReportData({ ...reportData, sleep_quality: v })}
                                        max={10}
                                        step={1}
                                    />
                                </div>

                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <Label className="flex items-center gap-2">
                                            <Zap className="w-4 h-4 text-amber-500" />
                                            Nivel de energía
                                        </Label>
                                        <span className="font-bold text-amber-500">{reportData.energy_level}/10</span>
                                    </div>
                                    <Slider
                                        value={[reportData.energy_level]}
                                        onValueChange={([v]) => setReportData({ ...reportData, energy_level: v })}
                                        max={10}
                                        step={1}
                                    />
                                </div>

                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <Label className="flex items-center gap-2">
                                            <Brain className="w-4 h-4 text-rose-500" />
                                            Nivel de estrés
                                        </Label>
                                        <span className="font-bold text-rose-500">{reportData.stress_level}/10</span>
                                    </div>
                                    <Slider
                                        value={[reportData.stress_level]}
                                        onValueChange={([v]) => setReportData({ ...reportData, stress_level: v })}
                                        max={10}
                                        step={1}
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Notes */}
                        <Card>
                            <CardContent className="p-4">
                                <Label className="mb-2 block">Notas adicionales</Label>
                                <Textarea
                                    value={reportData.notes}
                                    onChange={(e) => setReportData({ ...reportData, notes: e.target.value })}
                                    placeholder="¿Cómo te has sentido esta semana? ¿Alguna dificultad o logro?"
                                    rows={4}
                                    data-testid="notes-textarea"
                                />
                            </CardContent>
                        </Card>

                        <Button 
                            type="submit" 
                            className="w-full btn-primary"
                            disabled={submitting}
                            data-testid="submit-report-btn"
                        >
                            <Send className="w-4 h-4 mr-2" />
                            {submitting ? 'Enviando...' : 'Enviar reporte'}
                        </Button>
                    </form>
                </TabsContent>

                <TabsContent value="evolution" className="space-y-4">
                    {/* Weight Chart */}
                    {weightData.length > 0 ? (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Scale className="w-5 h-5" />
                                    Evolución del peso
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={weightData}>
                                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                                            <XAxis dataKey="date" className="text-xs" />
                                            <YAxis domain={['auto', 'auto']} className="text-xs" />
                                            <Tooltip />
                                            <Line 
                                                type="monotone" 
                                                dataKey="peso" 
                                                stroke="hsl(var(--primary))" 
                                                strokeWidth={2}
                                                dot={{ fill: 'hsl(var(--primary))' }}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <Card className="bg-muted/50">
                            <CardContent className="p-8 text-center">
                                <TrendingUp className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                                <h3 className="heading-3 mb-2">Sin datos de evolución</h3>
                                <p className="text-muted-foreground">
                                    Envía tu primer reporte para ver tu progreso.
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Photos Gallery */}
                    {evolution?.photos?.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <ImageIcon className="w-5 h-5" />
                                    Galería de fotos
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-3 gap-2">
                                    {evolution.photos.slice(0, 9).map((item, index) => (
                                        <div key={index} className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                                            <Camera className="w-6 h-6 text-muted-foreground" />
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="history">
                    <ScrollArea className="h-[60vh]">
                        <div className="space-y-3">
                            {reports.length > 0 ? (
                                reports.map((report) => (
                                    <Card key={report.id}>
                                        <CardContent className="p-4">
                                            <div className="flex items-start justify-between mb-3">
                                                <div>
                                                    <p className="font-semibold">
                                                        {new Date(report.created_at).toLocaleDateString('es-ES', {
                                                            day: 'numeric',
                                                            month: 'long',
                                                            year: 'numeric'
                                                        })}
                                                    </p>
                                                    <p className="text-2xl font-bold text-primary">
                                                        {report.weight} kg
                                                    </p>
                                                </div>
                                                <ChevronRight className="w-5 h-5 text-muted-foreground" />
                                            </div>
                                            
                                            <div className="grid grid-cols-2 gap-2 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <Activity className="w-4 h-4 text-primary" />
                                                    <span>Entreno: {report.training_compliance}%</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Activity className="w-4 h-4 text-secondary" />
                                                    <span>Nutrición: {report.nutrition_compliance}%</span>
                                                </div>
                                            </div>
                                            
                                            {report.trainer_feedback && (
                                                <div className="mt-3 p-3 bg-primary/5 rounded-lg">
                                                    <p className="text-xs font-semibold text-primary mb-1">Feedback del entrenador</p>
                                                    <p className="text-sm">{report.trainer_feedback}</p>
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))
                            ) : (
                                <p className="text-center text-muted-foreground py-8">
                                    No hay reportes anteriores.
                                </p>
                            )}
                        </div>
                    </ScrollArea>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ReportsPage;
