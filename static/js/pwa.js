// Регистрация Service Worker
async function registerSW() {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/static/sw.js');
      console.log('SW registered:', registration);
      // Запрашиваем разрешение на уведомления
      if (Notification.permission === 'default') {
        document.getElementById('enableNotificationsBtn')?.addEventListener('click', () => requestNotificationPermission(registration));
      } else if (Notification.permission === 'granted') {
        subscribeToPush(registration);
      }
    } catch (error) {
      console.error('SW registration failed:', error);
    }
  }
}

async function requestNotificationPermission(registration) {
  const permission = await Notification.requestPermission();
  if (permission === 'granted') {
    subscribeToPush(registration);
  } else {
    alert('Уведомления отключены. Вы не будете получать оповещения.');
  }
}

async function subscribeToPush(registration) {
  try {
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array('MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEFPP1qDfYxRLt8bwBIThjTRLF++gs
NjhyvOjKmFdPmdodf7U2l9HGaf0CDkfE9L8NNRNJ12RxzZCGzAWL9R8DMg==')
    // Отправляем подписку на сервер (опционально)
    await fetch('/api/push-subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscription)
    });
    console.log('Push subscription successful');
  } catch (error) {
    console.error('Push subscription failed:', error);
  }
}

// Вспомогательная функция для преобразования VAPID ключа
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// Показываем кнопку установки PWA (для Chrome)
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const installBtn = document.getElementById('installPwaBtn');
  if (installBtn) installBtn.style.display = 'inline-block';
  installBtn?.addEventListener('click', () => {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') console.log('PWA установлено');
      deferredPrompt = null;
    });
  });
});

registerSW();