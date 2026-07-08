import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Search, Dumbbell, ChevronRight } from 'lucide-react';
import { PlanBadge } from './ClientDashboard';

// Vista general de rutinas: quien tiene rutina activa y quien no.
// La rutina se genera/edita dentro de la ficha del cliente (pestaña Entreno).
const AdminRoutinesPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [onlyMissing, setOnlyMissing] = useState(false);

    useEffect(() => {
        api.get('/admin/routines/overview')
            .then(r => setRows(r.data || []))
            .catch(() => toast.error('Error cargando rutinas'))
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filtered = rows.filter(r =>
        (!onlyMissing || !r.has_routine) &&
        (!search || r.name?.toLowerCase().includes(search.toLowerCase()) || r.email?.toLowerCase().includes(search.toLowerCase()))
    );
    const withRoutine = rows.filter(r => r.has_routine).length;

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="admin-routines-page">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>RUTINAS</h1>
                <p className="text-white/40 text-sm">
                    {withRoutine} de {rows.length} clientes con rutina activa
                    {rows.length - withRoutine > 0 && <span className="text-yellow-400"> · {rows.length - withRoutine} sin rutina</span>}
                </p>
            </div>

            <div className="flex flex-col md:flex-row gap-3">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar cliente..." className="pl-9 bg-[#111] border-[#222] text-white" data-testid="routines-search" />
                </div>
                <button onClick={() => setOnlyMissing(v => !v)}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${onlyMissing ? 'bg-[#FF671F] text-white border-[#FF671F]' : 'bg-[#111] text-white/60 border-[#222] hover:text-white'}`}
                    data-testid="only-missing-toggle">
                    Solo sin rutina
                </button>
            </div>

            <Card className="bg-[#111] border-[#222]">
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-white/40 text-xs uppercase border-b border-[#222]">
                                    <th className="px-4 py-3">Cliente</th>
                                    <th className="px-4 py-3 hidden sm:table-cell">Plan</th>
                                    <th className="px-4 py-3">Rutina</th>
                                    <th className="px-4 py-3 hidden md:table-cell">Días de entreno</th>
                                    <th className="px-4 py-3 hidden lg:table-cell">Generada</th>
                                    <th className="px-4 py-3 text-right"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(r => (
                                    <tr key={r.client_id} className="border-b border-[#1a1a1a] cursor-pointer hover:bg-white/5"
                                        onClick={() => navigate(`/admin/clients/${r.client_id}`)} data-testid={`routine-row-${r.client_id}`}>
                                        <td className="px-4 py-3">
                                            <p className="text-white font-medium">{r.name || '-'}</p>
                                            <p className="text-white/40 text-xs">{r.email}</p>
                                        </td>
                                        <td className="px-4 py-3 hidden sm:table-cell"><PlanBadge plan={r.plan} /></td>
                                        <td className="px-4 py-3">
                                            {r.has_routine
                                                ? <Badge className="bg-green-500/15 text-green-500 border-0">Activa</Badge>
                                                : <Badge className="bg-yellow-500/15 text-yellow-400 border-0">Sin rutina</Badge>}
                                        </td>
                                        <td className="px-4 py-3 text-white/60 hidden md:table-cell">{r.has_routine ? `${r.training_days} días` : '-'}</td>
                                        <td className="px-4 py-3 text-white/40 text-xs hidden lg:table-cell">
                                            {r.routine_created_at ? new Date(r.routine_created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' }) : '-'}
                                        </td>
                                        <td className="px-4 py-3 text-right"><ChevronRight className="w-4 h-4 text-white/30 inline" /></td>
                                    </tr>
                                ))}
                                {filtered.length === 0 && (
                                    <tr><td colSpan={6} className="px-4 py-10 text-center text-white/30">
                                        <Dumbbell className="w-8 h-8 mx-auto mb-2 text-white/15" />
                                        {onlyMissing ? 'Todos los clientes tienen rutina' : 'Sin clientes'}
                                    </td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
            <p className="text-white/25 text-xs">La rutina se genera y edita dentro de la ficha del cliente, pestaña Entreno.</p>
        </div>
    );
};

export default AdminRoutinesPage;
