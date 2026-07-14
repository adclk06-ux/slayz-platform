# Yapılan İyileştirmeler

- Demo giriş ve otomatik demo admin kaldırıldı.
- İlk kurulum admin ekranı eklendi.
- Kayıt alan adı `@slayz.com` ile sınırlandı.
- Admin kullanıcı yönetim ekranı eklendi.
- Oturum yenileme süresi 30 güne çıkarıldı; ham şifre saklanmıyor.
- Gelen kutusu kullanıcıya özel alıcı modeliyle düzeltildi.
- Tüm aktif kullanıcıların listelendiği yeni DM seçici eklendi.
- Socket.IO kimlik doğrulama, oda üyeliği, çevrimiçi durum, yazıyor bilgisi ve okunma akışı düzeltildi.
- Haber paylaşımına alıcı seçme penceresi eklendi.
- Chat açma düğmesi AI düğmesiyle çakışmayacak biçimde sağ alta taşındı.
- Sahte haber kaynakları üretim hattından çıkarıldı ve temiz teslim paketinden eski veritabanı çıkarıldı.
- Haber akışı durum göstergesi ve admin manuel tarama düğmesi eklendi.
- OpenAI anahtarı yokken sahte analiz/tahmin üretimi kaldırıldı.
- SMTP gönderimi gerçek hale getirildi; yapılandırılmamış mail artık gönderilmiş sayılmıyor.
- Frontend bağımlılıkları Next.js 16 ile uyumlu React 19 sürümüne getirildi.
- Üretim REST proxy ve doğrudan WebSocket yapılandırması ayrıştırıldı.
- Veritabanı geçişi ve güvenli `.env.example` dosyaları güncellendi.

## Piyasalar v2

- Piyasa ekranına dört ayrı radar eklendi: **Savaşın Kazananları**, **Savaşın Kaybedenleri**, **Bugün En Çok Yükselenler** ve **Yakında Temettü Dağıtacak Hisseler**.
- Savaş listeleri, kesin kazanç/kayıp iddiası yerine sektör hassasiyeti ve risk gerekçesi gösteren tematik izleme sepetleri olarak tasarlandı.
- Günün yükselenleri yalnızca gerçek sağlayıcı verisi bulunan hisselerden hesaplanıyor; simülasyon verisi sıralamaya alınmıyor.
- Piyasa veri sağlayıcısı kesildiğinde rastgele fiyat üretme varsayılan olarak kapatıldı. Son doğrulanmış veri korunuyor ve veri durumu kullanıcıya gösteriliyor.
- `MARKET_ALLOW_SIMULATION=false` üretim varsayılanı eklendi. Simülasyon yalnızca bilinçli arayüz geliştirme testi için açılabilir.
- Temettü takvimi sağlayıcıdan açıklanmış tarihleri arka planda önbelleğe alıyor; tarih bulunamazsa sabit veya uydurma kayıt gösterilmiyor.
- Hisse detay ekranı fiyat başlığı, dönem seçimi (`1G`, `1H`, `1A`, `3A`, `1Y`, `5Y`), çizgi/mum grafik geçişi, tam ekran grafik ve istatistik kartlarıyla yenilendi.
- Grafik API'sine dönem bazlı gerçek OHLCV verisi desteği eklendi.
- Hisse seçilerek ekip arkadaşına gönderilebiliyor; paylaşım öncesinde alıcı seçiliyor ve mevcut AI özeti isteğe bağlı olarak mesaja ekleniyor.
- AI hisse analizi sunucu tarafında doğrulanmış fiyat, hesaplanmış dönem getirisi, oynaklık, maksimum geri çekilme, destek/direnç ve platformdaki gerçek haberleri kullanıyor.
- AI artık simülasyon verisiyle analiz üretmiyor; veri yetersiz veya OpenAI yapılandırılmamışsa açık hata veriyor.
- Bazı yanlış şirket adları düzeltildi (`DOAS`, `GESAN`, `GSRAY`, `IEYHO`, `KTLEV`, `PATEK`).
