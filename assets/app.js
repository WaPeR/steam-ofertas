const resultados = document.getElementById("resultados");
const busqueda = document.getElementById("busqueda");
const selectorRegion = document.getElementById("region");
const orden = document.getElementById("orden");
const soloOfertas = document.getElementById("soloOfertas");
const vacio = document.getElementById("vacio");

let ofertas = [];
let divisaActual = "EUR";

const FORMATOS = {
  EUR: { locale: "es-ES", currency: "EUR" },
  UAH: { locale: "uk-UA", currency: "UAH" },
  TRY: { locale: "tr-TR", currency: "TRY" },
  USD: { locale: "en-US", currency: "USD" },
};

function formatearPrecio(cantidad, divisa){
  const formato = FORMATOS[divisa] ?? FORMATOS.EUR;
  return new Intl.NumberFormat(formato.locale, {
    style: "currency",
    currency: formato.currency,
  }).format(cantidad);
}

function crearTarjeta(oferta){
  const article = document.createElement("article");
  article.className = "card";

  const enlace = document.createElement("a");
  enlace.href = oferta.url_steam;
  enlace.target = "_blank";
  enlace.rel = "noopener";

  const imagen = document.createElement("img");
  imagen.src = oferta.imagen;
  imagen.alt = `Portada de ${oferta.nombre}`;
  imagen.loading = "lazy";

  const info = document.createElement("div");
  info.className = "card-info";

  const titulo = document.createElement("h2");
  titulo.textContent = oferta.nombre;

  const precios = document.createElement("div");
  precios.className = "precios";

  const descuento = document.createElement("span");
  descuento.className = "descuento";
  descuento.textContent = `-${oferta.descuento}%`;

  const precioFinal = document.createElement("span");
  precioFinal.className = "precio-final";
  precioFinal.textContent = formatearPrecio(oferta.precio_final, divisaActual);

  const precioAnterior = document.createElement("span");
  precioAnterior.className = "precio-original";
  precioAnterior.textContent = formatearPrecio(oferta.precio_original, divisaActual);

  const tienda = document.createElement("span");
  tienda.className = "tienda";
  tienda.textContent = oferta.tienda;

  precios.append(descuento, precioFinal, precioAnterior);
  info.append(titulo, precios, tienda);
  enlace.append(imagen, info);
  article.append(enlace);
  return article;
}

function render(){
  const texto = busqueda.value.toLowerCase().trim();

  let lista = ofertas.filter(oferta =>
    !soloOfertas.checked || oferta.descuento > 0
  );

  if (texto){
    lista = lista.filter(oferta =>
      oferta.nombre.toLowerCase().includes(texto)
    );
  }

  if (orden.value === "descuento"){
    lista.sort((a, b) => b.descuento - a.descuento);
  } else if (orden.value === "precio"){
    lista.sort((a, b) => a.precio_final - b.precio_final);
  } else {
    lista.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }

  resultados.replaceChildren(...lista.map(crearTarjeta));
  vacio.hidden = lista.length > 0;
}

async function cargar(){
  const region = selectorRegion.value;

  try{
    const respuesta = await fetch(`data/ofertas-${region}.json`);

    if (!respuesta.ok){
      throw new Error(`No se encontró el archivo de la región ${region}`);
    }

    const datos = await respuesta.json();
    ofertas = datos.ofertas ?? [];
    divisaActual = datos.divisa ?? "EUR";

    document.getElementById("fecha").textContent =
      `${datos.nombre_region ?? "Región"} — Actualizado: ${new Date(datos.actualizado).toLocaleString("es-ES")}`;

    render();
  }catch(error){
    resultados.innerHTML = `<p>No se pudieron cargar las ofertas de esta región.</p>`;
  }
}

busqueda.addEventListener("input", render);
selectorRegion.addEventListener("change", cargar);
orden.addEventListener("change", render);
soloOfertas.addEventListener("change", render);
cargar();
