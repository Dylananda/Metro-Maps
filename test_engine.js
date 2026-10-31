const {createEngine}=require('./engine.js');
const D=JSON.parse(require('fs').readFileSync('data/network.json','utf8'));
const E=createEngine(D);
const poi=n=>{const p=D.pois.find(p=>p[0].toLowerCase().includes(n.toLowerCase()));if(!p)throw n;return {lat:p[2],lon:p[3],label:p[0]}};
const posTxt={front:'parte DELANTERA',back:'parte TRASERA',middle:'CENTRO'};
function show(a,b,opt){
  const A=poi(a),B=poi(b); const r=E.route(A,B,opt);
  console.log(`\n=== ${A.label} -> ${B.label} ${JSON.stringify(opt||{})}  total ${r.total.toFixed(0)} min`);
  for(const L of r.legs){
    if(L.type==='walk') console.log(` camina ${L.m|0} m`);
    if(L.type==='enter') console.log(` entra por "${L.ent?L.ent.name:'(sin datos)'}" ${L.ent&&L.ent.lift?'[ascensor]':''} a ${L.station.name} (${L.m|0} m)`);
    if(L.type==='ride') console.log(` ${L.line.ref} dir. ${L.p.to}: ${L.from.name} -> ${L.to.name} (${L.nStops} paradas, ${L.min.toFixed(1)} min) pos=${L.position&&posTxt[L.position.zone]} off=${L.position&&L.position.off.toFixed(0)} (${L.position&&L.position.why})`);
    if(L.type==='transfer') console.log(` transbordo ${L.from.name} -> ${L.to.name} ${L.m}m ${L.street?'POR LA CALLE '+(L.exitEnt&&L.exitEnt.name)+' -> '+(L.enterEnt&&L.enterEnt.name):'interior'}`);
    if(L.type==='exit') console.log(` sal por "${L.ent?L.ent.name:'(sin datos)'}" de ${L.station.name}, ${L.m|0} m al destino`);
  }
  r.notes.forEach(n=>console.log('  nota:',n.k));
}
show('Sagrada Fam','Museu Nacional d');
show('Parc Güell','Platja de la Barceloneta');
show('Spotify Camp Nou','Basílica');
show('T2B','Casa Batlló');
show('Hospital Clínic','Hospital de la Santa Creu i Sant Pau');
show('Sagrada Fam','Museu Nacional d',{accessible:true});
show('Atraccions Tibidabo','Font Màgica');
show('Casa Batlló','Platja del Bogatell');
show('Spotify Camp Nou','Platja de la Barceloneta');
show('Spotify Camp Nou','Basílica de la Sagrada');
