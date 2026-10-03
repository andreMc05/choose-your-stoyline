const $ = (id) => document.getElementById(id);

const roomLabel = $("room-label");
const vitals = $("vitals");
const passage = $("passage");
const flavorEl = $("flavor");
const exitsEl = $("exits");
const endingKind = $("ending-kind");
const sayForm = $("say-form");
const sayInput = $("say-input");
const newBtn = $("new-btn");
const storiesBtn = $("stories-btn");
const ledgerEl = $("ledger");
const readerEl = $("reader");

let play = null;
let screen = "play";

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${path}`);
  }
  return res.json();
}

function hidePlayBits() {
  endingKind.hidden = true;
  passage.hidden = true;
  flavorEl.hidden = true;
  exitsEl.hidden = true;
  ledgerEl.hidden = true;
  readerEl.hidden = true;
  sayForm.classList.add("is-over");
}

function formatWhen(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderVitals(game) {
  const bits = [
    ["HP", game.hp, ""],
    ...game.metrics.map((m) => [m.label, m.value, m.id === "wanted_heat" ? "heat" : ""]),
  ];
  const items = game.inventory.map((i) => i.name).join(", ") || "nothing";
  vitals.hidden = false;
  vitals.innerHTML = bits
    .map(([k, v, cls]) => `<div class="${cls}"><dt>${k}</dt><dd>${v}</dd></div>`)
    .join("");
  vitals.innerHTML += `<div class="inv"><dt>Coat</dt><dd>${items}</dd></div>`;
}

function renderPlay(game) {
  screen = "play";
  play = game;
  storiesBtn.classList.remove("is-on");
  hidePlayBits();
  passage.hidden = false;
  exitsEl.hidden = false;
  renderVitals(game);
  endingKind.hidden = true;
  endingKind.className = "kind";

  if (game.ended && game.ending) {
    roomLabel.textContent = "The tide decides";
    endingKind.hidden = false;
    endingKind.textContent = game.ending.kind;
    endingKind.classList.add(game.ending.kind);
    passage.textContent = game.ending.passage;
    flavorEl.hidden = true;
    exitsEl.innerHTML = "";
    const read = document.createElement("button");
    read.type = "button";
    read.dataset.n = "1";
    read.textContent = "Read the story";
    read.addEventListener("click", () => openReader("current"));
    exitsEl.appendChild(read);
    sayForm.classList.add("is-over");
    return;
  }

  sayForm.classList.remove("is-over");
  roomLabel.textContent = game.node ? game.node.title : game.title;
  passage.textContent = game.node ? game.node.passage : "";

  if (game.flavor) {
    flavorEl.hidden = false;
    flavorEl.textContent = game.flavor;
  } else {
    flavorEl.hidden = true;
    flavorEl.textContent = "";
  }

  exitsEl.innerHTML = "";
  (game.exits || []).forEach((exit, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.n = String(i + 1);
    btn.textContent = exit.label;
    btn.addEventListener("click", () => submit(exit.label, "button"));
    exitsEl.appendChild(btn);
  });
}

function renderLedger(payload) {
  screen = "ledger";
  storiesBtn.classList.add("is-on");
  hidePlayBits();
  vitals.hidden = true;
  roomLabel.textContent = "Other nights";
  const stories = payload.stories || [];
  if (!stories.length) {
    ledgerEl.hidden = false;
    ledgerEl.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No finished nights yet. End a run, then it will wait here.";
    passage.hidden = false;
    passage.textContent = empty.textContent;
    return;
  }
  ledgerEl.hidden = false;
  ledgerEl.innerHTML = "";
  stories.forEach((row) => {
    const item = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    const kind = row.ending_kind || "unfinished";
    btn.innerHTML = `<span>${row.title}</span><span class="meta">${kind} · ${row.turn} turns · ${formatWhen(row.updated_at)}</span>`;
    btn.addEventListener("click", () => openReader(row.id));
    item.appendChild(btn);
    ledgerEl.appendChild(item);
  });
}

function renderReader(story) {
  screen = "reader";
  storiesBtn.classList.add("is-on");
  hidePlayBits();
  vitals.hidden = true;
  readerEl.hidden = false;
  const kind = story.ending ? story.ending.kind : "";
  roomLabel.textContent = story.title || "The story";
  endingKind.hidden = !kind;
  endingKind.className = "kind";
  if (kind) {
    endingKind.textContent = kind;
    endingKind.classList.add(kind);
  }
  readerEl.innerHTML = "";
  (story.entries || []).forEach((entry) => {
    const p = document.createElement("p");
    p.className = entry.kind === "action" ? "action" : "passage";
    p.textContent = entry.text;
    readerEl.appendChild(p);
  });
  if (!story.entries || !story.entries.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "This night left no pages.";
    readerEl.appendChild(empty);
  }
}

async function load() {
  renderPlay(await api("/api/game"));
}

async function submit(text, kind) {
  renderPlay(await api("/api/turn", {
    method: "POST",
    body: JSON.stringify({ text, kind }),
  }));
}

async function openLedger() {
  renderLedger(await api("/api/stories"));
}

async function openReader(id) {
  renderReader(await api(`/api/stories/${id}`));
}

sayForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = sayInput.value.trim();
  if (!text) return;
  sayInput.value = "";
  submit(text, "text");
});

storiesBtn.addEventListener("click", async () => {
  if (screen === "ledger") {
    if (play) renderPlay(play);
    else await load();
    return;
  }
  await openLedger();
});

newBtn.addEventListener("click", async () => {
  if (newBtn.dataset.sure !== "1") {
    newBtn.dataset.sure = "1";
    newBtn.textContent = "Sure?";
    return;
  }
  newBtn.dataset.sure = "";
  newBtn.textContent = "New game";
  renderPlay(await api("/api/new", { method: "POST", body: "{}" }));
  sayInput.focus();
});

load().catch((err) => {
  passage.textContent = `Could not reach the game (${err.message}). Is web.py running?`;
});
