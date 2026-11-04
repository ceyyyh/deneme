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
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA = "IstanbulIsBul/1.0 (kisisel is ilani toplayici; +https://github.com/ceyyyh/deneme)"
TZ = dt.timezone(dt.timedelta(hours=3))  # Türkiye saati
NOW = dt.datetime.now(TZ)
TODAY = NOW.date()
KEEP_DAYS = 14          # bu kadar gündür görülmeyen ilanlar silinir
DELAY = 1.5             # istekler arası bekleme (sn)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9"})


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url: str) -> str | None:
    try:
        r = SESSION.get(url, timeout=25)
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


# ---------------------------------------------------------------- kariyer.net
def scrape_kariyer(pages: int) -> list[dict]:
    out = []
    for p in range(1, pages + 1):
        url = "https://www.kariyer.net/is-ilanlari/istanbul" + ("" if p == 1 else f"-{p}")
        html = get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select('div[data-test="ad-card"]')
        if not cards:
            break
        for c in cards:
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
            })
        log(f"  kariyer.net sayfa {p}: {len(cards)}")
    return out


# ---------------------------------------------------------------- eleman.net
def scrape_eleman(pages: int) -> list[dict]:
    out = []
    for p in range(1, pages + 1):
        url = "https://www.eleman.net/is-ilanlari/istanbul" + ("" if p == 1 else f"?sy={p}")
        html = get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.ilan_listeleme_bol")
        if not cards:
            break
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
            texts = c.select(".c-showcase-box__text")
            perks, snippet = "", ""
            for t in texts:
                if t.select_one(".hgi-eraser-add"):
                    perks = clean(t.get_text())
                else:
                    snippet = clean(t.get_text())
            logo = c.select_one("img.c-brand-logo__img")
            out.append({
                "source": "eleman.net",
                "title": clean(h.get_text()),
                "company": company,
                "location": location,
                "work_model": "",
                "job_type": "",
                "sector": "",
                "perks": perks,
                "posted": None,
                "url": a["href"].split("?")[0],
                "logo": logo["src"] if logo and logo.get("src", "").startswith("http") else "",
                "snippet": snippet[:220],
            })
        log(f"  eleman.net sayfa {p}: {len(cards)}")
    return out


# ---------------------------------------------------------------- secretcv
def scrape_secretcv() -> list[dict]:
    # robots.txt '?sf=' sayfalamasını yasaklıyor -> sadece ilk sayfa
    html = get("https://www.secretcv.com/is-ilanlari/istanbul-is-ilanlari")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for c in soup.select("div.cv-job-box"):
        a = c.select_one("a.title")
        if not a or not a.get("href", "").startswith("https://www.secretcv.com/"):
            continue
        comp = c.select_one("a.company")
        city = c.select_one(".city span")
        date = c.select_one(".city small")
        logo = c.select_one("img.img-brand")
        out.append({
            "source": "secretcv",
            "title": clean(a.get("title") or a.get_text()),
            "company": clean(comp.get("title") if comp else ""),
            "location": clean(city.get_text() if city else "İstanbul"),
            "work_model": "",
            "job_type": "",
            "sector": "",
            "posted": relative_date(date.get_text().replace("İlan Tarihi:", "") if date else ""),
            "url": a["href"].split("?")[0],
            "logo": logo["src"] if logo and logo.get("src", "").startswith("http") else "",
            "snippet": "",
        })
    log(f"  secretcv: {len(out)}")
    return out


# ---------------------------------------------------------------- JobSpy
def scrape_jobspy(site: str, wanted: int) -> list[dict]:
    from jobspy import scrape_jobs  # github.com/speedyapply/JobSpy

    df = scrape_jobs(
        site_name=[site],
        location="Istanbul, Turkey",
        results_wanted=wanted,
        hours_old=168,
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
            "snippet": desc[:220],
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
    j["side"] = ("Avrupa" if any(x in loc for x in AVRUPA)
                 else "Anadolu" if any(x in loc for x in ANADOLU) else "")
    j["district"] = next((x.title() for x in ILCELER if x in loc), "")
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

    pages = 1 if args.quick else 6
    sources = {
        "kariyer.net": lambda: scrape_kariyer(pages),
        "eleman.net": lambda: scrape_eleman(pages),
        "secretcv": scrape_secretcv,
        "indeed": lambda: scrape_jobspy("indeed", 30 if args.quick else 200),
        "linkedin": lambda: scrape_jobspy("linkedin", 20 if args.quick else 100),
    }

    old = {}
    if args.out.exists():
        try:
            old = {j["id"]: j for j in json.loads(args.out.read_text("utf-8")).get("jobs", [])}
        except (ValueError, KeyError):
            old = {}

    status, fresh = {}, []
    for name, fn in sources.items():
        log(f"> {name}")
        try:
            got = fn()
            status[name] = {"ok": bool(got), "count": len(got)}
            fresh += got
        except Exception as e:  # bir kaynak bozulursa diğerleri devam etsin
            log(f"  ! {name} hata: {type(e).__name__}: {str(e)[:200]}")
            status[name] = {"ok": False, "count": 0, "error": type(e).__name__}

    now_iso = NOW.isoformat(timespec="minutes")
    merged: dict[str, dict] = {}
    for j in fresh:
        j["id"] = job_id(j["url"])
        prev = old.get(j["id"])
        j["first_seen"] = prev["first_seen"] if prev else now_iso
        j["last_seen"] = now_iso
        j["posted"] = j.get("posted") or (prev or {}).get("posted") or j["first_seen"][:10]
        merged[j["id"]] = enrich(j)

    cutoff = (NOW - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for jid, j in old.items():  # bu turda görünmeyen eski ilanları bir süre tut
        if jid not in merged and j.get("last_seen", "") >= cutoff:
            merged[jid] = j

    # aynı ilan farklı sitelerde -> tek kart, diğer kaynaklar "also" olarak eklenir
    by_key: dict[str, dict] = {}
    for j in sorted(merged.values(), key=lambda x: x["first_seen"]):
        k = norm_key(j)
        if k in by_key and by_key[k]["source"] != j["source"]:
            also = by_key[k].setdefault("also", [])
            if not any(a["url"] == j["url"] for a in also):
                also.append({"source": j["source"], "url": j["url"]})
        else:
            j.pop("also", None) if k not in by_key else None
            by_key.setdefault(k, j)
    jobs = sorted(by_key.values(), key=lambda x: (x.get("posted") or "", x["first_seen"]), reverse=True)

    data = {"updated": now_iso, "city": "İstanbul", "sources": status, "count": len(jobs), "jobs": jobs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    log(f"= {len(jobs)} ilan -> {args.out}  {json.dumps(status, ensure_ascii=False)}")
    return 0 if any(s["ok"] for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
