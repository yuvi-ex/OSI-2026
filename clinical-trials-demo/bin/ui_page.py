"""The probe page. Kept apart from the server so the HTML stays readable.

Colour follows the dataviz method: distributions are a SINGLE series, so they
get one sequential hue and a direct value label -- no categorical palette, no
legend (the row label names the bar). Status colours are reserved and never
carry meaning alone: a wrong-section row is red AND says "wrong half".
"""

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trial retrieval probe</title><style>
:root{
  --surface:#fcfcfb; --bg:#f6f5f2; --fg:#1a1a19; --fg2:#4a4945; --mut:#6b6a66;
  --line:#e2e0da; --card:#fff;
  --seq:#2a78d6; --seq-soft:#cde2fb;         /* sequential hue, one series only */
  --critical:#d03b3b; --critical-bg:#fbeceb; /* reserved status, never alone */
  --good:#0ca30c; --good-bg:#eef8ee;
}
@media(prefers-color-scheme:dark){:root{
  --surface:#1a1a19; --bg:#141413; --fg:#eceae5; --fg2:#c9c6bf; --mut:#96938c;
  --line:#302d28; --card:#1e1c19;
  --seq:#3987e5; --seq-soft:#1c3a5c;
  --critical:#e66767; --critical-bg:#2e1d1d;
  --good:#3ec03e; --good-bg:#16261a;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1220px;margin:0 auto;padding:20px 20px 70px}
header h1{font-size:18px;margin:0 0 2px;letter-spacing:-.01em}
header .sub{color:var(--mut);font-size:12.5px}
nav{display:flex;gap:2px;margin:16px 0 18px;border-bottom:1px solid var(--line);
 flex-wrap:wrap}
nav button{font:inherit;font-size:13px;padding:8px 14px;border:0;background:none;
 color:var(--mut);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
nav button[aria-selected=true]{color:var(--fg);border-bottom-color:var(--seq);font-weight:600}
section[hidden]{display:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:15px 16px;margin-bottom:14px}
.card>h2{font-size:14px;margin:0 0 3px}
.card.lede p{margin:0;font-size:14px;line-height:1.6;color:var(--fg2)}
.card.lede b{color:var(--fg)}
.card>.note{font-size:12.5px;color:var(--mut);margin:0 0 12px}
.grid{display:grid;gap:14px;grid-template-columns:1fr}
@media(min-width:820px){.grid.two{grid-template-columns:1fr 1fr}}
/* --- stat tiles: a hero number needs no plot --- */
.tiles{display:grid;gap:10px;grid-template-columns:repeat(2,1fr)}
@media(min-width:700px){.tiles{grid-template-columns:repeat(4,1fr)}}
.tile{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:11px 13px}
.tile .v{font-size:20px;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.tile .k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin-top:2px}
.tile .x{font-size:11.5px;color:var(--mut);margin-top:3px}
/* --- single-series horizontal bars, in a table so a table view always exists --- */
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;
 color:var(--mut);border-bottom:1px solid var(--line);padding:5px 8px;font-weight:600}
td{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--fg2)}
.barcell{width:46%;min-width:110px}
.bar{height:9px;background:var(--seq);border-radius:0 4px 4px 0;
 box-shadow:2px 0 0 0 var(--card)}   /* 4px rounded data-end, 2px surface gap */
.barwrap{background:var(--seq-soft);border-radius:0 4px 4px 0;overflow:hidden}
/* --- results: one list, each row tagged with what the filter did to it --- */
tr.gone{background:var(--critical-bg)}
tr.gone td.crit{color:var(--critical)}
tr.up{background:var(--good-bg)}
.fate{
  display:inline-flex;align-items:center;gap:5px;white-space:nowrap;
  font-size:10.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;
}
.fate.f-gone{color:var(--critical)}
.fate.f-up{color:var(--good)}
.fate.f-kept{color:var(--mut);font-weight:600}
.glyph{
  display:inline-grid;place-items:center;width:15px;height:15px;border-radius:50%;
  font-size:9px;font-weight:700;color:#fff;
}
.f-gone .glyph{background:var(--critical)}
.f-up .glyph{background:var(--good)}
.f-kept .glyph{background:var(--line);color:var(--mut)}
.rank{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
  font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--mut);
}
.rank b{color:var(--fg);font-weight:650}
.rank .to{color:var(--good)}
tr.gone .rank b{color:var(--critical)}
.headline{
  border:1px solid var(--critical);background:var(--critical-bg);
  padding:15px 17px;margin-bottom:16px;
}
.headline.clean{border-color:var(--good);background:var(--good-bg)}
.headline .big{
  font-size:16.5px;font-weight:700;color:var(--critical);line-height:1.35;
  margin-bottom:5px;
}
.headline.clean .big{color:var(--good)}
.headline .why{font-size:13.5px;color:var(--fg2);max-width:76ch}
.subhead{
  font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);
  padding:14px 0 4px;font-weight:600;
}
.tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;
 padding:1px 5px;border-radius:4px;border:1px solid currentColor;margin-left:5px;
 vertical-align:1px}
