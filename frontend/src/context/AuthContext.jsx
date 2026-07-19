import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { deriveCapabilities } from '../lib/planAccess';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState(null);
    const [planCatalog, setPlanCatalog] = useState({});

    const api = axios.create({
        baseURL: API,
        headers: token ? { Authorization: `Bearer ${token}` } : {}
    });

    api.interceptors.response.use(
        (response) => response,
        (error) => {
            if (error.response?.status === 401) {
                const url = error.config?.url || '';
                const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register');
                const hadToken = !!localStorage.getItem('token');
                // Solo avisar de sesión expirada si el usuario estaba logueado y no es un
                // intento de login/registro (esos muestran su propio error). El id evita
                // que varios 401 simultáneos apilen el mismo aviso.
                if (hadToken && !isAuthEndpoint) {
                    toast.error('Tu sesión ha expirado. Vuelve a iniciar sesión.', { id: 'session-expired' });
                }
                logout();
            }
            return Promise.reject(error);
        }
    );

    const fetchUser = useCallback(async () => {
        if (!token) {
            setLoading(false);
            return;
        }
        
        try {
            const response = await api.get('/auth/me');
            setUser(response.data);

            // Cargar perfil de cliente si existe (el staff tambien puede tener uno, p.ej. con plan)
            try {
                const profileRes = await api.get('/clients/profile');
                setProfile(profileRes.data);
            } catch (e) {
                // No profile yet
                setProfile(null);
            }
        } catch (error) {
            console.error('Error fetching user:', error);
            logout();
        } finally {
            setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- api recreado cada render; refetch solo en cambio de token
    }, [token]);

    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    // Catálogo de planes (público): fuente única de habilitaciones/ciclos/precios.
    useEffect(() => {
        axios.get(`${API}/plans`)
            .then((res) => setPlanCatalog(res.data || {}))
            .catch(() => setPlanCatalog({}));
    }, []);

    const login = async (email, password) => {
        const response = await api.post('/auth/login', { email, password });
        const { access_token, user: userData } = response.data;
        
        localStorage.setItem('token', access_token);
        setToken(access_token);
        setUser(userData);
        
        // Cargar perfil de cliente si existe (staff incluido)
        try {
            const profileRes = await axios.get(`${API}/clients/profile`, {
                headers: { Authorization: `Bearer ${access_token}` }
            });
            setProfile(profileRes.data);
        } catch (e) {
            setProfile(null);
        }
        
        return userData;
    };

    const register = async (data) => {
        const response = await api.post('/auth/register', data);
        const { access_token, user: userData } = response.data;
        
        localStorage.setItem('token', access_token);
        setToken(access_token);
        setUser(userData);
        
        return userData;
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
        setProfile(null);
    };

    const updateProfile = (newProfile) => {
        setProfile(newProfile);
    };

    const refreshProfile = async () => {
        if (token) {
            try {
                const profileRes = await api.get('/clients/profile');
                setProfile(profileRes.data);
            } catch (e) {
                setProfile(null);
            }
        }
    };

    // Un checkout de Stripe iniciado y nunca pagado deja el perfil en pendiente_pago
    // con checkout_status draft/created: NO cuenta como plan contratado en toda la app.
    // Los perfiles antiguos de pagos manuales no tienen checkout_status y no entran aquí.
    const planUnpaid = !!(profile
        && profile.status === 'pendiente_pago'
        && ['draft', 'created'].includes(profile.checkout_status));

    // Plan del usuario actual (entrada del catálogo), sus habilitaciones y capacidades.
    const myPlan = useMemo(
        () => (profile?.plan && !planUnpaid ? planCatalog[profile.plan] || null : null),
        [profile?.plan, planUnpaid, planCatalog]
    );
    const habilitaciones = myPlan?.habilitaciones || null;
    const capabilities = useMemo(() => deriveCapabilities(habilitaciones), [habilitaciones]);
    // can(cap): ¿el plan del usuario habilita esta capacidad?
    // - MIENTRAS CARGA (perfil o catálogo sin resolver): true, para no parpadear.
    // - CARGADO y sin plan contratado (sin perfil, pago pendiente o plan desconocido):
    //   false. Antes abría por defecto y un registro sin plan veía TODAS las
    //   funcionalidades (rutina, reportes, suplementos...).
    const can = useCallback(
        (cap) => {
            if (loading || !Object.keys(planCatalog).length) return true;
            if (!myPlan) return false;
            return !!capabilities[cap];
        },
        [loading, planCatalog, myPlan, capabilities]
    );

    const value = {
        user,
        token,
        profile,
        loading,
        login,
        register,
        logout,
        updateProfile,
        refreshProfile,
        refreshUser: fetchUser,
        api,
        planCatalog,
        myPlan,
        planUnpaid,
        habilitaciones,
        capabilities,
        can,
        isAuthenticated: !!token && !!user,
        isAdmin: user?.role === 'admin',
        isTrainer: user?.role === 'trainer',
        isClient: user?.role === 'client'
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
