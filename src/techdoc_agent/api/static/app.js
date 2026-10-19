"use strict";

// Interfaz de TechDoc Agent. Todo lo que llega del servidor o del modelo es no confiable:
// el texto entra con textContent y el Markdown pasa por DOMPurify antes de tocar el DOM.

const $ = (id) => document.getElementById(id);
const els = {
  messages: $("messages"), chatEmpty: $("chat-empty"), form: $("chat-form"), input: $("message"),
  send: $("send"), newChat: $("new-chat"), docList: $("doc-list"), docEmpty: $("doc-empty"),
  docStatus: $("doc-status"), fileInput: $("file-input"), drop: $("drop"), dropHint: $("drop-hint"),
  turns: $("turns"), traceEmpty: $("trace-empty"), docsPanel: $("docs-panel"), tracePanel: $("trace-panel"),
  convPanel: $("conv-panel"), convList: $("conv-list"), convEmpty: $("conv-empty"), convStatus: $("conv-status"),
};

let turnCount = 0;
let mermaidCount = 0;
let busy = false;

// --- sesión: el id de la conversación actual se recuerda para volver a ella al recargar ---

function newSessionId() {
  return crypto.randomUUID().replaceAll("-", "");
}
function sessionId() {
  try {
    let id = localStorage.getItem("conversation_id");
    if (!id) { id = newSessionId(); localStorage.setItem("conversation_id", id); }
    return id;
  } catch { return (sessionId.fallback ||= newSessionId()); }
}
function setSession(id) {
  try { localStorage.setItem("conversation_id", id); } catch { sessionId.fallback = id; }
}

// --- utilidades ---

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try { body = await response.json(); } catch { /* respuesta sin JSON */ }
  if (!response.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : "Error " + response.status;
    throw new Error(detail);
  }
  return body;
}

// Markdown → HTML saneado. La salida del modelo se trata como entrada de un desconocido.
if (window.DOMPurify) {
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A") { node.setAttribute("target", "_blank"); node.setAttribute("rel", "noopener noreferrer"); }
  });
}
const LIBS_OK = Boolean(window.marked && window.DOMPurify);

// Si las librerías no cargaron (sin red o bloqueadas), el texto se muestra tal cual, nunca como HTML.
function setRich(node, text) {
  if (!LIBS_OK) { node.textContent = text; return; }
  const html = marked.parse(text, { gfm: true });
  node.innerHTML = DOMPurify.sanitize(html, {
    FORBID_TAGS: ["style", "form", "input", "button", "textarea", "select"], FORBID_ATTR: ["style"] });
}

function addCopyButtons(container) {
  container.querySelectorAll("pre").forEach((pre) => {
    const wrap = el("div", "codeblock");
    pre.replaceWith(wrap);
    wrap.append(pre);
    const button = el("button", "copy", "Copiar");
    button.type = "button";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(pre.textContent);
        button.textContent = "Copiado";
      } catch { button.textContent = "No se pudo copiar"; }
      setTimeout(() => { button.textContent = "Copiar"; }, 1500);
    });
    wrap.append(button);
  });
}

function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

function scrollToEnd() { els.messages.scrollTop = els.messages.scrollHeight; }

function setStatus(text, isError = false) {
  els.docStatus.textContent = text;
  els.docStatus.classList.toggle("error", isError);
}

// --- documentos ---

async function loadDocuments() {
  try {
    const docs = await api("/api/documents");
    els.docList.replaceChildren(...docs.map(docItem));
    els.docEmpty.hidden = docs.length > 0;
  } catch (error) { setStatus(error.message, true); }
}

function docItem(doc) {
  const item = el("li");
  item.append(el("span", "doc-name", doc.source), el("span", "doc-meta", plural(doc.chunks, "fragmento", "fragmentos")));
  const remove = el("button", "link-btn", "Quitar");
  remove.type = "button";
  remove.setAttribute("aria-label", "Quitar " + doc.source);
  remove.addEventListener("click", () => removeDocument(doc.source));
  item.append(remove);
  return item;
}

async function removeDocument(source) {
  if (!confirm("¿Quitar " + source + " del índice?")) return;
  try {
    await api("/api/documents/" + encodeURIComponent(source), { method: "DELETE" });
    setStatus(source + " quitado del índice.");
  } catch (error) { setStatus(error.message, true); }
  loadDocuments();
}

