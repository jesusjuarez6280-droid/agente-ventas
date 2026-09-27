// ---------------------------------------------------------------------------
// Armazón del panel: barra lateral y tema, compartidos por las tres pantallas.
//
// Se inyecta ALREDEDOR de lo que ya existe. Cada pantalla conserva su HTML y
// su lógica intactos — este módulo solo los envuelve. Así el trabajo visual no
// puede romper una llamada a la API por accidente, que es exactamente lo que
// no debe pasar al vestir algo que ya funciona.
//
// El diseño (colores, tipografía, espacios, el ancho de 212px de la barra) sale
// del sistema en ds/. Aquí no se inventa ni un color.
// ---------------------------------------------------------------------------

// Solo las pantallas conectadas a la API son navegables. Las demás del diseño
// original siguen siendo bocetos, y se listan como tales en vez de esconderse:
// un panel que promete secciones que no existen se cae en la primera demo.
const SECCIONES = [
  {id: 'bandeja',      titulo: 'Bandeja',          icono: 'ph-tray',        url: 'index.html'},
  {id: 'envivo',       titulo: 'Llamadas en curso', icono: 'ph-phone-call',  url: 'envivo.html'},
  {id: 'conversacion', titulo: 'La llamada',       icono: 'ph-chat-centered-text', url: 'conversacion.html'},
];

const BOCETOS = [
  {titulo: 'Tablero',    icono: 'ph-chart-line'},
  {titulo: 'Catálogo',   icono: 'ph-package'},
  {titulo: 'Inventario', icono: 'ph-warehouse'},
];

// El nombre sale del paquete de giro, vía /api/yo. El valor de abajo solo se
// ve el instante antes de que llegue la respuesta.
let NEGOCIO = '—';

/** Pide el nombre del negocio en cuanto haya sesión.
 *
 *  El armazón se monta ANTES del login, así que en la primera pasada todavía
 *  no hay token. En vez de acoplar este módulo al flujo de acceso de cada
 *  pantalla, reintenta solo hasta que la sesión exista, y se detiene al
 *  conseguirlo. Un panel que se queda con el nombre en blanco después de
 *  entrar se ve a medio terminar.
 */
async function pedirNegocio(intentos = 30) {
  let token = null;
  try { token = sessionStorage.getItem('token'); } catch {}
  if (!token) {
    if (intentos > 0) setTimeout(() => pedirNegocio(intentos - 1), 500);
    return;
  }
  try {
    const r = await fetch('/api/yo', {headers: {'Authorization': 'Bearer ' + token}});
    if (!r.ok) return;
    const d = await r.json();
    if (!d.negocio) return;

    NEGOCIO = d.negocio;
    const nombre = document.querySelector('.barra .nombre');
    const logo = document.querySelector('.barra .logo');
    if (nombre) nombre.textContent = NEGOCIO;
    if (logo) logo.textContent = iniciales(NEGOCIO);
    const giro = document.querySelector('.barra .giro');
    if (giro && d.giro) giro.textContent = `Agente de ventas · ${d.giro}`;
  } catch {
    if (intentos > 0) setTimeout(() => pedirNegocio(intentos - 1), 500);
  }
}

const iniciales = n => n.split(' ').filter(p => p.length > 2)
  .map(p => p[0]).slice(0, 2).join('').toUpperCase();

const CLAVE_TEMA = 'panel-tema';

function temaGuardado() {
  try { return localStorage.getItem(CLAVE_TEMA); } catch { return null; }
}

function aplicarTema(tema) {
  document.documentElement.setAttribute('data-theme', tema);
  try { localStorage.setItem(CLAVE_TEMA, tema); } catch {}
  const boton = document.getElementById('cambiar-tema');
  if (boton) {
    boton.innerHTML = tema === 'dark'
      ? '<i class="ph ph-sun"></i>Modo claro'
      : '<i class="ph ph-moon"></i>Modo oscuro';
  }
}

/** Envuelve la página en el armazón. `activa` es el id de la sección actual. */
export function montarArmazon(activa) {
  // El tema se fija antes de pintar, para que no haya un parpadeo claro.
  aplicarTema(temaGuardado()
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  const contenido = document.createElement('main');
  contenido.className = 'contenido';
  while (document.body.firstChild) {
    const nodo = document.body.firstChild;
    if (nodo.nodeType === 1 && nodo.tagName === 'SCRIPT') {
      // Los scripts se quedan donde están: moverlos los re-ejecuta.
      document.body.appendChild(nodo);
      break;
    }
    contenido.appendChild(nodo);
  }

  const marco = document.createElement('div');
  marco.className = 'marco';
  marco.innerHTML = `
    <aside class="barra">
      <div class="negocio">
        <div class="logo">${iniciales(NEGOCIO)}</div>
        <div style="min-width:0">
          <div class="nombre">${NEGOCIO}</div>
          <div class="giro">Agente de ventas</div>
        </div>
      </div>

      <nav>
        ${SECCIONES.map(s => `
          <a href="${s.url}" class="enlace ${s.id === activa ? 'activo' : ''}">
            <i class="ph ${s.icono}"></i>${s.titulo}
          </a>`).join('')}
      </nav>

      <div class="grupo">Sin conectar</div>
      <nav>
        ${BOCETOS.map(b => `
          <span class="enlace boceto" title="Boceto de diseño; todavía no lee de la API">
            <i class="ph ${b.icono}"></i>${b.titulo}
          </span>`).join('')}
      </nav>

      <div style="flex:1"></div>
      <button id="cambiar-tema" class="enlace" type="button"></button>
    </aside>`;

  marco.appendChild(contenido);
  document.body.prepend(marco);

  const boton = document.getElementById('cambiar-tema');
  boton.onclick = () => aplicarTema(
    document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  aplicarTema(document.documentElement.getAttribute('data-theme'));

  pedirNegocio();
}
