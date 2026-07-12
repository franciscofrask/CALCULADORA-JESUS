import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Input } from '../ui/input';
import { Check, Star } from 'lucide-react';

// Alimentos favoritos OCULTOS (petición 2026-07-06): la estrella alteraba el orden de los
// alimentos y no se quiere. Poner a true para reactivar la UI de favoritos.
export const FOOD_FAVORITES_UI = false;
import { Search, X } from 'lucide-react';

const CATEGORY_CHIPS = [
    { label: 'Todas', value: '', emoji: '🍽️' },
    { label: 'Huevos', value: '1', emoji: '🥚' },
    { label: 'Carnes', value: '2', emoji: '🥩' },
    { label: 'Pescados', value: '3', emoji: '🐟' },
    { label: 'Prot. polvo', value: '4', emoji: '💪' },
    { label: 'Lácteos', value: '5', emoji: '🥛' },
    { label: 'Embutidos', value: '6', emoji: '🥩' },
    { label: 'Cereales', value: '7', emoji: '🌾' },
    { label: 'Pan', value: '8', emoji: '🍞' },
    { label: 'Tubérculos', value: '9', emoji: '🥔' },
    { label: 'Legumbres', value: '10', emoji: '🫘' },
    { label: 'Fruta', value: '11', emoji: '🍎' },
    { label: 'Verduras', value: '13', emoji: '🥦' },
    { label: 'Frutos secos', value: '14', emoji: '🥜' },
    { label: 'Grasas', value: '17', emoji: '🫒' },
    { label: 'Intraentreno', value: '18', emoji: '⚡' },
    { label: 'Arroces', value: '21', emoji: '🍚' },
    { label: 'Pasta', value: '22', emoji: '🍝' },
    { label: 'Beb. vegetales', value: '24', emoji: '🥤' },
    { label: 'Prot. vegetal', value: '28', emoji: '🌱' },
    { label: 'Barritas prot.', value: '29', emoji: '🍫' },
];

