# Haber Akışı Düzeltmesi

- Boş PostgreSQL veritabanında backend açıldıktan 3 saniye sonra canlı kaynak taraması otomatik başlar.
- Dashboard boşsa `/api/articles/ensure-feed` üzerinden tarama kuyruğa alınır ve sayfa haberleri otomatik bekler.
- Piyasa detayındaki haber alanı boşsa aynı güvenli warm-up akışını kullanır.
- Sayfayı F5 ile yenilemek gerekmez.
- Vercel paket kurulumu için public npm registry sabitlenmiştir.
