// NH-7 Landslide Early Warning Service Worker
// Reference Offline Implementation for Web & PWA Testbench

const SHELL_CACHE = "nh7-app-shell-v2";
const OFFLINE_PACK_CACHE = "nh7-offline-pack-v2";
const DATA_CACHE = "nh7-data-cache-v2";

const APP_SHELL_URLS = [
  "/",
  "/static/index.html",
  "/manifest.json",
  "/static/vendor/leaflet/leaflet.css",
  "/static/vendor/leaflet/leaflet.js",
  "/static/vendor/leaflet/images/marker-icon.png",
  "/static/vendor/leaflet/images/marker-icon-2x.png",
  "/static/vendor/leaflet/images/marker-shadow.png",
  "/static/vendor/leaflet/images/layers.png",
  "/static/vendor/leaflet/images/layers-2x.png"
];

// Helper: check if a URL belongs to a map tile provider (OSM, Carto, Thunderforest, Mapbox, Esri, etc.)
function isMapTileRequest(url) {
  // CRITICAL RULE: Do not cache map tiles under any circumstances (never store in cache)
  if (url.hostname.includes("tile.openstreetmap.org")) return true;
  if (url.hostname.includes("cartocdn.com")) return true;
  if (url.hostname.includes("thunderforest.com")) return true;
  if (url.hostname.includes("mapbox.com")) return true;
  if (url.hostname.includes("arcgisonline.com")) return true;
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
    (async () => {
      // 1. Precache App Shell and Vendored Assets
      const shellCache = await caches.open(SHELL_CACHE);
      await shellCache.addAll(APP_SHELL_URLS);

      // 2. Precache /offline-pack into OFFLINE_PACK_CACHE
      try {
        const opResp = await fetch("/offline-pack");
        if (opResp && opResp.ok) {
          const opCache = await caches.open(OFFLINE_PACK_CACHE);
          await opCache.put("/offline-pack", opResp);
        }
      } catch (err) {
        console.warn("[SW] Precache /offline-pack error:", err);
      }

      // 3. Precache initial /risk-map response into DATA_CACHE
      try {
        const rmResp = await fetch("/risk-map");
        if (rmResp && rmResp.ok) {
          const dataCache = await caches.open(DATA_CACHE);
          await dataCache.put("/risk-map", rmResp);
        }
      } catch (err) {
        console.warn("[SW] Precache /risk-map error:", err);
      }

      return self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const allowedCaches = [SHELL_CACHE, OFFLINE_PACK_CACHE, DATA_CACHE];
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => !allowedCaches.includes(k)).map((k) => caches.delete(k))
      );
      return self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // 1. CRITICAL RULE: Do not cache map tiles under any circumstances (never store in cache)
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
              cache.put("/offline-pack", networkResp.clone());
            });
          }
          return networkResp;
        })
        .catch(() => {
          // Network failed (offline): serve latest cached offline pack
          return caches.match(event.request).then((cachedResp) => {
            if (cachedResp) return cachedResp;
            return caches.match("/offline-pack").then((fallbackResp) => {
              if (fallbackResp) return fallbackResp;
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
          });
        })
    );
    return;
  }

  // 3. Risk Map Endpoint: network-first with caching of latest response
  if (url.pathname === "/risk-map") {
    event.respondWith(
      fetch(event.request)
        .then((networkResp) => {
          if (networkResp && networkResp.status === 200) {
            const respClone = networkResp.clone();
            caches.open(DATA_CACHE).then((cache) => {
              cache.put(event.request, respClone);
              // Also store under canonical /risk-map key for query-independent offline fallback
              cache.put("/risk-map", networkResp.clone());
            });
          }
          return networkResp;
        })
        .catch(async () => {
          // Network failed (offline): match exact request or canonical /risk-map
          const cache = await caches.open(DATA_CACHE);
          const cachedMatch = await cache.match(event.request);
          if (cachedMatch) return cachedMatch;

          const canonicalMatch = await cache.match("/risk-map");
          if (canonicalMatch) return canonicalMatch;

          // If no /risk-map is cached, fallback to cached /offline-pack
          const opCache = await caches.open(OFFLINE_PACK_CACHE);
          const opMatch = await opCache.match("/offline-pack");
          if (opMatch) return opMatch;

          return new Response(
            JSON.stringify({
              error: "offline",
              message: "Offline: No cached risk map available."
            }),
            {
              status: 503,
              headers: { "Content-Type": "application/json" }
            }
          );
        })
    );
    return;
  }

  // 4. App Shell Navigation & Static Assets: network-first with cache fallback
  if (
    event.request.mode === "navigate" ||
    APP_SHELL_URLS.includes(url.pathname) ||
    url.pathname.startsWith("/static/")
  ) {
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
            return (
              cached ||
              caches.match("/") ||
              caches.match("/static/index.html")
            );
          });
        })
    );
    return;
  }

  // 5. Default same-origin requests: try network, fallback to cache
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
