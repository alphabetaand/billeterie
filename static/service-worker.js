const CACHE_NAME = "billetterie-v1";
const OFFLINE_URLS = [
  "/",
  "/select",
  "/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png"
];

// Installation : on met en cache les fichiers de base
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(OFFLINE_URLS))
  );
  self.skipWaiting();
});

// Activation : on nettoie les anciens caches
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Stratégie de cache
self.addEventListener("fetch", event => {
  const request = event.request;

  // On ne gère que les GET
  if (request.method !== "GET") return;

  // Pour les pages HTML : network first, fallback cache
  if (request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request).catch(() => caches.match("/"))
    );
    return;
  }

  // Pour le reste (icônes, manifest, etc.) : cache d'abord, puis réseau
  event.respondWith(
    caches.match(request).then(response => response || fetch(request))
  );
});
