import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { toast } from 'sonner';
import { 
    Apple, Calculator, Plus, Search, Trash2, 
    Flame, Beef, Wheat, Droplet, Check
} from 'lucide-react';

const NutritionPage = () => {
    const { api, profile } = useAuth();
    const [macros, setMacros] = useState(null);
    const [foods, setFoods] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedMeals, setSelectedMeals] = useState([]);
    const [isTrainingDay, setIsTrainingDay] = useState(true);
    const [loading, setLoading] = useState(true);
    const [showSuggestDialog, setShowSuggestDialog] = useState(false);
    const [newFood, setNewFood] = useState({ name: '', calories_per_100g: '', protein_per_100g: '', carbs_per_100g: '', fat_per_100g: '' });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [macrosRes, foodsRes] = await Promise.all([
                api.get('/macros'),
                api.get('/calculator/foods')
            ]);
            setMacros(macrosRes.data);
            setFoods(foodsRes.data);
        } catch (error) {
            console.error('Error fetching nutrition data:', error);
        } finally {
            setLoading(false);
        }
    };

    const currentMacros = isTrainingDay ? macros?.training : macros?.rest;

    const calculateConsumed = () => {
        return selectedMeals.reduce((total, meal) => ({
            calories: total.calories + (meal.calories * meal.quantity / 100),
            protein: total.protein + (meal.protein * meal.quantity / 100),
            carbs: total.carbs + (meal.carbs * meal.quantity / 100),
            fat: total.fat + (meal.fat * meal.quantity / 100)
        }), { calories: 0, protein: 0, carbs: 0, fat: 0 });
    };

    const consumed = calculateConsumed();
    const filteredFoods = foods.filter(f => 
        f.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const addFood = (food) => {
        setSelectedMeals([...selectedMeals, { ...food, quantity: 100 }]);
        toast.success(`${food.name} añadido`);
    };

    const removeFood = (index) => {
        setSelectedMeals(selectedMeals.filter((_, i) => i !== index));
    };

    const updateQuantity = (index, quantity) => {
        const updated = [...selectedMeals];
        updated[index].quantity = parseInt(quantity) || 0;
        setSelectedMeals(updated);
    };

    const handleSuggestFood = async () => {
        try {
            await api.post('/calculator/suggest-food', newFood);
            toast.success('Alimento sugerido correctamente');
            setShowSuggestDialog(false);
            setNewFood({ name: '', calories_per_100g: '', protein_per_100g: '', carbs_per_100g: '', fat_per_100g: '' });
        } catch (error) {
            toast.error('Error al sugerir alimento');
        }
    };

    if (loading) {
        return (
            <div className="p-4 md:p-6 pb-24 md:pb-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/3"></div>
                    <div className="h-48 bg-[#111] rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 pb-24 md:pb-6 animate-fade-in bg-[#0A0A0A] min-h-screen relative overflow-hidden">
            {/* Background */}
            <div 
                className="absolute inset-0 bg-cover bg-center opacity-5"
                style={{
                    backgroundImage: `url('https://customer-assets.emergentagent.com/job_language-12/artifacts/iguh6amq_IMG_5764.jpeg')`
                }}
            ></div>
            
            <div className="relative z-10 space-y-6">
                <div className="flex items-center justify-between">
                    <h1 className="heading-2 text-white">MI NUTRICIÓN</h1>
                    <div className="flex gap-2">
                        <Button
                            variant={isTrainingDay ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setIsTrainingDay(true)}
                            className={isTrainingDay ? 'bg-[#FF671F] text-white' : 'bg-transparent border-[#333] text-white/70 hover:border-[#FF671F]'}
                            data-testid="training-day-btn"
                        >
                            Entreno
                        </Button>
                        <Button
                            variant={!isTrainingDay ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setIsTrainingDay(false)}
                            className={!isTrainingDay ? 'bg-[#FF671F] text-white' : 'bg-transparent border-[#333] text-white/70 hover:border-[#FF671F]'}
                            data-testid="rest-day-btn"
                        >
                            Descanso
                        </Button>
                    </div>
                </div>

                {/* Macros Target */}
                {currentMacros ? (
                    <Card className="bg-[#111111] border-[#222]">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-white uppercase tracking-wider">Objetivos del día</h3>
                                <span className="text-sm text-[#FF671F]">
                                    {isTrainingDay ? 'Día de entrenamiento' : 'Día de descanso'}
                                </span>
                            </div>
                            
                            <div className="grid grid-cols-4 gap-4">
                                <div className="text-center">
                                    <div className="w-14 h-14 mx-auto bg-orange-500/10 rounded-xl flex items-center justify-center mb-2">
                                        <Flame className="w-7 h-7 text-orange-500" />
                                    </div>
                                    <p className="text-3xl font-bold text-orange-500" style={{ fontFamily: 'Bebas Neue' }}>
                                        {Math.round(currentMacros.calories)}
                                    </p>
                                    <p className="text-xs text-white/50 uppercase tracking-wider">kcal</p>
                                </div>
                                <div className="text-center">
                                    <div className="w-14 h-14 mx-auto bg-red-500/10 rounded-xl flex items-center justify-center mb-2">
                                        <Beef className="w-7 h-7 text-red-500" />
                                    </div>
                                    <p className="text-3xl font-bold text-red-500" style={{ fontFamily: 'Bebas Neue' }}>
                                        {Math.round(currentMacros.protein)}
                                    </p>
                                    <p className="text-xs text-white/50 uppercase tracking-wider">Proteína</p>
                                </div>
                                <div className="text-center">
                                    <div className="w-14 h-14 mx-auto bg-amber-500/10 rounded-xl flex items-center justify-center mb-2">
                                        <Wheat className="w-7 h-7 text-amber-500" />
                                    </div>
                                    <p className="text-3xl font-bold text-amber-500" style={{ fontFamily: 'Bebas Neue' }}>
                                        {Math.round(currentMacros.carbs)}
                                    </p>
                                    <p className="text-xs text-white/50 uppercase tracking-wider">Carbos</p>
                                </div>
                                <div className="text-center">
                                    <div className="w-14 h-14 mx-auto bg-blue-500/10 rounded-xl flex items-center justify-center mb-2">
                                        <Droplet className="w-7 h-7 text-blue-500" />
                                    </div>
                                    <p className="text-3xl font-bold text-blue-500" style={{ fontFamily: 'Bebas Neue' }}>
                                        {Math.round(currentMacros.fat)}
                                    </p>
                                    <p className="text-xs text-white/50 uppercase tracking-wider">Grasas</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    <Card className="bg-[#111111] border-[#222]">
                        <CardContent className="p-8 text-center">
                            <Apple className="w-16 h-16 text-[#FF671F]/30 mx-auto mb-4" />
                            <h3 className="heading-3 text-white mb-2">MACROS PENDIENTES</h3>
                            <p className="text-white/50">
                                Tu entrenador asignará tus macros personalizados pronto.
                            </p>
                        </CardContent>
                    </Card>
                )}

                <Tabs defaultValue="calculator" className="space-y-4">
                    <TabsList className="grid w-full grid-cols-2 bg-[#111111]">
                        <TabsTrigger 
                            value="calculator" 
                            data-testid="calculator-tab"
                            className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider"
                        >
                            <Calculator className="w-4 h-4 mr-2" />
                            Calculadora
                        </TabsTrigger>
                        <TabsTrigger 
                            value="foods" 
                            data-testid="foods-tab"
                            className="data-[state=active]:bg-[#FF671F] data-[state=active]:text-white uppercase tracking-wider"
                        >
                            <Search className="w-4 h-4 mr-2" />
                            Alimentos
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="calculator" className="space-y-4">
                        {/* Progress */}
                        {currentMacros && (
                            <Card className="bg-[#111111] border-[#222]">
                                <CardContent className="p-4 space-y-4">
                                    <h4 className="font-bold text-white uppercase tracking-wider text-sm">Consumo de hoy</h4>
                                    
                                    <div className="space-y-3">
                                        {[
                                            { name: 'Calorías', consumed: consumed.calories, target: currentMacros.calories, unit: 'kcal', color: 'bg-orange-500' },
                                            { name: 'Proteína', consumed: consumed.protein, target: currentMacros.protein, unit: 'g', color: 'bg-red-500' },
                                            { name: 'Carbohidratos', consumed: consumed.carbs, target: currentMacros.carbs, unit: 'g', color: 'bg-amber-500' },
                                            { name: 'Grasas', consumed: consumed.fat, target: currentMacros.fat, unit: 'g', color: 'bg-blue-500' }
                                        ].map((item) => (
                                            <div key={item.name}>
                                                <div className="flex justify-between text-sm mb-1">
                                                    <span className="text-white/70">{item.name}</span>
                                                    <span className="text-white">{Math.round(item.consumed)} / {Math.round(item.target)} {item.unit}</span>
                                                </div>
                                                <div className="w-full bg-[#222] rounded-full h-2">
                                                    <div 
                                                        className={`${item.color} h-2 rounded-full transition-all`}
                                                        style={{ width: `${Math.min((item.consumed / item.target) * 100, 100)}%` }}
                                                    ></div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Selected Foods */}
                        <Card className="bg-[#111111] border-[#222]">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-lg text-white uppercase tracking-wider">Alimentos añadidos</CardTitle>
                            </CardHeader>
                            <CardContent className="p-4">
                                {selectedMeals.length > 0 ? (
                                    <div className="space-y-3">
                                        {selectedMeals.map((meal, index) => (
                                            <div key={index} className="flex items-center gap-3 p-3 bg-[#1A1A1A] rounded-lg">
                                                <div className="flex-1 min-w-0">
                                                    <p className="font-medium text-white text-sm truncate">{meal.name}</p>
                                                    <p className="text-xs text-[#FF671F]">
                                                        {Math.round(meal.calories * meal.quantity / 100)} kcal
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Input
                                                        type="number"
                                                        value={meal.quantity}
                                                        onChange={(e) => updateQuantity(index, e.target.value)}
                                                        className="w-16 h-8 text-sm bg-[#0A0A0A] border-[#333] text-white"
                                                    />
                                                    <span className="text-xs text-white/50">g</span>
                                                    <Button 
                                                        variant="ghost" 
                                                        size="icon" 
                                                        className="h-8 w-8 text-red-500 hover:bg-red-500/10"
                                                        onClick={() => removeFood(index)}
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-center text-white/40 py-6">
                                        Añade alimentos desde la pestaña "Alimentos"
                                    </p>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="foods" className="space-y-4">
                        {/* Search */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                            <Input
                                placeholder="Buscar alimento..."
                                className="pl-10 bg-[#111111] border-[#333] text-white placeholder:text-white/30 focus:border-[#FF671F]"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                data-testid="food-search"
                            />
                        </div>

                        {/* Food List */}
                        <ScrollArea className="h-[40vh]">
                            <div className="space-y-2">
                                {filteredFoods.map((food) => (
                                    <Card key={food.id} className="bg-[#111111] border-[#222] hover:border-[#FF671F]/50 transition-colors">
                                        <CardContent className="p-3 flex items-center justify-between">
                                            <div>
                                                <p className="font-medium text-white text-sm">{food.name}</p>
                                                <p className="text-xs text-white/50">
                                                    <span className="text-orange-500">{food.calories}</span> kcal | 
                                                    P:<span className="text-red-500">{food.protein}</span>g 
                                                    C:<span className="text-amber-500">{food.carbs}</span>g 
                                                    G:<span className="text-blue-500">{food.fat}</span>g
                                                </p>
                                            </div>
                                            <Button 
                                                variant="ghost" 
                                                size="icon"
                                                className="text-[#FF671F] hover:bg-[#FF671F]/10"
                                                onClick={() => addFood(food)}
                                                data-testid={`add-food-${food.id}`}
                                            >
                                                <Plus className="w-4 h-4" />
                                            </Button>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </ScrollArea>

                        {/* Suggest Food */}
                        <Dialog open={showSuggestDialog} onOpenChange={setShowSuggestDialog}>
                            <DialogTrigger asChild>
                                <Button variant="outline" className="w-full bg-transparent border-[#333] text-white hover:border-[#FF671F]" data-testid="suggest-food-btn">
                                    <Plus className="w-4 h-4 mr-2" />
                                    Sugerir nuevo alimento
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-[#111111] border-[#333]">
                                <DialogHeader>
                                    <DialogTitle className="text-white uppercase tracking-wider">Sugerir alimento</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4">
                                    <div>
                                        <Label className="text-white/70">Nombre del alimento</Label>
                                        <Input
                                            value={newFood.name}
                                            onChange={(e) => setNewFood({ ...newFood, name: e.target.value })}
                                            placeholder="Ej: Quinoa"
                                            className="bg-[#0A0A0A] border-[#333] text-white"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <Label className="text-white/70">Calorías /100g</Label>
                                            <Input
                                                type="number"
                                                value={newFood.calories_per_100g}
                                                onChange={(e) => setNewFood({ ...newFood, calories_per_100g: e.target.value })}
                                                className="bg-[#0A0A0A] border-[#333] text-white"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-white/70">Proteína /100g</Label>
                                            <Input
                                                type="number"
                                                value={newFood.protein_per_100g}
                                                onChange={(e) => setNewFood({ ...newFood, protein_per_100g: e.target.value })}
                                                className="bg-[#0A0A0A] border-[#333] text-white"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-white/70">Carbos /100g</Label>
                                            <Input
                                                type="number"
                                                value={newFood.carbs_per_100g}
                                                onChange={(e) => setNewFood({ ...newFood, carbs_per_100g: e.target.value })}
                                                className="bg-[#0A0A0A] border-[#333] text-white"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-white/70">Grasas /100g</Label>
                                            <Input
                                                type="number"
                                                value={newFood.fat_per_100g}
                                                onChange={(e) => setNewFood({ ...newFood, fat_per_100g: e.target.value })}
                                                className="bg-[#0A0A0A] border-[#333] text-white"
                                            />
                                        </div>
                                    </div>
                                    <Button onClick={handleSuggestFood} className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white uppercase tracking-wider">
                                        Enviar sugerencia
                                    </Button>
                                </div>
                            </DialogContent>
                        </Dialog>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
};

export default NutritionPage;
