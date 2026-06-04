"""The tiny admin dashboard — one self-contained HTML page, no build step.

Served at GET /admin. It calls the JSON admin endpoints (/admin/overview,
/admin/conversations, /admin/conversations/{id}) and renders an operator view:
headline cost/latency cards, a daily cost rollup, and a click-to-expand list of
recent conversations with their full trace. Vanilla JS + CSS so it drops in
anywhere and screenshots cleanly for the case study.
"""

ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Anchor — Observability</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --panel-2: #1d212b; --line: #272c38;
    --text: #e6e8ee; --muted: #9aa3b2; --accent: #6ea8fe; --good: #4ade80;
    --warn: #fbbf24; --bad: #f87171;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  header { padding: 20px 24px; border-bottom: 1px solid var(--line); display: flex;
           align-items: baseline; gap: 12px; }
  header h1 { font-size: 18px; margin: 0; }
  header .sub { color: var(--muted); font-size: 13px; }
  header .refresh { margin-left: auto; color: var(--accent); cursor: pointer;
                    font-size: 13px; user-select: none; }
  main { padding: 24px; max-width: 1100px; margin: 0 auto; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
           gap: 14px; margin-bottom: 24px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
          padding: 16px; }
  .card .label { color: var(--muted); font-size: 12px; text-transform: uppercase;
                 letter-spacing: .04em; }
  .card .value { font-size: 24px; font-weight: 600; margin-top: 6px; }
  h2 { font-size: 14px; color: var(--muted); text-transform: uppercase;
       letter-spacing: .04em; margin: 28px 0 12px; }
  table { width: 100%; border-collapse: collapse; background: var(--panel);
          border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
  th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line);
           font-size: 13px; }
  th { color: var(--muted); font-weight: 500; background: var(--panel-2); }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr.conv { cursor: pointer; }
  tbody tr.conv:hover { background: var(--panel-2); }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
  .pill.answered { background: rgba(74,222,128,.15); color: var(--good); }
  .pill.escalated { background: rgba(251,191,36,.15); color: var(--warn); }
  .pill.error { background: rgba(248,113,113,.15); color: var(--bad); }
  .q { max-width: 460px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .detail { background: var(--panel-2); }
  .detail pre { margin: 0; padding: 14px 18px; white-space: pre-wrap; word-break: break-word;
                font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--text); }
  .empty { color: var(--muted); padding: 24px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Anchor</h1>
  <span class="sub">Observability &amp; cost</span>
  <span class="refresh" onclick="load()">↻ refresh</span>
</header>
<main>
  <div class="cards" id="cards"></div>
  <h2>Daily cost</h2>
  <table id="daily"><tbody></tbody></table>
  <h2>Recent conversations</h2>
  <table id="convs"><tbody></tbody></table>
</main>
<script>
const $ = (s) => document.querySelector(s);
const usd = (n) => "$" + Number(n).toFixed(4);
const esc = (s) => (s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

async function load() {
  const [ov, convs] = await Promise.all([
    fetch("/admin/overview").then(r => r.json()),
    fetch("/admin/conversations?limit=50").then(r => r.json()),
  ]);
  renderCards(ov);
  renderDaily(ov.daily);
  renderConvs(convs.conversations);
}

function renderCards(ov) {
  const cards = [
    ["Total runs", ov.total_runs],
    ["Total cost", usd(ov.total_cost_usd)],
    ["Avg cost / convo", usd(ov.avg_cost_per_conversation)],
    ["Avg latency", Math.round(ov.avg_latency_ms) + " ms"],
    ["Escalation rate", (ov.escalation_rate * 100).toFixed(1) + "%"],
    ["Tokens (in/out)", ov.total_input_tokens + " / " + ov.total_output_tokens],
  ];
  $("#cards").innerHTML = cards.map(([l, v]) =>
    `<div class="card"><div class="label">${l}</div><div class="value">${v}</div></div>`
  ).join("");
}

function renderDaily(daily) {
  const head = `<tr><th>Date</th><th class="num">Runs</th><th class="num">In</th>
    <th class="num">Out</th><th class="num">Escalated</th><th class="num">Cost</th></tr>`;
  const body = daily.length ? daily.map(d =>
    `<tr><td>${d.date}</td><td class="num">${d.runs}</td><td class="num">${d.input_tokens}</td>
     <td class="num">${d.output_tokens}</td><td class="num">${d.escalated}</td>
     <td class="num">${usd(d.cost_usd)}</td></tr>`
  ).join("") : `<tr><td colspan="6" class="empty">No runs yet — POST /chat to generate traces.</td></tr>`;
  $("#daily").innerHTML = "<tbody>" + head + body + "</tbody>";
}

function renderConvs(convs) {
  const head = `<tr><th>Time</th><th>Question</th><th>Outcome</th>
    <th class="num">Latency</th><th class="num">Cost</th></tr>`;
  if (!convs.length) {
    $("#convs").innerHTML = `<tbody>${head}<tr><td colspan="5" class="empty">No conversations yet.</td></tr></tbody>`;
    return;
  }
  const rows = convs.map(c => {
    const t = new Date(c.created_at).toLocaleString();
    const tools = c.tools.length ? ` · ${c.tools.join(", ")}` : "";
    return `<tr class="conv" onclick="toggle('${c.id}', this)">
      <td>${t}</td><td class="q">${esc(c.question)}</td>
      <td><span class="pill ${c.outcome}">${c.outcome}</span>${tools}</td>
      <td class="num">${Math.round(c.latency_ms)} ms</td>
      <td class="num">${usd(c.cost_usd)}</td></tr>`;
  }).join("");
  $("#convs").innerHTML = "<tbody>" + head + rows + "</tbody>";
}

async function toggle(id, row) {
  const next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) { next.remove(); return; }
  const trace = await fetch("/admin/conversations/" + id).then(r => r.json());
  const tr = document.createElement("tr");
  tr.className = "detail";
  tr.innerHTML = `<td colspan="5"><pre>${esc(JSON.stringify(trace, null, 2))}</pre></td>`;
  row.after(tr);
}

load();
</script>
</body>
</html>"""
