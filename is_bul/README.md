# İşBul İstanbul

İstanbul'daki iş ilanlarını tek bir sade arayüzde toplayan, kendi kendini güncelleyen web uygulaması.
LinkedIn'in filtre + detay paneli düzeni, kariyer.net'in kategori çipleri ve eleman.net'in büyük,
basit arama kutusu bir araya getirildi; telefonda filtreler ve ilan detayı alttan açılan panelde.

## Kaynaklar

| Site | Nasıl alınıyor | Tur başına |
|------|----------------|-----------|
| kariyer.net | İstanbul listeleme sayfaları (6 sayfa) | ~300 |
| eleman.net | İstanbul listeleme sayfaları (6 sayfa) | ~180 |
| Indeed (tr) | [JobSpy](https://github.com/speedyapply/JobSpy) | ~200 |
| LinkedIn | [JobSpy](https://github.com/speedyapply/JobSpy) | 40–100 (LinkedIn hız sınırı koyuyor) |
| SecretCV | İstanbul listeleme sayfası (robots.txt sayfalamayı yasakladığı için sadece 1. sayfa) | ~20 |

- Sadece robots.txt'nin izin verdiği sayfalar okunur, istekler arasında beklenir, bot kendini dürüstçe tanıtır.
- Aynı ilan birden fazla sitede varsa tek kart gösterilir, diğer siteler "Bu ilan ayrıca" altında listelenir.
- 14 gündür hiçbir sitede görünmeyen ilanlar otomatik silinir.
- Bir site o tur hata verirse diğerleri etkilenmez, o sitenin önceki ilanları kalır.
- Başvuru her zaman ilanın kendi sitesinde yapılır; uygulama sadece listeler.

## Dosyalar

```
is_bul/
  scrape.py          # tüm kaynakları tarar -> site/jobs.json
  requirements.txt
  site/              # yayınlanan statik site (index.html, app.js, style.css, jobs.json)
.github/workflows/is-bul.yml   # 4 saatte bir tarar, jobs.json'u commit'ler, Pages'e yayınlar
```

## Linkli ve otomatik güncellenen kurulum (bir kerelik)

1. Bu dalı reponun varsayılan dalına birleştir (zamanlanmış GitHub Actions sadece varsayılan dalda çalışır).
2. **Settings → Pages → Build and deployment → Source: "GitHub Actions"** seç.
   - Ücretsiz GitHub hesabında Pages yalnızca **public** repolarda çalışır. Repo private ise ya
     repoyu public yap ya da GitHub Pro kullan.
3. **Actions → "İşBul İstanbul - ilan güncelle" → Run workflow** ile ilk taramayı başlat.
4. Site şu adreste açılır: `https://<kullanici-adi>.github.io/<repo-adi>/`
   (bu repo için `https://ceyyyh.github.io/deneme/`). Sonrasında her 4 saatte bir kendiliğinden güncellenir.

## Kendi bilgisayarında çalıştırma

```bash
pip install -r is_bul/requirements.txt
python is_bul/scrape.py              # tam tarama (~1 dk)
python is_bul/scrape.py --quick      # hızlı deneme (her siteden 1 sayfa)
cd is_bul/site && python -m http.server 8000   # http://localhost:8000
```

## Not

LinkedIn ve Indeed'in kullanım şartları otomatik erişimi kısıtlar. Bu araç kişisel iş arama
içindir; düşük hacimde çalışır. Ticari kullanım veya toplu veri toplama için kullanma.