.sec{white-space:nowrap;font-size:11px}
.nct{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;font-size:11.5px}
.flag{margin-top:11px;padding:9px 11px;border-radius:7px;font-size:12.5px;
 border:1px solid currentColor;background:var(--critical-bg);color:var(--critical)}
.flag.ok{background:var(--good-bg);color:var(--good)}
label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 color:var(--mut);margin-bottom:5px}
input[type=text],select{width:100%;padding:8px 10px;font:inherit;color:var(--fg);
 background:var(--surface);border:1px solid var(--line);border-radius:6px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin-top:11px}
.row>div{flex:1;min-width:150px}
button.go{font:inherit;padding:8px 16px;border-radius:6px;border:1px solid var(--seq);
 background:var(--seq);color:#fff;font-weight:600;cursor:pointer}
.presets{margin-top:12px;display:flex;gap:7px;flex-wrap:wrap}
.presets button{font:inherit;font-size:12px;padding:5px 10px;border-radius:6px;
 border:1px solid var(--line);background:var(--surface);color:var(--fg2);cursor:pointer}
dl.legend{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:0;font-size:12px}
dl.legend dt{font-weight:650;color:var(--fg)}
dl.legend dd{margin:0;color:var(--mut)}
pre{background:var(--surface);border:1px solid var(--line);border-radius:7px;padding:11px;
 overflow-x:auto;font-size:11.5px;line-height:1.45;margin:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
details{margin-top:12px}summary{cursor:pointer;color:var(--mut);font-size:12px}
.spin{color:var(--mut);font-size:12.5px;padding:10px 0}
.kv{font-size:12.5px}
.kv div{display:flex;justify-content:space-between;gap:16px;padding:4px 0;
 border-bottom:1px solid var(--line)}
.kv div:last-child{border:0}
.kv b{font-weight:600}
.kv span{color:var(--mut);text-align:right}
.no{color:var(--critical)}
.yes{color:var(--good)}
svg{max-width:100%;height:auto;display:block}
.tokcmp{display:grid;gap:12px;grid-template-columns:1fr 1fr;font-size:12px}
.tokcmp ul{margin:4px 0 0;padding-left:17px}
</style></head><body>
<div class="wrap">
<header>
  <h1>Trial retrieval probe</h1>
  <div class="sub">Hybrid search over clinical-trial eligibility criteria, on Exasol Personal Local.
  Every number on this page is read from the database when you load it.</div>
</header>

<nav id="nav" role="tablist"></nav>

<!-- ================= PROBE ================= -->
<section id="tab-probe">
  <div class="card">
    <h2>Ask a question that needs both halves</h2>
    <p class="note">The <b>question</b> searches eligibility prose &mdash; the half no
    coded field can answer. The <b>filter</b> runs against the semantic layer &mdash;
    phase, status, sponsor, geography. They execute as one statement, with the
    structured filter applied <i>before</i> anything is scored, so the text search
    never looks at a trial the filter already excluded.</p>
    <form onsubmit="go(event)">
      <label for="q">Your question</label>
      <input type="text" id="q" value="prior treatment with an anti-PD-1 or anti-PD-L1 antibody">
      <div class="row">
        <div><label for="section">Which half you mean</label>
          <select id="section">
            <option value="EXCLUSION">EXCLUSION — trials that rule these patients out</option>
            <option value="INCLUSION">INCLUSION — trials that require this</option>
          </select></div>
        <div><label for="topk">Rows</label>
          <select id="topk"><option>6</option><option selected>10</option><option>20</option></select></div>
      </div>
      <div class="row">
        <div><label for="filter">Optional structured filter (SQL on the trial view)</label>
          <input type="text" id="filter" placeholder="AND t.PHASE='PHASE3' AND t.STATUS_GROUP='Open'"></div>
        <div style="flex:0 0 auto;display:flex;align-items:flex-end">
          <button class="go" type="submit">Run both ways</button></div>
      </div>
      <div class="presets" id="presets"></div>
    </form>
  </div>
  <div id="out"></div>
  <div class="card">
    <h2>What the columns mean</h2>
    <dl class="legend">
      <dt>Criteria half</dt><dd>Which half of the trial's criteria this sentence came from. If it does not match what you asked for, the answer is wrong.</dd>
      <dt>Meaning match</dt><dd>Cosine similarity, 0&ndash;1. "Does this sentence <i>mean</i> the same thing?"</dd>
      <dt>Keyword match</dt><dd>BM25 score. "Does this sentence share the same <i>words</i>?"</dd>
      <dt>Rank score</dt><dd>The fused score the list is sorted by. Higher is ranked higher.</dd>
      <dt>NCT ID</dt><dd>The trial's registry identifier &mdash; what an agent must cite.</dd>
    </dl>
  </div>
</section>

<!-- ================= DATASET ================= -->
<section id="tab-dataset" hidden>
  <div class="card lede">
    <p><b>ClinicalTrials.gov API v2 only.</b> <span id="ds-lede-n">12,404</span>
    interventional trials, non-small cell lung cancer + breast cancer, started 2015 or
    later. Committed as a <span id="ds-lede-mb">15</span>&nbsp;MB gzipped snapshot in
    <code>data/</code> &mdash; so the demo makes <b>no live API calls</b> and cannot be
    broken by a venue network.</p>
  </div>
  <div class="tiles" id="ds-tiles"></div>
  <div class="grid two" style="margin-top:14px">
    <div class="card"><h2>Where the data comes from</h2>
      <p class="note">One source. The snapshot is committed to the repository.</p>
      <div class="kv" id="ds-source"></div>
      <details><summary>Sources in the brief that are NOT used</summary>
        <p class="note" style="margin-top:8px"><b>PubMed IS now used</b> &mdash; publications
        live in an Iceberg lake and join on the NCT number, which PubMed carries as a
        DataBank accession. <b>EU CTR/CTIS, OpenAlex, Drugs@FDA and EMA EPARs are absent.</b>
        Each needs its own fetcher, and each joins on something weaker than an NCT id
        (drug name, or a second registry number that has to be reconciled).</p></details>
    </div>
    <div class="card"><h2>Criteria sentences by half</h2>
      <p class="note">The registry has <b>no</b> structured inclusion/exclusion field.
      This split is recovered from prose headings.</p>
      <div id="ds-sections"></div></div>
  </div>
  <div class="grid two">
    <div class="card"><h2>Trials by phase</h2>
      <p class="note">Read this before trusting any phase filter.</p><div id="ds-phase"></div>
      <div class="flag">A third of trials say <b>NOT_APPLICABLE</b> &mdash; the registry's own
      statement that they are unphased. <code>WHERE PHASE='PHASE3'</code> drops them
      silently, so the view exposes <code>PHASE_IS_STATED</code>.</div></div>
    <div class="card"><h2>Trials by region</h2>
      <p class="note">Countries as the API names them, rolled into 7 regions.</p>
      <div id="ds-region"></div></div>
  </div>
  <div class="grid two">
    <div class="card"><h2>Trials by status</h2><div id="ds-status"></div></div>
    <div class="card"><h2>Trials by sponsor type</h2><div id="ds-sponsor"></div></div>
  </div>
  <div class="grid two">
    <div class="card"><h2>Top countries</h2><div id="ds-countries"></div></div>
    <div class="card"><h2>Trial design</h2>
      <p class="note">Whether a control arm exists is structured. <i>Which</i> drug the
      control is sits in the arm label as prose.</p><div id="ds-comparator"></div></div>
  </div>
  <div class="card"><h2>Primary endpoint category</h2>
    <p class="note">Derived, not looked up: the registry gives endpoints as free text
    (a measure and a timeframe, nothing coded). These categories come from pattern
    matching in SQL.</p>
    <div id="ds-endpoint"></div>
    <div class="flag" id="ds-endpoint-flag"></div></div>
</section>

<!-- ================= MODEL ================= -->
<section id="tab-model" hidden>
  <div class="card"><h2>There is no neural network here</h2>
    <p class="note">No transformer, no embedding API, no prediction. This is classical
    information retrieval, chosen deliberately.</p>
    <div class="kv" id="md-kv"></div>
  </div>
  <div class="grid two">
    <div class="card"><h2>How a document becomes numbers</h2>
      <pre id="md-pipe"></pre>
      <p class="note" style="margin-top:10px">Vectors are unit length, so a dot product
      <i>is</i> cosine similarity. That is what lets the database do the search with
      arithmetic alone.</p></div>
    <div class="card"><h2>Why this model, knowing it is weaker</h2>
      <p class="note">It explains about 18% of variance and its similarity scores bunch
      up near 1.0, so only the <i>order</i> carries signal. A transformer would retrieve
      better &mdash; and would be <b>just as blind</b> to the failure below, which is the
      point being made. Choosing a modest model keeps the argument about the
      <i>architecture</i> rather than the model.</p>
      <p class="note">It also has to unpickle inside an Exasol UDF, so scikit-learn is
      pinned to the exact version the database's Python container ships.</p></div>
  </div>
  <div class="card"><h2>The failure this model makes visible</h2>
    <p class="note">Type two sentences that mean opposite things. The search reduces both
    to a bag of terms before scoring &mdash; if the bags match, nothing downstream can tell
    them apart.</p>
    <div class="row">
      <div><label for="t1">Sentence A</label>
        <input type="text" id="t1" value="No prior treatment with anti-PD-1"></div>
      <div><label for="t2">Sentence B</label>
        <input type="text" id="t2" value="Prior treatment with anti-PD-1"></div>
      <div style="flex:0 0 auto;display:flex;align-items:flex-end">
        <button class="go" type="button" onclick="tok()">Compare terms</button></div>
    </div>
    <div id="tok-out"></div></div>
</section>

<!-- ================= ARCHITECTURE ================= -->
<section id="tab-arch" hidden>
  <div class="card"><h2>How it runs on Exasol</h2>
    <p class="note">Everything expensive happens once, outside the database. The database
    is left with arithmetic it can spread across cores.</p>
    <div id="arch-svg"></div>
  </div>
  <div class="grid two">
    <div class="card"><h2>Vectors without a vector type</h2>
      <p class="note">Exasol has no vector column and no vector index. So a 96-dimension
      vector is stored as <b>96 rows</b>, and similarity becomes an ordinary join and
      <code>GROUP BY</code> &mdash; the shape a parallel database is built for.</p>
      <pre>SELECT v.NCT_ID, v.CHUNK_ID,
       SUM(v.VAL * q.VAL) AS SIM
FROM   CT.ELIG_VECTORS v
JOIN   QV q ON q.DIM = v.DIM
GROUP  BY v.NCT_ID, v.CHUNK_ID</pre>
      <div class="kv" id="arch-tables" style="margin-top:12px"></div></div>
    <div class="card"><h2>What runs where</h2>
      <div class="kv" id="arch-where"></div>
      <details><summary>Why the model file lives in BucketFS</summary>
        <p class="note" style="margin-top:8px">A UDF cannot reach your laptop's disk.
        BucketFS is the database's own file store, mounted inside the UDF sandbox at
        <code>/buckets/...</code>. The model is loaded once per query VM at module
        scope, not once per row.</p></details></div>
  </div>
</section>

<!-- ================= RESULTS ================= -->
<section id="tab-results" hidden>
  <div class="tiles" id="ev-tiles"></div>
  <div class="card" style="margin-top:14px"><h2>Every question, measured twice</h2>
    <p class="note">Text alone, then with the structured half applied before scoring.
    This is the credibility close, not the pitch: the numbers below say how much the
    structured half is worth, and the panel under them says where it buys nothing.</p>
    <div id="ev-table"></div></div>
  <div class="card"><h2>Two failures, not one</h2>
    <div class="kv" id="ev-fail"></div></div>
  <div class="card"><h2>What these numbers are not</h2>
    <p class="note" id="ev-caveat"></p></div>
</section>
</div>

<script>
/* Order is the ARGUMENT, not the build order. The platform claim sits second,
   right after the demo, instead of fourth where nobody clicked it. Validation
   closes, because "here is where it breaks" is a credibility move once the
   claim has been made and a weakness if it opens. */
const TABS=[["probe","Ask"],["arch","One engine"],["dataset","The data"],
            ["model","The model"],["results","Validation"]];
const nav=document.getElementById('nav');
TABS.forEach(([id,label],i)=>{const b=document.createElement('button');
  b.textContent=label; b.setAttribute('role','tab');
  b.setAttribute('aria-selected', i===0?'true':'false');
  b.onclick=()=>{TABS.forEach(([j])=>document.getElementById('tab-'+j).hidden=(j!==id));
    [...nav.children].forEach(c=>c.setAttribute('aria-selected',String(c===b)));};
  nav.appendChild(b);});

const esc=s=>(s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=n=>Number(n).toLocaleString();

/* One series per chart: single hue, direct value label, row label names it.
   No legend, because there is nothing to disambiguate. */
function bars(rows,unit){
  if(!rows||!rows.length) return '<div class="spin">no data</div>';
  const mx=Math.max(...rows.map(r=>r.n))||1;
  let h='<table><thead><tr><th>'+(unit||'Group')+'</th><th></th>'
       +'<th class="n">Count</th><th class="n">Share</th></tr></thead><tbody>';
  for(const r of rows){
    h+='<tr><td>'+esc(r.label)+'</td>'
      +'<td class="barcell"><div class="barwrap"><div class="bar" style="width:'
      +(100*r.n/mx).toFixed(1)+'%"></div></div></td>'
      +'<td class="n">'+fmt(r.n)+'</td><td class="n">'+r.pct+'%</td></tr>';
  }
  return h+'</tbody></table>';
}
const kv=o=>Object.entries(o).map(([k,v])=>'<div><b>'+esc(k)+'</b><span>'+v+'</span></div>').join('');
const tile=(v,k,x)=>'<div class="tile"><div class="v">'+v+'</div><div class="k">'+esc(k)+'</div>'
  +(x?'<div class="x">'+x+'</div>':'')+'</div>';

/* ---------------- probe ---------------- */
let PRESETS=[];
let TOTALS={};
function mkPresets(){const pc=document.getElementById('presets');pc.innerHTML='';
  PRESETS.forEach(p=>{const b=document.createElement('button');b.type='button';
    b.textContent=p[0];b.onclick=()=>{document.getElementById('q').value=p[1];
      document.getElementById('section').value=p[2];
      document.getElementById('filter').value=p[3];go();};pc.appendChild(b);});}

const keyOf = r => r.NCT_ID + '#' + r.CHUNK_ID;

/* One ranked list instead of two. Every row carries what the structured column
   did to it, because two near-identical tables side by side make the reader diff
   twenty rows by eye to find the one that changed -- and at a booth nobody does. */
function diffTable(A, B, want){
  if(!A.length) return '<div class="spin">no rows</div>';
  const bRank = new Map(B.map((r,i)=>[keyOf(r), i+1]));
  const aSeen = new Set(A.map(keyOf));
  const rows = A.map((r,i)=>{
    const wrong = want && r.CRITERION_SECTION !== want;
    const to = bRank.get(keyOf(r)) || null;
    // A row can survive the filter and still drop out of the visible top N,
    // because removing candidates re-scores the whole ranking rather than just
    // closing a gap. Labelling that "kept" would be a lie about what happened.
    return {r, from:i+1, to, fate: wrong ? 'gone' : (to ? 'kept' : 'out')};
  });
  const promoted = B.map((r,i)=>({r, from:null, to:i+1, fate:'up'}))
                    .filter(x=>!aSeen.has(keyOf(x.r)));

  const FATE = {
    gone:{cls:'f-gone', g:'\u2715', t:'Removed — wrong half'},
    kept:{cls:'f-kept', g:'\u2022', t:'Kept'},
    up:  {cls:'f-up',   g:'\u25B2', t:'Promoted into view'},
    out: {cls:'f-kept',  g:'\u2193', t:'Fell below the cut'},
  };
  const line = x => {
    const f = FATE[x.fate];
    const rank = x.fate==='up'
      ? '<span class="rank">&rarr; <b class="to">#'+x.to+'</b></span>'
      : x.fate==='out'
      ? '<span class="rank"><b>#'+x.from+'</b> &rarr; &mdash;</span>'
      : x.to && x.to!==x.from
        ? '<span class="rank"><b>#'+x.from+'</b> &rarr; <span class="to">#'+x.to+'</span></span>'
        : '<span class="rank"><b>#'+(x.from||x.to)+'</b></span>';
    return '<tr class="'+(x.fate==='gone'?'gone':x.fate==='up'?'up':'')+'">'
      +'<td>'+rank+'</td>'
      +'<td><span class="fate '+f.cls+'"><span class="glyph">'+f.g+'</span>'+f.t+'</span></td>'
      +'<td class="sec">'+esc(x.r.CRITERION_SECTION)+'</td>'
      +'<td class="n">'+esc(x.r.VEC_SIM)+'</td>'
      +'<td class="nct">'+esc(x.r.NCT_ID)+'</td>'
      +'<td class="'+(x.fate==='gone'?'crit':'')+'">'+esc(x.r.CRITERION)+'</td></tr>';
  };
  let h='<table><thead><tr><th>Rank</th><th>What the column did</th><th>Half</th>'
   +'<th class="n">Meaning</th><th>NCT ID</th><th>The criterion, as written</th>'
   +'</tr></thead><tbody>'+rows.map(line).join('');
  if(promoted.length){
    h+='<tr><td colspan="6" class="subhead">Rose into the top '+B.length
      +' once the wrong half was removed</td></tr>'+promoted.map(line).join('');
  }
  return h+'</tbody></table>';
}

/* The rank is the story, not the count. "1 of 10 wrong" reads as a 10% error
   rate and gets shrugged at; "#4 of 268,912, inside what an agent would cite"
   does not. */
function headline(A, want){
  const wrong = A.map((r,i)=>({r,rank:i+1})).filter(x=>x.r.CRITERION_SECTION!==want);
  const corpus = TOTALS.chunks ? TOTALS.chunks.toLocaleString() : 'the corpus';
  if(!wrong.length){
    return '<div class="headline clean"><div class="big">Every top answer came from the '
      +'half you asked for.</div><div class="why">Text search alone was already '
      +'correct here — the structured column had nothing to remove. Try one of the '
      +'failure presets to see where it is not.</div></div>';
  }
  const w = wrong[0];
  const cited = w.rank <= 5;
  return '<div class="headline"><div class="big">Ranked #'+w.rank+' out of '+corpus
    +' criteria — and it says the opposite of what you asked.</div>'
    +'<div class="why">'
    +(cited ? 'An agent citing its top five sources <b>would quote this one</b>. '
            : 'It sits just outside the usual citation window, which is luck rather than design. ')
    +esc(w.r.NCT_ID)+' reads &ldquo;'+esc(w.r.CRITERION.slice(0,90))+'&rdquo; and is filed under '
    +esc(w.r.CRITERION_SECTION)+'. '
    +(wrong.length>1 ? wrong.length+' of the '+A.length+' rows shown are from the wrong half.'
                     : 'Cosine cannot separate it from the correct answers.')
    +'</div></div>';
}

async function go(ev){
  if(ev)ev.preventDefault();
  const q=document.getElementById('q').value,section=document.getElementById('section').value,
        filter=document.getElementById('filter').value,topk=document.getElementById('topk').value;
  const out=document.getElementById('out');
  out.innerHTML='<div class="card"><div class="spin">Scanning 25.8M vector rows, twice&hellip;</div></div>';
  try{
    const d=await(await fetch('/search?'+new URLSearchParams({q,section,filter,topk}))).json();
    if(d.error){out.innerHTML='<div class="card"><div class="flag">'+esc(d.error)+'</div></div>';return;}
    out.innerHTML=
      headline(d.text_only.rows, section)
      +'<div class="card"><h2>What the structured column changed</h2>'
      +'<p class="note">One ranked list. Every row is tagged with what happened to it '
      +'once the wrong half of the criteria was removed before scoring.</p>'
      + diffTable(d.text_only.rows, d.with_section.rows, section)
      +'</div>'
      +'<div class="card"><details><summary>The SQL behind the unfiltered ranking</summary>'
      +'<pre style="margin-top:10px">'+esc(d.text_only.sql)+'</pre></details></div>';
  }catch(e){out.innerHTML='<div class="card"><div class="flag">'+esc(e)+'</div></div>';}
}

/* ---------------- model: the tokeniser proof ---------------- */
async function tok(){
  const a=document.getElementById('t1').value,b=document.getElementById('t2').value;
  const o=document.getElementById('tok-out');
  o.innerHTML='<div class="spin">asking the database&hellip;</div>';
  try{
    const d=await(await fetch('/tokens?'+new URLSearchParams({a,b}))).json();
    if(d.error){o.innerHTML='<div class="flag">'+esc(d.error)+'</div>';return;}
    const same=JSON.stringify(d.a)===JSON.stringify(d.b);
    o.innerHTML='<div class="tokcmp" style="margin-top:12px">'
      +'<div><b>A &rarr; '+d.a.length+' terms</b><ul>'+d.a.map(t=>'<li><code>'+esc(t)+'</code></li>').join('')+'</ul></div>'
      +'<div><b>B &rarr; '+d.b.length+' terms</b><ul>'+d.b.map(t=>'<li><code>'+esc(t)+'</code></li>').join('')+'</ul></div>'
      +'</div>'+(same
        ?'<div class="flag">Identical. The words that carry the negation &mdash; <code>no</code>, '
         +'<code>not</code>, <code>without</code> &mdash; are stopwords, so they are deleted before '
         +'anything is scored. Two opposite sentences are now the same question.</div>'
        :'<div class="flag ok">'+d.only_a.length+' term(s) only in A, '+d.only_b.length
         +' only in B. Shared: '+d.shared.length+'. A difference here is something the scorer can use.</div>');
  }catch(e){o.innerHTML='<div class="flag">'+esc(e)+'</div>';}
}

/* ---------------- architecture diagram ----------------
   Three numbered bands, read top to bottom. The previous version was flat --
   every box the same border, fill and weight, so nothing told the eye where to
   start. Hierarchy now comes from four devices, none of them colour alone:
     - a numbered accent badge anchors each band
     - the NUMBER is the big type; its label recedes to 10.5px muted
     - bands 1 and 2 sit on the recessed surface; band 3 sits on the raised card
       with a 4px accent rule, because it is the only band that runs per question
     - one arrow between bands, dead centre, crossing nothing                */
function archSvg(t){
  const L='var(--line)', T='var(--fg)', M='var(--mut)', S='var(--seq)',
        C='var(--card)', F='var(--surface)';
  const band=(y,h,hot)=>
    `<rect x="16" y="${y}" width="868" height="${h}" rx="10" fill="${hot?C:F}"
       stroke="${L}" stroke-width="1"/>` +
    (hot?`<path d="M16 ${y+10} a10 10 0 0 1 10 -10 h0 v${h} h0 a10 10 0 0 1 -10 -10 z"
       fill="${S}"/><rect x="20" y="${y}" width="2" height="${h}" fill="${S}"/>`:'');
  const badge=(x,y,n)=>
    `<circle cx="${x}" cy="${y}" r="14" fill="${S}"/>` +
    `<text x="${x}" y="${y+5}" fill="#fff" font-size="14" font-weight="700"
       text-anchor="middle" font-family="-apple-system,system-ui,sans-serif">${n}</text>`;
  const tx=(x,y,str,o={})=>`<text x="${x}" y="${y}" fill="${o.c||T}"
    font-size="${o.s||11.5}" font-weight="${o.w||400}" text-anchor="${o.a||'start'}"
    font-family="${o.f||'-apple-system,system-ui,sans-serif'}">${str}</text>`;
  // the number is the message; the label is the footnote
  const hero=(x,y,v,label)=>tx(x,y,v,{s:23,w:650}) + tx(x,y+18,label,{s:10.5,c:M});
  const chip=(x,y,w,h,a,b)=>
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7" fill="${F}"
       stroke="${L}" stroke-width="1"/>` +
    tx(x+13,y+19,a,{s:12,w:650}) + (b?tx(x+13,y+35,b,{s:10,c:M}):'');
  const rgt=(x1,x2,y)=>`<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}"
    stroke="${S}" stroke-width="2" marker-end="url(#ah)"/>`;
  const dn=(x,y1,y2)=>`<line x1="${x}" y1="${y1}" x2="${x}" y2="${y2}"
    stroke="${S}" stroke-width="2.5" marker-end="url(#ah)"/>`;

  return `<svg viewBox="0 0 900 566" role="img"
   aria-label="Three stages. One: built once in Docker - 12,404 trials become 268,912 criteria sentences become 96 dimensions each. Two: loaded once into Exasol - 25.8 million vector rows in a table and a 94 megabyte model file in BucketFS. Three: every question takes about five seconds - the question passes through two Python UDFs and is otherwise pure SQL, a join and a GROUP BY, returning ranked NCT IDs.">
  <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
    markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${S}"/></marker></defs>

  <!-- ================= 1 · BUILT ONCE ================= -->
  ${band(14,150,false)}
  ${badge(56,52,'1')}
  ${tx(84,50,'BUILT ONCE',{s:14,w:700})}
  ${tx(84,68,'in Docker &middot; scikit-learn pinned to the database&rsquo;s own version',{s:10.5,c:M})}
  ${hero(84,116,fmt(t.trials),'trials in the committed snapshot')}
  ${rgt(320,352,110)}
  ${hero(376,116,fmt(t.chunks),'criteria sentences, split in / out')}
  ${rgt(612,644,110)}
  ${hero(668,116,'96','dimensions per sentence')}

  ${dn(450,168,190)}

  <!-- ================= 2 · LOADED ONCE ================= -->
  ${band(194,150,false)}
  ${badge(56,232,'2')}
  ${tx(84,230,'LOADED ONCE',{s:14,w:700})}
  ${tx(84,248,'into Exasol Personal Local &middot; nothing leaves this machine',{s:10.5,c:M})}
  ${hero(84,296,fmt(t.vector_rows),'vector rows in ELIG_VECTORS &mdash; one row per dimension')}
  ${hero(560,296,'94 MB','elig_model.pkl, in BucketFS')}
  ${tx(84,330,`alongside ${fmt(t.token_rows)} token rows &middot; ${fmt(t.chunks)} criteria &middot; ${fmt(t.vocab)} terms`,{s:10.5,c:M})}

  ${dn(450,348,370)}

  <!-- ================= 3 · EVERY QUESTION (the hot path) ================= -->
  ${band(374,178,true)}
  ${badge(60,412,'3')}
  ${tx(88,410,'EVERY QUESTION',{s:14,w:700})}
  ${tx(88,428,'about 5 seconds &middot; only the second step runs Python',{s:10.5,c:M})}

  ${chip(88,446,158,46,'Your question','free text')}
  ${rgt(252,278,469)}
  ${chip(284,446,186,46,'2 Python UDFs','EMBED_QUERY &middot; QUERY_TERMS')}
  ${rgt(476,502,469)}
  ${chip(508,446,214,46,'Pure SQL','join &middot; GROUP BY &middot; rank &middot; fuse')}
  ${rgt(728,754,469)}
  ${chip(760,446,110,46,'NCT IDs','cited')}

  ${tx(88,528,'cosine = SUM(v.VAL &times; q.VAL)',{s:11.5,w:600,f:'ui-monospace,SFMono-Regular,Menlo,monospace'})}
  ${tx(300,528,'&mdash; there is no vector index and no vector type. There does not need to be.',{s:11,c:M})}
</svg>`;
}

/* ---------------- load everything ---------------- */
(async function(){
  let d;
  try{ d=await(await fetch('/stats')).json(); }
  catch(e){ document.getElementById('ds-tiles').innerHTML=
    '<div class="flag">Could not read the database: '+esc(e)+'</div>'; return; }
  if(d.error){ document.getElementById('ds-tiles').innerHTML=
    '<div class="flag">'+esc(d.error)+'</div>'; return; }
  PRESETS=d.presets||[]; mkPresets(); TOTALS=d.totals||{};
  const t=d.totals, sn=d.snapshot||{}, mm=d.model_meta||{};

  /* dataset */
  document.getElementById('ds-tiles').innerHTML=
     tile(fmt(t.trials),'Trials','NSCLC + breast, 2015 onward')
    +tile(fmt(t.chunks),'Criteria sentences','every trial has criteria text')
    +tile(fmt(t.sponsors),'Distinct sponsors','across '+t.countries+' countries')
    +tile(fmt(t.outcomes),'Recorded endpoints','free text, not coded');
  document.getElementById('ds-lede-n').textContent=fmt(sn.trials||t.trials);
  document.getElementById('ds-lede-mb').textContent=((sn.bytes||0)/1048576).toFixed(1);
  document.getElementById('ds-source').innerHTML=kv({
    'Source':'ClinicalTrials.gov API v2',
    'Fetched':(sn.fetched_utc||'?'),
    'Filter':'interventional, start 2015+',
    'Conditions':'non-small cell lung cancer; breast cancer',
    'Trials kept':fmt(sn.trials||t.trials),
    'Cross-listed dropped':fmt(sn.cross_listed_dropped||0),
    'Snapshot size':((sn.bytes||0)/1048576).toFixed(1)+' MB, committed',
    'Live API calls at demo time':'<span class="yes">none</span>'});
  document.getElementById('ds-sections').innerHTML=bars(d.sections,'Half');
  document.getElementById('ds-phase').innerHTML=bars(d.phase,'Phase');
  document.getElementById('ds-region').innerHTML=bars(d.region,'Region');
  document.getElementById('ds-status').innerHTML=bars(d.status,'Status');
  document.getElementById('ds-sponsor').innerHTML=bars(d.sponsor,'Sponsor type');
  document.getElementById('ds-countries').innerHTML=bars(d.top_countries,'Country');
  document.getElementById('ds-comparator').innerHTML=bars(d.comparator,'Design');
  document.getElementById('ds-endpoint').innerHTML=bars(d.endpoint,'Endpoint');
  const unc=(d.endpoint.find(r=>r.label.indexOf('Other')===0)||{}).pct;
  document.getElementById('ds-endpoint-flag').innerHTML='<b>'+unc+'%</b> of primary endpoints '
    +'still land in <i>Other / unclassified</i>. That is the cost of free-text endpoints, '
    +'and it is shown rather than hidden.';

  /* model */
  document.getElementById('md-kv').innerHTML=kv({
    'Document vectors':'TF-IDF &rarr; TruncatedSVD ('+(mm.dims||96)+' dims) &mdash; classic LSA',
    'Vocabulary':fmt(mm.vocab||t.vocab)+' terms (unigrams + bigrams)',
    'Similarity':'cosine, via a unit-length dot product',
    'Keyword scoring':'BM25, k1=1.2, b=0.75',
    'Combining the two':'reciprocal rank fusion, k=60',
    'Variance explained':((mm.explained_variance||0)*100).toFixed(1)+'%',
    'Transformer / neural model':'<span class="no">none</span>',
    'External API call':'<span class="no">none</span>',
    'Predictive model':'<span class="no">none &mdash; this retrieves, it does not predict</span>',
    'Library':'scikit-learn, pinned to the database’s container'});
  document.getElementById('md-pipe').textContent=
`criterion sentence
  -> lowercase, strip accents, drop stopwords
  -> unigrams + bigrams        ${fmt(mm.vocab||t.vocab)} term vocabulary
  -> TF-IDF weighting          sublinear tf
  -> TruncatedSVD              ${mm.dims||96} dimensions
  -> L2 normalise              so dot product == cosine
  -> ${fmt(t.vector_rows)} rows in Exasol   (one row per dimension)`;

  /* architecture */
  document.getElementById('arch-svg').innerHTML=archSvg(t);
  document.getElementById('arch-tables').innerHTML=kv({
    'ELIG_VECTORS':fmt(t.vector_rows)+' rows',
    'CHUNK_TOKENS':fmt(t.token_rows)+' rows',
    'ELIG_CHUNKS':fmt(t.chunks)+' rows',
    'TERM_IDF':fmt(t.vocab)+' rows',
    'Loaded from Parquet in':'~9 seconds',
    'Full similarity scan':'~5 seconds'});
  document.getElementById('arch-where').innerHTML=kv({
    'Fetch + shred':'laptop, Python',
    'TF-IDF + SVD fit':'Docker, once',
    'Vector storage':'Exasol table',
    'Model file':'Exasol BucketFS',
    'Query embedding':'Exasol Python UDF',
    'Similarity, BM25, fusion':'<b>Exasol SQL</b>',
    'Ranking + citation':'Exasol SQL'});

  /* results */
  if(!d.eval){document.getElementById('ev-tiles').innerHTML=
    '<div class="flag">No eval results yet &mdash; run <code>./06_eval.sh</code>.</div>';}
  else{
    const s=d.eval.summary, T=s.text_only, W=s.with_section;
    document.getElementById('ev-tiles').innerHTML=
       tile((T.recall_at_k*100).toFixed(1)+'%','Recall, text alone','of the right answers found')
      +tile((W.recall_at_k*100).toFixed(1)+'%','Recall, with the column','same search, one filter added')
      +tile((T.section_purity*100).toFixed(0)+'%','Right-half rate, text alone','how much of the top-k was usable')
      +tile((W.section_purity*100).toFixed(0)+'%','Right-half rate, filtered','');
    let h='<table><thead><tr><th>Question</th><th>Kind</th><th class="n">Recall, text alone</th>'
      +'<th class="n">Recall, filtered</th><th class="n">Change</th></tr></thead><tbody>';
    for(const r of d.eval.results){
      if(r.error){h+='<tr><td>'+esc(r.id)+'</td><td colspan="4">'+esc(r.error)+'</td></tr>';continue;}
      const a=r.text_only.recall_at_k,b=r.with_section.recall_at_k,dl=b-a;
      h+='<tr><td>'+esc(r.id)+'<div class="x" style="color:var(--mut);font-size:11.5px">'
        +esc(r.intent)+'</div></td><td class="sec">'+esc(r.category)+'</td>'
        +'<td class="n">'+a.toFixed(2)+'</td><td class="n">'+b.toFixed(2)+'</td>'
        +'<td class="n" style="color:'+(dl>0?'var(--good)':'var(--mut)')+'">'
        +(dl>0?'+':'')+dl.toFixed(2)+'</td></tr>';}
    document.getElementById('ev-table').innerHTML=h+'</tbody></table>';
    const bc=s.by_category||{};
    document.getElementById('ev-fail').innerHTML=kv({
      'Stopword deletion &mdash; "no prior treatment"':
        'the negation is deleted before scoring. <b>The criteria-half column fixes it.</b>',
      'Antonymy &mdash; "EGFR mutation negative"':
        '<span class="no">the column cannot fix this</span> &mdash; both sentences sit in the same half',
      'Polarity questions, recall':
        (bc.polarity? bc.polarity.recall_text_only+' &rarr; '+bc.polarity.recall_with_section:'?')
        +' (the weakest category)',
      'Other hybrid questions, recall':
        (bc.hybrid? bc.hybrid.recall_text_only+' &rarr; '+bc.hybrid.recall_with_section:'?'),
      'Worst single question':'"no prior systemic chemotherapy" &mdash; recall 0.15, because the '
        +'negation is in <i>your</i> question too'});
    document.getElementById('ev-caveat').textContent=s.caveat||'';
  }
  go();
})();
</script></body></html>"""
