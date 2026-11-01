// Pruebas de caminos interiores: node test_indoor.js
const fs = require("fs");
const D = JSON.parse(fs.readFileSync("data/network.json", "utf8"));
const PL = JSON.parse(fs.readFileSync("data/indoor.json", "utf8"));
const E = require("./engine.js").createEngine(D);
const I = require("./indoor.js").create(PL);
const P = I.plans[0];
const pat = (ref, to) => D.patterns.find((p) => E.lines[p.line].ref === ref && p.to.startsWith(to));
const show = (title, r) => console.log(title.padEnd(48), r ? `${Math.round(r.m)} m | ${I.describe(r)}` : "SIN CAMINO");
console.log("Plano:", P.name, "| estaciones", P.sids.join(","));
for (const e of P.ents) {
  show(`Boca ${e.name} (${e.id}) → L3 Zona Univ.`, I.enterToPlatform(P, e.id, pat("L3", "Zona").id));
}
show("L3 Zona Univ. → L4 La Pau", I.platformToPlatform(P, pat("L3", "Zona").id, pat("L4", "La Pau").id));
show("L4 La Pau → L2 Badalona", I.platformToPlatform(P, pat("L4", "La Pau").id, pat("L2", "Badalona").id));
show("Rodalies R2N Aeroport → L3 Trinitat", I.platformToPlatform(P, pat("R2N", "Aeroport").id, pat("L3", "Trinitat").id));
show("L2 Paral·lel → boca Passeig de Gràcia / Gran Via", I.platformToExit(P, pat("L2", "Paral").id, P.ents.find((e) => e.name === "Passeig de Gràcia / Gran Via").id));
show("L3 Zona Univ. → boca Aragó/València (sin escaleras)", I.platformToExit(P, pat("L3", "Zona").id, P.ents.find((e) => e.name === "Aragó / València").id, { accessible: true }));
