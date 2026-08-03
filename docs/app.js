/* 体育情报站 — 纯前端逻辑（无外部 CDN 依赖）
 * 数据来自同目录 data.json；可视化用原生 SVG；个性化存 localStorage。
 */
"use strict";

const LS = { bm: "sports_hub_bookmarks", hist: "sports_hub_history", subs: "sports_hub_subs", mon: "sports_hub_monitors", kw: "sports_hub_keywords" };
const SENT_LABEL = { pos: "正面", neg: "负面", neu: "中性" };
const SPORT_EMOJI = { "足球":"⚽","篮球":"🏀","电竞":"🎮","网球":"🎾","排球":"🏐","乒乓球":"🏓","羽毛球":"🏸","棒球":"⚾","橄榄球":"🏈","游泳":"🏊","跑步":"🏃","综合":"🏅" };
const PALETTE = ["#1D7AF0","#E63946","#18C29C","#F4A623","#7B61FF","#2EC4B6","#FF6B35","#3A86FF","#06D6A0","#EF476F","#118AB2","#073B4C","#9B5DE5","#0B1F3A"];

function sportEmoji(s){ return SPORT_EMOJI[s] || "🏟️"; }
function lsGet(k, d){ try{ const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; }catch(e){ return d; } }
function lsSet(k, v){ localStorage.setItem(k, JSON.stringify(v)); }
function esc(s){ return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c])); }
function fmtDate(s){ if(!s) return "未知"; return s.replace("T"," ").slice(0, 16); }
function toggleSet(set, v){ if(set.has(v)) set.delete(v); else set.add(v); }

const STATE = {
  data: [], stats: null,
  filters: { search: "", sort: "new", range: 30, sports: new Set(), categories: new Set(), sources: new Set(), sentiment: "all" },
  tab: "all", showN: 60,
  bookmarks: lsGet(LS.bm, []),
  history: lsGet(LS.hist, []),
  subs: lsGet(LS.subs, { sports: [], entities: [] }),
  monitors: lsGet(LS.mon, []),
  keywords: lsGet(LS.kw, []),
};
window.getArt = id => STATE.data.find(a => a.id === id);

