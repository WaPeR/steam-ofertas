const $ = id => document.getElementById(id);
const resultados = $('resultados'), busqueda = $('busqueda'), region = $('region');
const orden = $('orden'), solo = $('soloOfertas'), vacio = $('vacio');
const BLOQUE = 48;
let ofertas = [], filtradas = [], mostradas = 0, divisa = 'EUR', peticion = 0;
region.replaceChildren(...[['es', 'España (EUR)'], ['ua', 'Ucrania (UAH)']].map(([v, t]) => new Option(t, v)));
region.value = 'es';
const tipo = document.createElement('select');
tipo.id = 'tipo';
tipo.setAttribute('aria-label', 'Tipo de producto');
region.after(tipo);
const contador = document.createElement('p');
contador.setAttribute('role', 'status');
resultados.before(contador);
const mas = document.createElement('button');
mas.type = 'button';
mas.textContent = 'Ver más';
mas.hidden = true;
mas.style.cssText = 'display:block;margin:1.5rem auto;padding:.8rem 2rem;border-radius:8px;cursor:pointer;background:#66c0f4;border:0;color:#101820;font:inherit';
const estilo = document.createElement('style');
estilo.textContent = '[hidden]{display:none!important}';
document.head.append(estilo);
resultados.after(mas);
const normal = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const categoria = o => typeof o.tipo === 'string' && o.tipo.trim() ? o.tipo.trim().toLowerCase() : '__sin_tipo';
const etiquetas = {game:'Juegos', dlc:'DLC / expansiones', expansion:'Expansiones', soundtrack:'Bandas sonoras', bundle:'Packs', package:'Paquetes', '__sin_tipo':'Sin clasificar'};
function tipos(){
  tipo.replaceChildren(new Option('Todos los tipos', ''));
  [...new Set(ofertas.map(categoria))].sort().forEach(t => tipo.add(new Option(etiquetas[t] || `Tipo ITAD: ${t}`, t)));
}
function precio(n){
  return new Intl.NumberFormat('es-ES', {style:'currency', currency:divisa}).format(n);
}
function tarjeta(o){
  const a = document.createElement('article'); a.className = 'card';
  const link = document.createElement('a');
  try {
    const url = new URL(o.url || o.url_steam);
    if(url.protocol === 'https:') link.href = url.href;
  } catch {}
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  if(o.imagen){
    const img = document.createElement('img'); img.src = o.imagen;
    img.alt = `Portada de ${o.nombre}`; img.loading = 'lazy';
    img.addEventListener('error', () => { img.hidden = true; });
    link.append(img);
  }
  const info = document.createElement('div'); info.className = 'card-info';
  const h = document.createElement('h2'); h.textContent = o.nombre;
  const p = document.createElement('div'); p.className = 'precios';
  for(const [clase, texto] of [['descuento', `-${o.descuento}%`], ['precio-final', precio(o.precio_final)], ['precio-original', precio(o.precio_original)]]){
    const span = document.createElement('span'); span.className = clase; span.textContent = texto; p.append(span);
  }
  const meta = document.createElement('span'); meta.className = 'tienda';
  meta.textContent = `Steam · ${etiquetas[categoria(o)] || categoria(o)}`;
  info.append(h,p,meta); link.append(info); a.append(link); return a;
}
function actualizarContador(){
  contador.textContent = `Mostrando ${mostradas} de ${filtradas.length} resultados · ${ofertas.length} ofertas cargadas`;
  mas.hidden = mostradas >= filtradas.length;
  vacio.hidden = filtradas.length !== 0;
}
function verMas(){
  const siguientes = filtradas.slice(mostradas, mostradas + BLOQUE);
  const fragmento = document.createDocumentFragment();
  siguientes.forEach(o => fragmento.append(tarjeta(o)));
  resultados.append(fragmento); mostradas += siguientes.length; actualizarContador();
}
function filtrar(){
  const texto = normal(busqueda.value).trim();
  filtradas = ofertas.filter(o => (!solo.checked || o.descuento > 0) && normal(o.nombre).includes(texto) && (!tipo.value || categoria(o) === tipo.value));
  filtradas.sort(orden.value === 'precio' ? (a,b) => a.precio_final - b.precio_final : orden.value === 'nombre' ? (a,b) => a.nombre.localeCompare(b.nombre, 'es') : (a,b) => b.descuento - a.descuento || a.nombre.localeCompare(b.nombre, 'es'));
  mostradas = 0; resultados.replaceChildren(); verMas();
}
async function cargar(){
  const id = ++peticion, codigo = region.value;
  ofertas = []; filtradas = []; mostradas = 0; tipos(); filtrar();
  contador.textContent = 'Cargando ofertas…'; $('fecha').textContent = ''; $('aviso').textContent = '';
  try{
    const r = await fetch(`data/ofertas-${codigo}.json`);
    if(!r.ok) throw new Error('Error de carga');
    const datos = await r.json();
    if(id !== peticion) return;
    const esperada = codigo === 'es' ? 'EUR' : 'UAH';
    if(datos.divisa !== esperada || !Array.isArray(datos.ofertas) || datos.ofertas.some(o => o.divisa !== esperada)) throw new Error('Datos o divisa inesperados');
    ofertas = datos.ofertas; divisa = datos.divisa; tipos();
    $('fecha').textContent = `${codigo === 'es' ? 'España' : 'Ucrania'} — Actualizado: ${new Date(datos.actualizado).toLocaleString('es-ES')}`;
    $('aviso').textContent = datos.hay_mas !== false ? 'Listado incompleto: quedan ofertas sin descargar. La búsqueda solo cubre los datos disponibles.' : 'Precios regionales de Steam según ITAD, sin conversiones. Búsqueda sobre todo el listado descargado.';
    filtrar();
  }catch{
    if(id !== peticion) return;
    ofertas = []; filtradas = []; mostradas = 0; resultados.replaceChildren(); mas.hidden = true; vacio.hidden = true;
    contador.textContent = 'No se pudieron cargar las ofertas o la divisa no coincide. Comprueba la actualización de datos.';
  }
}
mas.addEventListener('click', verMas);
busqueda.addEventListener('input', filtrar);
orden.addEventListener('change', filtrar);
solo.addEventListener('change', filtrar);
tipo.addEventListener('change', filtrar);
region.addEventListener('change', cargar);
cargar();
