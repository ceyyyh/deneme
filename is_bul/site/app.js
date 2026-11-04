(() => {
  "use strict";

  const PAGE = 30;
  const $ = (s) => document.querySelector(s);
  const el = {
    updated: $("#updated"), heroSub: $("#heroSub"), form: $("#searchForm"), q: $("#q"),
    district: $("#district"), chips: $("#chips"), list: $("#list"), empty: $("#empty"),
    more: $("#more"), count: $("#resultCount"), active: $("#activeFilters"), sort: $("#sort"),
    detail: $("#detail"), filters: $("#filters"), backdrop: $("#backdrop"),
    modelChecks: $("#modelChecks"), typeChecks: $("#typeChecks"), sourceChecks: $("#sourceChecks"),
    filterCount: $("#filterCount"), sourceStatus: $("#sourceStatus"),
  };

  const SOURCES = {
    "kariyer.net": "kariyer.net", "eleman.net": "eleman.net", "isbul.net": "isbul.net",
    secretcv: "SecretCV", elemanonline: "Eleman Online", indeed: "Indeed", linkedin: "LinkedIn",
    "kariyer-sayfasi": "Şirket sitesi",
  };
  const PALETTE = ["#5b3df5", "#0a66c2", "#e8590c", "#0f9d58", "#c2255c", "#1098ad", "#7048e8", "#d9480f", "#2b8a3e", "#364fc7"];

  const state = { q: "", loc: "", cat: "", date: 0, collar: "", maxKm: 0, models: new Set(), types: new Set(), sources: new Set(), sort: "new", shown: PAGE, selected: null };
  let ALL = [], META = {}, TODAY = "";

  // ---------- yardımcılar ----------
  const fold = (s) => (s || "").replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase()
    .replace(/ı/g, "i").replace(/ş/g, "s").replace(/ğ/g, "g").replace(/ç/g, "c").replace(/ö/g, "o").replace(/ü/g, "u")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
  const srcClass = (s) => "src-" + s.replace(/\./g, "-");
  const hash = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); };
  const daysBetween = (a, b) => Math.round((Date.parse(a) - Date.parse(b)) / 864e5);

  function relDay(iso) {
    if (!iso) return "";
    const d = daysBetween(TODAY, iso.slice(0, 10));
    if (d <= 0) return "Bugün";
    if (d === 1) return "Dün";
    if (d < 7) return `${d} gün önce`;
    if (d < 30) return `${Math.floor(d / 7)} hafta önce`;
    return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
  }
  function relTime(iso) {
    const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
    if (m < 60) return `${m} dk önce`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h} saat önce`;
    return `${Math.round(h / 24)} gün önce`;
  }
  const fmtKm = (k) => k.toLocaleString("tr-TR", { maximumFractionDigits: 1 });
  // semt biliniyorsa tek değer; yalnız ilçe biliniyorsa ilçe içindeki noktaların ortancası
  const typicalKm = (j) => (j.dist ? (j.dist.length === 1 ? j.dist[0] : j.dist[1]) : null);
  function kmShort(j) {
    if (!j.dist) return "";
    return j.dist.length === 1 ? `~${fmtKm(j.dist[0])} km` : `${fmtKm(j.dist[0])}–${fmtKm(j.dist[2])} km`;
  }
  const house = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/></svg>';

  function normModel(m) {
    const f = fold(m);
    if (!f) return "";
    if (/uzak|remote|evden/.test(f)) return "Uzaktan";
    if (/hib|hyb/.test(f)) return "Hibrit";
    return "İş Yerinde";
  }
  function normType(t) {
    const f = fold(t);
    if (!f) return "";
    if (/staj|intern/.test(f)) return "Staj";
    if (/yari|part/.test(f)) return "Yarı Zamanlı";
    if (/donem|gecici|tempor|sezon/.test(f)) return "Dönemsel";
    if (/sozles|contract|proje|serbest|freelance/.test(f)) return "Sözleşmeli";
    if (/tam|full/.test(f)) return "Tam Zamanlı";
    return "";
  }

  // ---------- veri ----------
  async function load() {
    el.list.innerHTML = Array.from({ length: 6 }, () => '<li class="skel"></li>').join("");
    try {
      const data = window.__JOBS__ || (await (await fetch("jobs.json", { cache: "no-store" })).json());
      init(data);
    } catch (e) {
      el.list.innerHTML = "";
      el.updated.textContent = "İlanlar yüklenemedi";
      el.empty.hidden = false;
      el.empty.querySelector("h3").textContent = "İlan verisi yüklenemedi";
      el.empty.querySelector("p").textContent = "Sayfayı yenilemeyi deneyin.";
    }
  }

  function init(data) {
    META = data;
    TODAY = new Date(Date.parse(data.updated)).toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
    ALL = data.jobs.map((j) => ({
      ...j,
      model: normModel(j.work_model),
      type: normType(j.job_type),
      _text: fold([j.title, j.company, j.location, j.district, j.category, j.sector, j.snippet, j.perks].join(" ")),
    }));

    el.updated.innerHTML = `<span class="dot" aria-hidden="true"></span><span><span class="full">Güncellendi: </span>${esc(relTime(data.updated))} · <b>${ALL.length.toLocaleString("tr-TR")}</b> ilan</span>`;
    const okSources = Object.entries(data.sources || {}).filter(([, s]) => s.ok).map(([k]) => SOURCES[k] || k);
    if (okSources.length) el.heroSub.textContent = okSources.join(" · ");
    el.sourceStatus.textContent = "Son tarama: " + new Date(data.updated).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" }) + " — " +
      Object.entries(data.sources || {}).map(([k, s]) => `${SOURCES[k] || k}: ${s.ok ? s.count : "alınamadı"}`).join(", ");

    buildDistricts();
    buildChecks(el.modelChecks, "models", ["İş Yerinde", "Hibrit", "Uzaktan"], (j) => j.model);
    buildChecks(el.typeChecks, "types", ["Tam Zamanlı", "Yarı Zamanlı", "Dönemsel", "Sözleşmeli", "Staj"], (j) => j.type);
    buildChecks(el.sourceChecks, "sources", Object.keys(SOURCES), (j) => j.source, (k) => SOURCES[k]);
    readUrl();
    render();
  }

  function buildDistricts() {
    const by = { Avrupa: new Map(), Anadolu: new Map() };
    for (const j of ALL) if (j.district && by[j.side]) by[j.side].set(j.district, (by[j.side].get(j.district) || 0) + 1);
    for (const side of ["Avrupa", "Anadolu"]) {
      if (!by[side].size) continue;
      const g = document.createElement("optgroup");
      g.label = `${side} Yakası ilçeleri`;
      [...by[side].entries()].sort((a, b) => a[0].localeCompare(b[0], "tr")).forEach(([d, n]) => {
        g.append(new Option(`${d} (${n})`, "d:" + d));
      });
      el.district.append(g);
    }
  }

  function buildChecks(box, key, values, getter, label = (v) => v) {
    const counts = new Map();
    for (const j of ALL) { const v = getter(j); if (v) counts.set(v, (counts.get(v) || 0) + 1); }
    box.innerHTML = values.filter((v) => counts.get(v)).map((v) =>
      `<label class="check"><input type="checkbox" value="${esc(v)}" data-key="${key}"><span${key === "sources" ? ` class="src ${srcClass(v)}"` : ""}>${esc(label(v))}</span><span class="n">${counts.get(v)}</span></label>`
    ).join("") || '<span class="muted">—</span>';
  }

  // ---------- filtreleme ----------
  function matches(j, skip) {
    if (state.q) {
      for (const w of fold(state.q).split(/\s+/).filter(Boolean)) if (!j._text.includes(w)) return false;
    }
    if (state.loc) {
      const [k, v] = state.loc.split(/:(.*)/s);
      if (k === "side" && j.side !== v) return false;
      if (k === "d" && j.district !== v) return false;
    }
    if (skip !== "cat" && state.cat && j.category !== state.cat) return false;
    if (state.date) {
      const d = daysBetween(TODAY, (j.posted || j.first_seen).slice(0, 10));
      if (d >= state.date) return false;
    }
    if (state.collar && j.collar !== state.collar) return false;
    if (state.maxKm) { const k = typicalKm(j); if (k === null || k > state.maxKm) return false; }
    if (state.models.size && !state.models.has(j.model)) return false;
    if (state.types.size && !state.types.has(j.type)) return false;
    if (state.sources.size && !state.sources.has(j.source)) return false;
    return true;
  }

  function sorted(list) {
    const c = (a, b) => (a || "").localeCompare(b || "", "tr");
    if (state.sort === "company") return list.sort((a, b) => c(a.company, b.company));
    if (state.sort === "title") return list.sort((a, b) => c(a.title, b.title));
    if (state.sort === "near") return list.sort((a, b) => (typicalKm(a) ?? 1e9) - (typicalKm(b) ?? 1e9) || c(b.posted, a.posted));
    return list.sort((a, b) => c(b.posted, a.posted) || c(b.first_seen, a.first_seen));
  }

  // ---------- çizim ----------
  function logoHtml(j) {
    const name = (j.company || j.title || "?").trim();
    const initial = esc(name.charAt(0).toLocaleUpperCase("tr"));
    const bg = PALETTE[hash(name) % PALETTE.length];
    const src = safeUrl(j.logo);
    return src
      ? `<div class="logo" style="background:${bg}" aria-hidden="true"><span>${initial}</span><img src="${esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer"></div>`
      : `<div class="logo" style="background:${bg}" aria-hidden="true">${initial}</div>`;
  }

  const pin = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>';

  function cardHtml(j) {
    const place = j.semt ? `${j.semt}, ${j.district}` : j.district;
    const loc = place ? `${place}${j.side ? " · " + j.side : ""}` : j.side ? `${j.side} Yakası` : (j.location || "İstanbul");
    const isNew = j.posted && daysBetween(TODAY, j.posted.slice(0, 10)) <= 0;
    const tags = [
      isNew ? '<span class="tag new">Yeni</span>' : "",
      j.model ? `<span class="tag">${esc(j.model)}</span>` : "",
      j.type ? `<span class="tag">${esc(j.type)}</span>` : "",
      j.collar ? `<span class="tag ${j.collar === "Mavi yaka" ? "blue" : "white"}">${esc(j.collar)}</span>` : "",
    ].join("");
    return `<li class="card" tabindex="0" data-id="${esc(j.id)}" ${state.selected === j.id ? 'aria-current="true"' : ""}>
      ${logoHtml(j)}
      <div>
        <h3>${esc(j.title)}</h3>
        <div class="company">${esc(j.company || "Firma belirtilmemiş")}</div>
        <div class="meta"><span>${pin}${esc(loc)}</span>${j.dist ? `<span class="km" title="Eve araçla yol mesafesi">${house}${esc(kmShort(j))}</span>` : ""}<span>${esc(j.category)}</span></div>
        <div class="tags">${tags}<span class="src ${srcClass(j.source)}">${esc(SOURCES[j.source] || j.source)}</span><span class="when">${esc(relDay(j.posted))}</span></div>
      </div>
    </li>`;
  }

  function render() {
    const result = sorted(ALL.filter((j) => matches(j)));
    el.count.textContent = `${result.length.toLocaleString("tr-TR")} ilan bulundu`;
    el.list.innerHTML = result.slice(0, state.shown).map(cardHtml).join("");
    el.empty.hidden = result.length > 0;
    el.more.hidden = result.length <= state.shown;
    el.more.textContent = `Daha fazla ilan göster (${(result.length - state.shown).toLocaleString("tr-TR")} kaldı)`;
    renderChips();
    renderActive();
    syncChecks();
    writeUrl();
    if (!state.selected && result[0] && window.matchMedia("(min-width: 1101px)").matches) showDetail(result[0].id, false);
  }

  function renderChips() {
    const counts = new Map();
    let total = 0;
    for (const j of ALL) if (matches(j, "cat")) { counts.set(j.category, (counts.get(j.category) || 0) + 1); total++; }
    const cats = [...counts.entries()].sort((a, b) => (a[0] === "Diğer") - (b[0] === "Diğer") || b[1] - a[1]);
    el.chips.innerHTML = [`<button class="chip" type="button" data-cat="" aria-pressed="${!state.cat}">Tümü<small>${total}</small></button>`]
      .concat(cats.map(([c, n]) => `<button class="chip" type="button" data-cat="${esc(c)}" aria-pressed="${state.cat === c}">${esc(c)}<small>${n}</small></button>`))
      .join("");
  }

  function renderActive() {
    const items = [];
    if (state.q) items.push(["q", "", `“${state.q}”`]);
    if (state.loc) items.push(["loc", "", el.district.selectedOptions[0]?.textContent.replace(/\s\(\d+\)$/, "") || state.loc]);
    if (state.cat) items.push(["cat", "", state.cat]);
    if (state.date) items.push(["date", "", state.date === 1 ? "Bugün" : `Son ${state.date} gün`]);
    if (state.collar) items.push(["collar", "", state.collar]);
    if (state.maxKm) items.push(["maxKm", "", `Eve ≤ ${state.maxKm} km`]);
    for (const k of ["models", "types", "sources"]) for (const v of state[k]) items.push([k, v, SOURCES[v] || v]);
    el.active.innerHTML = items.map(([k, v, t]) => `<button class="af" type="button" data-k="${k}" data-v="${esc(v)}" aria-label="${esc(t)} filtresini kaldır">${esc(t)}</button>`).join("");
    const n = (state.date ? 1 : 0) + (state.collar ? 1 : 0) + (state.maxKm ? 1 : 0) + state.models.size + state.types.size + state.sources.size;
    el.filterCount.hidden = !n;
    el.filterCount.textContent = n;
  }

  function syncChecks() {
    el.filters.querySelectorAll("input[type=checkbox]").forEach((c) => { c.checked = state[c.dataset.key].has(c.value); });
    el.filters.querySelectorAll("input[name=date]").forEach((r) => { r.checked = +r.value === state.date; });
    el.filters.querySelectorAll("input[name=collar]").forEach((r) => { r.checked = r.value === state.collar; });
    el.filters.querySelectorAll("input[name=km]").forEach((r) => { r.checked = +r.value === state.maxKm; });
    el.q.value = state.q;
    el.district.value = state.loc;
    el.sort.value = state.sort;
  }

  function showDetail(id, openSheet = true) {
    const j = ALL.find((x) => x.id === id);
    if (!j) return;
    state.selected = id;
    document.querySelectorAll(".card").forEach((c) => c.toggleAttribute("aria-current", c.dataset.id === id));
    document.querySelectorAll('.card[aria-current]').forEach((c) => c.setAttribute("aria-current", "true"));
    const url = safeUrl(j.url);
    const loc = [j.semt, j.district, j.side && `${j.side} Yakası`].filter(Boolean).join(", ") || j.location || "İstanbul";
    const home = META.home || "ev";
    const kmText = !j.dist ? "Hesaplanamadı (ilanda ilçe yok)"
      : j.dist.length === 1 ? `≈ ${fmtKm(j.dist[0])} km (${j.semt} semt merkezine)`
      : `${fmtKm(j.dist[0])} – ${fmtKm(j.dist[2])} km (ilanda sadece ilçe var; ilçe içinde nereye düştüğüne göre, ortanca ${fmtKm(j.dist[1])} km)`;
    const rows = [
      ["Konum", loc], ["Eve uzaklık (araçla)", kmText], ["Yaka", j.collar], ["Kategori", j.category], ["Çalışma şekli", j.model || "Belirtilmemiş"],
      ["Çalışma tipi", j.type || j.job_type || "Belirtilmemiş"], ["İlan tarihi", relDay(j.posted)], ["Sektör", j.sector],
      ["Yan haklar", j.perks],
    ].filter(([, v]) => v);
    const also = (j.also || []).filter((a) => safeUrl(a.url));
    el.detail.innerHTML = `
      <div class="sheet-handle" aria-hidden="true"></div>
      <button class="icon-btn d-close" type="button" aria-label="Kapat">✕</button>
      <div class="d-body">
        <div class="d-top">${logoHtml(j)}<div>
          <h2 class="d-title">${esc(j.title)}</h2>
          <div class="d-company">${esc(j.company || "Firma belirtilmemiş")}</div>
          <div class="tags"><span class="src ${srcClass(j.source)}">${esc(SOURCES[j.source] || j.source)}</span></div>
        </div></div>
        <dl class="d-grid">${rows.map(([k, v]) => `<div class="d-item"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>
        ${j.snippet ? `<p class="d-snippet">${esc(j.snippet.length >= 210 ? j.snippet.replace(/\s+\S*$/, "") + "…" : j.snippet)}</p>` : ""}
        <div class="d-actions">
          ${url ? `<a class="btn-primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">İlana git ve başvur (${esc(SOURCES[j.source] || j.source)})
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>` : ""}
          ${also.length ? `<div class="d-also">Bu ilan ayrıca: ${also.map((a) => `<a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(SOURCES[a.source] || a.source)}</a>`).join(", ")}</div>` : ""}
        </div>
        <p class="d-note">Tam ilan metni ve başvuru, ilanın yayınlandığı sitededir.</p>
      </div>`;
    el.detail.scrollTop = 0;
    if (openSheet && window.matchMedia("(max-width: 1100px)").matches) openPanel(el.detail);
  }

  // ---------- paneller (mobil) ----------
  function openPanel(p) {
    closePanels();
    p.classList.add("open");
    el.backdrop.hidden = false;
    document.body.classList.add("locked");
  }
  function closePanels() {
    el.detail.classList.remove("open");
    el.filters.classList.remove("open");
    el.backdrop.hidden = true;
    document.body.classList.remove("locked");
  }

  // ---------- URL durumu ----------
  function writeUrl() {
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.loc) p.set("yer", state.loc);
    if (state.cat) p.set("kategori", state.cat);
    if (state.date) p.set("gun", state.date);
    if (state.collar) p.set("yaka", state.collar === "Mavi yaka" ? "mavi" : "beyaz");
    if (state.maxKm) p.set("km", state.maxKm);
    const s = p.toString();
    try { history.replaceState(null, "", s ? "?" + s : location.pathname); } catch (_) { /* önizleme ortamı */ }
  }
  function readUrl() {
    const p = new URLSearchParams(location.search);
    state.q = p.get("q") || "";
    state.loc = p.get("yer") || "";
    state.cat = p.get("kategori") || "";
    state.date = +p.get("gun") || 0;
    state.collar = { mavi: "Mavi yaka", beyaz: "Beyaz yaka" }[p.get("yaka")] || "";
    state.maxKm = +p.get("km") || 0;
  }

  // ---------- olaylar ----------
  const reset = () => { state.shown = PAGE; state.selected = null; };
  let t;
  el.q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { state.q = el.q.value.trim(); reset(); render(); }, 180); });
  el.form.addEventListener("submit", (e) => { e.preventDefault(); state.q = el.q.value.trim(); state.loc = el.district.value; reset(); render(); el.q.blur(); $(".results").scrollIntoView({ behavior: "smooth", block: "start" }); });
  el.district.addEventListener("change", () => { state.loc = el.district.value; reset(); render(); });
  el.sort.addEventListener("change", () => { state.sort = el.sort.value; reset(); render(); });
  el.chips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (!b) return; state.cat = b.dataset.cat; reset(); render(); });
  el.filters.addEventListener("change", (e) => {
    const i = e.target;
    if (i.name === "date") state.date = +i.value;
    else if (i.name === "collar") state.collar = i.value;
    else if (i.name === "km") state.maxKm = +i.value;
    else if (i.dataset.key) i.checked ? state[i.dataset.key].add(i.value) : state[i.dataset.key].delete(i.value);
    reset(); render();
  });
  const clearAll = () => { Object.assign(state, { q: "", loc: "", cat: "", date: 0, collar: "", maxKm: 0 }); state.models.clear(); state.types.clear(); state.sources.clear(); reset(); render(); };
  $("#clearAll").addEventListener("click", clearAll);
  $("#emptyClear").addEventListener("click", clearAll);
  el.active.addEventListener("click", (e) => {
    const b = e.target.closest(".af"); if (!b) return;
    const k = b.dataset.k;
    if (["models", "types", "sources"].includes(k)) state[k].delete(b.dataset.v);
    else state[k] = k === "date" || k === "maxKm" ? 0 : "";
    reset(); render();
  });
  el.more.addEventListener("click", () => { state.shown += PAGE; render(); });
  el.list.addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) showDetail(c.dataset.id); });
  el.list.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { const c = e.target.closest(".card"); if (c) { e.preventDefault(); showDetail(c.dataset.id); } } });
  el.detail.addEventListener("click", (e) => { if (e.target.closest(".d-close")) closePanels(); });
  $("#openFilters").addEventListener("click", () => openPanel(el.filters));
  $("#closeFilters").addEventListener("click", closePanels);
  $("#showResults").addEventListener("click", closePanels);
  el.backdrop.addEventListener("click", closePanels);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePanels(); });
  // logo yalnızca gerçekten yüklenirse gösterilir; yoksa renkli baş harf kalır
  document.addEventListener("load", (e) => {
    const img = e.target;
    if (img.tagName === "IMG" && img.parentElement?.classList.contains("logo") && img.naturalWidth > 1) img.parentElement.classList.add("has-img");
  }, true);
  document.addEventListener("error", (e) => { if (e.target.tagName === "IMG") e.target.remove(); }, true);

  load();
})();
