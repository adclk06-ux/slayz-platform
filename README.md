# Slayz Haber Otomasyonu

Kurum içi finansal haber akışı, OpenAI destekli analiz, kişisel gelen kutusu ve gerçek zamanlı ekip sohbeti sunan tam yığın uygulama.

## Bu sürümde hazır olanlar

- İlk açılışta tek seferlik yönetici kurulumu
- Yalnızca `@slayz.com` kurumsal hesapları
- Admin panelinden kullanıcı ekleme, pasifleştirme ve şifre yenileme
- Güvenli 30 günlük yenilenebilir oturum; şifre tarayıcıda tutulmaz
- Tüm aktif kullanıcıların göründüğü bire bir Desk Chat
- Socket.IO ile farklı bilgisayarlarda anlık mesajlaşma, çevrimiçi durum ve okunmamış sayacı
- Kullanıcıya özel gelen kutusu ve ekip arkadaşına not gönderme
- Haberi paylaşmadan önce alıcı seçme; otomatik sohbet yönlendirmesi yok
- Gerçek haber kaynakları modu, periyodik tarama ve admin için manuel kaynak taraması
- OpenAI anahtarının yalnızca backend'de tutulduğu AI altyapısı
- Resend, SendGrid veya gerçek SMTP üzerinden e-posta gönderimi
- Gerçek veriye bağlı piyasa radarı: savaş teması, günün yükselenleri ve yaklaşan temettüler
- Midas benzeri kullanım akışına sahip özgün hisse detay ekranı; dönem seçimi, çizgi/mum grafik ve istatistikler
- Hisseyi seçilen ekip arkadaşına, isteğe bağlı AI özetiyle birlikte gönderme
- Simülasyonu reddeden, teknik metrik ve gerçek haberlerle temellendirilmiş OpenAI hisse analizi

Demo kullanıcı ve hazır demo veritabanı pakete dahil değildir.

## Hızlı yerel kurulum

Ayrıntılı adımlar için `KURULUM_TR.md` dosyasına bakın.

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (ayrı terminal)
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Tarayıcıda `http://localhost:3000/setup` açılır. İlk oluşturulan hesap yöneticidir. Bundan sonra yeni hesapları yalnızca admin paneli oluşturur.

## Test edilen kritik akışlar

- Backend Python derlemesi
- Frontend TypeScript kontrolü ve Next.js üretim derlemesi
- Dış alan adlı e-posta kaydının reddedilmesi
- Admin tarafından iki gerçek kullanıcının oluşturulması
- İki farklı oturum arasında kalıcı DM mesajı
- İki ayrı Socket.IO istemcisi arasında anlık mesaj teslimi
- Gelen kutusu mesajının yalnızca seçilen alıcıya görünmesi
- Piyasa radarında simülasyon verisinin günün yükselenlerine girmemesi
- Dönem bazlı OHLCV grafik endpointi
- AI analizinin hesaplanmış teknik metrikleri kullanması ve simülasyon verisini reddetmesi
- Hisse kartının seçilen kullanıcıya kalıcı DM olarak gönderilmesi

## Üretim notu

Farklı bilgisayarların aynı kullanıcıları, mesajları ve haberleri görmesi için herkesin aynı yayımlanmış backend ve aynı veritabanına bağlanması gerekir. Yerel SQLite geliştirme için uygundur; büyüyen üretim kurulumu için PostgreSQL önerilir. Socket.IO kullandığı için backend tek bir paylaşılan servis olarak çalışmalıdır.
