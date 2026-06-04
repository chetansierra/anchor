/*
 * Anchor support widget — one <script> tag drops a grounded, action-taking
 * support agent onto any site.
 *
 *   <script src="https://YOUR_HOST/widget.js"
 *           data-business="Nimbus" data-color="#6ea8fe"
 *           data-position="bottom-right" data-machinery="off"></script>
 *
 * Everything lives inside a shadow root so the host page's CSS can't leak in (or
 * out). It talks to the same origin it was served from (override with data-api).
 * The "Show how it works" toggle (default off) reveals the machinery — retrieved
 * chunks + scores, latency, tokens, $ cost, tool-call JSON — proof on demand for
 * technical buyers, invisible to everyone else.
 */
(function () {
  "use strict";
  var me = document.currentScript;
  if (!me) return;

  var cfg = {
    api: (me.getAttribute("data-api") || new URL(me.src).origin).replace(/\/+$/, ""),
    business: me.getAttribute("data-business") || "",
    color: me.getAttribute("data-color") || "#6ea8fe",
    position: me.getAttribute("data-position") || "bottom-right",
    greeting: me.getAttribute("data-greeting") || "",
    machinery: (me.getAttribute("data-machinery") || "off").toLowerCase() === "on",
    topK: parseInt(me.getAttribute("data-top-k") || "3", 10),
  };

  // --- shadow-DOM host -------------------------------------------------------
  var host = document.createElement("div");
  host.setAttribute("data-anchor-widget", "");
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  var side = cfg.position.indexOf("left") !== -1 ? "left" : "right";
  root.innerHTML =
    "<style>" + styles(cfg.color, side) + "</style>" +
    '<div class="anchor' + (cfg.machinery ? " show-machinery" : "") + '">' +
    '  <button class="launcher" aria-label="Open chat">' + chatIcon() + "</button>" +
    '  <div class="panel" role="dialog" aria-label="Support chat" hidden>' +
    '    <header>' +
    '      <div class="title"><span class="dot"></span><span class="biz">Support</span></div>' +
    '      <label class="mech" title="Show retrieval, cost and tool details">' +
    '        <input type="checkbox" class="mech-toggle"' + (cfg.machinery ? " checked" : "") + " />" +
    "        <span>How it works</span>" +
    "      </label>" +
    '      <button class="close" aria-label="Close">&times;</button>' +
    "    </header>" +
    '    <div class="log"></div>' +
    '    <div class="chips"></div>' +
    '    <form class="composer">' +
    '      <input class="input" type="text" autocomplete="off" placeholder="Ask a question…" />' +
    '      <button class="send" type="submit" aria-label="Send">' + sendIcon() + "</button>" +
    "    </form>" +
    '    <div class="brand">powered by Anchor</div>' +
    "  </div>" +
    "</div>";

  var el = function (s) { return root.querySelector(s); };
  var panel = el(".panel"), log = el(".log"), chips = el(".chips");
  var input = el(".input"), anchorEl = el(".anchor"), bizEl = el(".biz");
  var busy = false;

  el(".launcher").addEventListener("click", openPanel);
  el(".close").addEventListener("click", function () { panel.hidden = true; });
  el(".mech-toggle").addEventListener("change", function (e) {
    anchorEl.classList.toggle("show-machinery", e.target.checked);
  });
  el(".composer").addEventListener("submit", function (e) {
    e.preventDefault();
    send(input.value);
  });

  // Self-configure from the server (business name + suggested prompts), with
  // data-attributes and sensible fallbacks winning where set.
  var suggested = ["How do I reset my password?", "Do you support SAML SSO?",
                   "What are your API rate limits?"];
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
    addMsg("bot", cfg.greeting ||
      ("Hi! Ask me anything about " + biz +
       " — I answer from our help center and can capture a request for you."));
    renderChips();
  }

  function openPanel() {
    panel.hidden = false;
    input.focus();
  }

  function renderChips() {
    chips.innerHTML = "";
    suggested.forEach(function (q) {
      var b = document.createElement("button");
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", function () { send(q); });
      chips.appendChild(b);
    });
  }

  function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    input.value = "";
    chips.innerHTML = "";
    addMsg("user", text);
    busy = true;
    var typing = addTyping();
    fetch(cfg.api + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, top_k: cfg.topK }),
    })
      .then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, status: r.status, body: j }; });
      })
      .then(function (res) {
        typing.remove();
        if (!res.ok) {
          addMsg("bot error", (res.body && res.body.detail) ||
            "Something went wrong. Please try again.");
          return;
        }
        renderAnswer(res.body);
      })
      .catch(function () {
        typing.remove();
        addMsg("bot error", "I couldn't reach the server. Please try again.");
      })
      .finally(function () { busy = false; });
  }

  // --- rendering -------------------------------------------------------------
  function addMsg(cls, text) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + cls;
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
    wrap.appendChild(bubble);
    log.appendChild(wrap);
    scroll();
    return wrap;
  }

  function addTyping() {
    var wrap = document.createElement("div");
    wrap.className = "msg bot";
    wrap.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
    log.appendChild(wrap);
    scroll();
    return wrap;
  }

  function renderAnswer(r) {
    var wrap = addMsg("bot", r.answer || "");

    // Visible actions — the tool call the user can see happen.
    (r.tool_calls || []).forEach(function (t) {
      var label = t.name === "book_callback" ? "Callback booked" : "Lead captured";
      var ref = (t.result.match(/lead_[a-z0-9]+/i) || [""])[0];
      var act = document.createElement("div");
      act.className = "action";
      act.innerHTML = "✅ " + escapeHtml(label) + (ref ? ' <code>' + ref + "</code>" : "");
      wrap.appendChild(act);
    });

    // Sources (citations).
    if (r.citations && r.citations.length) {
      var src = document.createElement("div");
      src.className = "sources";
      src.innerHTML = "Sources: " + r.citations.map(function (c) {
        return "[" + c.n + "] " + escapeHtml(c.title);
      }).join("  ·  ");
      wrap.appendChild(src);
    }

    // Machinery (revealed only when the toggle is on).
    wrap.appendChild(machinery(r));
    scroll();
  }

  function machinery(r) {
    var box = document.createElement("div");
    box.className = "machine";
    var u = r.usage || {};
    var stats =
      pill((r.latency_ms || 0).toFixed(0) + " ms") +
      pill("$" + (r.cost_usd || 0).toFixed(4)) +
      pill((u.input_tokens || 0) + "→" + (u.output_tokens || 0) + " tok") +
      pill((r.model || "") || "model") +
      (r.escalated ? pill("escalated") : "");
    var retrieved = (r.retrieved || []).map(function (h) {
      return '<div class="ret"><span class="score">' + (h.score || 0).toFixed(3) +
        '</span> <span class="rt">' + escapeHtml(h.title) + "</span></div>";
    }).join("");
    var tools = (r.tool_calls || []).length
      ? "<pre>" + escapeHtml(JSON.stringify(r.tool_calls, null, 2)) + "</pre>"
      : "";
    box.innerHTML =
      '<div class="stats">' + stats + "</div>" +
      '<div class="ret-head">retrieved</div>' + retrieved + tools;
    return box;
  }

  function pill(t) { return '<span class="pill">' + escapeHtml(t) + "</span>"; }
  function scroll() { log.scrollTop = log.scrollHeight; }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function chatIcon() {
    return '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
  }
  function sendIcon() {
    return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
  }
})();

