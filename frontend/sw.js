const CACHE_VERSION = "valorpublico-v3";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./css/styles.css",
  "./js/app.js",
  "./js/charts.js",
  "./js/firebase-init.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

// Nunca servidos do cache: modulos JS dinamicos que podem ter sido corrompidos
// por redeploys (ex.: firebase-config.js cacheado como HTML).
const NUNCA_CACHEAR = (url) =>
  url.pathname.endsWith("firebase-config.js");

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

  // firebase-config.js e modulos JS do app: SEMPRE da rede, sem cache.
  // Evita reincidencia do erro de MIME text/html apos redeploys.
  if (NUNCA_CACHEAR(url) || isGstatic || isGoogle) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
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

  // Assets estaticos imutaveis: cache-first.
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