import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

// variant: 'sidebar' (fila en nav oscura) | 'icon' (botón compacto)
const ThemeToggle = ({ variant = 'sidebar', className = '', testId = 'theme-toggle' }) => {
    const { isDark, toggleTheme } = useTheme();

    if (variant === 'icon') {
        return (
            <button onClick={toggleTheme} data-testid={testId}
                aria-label={isDark ? 'Activar modo claro' : 'Activar modo oscuro'}
                className={`w-10 h-10 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10 transition-colors ${className}`}>
                {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
        );
    }

    return (
        <button onClick={toggleTheme} data-testid={testId}
            aria-label={isDark ? 'Activar modo claro' : 'Activar modo oscuro'}
            className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/[0.07] transition-colors ${className}`}>
            <span className="relative w-9 h-5 rounded-full bg-white/15 flex items-center flex-shrink-0">
                <span className={`absolute w-4 h-4 rounded-full bg-brand flex items-center justify-center transition-transform duration-300 ${isDark ? 'translate-x-4' : 'translate-x-0.5'}`}>
                    {isDark ? <Moon className="w-2.5 h-2.5 text-white" /> : <Sun className="w-2.5 h-2.5 text-white" />}
                </span>
            </span>
            <span className="text-sm">{isDark ? 'Modo oscuro' : 'Modo claro'}</span>
        </button>
    );
};

export default ThemeToggle;
