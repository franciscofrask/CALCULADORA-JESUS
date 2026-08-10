import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { deriveCapabilities } from '../lib/planAccess';
import { limpiarLoDeLaPersona } from '../lib/almacenLocal';

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

    // ACTUAR COMO UN CLIENTE (punto 4.11). Cuando el entrenador abre la calculadora de un
    // cliente desde su ficha, la app entera trabaja como ese cliente: cada petición lleva la
    // cabecera y el backend resuelve el usuario ahí (ver core/actuar_como.py). Así funcionan
    // las dietas, el reparto, el buscador, el sugeridor y el recetario sin duplicar media API.
    //
    // Vive en sessionStorage y no en localStorage a propósito: se acaba al cerrar la pestaña.
    // Quedarse "actuando como" otra persona sin darte cuenta, y encima entre reinicios del
    // navegador, es exactamente lo que no puede pasar.
    const actuandoComo = (() => {
        try { return JSON.parse(sessionStorage.getItem('actuar_como') || 'null'); }
        catch { return null; }
    })();

    const api = axios.create({
        baseURL: API,
        headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(actuandoComo?.userId ? { 'X-Actuar-Como': actuandoComo.userId } : {}),
        },
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
            // Un reintento si la primera no llega. Conservar el token ya evita tener que
            // volver a escribir la contraseña, pero sin esto la app te deja igualmente en la
            // pantalla de login hasta que recargues. Un corte de un segundo -- entrar en el
            // metro, el servidor terminando de arrancar -- se recupera solo.
            let response;
            try {
                response = await api.get('/auth/me');
            } catch (primera) {
                if (primera.response) throw primera;      // el servidor contestó: no insistas
                await new Promise((r) => setTimeout(r, 1500));
                response = await api.get('/auth/me');
            }
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
            // UN FALLO DE RED NO ES UNA SESIÓN CADUCADA.
            //
            // Aquí se llamaba a `logout()` ante CUALQUIER excepción, y eso incluye el
            // «Network Error» de axios: sin cobertura, wifi que se cae, servidor
            // reiniciándose. O sea que abrir la app en el ascensor te echaba, y no solo eso:
            // `logout()` llama a `limpiarLoDeLaPersona()`, así que además te borraba la copia
            // local del día de Nutrición. Volvías a entrar y te faltaba lo del día.
            //
            // Salió buscando otra cosa: la sesión del entorno local se caía cada dos por tres
            // y parecía que alguien pulsaba «Cerrar sesión». No: era el backend reiniciándose
            // (recarga automática al guardar un fichero) mientras el navegador preguntaba
            // quién eres. En un móvil con mala cobertura pasa exactamente lo mismo.
            //
            // Solo se cierra sesión si el SERVIDOR dice que el token no vale. Los 401 de
            // verdad los recoge además el interceptor de arriba, que avisa al cliente.
            const status = error.response?.status;
            if (status === 401 || status === 403) {
                logout();
            } else {
                // Se conserva el token: al recuperar la conexión, recargar devuelve la sesión
                // sin volver a escribir la contraseña.
                console.error('No se pudo comprobar la sesión (se conserva):', error?.message || error);
            }
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
        // La conversación del chatbot caduca al cerrar sesión: se borra en el backend
        // (mejor esfuerzo: si el token ya expiró, el TTL de 7 días la limpiará igual)
        // y se descarta el snapshot local para que no reaparezca en el próximo login.
        const hadToken = localStorage.getItem('token');
        if (hadToken) {
            try { api.delete('/chatbot/sessions').catch(() => {}); } catch (e) {}
        }
        try { sessionStorage.removeItem('chatbot_session_state'); } catch (e) {}
        // Y TODO LO DEMÁS QUE SEA DE ESTA PERSONA (punto 4.7). No solo la conversación: la
        // copia local del día de Nutrición se quedaba puesta, y el siguiente que entrara en
        // este navegador se encontraba los alimentos del anterior -- y al guardar, se los
        // metía en su propia dieta. Se queda lo que es del aparato (tema, barra lateral).
        limpiarLoDeLaPersona();
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

    // Empezar y dejar de actuar como un cliente (punto 4.11). Recarga a propósito: la app
    // entera tiene que recomponerse con el otro usuario -- perfil, macros, capacidades --, y
    // hacerlo a medias es peor que no hacerlo.
    const actuarComo = (cliente) => {
        sessionStorage.setItem('actuar_como', JSON.stringify({
            userId: cliente.userId, nombre: cliente.nombre, clientId: cliente.clientId,
        }));
        window.location.assign('/dashboard/nutrition');
    };
    const dejarDeActuar = () => {
        const vuelta = actuandoComo?.clientId ? `/admin/clients/${actuandoComo.clientId}` : '/admin/clients';
        sessionStorage.removeItem('actuar_como');
        window.location.assign(vuelta);
    };

    const value = {
        user,
        token,
        profile,
        loading,
        login,
        register,
        logout,
        actuandoComo,
        actuarComo,
        dejarDeActuar,
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
