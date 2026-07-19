// Service worker mínimo para que la app sea instalable (PWA).
// NO cachea nada a propósito: la app vive del backend y un caché mal invalidado
// dejaría a los clientes con código viejo tras cada deploy. El fetch pasa tal cual.
self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {
    // Pasarela: no llamamos a respondWith, el navegador gestiona la petición normal.
});
