/*
 * Anchor support widget — one <script> tag drops a grounded, action-taking
 * support agent onto any site.
 *
 *   <script src="https://YOUR_HOST/widget.js"
 *           data-business="Nimbus" data-color="#0f5f36"
 *           data-position="bottom-right" data-machinery="off"></script>
 *
 * Everything lives inside a shadow root so the host page's CSS can't leak in (or
 * out). It talks to the same origin it was served from (override with data-api).
 * Retrieval is always visible (a "searching…" step + the sources each answer used);
 * the "Behind the answer" toggle adds the deeper machinery — chunk scores, latency,
 * tokens, $ cost, and tool-call JSON.
 */
(function () {
  "use strict";
  var me = document.currentScript;
  if (!me) return;

  var cfg = {
    api: (me.getAttribute("data-api") || new URL(me.src).origin).replace(/\/+$/, ""),
    business: me.getAttribute("data-business") || "",
    color: me.getAttribute("data-color") || "#0f5f36",
    position: me.getAttribute("data-position") || "bottom-right",
    greeting: me.getAttribute("data-greeting") || "",
    machinery: (me.getAttribute("data-machinery") || "off").toLowerCase() === "on",
    topK: parseInt(me.getAttribute("data-top-k") || "3", 10),
  };

  var host = document.createElement("div");
  host.setAttribute("data-anchor-widget", "");
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });
  var side = cfg.position.indexOf("left") !== -1 ? "left" : "right";

  root.innerHTML =
    "<style>" + styles(cfg.color, side) + "</style>" +
    '<div class="anchor' + (cfg.machinery ? " show-machinery" : "") + '">' +
    '  <div class="panel" role="dialog" aria-label="Support chat">' +
    '    <header>' +
    '      <div class="title">' +
    '        <span class="dot"></span>' +
    '        <div class="tt"><span class="biz">Support</span><span class="sub">AI agent · answers from the help center</span></div>' +
    "      </div>" +
    '      <button class="close" aria-label="Close chat">' + chevronIcon() + "</button>" +
    "    </header>" +
    '    <div class="log"></div>' +
    '    <div class="foot">' +
    '      <button class="mech-btn" type="button" aria-pressed="' + (cfg.machinery ? "true" : "false") + '">' +
    '        ' + eyeIcon() + '<span>Behind the answer</span>' +
    "      </button>" +
    '      <form class="composer">' +
    '        <input class="input" type="text" autocomplete="off" placeholder="Ask a question…" aria-label="Your question" />' +
    '        <button class="send" type="submit" aria-label="Send">' + sendIcon() + "</button>" +
    "      </form>" +
    "    </div>" +
    "  </div>" +
    '  <button class="launcher" aria-label="Open chat">' +
    '    <span class="ic ic-chat">' + chatIcon() + "</span>" +
    '    <span class="ic ic-close">' + closeIcon() + "</span>" +
    "  </button>" +
    "</div>";

  var el = function (s) { return root.querySelector(s); };
  var anchorEl = el(".anchor"), log = el(".log");
  var input = el(".input"), bizEl = el(".biz"), mechBtn = el(".mech-btn");
  var busy = false;

  el(".launcher").addEventListener("click", toggle);
  el(".close").addEventListener("click", close);
  mechBtn.addEventListener("click", function () {
    var on = !anchorEl.classList.contains("show-machinery");
    anchorEl.classList.toggle("show-machinery", on);
    mechBtn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  el(".composer").addEventListener("submit", function (e) {
    e.preventDefault();
    send(input.value);
  });

  // Let the host page drive the widget (e.g. "try it" chips in a hero).
  window.AnchorWidget = {
    open: open,
    ask: function (text) { open(); send(text); },
  };

  function open() { anchorEl.classList.add("open"); setTimeout(function () { input.focus(); }, 120); }
  function close() { anchorEl.classList.remove("open"); }
  function toggle() { anchorEl.classList.contains("open") ? close() : open(); }

  // Self-configure from the server (business + suggested prompts).
  var suggested = ["How do I reset my password?", "Do you support SAML SSO?",
                   "Can someone call me about pricing?"];
  var greeted = false;
  fetch(cfg.api + "/widget/config")
    .then(function (r) { return r.json(); })
    .catch(function () { return {}; })
    .then(function (c) {
      var biz = cfg.business || c.business || "us";
      bizEl.textContent = biz;
      if (Array.isArray(c.suggested) && c.suggested.length) suggested = c.suggested;
      if (!cfg.greeting && c.greeting) cfg.greeting = c.greeting;
      greet(biz);
    });

  function greet(biz) {
    if (greeted) return;
    greeted = true;
    addBot(cfg.greeting ||
      ("Hi! I'm the AI assistant for " + biz + ". I answer from their help center — " +
       "with sources — and can capture a request for you. Try one:"));
    renderChips();
  }

  function renderChips() {
    var col = lastBotCol();
    if (!col) return;
    var chips = document.createElement("div");
    chips.className = "chips";
    suggested.forEach(function (q) {
      var b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.textContent = q;
      b.addEventListener("click", function () { send(q); });
      chips.appendChild(b);
    });
    col.appendChild(chips);
    scroll();
  }

  function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    open();
    input.value = "";
    removeChips();
    addUser(text);
    busy = true;
    var thinking = addThinking();
    fetch(cfg.api + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, top_k: cfg.topK }),
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        thinking.remove();
        if (!res.ok) {
          addBot((res.body && res.body.detail) || "Something went wrong. Please try again.", "error");
          return;
        }
        renderAnswer(res.body);
      })
      .catch(function () {
        thinking.remove();
        addBot("I couldn't reach the server. Please try again.", "error");
      })
      .finally(function () { busy = false; });
  }

  // --- message construction --------------------------------------------------
  function addRow(who) {
    var row = document.createElement("div");
    row.className = "msg " + who;
    var col = document.createElement("div");
    col.className = "col";
    row.appendChild(col);
    log.appendChild(row);
    scroll();
    return col;
  }
  function bubble(col, text, extra) {
    var b = document.createElement("div");
    b.className = "bubble" + (extra ? " " + extra : "");
    b.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
    col.appendChild(b);
    return b;
  }
  function addUser(text) { var c = addRow("user"); bubble(c, text); }
  function addBot(text, extra) { var c = addRow("bot"); bubble(c, text, extra); return c; }

  function addThinking() {
    var col = addRow("bot");
    col.innerHTML =
      '<div class="bubble thinking">' + searchIcon() +
      '<span>Searching the knowledge base</span>' +
      '<span class="dots"><i></i><i></i><i></i></span></div>';
    var row = col.parentNode;
    return { remove: function () { row.remove(); } };
  }

  function renderAnswer(r) {
    var col = addRow("bot");
    bubble(col, r.answer || "");

    // Visible action — the tool call the user can see happen.
    (r.tool_calls || []).forEach(function (t) {
      var label = t.name === "book_callback" ? "Callback booked" : "Lead captured";
      var ref = (t.result.match(/lead_[a-z0-9]+/i) || [""])[0];
      var act = document.createElement("div");
      act.className = "action";
      act.innerHTML = "✓ " + escapeHtml(label) + (ref ? ' <code>' + ref + "</code>" : "");
      col.appendChild(act);
    });

    // Sources — always shown, so retrieval is visible without any toggle.
    if (r.citations && r.citations.length) {
      var src = document.createElement("div");
      src.className = "sources";
      src.innerHTML =
        '<span class="src-h">' + bookIcon() + " Answered from " + r.citations.length +
        " source" + (r.citations.length > 1 ? "s" : "") + "</span>" +
        r.citations.map(function (c) {
          return '<span class="src">[' + c.n + "] " + escapeHtml(c.title) + "</span>";
        }).join("");
      col.appendChild(src);
    } else if (!r.escalated) {
      var none = document.createElement("div");
      none.className = "sources muted";
      none.textContent = "No confident source match.";
      col.appendChild(none);
    }

    // Deeper machinery — revealed by the "Behind the answer" toggle.
    col.appendChild(machinery(r));
    scroll();
  }

  function machinery(r) {
    var box = document.createElement("div");
    box.className = "machine";
    var u = r.usage || {};
    var stats =
      pill((r.latency_ms || 0).toFixed(0) + " ms", "latency") +
      pill("$" + (r.cost_usd || 0).toFixed(4), "cost") +
      pill((u.input_tokens || 0) + "→" + (u.output_tokens || 0) + " tok") +
      pill(r.model || "model") +
      (r.escalated ? pill("escalated", "warn") : "");
    var retrieved = (r.retrieved || []).map(function (h) {
      var pct = Math.max(0, Math.min(1, h.score || 0)) * 100;
      return '<div class="ret">' +
        '<div class="ret-top"><span class="rt">' + escapeHtml(h.title) +
        '</span><span class="rs">' + (h.score || 0).toFixed(3) + "</span></div>" +
        '<div class="bar"><i style="width:' + pct.toFixed(0) + '%"></i></div></div>';
    }).join("");
    var tools = (r.tool_calls || []).length
      ? '<div class="m-h">tool call</div><pre>' + escapeHtml(JSON.stringify(r.tool_calls, null, 2)) + "</pre>"
      : "";
    box.innerHTML =
      '<div class="m-h">how this answer was produced</div>' +
      '<div class="stats">' + stats + "</div>" +
      (retrieved ? '<div class="m-h">retrieved chunks (cosine score)</div>' + retrieved : "") +
      tools;
    return box;
  }

  // --- helpers ---------------------------------------------------------------
  function lastBotCol() {
    var rows = log.querySelectorAll(".msg.bot .col");
    return rows.length ? rows[rows.length - 1] : null;
  }
  function removeChips() { var c = log.querySelector(".chips"); if (c) c.remove(); }
  function pill(t, cls) { return '<span class="pill ' + (cls || "") + '">' + escapeHtml(t) + "</span>"; }
  function scroll() { log.scrollTop = log.scrollHeight; }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function chatIcon(){return svg('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',26);}
  function closeIcon(){return svg('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',24);}
  function chevronIcon(){return svg('<polyline points="6 9 12 15 18 9"/>',20);}
  function sendIcon(){return svg('<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',18);}
  function eyeIcon(){return svg('<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>',15);}
  function searchIcon(){return svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',15);}
  function bookIcon(){return svg('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',13);}
  function svg(inner,s){return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+inner+"</svg>";}
})();

