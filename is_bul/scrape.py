#!/usr/bin/env python3
"""İstanbul iş ilanlarını birden fazla siteden toplayıp tek bir jobs.json'a yazar.

Kaynaklar:
  * LinkedIn ve Indeed  -> JobSpy (github.com/speedyapply/JobSpy) kütüphanesi
  * kariyer.net, eleman.net, secretcv.com -> herkese açık şehir listeleme sayfaları

Kurallar:
  * Yalnızca robots.txt'nin izin verdiği listeleme sayfaları çekilir
    (secretcv sayfalamayı yasakladığı için sadece 1. sayfa okunur).
  * Kendini dürüstçe tanıtan bir User-Agent kullanılır, istekler arasında beklenir.
  * Bir kaynak hata verirse diğerleri etkilenmez; o kaynağın önceki ilanları korunur.

Kullanım:  python is_bul/scrape.py [--out is_bul/site/jobs.json] [--quick]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA = "IstanbulIsBul/1.0 (kisisel is ilani toplayici; +https://github.com/ceyyyh/deneme)"
TZ = dt.timezone(dt.timedelta(hours=3))  # Türkiye saati
NOW = dt.datetime.now(TZ)
TODAY = NOW.date()
KEEP_DAYS = 14          # kaynağı hata verdiyse ilanlar en fazla bu kadar gün tutulur
GONE_DAYS = 2           # kaynağı sorunsuz tarandığı halde bu kadar gündür görünmeyen ilan kapanmış sayılır
DELAY = 1.0             # aynı siteye art arda istekler arası bekleme (sn)

_local = threading.local()


def session() -> requests.Session:
    # her kaynak kendi iş parçacığında, kendi oturumuyla sırayla istek atar
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})
    return _local.s


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url: str) -> str | None:
    try:
        r = session().get(url, timeout=30)
        if r.status_code != 200:
            log(f"  ! {r.status_code} {url}")
            return None
        r.encoding = r.encoding or "utf-8"
        return r.text
    except requests.RequestException as e:
        log(f"  ! {type(e).__name__} {url}")
        return None
    finally:
        time.sleep(DELAY)


def clean(s) -> str:
    if s is None:
        return ""
    s = str(s)
    if s.lower() == "nan":
        return ""
    return re.sub(r"\s+", " ", s).strip()


def relative_date(text: str) -> str | None:
    """'Bugün', 'Dün', '3 gün', '2 hafta önce', '5 saat' -> ISO tarih."""
    t = clean(text).lower()
    if not t:
        return None
    if "bugün" in t or "saat" in t or "dakika" in t or "yeni" in t:
        return TODAY.isoformat()
    if "dün" in t:
        return (TODAY - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*(gün|hafta|ay)", t)
    if m:
        n = int(m.group(1))
        days = n * {"gün": 1, "hafta": 7, "ay": 30}[m.group(2)]
        return (TODAY - dt.timedelta(days=days)).isoformat()
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", t)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- ilçeler
# (görünen ad, yaka, ascii slug) - kariyer.net ve secretcv ilçe sayfaları için
DISTRICTS = [
    ("Adalar", "Anadolu", "adalar"), ("Ataşehir", "Anadolu", "atasehir"), ("Beykoz", "Anadolu", "beykoz"),
    ("Çekmeköy", "Anadolu", "cekmekoy"), ("Kadıköy", "Anadolu", "kadikoy"), ("Kartal", "Anadolu", "kartal"),
    ("Maltepe", "Anadolu", "maltepe"), ("Pendik", "Anadolu", "pendik"), ("Sancaktepe", "Anadolu", "sancaktepe"),
    ("Sultanbeyli", "Anadolu", "sultanbeyli"), ("Şile", "Anadolu", "sile"), ("Tuzla", "Anadolu", "tuzla"),
    ("Ümraniye", "Anadolu", "umraniye"), ("Üsküdar", "Anadolu", "uskudar"),
    ("Arnavutköy", "Avrupa", "arnavutkoy"), ("Avcılar", "Avrupa", "avcilar"), ("Bağcılar", "Avrupa", "bagcilar"),
    ("Bahçelievler", "Avrupa", "bahcelievler"), ("Bakırköy", "Avrupa", "bakirkoy"),
    ("Başakşehir", "Avrupa", "basaksehir"), ("Bayrampaşa", "Avrupa", "bayrampasa"),
    ("Beşiktaş", "Avrupa", "besiktas"), ("Beylikdüzü", "Avrupa", "beylikduzu"), ("Beyoğlu", "Avrupa", "beyoglu"),
    ("Büyükçekmece", "Avrupa", "buyukcekmece"), ("Çatalca", "Avrupa", "catalca"), ("Esenler", "Avrupa", "esenler"),
    ("Esenyurt", "Avrupa", "esenyurt"), ("Eyüp", "Avrupa", "eyup"), ("Fatih", "Avrupa", "fatih"),
    ("Gaziosmanpaşa", "Avrupa", "gaziosmanpasa"), ("Güngören", "Avrupa", "gungoren"),
    ("Kağıthane", "Avrupa", "kagithane"), ("Küçükçekmece", "Avrupa", "kucukcekmece"),
    ("Sarıyer", "Avrupa", "sariyer"), ("Silivri", "Avrupa", "silivri"), ("Sultangazi", "Avrupa", "sultangazi"),
    ("Şişli", "Avrupa", "sisli"), ("Zeytinburnu", "Avrupa", "zeytinburnu"),
]


# ---------------------------------------------------------------- kariyer.net
def _kariyer_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for c in soup.select('div[data-test="ad-card"]'):
        a = c.select_one('a[data-test="ad-card-item"]')
        title = c.select_one('[data-test="ad-card-title"]')
        if not a or not title:
            continue
        comp = c.select_one('[data-test="subtitle"]')
        loc = c.select_one('[data-test="location"]')
        model = c.select_one('[data-test="work-model"]')
        logo = c.select_one('img[data-test="company-image"]')
        out.append({
            "source": "kariyer.net",
            "title": clean(title.get_text()),
            "company": clean(comp.get_text() if comp else ""),
            "location": clean(loc.get_text() if loc else c.get("cityname", "İstanbul")),
            "work_model": clean(model.get_text() if model else c.get("workmodeltext", "")),
            "job_type": clean(c.get("worktypetext", "")),
            "sector": clean(c.get("sectorname", "")),
            "posted": relative_date(c.get("time", "")),
            "url": "https://www.kariyer.net" + a["href"].split("?")[0],
            "logo": logo["src"] if logo and logo.get("src", "").startswith("http") else "",
            "snippet": "",
            "_sponsor": c.get("sponsor") == "true",
        })
    return out


def _kariyer_crawl(slug: str, found: dict, max_pages: int, district=None, side=None) -> int:
    """Bir listeyi, yeni ilan çıkmayana kadar (en fazla max_pages) sayfa sayfa gezer."""
    added = 0
    for p in range(1, max_pages + 1):
        html = get(f"https://www.kariyer.net/is-ilanlari/{slug}" + ("" if p == 1 else f"-{p}"))
        if not html:
            break
        cards = _kariyer_cards(html)
        organic = [c for c in cards if not c["_sponsor"]]
        if not organic:
            break
        new_here = 0
        for c in cards:
            prev = found.get(c["url"])
            if prev is None:
                found[c["url"]] = c
                prev = c
                if not c["_sponsor"]:
                    new_here += 1
            if district and not prev.get("district"):
                prev["district"], prev["side"] = district, side
        added += new_here
        if new_here == 0:
            break
    return added


def scrape_kariyer(max_pages: int, with_districts: bool) -> list[dict]:
    found: dict[str, dict] = {}
    if with_districts:  # önce ilçeler: ilana ilçe bilgisi de eklenir
        for name, side, slug in DISTRICTS:
            n = _kariyer_crawl(f"istanbul+{'asya' if side == 'Anadolu' else 'avrupa'}-{slug}", found, max_pages, name, side)
            log(f"  kariyer.net {name}: +{n}  (toplam {len(found)})")
    n = _kariyer_crawl("istanbul", found, max_pages)
    log(f"  kariyer.net İstanbul geneli: +{n}  (toplam {len(found)})")
    for j in found.values():
        j.pop("_sponsor", None)
    return list(found.values())


# ---------------------------------------------------------------- eleman.net
def scrape_eleman(max_pages: int) -> list[dict]:
    found: dict[str, dict] = {}
    for p in range(1, max_pages + 1):
        url = "https://www.eleman.net/is-ilanlari/istanbul" + ("" if p == 1 else f"?sy={p}")
        html = get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.ilan_listeleme_bol")
        if not cards:
            break
        before = len(found)
        for c in cards:
            a = c.select_one('a[href*="/is-ilani/"]')
            h = c.select_one("h3")
            if not a or not h:
                continue
            sub = c.select_one(".c-showcase-box__subtitle")
            company, location = "", "İstanbul"
            if sub:
                parts = [clean(x) for x in sub.get_text("\n").split("\n") if clean(x)]
                if parts:
                    company = parts[0]
                if len(parts) > 1:
                    location = parts[-1]
            perks, snippet = "", ""
            for t in c.select(".c-showcase-box__text"):
                if t.select_one(".hgi-eraser-add"):
                    perks = clean(t.get_text())
                else:
                    snippet = clean(t.get_text())
            logo = c.select_one("img.c-brand-logo__img")
            u = a["href"].split("?")[0]
            found.setdefault(u, {
                "source": "eleman.net",
                "title": clean(h.get_text()),
                "company": company,
                "location": location,
                "work_model": "",
                "job_type": "",
                "sector": "",
                "perks": perks,
                "posted": None,
                "url": u,
                "logo": logo["src"] if logo and logo.get("src", "").startswith("http") else "",
                "snippet": snippet[:200],
            })
        if p % 10 == 0 or len(found) == before:
            log(f"  eleman.net sayfa {p}: toplam {len(found)}")
        if len(found) == before:
            break
    return list(found.values())


# ---------------------------------------------------------------- secretcv
def _secretcv_page(url: str, found: dict, district=None, side=None) -> int:
    html = get(url)
    if not html:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    n = 0
    for c in soup.select("div.cv-job-box"):
        a = c.select_one("a.title")
        if not a or not a.get("href", "").startswith("https://www.secretcv.com/"):
            continue
        u = a["href"].split("?")[0]
        if u in found:
            if district and not found[u].get("district"):
                found[u]["district"], found[u]["side"] = district, side
            continue
        comp = c.select_one("a.company")
        city = c.select_one(".city span")
        date = c.select_one(".city small")
        logo = c.select_one("img.img-brand")
        found[u] = {
            "source": "secretcv",
            "title": clean(a.get("title") or a.get_text()),
            "company": clean(comp.get("title") if comp else ""),
            "location": clean(city.get_text() if city else "İstanbul"),
            "work_model": "",
            "job_type": "",
            "sector": "",
            "posted": relative_date(date.get_text().replace("İlan Tarihi:", "") if date else ""),
            "url": u,
            "logo": logo["src"] if logo and logo.get("src", "").startswith("http") else "",
            "snippet": "",
        }
        if district:
            found[u]["district"], found[u]["side"] = district, side
        n += 1
    return n


def scrape_secretcv(with_districts: bool) -> list[dict]:
    # robots.txt '?sf=' sayfalamasını yasaklıyor -> her listenin yalnızca 1. sayfası okunur,
    # bu yüzden il, yaka ve ilçe listelerinin hepsi ayrı ayrı gezilir.
    found: dict[str, dict] = {}
    base = "https://www.secretcv.com/is-ilanlari/"
    if with_districts:
        for name, side, slug in DISTRICTS:
            _secretcv_page(f"{base}istanbul-{side.lower()}/{slug}-is-ilanlari", found, name, side)
    for u in ("istanbul-is-ilanlari", "istanbul-avrupa-is-ilanlari", "istanbul-anadolu-is-ilanlari"):
        _secretcv_page(base + u, found)
    log(f"  secretcv: {len(found)}")
    return list(found.values())


# ---------------------------------------------------------------- isbul.net (resmi ajan API'si)
def scrape_isbul(max_pages: int) -> list[dict]:
    # isbul.net /api/agent uç noktasını robots.txt'de ajanlara açıkça izin veriyor
    out = []
    for p in range(1, max_pages + 1):
        txt = get(f"https://www.isbul.net/api/agent/jobs?city=istanbul&per_page=25&page={p}")
        if not txt:
            break
        d = json.loads(txt)
        jobs = d.get("data") or d.get("jobs") or []
        for r in jobs:
            city, dist = clean(r.get("city")), clean(r.get("district"))
            out.append({
                "source": "isbul.net",
                "title": clean(r.get("title")),
                "company": clean(r.get("company")),
                "location": " - ".join(x for x in (city, dist) if x) or "İstanbul",
                "work_model": clean(r.get("work_type")) if r.get("work_type") in ("Uzaktan", "Hibrit") else "",
                "job_type": clean(r.get("work_type")) if r.get("work_type") not in ("Uzaktan", "Hibrit") else "",
                "sector": clean(r.get("sector")),
                "posted": clean(r.get("published_at"))[:10] or None,
                "url": clean(r.get("url")),
                "logo": "",
                "snippet": clean(r.get("position")),
            })
        meta = d.get("meta") or {}
        if not jobs or p >= (meta.get("last_page") or p):
            break
    log(f"  isbul.net: {len(out)}")
    return [j for j in out if j["title"] and j["url"].startswith("https://www.isbul.net/")]


# ---------------------------------------------------------------- elemanonline
def scrape_elemanonline(max_pages: int) -> list[dict]:
    out, seen = [], set()
    for p in range(1, max_pages + 1):
        html = get("https://www.elemanonline.com.tr/is-ilanlari/istanbul" + ("" if p == 1 else f"?page={p}"))
        if not html:
            break
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            break
        jobs = (json.loads(m.group(1))["props"]["pageProps"].get("jobs") or {})
        items = (jobs.get("jobsShowcase") or []) + (jobs.get("jobs") or [])
        new = 0
        for r in items:
            if r.get("_id") in seen or not r.get("slug"):
                continue
            seen.add(r["_id"])
            new += 1
            loc = (r.get("location") or [{}])[0]
            comp = r.get("company") or {}
            logo = comp.get("profileUrl") or ""
            out.append({
                "source": "elemanonline",
                "title": clean(r.get("position")),
                "company": clean(comp.get("title")),
                "location": " - ".join(x for x in (clean(loc.get("provinceText")), clean(loc.get("townText"))) if x) or "İstanbul",
                "work_model": "",
                "job_type": clean(r.get("workingTypeText")),
                "sector": "",
                "posted": clean(r.get("publishDate"))[:10] or None,
                "url": "https://www.elemanonline.com.tr" + r["slug"],
                "logo": logo if logo.startswith("http") else "",
                "snippet": "",
            })
        if not new or p >= (jobs.get("totalPages") or p):
            break
    log(f"  elemanonline: {len(out)}")
    return out


# ---------------------------------------------------------------- JobSpy
def scrape_jobspy(site: str, wanted: int) -> list[dict]:
    from jobspy import scrape_jobs  # github.com/speedyapply/JobSpy

    df = scrape_jobs(
        site_name=[site],
        location="Istanbul, Turkey",
        results_wanted=wanted,
        hours_old=24 * KEEP_DAYS,
        country_indeed="turkey",
        linkedin_fetch_description=False,
        verbose=0,
    )
    out = []
    for _, r in df.iterrows():
        url = clean(r.get("job_url"))
        title = clean(r.get("title"))
        if not url or not title:
            continue
        posted = r.get("date_posted")
        posted = posted.isoformat() if hasattr(posted, "isoformat") else (clean(posted) or None)
        model = "Uzaktan" if r.get("is_remote") is True else ""
        jt = clean(r.get("job_type"))
        jt = {"fulltime": "Tam Zamanlı", "parttime": "Yarı Zamanlı", "internship": "Staj",
              "contract": "Sözleşmeli", "temporary": "Geçici"}.get(jt.split(",")[0], jt)
        desc = clean(r.get("description"))
        desc = re.sub(r"[*#_\\]+", "", desc)
        out.append({
            "source": "linkedin" if site == "linkedin" else "indeed",
            "title": title,
            "company": clean(r.get("company")),
            "location": clean(r.get("location")).replace(", T34", "").replace(", Türkiye", ""),
            "work_model": model,
            "job_type": jt,
            "sector": clean(r.get("company_industry")),
            "posted": posted,
            "url": url,
            "logo": clean(r.get("company_logo")) if clean(r.get("company_logo")).startswith("http") else "",
            "snippet": desc[:200],
        })
    log(f"  {site}: {len(out)}")
    return out


# ---------------------------------------------------------------- zenginleştirme
CATEGORIES = [
    ("Yazılım & IT", r"yazılım|developer|geliştirici|software|frontend|backend|full ?stack|devops|\bit\b|bilgi işlem|sistem (uzman|yönetici)|network|siber|data |veri (bilim|analist|mühendis)|python|java|\.net|react|test (uzman|mühendis)|qa\b|sap\b|erp|yapay zeka|ai\b|cloud|ciso"),
    ("Satış & Pazarlama", r"satış|sales|business development|iş geliştirme|marka uzman|brand|buyer|alıcı|pazarlama|marketing|temsilci|danışman(?!lık)|plasiyer|key account|bayi|e-?ticaret|dijital|sosyal medya|seo\b|reklam"),
    ("Mağaza & Perakende", r"mağaza|kasiyer|reyon|perakende|retail|tezgahtar|market"),
    ("Muhasebe & Finans", r"muhasebe|finans|portföy|vezne|collection|operations manager|finance|mali |accountant|accounting|bütçe|denetim|audit|vergi|tahsilat|bankacı|kredi|sigorta|treasury|ön muhasebe"),
    ("Lojistik & Şoför", r"lojistik|depo|sevkiyat|şoför|sürücü|kurye|forklift|dağıtım|nakliye|ithalat|ihracat|dış ticaret|gümrük|tır|kamyon|planlama|satın ?alma|tedarik|warehouse|logistics"),
    ("Üretim & Teknik", r"üretim|operatör|modelist|teknolog|vasıfsız|terzi|dikiş|konfeksiyon|montaj|kaynak|cnc|torna|teknisyen|tekniker|elektrik|mekanik|bakım|usta|kalfa|çırak|işçi|imalat|boyacı|tesisat|kalıp|paketleme|kalite"),
    ("Mühendislik & İnşaat", r"mühendis|engineer|mimar|inşaat|şantiye|proje (yönetici|müdür)|iş güvenliği|isg|harita|tekniker"),
    ("Yeme-İçme & Turizm", r"garson|aşçı|ekip üyesi|ikram|çay|kahve|f&b|yiyecek|aşcı|komi|barista|mutfak|şef|bulaşık|restoran|kafe|cafe|otel|resepsiyon|kat hizmet|pastane|fırın|turizm|servis personeli|bar\b"),
    ("Temizlik & Güvenlik", r"temizlik|güvenlik|bekçi|kat görevlisi|hasta bakıcı|bakıcı|apartman|site görevlisi|özel güvenlik"),
    ("Sağlık", r"hemşire|doktor|sterilizasyon|terapist|sosyal hizmet|hekim|eczacı|sağlık|ebe|fizyoterapist|diyetisyen|psikolog|laborant|klinik|tıbbi|medikal|diş"),
    ("Eğitim", r"öğretmen|eğitmen|akademisyen|okul|kreş|anaokulu|öğretim|eğitim (uzman|sorumlu)|teacher"),
    ("Müşteri Hizmetleri", r"çağrı merkezi|müşteri hizmet|müşteri temsil|call center|customer|destek uzman|danışma"),
    ("İK & İdari", r"insan kaynak|people|karşılama|\bik\b|human resources|\bhr\b|işe alım|recruit|sekreter|asistan|idari|ofis|büro|resepsiyonist|halkla|arşiv|veri giriş"),
    ("Tasarım & Medya", r"tasarım|tasarımcı|designer|grafik|editör|video|fotoğraf|içerik|metin yazar|copywriter|ui|ux|animasyon|kurgu"),
    ("Hukuk", r"avukat|hukuk|legal|stajyer avukat|noter"),
]
CAT_RE = [(name, re.compile(pat, re.I)) for name, pat in CATEGORIES]

AVRUPA = ["arnavutköy", "avcılar", "bağcılar", "bahçelievler", "bakırköy", "başakşehir", "bayrampaşa",
          "beşiktaş", "beylikdüzü", "beyoğlu", "büyükçekmece", "çatalca", "esenler", "esenyurt", "eyüp",
          "fatih", "gaziosmanpaşa", "güngören", "kağıthane", "küçükçekmece", "sarıyer", "silivri",
          "sultangazi", "şişli", "zeytinburnu", "avrupa", "avr"]
ANADOLU = ["adalar", "ataşehir", "beykoz", "çekmeköy", "kadıköy", "kartal", "maltepe", "pendik",
           "sancaktepe", "sultanbeyli", "şile", "tuzla", "ümraniye", "üsküdar", "anadolu", "asya"]
ILCELER = sorted({x for x in AVRUPA + ANADOLU if x not in ("avrupa", "avr", "anadolu", "asya")})


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def enrich(j: dict) -> dict:
    title, sector = tr_lower(j["title"]), tr_lower(j.get("sector", ""))
    j["category"] = (next((n for n, rx in CAT_RE if rx.search(title)), None)
                     or next((n for n, rx in CAT_RE if sector and rx.search(sector)), "Diğer"))
    loc = tr_lower(j.get("location", ""))
    if not j.get("district"):
        j["district"] = next((d for d, side, _ in DISTRICTS if tr_lower(d) in loc), "")
    if not j.get("side"):
        j["side"] = (next((side for d, side, _ in DISTRICTS if d == j["district"]), "") if j["district"]
                     else "Avrupa" if any(x in loc for x in AVRUPA)
                     else "Anadolu" if any(x in loc for x in ANADOLU) else "")
    text = tr_lower(f"{j['title']} {j.get('work_model', '')} {j.get('job_type', '')} {loc}")
    if not j.get("work_model"):
        if re.search(r"uzaktan|remote|evden", text):
            j["work_model"] = "Uzaktan"
        elif re.search(r"hibrit|hybrid", text):
            j["work_model"] = "Hibrit"
    if not j.get("job_type"):
        if re.search(r"part[ -]?time|yarı zamanlı", text):
            j["job_type"] = "Yarı Zamanlı"
        elif re.search(r"stajyer|intern|staj\b", text):
            j["job_type"] = "Staj"
    return j


def norm_key(j: dict) -> str:
    def n(s):
        s = unicodedata.normalize("NFKD", tr_lower(s))
        return re.sub(r"[^a-z0-9]", "", s)
    return n(j["title"])[:60] + "|" + n(j["company"])[:30]


def job_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- ana akış
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "site" / "jobs.json")
    ap.add_argument("--quick", action="store_true", help="az sayfa (test için)")
    args = ap.parse_args()

    q = args.quick
    sources = {
        "kariyer.net": lambda: scrape_kariyer(1 if q else 100, not q),
        "eleman.net": lambda: scrape_eleman(1 if q else 300),
        "secretcv": lambda: scrape_secretcv(not q),
        "isbul.net": lambda: scrape_isbul(1 if q else 100),
        "elemanonline": lambda: scrape_elemanonline(1 if q else 100),
        "indeed": lambda: scrape_jobspy("indeed", 30 if q else 1000),
        "linkedin": lambda: scrape_jobspy("linkedin", 20 if q else 150),
    }

    old = {}
    if args.out.exists():
        try:
            old = {j["id"]: j for j in json.loads(args.out.read_text("utf-8")).get("jobs", [])}
        except (ValueError, KeyError):
            old = {}

    def run(name):
        t0 = time.time()
        log(f"> {name} başladı")
        try:
            got = sources[name]()
            log(f"< {name}: {len(got)} ilan ({time.time() - t0:.0f} sn)")
            return name, got, None
        except Exception as e:  # bir kaynak bozulursa diğerleri devam etsin
            log(f"  ! {name} hata: {type(e).__name__}: {str(e)[:200]}")
            return name, [], type(e).__name__

    status, fresh = {}, []
    with ThreadPoolExecutor(max_workers=len(sources)) as ex:  # her site ayrı iş parçacığında
        for name, got, err in ex.map(run, sources):
            status[name] = {"ok": bool(got), "count": len(got)} | ({"error": err} if err else {})
            fresh += got

    now_iso = NOW.isoformat(timespec="minutes")
    merged: dict[str, dict] = {}
    for j in fresh:
        j["id"] = job_id(j["url"])
        prev = old.get(j["id"])
        j["first_seen"] = prev["first_seen"] if prev else now_iso
        j["last_seen"] = now_iso
        j["posted"] = j.get("posted") or (prev or {}).get("posted") or j["first_seen"][:10]
        merged[j["id"]] = enrich(j)

    keep_cut = (NOW - dt.timedelta(days=KEEP_DAYS)).isoformat()
    gone_cut = (NOW - dt.timedelta(days=GONE_DAYS)).isoformat()
    for jid, j in old.items():  # bu turda görünmeyen eski ilanlar
        if jid in merged:
            continue
        src_ok = status.get(j.get("source"), {}).get("ok")
        if j.get("last_seen", "") >= (gone_cut if src_ok else keep_cut):
            merged[jid] = j

    # aynı ilan farklı sitelerde -> tek kart, diğer kaynaklar "also" olarak eklenir
    by_key: dict[str, dict] = {}
    for j in sorted(merged.values(), key=lambda x: (x["first_seen"], x["source"] != "kariyer.net")):
        j.pop("also", None)
        k = norm_key(j)
        first = by_key.get(k)
        if first is None:
            by_key[k] = j
        elif first["source"] != j["source"] and not any(a["source"] == j["source"] for a in first.get("also", [])):
            first.setdefault("also", []).append({"source": j["source"], "url": j["url"]})
            for f in ("district", "side", "logo", "snippet", "job_type", "work_model"):
                if not first.get(f) and j.get(f):
                    first[f] = j[f]
        elif first["source"] == j["source"]:
            # aynı sitede aynı başlık+firma ama farklı ilçe -> ayrı ilan say
            k2 = k + "|" + (j.get("district") or j["id"])
            by_key.setdefault(k2, j)
    jobs = sorted(by_key.values(), key=lambda x: (x.get("posted") or "", x["first_seen"]), reverse=True)

    data = {"updated": now_iso, "city": "İstanbul", "sources": status, "count": len(jobs), "jobs": jobs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    log(f"= {len(jobs)} ilan -> {args.out}  {json.dumps(status, ensure_ascii=False)}")
    return 0 if any(s["ok"] for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
