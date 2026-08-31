/**
 * Diálogos de confirmación y de texto propios de la app.
 *
 * Sustituyen a window.confirm y window.prompt, que además de no pegar con el diseño
 * bloquean la pestaña entera mientras están abiertos (y en móvil salen con el nombre
 * del dominio delante). Se usan igual de fácil, pero con await:
 *
 *   const { confirm, prompt, elegir } = useConfirm();
 *   if (!(await confirm({ title: '¿Borrar el menú?', danger: true }))) return;
 *   const motivo = await prompt({ title: 'Motivo del rechazo', optional: true });
 *   const de = await elegir({ title: '¿De dónde bajo la proteína?', opciones: [
 *       { valor: 'polvo', titulo: 'Aislado · 60 g', detalle: 'se quedaría en 9 g' },
 *       { valor: 'queso', titulo: 'Queso · 300 g', detalle: 'se quedaría en 50 g' },
 *   ] });
 *
 * confirm devuelve true/false; prompt devuelve el texto o null si se cancela; elegir
 * devuelve el `valor` de la opción elegida, o null si se cierra sin elegir.
 *
 * NINGUNA OPCIÓN VIENE MARCADA (Jesús, 31-08-2026, sobre de dónde bajar un macro: «ni
 * siquiera que sugiera»). Marcar una es sugerirla, y lo que se pregunta aquí es justo lo
 * que la app no puede saber.
 *
 * El estilo se adapta solo: oscuro en el panel del coach, del tema en la app del cliente.
 */
import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './dialog';
import { Button } from './button';
import { Textarea } from './textarea';

const ConfirmContext = createContext(null);

export const useConfirm = () => {
    const ctx = useContext(ConfirmContext);
    if (!ctx) throw new Error('useConfirm necesita <ConfirmProvider> por encima');
    return ctx;
};

export const ConfirmProvider = ({ children }) => {
    const [dialogo, setDialogo] = useState(null);   // null = cerrado
    const [texto, setTexto] = useState('');
    const resolver = useRef(null);
    const location = useLocation();
    const oscuro = location.pathname.startsWith('/admin');

    const abrir = useCallback((opts, modo) => new Promise((resolve) => {
        resolver.current = resolve;
        setTexto(opts.defaultValue || '');
        setDialogo({ modo, ...opts });
    }), []);

    const confirm = useCallback((opts = {}) => abrir(opts, 'confirm'), [abrir]);
    const prompt = useCallback((opts = {}) => abrir(opts, 'prompt'), [abrir]);
    const elegir = useCallback((opts = {}) => abrir(opts, 'elegir'), [abrir]);

    const cerrar = (valor) => {
        setDialogo(null);
        if (resolver.current) { resolver.current(valor); resolver.current = null; }
    };

    const esPrompt = dialogo?.modo === 'prompt';
    const esElegir = dialogo?.modo === 'elegir';
    const puedeConfirmar = !esPrompt || dialogo?.optional || texto.trim().length > 0;
    const nada = esPrompt || esElegir ? null : false;   // qué devuelve cerrar sin elegir

    return (
        <ConfirmContext.Provider value={{ confirm, prompt, elegir }}>
            {children}
            <Dialog open={!!dialogo} onOpenChange={(o) => { if (!o) cerrar(nada); }}>
                {dialogo && (
                    <DialogContent
                        className={`max-w-md ${oscuro ? 'bg-[#111] border-[#333] text-white' : 'bg-card border-border text-foreground'}`}
                        data-testid="confirm-dialog">
                        <DialogHeader>
                            <DialogTitle className="uppercase tracking-wider flex items-center gap-2">
                                {dialogo.danger && <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />}
                                {dialogo.title}
                            </DialogTitle>
                        </DialogHeader>
                        {dialogo.description && (
                            <p className={`text-sm ${oscuro ? 'text-white/60' : 'text-muted-foreground'}`}>{dialogo.description}</p>
                        )}
                        {esPrompt && (
                            <Textarea
                                autoFocus
                                value={texto}
                                onChange={(e) => setTexto(e.target.value)}
                                placeholder={dialogo.placeholder || ''}
                                className={oscuro ? 'bg-[#0A0A0A] border-[#333] text-white' : ''}
                                data-testid="confirm-input"
                            />
                        )}
                        {esElegir && (
                            <div className="space-y-2">
                                {(dialogo.opciones || []).map((o) => (
                                    <button key={o.valor} type="button"
                                        onClick={() => cerrar(o.valor)}
                                        data-testid={`elegir-${o.valor}`}
                                        className={`w-full text-left rounded-xl border p-3 transition-colors ${oscuro
                                            ? 'border-[#333] hover:border-[#FF671F] hover:bg-[#FF671F]/10'
                                            : 'border-border hover:border-brand hover:bg-brand/5'}`}>
                                        <span className="block text-sm font-semibold">{o.titulo}</span>
                                        {o.detalle && (
                                            <span className={`block text-xs mt-0.5 ${oscuro ? 'text-white/60' : 'text-muted-foreground'}`}>
                                                {o.detalle}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}
                        <DialogFooter>
                            <Button variant="outline"
                                onClick={() => cerrar(nada)}
                                className={oscuro ? 'bg-transparent border-[#333] text-white' : ''}
                                data-testid="confirm-cancel">
                                {dialogo.cancelLabel || 'Cancelar'}
                            </Button>
                            {/* En «elegir» el botón de aceptar no existe: cada opción es su propio
                                botón, así que un «Confirmar» aparte no confirmaría nada. */}
                            {!esElegir && (
                                <Button
                                    onClick={() => cerrar(esPrompt ? texto.trim() : true)}
                                    disabled={!puedeConfirmar}
                                    className={dialogo.danger
                                        ? 'bg-red-600 hover:bg-red-700 text-white'
                                        : 'bg-[#FF671F] hover:bg-[#FF671F]/90 text-white'}
                                    data-testid="confirm-ok">
                                    {dialogo.confirmLabel || 'Confirmar'}
                                </Button>
                            )}
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </ConfirmContext.Provider>
    );
};
