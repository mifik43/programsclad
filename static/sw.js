const CACHE_NAME = 'service-center-v2';
const STATIC_CACHE = 'static-v2';
const API_CACHE = 'api-v2';

// Ресурсы для кэширования статики
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  '/static/js/pwa.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js',
  '/offline'  // отдельная страница офлайн (создадим маршрут)
];

// Установка: кэшируем статику
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Активация: очищаем старые кэши
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== STATIC_CACHE && key !== API_CACHE && key !== CACHE_NAME)
          .map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

// Стратегия кэширования: stale-while-revalidate для API, network-first для статики
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Кэшируем API-запросы (GET) с стратегией: сначала сеть, при ошибке кэш
  if (url.pathname.startsWith('/api/') && event.request.method === 'GET') {
    event.respondWith(
      fetch(event.request).then(response => {
        // Клонируем и сохраняем в кэш
        const responseClone = response.clone();
        caches.open(API_CACHE).then(cache => cache.put(event.request, responseClone));
        return response;
      }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/offline')))
    );
    return;
  }
  
  // Статические ресурсы: сначала кэш, потом сеть
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).catch(() => caches.match('/offline')))
  );
});

// Обработка push-уведомлений
self.addEventListener('push', event => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'Новое уведомление', body: event.data.text() };
    }
  }
  const options = {
    body: data.body || 'Проверьте сервисный центр',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-72.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/' }
  };
  event.waitUntil(
    self.registration.showNotification(data.title || 'Сервисный центр', options)
  );
});

// Обработка клика по уведомлению
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({type: 'window', includeUncontrolled: true}).then(windowClients => {
      for (let client of windowClients) {
        if (client.url === urlToOpen && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(urlToOpen);
    })
  );
});