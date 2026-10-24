const CACHE = "linea-de-valor-v2";
const FILES = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png", "icon-maskable-512.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES.map(f => new Request(f, { cache: "reload" })))).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  // Siempre se intenta la versión más nueva del servidor; la copia guardada solo se usa sin conexión.
  e.respondWith(fetch(req, { cache: "no-cache" }).then(r => {
    if (r.ok && !req.url.includes("/datos/")) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {}); }
    return r;
  }).catch(() => caches.match(req).then(r => r || caches.match("index.html"))));
});
