"""The booth page: one question, five stages, nothing hidden.

WHY THIS EXISTS. The probe page answers "what did retrieval return", which is an
analyst's question and needs the analyst already in the room. A visitor walking
past needs the MECHANISM: that a trial question has a structured half and a text
half, that the layer is what separates them, and that both halves end up in ONE
statement. So this page does not show an answer. It shows a question BECOMING
SQL, a stage at a time, at the pace of whoever is narrating.

Everything on it is measured on the spot. There is no scripted timing, no canned
result, and the failure stage is the real ranking, not an illustration.

Design follows the probe page's tokens so the two read as one product. Colour is
structural, never decorative: one hue for the structured half, one for the text
half, and the reserved red only ever marks a row from the wrong half -- and it
says "wrong half" in words beside it.
"""

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>One question, two kinds of data</title><style>
:root{
  --surface:#fcfcfb; --bg:#f6f5f2; --fg:#1a1a19; --fg2:#4a4945; --mut:#6b6a66;
  --line:#e2e0da; --card:#fff;
  --struct:#2a78d6; --struct-bg:#eaf2fd;    /* the WHERE-clause half */
  --text:#8a5cd6;   --text-bg:#f1ebfc;      /* the retrieval half */
  --critical:#d03b3b; --critical-bg:#fbeceb;
  --good:#0ca30c; --good-bg:#eef8ee;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media(prefers-color-scheme:dark){:root{
  --surface:#1a1a19; --bg:#141413; --fg:#eceae5; --fg2:#c9c6bf; --mut:#96938c;
  --line:#302d28; --card:#1e1c19;
  --struct:#5b9df0; --struct-bg:#16283f;
  --text:#a684e8;   --text-bg:#241a38;
  --critical:#e66767; --critical-bg:#2e1d1d;
  --good:#3ec03e; --good-bg:#16261a;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:22px 20px 120px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}
header h1{font-size:17px;margin:0;letter-spacing:-.01em}
header .sub{color:var(--mut);font-size:12.5px}
header a{color:var(--mut);font-size:12.5px}

/* --- the ask --- */
.ask{background:var(--card);border:1px solid var(--line);border-radius:11px;
 padding:14px 15px;margin:16px 0 10px}
.ask form{display:flex;gap:8px;flex-wrap:wrap}
.ask input{flex:1;min-width:280px;font:inherit;font-size:15px;padding:9px 11px;
 border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--fg)}
