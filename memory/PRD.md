# JG12↗ - Plataforma Jesús Gallego Trainer

## Documento de Requisitos del Producto (PRD)

### Fecha de creación: 6 de marzo de 2026
### Última actualización: 6 de marzo de 2026
### Estado: MVP Completado + Branding Oficial

---

## 1. Descripción General

**12EN12** es una plataforma de gestión de entrenamiento personal online para Gallego Trainer Internacional. Permite la gestión integral de clientes, rutinas, nutrición, reportes y comunicación entre entrenadores y clientes.

---

## 2. User Personas

### Cliente
- Usuarios que contratan servicios de entrenamiento personal online
- Acceden a su rutina, macros, reportes y chat con entrenador
- Planes: Gold (149€), Silver (99€), Bronze (69€), ELM (39€)

### Operaciones/Admin
- Staff que gestiona clientes, pagos, rutinas y comunicaciones
- Acceso a dashboard de métricas y generador de rutinas con IA

### Entrenador
- Profesionales que diseñan rutinas y nutición personalizada
- Interactúan con clientes via chat

---

## 3. Core Requirements

### Portal Cliente
- [x] Login/Registro con email y contraseña (JWT)
- [x] Home Dashboard con progreso del ciclo
- [x] Mi Rutina - Visualización de ejercicios por día
- [x] Mi Nutrición - Calculadora de macros integrada
- [x] Mis Reportes - Formularios de seguimiento con evolución
- [x] Mensajes - Chat con entrenador
- [x] Mi Perfil - Datos personales y plan

### Panel Operaciones
- [x] Dashboard con métricas (MRR, clientes, pagos)
- [x] Listado de clientes con filtros
- [x] Ficha única de cliente (tabs múltiples)
- [x] Generador de rutinas con IA (Claude Sonnet 4.5)
- [x] Gestión de macros por cliente

---

## 4. Implementación Completada

### Backend (FastAPI + MongoDB)
- Autenticación JWT completa
- CRUD de usuarios, perfiles, rutinas, reportes
- Sistema de mensajería
- Calculadora de macros con base de datos de alimentos
- Integración Claude Sonnet 4.5 para generación de rutinas
- Pagos simulados (mockeados)

### Frontend (React + Tailwind + Shadcn)
- 18 pantallas implementadas
- Diseño responsive mobile-first
- Badges de planes (Gold, Silver, Bronze, ELM)
- Charts de evolución con Recharts
- Sistema de notificaciones con Sonner

### Integraciones
- Claude Sonnet 4.5 via emergentintegrations

---

## 5. Backlog Priorizado

### P0 (Crítico)
- [ ] Integración real de Stripe para pagos
- [ ] Sistema de recordatorios automáticos (semana 3 = reporte)
- [ ] Notificaciones push/email

### P1 (Alta prioridad)
- [ ] Subida de fotos en reportes
- [ ] Videos de ejercicios embebidos
- [ ] Panel CEO con analytics avanzados
- [ ] Exportación de rutinas a PDF

### P2 (Media prioridad)
- [ ] App móvil nativa
- [ ] Historial de macros con gráficos
- [ ] Sistema de objetivos y metas
- [ ] Gamificación (badges, streaks)

---

## 6. Stack Técnico

- **Frontend**: React 18, Tailwind CSS, Shadcn UI, Recharts
- **Backend**: FastAPI, Motor (MongoDB async)
- **Base de datos**: MongoDB
- **IA**: Claude Sonnet 4.5 (emergentintegrations)
- **Pagos**: Stripe (pendiente - actualmente mockeado)

### Branding JG12
- **Color Primario**: #FF671F (Naranja)
- **Color Secundario**: #000000 (Negro)
- **Fuente Principal**: Bebas Neue (headings)
- **Fuente Secundaria**: Inter (body)
- **Logo**: JG12↗ con flecha naranja

---

## 7. URLs y Credenciales de Test

### Credenciales Admin
- Email: admin@12en12.com
- Password: admin123

### Credenciales Cliente Test
- Email: clientedemo@test.com  
- Password: demo123

---

## 8. Notas de Implementación

- Pagos están MOCKEADOS - todos retornan success
- La generación de rutinas con IA puede tardar 5-10 segundos
- El sistema usa ciclos de 4 semanas
- Los planes Gold incluyen cardio personalizado

---

## 9. Próximos Pasos Recomendados

1. Integrar Stripe real para pagos
2. Implementar sistema de notificaciones por email
3. Añadir Panel CEO con KPIs y OKRs
4. Desarrollar app móvil con React Native
