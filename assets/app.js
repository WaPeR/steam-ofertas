const $ = id => document.getElementById(id);
let ofertas = [], lista = [], visibles = 0, cambio = null;
const grid = $('resultados'), mas = $('mas'), contador = $('contador');
const dinero = (n,c) => new Intl.NumberFormat('es-ES',{style:'currency',currency:c}).format(n);
function tarjeta(o){
  const a = document.createElement('article'); a.className='card';
  const link = document.createElement('a'); link.href=`https://store.steampowered.com/app/${encodeURIComponent(o.id)}/?cc=ua`; link.target='_blank'; link.rel='noopener noreferrer';
  const img = document.createElement('img'); img.src=o.imagen; img.alt=o.nombre; img.loading='lazy'; img.onerror=()=>{img.hidden=true;};
  const info=document.createElement('div'); info.className='card-info';
  const h=document.createElement('h2'); h.textContent=o.nombre;
  const p=document.createElement('div'); p.className='precios';
  for(const [clase,texto] of [['descuento',`-${o.descuento}%`],['precio-final',dinero(o.precio_final,'UAH')],['precio-original',dinero(o.precio_original,'UAH')]]){
    const span=document.createElement('span'); span.className=clase; span.textContent=texto; p.append(span);
  }
  const eur=document.createElement('span'); eur.className='equivalente-eur'; eur.dataset.uah=o.precio_final;
  eur.textContent=cambio ? ` ≈ ${dinero(o.precio_final/cambio,'EUR')}` : ' · Conversión no disponible';
  p.append(eur);
  const tienda=document.createElement('span'); tienda.className='tienda'; tienda.textContent='Steam Ucrania · Juego';
  info.append(h,p,tienda); link.append(img,info); a.append(link); return a;
}
function verMas(){
  const siguientes=lista.slice(visibles,visibles+48);
  const fragmento=document.createDocumentFragment(); siguientes.forEach(o=>fragmento.append(tarjeta(o))); grid.append(fragmento);
  visibles+=siguientes.length; mas.hidden=visibles>=lista.length; $('vacio').hidden=lista.length>0;
  contador.textContent=`Mostrando ${visibles} de ${lista.length} resultados · ${ofertas.length} ofertas con descuento ≥50 %`;
}
function filtrar(){
  const texto=$('busqueda').value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  lista=ofertas.filter(o=>o.nombre.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(texto) && (!$('tipo').value || o.tipo===$('tipo').value));
  const orden=$('orden').value;
  lista.sort(orden==='precio' ? (a,b)=>a.precio_final-b.precio_final : orden==='nombre' ? (a,b)=>a.nombre.localeCompare(b.nombre,'es') : (a,b)=>b.descuento-a.descuento || a.nombre.localeCompare(b.nombre,'es'));
  visibles=0; grid.replaceChildren(); verMas();
}
async function cargar(){
  contador.textContent='Cargando ofertas de Ucrania…';
  try{
    const r=await fetch('data/ofertas-ua.json',{cache:'no-cache'});
    if(!r.ok) throw Error();
    const d=await r.json();
    if(d.pais!=='UA' || d.divisa!=='UAH' || !Array.isArray(d.ofertas) || !d.ofertas.length || d.ofertas.some(o=>o.divisa!=='UAH' || !Number.isFinite(o.precio_final) || o.precio_final<0 || !Number.isFinite(o.precio_original) || !/^\d+$/.test(o.id) || typeof o.nombre!=='string')) throw Error();
    ofertas=d.ofertas.filter(o=>o.descuento>=50 && o.tipo==='game');
    $('fecha').textContent=`Ucrania — Ofertas actualizadas: ${new Date(d.actualizado).toLocaleString('es-ES')}`;
    $('aviso').textContent=d.hay_mas ? 'Listado incompleto según la última actualización.' : 'Precios nativos de Steam en UAH. El equivalente en EUR es orientativo y no incluye comisiones.';
    filtrar();
  }catch{
    contador.textContent='Todavía no hay un listado válido en UAH. La actualización puede estar pendiente o haber fallado; no se mostrarán precios USD como UAH.';
    mas.hidden=true; $('vacio').hidden=true;
  }
}
async function cargarCambio(){
  try{
    const r=await fetch('https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=EUR&json',{signal:AbortSignal.timeout(12000)});
    if(!r.ok) throw Error();
    const d=await r.json(), eur=Array.isArray(d) ? d.find(x=>x.cc==='EUR') : null;
    if(!eur || typeof eur.rate!=='number' || !Number.isFinite(eur.rate) || eur.rate<=0) throw Error();
    cambio=eur.rate;
    document.querySelectorAll('[data-uah]').forEach(e=>{e.textContent=` ≈ ${dinero(Number(e.dataset.uah)/cambio,'EUR')}`;});
    $('cambio').textContent='Conversión aproximada con el último tipo oficial disponible del Banco Nacional de Ucrania.';
  }catch{ $('cambio').textContent='Conversión EUR no disponible. Los precios UAH no se modifican.'; }
}
$('busqueda').addEventListener('input',filtrar); $('tipo').addEventListener('change',filtrar); $('orden').addEventListener('change',filtrar); mas.addEventListener('click',verMas);
cargar(); cargarCambio();