.ask button{font:inherit;font-size:14px;font-weight:600;padding:9px 18px;border:0;
 border-radius:8px;background:var(--struct);color:#fff;cursor:pointer}
.ask button:disabled{opacity:.5;cursor:default}
.presets{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.presets button{font:inherit;font-size:12px;padding:5px 10px;border:1px solid var(--line);
 border-radius:20px;background:var(--surface);color:var(--fg2);cursor:pointer}
.presets button:hover{border-color:var(--struct);color:var(--fg)}

/* --- stages --- */
.stage{background:var(--card);border:1px solid var(--line);border-radius:11px;
 padding:16px 17px;margin-bottom:12px;
 opacity:0;transform:translateY(8px);transition:opacity .34s ease,transform .34s ease}
.stage.on{opacity:1;transform:none}
.stage[hidden]{display:none}
.stage>h2{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--mut);
 margin:0 0 10px;font-weight:650;display:flex;gap:9px;align-items:center}
.stage>h2 .num{display:inline-flex;align-items:center;justify-content:center;
 width:19px;height:19px;border-radius:50%;background:var(--fg);color:var(--bg);
 font-size:11px;letter-spacing:0}
.lede{font-size:14px;color:var(--fg2);margin:0 0 12px}
.lede b{color:var(--fg)}

/* 1 the question */
.q{font-size:25px;line-height:1.35;font-weight:600;letter-spacing:-.02em;margin:2px 0 10px}
.q .hl-s{background:var(--struct-bg);color:var(--struct);border-radius:4px;padding:1px 4px}
.q .hl-t{background:var(--text-bg);color:var(--text);border-radius:4px;padding:1px 4px}

/* 2 the split */
.halves{display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:800px){.halves{grid-template-columns:1fr 1fr}}
.half{border:1px solid var(--line);border-radius:9px;padding:13px 14px}
.half.s{border-left:3px solid var(--struct)}
.half.t{border-left:3px solid var(--text)}
.half h3{font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin:0 0 3px}
.half.s h3{color:var(--struct)} .half.t h3{color:var(--text)}
.half .why{font-size:12px;color:var(--mut);margin:0 0 10px}
.chip{display:block;font-family:var(--mono);font-size:12.5px;padding:6px 9px;border-radius:6px;
 margin-bottom:5px}
.half.s .chip{background:var(--struct-bg);color:var(--struct)}
.half.t .chip{background:var(--text-bg);color:var(--text)}
.chip .from{display:block;font-family:inherit;font-size:11px;color:var(--mut);margin-top:2px}
.flag{background:var(--critical-bg);border-left:3px solid var(--critical);border-radius:0 6px 6px 0;
 padding:9px 11px;font-size:12.5px;color:var(--fg2);margin-top:10px}
.flag b{color:var(--critical)}

/* 3 the sql */
pre.sql{font-family:var(--mono);font-size:11.5px;line-height:1.62;background:var(--surface);
 border:1px solid var(--line);border-radius:8px;padding:13px 14px;overflow-x:auto;margin:0;
 white-space:pre;color:var(--fg2);max-height:430px}
pre.sql mark.s{background:var(--struct-bg);color:var(--struct);font-weight:650;
 border-radius:3px;padding:1px 2px}
pre.sql mark.t{background:var(--text-bg);color:var(--text);font-weight:650;
 border-radius:3px;padding:1px 2px}
.key{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-bottom:9px}
.key i{font-style:normal;border-radius:3px;padding:1px 6px;font-family:var(--mono);font-size:11.5px}
.key i.s{background:var(--struct-bg);color:var(--struct)}
.key i.t{background:var(--text-bg);color:var(--text)}

/* 4 the scan */
.tiles{display:grid;gap:10px;grid-template-columns:repeat(2,1fr)}
@media(min-width:760px){.tiles{grid-template-columns:repeat(4,1fr)}}
.tile{border:1px solid var(--line);border-radius:9px;padding:11px 13px}
.tile .v{font-size:21px;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.tile .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin-top:2px}
.mech{font-family:var(--mono);font-size:12.5px;background:var(--surface);border:1px solid var(--line);
 border-radius:8px;padding:12px 14px;margin-top:11px;color:var(--fg2);overflow-x:auto}
.mech b{color:var(--struct)}

/* 5 results */
.cols{display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:900px){.cols{grid-template-columns:1fr 1fr}}
.col h3{font-size:12px;margin:0 0 2px}
.col .why{font-size:11.5px;color:var(--mut);margin:0 0 9px}
.row{border:1px solid var(--line);border-radius:8px;padding:9px 11px;margin-bottom:6px;font-size:12.5px}
.row.bad{background:var(--critical-bg);border-color:var(--critical)}
.row .top{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.row .nct{font-family:var(--mono);font-size:12px;color:var(--fg2)}
.row .sec{font-size:10px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;
 border-radius:3px;padding:1px 5px;background:var(--good-bg);color:var(--good)}
.row.bad .sec{background:var(--critical);color:#fff}
.row .sim{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--mut)}
.row .txt{margin-top:4px;color:var(--fg2);line-height:1.5}
.verdict{margin-top:11px;font-size:13.5px;padding:11px 13px;border-radius:8px}
.verdict.win{background:var(--good-bg);border-left:3px solid var(--good)}
.verdict.lose{background:var(--critical-bg);border-left:3px solid var(--critical)}

/* driver bar */
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);
 padding:9px 20px;display:flex;gap:14px;align-items:center;justify-content:center;font-size:12.5px;
 color:var(--mut)}
.bar kbd{font-family:var(--mono);font-size:11px;border:1px solid var(--line);border-bottom-width:2px;
 border-radius:4px;padding:1px 6px;background:var(--surface);color:var(--fg2)}
