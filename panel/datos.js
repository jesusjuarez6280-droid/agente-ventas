// Datos de ejemplo. Nombres de campos iguales a la base; reemplazar por llamadas a la API.
export const EMPRESA = 'Distribuidora Occidente';

export const productos = [
  { sku: 'HAR-PAN-044', nombre_erp: 'HARINA DE TRIGO PANIFICABLE 44 KG', nombre_corto: 'Harina panificable', alias: ['harina de pan', 'la fuerte', 'harina de bolillo', 'la panificadora', 'harina roja'], presentaciones: [{ nombre: 'bulto', kg: 44 }], precio_kg: 14.80 },
  { sku: 'HAR-TOR-044', nombre_erp: 'HARINA DE TRIGO TORTILLERA 44 KG', nombre_corto: 'Harina tortillera', alias: ['harina de tortilla', 'la de tortilla de harina'], presentaciones: [{ nombre: 'bulto', kg: 44 }], precio_kg: 13.90 },
  { sku: 'HAR-INT-025', nombre_erp: 'HARINA INTEGRAL DE TRIGO 25 KG', nombre_corto: 'Harina integral', alias: ['integral', 'la morena'], presentaciones: [{ nombre: 'bulto', kg: 25 }], precio_kg: 18.40 },
  { sku: 'AZU-EST-050', nombre_erp: 'AZUCAR ESTANDAR 50 KG', nombre_corto: 'Azúcar estándar', alias: ['azúcar morena', 'estándar', 'la café'], presentaciones: [{ nombre: 'bulto', kg: 50 }], precio_kg: 23.60 },
  { sku: 'AZU-REF-050', nombre_erp: 'AZUCAR REFINADA 50 KG', nombre_corto: 'Azúcar refinada', alias: ['azúcar blanca', 'refinada', 'la blanca'], presentaciones: [{ nombre: 'bulto', kg: 50 }], precio_kg: 27.20 },
  { sku: 'AZU-MAS-025', nombre_erp: 'AZUCAR MASCABADO 25 KG', nombre_corto: 'Azúcar mascabado', alias: ['mascabado'], presentaciones: [{ nombre: 'bulto', kg: 25 }], precio_kg: 31.50 },
  { sku: 'FRI-PIN-050', nombre_erp: 'FRIJOL PINTO NACIONAL 50 KG', nombre_corto: 'Frijol pinto', alias: ['pinto', 'frijol de la olla'], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 33.80 },
  { sku: 'FRI-NEG-050', nombre_erp: 'FRIJOL NEGRO JAMAPA 50 KG', nombre_corto: 'Frijol negro', alias: ['negro', 'jamapa'], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 31.20 },
  { sku: 'ARR-SUP-050', nombre_erp: 'ARROZ SUPER EXTRA 50 KG', nombre_corto: 'Arroz súper extra', alias: ['arroz', 'el largo'], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 25.90 },
  { sku: 'MAI-BLA-050', nombre_erp: 'MAIZ BLANCO 50 KG', nombre_corto: 'Maíz blanco', alias: ['maíz', 'grano blanco'], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 7.40 },
  { sku: 'AVE-HOJ-025', nombre_erp: 'AVENA EN HOJUELA 25 KG', nombre_corto: 'Avena en hojuela', alias: ['avena'], presentaciones: [{ nombre: 'bulto', kg: 25 }], precio_kg: 22.60 },
  { sku: 'SAL-REF-025', nombre_erp: 'SAL REFINADA 25 KG', nombre_corto: 'Sal refinada', alias: ['sal'], presentaciones: [{ nombre: 'bulto', kg: 25 }], precio_kg: 6.90 },
  { sku: 'GAR-GRA-050', nombre_erp: 'GARBANZO GRANDE 50 KG', nombre_corto: 'Garbanzo', alias: [], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 38.50 },
  { sku: 'LEN-CHI-050', nombre_erp: 'LENTEJA CHICA 50 KG', nombre_corto: 'Lenteja chica', alias: ['lenteja'], presentaciones: [{ nombre: 'costal', kg: 50 }], precio_kg: 29.70 },
  { sku: 'HAR-MAI-020', nombre_erp: 'HARINA DE MAIZ NIXTAMALIZADO 20 KG', nombre_corto: 'Harina de maíz', alias: ['masa', 'harina para tamal'], presentaciones: [{ nombre: 'bulto', kg: 20 }], precio_kg: 16.30 },
];
const P = Object.fromEntries(productos.map(p => [p.sku, p]));

