import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ConfirmProvider } from "./components/ui/confirm";
import { OnboardingProvider } from "./context/OnboardingContext";
import { ThemeProvider } from "./context/ThemeContext";

// Pages
import AuthPage from "./pages/AuthPage";
import RecuperarPage from "./pages/RecuperarPage";
import MiCuerpoPage from "./pages/MiCuerpoPage";
import { leerDestino } from "./lib/navegacion";
import { ClientDashboard, ClientLayout } from "./pages/ClientDashboard";
import RoutinePage from "./pages/RoutinePage";
import EntrenoPage from "./pages/EntrenoPage";
import NutritionPage from "./pages/NutritionPage";
import MiSemanaPage from "./pages/MiSemanaPage";
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
import AdminPagosPage from "./pages/AdminPagosPage";
import AdminMessagesPage from "./pages/AdminMessagesPage";
import AdminRoutinesPage from "./pages/AdminRoutinesPage";
import SupplementsPage from "./pages/SupplementsPage";
import CheckInsPage from "./pages/CheckInsPage";
import MacroCalculatorClientPage from "./pages/MacroCalculatorClientPage";
import RevisionPage from "./pages/RevisionPage";
import FoodSearchPage from "./pages/FoodSearchPage";
import AdminFoodSuggestionsPage from "./pages/AdminFoodSuggestionsPage";
import AdminPlansPage from "./pages/AdminPlansPage";
import AdminTareasPage from "./pages/AdminTareasPage";
import AdminPanelesPage from "./pages/AdminPanelesPage";
import QuestionnairePage from "./pages/QuestionnairePage";
import WelcomePage from "./pages/WelcomePage";
import PlanesPage from "./pages/PlanesPage";
import RenovacionPage from "./pages/RenovacionPage";
import QuizVentaPage from "./pages/QuizVentaPage";
import InstallPrompt from "./components/InstallPrompt";
import BarraActuandoComo from "./components/BarraActuandoComo";

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