.bar .dots{display:flex;gap:5px}
.bar .dot{width:7px;height:7px;border-radius:50%;background:var(--line)}
.bar .dot.on{background:var(--struct)}
.err{background:var(--critical-bg);border-left:3px solid var(--critical);padding:11px 13px;
 border-radius:0 8px 8px 0;font-size:13px;margin-top:10px}
</style></head><body>
<div class="wrap">
<header>
  <div><h1>One question, two kinds of data</h1>
  <div class="sub">Clinical-trial eligibility on Exasol &mdash; the structured half and the text half, in one statement.</div></div>
  <a href="/">probe view &rarr;</a>
</header>

<div class="ask">
  <form id="f"><input id="q" autocomplete="off"
     value="Phase 3 NSCLC trials that exclude patients with prior anti-PD-1 therapy">
    <button id="go" type="submit">Run</button></form>
  <div class="presets" id="presets"></div>
</div>

<div id="err"></div>

<div class="stage" id="s1" hidden><h2><span class="num">1</span> The question</h2>
  <div class="q" id="q1"></div>
  <p class="lede">Two kinds of data in one sentence. <b class="hl-s">Blue</b> is coded in the
  registry and becomes a <b>WHERE</b> clause. <b class="hl-t">Purple</b> exists only as prose
  inside the eligibility text &mdash; no field holds it, so it has to be <b>retrieved</b>.</p>
</div>

<div class="stage" id="s2" hidden><h2><span class="num">2</span> The semantic layer splits it</h2>
  <p class="lede">Not a language model. Each word is looked up in the layer's <b>own vocabulary</b>,
  read live from <code>CT.V_LANDSCAPE</code>. Whatever the layer cannot name stays on the right &mdash;
  and that residue is exactly what retrieval is for.</p>
  <div class="halves">
    <div class="half s"><h3>Structured &rarr; a WHERE clause</h3>
      <p class="why">Matched against values that exist in the layer.</p>
      <div id="s2s"></div></div>
    <div class="half t"><h3>Text &rarr; retrieval</h3>
      <p class="why">No column holds this. It lives in the criteria prose.</p>
      <div id="s2t"></div></div>
  </div>
  <div id="s2u"></div>
</div>

<div class="stage" id="s3" hidden><h2><span class="num">3</span> Both halves become one statement</h2>
  <div class="key"><span><i class="s">structured</i> from the left half</span>
    <span><i class="t">text</i> from the right half</span>
    <span>everything else is the fixed template &mdash; <code>sql/05_hybrid_search.sql.tmpl</code></span></div>
  <pre class="sql" id="s3sql"></pre>
</div>

<div class="stage" id="s4" hidden><h2><span class="num">4</span> What the engine actually does</h2>
  <p class="lede">Exasol has <b>no vector type and no vector index</b>. A 96-dimension vector is
  stored as <b>96 rows</b>, normalised at build time &mdash; so cosine similarity is a join and a
  <b>GROUP BY</b>, and the database does what it was built to do: scan and aggregate.</p>
  <div class="tiles" id="s4t"></div>
  <div class="mech">SELECT v.NCT_ID, v.CHUNK_ID, <b>SUM(v.VAL * q.VAL)</b> AS SIM
FROM   CT.ELIG_VECTORS v JOIN QV q ON q.DIM = v.DIM
<b>GROUP  BY</b> v.NCT_ID, v.CHUNK_ID        &larr; that is the whole vector search</div>
</div>

<div class="stage" id="s5" hidden><h2><span class="num">5</span> The result, and what the column is worth</h2>
  <div class="cols">
    <div class="col"><h3>Text alone</h3>
      <p class="why">Vector + BM25 + fusion. No structured filter.</p><div id="s5a"></div></div>
    <div class="col"><h3>With the structured filter</h3>
      <p class="why">The same scoring, on candidates the layer restricted first.</p><div id="s5b"></div></div>
  </div>
  <div id="s5v"></div>
  <div id="s5blind"></div>
</div>

</div>
<div class="bar">
  <span><kbd>space</kbd> next</span><span><kbd>&larr;</kbd><kbd>&rarr;</kbd> step</span>
  <span><kbd>r</kbd> restart</span>
  <div class="dots" id="dots"></div>
  <span id="pos"></span>