async function uploadFile(file) {
  setStatus("Indexando " + file.name + "…");
  const data = new FormData();
  data.append("file", file);
  try {
    const result = await api("/api/documents", { method: "POST", body: data });
    const warnings = result.warnings.length ? " Avisos: " + result.warnings.join("; ") : "";
    setStatus(result.source + " indexado: " + result.chunks + " fragmentos." + warnings);
  } catch (error) { setStatus(error.message, true); }
  els.fileInput.value = "";
  loadDocuments();
}

els.fileInput.addEventListener("change", () => { if (els.fileInput.files[0]) uploadFile(els.fileInput.files[0]); });
["dragenter", "dragover"].forEach((type) => els.drop.addEventListener(type, (event) => {
  event.preventDefault(); els.drop.classList.add("over");
}));
["dragleave", "drop"].forEach((type) => els.drop.addEventListener(type, (event) => {
  event.preventDefault(); els.drop.classList.remove("over");
}));
els.drop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) uploadFile(file);
});

// --- chat ---

function addUserMessage(text) {
  els.chatEmpty.hidden = true;
  els.messages.append(el("div", "msg-user", text));
  scrollToEnd();
}

function addAgentMessage(reply) {
  const box = el("div", "msg-agent");
  setRich(box, reply);
  addCopyButtons(box);
  els.messages.append(box);
  return box;
}

async function addArtifact(box, artifact) {
  const card = el("section", "artifact");
  const head = el("header");
  head.append(el("span", "artifact-title", artifact.title || artifact.name), el("span", "artifact-name", artifact.name));
  const link = el("a", "download", "Descargar");
  link.href = "/api/artifacts/" + encodeURIComponent(artifact.name);
  link.download = artifact.name;
  head.append(link);
  const body = el("div", "artifact-body");
  card.append(head, body);
  box.append(card);
  try {
    const response = await fetch(link.href);
    if (response.status === 404) throw new Error("El archivo de este artefacto ya no está disponible.");
    if (!response.ok) throw new Error("No se pudo leer el artefacto (" + response.status + ")");
    const text = await response.text();
    if (artifact.type === "mermaid" && window.mermaid) await renderMermaid(body, text);
    else if (artifact.type === "mermaid") body.append(el("pre", "", text));
    else setRich(body, text);
  } catch (error) { body.append(el("p", "artifact-note", error.message)); }
}

async function renderMermaid(body, code) {
  try {
    const { svg } = await mermaid.render("mmd-" + (++mermaidCount), code);
    body.innerHTML = svg; // generado por mermaid con securityLevel "strict"
  } catch (error) {
    // La validación del servidor es heurística: un diagrama puede pasarla y aun así no renderizar.
    body.append(el("p", "artifact-note", "Mermaid no pudo dibujar este diagrama. Se muestra su código."));
    const pre = el("pre"); pre.append(el("code", "", code));
    body.append(pre);
    addCopyButtons(body);
    document.querySelectorAll('[id^="dmmd-"]').forEach((node) => node.remove()); // restos del render fallido
  }
}

function addTurn(data) {
  turnCount += 1;
  els.traceEmpty.hidden = true;
  const turn = el("li");
  const tokens = data.usage.input_tokens + " tokens de entrada, " + data.usage.output_tokens + " de salida";
  turn.append(el("p", "turn-head", "Respuesta " + turnCount + " · " + tokens));
  if (!data.tool_calls.length) {
    turn.append(el("p", "no-steps", "Respondió sin usar herramientas."));
  } else {
    const steps = el("ol", "steps");
    for (const call of data.tool_calls) {
      const step = el("li", "step" + (call.is_error ? " error" : ""));
      const title = el("div", "step-title");
      title.append(el("span", "name", call.tool), el("span", "time", call.duration_ms + " ms"));
      step.append(title);
      if (call.is_error) step.append(el("div", "step-error", "La herramienta devolvió un error; el agente puede corregirlo."));
      step.append(el("pre", "", JSON.stringify(call.args, null, 2)));
      steps.append(step);
    }
    turn.append(steps);
  }
  els.turns.append(turn);
  els.tracePanel.scrollTop = els.tracePanel.scrollHeight;
}

