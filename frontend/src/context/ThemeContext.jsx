import React, { createContext, useContext, useEffect, useState } from 'react';
import { guardarAjusteEnFicha } from '../lib/ajustesEnFicha';

const ThemeContext = createContext(null);

export const useTheme = () => {
    const ctx = useContext(ThemeContext);
    if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
    return ctx;
};

export const ThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        const stored = localStorage.getItem('theme');
        // EL OSCURO ES EL DE FÁBRICA (doc 19-08, «en toda la app»): sin elección guardada
        // (ni en el navegador ni en la ficha), la app sale oscura. Lo elegido manda igual.
        return stored === 'dark' || stored === 'light' ? stored : 'dark';
    });

    useEffect(() => {
        const root = document.documentElement;
        if (theme === 'dark') root.classList.add('dark');
        else root.classList.remove('dark');
        root.style.colorScheme = theme;
        localStorage.setItem('theme', theme);
    }, [theme]);

    // El tema guardado en la ficha llega DESPUÉS de montarse esto (lo trae el perfil, ver
    // lib/ajustesEnFicha): se escucha el aviso y se aplica. Así el que eligió claro en el
    // móvil entra claro también en el portátil (doc 19-08, bloque 07).
    useEffect(() => {
        const alLlegarDeLaFicha = (e) => {
            if (e.detail === 'dark' || e.detail === 'light') setTheme(e.detail);
        };
        window.addEventListener('tema-de-ficha', alLlegarDeLaFicha);
        return () => window.removeEventListener('tema-de-ficha', alLlegarDeLaFicha);
    }, []);

    const toggleTheme = () => setTheme(t => {
        const siguiente = t === 'dark' ? 'light' : 'dark';
        guardarAjusteEnFicha('tema', siguiente);
        return siguiente;
    });

    return (
        <ThemeContext.Provider value={{ theme, toggleTheme, setTheme, isDark: theme === 'dark' }}>
            {children}
        </ThemeContext.Provider>
    );
};
