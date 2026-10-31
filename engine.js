// Motor de rutas de Metro Maps BCN.
// Funciona en el navegador (global MetroEngine) y en Node (module.exports) para poder probarlo.
(function (root) {
  "use strict";

  const WALK = 75;        // m/min caminando
  const DETOUR = 1.3;     // la calle nunca es línea recta
  const BOARD_PENALTY = 1.5; // min extra por cada subida a un tren (preferir menos transbordos)
  const TRAIN_LEN = { metro: 95, fgc: 75, rodalies: 160, funicular: 30 };

  function dist(a, b) {
    const la = ((a.lat + b.lat) / 2) * Math.PI / 180;
    const dx = (b.lon - a.lon) * 111320 * Math.cos(la);
    const dy = (b.lat - a.lat) * 110540;
    return Math.hypot(dx, dy);
  }
  function vec(a, b) {
    const la = ((a.lat + b.lat) / 2) * Math.PI / 180;
    return [(b.lon - a.lon) * 111320 * Math.cos(la), (b.lat - a.lat) * 110540];
  }
  const walkMin = (m) => (m * DETOUR) / WALK;

  // Montículo binario mínimo para Dijkstra.
  class Heap {
    constructor() { this.a = []; }
    push(k, v) {
      const a = this.a; a.push([k, v]); let i = a.length - 1;
      while (i > 0) { const p = (i - 1) >> 1; if (a[p][0] <= a[i][0]) break; [a[p], a[i]] = [a[i], a[p]]; i = p; }
    }
    pop() {
      const a = this.a, top = a[0], last = a.pop();
      if (a.length) {
        a[0] = last; let i = 0;
        for (;;) {
          const l = 2 * i + 1, r = l + 1; let m = i;
          if (l < a.length && a[l][0] < a[m][0]) m = l;
          if (r < a.length && a[r][0] < a[m][0]) m = r;
          if (m === i) break; [a[m], a[i]] = [a[i], a[m]]; i = m;
        }
      }
      return top;
    }
    get size() { return this.a.length; }
  }

  function createEngine(D) {
    const lines = {};
    D.lines.forEach((l) => { lines[l.id] = l; });
    const stations = {};
    D.stations.forEach((s, i) => {
      stations[s.id] = s; s.idx = i; s.ents = []; s.xfers = []; s.lineSet = new Set(); s.pats = [];
    });
    D.entrances.forEach((e) => e.s.forEach((sid) => stations[sid] && stations[sid].ents.push(e)));
    D.patterns.forEach((p) => {
      p.L = lines[p.line];
      p.stops = p.seq.map(([sid, lat, lon, role]) => ({ sid, lat, lon, role }));
      p.stops.forEach((x, i) => { const s = stations[x.sid]; s.lineSet.add(p.line); s.pats.push([p, i]); });
    });
    D.stations.forEach((s) => {
      s.lines = [...s.lineSet].map((id) => lines[id]).sort(lineOrder);
    });
    D.transfers.forEach(([a, b, min, m, same]) => {
      stations[a].xfers.push({ to: b, min, m, same: !!same });
      stations[b].xfers.push({ to: a, min, m, same: !!same });
    });

    function lineOrder(a, b) {
      const rank = { metro: 0, funicular: 1, fgc: 2, rodalies: 3 };
      if (rank[a.mode] !== rank[b.mode]) return rank[a.mode] - rank[b.mode];
      return a.ref.localeCompare(b.ref, "es", { numeric: true });
    }

    const nS = D.stations.length;
    const pOffset = [];
    let nP = 0;
    D.patterns.forEach((p, k) => { p.k = k; pOffset.push(nS + nP); nP += p.stops.length; });
    const N = nS + nP, O = N, T = N + 1;

    const insideMin = (s, e) => (s.modes.includes("rodalies") ? 2 : 1.5) + (e && e.lift ? 0.5 : 0);
    const accessOK = (e, opt) => !opt.accessible || e.wc === 1 || e.lift;

    // Mejor boca para entrar/salir de la estación s desde/hacia el punto pt.
    function bestAccess(s, pt, opt) {
      let best = null;
      for (const e of s.ents) {
        if (!accessOK(e, opt)) continue;
        const m = dist(pt, e);
        const min = walkMin(m) + insideMin(s, e);
        if (!best || min < best.min) best = { ent: e, m, min };
      }
      if (best) return best;
      if (s.ents.length && opt.accessible) return null; // tiene bocas pero ninguna accesible
      const m = dist(pt, s);
      return { ent: null, m, min: walkMin(m) + insideMin(s, null) + 1 };
    }

    function modeAllowed(p, opt) {
      const m = p.L.mode === "funicular" ? "metro" : p.L.mode;
      return !opt.modes || opt.modes.includes(m);
    }

    function accessEdges(pt, opt) {
      // Estaciones alcanzables a pie; si no hay ninguna cerca, ampliamos el radio.
      for (const R of [1100, 2000, 3500]) {
        const out = [];
        for (const s of D.stations) {
          if (!s.pats.some(([p]) => modeAllowed(p, opt))) continue;
          if (dist(pt, s) > R) continue;
          const a = pt.sids && pt.sids.includes(s.id)
            ? { ent: null, m: 0, min: 0, here: true }
            : bestAccess(s, pt, opt);
          if (a) out.push([s, a]);
        }
        if (out.length) return out;
      }
      return [];
    }

    function route(from, to, opt = {}) {
      opt = { accessible: false, modes: null, ...opt };
      const dist0 = new Float64Array(N + 2).fill(Infinity);
      const prev = new Int32Array(N + 2).fill(-1);
      const how = new Array(N + 2);
      const heap = new Heap();
      const relax = (u, v, c, info) => {
        const nd = dist0[u] + c;
        if (nd < dist0[v] - 1e-9) { dist0[v] = nd; prev[v] = u; how[v] = info; heap.push(nd, v); }
      };

      const outEdges = new Map();
      accessEdges(to, opt).forEach(([s, a]) => outEdges.set(s.idx, a));

      dist0[O] = 0; heap.push(0, O);
      const direct = dist(from, to);
      while (heap.size) {
        const [d, u] = heap.pop();
        if (d > dist0[u]) continue;
        if (u === T) break;
        if (u === O) {
          relax(O, T, walkMin(direct), { t: "walk", m: direct });
          for (const [s, a] of accessEdges(from, opt)) relax(O, s.idx, a.min, { t: "in", s, a });
          continue;
        }
        if (u < nS) {
          const s = D.stations[u];
          for (const [p, i] of s.pats) {
            if (!modeAllowed(p, opt) || i === p.stops.length - 1 || p.stops[i].role === 2) continue;
            relax(u, pOffset[p.k] + i, p.hw / 2 + BOARD_PENALTY, { t: "board", p, i });
          }
          for (const x of s.xfers) relax(u, stations[x.to].idx, x.min + 0.5, { t: "xfer", x, s });
          const a = outEdges.get(u);
          if (a) relax(u, T, a.min, { t: "out", s, a });
          continue;
        }
        // nodo de tren: (patrón, parada)
        const pi = findPattern(u);
        const p = D.patterns[pi], i = u - pOffset[pi];
        if (i + 1 < p.stops.length) {
          const m = dist(p.stops[i], p.stops[i + 1]);
          relax(u, u + 1, m / D.speed[p.L.mode] + D.dwell, { t: "ride", p, i, m });
        }
        if (p.stops[i].role !== 1) relax(u, stations[p.stops[i].sid].idx, 0, { t: "alight", p, i });
      }
      if (!isFinite(dist0[T])) return null;

      const path = [];
      for (let v = T; v !== O; v = prev[v]) path.push(how[v]);
      path.reverse();
      return buildLegs(path, from, to, dist0[T], opt);
    }

    function findPattern(u) {
      let lo = 0, hi = pOffset.length - 1;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (pOffset[mid] <= u) lo = mid; else hi = mid - 1; }
      return lo;
    }

    function buildLegs(path, from, to, total, opt) {
      const legs = [];
      let ride = null;
      for (const h of path) {
        if (h.t === "walk") legs.push({ type: "walk", m: h.m, min: walkMin(h.m) });
        else if (h.t === "in") legs.push({ type: "enter", station: h.s, ent: h.a.ent, m: h.a.m, min: h.a.min, here: !!h.a.here });
        else if (h.t === "board") ride = { type: "ride", p: h.p, line: h.p.L, i: h.i, j: h.i, wait: h.p.hw / 2, min: 0 };
        else if (h.t === "ride") { ride.j = h.i + 1; ride.min += h.m / D.speed[h.p.L.mode] + D.dwell; }
        else if (h.t === "alight") { if (ride) { legs.push(ride); ride = null; } }
        else if (h.t === "xfer") legs.push({ type: "transfer", from: h.s, to: stations[h.x.to], min: h.x.min, m: h.x.m, same: h.x.same });
        else if (h.t === "out") legs.push({ type: "exit", station: h.s, ent: h.a.ent, m: h.a.m, min: h.a.min, here: !!h.a.here });
      }
      // Bajar y volver a subir en la misma estación al mismo tren no aporta nada: ya lo evita la penalización.
      legs.forEach((L, k) => {
        if (L.type !== "ride") return;
        L.from = stations[L.p.stops[L.i].sid];
        L.to = stations[L.p.stops[L.j].sid];
        L.stopsBetween = L.p.stops.slice(L.i + 1, L.j).map((x) => stations[x.sid]);
        L.nStops = L.j - L.i;
        L.position = trainPosition(L, legs[k + 1], legs[k + 2], to);
      });
      legs.forEach((L) => {
        if (L.type !== "transfer") return;
        L.street = !L.same;
        if (L.street) {
          L.exitEnt = nearestEnt(L.from, L.to, opt);
          L.enterEnt = nearestEnt(L.to, L.exitEnt || L.from, opt);
        }
      });
      const rides = legs.filter((l) => l.type === "ride");
      return { legs, total, rides: rides.length, notes: notesFor(legs, rides) };
    }

    function nearestEnt(s, pt, opt) {
      let best = null;
      for (const e of s.ents) {
        if (!accessOK(e, opt)) continue;
        const m = dist(pt, e);
        if (!best || m < best.m) best = { e, m };
      }
      return best ? best.e : null;
    }

    // ¿En qué parte del tren conviene ir para quedar cerca de la salida o del transbordo?
    function trainPosition(L, next, next2, dest) {
      const stops = L.p.stops, j = L.j;
      const here = stops[j];
      const before = stops[j - 1];
      let target = null, why = "";
      if (next && next.type === "exit") { target = next.ent || dest; why = next.ent ? "salida" : "destino"; }
      else if (next && next.type === "transfer") {
        if (next.street) { target = next.exitEnt || next.to; why = "salida"; }
        else if (next2 && next2.type === "ride") { target = next2.p.stops[next2.i]; why = "transbordo"; }
        else { target = next.to; why = "transbordo"; }
      } else if (next && next.type === "ride") { target = next.p.stops[next.i]; why = "transbordo"; }
      if (!target || !before) return null;
      const dir = vec(before, here);
      const len = Math.hypot(dir[0], dir[1]) || 1;
      const t = vec(here, target);
      const off = (t[0] * dir[0] + t[1] * dir[1]) / len;   // metros hacia delante (+) o atrás (−)
      const half = TRAIN_LEN[L.line.mode] / 2;
      const rel = Math.max(-1, Math.min(1, off / half));
      const zone = rel > 0.3 ? "front" : rel < -0.3 ? "back" : "middle";
      return { zone, rel, off, why };
    }

    function notesFor(legs, rides) {
      const notes = [];
      const names = new Set();
      rides.forEach((r) => r.p.stops.slice(r.i, r.j + 1).forEach((x) => names.add(stations[x.sid].name)));
      if (rides.some((r) => r.line.ref === "L9S") && [...names].some((n) => /^Aeroport T[12]$/.test(n))) {
        notes.push({ k: "ticket", text: "Las estaciones Aeroport T1 y T2 de la L9 Sud necesitan el billete Aeroport: la T-casual no sirve para entrar ni salir. El tren R2 Nord de Rodalies sí acepta los billetes integrados." });
      }
      if (rides.length > 1) {
        notes.push({ k: "ticket", text: "Con un billete integrado (T-casual, T-usual, T-jove…) los transbordos están incluidos: hasta 3 transbordos en 1 h 15 min. Valida el billete al entrar en cada red." });
      }
      if (legs.some((l) => l.type === "transfer" && l.street)) {
        notes.push({ k: "street", text: "Algún transbordo se hace por la calle: no hay pasillo interior entre esas estaciones (según los datos disponibles)." });
      }
      const ops = new Set(rides.map((r) => r.line.op));
      if (ops.size > 1) notes.push({ k: "ops", text: "El trayecto combina operadores (" + [...ops].join(", ") + "). Las señales de cada red son distintas: busca el logotipo de la red además del número de línea." });
      const far = rides.some((r) => r.p.stops.slice(r.i, r.j + 1).some((x) => dist(x, { lat: 41.387, lon: 2.17 }) > 14000));
      if (far && rides.some((r) => r.line.mode !== "metro")) notes.push({ k: "zones", text: "Parte del trayecto sale de la zona 1: comprueba que tu billete cubre las zonas necesarias." });
      if (rides.some((r) => r.line.mode === "metro" && r.line.op === "TMB")) {
        notes.push({ k: "hours", text: "Horario del metro: de domingo a jueves de 5:00 a 24:00; viernes y vísperas de festivo hasta las 2:00; el sábado funciona toda la noche." });
      }
      return notes;
    }

    return { route, stations, lines, dist, walkMin };
  }

  const api = { createEngine };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MetroEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
