// KIMANUS Service Worker v166-bridge (frisch)
const CACHE_NAME = 'kimanus-v166-bridge';
self.addEventListener('install', event => { self.skipWaiting(); });
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// KEIN fetch-Handler = kein Caching = keine Probleme
