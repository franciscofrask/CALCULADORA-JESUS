// SOLO MODO OSCURO, por decisión de Jesús (doc 21-08): el tema claro se quitó entero.
// Ya no hay estado, ni localStorage, ni toggle: la app es oscura siempre. Este contexto
// se queda para que los `useTheme()` repartidos por la app sigan funcionando sin tocarlos.
import React, { createContext, useContext, useEffect } from 'react';

const ThemeContext = createContext(null);

export const useTheme = () => {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
    return ctx;
};

export const ThemeProvider = ({ children }) => {
    useEffect(() => {
        const root = document.documentElement;
        root.classList.add('dark');
        root.style.colorScheme = 'dark';
    }, []);

    return (
        <ThemeContext.Provider value={{ theme: 'dark', isDark: true }}>
            {children}
        </ThemeContext.Provider>
    );
};
