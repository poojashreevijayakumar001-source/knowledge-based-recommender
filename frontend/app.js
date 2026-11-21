(function () {
  "use strict";

  // When opened straight from disk, talk to the local backend.
  const API = location.protocol === "file:" ? "http://localhost:8000" : "";
  const $ = (id) => document.getElementById(id);

  const state = { meta: null, knowledge: null, category: null, useCases: new Set(), excluded: new Set() };
  let currency = "INR";

  const fmt = (n) => new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(n);

  function el(tag, props, children) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v);
    });
    (children || []).forEach((c) => node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return node;
  }

  async function api(path, body) {
    const res = await fetch(API + path, body
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : undefined);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
  }

  function chip(label, pressed, onClick, extra) {
    const b = el("button", { type: "button", class: "chip " + (extra || ""), "aria-pressed": String(pressed), text: label });
    b.addEventListener("click", () => {
      const now = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(now));
      onClick(now);
    });
    return b;
  }

  function renderCategories() {
    const box = $("categories");
    box.innerHTML = "";
    Object.entries(state.meta.categories).forEach(([key, cat]) => {
      const b = el("button", { type: "button", class: "chip", role: "radio", "aria-checked": "false", text: cat.label });
      b.addEventListener("click", () => selectCategory(key));
      b.dataset.key = key;
      box.appendChild(b);
    });
  }

  function selectCategory(key) {
    state.category = key;
    state.useCases.clear();
    state.excluded.clear();
    document.querySelectorAll("#categories .chip").forEach((b) =>
      b.setAttribute("aria-checked", String(b.dataset.key === key)));

    const cat = state.meta.categories[key];
    $("steps").hidden = false;

    const slider = $("budget");
    const step = cat.max_price > 50000 ? 1000 : 500;
    slider.min = Math.floor(cat.min_price / step) * step;
    slider.max = Math.ceil(cat.max_price / step) * step;
    slider.step = step;
    slider.value = slider.max;
    $("minPrice").textContent = fmt(slider.min);
    $("maxPrice").textContent = fmt(slider.max);
    updateBudget();

    const uc = $("useCases");
    uc.innerHTML = "";
    cat.use_cases.forEach((u) =>
      uc.appendChild(chip(u.label, false, (on) => {
        on ? state.useCases.add(u.id) : state.useCases.delete(u.id);
        const picked = cat.use_cases.filter((x) => state.useCases.has(x.id)).map((x) => x.description);
        $("useCaseHint").textContent = picked.join(" ");
      })));
    $("useCaseHint").textContent = "Skip this and we'll rank by rating and popularity.";

    const br = $("brands");
    br.innerHTML = "";
    cat.brands.forEach((b) =>
      br.appendChild(chip(b, false, (on) => (on ? state.excluded.add(b) : state.excluded.delete(b)), "exclude")));

    $("output").hidden = true;
    $("intro").hidden = false;
    renderKnowledge();
  }

  function updateBudget() {
    $("budgetValue").textContent = fmt(Number($("budget").value));
  }

  function renderKnowledge() {
    const cat = state.knowledge.categories[state.category];
    const body = $("kbBody");
    body.innerHTML = "";
    Object.values(cat.use_cases).forEach((u) => {
      body.appendChild(el("h5", { text: u.label }));
      const tbody = el("tbody");
      u.rules.forEach((r) =>
        tbody.appendChild(el("tr", {}, [
          el("td", { text: r.reason }),
          el("td", { text: "weight " + r.weight }),
          el("td", { text: r.hard ? "must-have" : "preferred" }),
        ])));
      body.appendChild(el("table", {}, [tbody]));
    });
    $("kb").hidden = false;
  }

  function specLabel(k, v) {
    const name = k.replace(/_/g, " ");
    if (v === true) return name;
    if (v === false) return "no " + name;
    return name + ": " + v;
  }

  function renderResults(resp) {
    $("intro").hidden = true;
    $("output").hidden = false;

    const banner = $("banner");
    banner.innerHTML = "";
    if (resp.relaxations.length) {
      banner.hidden = false;
      banner.appendChild(el("strong", { text: resp.results.length
        ? "Nothing matched exactly, so we relaxed your constraints:"
        : "Nothing matched, even after relaxing:" }));
      banner.appendChild(el("ul", {}, resp.relaxations.map((t) => el("li", { text: t }))));
    } else {
      banner.hidden = true;
    }

    const t = resp.trace;
    const trace = $("trace");
    trace.innerHTML = "";
    [["In category", t.in_category], ["Within budget", t.after_budget], ["Brands OK", t.after_brands], ["Must-haves met", t.after_must_haves]]
      .forEach(([label, n], i) => {
        if (i) trace.appendChild(document.createTextNode("→"));
        trace.appendChild(el("span", { class: "step", text: label + ": " + n }));
      });

    const list = $("list");
    list.innerHTML = "";
    if (!resp.results.length) {
      list.appendChild(el("p", { class: "error", text: resp.message || "No matches found." }));
      return;
    }
    list.appendChild(el("p", { class: "hint", text: resp.strategy }));

    resp.results.forEach((r, i) => {
      const p = r.product;
      const specs = el("div", { class: "specs" },
        Object.entries(p.specs).slice(0, 8).map(([k, v]) => el("span", { class: "spec", text: specLabel(k, v) })));

      const meterText = r.need_match === null ? "Ranked by rating & popularity" : r.need_match + "% match to your needs";
      const meterWidth = r.need_match === null ? r.score : r.need_match;

      const card = el("article", { class: "card" }, [
        el("div", { class: "card-head" }, [
          el("div", {}, [
            el("div", { class: "rank", text: "#" + (i + 1) + " pick" }),
            el("h3", { text: p.name }),
            el("div", { class: "brand", text: p.brand }),
          ]),
          el("div", {}, [
            el("div", { class: "price", text: fmt(p.price) }),
            el("div", { class: "rating", text: "★ " + p.rating.toFixed(1) }),
          ]),
        ]),
        el("div", { class: "meter" }, [
          el("div", { class: "bar" }, [el("i", { style: "width:" + meterWidth + "%" })]),
          el("small", { text: meterText }),
        ]),
        specs,
      ]);

      if (r.why.length) {
        card.appendChild(el("div", { class: "why" }, [
          el("h4", { text: "Why it was recommended" }),
          el("ul", {}, r.why.map((w) => el("li", { text: w.text }))),
        ]));
      }
      if (r.tradeoffs.length) {
        card.appendChild(el("div", { class: "trade" }, [
          el("h4", { text: "Trade-offs" }),
          el("ul", {}, r.tradeoffs.map((w) => el("li", { text: w.text }))),
        ]));
      }
      list.appendChild(card);
    });
  }

  async function recommend() {
    const btn = $("go");
    btn.disabled = true;
    btn.textContent = "Thinking…";
    try {
      const resp = await api("/api/recommend", {
        category: state.category,
        budget_max: Number($("budget").value),
        use_cases: [...state.useCases],
        exclude_brands: [...state.excluded],
        top_n: 5,
      });
      renderResults(resp);
    } catch (e) {
      $("intro").hidden = true;
      $("output").hidden = false;
      $("banner").hidden = true;
      $("trace").innerHTML = "";
      $("list").innerHTML = "";
      $("list").appendChild(el("p", { class: "error", text: "Could not get recommendations: " + e.message +
        ". Is the backend running (python3 backend/server.py)?" }));
    } finally {
      btn.disabled = false;
      btn.textContent = "Recommend products";
    }
  }

  async function init() {
    try {
      [state.meta, state.knowledge] = await Promise.all([api("/api/meta"), api("/api/knowledge")]);
      currency = state.meta.currency;
      renderCategories();
      $("budget").addEventListener("input", updateBudget);
      $("go").addEventListener("click", recommend);
    } catch (e) {
      $("categories").appendChild(el("p", { class: "error", text: "Backend not reachable. Start it with: python3 backend/server.py" }));
    }
  }

  init();
})();