// A dónde va una dirección que no existe. Al login SOLO si no hay sesión; si el usuario ya
// está dentro se le deja en su panel, que es lo que esperaría de un enlace que no lleva a
// ninguna parte. Mientras se comprueba la sesión no se redirige a nada: hacerlo antes de
// saber quién es era la otra forma de acabar en el login sin motivo.
const ADondeSea = () => {
    const { isAuthenticated, user, loading } = useAuth();
    if (loading) return null;
    if (!isAuthenticated) return <Navigate to="/auth" replace />;
    const esDelEquipo = user?.role === 'admin' || user?.role === 'trainer';
    return <Navigate to={esDelEquipo ? '/admin' : '/dashboard'} replace />;
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
        // Iba a algún sitio antes de identificarse (el test de nivel): manda ahí, no al
        // panel. Ver lib/navegacion: sin esto la venta del test se perdía.
        const pendiente = leerDestino();
        return <Navigate to={pendiente || '/dashboard'} replace />;
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

            {/* El quiz de venta va SIN sesion y sin PublicRoute: "ve su resultado sin dar
                el correo" (parte 10), y PublicRoute redirige al panel al que ya ha
                entrado alguna vez, que es justo a quien se le manda el enlace. */}
            <Route path="/test" element={<QuizVentaPage />} />

            {/* Recuperar la contraseña. SIN PublicRoute a propósito: si no puedes entrar,
                no puedes estar dentro para arreglarlo, y PublicRoute echa de aquí a quien
                tenga sesión abierta -- justo el que llega desde el enlace del correo en
                el móvil donde sigue logueado. */}
            <Route path="/recuperar" element={<RecuperarPage />} />

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
                        {/* Una sola pantalla de planes. /onboarding es la vieja: se hizo
                            para los planes de antes y listaba cualquier plan activo con
                            precio, así que al añadir los tres niveles cogió el Nivel 3
                            con botón de pagar — cuando el documento dice que se contrata
                            hablando. Además le faltaban los textos de los niveles nuevos.
                            Manda /planes, que es la que cumple el documento.
                            Se conserva la query para no perder la vuelta de Stripe de un
                            pago que se hubiera iniciado antes de este cambio. */}
                        <Navigate to={`/planes${window.location.search}`} replace />
                    </ProtectedRoute>
                }
            />

            {/* El regalo del acceso gratis: "te digo cuanto musculo tienes". Pide sesion
                -- hay que registrarse para recibirlo -- pero NO plan: es lo unico de la
                app que se da sin pagar, y ese es justo el punto. */}
            <Route
                path="/mi-cuerpo"
                element={
                    <ProtectedRoute>
                        <MiCuerpoPage />
                    </ProtectedRoute>
                }
            />

            {/* Elegir nivel. Fuera del layout de cliente a proposito: aqui llega tanto
                el que todavia no tiene plan como el que viene a cambiarlo. */}
            <Route
                path="/planes"
                element={
                    <ProtectedRoute>
                        <PlanesPage />
                    </ProtectedRoute>
                }
            />

            {/* La semana 12: el balance del ciclo y las tres salidas */}
            <Route
                path="/renovacion"
                element={
                    <ProtectedRoute>
                        <RenovacionPage />
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
                {/* El registro del entreno del día (T3). Va con la misma llave que la
                    rutina: CAP.RUTINA ya lleva dentro el interruptor `t3_entreno`. */}
                <Route path="entreno" element={<CapabilityRoute cap="rutina"><EntrenoPage /></CapabilityRoute>} />
                <Route path="nutrition" element={<NutritionPage />} />
                {/* Mi semana (rediseño 21-08). Sin entrada en el menú todavía: se llega por URL. */}
                <Route path="semana" element={<MiSemanaPage />} />
                <Route path="reports" element={<CapabilityRoute cap="reportes"><ReportsPage /></CapabilityRoute>} />
                <Route path="messages" element={<MessagesPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="chatbot" element={<ChatbotPage />} />
                <Route path="supplements" element={<CapabilityRoute cap="suplementacion"><SupplementsPage /></CapabilityRoute>} />
                <Route path="checkins" element={<CapabilityRoute cap="reportes"><CheckInsPage /></CapabilityRoute>} />
                <Route path="macro-calculator" element={<MacroCalculatorClientPage />} />
                {/* LOS DOS NOMBRES QUE LA GENTE ESCRIBE (punto 22 del 17-08). `/dashboard/macros`
                    y `/dashboard/my-macros` no estaban declaradas, así que caían en el comodín y
                    acababan en el panel de admin: a Mis macros solo se llegaba pinchando en el
                    menú. Se redirige, no se duplica la pantalla: una ruta, un componente. */}
                <Route path="macros" element={<Navigate to="/dashboard/macro-calculator" replace />} />
                <Route path="my-macros" element={<Navigate to="/dashboard/macro-calculator" replace />} />
                <Route path="foods" element={<FoodSearchPage />} />
                {/* La revisión suelta: pantalla, no popup (documento del 06-08-2026) */}
                <Route path="revision" element={<RevisionPage />} />
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
                {/* El catálogo de planes decide qué incluye cada plan y, dentro, qué
                    pantallas están encendidas para todos los clientes. Mismo candado que
                    Usuarios y Cobros, y el backend lo vuelve a comprobar con
                    `get_admin_only_user` por si alguien llama al endpoint a mano. */}
                <Route path="planes" element={
                    <ProtectedRoute allowedRoles={['admin']}>
                        <AdminPlansPage />
                    </ProtectedRoute>
                } />
                <Route path="clients" element={<AdminClientsList />} />
                <Route path="clients/:clientId" element={<ClientDetailPage />} />
                {/* Las tareas del equipo (doc 19-08, apartado 05): admin y entrenadores,
                    cada uno ve las suyas y las que asignó. */}
                <Route path="tareas" element={<AdminTareasPage />} />
                {/* Los cuatro paneles (doc 19-08, bloque 12). Admin ve los cuatro; el
                    entrenador entra a la misma ruta y la página le enseña solo el suyo.
                    Dirección la protege el backend con get_admin_only_user. */}
                <Route path="paneles" element={<AdminPanelesPage />} />
                <Route path="leads" element={<LeadsPage />} />
                <Route path="messages" element={<AdminMessagesPage />} />
                <Route path="routines" element={<AdminRoutinesPage />} />
                <Route path="supplements-catalog" element={<SupplementsCatalogPage />} />
                <Route path="menus" element={<AdminMenusPage />} />
                <Route path="alimentos" element={<AdminFoodSuggestionsPage />} />
                <Route path="usuarios" element={
                    <ProtectedRoute allowedRoles={['admin']}>
                        <AdminUsersPage />
                    </ProtectedRoute>
                } />
                {/* Lo que ha pagado cada cliente NO es información de entrenamiento, es del
                    negocio: mismo candado que Usuarios, y el backend lo vuelve a comprobar
                    con `get_admin_only_user` por si alguien llama al endpoint a mano. */}
                <Route path="pagos" element={
                    <ProtectedRoute allowedRoles={['admin']}>
                        <AdminPagosPage />
                    </ProtectedRoute>
                } />
            </Route>

            {/* Cualquier dirección que no exista. Antes mandaba al login sin más, así que
                un enlace roto echaba de la app a un cliente con la sesión abierta: es lo que
                pasaba con el aviso de los macros provisionales. Ahora al login solo va quien
                no ha entrado; al que ya está dentro se le deja en su sitio. */}
            <Route path="*" element={<ADondeSea />} />
        </Routes>
    );
}

function App() {
    return (
        <ThemeProvider>
            <BrowserRouter>
                <AuthProvider>
                    <ConfirmProvider>
                        <OnboardingProvider>
                            {/* Arriba del todo y en todas las pantallas: si el entrenador
                                está dentro de la cuenta de un cliente, tiene que verlo esté
                                donde esté (punto 4.11). */}
                            <BarraActuandoComo />
                            <AppRoutes />
                            {/* LOS AVISOS SE CIERRAN, Y SE CIERRAN SOLOS (Jesús, 15-08,
                                fallo 37): no tenían aspa y alguno se quedó minutos tapando
                                el título de un panel. Seis segundos y una cruz en todos; el
                                que necesite más tiempo lo pide en su `duration`.
                                Y ABAJO A LA DERECHA (doc 57, F6): arriba-centro el aviso
                                caía justo encima de las pestañas de comida y se comía los
                                clics mientras estaba visible. */}
                            <Toaster position="bottom-right" richColors closeButton duration={6000} />
                            <InstallPrompt />
                        </OnboardingProvider>
                    </ConfirmProvider>
                </AuthProvider>
            </BrowserRouter>
        </ThemeProvider>
    );
}

export default App;