async function showAgentTurn(data) {
  const box = addAgentMessage(data.reply);
  addTurn(data);
  for (const artifact of data.artifacts) await addArtifact(box, artifact);
}

async function sendMessage(text) {
  busy = true;
  els.send.disabled = true;
  addUserMessage(text);
  const waiting = el("div", "msg-wait", "El agente está trabajando…");
  els.messages.append(waiting);
  scrollToEnd();
  try {
    const data = await api("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId(), message: text }),
    });
    waiting.remove();
    await showAgentTurn(data);
    loadConversations();
  } catch (error) {
    waiting.replaceWith(el("div", "msg-error", error.message));
  } finally {
    busy = false;
    els.send.disabled = false;
    els.input.focus();
    scrollToEnd();
  }
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = els.input.value.trim();
  if (!text || busy) return;
  els.input.value = "";
  sendMessage(text);
});
els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); els.form.requestSubmit(); }
});
function clearChat() {
  turnCount = 0;
  els.messages.replaceChildren(els.chatEmpty);
  els.chatEmpty.hidden = false;
  els.turns.replaceChildren();
  els.traceEmpty.hidden = false;
}

els.newChat.addEventListener("click", () => {
  if (busy) return;
  setSession(newSessionId());
  clearChat();
  loadConversations();
  els.input.focus();
});

// --- conversaciones guardadas ---

function setConvStatus(text, isError = false) {
  els.convStatus.textContent = text;
  els.convStatus.classList.toggle("error", isError);
}

async function loadConversations() {
  try {
    const list = await api("/api/conversations");
    const current = sessionId();
    els.convList.replaceChildren(...list.map((conv) => convItem(conv, conv.id === current)));
    els.convEmpty.hidden = list.length > 0;
    return list;
  } catch (error) { setConvStatus(error.message, true); return []; }
}

function convItem(conv, isCurrent) {
  const item = el("li");
  if (isCurrent) item.setAttribute("aria-current", "true");
  const open = el("button", "conv-open");
  open.type = "button";
  const when = new Date(conv.updated).toLocaleString("es", { dateStyle: "short", timeStyle: "short" });
  open.append(el("span", "conv-title", conv.title), el("span", "conv-meta", plural(conv.turns, "pregunta", "preguntas") + " · " + when));
  open.addEventListener("click", () => openConversation(conv.id));
  const remove = el("button", "link-btn", "Quitar");
  remove.type = "button";
  remove.setAttribute("aria-label", "Quitar la conversación " + conv.title);
  remove.addEventListener("click", () => removeConversation(conv.id, conv.title));
  item.append(open, remove);
  return item;
}

async function openConversation(id) {
  if (busy) return;
  try {
    const conv = await api("/api/conversations/" + encodeURIComponent(id));
    setSession(id);
    clearChat();
    for (const turn of conv.turns) {
      addUserMessage(turn.message);
      await showAgentTurn(turn);
    }
    setConvStatus("");
    loadConversations();
  } catch (error) { setConvStatus(error.message, true); }
}

async function removeConversation(id, title) {
  if (busy || !confirm("¿Quitar la conversación «" + title + "»?")) return;
  try {
    await api("/api/conversations/" + encodeURIComponent(id), { method: "DELETE" });
    if (id === sessionId()) { setSession(newSessionId()); clearChat(); }
    setConvStatus("Conversación quitada.");
  } catch (error) { setConvStatus(error.message, true); }
  loadConversations();
}

// --- arranque ---

function init() {
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (window.mermaid) mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: dark ? "dark" : "default" });
  if (!LIBS_OK || !window.mermaid) setStatus("No se cargaron las librerías de la página (¿sin conexión?). Las respuestas se verán como texto plano.", true);
  if (window.matchMedia("(max-width: 900px)").matches) {
    els.convPanel.open = false;
    els.docsPanel.open = false;
    els.tracePanel.open = false;
  }
  loadDocuments();
  // Si la conversación recordada existe en el servidor, se reabre (sobrevive a recargas y reinicios).
  loadConversations().then((list) => { if (list.some((c) => c.id === sessionId())) openConversation(sessionId()); });
}
init();
