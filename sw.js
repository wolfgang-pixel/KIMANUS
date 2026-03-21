// KIMANUS Service Worker v1.0
// Minimal SW fuer PWA Install-Prompt + Offline-Grundschutz

const CACHE_NAME = 'kimanus-v6';
const OFFLINE_URL = '/';

// Install: Startseite cachen fuer Offline-Grundschutz
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.add(OFFLINE_URL))
  );
});

// Activate: Alte Caches aufraeumen
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: Network-first, Fallback auf Cache
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(OFFLINE_URL))
    );
  }
});
