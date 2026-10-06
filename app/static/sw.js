// NH-7 Landslide Early Warning Service Worker
// Reference Offline Implementation for Web & PWA Testbench

const SHELL_CACHE = "nh7-app-shell-v1";
const OFFLINE_PACK_CACHE = "nh7-offline-pack-v1";

const APP_SHELL_URLS = [
  "/",
  "/static/index.html",
  "/manifest.json"
];

// Helper: check if a URL belongs to a map tile provider (OSM, Carto, Thunderforest, Mapbox, etc.)
function isMapTileRequest(url) {
  // CRITICAL RULE: Do not cache map tiles under any circumstances
  if (url.hostname.includes("tile.openstreetmap.org")) return true;
  if (url.hostname.includes("cartocdn.com")) return true;
  if (url.hostname.includes("thunderforest.com")) return true;
  if (url.hostname.includes("mapbox.com")) return true;
  if (url.pathname.includes("/tiles/")) return true;
  if (url.pathname.includes("/tile/")) return true;
  // External raster tiles
  if (url.hostname !== self.location.hostname && url.pathname.match(/\.(png|jpg|jpeg|webp)$/i)) {
    return true;
  }
  return false;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => {
      return cache.addAll(APP_SHELL_URLS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== SHELL_CACHE && k !== OFFLINE_PACK_CACHE)
            .map((k) => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // 1. CRITICAL RULE: Do not cache map tiles
  if (isMapTileRequest(url)) {
    // Pass tile requests straight through to network; never store in cache
    return;
  }

  // 2. Offline Pack Endpoint: network-first with background cache update
  if (url.pathname === "/offline-pack") {
    event.respondWith(
      fetch(event.request)
        .then((networkResp) => {
          if (networkResp && networkResp.status === 200) {
            const respClone = networkResp.clone();
            caches.open(OFFLINE_PACK_CACHE).then((cache) => {
              cache.put(event.request, respClone);
            });
          }
          return networkResp;
        })
        .catch(() => {
          // Network failed (offline): serve latest cached offline pack
          return caches.match(event.request).then((cachedResp) => {
            if (cachedResp) {
              return cachedResp;
            }
            return new Response(
              JSON.stringify({
                error: "offline",
                message: "Offline: No cached offline pack available yet."
              }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" }
              }
            );
          });
        })
    );
    return;
  }

  // 3. App Shell Navigation & Static Assets: network-first with cache fallback
  if (event.request.mode === "navigate" || APP_SHELL_URLS.includes(url.pathname)) {
    event.respondWith(
      fetch(event.request)
        .then((networkResp) => {
          if (networkResp && networkResp.status === 200) {
            const respClone = networkResp.clone();
            caches.open(SHELL_CACHE).then((cache) => {
              cache.put(event.request, respClone);
            });
          }
          return networkResp;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            return cached || caches.match("/") || caches.match("/static/index.html");
          });
        })
    );
    return;
  }

  // 4. Default same-origin requests: try network, fallback to cache
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
