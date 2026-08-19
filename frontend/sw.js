const CACHE_VERSION = "valorpublico-v2";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./css/styles.css",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

const IGNORAR_CACHE = (url) =>
  url.pathname.endsWith(".js") || url.pathname.endsWith("firebase-config.js");

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_VERSION)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isGstatic = url.hostname.endsWith("gstatic.com");
  const isGoogle = url.hostname.endsWith("googleapis.com");

  // Modulos JS (firebase-config, app, etc.) e CDNs: sempre da rede (network-first).
  // Evita servir HTML cacheado no lugar de JS (erro de MIME) apos redeploys.
  if (IGNORAR_CACHE(url) || isGstatic || isGoogle) {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          if (resp.ok && IGNORAR_CACHE(url)) {
            const copy = resp.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          }
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          return resp;
        })
        .catch(() => caches.match("./index.html"))
    );
    return;
  }

  // Assets estaticos imutaveis do app shell: cache-first.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
        }
        return resp;
      });
    })
  );
});