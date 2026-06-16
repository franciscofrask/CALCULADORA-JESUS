import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

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

    const api = axios.create({
        baseURL: API,
        headers: token ? { Authorization: `Bearer ${token}` } : {}
    });

    api.interceptors.response.use(
        (response) => response,
        (error) => {
            if (error.response?.status === 401) {
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
            
            // Fetch profile if client
            if (response.data.role === 'client') {
                try {
                    const profileRes = await api.get('/clients/profile');
                    setProfile(profileRes.data);
                } catch (e) {
                    // No profile yet
                    setProfile(null);
                }
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

    const login = async (email, password) => {
        const response = await api.post('/auth/login', { email, password });
        const { access_token, user: userData } = response.data;
        
        localStorage.setItem('token', access_token);
        setToken(access_token);
        setUser(userData);
        
        // Fetch profile
        if (userData.role === 'client') {
            try {
                const profileRes = await axios.get(`${API}/clients/profile`, {
                    headers: { Authorization: `Bearer ${access_token}` }
                });
                setProfile(profileRes.data);
            } catch (e) {
                setProfile(null);
            }
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
        api,
        isAuthenticated: !!token && !!user,
        isAdmin: user?.role === 'admin' || user?.role === 'operations',
        isTrainer: user?.role === 'trainer',
        isClient: user?.role === 'client'
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
