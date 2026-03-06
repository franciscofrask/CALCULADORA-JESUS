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
    Flame, Beef, Wheat, Droplet, Check, X, Clock
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

    const getProgressColor = (consumed, target) => {
        const percentage = (consumed / target) * 100;
        if (percentage < 80) return 'bg-yellow-500';
        if (percentage <= 105) return 'bg-secondary';
        return 'bg-destructive';
    };

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
            <div className="flex items-center justify-between">
                <h1 className="heading-2">Mi Nutrición</h1>
                <div className="flex gap-2">
                    <Button
                        variant={isTrainingDay ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setIsTrainingDay(true)}
                        data-testid="training-day-btn"
                    >
                        Entreno
                    </Button>
                    <Button
                        variant={!isTrainingDay ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setIsTrainingDay(false)}
                        data-testid="rest-day-btn"
                    >
                        Descanso
                    </Button>
                </div>
            </div>

            {/* Macros Target */}
            {currentMacros ? (
                <Card className="bg-gradient-to-r from-primary/5 via-secondary/5 to-accent/5">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-semibold">Objetivos del día</h3>
                            <span className="text-sm text-muted-foreground">
                                {isTrainingDay ? 'Día de entrenamiento' : 'Día de descanso'}
                            </span>
                        </div>
                        
                        <div className="grid grid-cols-4 gap-4">
                            <div className="text-center">
                                <div className="w-12 h-12 mx-auto bg-orange-500/10 rounded-full flex items-center justify-center mb-2">
                                    <Flame className="w-5 h-5 text-orange-500" />
                                </div>
                                <p className="stat-number text-orange-500 text-2xl">{Math.round(currentMacros.calories)}</p>
                                <p className="text-xs text-muted-foreground">kcal</p>
                            </div>
                            <div className="text-center">
                                <div className="w-12 h-12 mx-auto bg-red-500/10 rounded-full flex items-center justify-center mb-2">
                                    <Beef className="w-5 h-5 text-red-500" />
                                </div>
                                <p className="stat-number text-red-500 text-2xl">{Math.round(currentMacros.protein)}</p>
                                <p className="text-xs text-muted-foreground">Proteína</p>
                            </div>
                            <div className="text-center">
                                <div className="w-12 h-12 mx-auto bg-amber-500/10 rounded-full flex items-center justify-center mb-2">
                                    <Wheat className="w-5 h-5 text-amber-500" />
                                </div>
                                <p className="stat-number text-amber-500 text-2xl">{Math.round(currentMacros.carbs)}</p>
                                <p className="text-xs text-muted-foreground">Carbos</p>
                            </div>
                            <div className="text-center">
                                <div className="w-12 h-12 mx-auto bg-blue-500/10 rounded-full flex items-center justify-center mb-2">
                                    <Droplet className="w-5 h-5 text-blue-500" />
                                </div>
                                <p className="stat-number text-blue-500 text-2xl">{Math.round(currentMacros.fat)}</p>
                                <p className="text-xs text-muted-foreground">Grasas</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card className="bg-muted/50">
                    <CardContent className="p-6 text-center">
                        <Apple className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                        <h3 className="heading-3 mb-2">Macros pendientes</h3>
                        <p className="text-muted-foreground">
                            Tu entrenador asignará tus macros personalizados pronto.
                        </p>
                    </CardContent>
                </Card>
            )}

            <Tabs defaultValue="calculator" className="space-y-4">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="calculator" data-testid="calculator-tab">
                        <Calculator className="w-4 h-4 mr-2" />
                        Calculadora
                    </TabsTrigger>
                    <TabsTrigger value="foods" data-testid="foods-tab">
                        <Search className="w-4 h-4 mr-2" />
                        Alimentos
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="calculator" className="space-y-4">
                    {/* Progress */}
                    {currentMacros && (
                        <Card>
                            <CardContent className="p-4 space-y-4">
                                <h4 className="font-semibold">Consumo de hoy</h4>
                                
                                <div className="space-y-3">
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Calorías</span>
                                            <span>{Math.round(consumed.calories)} / {Math.round(currentMacros.calories)} kcal</span>
                                        </div>
                                        <Progress 
                                            value={Math.min((consumed.calories / currentMacros.calories) * 100, 100)} 
                                            className={`h-2 ${getProgressColor(consumed.calories, currentMacros.calories)}`}
                                        />
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Proteína</span>
                                            <span>{Math.round(consumed.protein)} / {Math.round(currentMacros.protein)} g</span>
                                        </div>
                                        <Progress 
                                            value={Math.min((consumed.protein / currentMacros.protein) * 100, 100)} 
                                            className="h-2"
                                        />
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Carbohidratos</span>
                                            <span>{Math.round(consumed.carbs)} / {Math.round(currentMacros.carbs)} g</span>
                                        </div>
                                        <Progress 
                                            value={Math.min((consumed.carbs / currentMacros.carbs) * 100, 100)} 
                                            className="h-2"
                                        />
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Grasas</span>
                                            <span>{Math.round(consumed.fat)} / {Math.round(currentMacros.fat)} g</span>
                                        </div>
                                        <Progress 
                                            value={Math.min((consumed.fat / currentMacros.fat) * 100, 100)} 
                                            className="h-2"
                                        />
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Selected Foods */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-lg">Alimentos añadidos</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4">
                            {selectedMeals.length > 0 ? (
                                <div className="space-y-3">
                                    {selectedMeals.map((meal, index) => (
                                        <div key={index} className="flex items-center gap-3 p-2 bg-muted/50 rounded-lg">
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-sm truncate">{meal.name}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {Math.round(meal.calories * meal.quantity / 100)} kcal
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Input
                                                    type="number"
                                                    value={meal.quantity}
                                                    onChange={(e) => updateQuantity(index, e.target.value)}
                                                    className="w-16 h-8 text-sm"
                                                />
                                                <span className="text-xs text-muted-foreground">g</span>
                                                <Button 
                                                    variant="ghost" 
                                                    size="icon" 
                                                    className="h-8 w-8 text-destructive"
                                                    onClick={() => removeFood(index)}
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-center text-muted-foreground py-4">
                                    Añade alimentos desde la pestaña "Alimentos"
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="foods" className="space-y-4">
                    {/* Search */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder="Buscar alimento..."
                            className="pl-10"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            data-testid="food-search"
                        />
                    </div>

                    {/* Food List */}
                    <ScrollArea className="h-[40vh]">
                        <div className="space-y-2">
                            {filteredFoods.map((food) => (
                                <Card key={food.id} className="cursor-pointer hover:bg-muted/50 transition-colors">
                                    <CardContent className="p-3 flex items-center justify-between">
                                        <div>
                                            <p className="font-medium text-sm">{food.name}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {food.calories} kcal | P:{food.protein}g C:{food.carbs}g G:{food.fat}g
                                            </p>
                                        </div>
                                        <Button 
                                            variant="ghost" 
                                            size="icon"
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
                            <Button variant="outline" className="w-full" data-testid="suggest-food-btn">
                                <Plus className="w-4 h-4 mr-2" />
                                Sugerir nuevo alimento
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Sugerir alimento</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4">
                                <div>
                                    <Label>Nombre del alimento</Label>
                                    <Input
                                        value={newFood.name}
                                        onChange={(e) => setNewFood({ ...newFood, name: e.target.value })}
                                        placeholder="Ej: Quinoa"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label>Calorías /100g</Label>
                                        <Input
                                            type="number"
                                            value={newFood.calories_per_100g}
                                            onChange={(e) => setNewFood({ ...newFood, calories_per_100g: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <Label>Proteína /100g</Label>
                                        <Input
                                            type="number"
                                            value={newFood.protein_per_100g}
                                            onChange={(e) => setNewFood({ ...newFood, protein_per_100g: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <Label>Carbos /100g</Label>
                                        <Input
                                            type="number"
                                            value={newFood.carbs_per_100g}
                                            onChange={(e) => setNewFood({ ...newFood, carbs_per_100g: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <Label>Grasas /100g</Label>
                                        <Input
                                            type="number"
                                            value={newFood.fat_per_100g}
                                            onChange={(e) => setNewFood({ ...newFood, fat_per_100g: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <Button onClick={handleSuggestFood} className="w-full">
                                    Enviar sugerencia
                                </Button>
                            </div>
                        </DialogContent>
                    </Dialog>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default NutritionPage;