function styles(color, side) {
  return [
    ":host{all:initial}",
    "*{box-sizing:border-box}",
    ".anchor{position:fixed;bottom:20px;" + side + ":20px;z-index:2147483000;",
    "  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}",

    /* launcher */
    ".launcher{position:absolute;bottom:0;" + side + ":0;width:58px;height:58px;border-radius:50%;border:none;",
    "  cursor:pointer;background:" + color + ";color:#fff;display:flex;align-items:center;justify-content:center;",
    "  box-shadow:0 8px 24px rgba(0,0,0,.20);transition:transform .15s}",
    ".launcher:hover{transform:scale(1.06)}",
    ".launcher .ic{position:absolute;display:flex;transition:opacity .18s,transform .18s}",
    ".ic-close{opacity:0;transform:rotate(-90deg) scale(.6)}",
    ".anchor.open .ic-chat{opacity:0;transform:rotate(90deg) scale(.6)}",
    ".anchor.open .ic-close{opacity:1;transform:none}",

    /* panel + open animation */
    ".panel{position:absolute;bottom:74px;" + side + ":0;width:380px;max-width:calc(100vw - 32px);",
    "  height:564px;max-height:calc(100vh - 120px);background:#fff;border-radius:18px;overflow:hidden;",
    "  display:flex;flex-direction:column;border:1px solid #e7ece8;box-shadow:0 18px 50px rgba(12,28,20,.22);",
    "  opacity:0;visibility:hidden;transform:translateY(12px) scale(.97);transform-origin:bottom " + side + ";",
    "  transition:opacity .2s ease,transform .2s ease,visibility .2s}",
    ".anchor.open .panel{opacity:1;visibility:visible;transform:none}",

    /* header */
    "header{display:flex;align-items:center;gap:11px;padding:13px 14px;border-bottom:1px solid #eef2ef;background:#fff}",
    ".title{display:flex;align-items:center;gap:10px;min-width:0}",
    ".dot{width:9px;height:9px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 3px rgba(34,197,94,.18);flex:none}",
    ".tt{display:flex;flex-direction:column;min-width:0}",
    ".biz{font-weight:700;color:#10231a;font-size:15px;line-height:1.2}",
    ".sub{font-size:11.5px;color:#7d8a82;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".close{margin-left:auto;background:#f3f6f4;border:none;color:#5b6b62;width:30px;height:30px;border-radius:9px;",
    "  cursor:pointer;display:flex;align-items:center;justify-content:center}",
    ".close:hover{background:#e8efea}",

    /* log */
    ".log{flex:1;overflow-y:auto;padding:14px;background:#f7faf8;display:flex;flex-direction:column;gap:12px}",
    ".msg{display:flex}",
    ".msg.user{justify-content:flex-end}",
    ".col{display:flex;flex-direction:column;gap:7px;max-width:90%;min-width:0}",
    ".msg.user .col{align-items:flex-end}",
    ".bubble{padding:10px 13px;border-radius:14px;font-size:14px;line-height:1.5;color:#16241d;background:#fff;",
    "  border:1px solid #e7ece8;word-wrap:break-word;overflow-wrap:anywhere;max-width:100%}",
    ".msg.user .bubble{background:" + color + ";color:#fff;border-color:transparent;border-bottom-right-radius:5px}",
    ".msg.bot .bubble{border-bottom-left-radius:5px}",
    ".bubble.error{background:#fef2f2;border-color:#fecaca;color:#b91c1c}",
    ".thinking{display:flex;align-items:center;gap:8px;color:#5b6b62}",
    ".dots{display:inline-flex;gap:3px}",
    ".dots i{width:5px;height:5px;border-radius:50%;background:#b9c4bd;animation:blink 1.2s infinite both}",
    ".dots i:nth-child(2){animation-delay:.2s}.dots i:nth-child(3){animation-delay:.4s}",
    "@keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}",

    /* action + sources (always visible) */
    ".action{font-size:13px;color:#0f5f36;background:#eaf6ec;border:1px solid #c7e6d2;border-radius:10px;padding:7px 11px}",
    ".action code{background:#d6efde;border-radius:5px;padding:1px 6px;font-size:12px}",
    ".sources{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:11.5px}",
    ".sources.muted{color:#9aa79f}",
    ".src-h{display:inline-flex;align-items:center;gap:5px;color:#5b6b62;font-weight:600}",
    ".src{background:#eef2ef;color:#46564d;border-radius:6px;padding:2px 8px}",

    /* machinery (toggle) */
    ".machine{display:none;margin-top:2px;background:#fbfdfc;border:1px solid #e7ece8;border-radius:12px;padding:11px}",
    ".show-machinery .machine{display:block}",
    ".m-h{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#9aa79f;margin:0 0 6px}",
    ".m-h+.m-h,.stats+.m-h,.ret+.m-h{margin-top:10px}",
    ".stats{display:flex;flex-wrap:wrap;gap:5px}",
    ".pill{font-size:11px;background:#eef2ef;color:#46564d;border-radius:999px;padding:2px 9px;font-variant-numeric:tabular-nums}",
    ".pill.cost{background:#eaf6ec;color:" + color + ";font-weight:600}",
    ".pill.warn{background:#fff4e5;color:#b45309}",
    ".ret{margin:6px 0}",
    ".ret-top{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#46564d}",
    ".ret .rs{color:" + color + ";font-variant-numeric:tabular-nums}",
    ".bar{height:5px;background:#eef2ef;border-radius:3px;margin-top:3px;overflow:hidden}",
    ".bar i{display:block;height:100%;background:" + color + ";border-radius:3px}",
    ".machine pre{margin:6px 0 0;background:#0c1c14;color:#cdeed8;border-radius:8px;padding:9px;font-size:11px;",
    "  overflow-x:auto;white-space:pre-wrap;word-break:break-word}",

    /* chips */
    ".chips{display:flex;flex-wrap:wrap;gap:7px}",
    ".chip{font-size:13px;text-align:left;background:#fff;border:1px solid #cfe3d6;color:" + color + ";border-radius:12px;",
    "  padding:8px 12px;cursor:pointer;transition:background .12s,transform .12s;font-weight:500}",
    ".chip:hover{background:#eaf6ec;transform:translateY(-1px)}",

    /* footer: behind-the-answer toggle + composer */
    ".foot{border-top:1px solid #eef2ef;background:#fff;padding:9px 12px 11px}",
    ".mech-btn{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:#5b6b62;background:#f3f6f4;",
    "  border:1px solid #e3eae5;border-radius:999px;padding:5px 11px;cursor:pointer;margin-bottom:9px;transition:.12s}",
    ".mech-btn:hover{background:#e8efea}",
    ".mech-btn[aria-pressed='true']{background:#eaf6ec;border-color:#c7e6d2;color:" + color + ";font-weight:600}",
    ".composer{display:flex;gap:8px}",
    ".input{flex:1;border:1px solid #d6e0da;border-radius:11px;padding:11px 13px;font-size:14px;outline:none;color:#16241d}",
    ".input:focus{border-color:" + color + ";box-shadow:0 0 0 3px rgba(15,95,54,.10)}",
    ".send{border:none;background:" + color + ";color:#fff;border-radius:11px;width:44px;flex:none;cursor:pointer;",
    "  display:flex;align-items:center;justify-content:center}",
    ".send:hover{filter:brightness(1.06)}",
  ].join("");
}
