// Caminos por dentro de las estaciones con plano (data/indoor.json).
// Funciona en el navegador (global MetroIndoor) y en Node para poder probarlo.
(function (root) {
  "use strict";

  const K = { corridor: 0, steps: 1, elevator: 2, platform: 3, gap: 4 };

  function dist(a, b) {
    const la = ((a[0] + b[0]) / 2) * Math.PI / 180;
    return Math.hypot((b[1] - a[1]) * 111320 * Math.cos(la), (b[0] - a[0]) * 110540);
  }

  function create(PLANS) {
    const plans = Object.values(PLANS || {});
    plans.forEach((P) => {
      P.adj = P.nodes.map(() => []);
      P.edges.forEach(([a, b, k]) => {
        const m = dist(P.nodes[a], P.nodes[b]);
        P.adj[a].push([b, m, k]); P.adj[b].push([a, m, k]);
      });
      P.entIndex = new Map(P.ents.map((e) => [e.id, e]));
    });

    const planFor = (sid) => plans.find((P) => P.sids.includes(sid)) || null;
    const platformFor = (P, patId) => P.platforms.find((p) => p.pats.includes(patId)) || null;

    // Dijkstra de varios orígenes a varios destinos. Con «accessible», las escaleras casi se prohíben.
    function shortest(P, from, to, opt = {}) {
      const target = new Set(to);
      const d = new Float64Array(P.nodes.length).fill(Infinity);
      const prev = new Int32Array(P.nodes.length).fill(-1);
      const pk = new Int8Array(P.nodes.length).fill(-1);
      const open = [];
      from.forEach((i) => { d[i] = 0; open.push(i); });
      const done = new Uint8Array(P.nodes.length);
      while (open.length) {
        let bi = 0;
        for (let i = 1; i < open.length; i++) if (d[open[i]] < d[open[bi]]) bi = i;
        const u = open.splice(bi, 1)[0];
        if (done[u]) continue;
        done[u] = 1;
        if (target.has(u)) {
          const nodes = [], kinds = [];
          for (let v = u; v !== -1; v = prev[v]) { nodes.push(v); if (pk[v] !== -1) kinds.push(pk[v]); }
          nodes.reverse(); kinds.reverse();
          return summarize(P, nodes, kinds);
        }
        for (const [v, m, k] of P.adj[u]) {
          const w = m * (k === K.steps ? (opt.accessible ? 60 : 1.4) : k === K.gap ? 1.3 : 1) + (k === K.elevator ? 20 : 0);
          if (d[u] + w < d[v]) { d[v] = d[u] + w; prev[v] = u; pk[v] = k; open.push(v); }
        }
      }
      return null;
    }

    // Convierte el camino en tramos legibles: pasillo, escaleras, ascensor, andén.
    function summarize(P, nodes, kinds) {
      const segs = [];
      let m = 0;
      for (let i = 1; i < nodes.length; i++) {
        const len = dist(P.nodes[nodes[i - 1]], P.nodes[nodes[i]]);
        m += len;
        let k = kinds[i - 1];
        if (k === K.gap) k = K.corridor;
        const last = segs[segs.length - 1];
        if (last && last.k === k) { last.m += len; last.to = nodes[i]; }
        else segs.push({ k, m: len, from: nodes[i - 1], to: nodes[i] });
      }
      segs.forEach((s) => {
        const a = P.nodes[s.from][2], b = P.nodes[s.to][2];
        if (a != null && b != null && a !== b) s.dir = b < a ? "baja" : "sube";
        s.lvl = b != null ? b : a;
      });
      return { nodes, segs: segs.filter((s) => s.m > 3 || s.k !== K.corridor), m };
    }

    const platNodes = (p) => p.n;

    function enterToPlatform(P, entId, patId, opt) {
      const e = P.entIndex.get(entId), p = platformFor(P, patId);
      if (!e || !p) return null;
      const r = shortest(P, [e.i], platNodes(p), opt);
      return r && { ...r, plan: P, start: { type: "ent", ent: e }, end: { type: "platform", platform: p } };
    }
    function platformToExit(P, patId, entId, opt) {
      const e = P.entIndex.get(entId), p = platformFor(P, patId);
      if (!e || !p) return null;
      const r = shortest(P, platNodes(p), [e.i], opt);
      return r && { ...r, plan: P, start: { type: "platform", platform: p }, end: { type: "ent", ent: e } };
    }
    function platformToPlatform(P, patA, patB, opt) {
      const a = platformFor(P, patA), b = platformFor(P, patB);
      if (!a || !b) return null;
      if (a === b) return { nodes: [], segs: [], m: 0, plan: P, same: true, start: { type: "platform", platform: a }, end: { type: "platform", platform: b } };
      const r = shortest(P, platNodes(a), platNodes(b), opt);
      return r && { ...r, plan: P, start: { type: "platform", platform: a }, end: { type: "platform", platform: b } };
    }

    // Texto corto: «pasillo 60 m · escaleras (bajan) · pasillo 40 m»
    function describe(path) {
      if (path.same) return "Mismo andén: espera el otro tren aquí.";
      const merged = [];
      path.segs.filter((s) => s.k !== K.platform).forEach((s) => {
        const last = merged[merged.length - 1];
        if (last && last.k === s.k) { last.m += s.m; last.dir = last.dir || s.dir; } else merged.push({ ...s });
      });
      return merged.map((s) => {
        if (s.k === K.steps) return "escaleras" + (s.dir ? (s.dir === "baja" ? " (bajan)" : " (suben)") : "");
        if (s.k === K.elevator) return "ascensor";
        return "pasillo " + Math.max(10, Math.round(s.m / 10) * 10) + " m";
      }).join(" · ");
    }

    return { plans, planFor, platformFor, enterToPlatform, platformToExit, platformToPlatform, describe, K };
  }

  const api = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MetroIndoor = api;
})(typeof window !== "undefined" ? window : globalThis);
