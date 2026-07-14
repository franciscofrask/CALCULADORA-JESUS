import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { OnboardingProvider } from "./context/OnboardingContext";
import { ThemeProvider } from "./context/ThemeContext";

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
import LeadsPage from "./pages/LeadsPage";
import ChatbotPage from "./pages/ChatbotPage";
import SupplementsCatalogPage from "./pages/SupplementsCatalogPage";
import AdminMenusPage from "./pages/AdminMenusPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AdminMessagesPage from "./pages/AdminMessagesPage";
import AdminRoutinesPage from "./pages/AdminRoutinesPage";
import SupplementsPage from "./pages/SupplementsPage";
import CheckInsPage from "./pages/CheckInsPage";
import MacroCalculatorClientPage from "./pages/MacroCalculatorClientPage";
import FoodSearchPage from "./pages/FoodSearchPage";
import AdminFoodSuggestionsPage from "./pages/AdminFoodSuggestionsPage";
import AdminPlansPage from "./pages/AdminPlansPage";
import QuestionnairePage from "./pages/QuestionnairePage";
import WelcomePage from "./pages/WelcomePage";

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

// Capability Route - gate a page by a plan capability (ver lib/planAccess.js).
// Si el plan del usuario no la habilita, redirige al inicio del panel.
const CapabilityRoute = ({ cap, children }) => {
    const { can, loading } = useAuth();
    if (loading) return null;
    if (!can(cap)) return <Navigate to="/dashboard" replace />;
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
        if (user?.role === 'admin' || user?.role === 'trainer') {
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

            {/* Cuestionario inicial obligatorio (antes del plan) */}
            <Route
                path="/questionnaire"
                element={
                    <ProtectedRoute>
                        <QuestionnairePage />
                    </ProtectedRoute>
                }
            />

            {/* Bienvenida tras el cuestionario (muestra macros + primer paso) */}
            <Route
                path="/welcome"
                element={
                    <ProtectedRoute>
                        <WelcomePage />
                    </ProtectedRoute>
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
                <Route path="routine" element={<CapabilityRoute cap="rutina"><RoutinePage /></CapabilityRoute>} />
                <Route path="nutrition" element={<NutritionPage />} />
                <Route path="reports" element={<CapabilityRoute cap="reportes"><ReportsPage /></CapabilityRoute>} />
                <Route path="messages" element={<MessagesPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="chatbot" element={<ChatbotPage />} />
                <Route path="supplements" element={<CapabilityRoute cap="suplementacion"><SupplementsPage /></CapabilityRoute>} />
                <Route path="checkins" element={<CapabilityRoute cap="reportes"><CheckInsPage /></CapabilityRoute>} />
                <Route path="macro-calculator" element={<MacroCalculatorClientPage />} />
                <Route path="foods" element={<FoodSearchPage />} />
            </Route>

            {/* Admin Routes */}
            <Route
                path="/admin"
                element={
                    <ProtectedRoute allowedRoles={['admin', 'trainer']}>
                        <AdminLayout />
                    </ProtectedRoute>
                }
            >
                <Route index element={<AdminDashboard />} />
                <Route path="planes" element={<AdminPlansPage />} />
                <Route path="clients" element={<AdminClientsList />} />
                <Route path="clients/:clientId" element={<ClientDetailPage />} />
                <Route path="leads" element={<LeadsPage />} />
                <Route path="messages" element={<AdminMessagesPage />} />
                <Route path="routines" element={<AdminRoutinesPage />} />
                <Route path="supplements-catalog" element={<SupplementsCatalogPage />} />
                <Route path="menus" element={<AdminMenusPage />} />
                <Route path="alimentos" element={<AdminFoodSuggestionsPage />} />
                <Route path="usuarios" element={<AdminUsersPage />} />
            </Route>

            {/* Catch all */}
            <Route path="*" element={<Navigate to="/auth" replace />} />
        </Routes>
    );
}

function App() {
    return (
        <ThemeProvider>
            <BrowserRouter>
                <AuthProvider>
                    <OnboardingProvider>
                        <AppRoutes />
                        <Toaster position="top-center" richColors />
                    </OnboardingProvider>
                </AuthProvider>
            </BrowserRouter>
        </ThemeProvider>
    );
}

export default App;