</div>
<script>
const PRESETS = [
  ["The polarity failure", "Phase 3 NSCLC trials that exclude patients with prior anti-PD-1 therapy"],
  ["Where the column cannot help", "NSCLC trials including patients who are EGFR mutation positive"],
  ["All text, no WHERE clause", "trials with no prior systemic chemotherapy for metastatic disease"],
  ["Structured-heavy", "open industry-sponsored phase 2 breast trials excluding brain metastases"],
  ["A field the layer lacks", "phase 3 NSCLC trials whose primary endpoint is overall survival"],
];
let D = null, step = 0;
const N = 5;
const $ = s => document.querySelector(s);
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const num = n => Number(n).toLocaleString("en-US");

function paintPresets(){
  $("#presets").innerHTML = "";
  PRESETS.forEach(([label, q]) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.onclick = () => { $("#q").value = q; run(); };
    $("#presets").appendChild(b);
  });
}

function show(n){
  step = Math.max(0, Math.min(N, n));
  for (let i = 1; i <= N; i++){
    const el = $("#s" + i);
    el.hidden = i > step;
    if (i <= step) requestAnimationFrame(() => el.classList.add("on"));
    else el.classList.remove("on");
  }
  $("#dots").innerHTML = Array.from({length: N},
    (_, i) => '<span class="dot' + (i < step ? " on" : "") + '"></span>').join("");
  $("#pos").textContent = step ? step + " / " + N : "";
  if (step) $("#s" + step).scrollIntoView({behavior: "smooth", block: "center"});
}

// Stage 1 -- colour the question by which half each phrase went to.
function paintQuestion(){
  let html = esc(D.split.question);
  const marks = [];
  D.split.structured.forEach(s => marks.push([s.matched, "hl-s"]));
  if (D.split.section_cue) marks.push([D.split.section_cue, "hl-t"]);
  D.split.text.split(/\s+/).filter(w => w.length > 3).forEach(w => marks.push([w, "hl-t"]));
  marks.sort((a, b) => b[0].length - a[0].length).forEach(([phrase, cls]) => {
    const re = new RegExp("(?![^<]*>)\\b(" + phrase.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&") + ")\\b", "i");
    html = html.replace(re, '<span class="' + cls + '">$1</span>');
  });
  $("#q1").innerHTML = html;
}

function paintSplit(){
  const s = D.split;
  $("#s2s").innerHTML = s.structured.length
    ? s.structured.map(c => '<span class="chip">' + esc(c.clause) +
        '<span class="from">from &ldquo;' + esc(c.matched) + '&rdquo;</span></span>').join("")
    : '<span class="chip">(nothing coded &mdash; the whole question is text)</span>';
  let t = '<span class="chip">' + esc(s.text) +
          '<span class="from">&rarr; CT.EMBED_QUERY() and CT.QUERY_TERMS()</span></span>';
  if (s.section)
    t += '<span class="chip">AND c.CRITERION_SECTION = \'' + esc(s.section) + '\'' +
         '<span class="from">from &ldquo;' + esc(s.section_cue) +
         '&rdquo; &mdash; recovered from prose, the registry has no such field</span></span>';
  $("#s2t").innerHTML = t;
  $("#s2u").innerHTML = (s.unresolved || []).map(u =>
    '<div class="flag"><b>' + esc(u.column) + ' is not a filter here.</b> ' + esc(u.why) + '</div>').join("");
}

function paintSql(){
  let html = esc(D.sql);
  const put = (frag, cls) => {
    if (!frag) return;
    const e = esc(frag).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    html = html.replace(new RegExp(e, "g"), '<mark class="' + cls + '">' + esc(frag) + '</mark>');
  };
  (D.split.structured || []).forEach(c => put(c.clause, "s"));
  put(D.section_clause, "t");
  put(D.split.text, "t");
  $("#s3sql").innerHTML = html;
}

function paintScan(){
  const s = D.scan;
  $("#s4t").innerHTML = [
    [num(s.vector_rows), "vector rows scanned"],
    [num(s.criteria), "criteria embedded"],
    [s.dims, "dimensions each"],
    [s.elapsed_ms + " ms", "measured, just now"],
  ].map(([v, k]) => '<div class="tile"><div class="v">' + v + '</div><div class="k">' + k + '</div></div>').join("");
}