const SearchFoodModal = ({
    open, mealKey, onClose, searchQuery, setSearchQuery,
    searchCategory, setSearchCategory, searchLoading, searchResults,
    onAddFood, getFoodEmoji, favorites = new Set(), onToggleFavorite,
}) => (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden">
            <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                <div className="flex items-center justify-between">
                    <DialogTitle className="text-white flex items-center gap-2">
                        Buscador de alimentos <span className="text-brand-orange text-sm">({mealKey})</span>
                    </DialogTitle>
                    <button onClick={onClose} className="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
                        <X className="w-5 h-5 text-white" />
                    </button>
                </div>
                <DialogDescription className="sr-only">Busca alimentos para añadir a tu comida</DialogDescription>
            </DialogHeader>

            <div className="p-4 bg-card flex-shrink-0 border-b">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input placeholder="Escribe un alimento..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10 h-12 rounded-xl bg-muted border-0" data-testid="search-food-input" />
                </div>
            </div>

            <div className="flex-shrink-0 bg-card border-b">
                <div className="flex gap-2 px-4 py-3 overflow-x-auto scrollbar-hide">
                    {CATEGORY_CHIPS.map(chip => (
                        <button key={chip.value} onClick={() => setSearchCategory(chip.value)}
                            className={`flex-shrink-0 inline-flex items-center px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
                                searchCategory === chip.value ? 'bg-brand-orange text-white shadow-md' : 'bg-muted text-foreground hover:bg-muted'
                            }`}>
                            <span className="mr-1">{chip.emoji}</span> {chip.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto bg-muted">
                {searchLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-orange border-t-transparent" />
                    </div>
                ) : searchResults.length === 0 ? (
                    <div className="text-center py-12">
                        <span className="text-4xl mb-3 block">🔍</span>
                        <p className="text-muted-foreground">{searchQuery ? 'No se encontraron resultados' : 'Escribe para buscar'}</p>
                    </div>
                ) : (
                    <div className="p-4 space-y-2">
                        {searchResults.map(food => {
                            const macrosEf = food.macros_efectivos || {};
                            const pEf = macrosEf.P ?? food.proteinas ?? 0;
                            const hEf = macrosEf.H ?? food.hidratos ?? 0;
                            const gEf = macrosEf.G ?? food.grasas ?? 0;
                            const racion = food.racion || 100;
                            const isFav = favorites.has(String(food.id));
                            return (
                                <div key={food.id} className="flex items-start gap-1 bg-card rounded-xl shadow-sm hover:shadow-md transition-all">
                                    {FOOD_FAVORITES_UI && onToggleFavorite && (
                                        <button
                                            onClick={(e) => { e.stopPropagation(); onToggleFavorite(food.id); }}
                                            className={`flex-shrink-0 p-3 pt-4 rounded transition-colors ${isFav ? 'text-yellow-400' : 'text-muted-foreground hover:text-yellow-300'}`}
                                            data-testid={`fav-search-${food.id}`}
                                        >
                                            <Star className="w-4 h-4" fill={isFav ? 'currentColor' : 'none'} />
                                        </button>
                                    )}
                                    <button className={`flex-1 text-left p-4 active:scale-[0.98] ${FOOD_FAVORITES_UI ? 'pl-0' : ''}`}
                                        onClick={() => onAddFood(food)}>
                                        <div className="flex items-start gap-3">
                                            <span className="text-2xl">{getFoodEmoji(food.categorias)}</span>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-semibold text-foreground truncate">{food.nombre}</p>
                                                <p className="text-xs text-muted-foreground">{racion}g / 1 ración</p>
                                                <div className="flex flex-wrap gap-1 mt-2">
                                                    {pEf > 0 && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-protein-yellow text-foreground">{pEf.toFixed(1)}g P</span>}
                                                    {hEf > 0 && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-carbs-green text-white">{hEf.toFixed(1)}g H</span>}
                                                    {gEf > 0 && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-fat-red text-white">{gEf.toFixed(1)}g G</span>}
                                                    {pEf === 0 && hEf === 0 && gEf === 0 && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground">Sin macros</span>}
                                                </div>
                                            </div>
                                        </div>
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </DialogContent>
    </Dialog>
);

// Filtro "con estos alimentos": chips + autocompletado contra /calculator/search
// (exportado: lo reutiliza el buscador de menús del coach en la ficha del cliente)
export const FoodFilterBar = ({ api, selected, onChange }) => {
    const [query, setQuery] = React.useState('');
    const [sugerencias, setSugerencias] = React.useState([]);
    React.useEffect(() => {
        if (query.trim().length < 2) { setSugerencias([]); return; }
        const t = setTimeout(() => {
            const params = new URLSearchParams({ q: query.trim(), limit: '8' });
            api(`/api/calculator/search?${params}`)
                .then(r => setSugerencias((r.alimentos || []).filter(a => !selected.some(s => s.id === a.id))))
                .catch(() => setSugerencias([]));
        }, 300);
        return () => clearTimeout(t);
    }, [query, api, selected]);

    const add = (a) => {
        setQuery(''); setSugerencias([]);
        onChange([...selected, { id: a.id, nombre: a.nombre }]);
    };
    const remove = (id) => onChange(selected.filter(s => s.id !== id));

    return (
        <div className="px-4 py-3 border-b bg-card flex-shrink-0" data-testid="menu-food-filter">
            <p className="text-xs font-semibold text-muted-foreground mb-1.5">Con estos alimentos (opcional):</p>
            {selected.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                    {selected.map(s => (
                        <span key={s.id} className="inline-flex items-center gap-1 bg-brand-orange/10 text-brand-orange border border-brand-orange/30 rounded-full pl-2.5 pr-1 py-0.5 text-xs font-semibold">
                            {s.nombre.split(' (')[0].slice(0, 26)}
                            <button onClick={() => remove(s.id)} className="w-4 h-4 rounded-full hover:bg-brand-orange/20 flex items-center justify-center">
                                <X className="w-3 h-3" />
                            </button>
                        </span>
                    ))}
                </div>
            )}
            <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ej: pollo, arroz, claras..." className="pl-8 h-9 text-sm" data-testid="menu-food-filter-input" />
                {sugerencias.length > 0 && (
                    <div className="absolute left-0 right-0 top-10 z-20 bg-card border border-border rounded-xl shadow-lg overflow-hidden">
                        {sugerencias.map(a => (
                            <button key={a.id} onClick={() => add(a)}
                                className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-muted truncate">
                                {a.nombre}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const normalizarTexto = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

const MenuOptionsModal = ({ open, mealKey, onClose, mealInfo, menuOptionsLoading, menuOptions, onApplyOption, api, foodFilter = [], onFoodFilterChange, relajado = false }) => {
    // Buscador por NOMBRE de menú (filtra en local sobre las opciones ya calculadas)
    const [nameQuery, setNameQuery] = React.useState('');
    React.useEffect(() => { if (open) setNameQuery(''); }, [open, mealKey]);
    const opcionesFiltradas = nameQuery.trim()
        ? menuOptions.filter(o => normalizarTexto(o.nombre).includes(normalizarTexto(nameQuery)))
        : menuOptions;

    return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0">
            <DialogHeader className="bg-bg-dark p-4">
                <DialogTitle className="text-white">Elige tu menú</DialogTitle>
                <DialogDescription className="text-muted-foreground">{mealKey && mealInfo[mealKey]?.name}</DialogDescription>
            </DialogHeader>
            {api && onFoodFilterChange && (
                <FoodFilterBar api={api} selected={foodFilter} onChange={onFoodFilterChange} />
            )}
            {!menuOptionsLoading && menuOptions.length > 0 && (
                <div className="px-4 py-3 border-b bg-card flex-shrink-0">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                        <Input value={nameQuery} onChange={(e) => setNameQuery(e.target.value)}
                            placeholder={`Buscar entre ${menuOptions.length} menús...`}
                            className="pl-8 h-9 text-sm" data-testid="menu-name-search" />
                    </div>
                </div>
            )}
            {/* div con overflow en vez de ScrollArea: el viewport de Radix no respeta
                el alto del flex container aquí y las opciones B/C quedaban cortadas sin scroll */}
            <div className="flex-1 min-h-0 overflow-y-auto bg-muted">
                {relajado && !menuOptionsLoading && (
                    <p className="px-4 pt-3 text-xs text-amber-500 font-medium">
                        No hay menús con todos esos alimentos a la vez: te muestro los que más se acercan.
                    </p>
                )}
                {menuOptionsLoading ? (
                    <div className="flex flex-col items-center justify-center py-16">
                        <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent mb-4" />
                        <p className="text-muted-foreground">Cargando menús...</p>
                    </div>
                ) : menuOptions.length === 0 ? (
                    <div className="text-center py-14 px-6">
                        <span className="text-4xl mb-3 block">🍽️</span>
                        <p className="font-semibold text-foreground mb-1.5">No hay menús disponibles todavía</p>
                        <p className="text-sm text-muted-foreground">
                            Elige tú los alimentos con <span className="font-semibold text-foreground">"Lo hago yo"</span> o
                            pídeselo al <span className="font-semibold text-foreground">asistente IA</span>.
                        </p>
                    </div>
                ) : opcionesFiltradas.length === 0 ? (
                    <div className="text-center py-14 px-6">
                        <span className="text-4xl mb-3 block">🔍</span>
                        <p className="font-semibold text-foreground mb-1.5">Ningún menú se llama "{nameQuery}"</p>
                        <p className="text-sm text-muted-foreground">Prueba con otro nombre o borra la búsqueda.</p>
                    </div>
                ) : (
                    <div className="p-4 space-y-3">
                        {opcionesFiltradas.map((option, index) => (
                            <button key={option.id || option.plantilla_id || index}
                                className="w-full text-left p-4 bg-card rounded-2xl shadow-md hover:shadow-lg hover:ring-1 hover:ring-brand-orange/40 transition-all"
                                onClick={() => onApplyOption(option)} data-testid={`menu-option-${index}`}>
                                <div className="flex items-center justify-between gap-2 mb-1">
                                    <h3 className="font-bold text-foreground text-sm leading-snug">{option.nombre}</h3>
                                    {option.momento && (
                                        <span className="flex-shrink-0 text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{option.momento}</span>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    {(option.alimentos || []).join(' · ')}
                                </p>
                                <p className="text-[11px] text-brand-orange font-semibold mt-1.5 flex items-center gap-1">
                                    <Check className="w-3 h-3" /> Se cuadra a tus macros al elegirlo
                                </p>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </DialogContent>
    </Dialog>
    );
};

export { SearchFoodModal, MenuOptionsModal, CATEGORY_CHIPS };
