import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";

// Pages
import AuthPage from "./pages/AuthPage";
import OnboardingPage from "./pages/OnboardingPage";
import { ClientDashboard, ClientLayout } from "./pages/ClientDashboard";
import RoutinePage from "./pages/RoutinePage";
import NutritionPage from "./pages/NutritionPage";
import ReportsPage from "./pages/ReportsPage";
import MessagesPage from "./pages/MessagesPage";
import ProfilePage from "./pages/ProfilePage";
import { AdminDashboard, AdminClientsList, AdminLayout } from "./pages/AdminDashboard";
import ClientDetailPage from "./pages/ClientDetailPage";
import ChatbotPage from "./pages/ChatbotPage";

// Protected Route Component
const ProtectedRoute = ({ children, allowedRoles }) => {
    const { isAuthenticated, user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/auth" replace />;
    }

    if (allowedRoles && !allowedRoles.includes(user?.role)) {
        return <Navigate to="/dashboard" replace />;
    }

    return children;
};

// Public Route - Redirect if authenticated
const PublicRoute = ({ children }) => {
    const { isAuthenticated, user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (isAuthenticated) {
        if (user?.role === 'admin' || user?.role === 'operations') {
            return <Navigate to="/admin" replace />;
        }
        return <Navigate to="/dashboard" replace />;
    }

    return children;
};

function AppRoutes() {
    return (
        <Routes>
            {/* Public Routes */}
            <Route path="/" element={<Navigate to="/auth" replace />} />
            <Route
                path="/auth"
                element={
                    <PublicRoute>
                        <AuthPage />
                    </PublicRoute>
                }
            />

            {/* Onboarding */}
            <Route
                path="/onboarding"
                element={
                    <ProtectedRoute>
                        <OnboardingPage />
                    </ProtectedRoute>
                }
            />

            {/* Client Routes */}
            <Route
                path="/dashboard"
                element={
                    <ProtectedRoute>
                        <ClientLayout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<ClientDashboard />} />
                <Route path="routine" element={<RoutinePage />} />
                <Route path="nutrition" element={<NutritionPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="messages" element={<MessagesPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="chatbot" element={<ChatbotPage />} />
            </Route>

            {/* Admin Routes */}
            <Route
                path="/admin"
                element={
                    <ProtectedRoute allowedRoles={['admin', 'operations', 'trainer']}>
                        <AdminLayout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<AdminDashboard />} />
                <Route path="clients" element={<AdminClientsList />} />
                <Route path="clients/:clientId" element={<ClientDetailPage />} />
                <Route path="routines" element={<AdminClientsList />} />
                <Route path="payments" element={<AdminDashboard />} />
            </Route>

            {/* Catch all */}
            <Route path="*" element={<Navigate to="/auth" replace />} />
        </Routes>
    );
}

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <AppRoutes />
                <Toaster position="top-center" richColors />
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
