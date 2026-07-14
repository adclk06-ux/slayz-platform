# Kurulum ve İlk Çalıştırma

## 1. Gizli anahtarları oluşturun

`backend/.env.example` dosyasını `backend/.env` olarak kopyalayın. En az şu alanları değiştirin:

- `APP_SECRET_KEY`
- `JWT_SECRET_KEY`
- `DB_ENCRYPTION_KEY`
- `ALLOWED_EMAIL_DOMAIN=slayz.com`
- `OPENAI_API_KEY` (AI kullanılacaksa)

`.env` dosyasını Git'e veya ZIP teslimlerine koymayın.

## 2. İlk yönetici hesabı

Boş veritabanıyla uygulama açıldığında `/setup` ekranı görünür. Buraya kendi `@slayz.com` adresinizi ve şifrenizi girin. Bu işlem yalnızca bir kez çalışır.

Yönetici hesabıyla ana ekrandaki ayar simgesinden `/admin/users` sayfasına giderek çalışanları oluşturabilirsiniz. Kullanıcılar kendi kendine kayıt olamaz.

## 3. Çoklu bilgisayar testi

1. Backend'i internete açık tek bir sunucuya yayımlayın.
2. Frontend'de `BACKEND_URL` değerini bu sunucuya ayarlayın.
3. WebSocket proxy desteklenmiyorsa `NEXT_PUBLIC_WS_URL` değerini doğrudan backend adresine ayarlayın.
4. Admin panelinden en az iki kullanıcı oluşturun.
5. İki bilgisayarda farklı hesaplarla giriş yapın.
6. Desk Chat > Yeni Sohbet üzerinden diğer kullanıcıyı seçin.

Mesajlar veritabanına yazılır; alıcı çevrimiçiyse Socket.IO ile anında, çevrimdışıysa sonraki girişinde geçmişten görünür.

## 4. Haber akışı

- Sentetik haber üreticileri bu sürümden çıkarılmıştır; yalnızca gerçek kaynak adaptörleri çalışır.
- Zamanlayıcı `SCRAPER_INTERVAL_MINUTES` aralığında gerçek kaynakları tarar.
- Admin ana ekrandaki **Kaynakları Tara** düğmesiyle manuel tarama yapabilir.
- Ana ekran 60 saniyede bir yeni kayıtları kontrol eder.
- Kaynakların erişilebilirliği, robot engelleri ve internet bağlantısı sonucu etkileyebilir.

OpenAI anahtarı yoksa gerçek haberler yine kaydedilir; AI başlığı/özeti üretilemez ve sahte tahmin döndürülmez.

## 5. E-posta

`MAIL_PROVIDER` değerini `resend`, `sendgrid` veya `smtp` yapın. Sağlayıcı kurulmamışsa API artık gönderilmiş gibi davranmaz; açık biçimde `503` hatası verir.

Kendi `noreply@slayz.com` adresinizden gönderim ve dışarıdan e-posta alma için alan adının DNS tarafında sağlayıcının istediği SPF, DKIM ve MX kayıtları ayrıca kurulmalıdır. Gelen e-posta/delivery webhook'u için `MAIL_WEBHOOK_SECRET` belirleyin.

## 6. Oturum güvenliği

Kullanıcı şifresi hiçbir zaman tarayıcıya düz metin olarak kaydedilmez. Erişim anahtarı kısa/orta süreli, yenileme anahtarı ise HTTP-only cookie olarak 30 gün geçerlidir. Üretimde HTTPS zorunludur.

## 7. Piyasa verisi ve AI hisse analizi

Piyasa fiyatları varsayılan olarak Yahoo Finance sağlayıcısından backend üzerinden alınır. Üretimde aşağıdaki değer kapalı kalmalıdır:

```env
MARKET_ALLOW_SIMULATION=false
```

Bu ayar `false` iken sağlayıcıya ulaşılamazsa sistem fiyat uydurmaz; son doğrulanmış veriyi `stale` olarak gösterir veya veri yoksa boş durum gösterir. Yalnızca görsel geliştirme sırasında hareketli demo grafik gerektiğinde geçici olarak `true` yapılabilir.

Piyasa ekranındaki:

- **Bugün En Çok Yükselenler** listesi sadece gerçek sağlayıcı verisinden hesaplanır.
- **Yakında Temettü Dağıtacaklar** listesi sağlayıcıda açıklanmış yaklaşan takvim kayıtlarını kullanır ve 30 dakika önbellekler.
- AI hisse analizi için `OPENAI_API_KEY` gerekir. AI, simülasyon verisiyle çalışmaz.
- Grafik zaman aralıkları `1G`, `1H`, `1A`, `3A`, `1Y`, `5Y` seçeneklerini destekler.

İlk açılışta temettü takvimi arka planda yenilendiği için listenin görünmesi kısa bir süre ve bir sonraki 60 saniyelik ekran yenilemesini gerektirebilir.
