/**
 * Diálogos de confirmación y de texto propios de la app.
 *
 * Sustituyen a window.confirm y window.prompt, que además de no pegar con el diseño
 * bloquean la pestaña entera mientras están abiertos (y en móvil salen con el nombre
 * del dominio delante). Se usan igual de fácil, pero con await:
 *
 *   const { confirm, prompt } = useConfirm();
 *   if (!(await confirm({ title: '¿Borrar el menú?', danger: true }))) return;
 *   const motivo = await prompt({ title: 'Motivo del rechazo', optional: true });
 *
 * confirm devuelve true/false; prompt devuelve el texto o null si se cancela.
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

    const cerrar = (valor) => {
        setDialogo(null);
        if (resolver.current) { resolver.current(valor); resolver.current = null; }
    };

    const esPrompt = dialogo?.modo === 'prompt';
    const puedeConfirmar = !esPrompt || dialogo?.optional || texto.trim().length > 0;

    return (
        <ConfirmContext.Provider value={{ confirm, prompt }}>
            {children}
            <Dialog open={!!dialogo} onOpenChange={(o) => { if (!o) cerrar(esPrompt ? null : false); }}>
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
                        <DialogFooter>
                            <Button variant="outline"
                                onClick={() => cerrar(esPrompt ? null : false)}
                                className={oscuro ? 'bg-transparent border-[#333] text-white' : ''}
                                data-testid="confirm-cancel">
                                {dialogo.cancelLabel || 'Cancelar'}
                            </Button>
                            <Button
                                onClick={() => cerrar(esPrompt ? texto.trim() : true)}
                                disabled={!puedeConfirmar}
                                className={dialogo.danger
                                    ? 'bg-red-600 hover:bg-red-700 text-white'
                                    : 'bg-[#FF671F] hover:bg-[#FF671F]/90 text-white'}
                                data-testid="confirm-ok">
                                {dialogo.confirmLabel || 'Confirmar'}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </ConfirmContext.Provider>
    );
};
