import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { useAuth } from '../../context/AuthContext';
import { toast } from 'sonner';
import { X, Upload, Loader2 } from 'lucide-react';
import HelpTooltip from '../HelpTooltip';

const EMPTY = {
    nombre: '',
    por_unidad: false,
    racion: '',        // gramos de la unidad (solo si por_unidad)
    peso_tipo: 'neto', // 'neto' | 'escurrido' (informativo para la revisión)
    proteinas: '',
    hidratos: '',
    grasas: '',
    url: '',
};

const PESO_AYUDA = {
    neto: 'Peso total del producto tal cual, incluyendo el líquido o caldo de la conserva.',
    escurrido: 'Peso solo del alimento sólido, una vez escurrido el líquido de la conserva.',
};

// Campo de subida de una foto con vista previa.
const PhotoField = ({ label, hint, file, onChange }) => {
    const preview = file ? URL.createObjectURL(file) : null;
    return (
        <div>
            <label className="block text-xs font-semibold text-muted-foreground mb-1">{label}</label>
            <label className="flex items-center gap-3 border border-dashed border-input rounded-lg p-3 cursor-pointer hover:border-brand-orange/60 transition-colors">
                {preview ? (
                    <img src={preview} alt={label} className="w-14 h-14 rounded object-cover flex-shrink-0" />
                ) : (
                    <div className="w-14 h-14 rounded bg-muted flex items-center justify-center flex-shrink-0">
                        <Upload className="w-5 h-5 text-muted-foreground" />
                    </div>
                )}
                <div className="min-w-0">
                    <p className="text-sm text-foreground truncate">{file ? file.name : 'Seleccionar imagen'}</p>
                    <p className="text-xs text-muted-foreground">{hint}</p>
                </div>
                <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={e => onChange(e.target.files?.[0] || null)}
                />
            </label>
        </div>
    );
};

const NumField = ({ label, value, onChange, placeholder }) => (
    <div>
        <label className="block text-xs font-semibold text-muted-foreground mb-1">{label}</label>
        <input
            type="number"
            min="0"
            step="0.1"
            inputMode="decimal"
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
        />
    </div>
);