function rowHtml(r, want){
  const bad = want && r.CRITERION_SECTION !== want;
  return '<div class="row' + (bad ? " bad" : "") + '"><div class="top">' +
    '<span class="nct">' + esc(r.NCT_ID) + '</span>' +
    '<span class="sec">' + esc(r.CRITERION_SECTION) + (bad ? " &mdash; wrong half" : "") + '</span>' +
    '<span class="sim">cos ' + esc(r.VEC_SIM) + '</span></div>' +
    '<div class="txt">' + esc(r.CRITERION) + '</div></div>';
}

function paintResults(){
  const want = D.split.section;
  $("#s5a").innerHTML = D.results.text_only.map(r => rowHtml(r, want)).join("") || "<p class='why'>(no rows)</p>";
  $("#s5b").innerHTML = D.results.with_section.map(r => rowHtml(r, want)).join("") || "<p class='why'>(no rows)</p>";
  const v = $("#s5v");
  if (!want){ v.innerHTML = ""; return; }
  const wrongA = D.results.text_only.filter(r => r.CRITERION_SECTION !== want).length;
  const wrongB = D.results.with_section.filter(r => r.CRITERION_SECTION !== want).length;
  if (wrongA > 0 && wrongB === 0)
    v.innerHTML = '<div class="verdict win"><b>' + wrongA + ' of ' + D.results.text_only.length +
      '</b> top rows on the left come from the <b>wrong half of the criteria</b> &mdash; ' +
      'similarity cannot see the difference, because <code>no</code> and <code>not</code> are stopwords ' +
      'and are deleted before any scoring happens. On the right, none do. ' +
      'What fixed it was a <b>column</b>, not a bigger model.</div>';
  else if (wrongA > 0)
    v.innerHTML = '<div class="verdict lose">Still <b>' + wrongB + '</b> wrong-half rows on the right. ' +
      'The section filter cannot rescue this one &mdash; when both the right and the wrong criterion ' +
      'sit in the <b>same</b> section, there is nothing to filter on. Documented, not hidden.</div>';
  else
    v.innerHTML = '<div class="verdict win">Both sides land in the intended half: this question ' +
      'was never ambiguous about polarity. The column costs nothing when it is not needed.</div>';
  paintBlind();
}

// The second, harder failure: same half, opposite meaning. Shown only when it
// is actually present in the ranking, with its real rank.
function paintBlind(){
  const b = D.blind_spot, el = $("#s5blind");
  if (!b){ el.innerHTML = ""; return; }
  el.innerHTML = '<div class="verdict lose"><b>And here is what the column cannot fix.</b> ' +
    'At rank <b>' + b.rank + '</b> of the filtered list sits ' +
    '<span class="nct">' + esc(b.nct) + '</span> &mdash; &ldquo;' + esc(b.text) + '&rdquo; &mdash; ' +
    'cosine <b>' + esc(b.sim) + '</b>, and it is in <b>' + esc(b.section) + '</b>, the half we asked for. ' +
    '&ldquo;' + esc(b.term) + '&rdquo; is <b>not</b> a stopword: the token survives, the meaning does not. ' +
    'The section filter has nothing left to separate. Left unfixed, and documented.</div>';
}

async function run(){
  $("#go").disabled = true; $("#err").innerHTML = ""; show(0);
  try{
    const r = await fetch("/api/story?q=" + encodeURIComponent($("#q").value));
    D = await r.json();
    if (D.error) throw new Error(D.error);
    paintQuestion(); paintSplit(); paintSql(); paintScan(); paintResults();
    show(1);
  }catch(e){
    $("#err").innerHTML = '<div class="err">' + esc(e.message) + '</div>';
  }finally{ $("#go").disabled = false; }
}

$("#f").onsubmit = e => { e.preventDefault(); run(); };
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === " " || e.key === "ArrowRight"){ e.preventDefault(); if (D) show(step + 1); }
  else if (e.key === "ArrowLeft"){ e.preventDefault(); if (D) show(step - 1); }
  else if (e.key === "r" || e.key === "R"){ e.preventDefault(); run(); }
});
paintPresets(); run();
</script></body></html>
"""
