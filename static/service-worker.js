/* Placeholder service worker for OpenPassGen PWA */
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open('openpassgen').then(function(cache) {
      return cache.addAll([
        '/',
        '/static/manifest.json',
        // Add more static files if needed
      ]);
    })
  );
});

self.addEventListener('fetch', function(e) {
  e.respondWith(
    caches.match(e.request).then(function(response) {
      return response || fetch(e.request);
    })
  );
});