export const clientes = [
  { cliente_id: 'C-1042', nombre: 'Rogelio Mendoza', razon_social: 'Panificadora La Espiga de Oro SA de CV', telefono: '33 3614 2290', vendedor: 'Martha Ibarra', limite_credito: 250000, saldo_actual: 118400, dias_credito: 30 },
  { cliente_id: 'C-0877', nombre: 'Guadalupe Ruelas', razon_social: 'Abarrotes Hermanos Ruelas', telefono: '33 3825 7710', vendedor: 'Martha Ibarra', limite_credito: 120000, saldo_actual: 96300, dias_credito: 15 },
  { cliente_id: 'C-1203', nombre: 'Jesús Carranza', razon_social: 'Mayoreo Don Chuy', telefono: '33 1290 4418', vendedor: 'Óscar Plascencia', limite_credito: 400000, saldo_actual: 142900, dias_credito: 30 },
  { cliente_id: 'C-0931', nombre: 'Leticia Orozco', razon_social: 'Pastelería Montserrat', telefono: '33 3647 0152', vendedor: 'Martha Ibarra', limite_credito: 90000, saldo_actual: 21800, dias_credito: 15 },
  { cliente_id: 'C-1118', nombre: 'Arturo Gallardo', razon_social: 'Tortillería Los Arcos', telefono: '33 3122 9087', vendedor: 'Óscar Plascencia', limite_credito: 150000, saldo_actual: 64500, dias_credito: 21 },
  { cliente_id: 'C-0765', nombre: 'Patricia Lomelí', razon_social: 'Comercializadora Tapatía de Granos', telefono: '33 3905 6621', vendedor: 'Raúl Cisneros', limite_credito: 600000, saldo_actual: 388000, dias_credito: 45 },
  { cliente_id: 'C-1307', nombre: 'Fernando Aceves', razon_social: 'Cremería y Abarrotes Zapopan', telefono: '33 1580 3344', vendedor: 'Raúl Cisneros', limite_credito: 80000, saldo_actual: 57200, dias_credito: 15 },
  { cliente_id: 'C-0990', nombre: 'Marisela Topete', razon_social: 'Dulcería El Trébol', telefono: '33 3658 1270', vendedor: 'Óscar Plascencia', limite_credito: 200000, saldo_actual: 45100, dias_credito: 30 },
  { cliente_id: 'C-1250', nombre: 'Humberto Navarro', razon_social: 'Restaurante El Pialadero', telefono: '33 3616 9902', vendedor: 'Raúl Cisneros', limite_credito: 60000, saldo_actual: 12300, dias_credito: 15 },
  { cliente_id: 'C-1011', nombre: 'Ana Karen Ríos', razon_social: 'Tienda La Providencia', telefono: '33 2001 5563', vendedor: 'Martha Ibarra', limite_credito: 70000, saldo_actual: 38900, dias_credito: 15 },
  { cliente_id: 'C-1164', nombre: 'Salvador Íñiguez', razon_social: 'Panadería San Juan Bosco', telefono: '33 3619 4471', vendedor: 'Óscar Plascencia', limite_credito: 180000, saldo_actual: 71000, dias_credito: 30 },
  { cliente_id: null, nombre: 'Eduardo Pulido', razon_social: 'No registrado', telefono: '33 1847 6620', vendedor: 'Sin asignar', limite_credito: 0, saldo_actual: 0, dias_credito: 0 },
];
const C = Object.fromEntries(clientes.map(c => [c.telefono, c]));

let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const hex = n => Array.from({ length: n }, () => '0123456789ABCDEF'[Math.floor(rnd() * 16)]).join('');
const r2 = n => Math.round(n * 100) / 100;

