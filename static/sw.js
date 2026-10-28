const CACHE = 'cedz-public-v3';
const ASSETS = ['/offline', '/static/css/app.css', '/static/css/background.css', '/static/pwa-icon.svg', '/static/favicon.svg'];

self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline')));
    return;
  }
  const url = new URL(event.request.url);
  if (url.origin !== location.origin || !ASSETS.includes(url.pathname)) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});

self.addEventListener('push', event => {
  let payload = {title: 'Cedz', body: 'Une nouveauté t’attend.', url: '/compte#home'};
  try { payload = {...payload, ...event.data.json()}; } catch (_) {}
  event.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body,
    icon: '/static/pwa-icon.svg',
    badge: '/static/pwa-icon.svg',
    data: {url: payload.url},
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/compte#home', self.location.origin).href;
  if (new URL(target).origin !== self.location.origin) {
    event.waitUntil(clients.openWindow(target));
    return;
  }
  event.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then(windows => {
    const existing = windows.find(client => client.url.startsWith(self.location.origin));
    if (existing) return existing.focus().then(() => existing.navigate(target));
    return clients.openWindow(target);
  }));
});
