# Production Stabilizasyonu

Bu sürüm üç üretim sorununu hedefler:

1. **Kalıcı kullanıcılar:** Render PostgreSQL kullanılır. `DATABASE_URL` mutlaka kalıcı PostgreSQL bağlantısı olmalıdır. Eski geçici SQLite verileri otomatik taşınmaz.
2. **Soğuk başlangıç:** İlk haber taraması deploy başlangıcından çıkarıldı. Arayüz backend uyanırken oturumu silmez; yükleme ekranı ve kontrollü yeniden deneme kullanır.
3. **Canlı Desk Chat:** Yeni oda açıldığında bağlı tüm cihazlar odaya anında alınır. Socket yeniden bağlanır ve 2.5 saniyelik güvenilir senkronizasyon F5 ihtiyacını kaldırır.

## Render ortamı
- `DATABASE_URL`: Render PostgreSQL internal connection URL
- `ALLOWED_ORIGINS=https://slayz-platform.vercel.app`
- `SOCKETIO_CORS_ORIGINS=https://slayz-platform.vercel.app`
- `FRONTEND_BASE_URL=https://slayz-platform.vercel.app`
- `RUN_PIPELINE_ON_STARTUP=false`

Render ücretsiz web servisleri uykuya geçebilir. Kod bunu kullanıcı oturumunu bozmadan karşılar; sürekli sıfır gecikme için ücretli always-on instance gerekir.
