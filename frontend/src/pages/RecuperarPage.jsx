/**
 * RecuperarPage - Recuperar la contraseña.
 *
 * Dos pantallas en una, según venga con token o sin él:
 *   - sin token  -> pide el correo y manda el enlace
 *   - con token  -> elige la contraseña nueva (es a donde lleva el correo)
 *
 * Hasta hoy esto no existía: quien perdía la contraseña tenía que escribirle a su
 * entrenador por WhatsApp. Con clientes que conoces se aguanta; con el registro abierto
 * a quien llega de Instagram, y sin entrenador detrás, se rompe el primer día.
 *
 * Pública a propósito: si no puedes entrar, no puedes estar dentro para arreglarlo.
 */
import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Mail, Lock, Loader2, ArrowLeft, Check } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';

const API = process.env.REACT_APP_BACKEND_URL || '';

/**
 * El marco (logo, centrado y el "Volver a entrar") vive FUERA de RecuperarPage a propósito.
 *
 * Cuando estaba definido dentro, cada render creaba una función Marco nueva; React la veía
 * como otro tipo de componente y desmontaba y volvía a montar el formulario entero. Como el
 * formulario es controlado, eso pasaba en cada tecla: el input se quedaba sin foco y solo
 * entraba una letra por clic. Medido el 13-08 escribiendo "prueba@correo.com": quedaba "p".
 *
 * Definido aquí arriba la identidad no cambia entre renders, así que el input es el mismo
 * nodo del DOM de principio a fin y conserva el foco.
 */
const Marco = ({ children }) => {
    const navigate = useNavigate();
    return (
        <div className="min-h-screen bg-black flex flex-col items-center justify-center p-6">
            <div className="w-full max-w-sm flex flex-col items-center">
                <div className="mb-10"><Logo12EN12 size="lg" /></div>
                {children}
                <button onClick={() => navigate('/auth')}
                    className="mt-8 inline-flex items-center gap-1.5 text-white/50 hover:text-white text-sm transition-colors">
                    <ArrowLeft className="w-4 h-4" /> Volver a entrar
                </button>
            </div>
        </div>
    );
};

const RecuperarPage = () => {
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const token = params.get('token');

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [repetida, setRepetida] = useState('');
    const [cargando, setCargando] = useState(false);
    const [enviado, setEnviado] = useState(false);
    const [listo, setListo] = useState(false);

    const pedirEnlace = async (e) => {
        e.preventDefault();
        setCargando(true);
        try {
            await axios.post(`${API}/api/auth/forgot-password`, { email: email.trim() });
            // Sale lo mismo exista o no la cuenta: decir "ese correo no está registrado"
            // convertiría esta pantalla en una forma de averiguar quién es cliente.
            setEnviado(true);
        } catch {
            toast.error('No hemos podido enviarlo. Inténtalo en un momento.');
        } finally {
            setCargando(false);
        }
    };

    const cambiar = async (e) => {
        e.preventDefault();
        if (password !== repetida) { toast.error('Las dos contraseñas no coinciden'); return; }
        if (password.length < 8) { toast.error('La contraseña debe tener al menos 8 caracteres'); return; }
        setCargando(true);
        try {
            await axios.post(`${API}/api/auth/reset-password`, { token, password });
            setListo(true);
            setTimeout(() => navigate('/auth'), 2200);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'No hemos podido cambiarla');
        } finally {
            setCargando(false);
        }
    };

    if (listo) {
        return (
            <Marco>
                <div className="text-center" data-testid="recuperar-listo">
                    <div className="w-14 h-14 rounded-full bg-brand/20 flex items-center justify-center mx-auto mb-4">
                        <Check className="w-7 h-7 text-brand" />
                    </div>
                    <p className="text-white font-bold text-lg">Contraseña cambiada</p>
                    <p className="text-white/60 text-sm mt-1">Te llevamos a la pantalla de entrar.</p>
                </div>
            </Marco>
        );
    }

    // ── Con token: elegir la nueva ────────────────────────────────────────────
    if (token) {
        return (
            <Marco>
                <h1 className="text-white text-2xl font-bold mb-2">Elige tu contraseña</h1>
                <p className="text-white/60 text-sm mb-8 text-center">Al menos 8 caracteres.</p>
                <form onSubmit={cambiar} className="w-full space-y-4">
                    {[['Nueva contraseña', password, setPassword, 'recuperar-password'],
                      ['Repítela', repetida, setRepetida, 'recuperar-repetida']].map(([ph, val, set, tid]) => (
                        <div className="relative" key={tid}>
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand/20 flex items-center justify-center">
                                <Lock className="w-3 h-3 text-brand" />
                            </div>
                            <input type="password" placeholder={ph} value={val} required minLength={8}
                                onChange={(e) => set(e.target.value)} data-testid={tid}
                                className="w-full pl-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand outline-none" />
                        </div>
                    ))}
                    <button type="submit" disabled={cargando} data-testid="recuperar-guardar"
                        className="w-full h-14 rounded-xl bg-brand hover:bg-brand/90 text-white font-bold disabled:opacity-60 flex items-center justify-center gap-2">
                        {cargando ? <><Loader2 className="w-4 h-4 animate-spin" /> Guardando...</> : 'Guardar'}
                    </button>
                </form>
            </Marco>
        );
    }

    // ── Sin token: pedir el enlace ────────────────────────────────────────────
    return (
        <Marco>
            {enviado ? (
                <div className="text-center" data-testid="recuperar-enviado">
                    <div className="w-14 h-14 rounded-full bg-brand/20 flex items-center justify-center mx-auto mb-4">
                        <Mail className="w-7 h-7 text-brand" />
                    </div>
                    <p className="text-white font-bold text-lg">Mira tu correo</p>
                    <p className="text-white/60 text-sm mt-2">
                        Si ese correo tiene cuenta, te llega un enlace en un minuto. Vale dos horas.
                    </p>
                </div>
            ) : (
                <>
                    <h1 className="text-white text-2xl font-bold mb-2">¿Se te ha olvidado?</h1>
                    <p className="text-white/60 text-sm mb-8 text-center">
                        Dinos tu correo y te mandamos un enlace para elegir otra.
                    </p>
                    <form onSubmit={pedirEnlace} className="w-full space-y-4">
                        <div className="relative">
                            <div className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-brand/20 flex items-center justify-center">
                                <Mail className="w-3 h-3 text-brand" />
                            </div>
                            <input type="email" placeholder="Tu correo" value={email} required
                                onChange={(e) => setEmail(e.target.value)} data-testid="recuperar-email"
                                className="w-full pl-12 h-14 bg-bg-input-dark border-0 text-white placeholder:text-white/40 rounded-xl focus:ring-2 focus:ring-brand outline-none" />
                        </div>
                        <button type="submit" disabled={cargando} data-testid="recuperar-pedir"
                            className="w-full h-14 rounded-xl bg-brand hover:bg-brand/90 text-white font-bold disabled:opacity-60 flex items-center justify-center gap-2">
                            {cargando ? <><Loader2 className="w-4 h-4 animate-spin" /> Enviando...</> : 'Enviar el enlace'}
                        </button>
                    </form>
                </>
            )}
        </Marco>
    );
};

export default RecuperarPage;
