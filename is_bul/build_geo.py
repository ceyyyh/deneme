#!/usr/bin/env python3
"""Eve uzaklık için konum verisini bir kez hazırlar -> is_bul/geo.json

Ev: PTT Evleri Mahallesi, Sarıyer (OpenStreetMap sınırının merkezi).

İş ilanı siteleri tam çalışma adresi yayınlamıyor; en kesin bilgi ilçe, bazen semt.
Bu yüzden yanlış bir kesinlik göstermek yerine:
  * semt biliniyorsa  -> semt merkezine gerçek YOL mesafesi
  * ilçe biliniyorsa  -> ilçe sınırı içine ~1,5 km aralıklarla yerleştirilen noktaların
                         hepsine yol mesafesi; en yakın / ortanca / en uzak değerler
                         ("6-13 km" gibi aralık olarak gösterilir)

Veri: OpenStreetMap Nominatim (sınırlar, semt konumları) ve OSRM (araçla yol mesafesi).
Her iki servisin kullanım kurallarına uyulur: saniyede en fazla 1 istek, sonuç dosyaya
yazılır ve iş akışı bu dosyayı kullanır (servisler her taramada tekrar sorgulanmaz).

Kullanım: python is_bul/build_geo.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from scrape import DISTRICTS, UA  # noqa: E402

OUT = Path(__file__).parent / "geo.json"
S = requests.Session()
S.headers["User-Agent"] = UA
GRID_KM = 1.5

# İlan metinlerinde sık geçen iş bölgeleri / semtler (ad, ilçe)
SEMTS = [
    ("Maslak", "Sarıyer"), ("Ayazağa", "Sarıyer"), ("İstinye", "Sarıyer"), ("Tarabya", "Sarıyer"),
    ("Yeniköy", "Sarıyer"), ("Emirgan", "Sarıyer"), ("Bahçeköy", "Sarıyer"), ("Rumelihisarı", "Sarıyer"),
    ("Levent", "Beşiktaş"), ("Etiler", "Beşiktaş"), ("Ortaköy", "Beşiktaş"), ("Bebek", "Beşiktaş"),
    ("Gayrettepe", "Beşiktaş"), ("Balmumcu", "Beşiktaş"), ("Arnavutköy", "Beşiktaş"),
    ("Mecidiyeköy", "Şişli"), ("Nişantaşı", "Şişli"), ("Esentepe", "Şişli"), ("Fulya", "Şişli"),
    ("Bomonti", "Şişli"), ("Kurtuluş", "Şişli"), ("Okmeydanı", "Şişli"),
    ("Seyrantepe", "Kağıthane"), ("Çağlayan", "Kağıthane"), ("Gültepe", "Kağıthane"),
    ("Taksim", "Beyoğlu"), ("Karaköy", "Beyoğlu"), ("Galata", "Beyoğlu"), ("Cihangir", "Beyoğlu"),
    ("Kasımpaşa", "Beyoğlu"), ("Okmeydanı", "Beyoğlu"),
    ("Eminönü", "Fatih"), ("Sultanahmet", "Fatih"), ("Aksaray", "Fatih"), ("Laleli", "Fatih"),
    ("Beyazıt", "Fatih"), ("Sirkeci", "Fatih"), ("Topkapı", "Fatih"), ("Balat", "Fatih"),
    ("Merter", "Güngören"), ("Bahçelievler", "Bahçelievler"), ("Yenibosna", "Bahçelievler"),
    ("Şirinevler", "Bahçelievler"), ("Ataköy", "Bakırköy"), ("Yeşilköy", "Bakırköy"),
    ("Florya", "Bakırköy"), ("Yeşilyurt", "Bakırköy"), ("İkitelli", "Başakşehir"),
    ("Kayaşehir", "Başakşehir"), ("Halkalı", "Küçükçekmece"), ("Sefaköy", "Küçükçekmece"),
    ("Hadımköy", "Arnavutköy"), ("İstanbul Havalimanı", "Arnavutköy"), ("Göktürk", "Eyüpsultan"),
    ("Alibeyköy", "Eyüpsultan"), ("Kemerburgaz", "Eyüpsultan"), ("Rami", "Eyüpsultan"),
    ("Topçular", "Eyüpsultan"), ("Güneşli", "Bağcılar"), ("Mahmutbey", "Bağcılar"),
    ("Kozyatağı", "Kadıköy"), ("Göztepe", "Kadıköy"), ("Moda", "Kadıköy"), ("Fikirtepe", "Kadıköy"),
    ("Bostancı", "Kadıköy"), ("Suadiye", "Kadıköy"), ("Erenköy", "Kadıköy"), ("Acıbadem", "Kadıköy"),
    ("Altunizade", "Üsküdar"), ("Kısıklı", "Üsküdar"), ("Bağlarbaşı", "Üsküdar"), ("Beylerbeyi", "Üsküdar"),
    ("Çengelköy", "Üsküdar"), ("Ünalan", "Üsküdar"), ("Kavacık", "Beykoz"), ("Anadoluhisarı", "Beykoz"),
    ("Dudullu", "Ümraniye"), ("Çakmak", "Ümraniye"), ("Şerifali", "Ümraniye"), ("Yukarı Dudullu", "Ümraniye"),
    ("Kurtköy", "Pendik"), ("Sabiha Gökçen", "Pendik"), ("Kaynarca", "Pendik"), ("Yenişehir", "Pendik"),
    ("Kozyatağı", "Ataşehir"), ("İçerenköy", "Ataşehir"), ("Barbaros", "Ataşehir"),
    ("Taşdelen", "Çekmeköy"), ("Soğanlık", "Kartal"), ("Yakacık", "Kartal"), ("Cevizli", "Maltepe"),
    ("İdealtepe", "Maltepe"), ("Küçükyalı", "Maltepe"), ("Aydınlı", "Tuzla"), ("Orhanlı", "Tuzla"),
    ("İçmeler", "Tuzla"), ("Şekerpınar", "Çayırova"), ("Beylikdüzü OSB", "Beylikdüzü"),
    ("Yakuplu", "Beylikdüzü"), ("Kıraç", "Esenyurt"), ("Avcılar", "Avcılar"), ("Ambarlı", "Avcılar"),
    ("Firuzköy", "Avcılar"), ("Bayrampaşa", "Bayrampaşa"), ("Zeytinburnu", "Zeytinburnu"),
    ("Kazlıçeşme", "Zeytinburnu"), ("Davutpaşa", "Esenler"), ("Atışalanı", "Esenler"),
]


def nominatim(params: dict) -> list:
    params = {"format": "jsonv2", "countrycodes": "tr", **params}
    for _ in range(3):
        r = S.get("https://nominatim.openstreetmap.org/search", params=params, timeout=60)
        time.sleep(1.2)
        if r.status_code == 200:
            return r.json()
        time.sleep(5)
    return []


def rings(geo: dict) -> list[list[tuple[float, float]]]:
    """GeoJSON (Multi)Polygon -> dış halkalar [(lon, lat), ...]"""
    if geo["type"] == "Polygon":
        return [[tuple(p) for p in geo["coordinates"][0]]]
    if geo["type"] == "MultiPolygon":
        return [[tuple(p) for p in poly[0]] for poly in geo["coordinates"]]
    return []


def inside(lon: float, lat: float, ring) -> bool:
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
            c = not c
        j = i
    return c


def grid(rs) -> list[tuple[float, float]]:
    lons = [p[0] for r in rs for p in r]
    lats = [p[1] for r in rs for p in r]
    dlat = GRID_KM / 111.0
    dlon = GRID_KM / (111.0 * math.cos(math.radians(41.0)))
    pts = []
    lat = min(lats) + dlat / 2
    while lat < max(lats):
        lon = min(lons) + dlon / 2
        while lon < max(lons):
            if any(inside(lon, lat, r) for r in rs):
                pts.append((round(lon, 5), round(lat, 5)))
            lon += dlon
        lat += dlat
    return pts


def road_km(home: tuple[float, float], pts: list[tuple[float, float]]) -> list[float | None]:
    """OSRM table: evden her noktaya araçla en kısa yol mesafesi (km)."""
    out: list[float | None] = []
    for i in range(0, len(pts), 90):
        chunk = pts[i:i + 90]
        coords = ";".join(f"{x},{y}" for x, y in [home] + chunk)
        url = f"https://router.project-osrm.org/table/v1/driving/{coords}"
        for attempt in range(4):
            r = S.get(url, params={"sources": "0", "annotations": "distance"}, timeout=90)
            time.sleep(1.2)
            if r.status_code == 200 and r.json().get("code") == "Ok":
                row = r.json()["distances"][0][1:]
                out += [round(d / 1000, 1) if d is not None else None for d in row]
                break
            time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"OSRM yanıt vermedi: {r.status_code}")
    return out


def main() -> None:
    home_res = nominatim({"q": "PTT Evleri Mahallesi, Sarıyer, İstanbul", "limit": 1})
    h = home_res[0]
    home = (round(float(h["lon"]), 6), round(float(h["lat"]), 6))
    print("ev:", h["display_name"], home)

    data = {
        "home": {"name": "PTT Evleri Mahallesi, Sarıyer", "lon": home[0], "lat": home[1]},
        "method": "araçla yol mesafesi (OSRM, OpenStreetMap yol ağı)",
        "districts": {},
        "semts": {},
    }
    if OUT.exists():  # önceki sonuçları koru, sadece eksikleri hesapla
        prev = json.loads(OUT.read_text("utf-8"))
        if prev.get("home", {}).get("lon") == home[0]:
            data["districts"], data["semts"] = prev.get("districts", {}), prev.get("semts", {})
    for name, side, _slug in DISTRICTS:
        if name in data["districts"] or name == "Adalar":  # Adalar'a karayolu yok
            continue
        q = "Eyüpsultan" if name == "Eyüp" else name
        res = nominatim({"q": f"{q}, İstanbul", "polygon_geojson": 1, "polygon_threshold": 0.002, "limit": 3})
        res = [r for r in res if r.get("geojson", {}).get("type") in ("Polygon", "MultiPolygon")
               and (r.get("addresstype") in ("town", "county", "city", "district", "municipality", "borough")
                    or r.get("display_name", "").startswith(f"{q}, İstanbul,"))]
        if not res:
            print("! sınır bulunamadı:", name)
            continue
        rs = rings(res[0]["geojson"])
        pts = grid(rs) or [(float(res[0]["lon"]), float(res[0]["lat"]))]
        km = [k for k in road_km(home, pts) if k is not None]
        if not km:
            continue
        data["districts"][name] = {
            "min": min(km), "median": round(statistics.median(km), 1), "max": max(km), "points": len(km),
        }
        print(f"{name:14s} {len(km):4d} nokta  {min(km):5.1f} / {statistics.median(km):5.1f} / {max(km):5.1f} km")

    semt_pts = []
    for semt, dist in SEMTS:
        if semt in data["semts"]:
            continue
        q = "Eyüpsultan" if dist == "Eyüp" else dist
        res = nominatim({"q": f"{semt}, {q}, İstanbul", "limit": 1})
        if res:
            semt_pts.append((semt, dist, (round(float(res[0]["lon"]), 6), round(float(res[0]["lat"]), 6))))
        else:
            print("! semt bulunamadı:", semt, dist)
    km = road_km(home, [p for _, _, p in semt_pts]) if semt_pts else []
    for (semt, dist, p), k in zip(semt_pts, km):
        if k is not None and semt not in data["semts"]:
            data["semts"][semt] = {"district": "Eyüp" if dist == "Eyüpsultan" else dist, "km": k,
                                   "lon": p[0], "lat": p[1]}
    print(len(data["semts"]), "semt")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print("->", OUT)


if __name__ == "__main__":
    main()