// [sku, unidades, frase del cliente, {sust: sku original, justo: true}]
const BRUTO = [
  ['33 3614 2290', 'voz', '06:52', [['HAR-PAN-044', 40, 'Mándame cuarenta bultos de la de siempre, la de bolillo'], ['AZU-EST-050', 20, 'y ponle veinte de azúcar estándar'], ['SAL-REF-025', 6, 'ah, y seis de sal, que ya se me está acabando']], 'Entregar antes de las 11, el andén de atrás.'],
  ['33 1290 4418', 'voz', '07:08', [['FRI-PIN-050', 60, 'Necesito sesenta costales de pinto'], ['ARR-SUP-050', 40, 'cuarenta de arroz del largo'], ['FRI-NEG-050', 30, 'y treinta de jamapa', { justo: true }]], ''],
  ['33 3825 7710', 'whatsapp', '07:31', [['AZU-REF-050', 25, '25 bultos de azúcar blanca'], ['FRI-PIN-050', 15, '15 de pinto'], ['LEN-CHI-050', 10, '10 lenteja'], ['AVE-HOJ-025', 12, 'y 12 de avena']], ''],
  ['33 3647 0152', 'voz', '07:46', [['AZU-EST-050', 18, 'Dame dieciocho bultos de refinada', { sust: 'AZU-REF-050' }], ['HAR-INT-025', 8, 'ocho de la integral']], 'Si no hay refinada, estándar está bien.'],
  ['33 3122 9087', 'voz', '08:03', [['HAR-TOR-044', 80, 'Ochenta bultos de harina para tortilla'], ['SAL-REF-025', 10, 'diez de sal']], ''],
  ['33 3905 6621', 'email', '08:15', [['MAI-BLA-050', 400, '400 costales de maíz blanco'], ['FRI-PIN-050', 120, '120 costales frijol pinto'], ['GAR-GRA-050', 40, '40 costales garbanzo', { justo: true }]], 'Orden de compra OC-22871 adjunta.'],
  ['33 1580 3344', 'voz', '08:27', [['AZU-EST-050', 30, 'Oiga, mándeme treinta de azúcar'], ['ARR-SUP-050', 20, 'veinte de arroz'], ['FRI-NEG-050', 12, 'y doce de frijol negro']], ''],
  ['33 3658 1270', 'texto', '08:40', [['AZU-REF-050', 45, '45 refinada'], ['AZU-MAS-025', 10, '10 mascabado']], ''],
  ['33 3616 9902', 'voz', '08:58', [['FRI-PIN-050', 8, 'Ocho costales de frijol de la olla'], ['ARR-SUP-050', 10, 'diez de arroz'], ['HAR-MAI-020', 15, 'y quince de harina para tamal']], 'Recoge en sucursal.'],
  ['33 1847 6620', 'voz', '09:12', [['HAR-PAN-044', 30, 'Quiero treinta bultos de harina de pan'], ['AZU-EST-050', 10, 'y diez de azúcar']], 'Cliente nuevo, pidió factura.'],
  ['33 3619 4471', 'whatsapp', '09:20', [['HAR-PAN-044', 50, '50 bultos de la fuerte'], ['AZU-REF-050', 20, '20 de blanca'], ['AVE-HOJ-025', 6, '6 avena']], ''],
  ['33 2001 5563', 'voz', '09:34', [['FRI-PIN-050', 10, 'Diez costales de pinto'], ['AZU-EST-050', 12, 'doce de estándar'], ['SAL-REF-025', 8, 'ocho de sal'], ['LEN-CHI-050', 5, 'y cinco de lenteja']], ''],
  ['33 1290 4418', 'whatsapp', '09:51', [['MAI-BLA-050', 150, '150 de maíz'], ['HAR-MAI-020', 40, '40 de masa']], ''],
  ['33 3614 2290', 'voz', '10:06', [['HAR-INT-025', 20, 'Me faltó: veinte de integral'], ['AZU-MAS-025', 8, 'y ocho de mascabado']], 'Complemento del pedido de la mañana.'],
  ['33 3122 9087', 'texto', '10:18', [['HAR-TOR-044', 40, '40 harina tortilla'], ['HAR-PAN-044', 10, '10 panificable']], ''],
];