/* ---------------- 可视化 ---------------- */
function arc(cx, cy, r, a0, a1, color, title){
  const p = a => [cx + r * Math.cos(Math.PI * a / 180), cy + r * Math.sin(Math.PI * a / 180)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  const large = (a1 - a0) > 180 ? 1 : 0;
  return `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 ${large},1 ${x1.toFixed(1)},${y1.toFixed(1)} Z" fill="${color}" stroke="#fff" stroke-width="1.5"><title>${title}</title></path>`;
}
function pieSVG(data, title){
  const entries = Object.entries(data || {}).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if(!total) return '<div class="note">暂无数据</div>';
  const cx = 90, cy = 90, r = 82; let start = 0, paths = "", legend = "";
  entries.forEach(([label, val], i) => {
    const frac = val / total, end = start + frac * 360, color = PALETTE[i % PALETTE.length];
    paths += arc(cx, cy, r, start, end, color, `${label}: ${val} (${(frac*100).toFixed(1)}%)`);
    legend += `<div style="display:flex;align-items:center;gap:6px;font-size:12px;margin:2px 0;"><span style="width:12px;height:12px;border-radius:3px;background:${color};display:inline-block;"></span>${esc(label)} · ${val} · ${(frac*100).toFixed(1)}%</div>`;
    start = end;
  });
  return `<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;"><svg width="180" height="180" viewBox="0 0 180 180">${paths}<circle cx="${cx}" cy="${cy}" r="${(r*0.45).toFixed(1)}" fill="#fff"/><text x="${cx}" y="${cy-3}" text-anchor="middle" font-size="20" font-weight="800" fill="#14213D">${total}</text><text x="${cx}" y="${cy+15}" text-anchor="middle" font-size="10" fill="#8A8290">${title}</text></svg><div style="min-width:140px;">${legend}</div></div>`;
}
function stackedBar(dailySport){
  const sports = Object.keys(dailySport || {});
  if(!sports.length) return '<div class="note">暂无数据</div>';
  let dates = [...new Set(sports.flatMap(s => Object.keys(dailySport[s])))].sort().slice(-30);
  const W = Math.max(300, dates.length * 22 + 40), H = 210, padL = 30, padB = 38, padT = 12;
  const maxTotal = Math.max(1, ...dates.map(d => sports.reduce((s, sp) => s + (dailySport[sp][d] || 0), 0)));
  const plotH = H - padB - padT, plotW = W - padL - 12, bw = plotW / dates.length;
  let bars = "";
  dates.forEach((d, i) => {
    let y = H - padB; const x = padL + i * bw + bw * 0.15, w = bw * 0.7;
    sports.forEach((sp, si) => {
      const v = dailySport[sp][d] || 0; if(!v) return;
      const h = v / maxTotal * plotH, color = PALETTE[si % PALETTE.length];
      bars += `<rect x="${x.toFixed(1)}" y="${(y-h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}"><title>${d} ${sp}: ${v}</title></rect>`;
      y -= h;
    });
  });
  let xlabels = "";
  const step = Math.max(1, Math.ceil(dates.length / 8));
  dates.forEach((d, i) => { if(i % step === 0 || i === dates.length - 1){ const x = padL + i * bw + bw/2; xlabels += `<text x="${x.toFixed(1)}" y="${H-padB+14}" font-size="9" fill="#8A8290" text-anchor="middle">${d.slice(5)}</text>`; } });
  const legend = sports.map((sp, si) => `<span class="chip sport">${sportEmoji(sp)} ${esc(sp)}</span>`).join("");
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="max-width:100%;">${bars}${xlabels}<line x1="${padL}" y1="${H-padB}" x2="${W-12}" y2="${H-padB}" stroke="#d8e0ec"/></svg><div class="filter-group" style="margin-top:8px;">${legend}</div>`;
}
function lineChart(dailyTotal){
  const dates = Object.keys(dailyTotal || {}).sort().slice(-7);
  if(!dates.length) return '<div class="note">暂无数据</div>';
  const vals = dates.map(d => dailyTotal[d]);
  const maxV = Math.max(1, ...vals), W = 320, H = 185, padL = 30, padB = 28, padT = 14, padR = 12;
  const plotW = W - padL - padR, plotH = H - padB - padT;
  const pts = dates.map((d, i) => [padL + i * plotW / (dates.length - 1 || 1), padT + plotH - (vals[i] / maxV) * plotH]);
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  let dots = "", labels = "", grid = "";
  for(let g = 0; g <= 2; g++){ const y = padT + plotH * g / 2, v = Math.round(maxV * (1 - g / 2)); grid += `<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="#eef2f7"/><text x="${padL-4}" y="${y+3}" font-size="8" fill="#aab" text-anchor="end">${v}</text>`; }
  pts.forEach((p, i) => { dots += `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5" fill="#1D7AF0"><title>${dates[i]}: ${vals[i]}</title></circle>`; if(i % Math.ceil(dates.length/7) === 0 || i === dates.length-1){ labels += `<text x="${p[0].toFixed(1)}" y="${H-padB+13}" font-size="9" fill="#8A8290" text-anchor="middle">${dates[i].slice(5)}</text>`; } });
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="max-width:100%;">${grid}<path d="${path}" fill="none" stroke="#1D7AF0" stroke-width="2.5" stroke-linejoin="round"/>${dots}${labels}</svg>`;
}
function wordCloud(freq){
  const entries = Object.entries(freq || {});
  if(!entries.length) return '<div class="note">暂无数据</div>';
  const maxf = Math.max(...entries.map(e => e[1])), minf = Math.min(...entries.map(e => e[1]));
  let spans = "";
  entries.forEach(([w, f], i) => {
    const size = maxf === minf ? 22 : 14 + 26 * (f - minf) / (maxf - minf);
    const color = PALETTE[i % PALETTE.length], rot = (i % 5 - 2) * 2;
    spans += `<span class="cloudw" data-w="${esc(w)}" title="${esc(w)}: ${f}" style="display:inline-block;font-size:${size.toFixed(0)}px;color:${color};font-weight:800;margin:2px 7px;transform:rotate(${rot}deg);cursor:pointer;">${esc(w)}</span>`;
  });
  return `<div style="padding:12px;background:#F4F8FD;border:2px dashed #1D7AF0;border-radius:16px;text-align:center;line-height:1.5;">${spans}</div>`;
}
function renderViz(){
  document.getElementById("viz-source").innerHTML = pieSVG(STATE.stats.source_pie, "发文总数");
  const sl = {}; Object.entries(STATE.stats.sentiment_pie || {}).forEach(([k, v]) => { sl = { ...sl, [({pos:"正面", neg:"负面", neu:"中性"}[k] || k)]: v }; });
  document.getElementById("viz-sentiment").innerHTML = pieSVG(sl, "情感");
  document.getElementById("viz-stacked").innerHTML = stackedBar(STATE.stats.daily_sport);
  document.getElementById("viz-line").innerHTML = lineChart(STATE.stats.daily_total);
  document.getElementById("viz-cloud").innerHTML = wordCloud(STATE.stats.keyword_freq);
  document.querySelectorAll("#viz-cloud .cloudw").forEach(el => { el.onclick = () => { const s = el.dataset.w; document.getElementById("search").value = s; STATE.filters.search = s; render(); }; });
}

/* ---------------- 统计卡片 ---------------- */
function renderStats(){
  const s = STATE.stats, sp = s.sentiment_pie || {};
  document.getElementById("stat-row").innerHTML = `
    <div class="stat accent"><div class="num">${s.total || 0}</div><div class="lbl">📰 资讯总数</div></div>
    <div class="stat green"><div class="num">${sp.pos || 0}</div><div class="lbl">😊 正面</div></div>
    <div class="stat red"><div class="num">${sp.neg || 0}</div><div class="lbl">😟 负面</div></div>
    <div class="stat amber"><div class="num">${sp.neu || 0}</div><div class="lbl">😐 中性</div></div>
    <div class="stat accent"><div class="num">${s.comments_total || 0}</div><div class="lbl">💬 评论数</div></div>
    <div class="stat"><div class="num">${Object.keys(s.source_pie || {}).length}</div><div class="lbl">🔗 数据源</div></div>`;
}

/* ---------------- 全文检索文本 ---------------- */
function haystack(a){
  return (a.title + " " + (a.summary || "") + " " + (a.content || "") + " " +
    (a.entity_tags || []).join(" ") + " " + (a.kw_tags || []).join(" ") + " " +
    (a.category_tags || []).join(" ")).toLowerCase();
}

/* ---------------- 筛选 ---------------- */
function applyFilters(){
  let list = STATE.data.slice();
  const f = STATE.filters;
  if(f.range > 0){ const cut = Date.now() - f.range * 864e5; list = list.filter(a => !a.published_at || new Date(a.published_at).getTime() >= cut); }
  if(f.sports.size){ list = list.filter(a => (a.sport_tags || []).some(s => f.sports.has(s))); }
  if(f.categories.size){ list = list.filter(a => (a.category_tags || []).some(c => f.categories.has(c))); }
  if(f.sources.size){ list = list.filter(a => f.sources.has(a.source_id)); }
  if(f.sentiment !== "all"){ list = list.filter(a => (a.sentiment || "neu") === f.sentiment); }
  if(f.search){ const q = f.search.toLowerCase(); list = list.filter(a => haystack(a).includes(q)); }
  if(STATE.keywords.length){
    const ks = STATE.keywords.map(k => k.toLowerCase());
    list = list.filter(a => ks.some(k => haystack(a).includes(k)));
  }
  if(STATE.tab === "subs"){
    const sp = new Set(STATE.subs.sports), en = STATE.subs.entities;
    if(sp.size || en.length){
      const enRe = en.length ? new RegExp(en.map(e => e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "i") : null;
      list = list.filter(a => (sp.size && (a.sport_tags || []).some(s => sp.has(s))) || (en.length && ((a.entity_tags || []).some(e => en.includes(e)) || (enRe && enRe.test(a.title + a.summary)))));
    }
  }
  if(STATE.tab === "bookmarks"){ const urls = new Set(STATE.bookmarks.map(b => b.url)); list = list.filter(a => urls.has(a.url)); }
  if(STATE.tab === "history"){ const urls = new Set(STATE.history.map(h => h.url)); list = list.filter(a => urls.has(h.url)); }
  if(f.sort === "new") list.sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
  else if(f.sort === "comments") list.sort((a, b) => (b.comment_count || 0) - (a.comment_count || 0));
  else if(f.sort === "score") list.sort((a, b) => Math.abs((b.sentiment_score || .5) - .5) - Math.abs((a.sentiment_score || .5) - .5));
  return list;
}

/* ---------------- 卡片 ---------------- */
function cardHTML(a){
  const monitored = STATE.monitors.some(m => (a.title + " " + (a.summary||"")).includes(m)) || STATE.keywords.some(k => (a.title+" "+(a.summary||"")).includes(k));
  const bm = STATE.bookmarks.some(b => b.url === a.url);
  const s0 = (a.sport_tags && a.sport_tags[0]) || "";
  const thumb = a.image_url
    ? `<img class="thumb" src="${esc(a.image_url)}" loading="lazy" referrerpolicy="no-referrer" onerror="onImgErr(this,'${sportEmoji(s0)}')">`
    : `<div class="thumb empty">${sportEmoji(s0)}</div>`;
  const sent = a.sentiment || "neu";
  const sportChips = (a.sport_tags || []).map(s => `<span class="chip sport">${sportEmoji(s)} ${esc(s)}</span>`).join("");
  const catChips = (a.category_tags || []).slice(0,3).map(c => `<span class="chip cat">${esc(c)}</span>`).join("");
  const kwChips = (a.kw_tags || []).slice(0, 4).map(k => `<span class="chip kw">#${esc(k)}</span>`).join("");
  return `<div class="card ${monitored ? "monitored" : ""}">
    ${thumb}
    <div class="body">
      <div class="title"><a href="${esc(a.url)}" target="_blank" rel="noopener" onclick="recordHistory(${a.id})">${esc(a.title)}</a></div>
      <div class="sub">
        <span>📰 ${esc(a.source_name)}</span>
        <span class="badge-dot ${sent}"></span><span>${SENT_LABEL[sent]}</span>
        <span>🕘 ${fmtDate(a.published_at)}</span>
        ${a.comment_count ? `<span>💬 ${a.comment_count}</span>` : ""}
      </div>
      ${sportChips || catChips ? `<div class="tags">${sportChips}${catChips}</div>` : ""}
      ${a.summary ? `<div class="summary">${esc(a.summary)}</div>` : ""}
      ${kwChips ? `<div class="tags">${kwChips}</div>` : ""}
      <div class="foot">
        <div class="actions">
          <span class="star ${bm ? "on" : ""}" onclick="toggleBookmark(${a.id})">${bm ? "★" : "☆"}</span>
          <button class="btn sm ghost" onclick="openDetail(${a.id})">🔍 详情</button>
          <button class="btn sm" onclick="translateCard(${a.id})">🌐 翻译</button>
        </div>
        <a class="btn sm" href="${esc(a.url)}" target="_blank" rel="noopener">原文 ↗</a>
      </div>
    </div>
  </div>`;
}

/* ---------------- 渲染主流程 ---------------- */
function render(){
  const list = applyFilters();
  document.getElementById("bm-count").textContent = STATE.bookmarks.length ? "(" + STATE.bookmarks.length + ")" : "";
  const cardsEl = document.getElementById("cards");
  if(!list.length){
    cardsEl.innerHTML = "";
    const tip = document.getElementById("empty-tip");
    tip.style.display = "block";
    tip.textContent = STATE.tab === "bookmarks" ? "还没有收藏，点卡片上的 ☆ 即可收藏"
      : STATE.tab === "history" ? "还没有浏览记录，点开新闻卡片即可记录"
      : STATE.tab === "subs" && !(STATE.subs.sports.length || STATE.subs.entities.length) ? "先在上方勾选想订阅的运动或球队"
      : "没有匹配的新闻，换个筛选条件试试";
    return;
  }
  document.getElementById("empty-tip").style.display = "none";
  const n = Math.min(list.length, STATE.showN);
  let html = "";
  for(let i = 0; i < n; i++) html += cardHTML(list[i]);
  if(list.length > n) html += `<div style="grid-column:1/-1;text-align:center;padding:14px;"><button class="btn ghost" id="load-more">加载更多（还剩 ${list.length - n} 条）</button></div>`;
  cardsEl.innerHTML = html;
  const lm = document.getElementById("load-more");
  if(lm) lm.onclick = () => { STATE.showN += 60; render(); };
}

/* ---------------- 个性化 ---------------- */
window.recordHistory = function(id){
  const a = window.getArt(id); if(!a) return;
  STATE.history = STATE.history.filter(h => h.url !== a.url);
  STATE.history.unshift({ id: a.id, title: a.title, url: a.url, source: a.source_name, published: a.published_at });
  if(STATE.history.length > 100) STATE.history = STATE.history.slice(0, 100);
  lsSet(LS.hist, STATE.history);
};
window.toggleBookmark = function(id){
  const a = window.getArt(id); if(!a) return;
  const i = STATE.bookmarks.findIndex(b => b.url === a.url);
  if(i >= 0) STATE.bookmarks.splice(i, 1);
  else STATE.bookmarks.unshift({ id: a.id, title: a.title, url: a.url, source: a.source_name, published: a.published_at });
  lsSet(LS.bm, STATE.bookmarks);
  render();
};
window.onImgErr = function(img, em){
  const d = document.createElement("div"); d.className = "thumb empty"; d.textContent = em;
  if(img.parentNode) img.parentNode.replaceChild(d, img);
};

/* ---------------- 订阅面板 ---------------- */
function initSubs(){
  const sports = new Set(); STATE.data.forEach(a => (a.sport_tags || []).forEach(s => sports.add(s)));
  const box = document.getElementById("sub-sport");
  [...sports].sort().forEach(s => {
    const el = document.createElement("span");
    el.className = "toggle" + (STATE.subs.sports.includes(s) ? " active" : "");
    el.textContent = sportEmoji(s) + " " + s;
    el.onclick = () => {
      const i = STATE.subs.sports.indexOf(s);
      if(i >= 0) STATE.subs.sports.splice(i, 1); else STATE.subs.sports.push(s);
      lsSet(LS.subs, STATE.subs); el.classList.toggle("active"); render();
    };
    box.appendChild(el);
  });
  const ei = document.getElementById("sub-entity");
  ei.onkeydown = e => { if(e.key === "Enter" && ei.value.trim()){ const v = ei.value.trim(); if(!STATE.subs.entities.includes(v)) STATE.subs.entities.push(v); lsSet(LS.subs, STATE.subs); ei.value = ""; renderSubEntities(); render(); } };
  renderSubEntities();
}
function renderSubEntities(){
  document.getElementById("sub-entity-list").innerHTML = STATE.subs.entities.map(en => `<span class="chip" style="cursor:pointer" onclick="removeSubEntity('${esc(en)}')">${esc(en)} ✕</span>`).join("") || '<span class="note">还没有订阅的球队/球员</span>';
}
window.removeSubEntity = function(en){ STATE.subs.entities = STATE.subs.entities.filter(x => x !== en); lsSet(LS.subs, STATE.subs); renderSubEntities(); render(); };

/* ---------------- 自定义关键词 ---------------- */
function renderKw(){
  document.getElementById("kw-list").innerHTML = STATE.keywords.map(k => `<span class="chip kw" style="cursor:pointer" onclick="removeKw('${esc(k)}')">🔑 ${esc(k)} ✕</span>`).join("") || '<span class="note">还没有自定义关键词，添加后可按项目/关键词筛选</span>';
}
function addKw(){
  const inp = document.getElementById("kw-input");
  const v = inp.value.trim(); if(!v) return;
  if(!STATE.keywords.includes(v)) STATE.keywords.push(v);
  lsSet(LS.kw, STATE.keywords); inp.value = ""; renderKw(); render();
}
window.removeKw = function(k){ STATE.keywords = STATE.keywords.filter(x => x !== k); lsSet(LS.kw, STATE.keywords); renderKw(); render(); };

/* ---------------- 监控面板 ---------------- */
function monitorHits(){
  const h = {};
  STATE.monitors.forEach(m => { h[m] = STATE.data.filter(a => haystack(a).includes(m.toLowerCase())).length; });
  return h;
}
function initMonitor(){
  const mi = document.getElementById("mon-input");
  mi.onkeydown = e => { if(e.key === "Enter" && mi.value.trim()){ const v = mi.value.trim(); if(!STATE.monitors.includes(v)) STATE.monitors.push(v); lsSet(LS.mon, STATE.monitors); mi.value = ""; renderMon(); render(); } };
  renderMon();
}
function renderMon(){
  const hit = monitorHits();
  const box = document.getElementById("mon-list");
  box.innerHTML = STATE.monitors.map(m => `<span class="chip" style="cursor:pointer" onclick="removeMon('${esc(m)}')">📡 ${esc(m)} ${hit[m] ? `<b>(${hit[m]})</b>` : ""} ✕</span>`).join("") || '<span class="note">还没有监控词，输入后回车添加</span>';
}
window.removeMon = function(m){ STATE.monitors = STATE.monitors.filter(x => x !== m); lsSet(LS.mon, STATE.monitors); renderMon(); render(); };

/* ---------------- 文章详情（正文 + 评论） ---------------- */
window.openDetail = function(id){
  const a = window.getArt(id); if(!a) return;
  recordHistory(id);
  const sent = a.sentiment || "neu";
  const sportChips = (a.sport_tags || []).map(s => `<span class="chip sport">${sportEmoji(s)} ${esc(s)}</span>`).join("");
  const catChips = (a.category_tags || []).map(c => `<span class="chip cat">${esc(c)}</span>`).join("");
  const entChips = (a.entity_tags || []).map(e => `<span class="chip">${esc(e)}</span>`).join("");
  const kwChips = (a.kw_tags || []).slice(0, 8).map(k => `<span class="chip kw">#${esc(k)}</span>`).join("");
  const content = a.content ? a.content : (a.summary || "（暂无正文，可点击「原文」查看）");
  const comments = a.comments || [];
  const cmtHtml = comments.length ? comments.map(c => `
    <div class="comment">
      <div class="top"><span class="author">${esc(c.author)}</span><span class="likes">👍 ${c.likes || 0}</span></div>
      <div class="ctext">${esc(c.content)}</div>
      ${c.published_at ? `<div class="ctime">${fmtDate(c.published_at)}</div>` : ""}
    </div>`).join("") : '<div class="note">这篇文章暂无抓取到的评论</div>';
  document.getElementById("detail-title").textContent = a.title;
  document.getElementById("detail-body").innerHTML = `
    <div class="detail-meta">
      <span>📰 ${esc(a.source_name)}</span>
      <span class="badge-dot ${sent}"></span><span>${SENT_LABEL[sent]}</span>
      <span>🕘 ${fmtDate(a.published_at)}</span>
      ${a.comment_count ? `<span>💬 ${a.comment_count} 条评论</span>` : ""}
      <a class="btn sm" href="${esc(a.url)}" target="_blank" rel="noopener">查看原文 ↗</a>
    </div>
    <div class="detail-section-t">📄 正文</div>
    <div class="detail-content">${esc(content)}</div>
    <div class="detail-section-t">🏷️ 标签</div>
    <div class="tags" style="display:flex;flex-wrap:wrap;gap:6px;">${sportChips}${catChips}${entChips}${kwChips || '<span class="note">无</span>'}</div>
    <div class="detail-section-t">💬 网友评论（${comments.length}）</div>
    ${cmtHtml}
  `;
  document.getElementById("detail-mask").classList.add("show");
};
window.closeDetail = function(){ document.getElementById("detail-mask").classList.remove("show"); };

/* ---------------- 导出 Markdown ---------------- */
function exportMarkdown(){
  const list = applyFilters();
  let md = `# 体育情报站 · 资讯精选\n\n> 导出时间：${new Date().toLocaleString("zh-CN")}　共 ${list.length} 条\n\n`;
  const tags = {}; list.forEach(a => (a.sport_tags || []).forEach(s => tags[s] = (tags[s] || 0) + 1));
  const top = Object.entries(tags).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if(top.length) md += "**热门运动：** " + top.map(([k, v]) => `${k}(${v})`).join(" · ") + "\n\n";
  list.forEach((a, i) => {
    const ts = a.published_at ? a.published_at.replace("T", " ") : "未知时间";
    md += `## ${i + 1}. ${a.title}\n`;
    md += `来源：${a.source_name} | 时间：${ts}`;
    if(a.sport_tags && a.sport_tags.length) md += " | 运动：" + a.sport_tags.join("、");
    if(a.category_tags && a.category_tags.length) md += " | 产业：" + a.category_tags.join("、");
    md += ` | 情感：${SENT_LABEL[a.sentiment || "neu"]}\n\n`;
    if(a.summary) md += `> **摘要**：${a.summary}\n\n`;
    if(a.content) md += (a.content.length > 300 ? a.content.slice(0, 300) + "…" : a.content) + "\n\n";
    if(a.entity_tags && a.entity_tags.length) md += "**相关**：" + a.entity_tags.join("、") + "\n\n";
    if(a.comment_count) md += `**评论数**：${a.comment_count}\n\n`;
    md += `[查看原文](${a.url})\n\n---\n\n`;
  });
  openModal("📝 Markdown 导出", md, "sports-news.md");
}

/* ---------------- 翻译 ---------------- */
async function translateText(text){
  if(!text) return "（无内容可翻译）";
  try{
    const r = await fetch(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(text.slice(0, 500))}&langpair=en|zh-CN`);
    const j = await r.json();
    if(j && j.responseData && j.responseData.translatedText) return j.responseData.translatedText;
    return "（翻译服务暂不可用）";
  }catch(e){ return "（翻译服务暂不可用，可手动复制原文到翻译工具）"; }
}
window.translateCard = async function(id){
  const a = window.getArt(id); if(!a) return;
  const src = a.content || a.summary || a.title;
  openModal("🌐 翻译结果", "翻译中…", "translate.txt");
  const res = await translateText(src);
  document.getElementById("modal-text").value = `【原文】\n${src}\n\n【译文】\n${res}`;
};

/* ---------------- Modal ---------------- */
function openModal(title, text, filename){
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-text").value = text;
  window.__dl = filename || "export.md";
  document.getElementById("modal-mask").classList.add("show");
}
function closeModal(){ document.getElementById("modal-mask").classList.remove("show"); }

/* ---------------- 爬虫面板 ---------------- */
function renderCrawl(){
  const cs = STATE.stats.crawl_stats || {};
  document.getElementById("crawl-stats").innerHTML = `
    <div class="stat accent"><div class="num">${cs.ok || 0}</div><div class="lbl">✓ 成功抓取</div></div>
    <div class="stat red"><div class="num">${cs.fail || 0}</div><div class="lbl">✗ 失败次数</div></div>
    <div class="stat"><div class="num">${Math.round((cs.avg_duration_ms || 0) / 1000)}s</div><div class="lbl">⏱ 平均耗时</div></div>
    <div class="stat green"><div class="num">${STATE.stats.last_crawl && STATE.stats.last_crawl.started_at ? STATE.stats.last_crawl.started_at.slice(5, 16) : "—"}</div><div class="lbl">🕘 最近抓取</div></div>`;
  const runs = (cs.runs || []).slice(0, 12);
  document.getElementById("crawl-runs").innerHTML = runs.map(r => `<div class="run-row"><span>📰 ${esc(r.source_id)} · ${r.started_at ? r.started_at.slice(5, 16) : ""}</span><span class="${r.status === "ok" ? "ok" : "fail"}">${r.status === "ok" ? `✓ ${r.fetched || 0} 条` : "✗ " + esc((r.error || "").slice(0, 24))}</span></div>`).join("") || '<div class="note">暂无抓取记录</div>';
}

/* ---------------- 初始化 ---------------- */
function initFilters(){
  const sports = new Set(), sources = {};
  STATE.data.forEach(a => { (a.sport_tags || []).forEach(s => sports.add(s)); if(a.source_id && a.source_name) sources[a.source_id] = a.source_name; });
  const fs = document.getElementById("filter-sport");
  [...sports].sort().forEach(s => {
    const el = document.createElement("span"); el.className = "toggle"; el.textContent = sportEmoji(s) + " " + s;
    el.onclick = () => { toggleSet(STATE.filters.sports, s); el.classList.toggle("active"); render(); };
    fs.appendChild(el);
  });
  const fsrc = document.getElementById("filter-source");
  Object.entries(sources).forEach(([id, name]) => {
    const el = document.createElement("span"); el.className = "toggle"; el.textContent = name;
    el.onclick = () => { toggleSet(STATE.filters.sources, id); el.classList.toggle("active"); render(); };
    fsrc.appendChild(el);
  });
  const fc = document.getElementById("filter-category");
  Object.entries(STATE.stats.categories || {}).forEach(([cat, cnt]) => {
    const el = document.createElement("span"); el.className = "toggle cat"; el.textContent = cat + " (" + cnt + ")";
    el.onclick = () => { toggleSet(STATE.filters.categories, cat); el.classList.toggle("active"); render(); };
    fc.appendChild(el);
  });
}
function bindEvents(){
  const se = document.getElementById("search"); se.oninput = () => { STATE.filters.search = se.value.trim(); render(); };
  document.getElementById("sort").onchange = e => { STATE.filters.sort = e.target.value; render(); };
  document.getElementById("range").onchange = e => { STATE.filters.range = parseInt(e.target.value, 10); STATE.showN = 60; render(); };
  document.getElementById("kw-add").onclick = addKw;
  document.getElementById("kw-input").onkeydown = e => { if(e.key === "Enter") addKw(); };
  document.querySelectorAll("#filter-sentiment .toggle").forEach(t => {
    t.onclick = () => { document.querySelectorAll("#filter-sentiment .toggle").forEach(x => x.classList.remove("active")); t.classList.add("active"); STATE.filters.sentiment = t.dataset.sent; render(); };
  });
  document.querySelectorAll("#tabs .tab").forEach(t => {
    t.onclick = () => {
      document.querySelectorAll("#tabs .tab").forEach(x => x.classList.remove("active")); t.classList.add("active");
      STATE.tab = t.dataset.tab; STATE.showN = 60;
      document.getElementById("tab-subs").style.display = STATE.tab === "subs" ? "block" : "none";
      document.getElementById("tab-monitor").style.display = STATE.tab === "monitor" ? "block" : "none";
      render();
    };
  });
  document.getElementById("btn-export").onclick = exportMarkdown;
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal-mask").onclick = e => { if(e.target.id === "modal-mask") closeModal(); };
  document.getElementById("detail-mask").onclick = e => { if(e.target.id === "detail-mask") closeDetail(); };
  document.getElementById("modal-copy").onclick = () => { const t = document.getElementById("modal-text").value; if(navigator.clipboard) navigator.clipboard.writeText(t); else document.getElementById("modal-text").select(); };
  document.getElementById("modal-download").onclick = () => {
    const blob = new Blob([document.getElementById("modal-text").value], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = window.__dl || "export.md"; a.click(); URL.revokeObjectURL(url);
  };
}

async function boot(){
  try{
    const res = await fetch("data.json", { cache: "no-store" });
    if(!res.ok) throw new Error("HTTP " + res.status);
    const j = await res.json();
    STATE.data = j.articles || []; STATE.stats = j.stats || {};
    document.getElementById("loading").style.display = "none";
    document.getElementById("app").style.display = "block";
    document.getElementById("hero-meta").innerHTML = `<b>📅 更新于 ${esc((j.generated_at || "").replace("T", " "))}</b><b>📰 ${STATE.data.length} 篇资讯</b><b>💬 ${STATE.stats.comments_total || 0} 条评论</b><b>🔗 GitHub Pages</b>`;
    renderStats(); renderViz(); initFilters(); initSubs(); initMonitor(); renderKw(); bindEvents(); render(); renderCrawl();
  }catch(e){
    document.getElementById("loading").innerHTML = "加载失败：" + esc(e.message) + "<br>请确认 data.json 已生成，或稍后刷新重试。";
  }
}
boot();
