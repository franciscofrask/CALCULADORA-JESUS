import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Utensils, Dumbbell, Calculator, Menu } from 'lucide-react';

const BottomNav = () => {
    const location = useLocation();

    const navItems = [
        { path: '/dashboard', icon: Home, label: 'Inicio', emoji: '🏠' },
        { path: '/dashboard/nutrition', icon: Utensils, label: 'Nutrición', emoji: '🍽️' },
        { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina', emoji: '💪' },
        { path: '/dashboard/macro-calculator', icon: Calculator, label: 'Macros', emoji: '🔢' },
        { path: '/dashboard/profile', icon: Menu, label: 'Más', emoji: '≡' },
    ];

    const isActive = (path) => {
        if (path === '/dashboard') {
            return location.pathname === '/dashboard';
        }
        return location.pathname.startsWith(path);
    };

    return (
        <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-lg md:hidden" data-testid="bottom-nav">
            <div className="flex items-center justify-around h-16 px-2">
                {navItems.map((item) => {
                    const active = isActive(item.path);
                    return (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`flex flex-col items-center justify-center flex-1 py-2 transition-all duration-200 ${
                                active ? 'text-brand-orange' : 'text-gray-500'
                            }`}
                            data-testid={`nav-${item.label.toLowerCase()}`}
                        >
                            <item.icon 
                                className={`w-5 h-5 mb-1 transition-all duration-200 ${
                                    active ? 'text-brand-orange scale-110' : 'text-gray-400'
                                }`} 
                                strokeWidth={active ? 2.5 : 2}
                            />
                            <span className={`text-xs font-medium ${active ? 'font-bold' : ''}`}>
                                {item.label}
                            </span>
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
};

export default BottomNav;
