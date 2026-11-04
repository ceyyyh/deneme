# İşBul İstanbul

İstanbul'daki iş ilanlarını tek bir sade arayüzde toplayan, kendi kendini güncelleyen web uygulaması.
LinkedIn'in filtre + detay paneli düzeni, kariyer.net'in kategori çipleri ve eleman.net'in büyük,
basit arama kutusu bir araya getirildi; telefonda filtreler ve ilan detayı alttan açılan panelde.

## Kaynaklar

Her turda tüm sitelerdeki İstanbul ilanlarının tamamına ulaşmaya çalışılır. Siteler paralel taranır;
aynı siteye istekler sırayla ve araya bekleme konarak gönderilir.

| Site | Nasıl alınıyor |
|------|----------------|
| kariyer.net | 39 ilçe sayfası + İstanbul geneli, yeni ilan çıkmayana kadar tüm sayfalar (site liste başına en fazla 100 sayfa gösteriyor, ilçe sayfaları bu sınırı aşmayı ve ilçe bilgisini sağlıyor) |
| eleman.net | İstanbul listesinin tüm sayfaları |
| isbul.net | Sitenin yapay zeka ajanları için açtığı resmi API (`/api/agent/jobs`) |
| SecretCV | İl, yaka ve 39 ilçe listesinin 1. sayfaları (robots.txt sayfalamayı yasaklıyor) |
| Eleman Online | İstanbul listesinin tüm sayfaları |
| Indeed (tr) | [JobSpy](https://github.com/speedyapply/JobSpy), son 14 gün, en fazla 1000 ilan |
| LinkedIn | [JobSpy](https://github.com/speedyapply/JobSpy) (LinkedIn hız sınırı koyduğu için az sayıda) |

Taranamayan siteler: **isinolsun.com** (ilan listesi sayfaları bota yanıt vermiyor), **yenibiris.com**
ve **sahibinden.com** (erişimi reddediyor), **careerjet** (robot doğrulaması istiyor). Bu sitelerin
engelleri aşılmaya çalışılmaz.

- Sadece robots.txt'nin izin verdiği sayfalar okunur, bot kendini dürüstçe tanıtır.
- Aynı ilan birden fazla sitede varsa tek kart gösterilir, diğer siteler "Bu ilan ayrıca" altında listelenir.
- Sitesi sorunsuz tarandığı halde 2 gündür görünmeyen ilan kapanmış sayılıp silinir. Bir site o tur
  hata verirse onun ilanları 14 güne kadar korunur.
- Başvuru her zaman ilanın kendi sitesinde yapılır; uygulama sadece listeler.

## Dosyalar

```
is_bul/
  scrape.py          # tüm kaynakları tarar -> site/jobs.json
  requirements.txt
  site/              # yayınlanan statik site (index.html, app.js, style.css, jobs.json)
.github/workflows/is-bul.yml   # 6 saatte bir tarar, jobs.json'u commit'ler, Pages'e yayınlar
```

## Linkli ve otomatik güncellenen kurulum (bir kerelik)

1. Bu dalı reponun varsayılan dalına birleştir (zamanlanmış GitHub Actions sadece varsayılan dalda çalışır).
2. **Settings → Pages → Build and deployment → Source: "GitHub Actions"** seç.
   - Ücretsiz GitHub hesabında Pages yalnızca **public** repolarda çalışır. Repo private ise ya
     repoyu public yap ya da GitHub Pro kullan.
3. **Actions → "İşBul İstanbul - ilan güncelle" → Run workflow** ile ilk taramayı başlat.
4. Site şu adreste açılır: `https://<kullanici-adi>.github.io/<repo-adi>/`
   (bu repo için `https://ceyyyh.github.io/deneme/`). Sonrasında her 6 saatte bir kendiliğinden güncellenir.

## Kendi bilgisayarında çalıştırma

```bash
pip install -r is_bul/requirements.txt
python is_bul/scrape.py              # tam tarama (~10-15 dk)
python is_bul/scrape.py --quick      # hızlı deneme (her siteden 1 sayfa)
cd is_bul/site && python -m http.server 8000   # http://localhost:8000
```

## Not

LinkedIn ve Indeed'in kullanım şartları otomatik erişimi kısıtlar. Bu araç kişisel iş arama
içindir; düşük hacimde çalışır. Ticari kullanım veya toplu veri toplama için kullanma.
