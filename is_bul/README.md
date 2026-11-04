# İşBul İstanbul

İstanbul'daki iş ilanlarını tek bir sade arayüzde toplayan, kendi kendini güncelleyen web uygulaması.
LinkedIn'in filtre + detay paneli düzeni, kariyer.net'in kategori çipleri ve eleman.net'in büyük,
basit arama kutusu bir araya getirildi; telefonda filtreler ve ilan detayı alttan açılan panelde.

## Kaynaklar

Her turda tüm sitelerdeki İstanbul ilanlarının tamamına ulaşmaya çalışılır. Siteler paralel taranır;
aynı siteye istekler sırayla ve araya bekleme konarak gönderilir.

| Site | Nasıl alınıyor |
|------|----------------|
| kariyer.net | İstanbul geneli (100 sayfa) + 39 ilçe sayfası. Site belli sayıda istekten sonra geçici olarak durdurduğu için her tur kaldığı yerden devam eder; tamamı ~2 günde bir dolaşılır. İlçe sayfaları ilanlara ilçe bilgisini de ekler |
| eleman.net | İstanbul listesinin tüm sayfaları |
| isbul.net | Sitenin yapay zeka ajanları için açtığı resmi API (`/api/agent/jobs`) |
| SecretCV | İl, yaka ve 39 ilçe listesinin 1. sayfaları (robots.txt sayfalamayı yasaklıyor) |
| Eleman Online | İstanbul listesinin tüm sayfaları |
| Indeed (tr) | [JobSpy](https://github.com/speedyapply/JobSpy), son 14 gün; tek arama ~1000 ilanla sınırlı olduğu için 80 farklı arama terimiyle |
| LinkedIn | [JobSpy](https://github.com/speedyapply/JobSpy), 80 arama terimi; LinkedIn hız sınırı koyduğu için her tur ~15 dk'lık bütçeyle çalışır ve kaldığı terimden devam eder |
| Şirket kariyer sayfaları | Haiku ajanlarıyla araştırılıp tek tek doğrulanan herkese açık ATS feed'leri (Trendyol, Dream Games, Codeway, iyzico, Çiçeksepeti, OKX, Bybit). Büyük Türk işverenlerinin çoğu ilanlarını zaten kariyer.net / eleman.net / SecretCV'de yayınladığı ya da kendi sitesinde makinece okunabilir bir liste sunmadığı için ayrıca eklenmedi |

Taranamayan siteler: **isinolsun.com** (ilan listesi sayfaları bota yanıt vermiyor), **yenibiris.com**
ve **sahibinden.com** (erişimi reddediyor), **careerjet** (robot doğrulaması istiyor). Bu sitelerin
engelleri aşılmaya çalışılmaz.

- Sadece robots.txt'nin izin verdiği sayfalar okunur, bot kendini dürüstçe tanıtır.
- Aynı ilan birden fazla sitede varsa tek kart gösterilir, diğer siteler "Bu ilan ayrıca" altında listelenir.
- Sitesi sorunsuz tarandığı halde 2 gündür görünmeyen ilan kapanmış sayılıp silinir. Bir site o tur
  hata verirse onun ilanları 14 güne kadar korunur.
- Başvuru her zaman ilanın kendi sitesinde yapılır; uygulama sadece listeler.

## Eve uzaklık

Ev: **PTT Evleri Mahallesi, Sarıyer**. Mesafe, OpenStreetMap yol ağı üzerinden [OSRM](https://project-osrm.org/)
ile hesaplanan **araçla yol mesafesidir** (kuş uçuşu değil).

İş ilanı siteleri çalışma yerinin tam adresini yayınlamıyor; en kesin bilgi ilçe, bazen semt. Yanlış bir
kesinlik göstermemek için:

- **Semt biliniyorsa** (ör. Maslak, Levent, Kozyatağı): semt merkezine tek değer, `~6,9 km`.
- **Yalnız ilçe biliniyorsa**: ilçe sınırı içine ~1,5 km aralıkla yerleştirilen tüm noktalara yol
  mesafesi hesaplanır; en yakın–en uzak aralığı gösterilir, `10–18,9 km`. "Eve ≤ X km" filtresi ve
  "Eve en yakın" sıralaması bu noktaların ortancasını kullanır.
- **İlçe yoksa** mesafe gösterilmez.

Konum verisi `is_bul/geo.json` dosyasındadır ve `python is_bul/build_geo.py` ile bir kez üretilir
(Nominatim ve OSRM'in kullanım kurallarına uyarak saniyede en fazla 1 istek). Evi değiştirmek için
`build_geo.py` içindeki adresi değiştirip `geo.json`'u silerek yeniden çalıştırın.

## Mavi yaka / beyaz yaka

Her ilan başlığına (ör. "müdür, uzman, mühendis" → beyaz; "eleman, personel, şoför, garson" → mavi),
başlık belirsizse kategorisine göre sınıflandırılır. Sınıflandırılamayanlar yalnız "Tümü"de görünür.

## Dosyalar

```
is_bul/
  scrape.py          # tüm kaynakları tarar -> site/jobs.json
  build_geo.py       # eve uzaklık verisini bir kez üretir -> geo.json
  geo.json           # ilçe mesafe aralıkları + semt mesafeleri
  requirements.txt
  site/              # yayınlanan statik site (index.html, app.js, style.css, jobs.json)
.github/workflows/is-bul.yml   # 3 saatte bir tarar, jobs.json'u commit'ler, Pages'e yayınlar
```

## Linkli ve otomatik güncellenen kurulum (bir kerelik)

1. Bu dalı reponun varsayılan dalına birleştir (zamanlanmış GitHub Actions sadece varsayılan dalda çalışır).
2. **Settings → Pages → Build and deployment → Source: "GitHub Actions"** seç.
   - Ücretsiz GitHub hesabında Pages yalnızca **public** repolarda çalışır. Repo private ise ya
     repoyu public yap ya da GitHub Pro kullan.
3. **Actions → "İşBul İstanbul - ilan güncelle" → Run workflow** ile ilk taramayı başlat.
4. Site şu adreste açılır: `https://<kullanici-adi>.github.io/<repo-adi>/`
   (bu repo için `https://ceyyyh.github.io/deneme/`). Sonrasında her 3 saatte bir kendiliğinden güncellenir.

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
