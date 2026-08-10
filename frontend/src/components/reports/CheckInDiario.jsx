import React, { useState } from 'react';
import { toast } from 'sonner';
import { Zap, Send, Loader2, CheckCircle2 } from 'lucide-react';

/**
 * EL CHECK-IN DE HOY, PARA RELLENARLO DONDE ESTÉS.
 *
 * Sale de la pantalla de Check-ins para poder ponerlo TAMBIÉN dentro de Seguimiento, en
 * la propia tarjeta de «Hoy · 10 segundos». La razón es esa promesa: si algo dura diez
 * segundos, cambiar de pantalla ya se come dos. Decisión de Francisco, 10-08.
 *
 * Lo que NO se hizo, y merece quedar escrito: juntar además el reporte en esa misma vista.
 * El reporte son varios minutos -- peso, diez medidas, huecos, notas, tres preguntas y tres
 * fotos -- y solo se puede rellenar con su ventana abierta, cuatro días de cada quince o
 * treinta. Pegarlo a lo que se usa a diario es como se llegó a la pantalla de 3.770 px que
 * había que arreglar.
 *
 * Dos campos y ni uno más (documento del 31-07, partes 6 y 7.2): solo lo que no está en
 * ningún otro dato. El ánimo se quitó, y la dieta y el entreno no se preguntan porque ya
 * constan en lo registrado.
 */
const Escala = ({ label, valor, onElegir, testid, icono: Icono, ayuda }) => (
    <div>
        <span className="text-sm text-foreground/70 mb-2 block">{label}</span>
        <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(v => (
                <button key={v} type="button" onClick={() => onElegir(v)} data-testid={`${testid}-${v}`}
                    className={`flex-1 py-3 rounded-xl border transition-all flex items-center justify-center gap-1 font-bold text-sm ${
                        valor === v ? 'border-brand bg-brand/10 text-brand' : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                    {Icono && <Icono className="w-3.5 h-3.5" />}{v}
                </button>
            ))}
        </div>
        {ayuda && <p className="text-[11px] text-foreground/40 mt-1.5">{ayuda}</p>}
    </div>
);

const CheckInDiario = ({ api, hecho, onEnviado, inputCls }) => {
    const [daily, setDaily] = useState({ energy: null, hunger_anxiety: null, comido_hoy: '' });
    const [enviando, setEnviando] = useState(false);

    // Ya está hecho: se dice lo que contestó, no se le vuelve a pedir.
    if (hecho) {
        return (
            <div className="flex items-start gap-3" data-testid="checkin-hoy-hecho">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                    <p className="font-bold text-foreground">Check-in de hoy hecho</p>
                    <p className="text-sm text-foreground/60 mt-0.5">
                        Energía {hecho.energy}/5
                        {hecho.hunger_anxiety != null && ` · Hambre ${hecho.hunger_anxiety}/5`}
                        {/* La dieta la rellena el sistema con lo registrado, no él. */}
                        {hecho.nutrition_followed != null && (hecho.nutrition_followed ? ' · Dieta registrada' : ' · Sin dieta registrada')}
                    </p>
                </div>
            </div>
        );
    }

    const enviar = async () => {
        if (daily.energy == null || daily.hunger_anxiety == null) {
            return toast.error('Dinos cómo vas de energía y de hambre');
        }
        setEnviando(true);
        try {
            await api.post('/checkins', {
                type: 'daily', ...daily,
                comido_hoy: (daily.comido_hoy || '').trim() || null,
            });
            toast.success('Check-in diario enviado');
            setDaily({ energy: null, hunger_anxiety: null, comido_hoy: '' });
            onEnviado?.();
        } catch { toast.error('Error al enviar check-in'); }
        finally { setEnviando(false); }
    };

    return (
        <div className="space-y-5" data-testid="checkin-hoy">
            <Escala label="Nivel de energía" valor={daily.energy} icono={Zap} testid="daily-energy"
                onElegir={v => setDaily({ ...daily, energy: v })} />
            <Escala label="Ansiedad y hambre" valor={daily.hunger_anxiety} testid="daily-hunger"
                ayuda="1 = nada · 5 = mucha"
                onElegir={v => setDaily({ ...daily, hunger_anxiety: v })} />
            {/* Lo que ha comido de verdad, con sus palabras. No es su dieta: esa ya está en la
                app. Es el picoteo, la cerveza y el trozo de tarta que no aparecen en ningún
                sitio, y que son justo lo que explica por qué alguien coge peso sin saberlo. */}
            <div>
                <span className="text-sm text-foreground/70 mb-2 block">¿Qué has comido hoy?</span>
                <textarea rows={3} value={daily.comido_hoy} data-testid="daily-comido"
                    onChange={e => setDaily({ ...daily, comido_hoy: e.target.value })}
                    placeholder="Cuéntalo a tu manera, sin pesar nada. Incluye lo que picaste entre horas."
                    className={(inputCls || 'w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm focus:outline-none focus:border-[#FF671F]') + ' resize-none'} />
                <p className="text-[11px] text-foreground/40 mt-1.5">
                    Opcional, pero es lo que más ayuda a entender cómo te va.
                </p>
            </div>
            <button onClick={enviar} disabled={enviando} data-testid="enviar-checkin-hoy"
                className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                {enviando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar check-in
            </button>
        </div>
    );
};

export default CheckInDiario;