export const pedidos = BRUTO.map(([tel, canal, hora, lineas, obs], i) => {
  const cli = C[tel];
  const partidas = lineas.map(([sku, n, frase, ex = {}], k) => {
    const p = P[sku], pres = p.presentaciones[0], kg = n * pres.kg;
    return { linea: k + 1, sku, descripcion: p.nombre_erp, nombre_corto: p.nombre_corto, cantidad_kg: kg, cantidad_texto: `${n} ${pres.nombre}${n === 1 ? '' : 's'}`, unidades: n, presentacion: pres, precio_unitario: p.precio_kg, importe: r2(kg * p.precio_kg), frase_origen: frase, offset_audio_ms: null, sustituye: ex.sust ? P[ex.sust].nombre_corto : null, justo: !!ex.justo };
  });
  const total = r2(partidas.reduce((s, x) => s + x.importe, 0));
  const disponible = cli.limite_credito - cli.saldo_actual;
  const banderas = [];
  if (!cli.cliente_id) banderas.push({ tipo: 'cliente_nuevo', texto: 'Cliente nuevo no registrado', tono: 'warning' });
  else if (total > disponible) banderas.push({ tipo: 'credito', texto: 'Crédito excedido por ' + fmt$(total - disponible), tono: 'danger' });
  partidas.filter(x => x.justo).forEach(x => banderas.push({ tipo: 'inventario', texto: 'Inventario justo: ' + x.nombre_corto, tono: 'warning' }));
  partidas.filter(x => x.sustituye).forEach(x => banderas.push({ tipo: 'sustituto', texto: `Sustituido: ${x.sustituye} → ${x.nombre_corto}`, tono: 'warning' }));
  const conversacion_id = 'CONV-' + hex(8);
  return { folio: 'BOR-' + hex(10), cliente_id: cli.cliente_id, cliente: cli, canal, estado: 'por_aprobar', total, fecha_entrega: i < 9 ? '2026-09-26' : '2026-09-28', observaciones: obs, folio_erp: null, motivo_fallo: null, creado_en: '2026-09-26T' + hora + ':00', hora, conversacion_id, partidas, banderas, credito_disponible: disponible };
});

// Transcripción generada a partir de las partidas (en producción viene de la tabla traza)
export function traza(pedido) {
  const voz = pedido.canal === 'voz', cli = pedido.cliente;
  const out = []; let t = 0, s = 0;
  const [hh, mm] = pedido.hora.split(':').map(Number);
  const reloj = ms => { const d = new Date(2026, 8, 26, hh, mm, 0, 0); d.setMilliseconds(ms); return d.toTimeString().slice(0, 8); };
  const add = (tipo, contenido, extra = {}, dur = 0) => { out.push({ conversacion_id: pedido.conversacion_id, secuencia: ++s, tipo, contenido, offset_audio_ms: voz ? t : null, creado_en: reloj(t), ...extra }); t += dur; };
  const tool = (herramienta, entrada, salida, latencia_ms) => { add('herramienta', '', { herramienta, entrada, salida, latencia_ms }, latencia_ms); };
  if (voz) {
    add('agente', `${EMPRESA}, buenos días. Soy el asistente de pedidos. ¿Con quién tengo el gusto?`, {}, 4200);
    add('cliente', cli.cliente_id ? `Qué tal, habla ${cli.nombre.split(' ')[0]}, de ${cli.razon_social.replace(/ SA de CV/, '')}.` : `Buenos días, soy ${cli.nombre}. Es la primera vez que les compro.`, {}, 3100);
  } else {
    add('cliente', pedido.partidas.map(p => p.frase_origen).join('\n'), {}, 900);
  }
  tool('identificar_cliente', `{ telefono: "${cli.telefono}" }`, cli.cliente_id ? `{ cliente_id: "${cli.cliente_id}", credito_disp: ${pedido.credito_disponible} }` : '{ encontrado: false }', 90 + Math.round(rnd() * 80));
  if (voz) add('agente', cli.cliente_id ? `Buenos días, ${cli.nombre.split(' ')[0]}. ¿Qué le mando hoy?` : 'Con gusto lo atiendo. ¿Qué producto necesita?', {}, 2600);
  pedido.partidas.forEach((p, k) => {
    if (voz) { p.offset_audio_ms = t; add('cliente', p.frase_origen, { linea: p.linea }, 3400); }
    else { p.offset_audio_ms = null; if (k === 0) out[0].linea_multi = true; }
    tool('buscar_producto', `{ termino: "${p.frase_origen.toLowerCase().slice(0, 36)}" }`, `{ sku: "${p.sku}", confianza: ${(0.86 + rnd() * 0.13).toFixed(2)} }`, 70 + Math.round(rnd() * 160));
    tool('consultar_disponibilidad', `{ sku: "${p.sku}", kg: ${p.cantidad_kg} }`, `{ disponible_kg: ${p.cantidad_kg + (p.justo ? 120 : 2400 + Math.round(rnd() * 8000))} }`, 50 + Math.round(rnd() * 110));
    if (p.sustituye && voz) {
      add('agente', `De ${p.sustituye.toLowerCase()} no tengo hoy. Le puedo mandar ${p.nombre_corto.toLowerCase()}, ${p.cantidad_texto} a $${p.precio_unitario.toFixed(2)} el kilo. ¿Le parece?`, {}, 5200);
      add('cliente', 'Sí, ándale, mándame esa.', { linea: p.linea, confirma: true }, 2000);
    } else if (voz) {
      add('agente', `Anotado: ${p.cantidad_texto} de ${p.nombre_corto.toLowerCase()}, ${fmtKg(p.cantidad_kg)}.` + (p.justo ? ' Es lo último que tengo de ese producto hoy.' : ''), {}, 3600);
    }
    tool('agregar_al_pedido', `{ linea: ${p.linea}, sku: "${p.sku}", kg: ${p.cantidad_kg} }`, `{ importe: ${p.importe} }`, 40 + Math.round(rnd() * 60));
  });
  tool('crear_borrador', `{ cliente_id: "${cli.cliente_id ?? 'NUEVO'}" }`, `{ folio: "${pedido.folio}", estado: "por_aprobar" }`, 180 + Math.round(rnd() * 120));
  add('agente', `Queda su pedido ${pedido.folio} por ${fmt$(pedido.total)}, con entrega el ${pedido.fecha_entrega === '2026-09-26' ? 'día de hoy' : 'lunes 28'}. En cuanto lo confirmemos le llega el mensaje.`, {}, 6100);
  if (voz) add('cliente', 'Órale, muchas gracias.', {}, 1800);
  add('sistema', voz ? 'Llamada terminada por el cliente' : 'Conversación cerrada', {}, 0);
  return { turnos: out, duracion_ms: t };
}

