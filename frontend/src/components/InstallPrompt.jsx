import React, { useEffect, useState } from 'react';
import { X, Download, Share } from 'lucide-react';

// Aviso de instalación de la PWA.
// - Android / Chrome / Edge: el navegador dispara `beforeinstallprompt`; lo
//   guardamos y enseñamos nuestro banner con el botón Instalar (prompt nativo).
// - iPhone/iPad (Safari): no existe ese evento; enseñamos la instrucción de
//   "Compartir > Añadir a pantalla de inicio" una vez, descartable.
const DISMISS_KEY = 'install-prompt-dismissed';

const esIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const yaInstalada = () =>
    window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

const InstallPrompt = () => {
    const [deferred, setDeferred] = useState(null);
    const [showIOS, setShowIOS] = useState(false);

    useEffect(() => {
        if (yaInstalada() || localStorage.getItem(DISMISS_KEY)) return;

        const onPrompt = (e) => {
            e.preventDefault();   // sin esto Chrome enseña (o no) su mini-aviso y lo pierde
            setDeferred(e);
        };
        window.addEventListener('beforeinstallprompt', onPrompt);

        if (esIOS()) setShowIOS(true);
        return () => window.removeEventListener('beforeinstallprompt', onPrompt);
    }, []);

    const dismiss = () => {
        localStorage.setItem(DISMISS_KEY, '1');
        setDeferred(null);
        setShowIOS(false);
    };

    const instalar = async () => {
        if (!deferred) return;
        deferred.prompt();
        try { await deferred.userChoice; } finally { dismiss(); }
    };

    if (!deferred && !showIOS) return null;

    return (
        <div className="fixed bottom-20 lg:bottom-4 left-1/2 -translate-x-1/2 z-[60] w-[calc(100%-2rem)] max-w-md">
            <div className="bg-[#111111] border border-[#333] rounded-2xl shadow-2xl p-4 flex items-center gap-3">
                <img src="/icons/icon-192.png" alt="12EN12" className="w-11 h-11 rounded-xl flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-bold">Instala 12EN12 en tu dispositivo</p>
                    {deferred ? (
                        <p className="text-white/50 text-xs">Acceso directo, pantalla completa y más rápida.</p>
                    ) : (
                        <p className="text-white/50 text-xs flex items-center gap-1 flex-wrap">
                            Toca <Share className="w-3.5 h-3.5 inline text-white/70" /> Compartir y luego
                            <span className="font-semibold text-white/70">"Añadir a pantalla de inicio"</span>
                        </p>
                    )}
                </div>
                {deferred && (
                    <button onClick={instalar} data-testid="install-app-btn"
                        className="flex-shrink-0 bg-[#FF671F] hover:bg-[#e55a15] text-white text-sm font-bold px-4 py-2 rounded-full flex items-center gap-1.5 transition-colors">
                        <Download className="w-4 h-4" /> Instalar
                    </button>
                )}
                <button onClick={dismiss} aria-label="Cerrar" className="flex-shrink-0 text-white/40 hover:text-white p-1">
                    <X className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

export default InstallPrompt;