const SuggestFoodModal = ({ open, onClose, onSubmitted }) => {
    const { api } = useAuth();
    const [form, setForm] = useState(EMPTY);
    const [frontal, setFrontal] = useState(null);
    const [reverso, setReverso] = useState(null);
    const [saving, setSaving] = useState(false);

    const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

    const reset = () => { setForm(EMPTY); setFrontal(null); setReverso(null); };

    const close = () => { if (!saving) { reset(); onClose(); } };

    const submit = async () => {
        if (!form.nombre.trim()) return toast.error('Indica el nombre del alimento');
        if (form.por_unidad && !(Number(form.racion) > 0)) return toast.error('Indica el peso de la unidad en gramos');

        const fd = new FormData();
        fd.append('nombre', form.nombre.trim());
        fd.append('por_unidad', form.por_unidad ? 'true' : 'false');
        fd.append('racion', form.por_unidad ? String(form.racion) : '100');
        fd.append('peso_tipo', form.peso_tipo);
        fd.append('proteinas', String(form.proteinas || 0));
        fd.append('hidratos', String(form.hidratos || 0));
        fd.append('grasas', String(form.grasas || 0));
        if (form.url.trim()) fd.append('url', form.url.trim());
        if (frontal) fd.append('foto_frontal', frontal);
        if (reverso) fd.append('foto_reverso', reverso);

        setSaving(true);
        try {
            await api.post('/calculator/suggest-food', fd);
            toast.success('Sugerencia enviada. El equipo la revisará pronto.');
            reset();
            onClose();
            onSubmitted?.();
        } catch (e) {
            toast.error(e.response?.data?.detail || 'No se pudo enviar la sugerencia');
        } finally {
            setSaving(false);
        }
    };

    const racionLabel = form.por_unidad ? 'por unidad' : 'por 100 g';

    return (
        <Dialog open={open} onOpenChange={(o) => !o && close()}>
            <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden">
                <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                    <div className="flex items-center justify-between">
                        <DialogTitle className="text-white">Sugerir un alimento</DialogTitle>
                        <button onClick={close} className="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
                            <X className="w-5 h-5 text-white" />
                        </button>
                    </div>
                    <DialogDescription className="text-white/60 text-sm">
                        Rellena los datos de la etiqueta del producto. El equipo lo revisará y, si procede, lo añadirá a la calculadora.
                    </DialogDescription>
                </DialogHeader>

                <div className="p-4 overflow-y-auto space-y-4 bg-card">
                    <div>
                        <label className="block text-xs font-semibold text-muted-foreground mb-1">Nombre del alimento</label>
                        <input
                            type="text"
                            value={form.nombre}
                            onChange={e => set('nombre', e.target.value)}
                            placeholder="Nombre exacto. Si tiene marca, entre paréntesis"
                            className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
                        />
                        <p className="text-xs text-muted-foreground mt-1">Ej.: "Yogur proteico (Hacendado)". Si es genérico, no incluyas marca.</p>
                    </div>

                    {/* Tipo de ración */}
                    <div>
                        <label className="block text-xs font-semibold text-muted-foreground mb-1">Tipo de ración</label>
                        <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                            <input
                                type="checkbox"
                                checked={form.por_unidad}
                                onChange={e => set('por_unidad', e.target.checked)}
                                className="w-4 h-4 accent-brand-orange"
                            />
                            Se toma por unidad (pieza)
                        </label>
                        {form.por_unidad ? (
                            <div className="mt-2">
                                <NumField label="Peso de la unidad (g)" value={form.racion}
                                    onChange={v => set('racion', v)} placeholder="Ej.: 30" />
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground mt-1">Por defecto los valores se registran por 100 g.</p>
                        )}
                    </div>

                    {/* Tipo de peso (informativo para la revisión) */}
                    <div>
                        <label className="block text-xs font-semibold text-muted-foreground mb-1">Tipo de peso</label>
                        <div className="flex flex-col gap-1.5">
                            {[['neto', 'Peso neto'], ['escurrido', 'Peso escurrido']].map(([val, label]) => (
                                <label key={val} className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                                    <input
                                        type="radio"
                                        name="peso_tipo"
                                        checked={form.peso_tipo === val}
                                        onChange={() => set('peso_tipo', val)}
                                        className="appearance-none shrink-0 w-3.5 h-3.5 rounded-full border border-input bg-card checked:bg-brand-orange checked:border-brand-orange cursor-pointer"
                                    />
                                    {label}
                                    <HelpTooltip text={PESO_AYUDA[val]} />
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Valor nutricional */}
                    <div>
                        <label className="block text-xs font-semibold text-muted-foreground mb-1">
                            Valor nutricional ({racionLabel})
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                            <NumField label="Proteínas" value={form.proteinas} onChange={v => set('proteinas', v)} placeholder="g" />
                            <NumField label="Hidratos" value={form.hidratos} onChange={v => set('hidratos', v)} placeholder="g" />
                            <NumField label="Grasas" value={form.grasas} onChange={v => set('grasas', v)} placeholder="g" />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Toma los valores exactamente de la etiqueta del producto.</p>
                    </div>

                    {/* Enlace */}
                    <div>
                        <label className="block text-xs font-semibold text-muted-foreground mb-1">Enlace de la fuente</label>
                        <input
                            type="url"
                            value={form.url}
                            onChange={e => set('url', e.target.value)}
                            placeholder="https://..."
                            className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
                        />
                        <p className="text-xs text-muted-foreground mt-1">URL donde se pueden verificar los datos nutricionales.</p>
                    </div>

                    {/* Fotos (opcionales) */}
                    <div className="space-y-3">
                        <p className="text-xs text-muted-foreground">Fotos (opcionales, pero ayudan a la revisión):</p>
                        <PhotoField label="Foto frontal" hint="Que se vea el nombre del producto (opcional)"
                            file={frontal} onChange={setFrontal} />
                        <PhotoField label="Foto del reverso" hint="Que se vea la tabla nutricional (opcional)"
                            file={reverso} onChange={setReverso} />
                    </div>
                </div>

                <div className="p-4 border-t border-border bg-card flex-shrink-0">
                    <button
                        onClick={submit}
                        disabled={saving}
                        className="w-full bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm flex items-center justify-center gap-2 transition-colors"
                    >
                        {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                        Enviar sugerencia
                    </button>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default SuggestFoodModal;