export function fmt$(n, dec = 2) { return '$' + Number(n).toLocaleString('es-MX', { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
export function fmtKg(n) { return Number(n).toLocaleString('es-MX') + ' kg'; }
export function fmtN(n) { return Number(n).toLocaleString('es-MX'); }

export const tablero = {
  hoy: { llamadas: 142, llamadas_prev: 128, pedidos: 97, monto: 2184300, monto_prev: 1962100, acierto: 91.8, acierto_prev: 90.6, tendencia: [86.2, 87.9, 88.4, 89.1, 90.2, 90.6, 91.8], etiquetas: ['L', 'M', 'M', 'J', 'V', 'S', 'Hoy'], lat_p50: 412, lat_p95: 980, escal: 9, motivos: [['Pidió hablar con su vendedor', 4], ['Reclamo de entrega', 3], ['Precio especial', 2]] },
  semana: { llamadas: 894, llamadas_prev: 842, pedidos: 611, monto: 13482900, monto_prev: 12790400, acierto: 90.4, acierto_prev: 88.7, tendencia: [82.1, 84.0, 85.3, 86.9, 87.4, 88.7, 90.4], etiquetas: ['S31', 'S32', 'S33', 'S34', 'S35', 'S36', 'S37'], lat_p50: 428, lat_p95: 1040, escal: 57, motivos: [['Pidió hablar con su vendedor', 22], ['Reclamo de entrega', 17], ['Precio especial', 11], ['No se entendió el audio', 7]] },
  mes: { llamadas: 3712, llamadas_prev: 3210, pedidos: 2498, monto: 54917600, monto_prev: 47322800, acierto: 88.9, acierto_prev: 84.2, tendencia: [71.5, 76.2, 80.8, 84.2, 88.9], etiquetas: ['May', 'Jun', 'Jul', 'Ago', 'Sep'], lat_p50: 436, lat_p95: 1110, escal: 241, motivos: [['Pidió hablar con su vendedor', 96], ['Reclamo de entrega', 71], ['Precio especial', 44], ['No se entendió el audio', 30]] },
};

export const ventaRiesgo = [
  { sku: 'GAR-GRA-050', producto: 'Garbanzo', veces: 38, kg: 21400, monto: 823900, proxima: 'Jue 1 oct · 8 t' },
  { sku: 'AZU-REF-050', producto: 'Azúcar refinada', veces: 52, kg: 27800, monto: 756160, proxima: 'Mar 29 sep · 12 t' },
  { sku: 'FRI-NEG-050', producto: 'Frijol negro', veces: 29, kg: 16500, monto: 514800, proxima: 'Sin fecha' },
  { sku: 'AZU-MAS-025', producto: 'Azúcar mascabado', veces: 21, kg: 6250, monto: 196880, proxima: 'Lun 5 oct · 3 t' },
  { sku: 'LEN-CHI-050', producto: 'Lenteja chica', veces: 11, kg: 4400, monto: 130680, proxima: 'Jue 1 oct · 5 t' },
  { sku: 'AVE-HOJ-025', producto: 'Avena en hojuela', veces: 9, kg: 2750, monto: 62150, proxima: 'Estimada 8 oct' },
];

export const aliasPendientes = [
  { termino: 'la de siempre', veces: 64, ejemplo: '“mándame cuarenta bultos de la de siempre”', sku_resuelto: null, revisado: false, nota: 'Depende del cliente: usar su último pedido' },
  { termino: 'harina tres estrellas', veces: 27, ejemplo: '“¿tienes de la tres estrellas?”', sku_resuelto: null, revisado: false },
  { termino: 'azúcar de caña', veces: 19, ejemplo: '“diez de azúcar de caña”', sku_resuelto: null, revisado: false },
  { termino: 'frijol bayo', veces: 14, ejemplo: '“¿manejas bayo?”', sku_resuelto: null, revisado: false },
  { termino: 'la gruesa', veces: 11, ejemplo: '“la avena gruesa, no la fina”', sku_resuelto: null, revisado: false },
  { termino: 'pinto americano', veces: 8, ejemplo: '“del pinto americano, no el nacional”', sku_resuelto: null, revisado: false },
];

export const porHora = [
  [6, 14], [7, 61], [8, 78], [9, 92], [10, 85], [11, 71], [12, 58], [13, 44], [14, 39], [15, 52], [16, 57], [17, 48], [18, 36], [19, 29], [20, 33], [21, 47], [22, 18],
];
export const HORARIO = [9, 18]; // horario con personal en oficina

export const catalogo = [
  ['HAR-PAN-044', 612, 0.94], ['AZU-EST-050', 540, 0.71], ['FRI-PIN-050', 488, 0.89], ['AZU-REF-050', 431, 0.66], ['ARR-SUP-050', 392, 0.92],
  ['HAR-TOR-044', 355, 0.83], ['MAI-BLA-050', 301, 0.95], ['FRI-NEG-050', 244, 0.78], ['SAL-REF-025', 210, 0.97], ['HAR-INT-025', 118, 0.74],
  ['AVE-HOJ-025', 96, 0.88], ['HAR-MAI-020', 91, 0.62], ['LEN-CHI-050', 64, 0.9], ['GAR-GRA-050', 58, 0.93], ['AZU-MAS-025', 41, 0.86],
].map(([sku, pedidos_mes, confianza]) => ({ ...P[sku], pedidos_mes, confianza }));

export const existencias = [
  ['HAR-PAN-044', 'Central', 48400, 21120, 1760], ['HAR-TOR-044', 'Central', 31680, 5280, 3520], ['HAR-INT-025', 'Central', 4200, 1700, 500],
  ['AZU-EST-050', 'Central', 36500, 14400, 3000], ['AZU-REF-050', 'Central', 3150, 2900, 0], ['AZU-MAS-025', 'Central', 900, 450, 200],
  ['FRI-PIN-050', 'Central', 42000, 12150, 4000], ['FRI-NEG-050', 'Central', 2600, 1500, 600], ['ARR-SUP-050', 'Central', 24500, 3500, 1000],
  ['MAI-BLA-050', 'Norte', 96000, 27500, 7500], ['GAR-GRA-050', 'Norte', 2400, 2000, 0], ['LEN-CHI-050', 'Norte', 5100, 750, 250],
  ['SAL-REF-025', 'Central', 18750, 600, 400], ['AVE-HOJ-025', 'Central', 3300, 450, 300], ['HAR-MAI-020', 'Central', 7600, 1100, 800],
].map(([sku, almacen, existencia_kg, comprometido_kg, apartado_kg]) => ({ sku, nombre: P[sku].nombre_corto, almacen, existencia_kg, comprometido_kg, apartado_kg, disponible_kg: existencia_kg - comprometido_kg - apartado_kg }));

export const reposiciones = [
  { sku: 'AZU-REF-050', nombre: 'Azúcar refinada', cantidad_kg: 12000, fecha_estimada: 'Mar 29 sep', origen: 'compra', confianza: 'confirmada', referencia: 'OC-10482 · Ingenio Tala' },
  { sku: 'GAR-GRA-050', nombre: 'Garbanzo', cantidad_kg: 8000, fecha_estimada: 'Jue 1 oct', origen: 'compra', confianza: 'confirmada', referencia: 'OC-10477 · Agrícola del Fuerte' },
  { sku: 'LEN-CHI-050', nombre: 'Lenteja chica', cantidad_kg: 5000, fecha_estimada: 'Jue 1 oct', origen: 'traspaso', confianza: 'confirmada', referencia: 'TR-2291 · Almacén Norte' },
  { sku: 'HAR-PAN-044', nombre: 'Harina panificable', cantidad_kg: 22000, fecha_estimada: 'Vie 2 oct', origen: 'produccion', confianza: 'estimada', referencia: 'OP-771 · Molino 2' },
  { sku: 'AZU-MAS-025', nombre: 'Azúcar mascabado', cantidad_kg: 3000, fecha_estimada: 'Lun 5 oct', origen: 'compra', confianza: 'estimada', referencia: 'OC-10490 · pendiente de embarque' },
  { sku: 'AVE-HOJ-025', nombre: 'Avena en hojuela', cantidad_kg: 4000, fecha_estimada: 'Jue 8 oct', origen: 'compra', confianza: 'estimada', referencia: 'OC-10493' },
];

// Llamadas en vivo (guion que se reproduce en la demo)
export const enVivo = [
  { telefono: '33 3614 2290', cliente: 'Panificadora La Espiga de Oro', guion: [
    ['agente', `${EMPRESA}, buenos días. Soy el asistente de pedidos. ¿Con quién tengo el gusto?`],
    ['cliente', 'Habla Rogelio, de La Espiga.'],
    ['herramienta', 'identificar_cliente', 112],
    ['agente', 'Buenos días, Rogelio. ¿Qué le mando hoy?'],
    ['cliente', 'Mándame treinta bultos de la de bolillo.'],
    ['herramienta', 'buscar_producto', 94], ['herramienta', 'consultar_disponibilidad', 71],
    ['agente', 'Anotado: 30 bultos de harina panificable, 1,320 kg.'], ['partida', 'HAR-PAN-044', 30],
    ['cliente', 'Y quince de refinada.'],
    ['herramienta', 'buscar_producto', 88], ['herramienta', 'consultar_disponibilidad', 64],
    ['agente', 'De refinada hoy sólo tengo 5 bultos. El martes 29 entran doce toneladas. ¿Le mando 5 hoy y 10 el martes?'],
    ['cliente', 'Sí, así está bien.'], ['partida', 'AZU-REF-050', 5],
    ['cliente', 'Y ocho de sal.'],
    ['herramienta', 'buscar_producto', 61], ['herramienta', 'consultar_disponibilidad', 58],
    ['agente', 'Anotado: 8 bultos de sal refinada, 200 kg.'], ['partida', 'SAL-REF-025', 8],
  ] },
  { telefono: '33 3905 6621', cliente: 'Comercializadora Tapatía de Granos', estado: 'Pidiendo', dur: '01:48', partidas: 2 },
  { telefono: '33 3122 9087', cliente: 'Tortillería Los Arcos', estado: 'Confirmando', dur: '02:31', partidas: 3 },
];
export { P as productosPorSku };
