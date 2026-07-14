# Test Raporu — Piyasalar v2

## Başarılı kontroller

- Backend Python modülleri `compileall` ile derlendi.
- Frontend TypeScript kontrolü `tsc --noEmit` ile geçti.
- Next.js production build başarıyla oluşturuldu.
- `npm audit --audit-level=high`: **0 güvenlik açığı**.
- Piyasa radarında gerçek veri sıralaması test edildi; simüle edilmiş `%102` değişimli örnek hisse yükselenler listesinden dışlandı.
- Savaş teması kazanan/kaybeden sepetleri ve gerekçeleri API yanıtında doğrulandı.
- Yaklaşan temettü kaydı API yanıtında doğrulandı.
- `1G–5Y` geçmiş endpointinin OHLCV/mum verisi döndürmesi doğrulandı.
- Hisse detay istatistik endpointi doğrulandı.
- OpenAI yanıtı kontrollü test istemcisiyle çalıştırıldı; hesaplanan dönem getirisi AI yanıt metriklerine taşındı.
- Simülasyon verisiyle AI analizi isteği `409` ile reddedildi.
- Hisse kartı iki gerçek kullanıcı arasındaki direkt odaya gönderildi ve alıcı hesabından kalıcı mesaj geçmişinde görüldü.

## Ortam sınırı

Bu çalışma ortamı dış DNS bağlantılarını engellediği için Yahoo Finance ve OpenAI servislerine gerçek ağ çağrısı yapılamadı. Sağlayıcı adaptörleri hata durumunda sahte sonuç üretmeyecek şekilde test edildi; canlı ağ doğrulaması uygulama internete açık bir makinede çalıştırıldığında yapılmalıdır.