function styles(color, side) {
  return [
    ":host{all:initial}",
    ".anchor{position:fixed;bottom:20px;" + side + ":20px;z-index:2147483000;",
    "  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}",
    ".launcher{width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;",
    "  background:" + color + ";color:#fff;display:flex;align-items:center;justify-content:center;",
    "  box-shadow:0 6px 20px rgba(0,0,0,.18);transition:transform .15s}",
    ".launcher:hover{transform:scale(1.06)}",
    ".panel{position:absolute;bottom:70px;" + side + ":0;width:370px;max-width:calc(100vw - 32px);",
    "  height:560px;max-height:calc(100vh - 110px);background:#fff;border-radius:16px;",
    "  box-shadow:0 16px 48px rgba(0,0,0,.22);display:flex;flex-direction:column;overflow:hidden;",
    "  border:1px solid #e7e9ee}",
    "header{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #eef0f4;",
    "  background:#fff}",
    ".title{display:flex;align-items:center;gap:8px;font-weight:600;color:#1c2130;font-size:15px}",
    ".dot{width:9px;height:9px;border-radius:50%;background:#4ade80;box-shadow:0 0 0 3px rgba(74,222,128,.18)}",
    ".mech{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280;",
    "  cursor:pointer;user-select:none}",
    ".mech input{accent-color:" + color + ";cursor:pointer}",
    ".close{background:none;border:none;font-size:22px;line-height:1;color:#9aa3b2;cursor:pointer;padding:0 2px}",
    ".log{flex:1;overflow-y:auto;padding:14px;background:#f7f8fa;display:flex;flex-direction:column;gap:10px}",
    ".msg{display:flex}",
    ".msg.user{justify-content:flex-end}",
    ".bubble{max-width:84%;padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.45;",
    "  color:#1c2130;background:#fff;border:1px solid #e7e9ee;white-space:normal;word-wrap:break-word}",
    ".msg.user .bubble{background:" + color + ";color:#fff;border-color:transparent}",
    ".msg.error .bubble{background:#fef2f2;border-color:#fecaca;color:#b91c1c}",
    ".typing{display:flex;gap:4px;align-items:center}",
    ".typing span{width:6px;height:6px;border-radius:50%;background:#c4c9d4;animation:blink 1.2s infinite both}",
    ".typing span:nth-child(2){animation-delay:.2s}.typing span:nth-child(3){animation-delay:.4s}",
    "@keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}",
    ".action{margin-top:7px;font-size:13px;color:#166534;background:#f0fdf4;border:1px solid #bbf7d0;",
    "  border-radius:10px;padding:6px 10px}",
    ".action code{background:#dcfce7;border-radius:5px;padding:1px 5px;font-size:12px}",
    ".sources{margin-top:6px;font-size:11.5px;color:#8a93a3;line-height:1.4}",
    ".machine{display:none;margin-top:8px;border-top:1px dashed #e2e5ec;padding-top:8px}",
    ".show-machinery .machine{display:block}",
    ".stats{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}",
    ".pill{font-size:11px;background:#eef1f6;color:#4b5563;border-radius:999px;padding:2px 8px;",
    "  font-variant-numeric:tabular-nums}",
    ".ret-head{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#9aa3b2;margin:4px 0 2px}",
    ".ret{display:flex;gap:8px;font-size:12px;color:#4b5563;padding:1px 0}",
    ".ret .score{color:" + color + ";font-variant-numeric:tabular-nums}",
    ".machine pre{margin:6px 0 0;background:#0f1115;color:#e6e8ee;border-radius:8px;padding:8px;",
    "  font-size:11px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}",
    ".chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 8px}",
    ".chip{font-size:12.5px;background:#fff;border:1px solid #d8dce4;color:#374151;border-radius:999px;",
    "  padding:6px 11px;cursor:pointer;transition:background .12s}",
    ".chip:hover{background:#f1f3f7}",
    ".composer{display:flex;gap:8px;padding:10px 12px;border-top:1px solid #eef0f4;background:#fff}",
    ".input{flex:1;border:1px solid #d8dce4;border-radius:10px;padding:9px 12px;font-size:14px;outline:none}",
    ".input:focus{border-color:" + color + "}",
    ".send{border:none;background:" + color + ";color:#fff;border-radius:10px;width:40px;cursor:pointer;",
    "  display:flex;align-items:center;justify-content:center}",
    ".brand{text-align:center;font-size:10px;color:#b8bec9;padding:0 0 8px}",
  ].join("");
}
