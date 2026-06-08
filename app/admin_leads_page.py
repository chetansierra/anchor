"""The /admin/leads dashboard — one self-contained page (vanilla JS + fetch).

Reads /leads (admin-gated) and lets an operator set talk_to / country / note /
status inline. No framework, no build step — same spirit as admin_page.py. The
admin token comes from the page URL (?token=...) and is forwarded as a header.
"""

ADMIN_LEADS_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Leads</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; background:#0f1115; color:#e6e8ee; font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  header { padding:18px 22px; border-bottom:1px solid #232733; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
  h1 { font-size:17px; margin:0; font-weight:650; }
  .count { color:#8b93a7; font-size:13px; }
  .filters { display:flex; gap:8px; flex-wrap:wrap; margin-left:auto; }
  select, input { background:#161a22; border:1px solid #2a2f3d; color:#e6e8ee; border-radius:8px; padding:6px 9px; font:inherit; }
  input::placeholder { color:#6b7385; }
  .wrap { padding:16px 22px; overflow-x:auto; }
  table { width:100%; border-collapse:collapse; min-width:1040px; }
  th, td { text-align:left; padding:9px 10px; border-bottom:1px solid #1d212b; vertical-align:top; }
  th { color:#8b93a7; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; position:sticky; top:0; background:#0f1115; }
  td.small { color:#9aa3b5; font-size:12.5px; white-space:nowrap; }
  .src { display:inline-block; padding:1px 7px; border-radius:999px; font-size:11.5px; border:1px solid #2a2f3d; color:#aab2c5; }
  .problem { max-width:280px; }
  .cell-in { width:100%; min-width:90px; }
  .note-in { min-width:150px; }
  td.email { font-weight:600; }
  a { color:#6ea8fe; }
  .empty { color:#8b93a7; padding:40px 0; text-align:center; }
  .saved { outline:1px solid #2e7d52; transition:outline .1s; }
</style>
</head>
<body>
<header>
  <h1>Leads</h1>
  <span class="count" id="count"></span>
  <div class="filters">
    <input id="q" type="search" placeholder="Search email / problem / note" />
    <select id="f-source"><option value="">All sources</option><option value="consult">consult</option><option value="chat">chat</option></select>
    <select id="f-status"><option value="">All statuses</option><option value="new">new</option><option value="contacted">contacted</option><option value="closed">closed</option></select>
    <select id="f-talk"><option value="">Talk? any</option><option value="true">talk to</option><option value="false">skip</option></select>
    <input id="f-country" type="text" placeholder="Country" size="10" />
  </div>
</header>
<div class="wrap">
  <table>
    <thead><tr>
      <th>When</th><th>Source</th><th>Email</th><th>Contact</th><th>Problem</th>
      <th>Country</th><th>Talk?</th><th>Status</th><th>Note</th><th>Updated</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="empty" id="empty" style="display:none">No leads yet.</div>
</div>
<script>
  var TOKEN = new URLSearchParams(location.search).get("token") || "";
  function headers(extra) { var h = extra || {}; if (TOKEN) h["X-Admin-Token"] = TOKEN; return h; }
  function esc(s){ var d=document.createElement("div"); d.textContent = s==null?"":String(s); return d.innerHTML; }
  function fmt(ts){ if(!ts) return ""; try { return new Date(ts).toLocaleString(); } catch(e){ return ts; } }
  var $ = function(s){ return document.querySelector(s); };

  function query() {
    var p = new URLSearchParams();
    var q = $("#q").value.trim(); if (q) p.set("q", q);
    var s = $("#f-source").value; if (s) p.set("source", s);
    var st = $("#f-status").value; if (st) p.set("status", st);
    var t = $("#f-talk").value; if (t) p.set("talk_to", t);
    var c = $("#f-country").value.trim(); if (c) p.set("country", c);
    return p.toString();
  }

  function patch(id, field, value, el) {
    var body = {}; body[field] = value;
    fetch("/admin/leads/" + id, {
      method: "PATCH",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    }).then(function(r){
      if (el && r.ok) { el.classList.add("saved"); setTimeout(function(){ el.classList.remove("saved"); }, 600); }
    });
  }

  function talkSelect(lead) {
    var v = lead.talk_to === true ? "true" : lead.talk_to === false ? "false" : "";
    return '<select class="cell-in" data-f="talk_to" data-id="'+lead.id+'">' +
      '<option value=""'+(v===""?" selected":"")+'>—</option>' +
      '<option value="true"'+(v==="true"?" selected":"")+'>talk to</option>' +
      '<option value="false"'+(v==="false"?" selected":"")+'>skip</option></select>';
  }
  function statusSelect(lead) {
    var v = lead.status || "new";
    return ["new","contacted","closed"].map(function(o){
      return '<option value="'+o+'"'+(v===o?" selected":"")+'>'+o+'</option>';
    }).join("");
  }

  function render(leads) {
    $("#count").textContent = leads.length + " lead" + (leads.length===1?"":"s");
    $("#empty").style.display = leads.length ? "none" : "block";
    $("#rows").innerHTML = leads.map(function(l){
      return '<tr>' +
        '<td class="small">'+fmt(l.created_at)+'</td>' +
        '<td><span class="src">'+esc(l.source||"")+'</span></td>' +
        '<td class="email">'+esc(l.email||"")+'</td>' +
        '<td>'+esc(l.contact||"")+'</td>' +
        '<td class="problem">'+esc(l.problem||"")+'</td>' +
        '<td><input class="cell-in" data-f="country" data-id="'+l.id+'" value="'+esc(l.country||"")+'" placeholder="—" /></td>' +
        '<td>'+talkSelect(l)+'</td>' +
        '<td><select class="cell-in" data-f="status" data-id="'+l.id+'">'+statusSelect(l)+'</select></td>' +
        '<td><input class="cell-in note-in" data-f="note" data-id="'+l.id+'" value="'+esc(l.note||"")+'" placeholder="add a note" /></td>' +
        '<td class="small">'+fmt(l.updated_at)+'</td>' +
      '</tr>';
    }).join("");

    // wire inline edits
    document.querySelectorAll("[data-f]").forEach(function(el){
      var ev = el.tagName === "SELECT" ? "change" : "change"; // inputs fire change on blur/enter
      el.addEventListener(ev, function(){
        var f = el.getAttribute("data-f"), id = el.getAttribute("data-id"), v = el.value;
        if (f === "talk_to") v = v === "" ? null : v === "true";
        patch(id, f, v, el);
      });
    });
  }

  function load() {
    fetch("/leads?" + query(), { headers: headers() })
      .then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(function(d){ render(d.leads || []); })
      .catch(function(){ $("#rows").innerHTML = ""; $("#empty").style.display="block"; $("#empty").textContent = "Couldn't load leads (check the admin token in the URL)."; });
  }

  ["#q","#f-source","#f-status","#f-talk","#f-country"].forEach(function(s){
    $(s).addEventListener("input", load); $(s).addEventListener("change", load);
  });
  load();
</script>
</body>
</html>
"""
