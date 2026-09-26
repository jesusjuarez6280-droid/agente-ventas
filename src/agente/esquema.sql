-- ============================================================================
-- Esquema del nucleo. Escrito en SQL portable: corre en SQLite para desarrollo
-- y migra a Postgres cambiando muy poco (los TEXT de fecha pasan a TIMESTAMPTZ).
--
-- Todas las tablas llevan `tenant` para que el dia que atiendas a mas de una
-- empresa no haya que rehacer nada.
-- ============================================================================

CREATE TABLE IF NOT EXISTS productos (
    tenant          TEXT NOT NULL,
    sku             TEXT NOT NULL,
    nombre_erp      TEXT NOT NULL,
    nombre_corto    TEXT NOT NULL,
    alias           TEXT NOT NULL DEFAULT '',   -- separados por ';'
    unidad_base     TEXT NOT NULL DEFAULT 'kg',
    presentaciones  TEXT NOT NULL DEFAULT '',   -- 'bulto:50;tarima:2000'
    precio_kg       REAL NOT NULL DEFAULT 0,
    activo          INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tenant, sku)
);

CREATE TABLE IF NOT EXISTS clientes (
    tenant          TEXT NOT NULL,
    cliente_id      TEXT NOT NULL,
    nombre          TEXT NOT NULL,
    razon_social    TEXT,
    telefono        TEXT,
    vendedor        TEXT,
    limite_credito  REAL NOT NULL DEFAULT 0,
    saldo_actual    REAL NOT NULL DEFAULT 0,
    dias_credito    INTEGER NOT NULL DEFAULT 0,
    activo          INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tenant, cliente_id)
);
CREATE INDEX IF NOT EXISTS ix_clientes_tel ON clientes (tenant, telefono);

-- Espejo del inventario del ERP. Se refresca por sincronizacion, nunca se
-- consulta el ERP en vivo durante una llamada.
CREATE TABLE IF NOT EXISTS existencias (
    tenant          TEXT NOT NULL,
    sku             TEXT NOT NULL,
    almacen         TEXT NOT NULL DEFAULT 'PRINCIPAL',
    existencia_kg   REAL NOT NULL DEFAULT 0,
    comprometido_kg REAL NOT NULL DEFAULT 0,
    sincronizado_en TEXT,
    PRIMARY KEY (tenant, sku, almacen)
);

-- Reserva suave: aparta material mientras se cierra el pedido y se libera sola.
CREATE TABLE IF NOT EXISTS reservas (
    reserva_id      TEXT PRIMARY KEY,
    tenant          TEXT NOT NULL,
    sku             TEXT NOT NULL,
    almacen         TEXT NOT NULL DEFAULT 'PRINCIPAL',
    cantidad_kg     REAL NOT NULL,
    folio           TEXT,
    creada_en       TEXT NOT NULL,
    vence_en        TEXT NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'activa'  -- activa | consumida | liberada
);
CREATE INDEX IF NOT EXISTS ix_reservas_sku ON reservas (tenant, sku, estado);

CREATE TABLE IF NOT EXISTS pedidos (
    folio               TEXT PRIMARY KEY,
    tenant              TEXT NOT NULL,
    cliente_id          TEXT,
    canal               TEXT NOT NULL,          -- voz | whatsapp | texto | email
    conversacion_id     TEXT,
    estado              TEXT NOT NULL,          -- borrador | por_aprobar | confirmado | en_erp | cancelado | fallido
    total               REAL NOT NULL DEFAULT 0,
    fecha_entrega       TEXT,
    observaciones       TEXT,
    folio_erp           TEXT,
    motivo_fallo        TEXT,
    creado_en           TEXT NOT NULL,
    actualizado_en      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pedidos_estado ON pedidos (tenant, estado);

CREATE TABLE IF NOT EXISTS partidas (
    partida_id       TEXT PRIMARY KEY,
    folio            TEXT NOT NULL,
    linea            INTEGER NOT NULL,
    sku              TEXT NOT NULL,
    descripcion      TEXT NOT NULL,
    cantidad_kg      REAL NOT NULL,
    cantidad_texto   TEXT,                      -- '40 bultos' tal como lo dijo el cliente
    precio_unitario  REAL NOT NULL,
    importe          REAL NOT NULL,
    reserva_id       TEXT,
    -- Trazabilidad de origen: donde en la conversacion se pidio esta partida.
    turno_id         TEXT,
    offset_audio_ms  INTEGER,
    frase_origen     TEXT
);
CREATE INDEX IF NOT EXISTS ix_partidas_folio ON partidas (folio);

-- Traza completa: cada turno de conversacion y cada llamada a herramienta.
CREATE TABLE IF NOT EXISTS traza (
    turno_id         TEXT PRIMARY KEY,
    tenant           TEXT NOT NULL,
    conversacion_id  TEXT NOT NULL,
    secuencia        INTEGER NOT NULL,
    tipo             TEXT NOT NULL,             -- cliente | agente | herramienta | sistema
    contenido        TEXT,
    herramienta      TEXT,
    entrada          TEXT,                      -- JSON
    salida           TEXT,                      -- JSON
    latencia_ms      INTEGER,
    offset_audio_ms  INTEGER,
    creado_en        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_traza_conv ON traza (conversacion_id, secuencia);

CREATE TABLE IF NOT EXISTS conversaciones (
    conversacion_id  TEXT PRIMARY KEY,
    tenant           TEXT NOT NULL,
    canal            TEXT NOT NULL,
    telefono         TEXT,
    cliente_id       TEXT,
    estado           TEXT NOT NULL DEFAULT 'abierta',  -- abierta | cerrada | escalada
    motivo_cierre    TEXT,
    ruta_audio       TEXT,
    iniciada_en      TEXT NOT NULL,
    terminada_en     TEXT
);

-- Cosas que no son pedido: quejas, consultas, seguimientos, avisos.
CREATE TABLE IF NOT EXISTS incidencias (
    incidencia_id    TEXT PRIMARY KEY,
    tenant           TEXT NOT NULL,
    conversacion_id  TEXT,
    cliente_id       TEXT,
    tipo             TEXT NOT NULL,             -- queja | consulta | seguimiento | escalamiento
    resumen          TEXT NOT NULL,
    detalle          TEXT,
    prioridad        TEXT NOT NULL DEFAULT 'normal',
    estado           TEXT NOT NULL DEFAULT 'abierta',
    creada_en        TEXT NOT NULL
);

-- Terminos que el cliente uso y el catalogo no reconocio. Alimenta la mejora
-- continua del catalogo: cada llamada fallida enseña algo.
CREATE TABLE IF NOT EXISTS alias_pendientes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant           TEXT NOT NULL,
    termino          TEXT NOT NULL,
    sku_resuelto     TEXT,
    veces            INTEGER NOT NULL DEFAULT 1,
    revisado         INTEGER NOT NULL DEFAULT 0,
    visto_en         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historial_compras (
    tenant       TEXT NOT NULL,
    cliente_id   TEXT NOT NULL,
    sku          TEXT NOT NULL,
    cantidad_kg  REAL NOT NULL,
    fecha        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_hist_cliente ON historial_compras (tenant, cliente_id, fecha);

-- Lo que todavia no esta pero va a llegar: compras en transito y produccion
-- programada. Es la diferencia entre decir "no hay" y decir "no hay hoy, pero
-- el jueves entran ocho toneladas". Una cierra la venta, la otra la pierde.
CREATE TABLE IF NOT EXISTS reposiciones (
    reposicion_id   TEXT PRIMARY KEY,
    tenant          TEXT NOT NULL,
    sku             TEXT NOT NULL,
    almacen         TEXT NOT NULL DEFAULT 'PRINCIPAL',
    cantidad_kg     REAL NOT NULL,
    fecha_estimada  TEXT NOT NULL,
    origen          TEXT NOT NULL,          -- compra | produccion | traspaso
    confianza       TEXT NOT NULL DEFAULT 'estimada',  -- confirmada | estimada
    referencia      TEXT
);
CREATE INDEX IF NOT EXISTS ix_repo_sku ON reposiciones (tenant, sku, fecha_estimada);

-- @migraciones — de aqui en adelante, sentencia por sentencia y tolerando
-- que ya existan. El orden importa: los indices van despues de sus ALTER.

-- Marca si una persona tuvo que corregir el pedido antes de aprobarlo. De aqui
-- sale la tasa de acierto, que es la metrica que decide cuando se le suelta al
-- agente la escritura automatica al ERP.
ALTER TABLE pedidos ADD COLUMN corregido_en_revision INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------------------
-- Correcciones de la auditoria
-- ---------------------------------------------------------------------------

-- `partidas` no llevaba tenant, pese a que el comentario de arriba afirmaba que
-- todas lo llevaban. Sin el, salud_catalogo unia partidas por SKU y le sumaba a
-- un cliente las ventas de otro que vendiera el mismo producto.
ALTER TABLE partidas ADD COLUMN tenant TEXT NOT NULL DEFAULT '';

-- Idempotencia real de la escritura al ERP. Antes se deducia de pedidos.folio_erp,
-- que se llena DESPUES de que el ERP responde: si el proceso moria en medio, el
-- reintento creaba un segundo pedido. Aqui la clave se registra en la misma
-- transaccion que marca el pedido como escrito.
CREATE TABLE IF NOT EXISTS idempotencia_erp (
    clave        TEXT PRIMARY KEY,       -- el folio del borrador
    tenant       TEXT NOT NULL,
    folio_erp    TEXT,
    estado       TEXT NOT NULL,          -- en_vuelo | confirmada | fallida
    intentos     INTEGER NOT NULL DEFAULT 1,
    detalle      TEXT,
    creada_en    TEXT NOT NULL,
    cerrada_en   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_partidas_linea ON partidas (folio, linea);
CREATE UNIQUE INDEX IF NOT EXISTS ux_traza_secuencia ON traza (conversacion_id, secuencia);
CREATE INDEX IF NOT EXISTS ix_partidas_tenant ON partidas (tenant, sku);
CREATE TABLE IF NOT EXISTS erp_pedidos (
    folio_erp   TEXT PRIMARY KEY,
    tenant      TEXT NOT NULL,
    clave       TEXT NOT NULL,
    cliente_id  TEXT,
    total       REAL NOT NULL DEFAULT 0,
    cuerpo      TEXT,
    creado_en   TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_erp_clave ON erp_pedidos (tenant, clave);
CREATE TABLE IF NOT EXISTS usuarios (
    usuario        TEXT NOT NULL,
    tenant         TEXT NOT NULL,
    nombre         TEXT,
    password_hash  TEXT NOT NULL,
    rol            TEXT NOT NULL DEFAULT 'consulta',
    activo         INTEGER NOT NULL DEFAULT 1,
    creado_en      TEXT NOT NULL,
    ultimo_acceso  TEXT,
    PRIMARY KEY (tenant, usuario)
);
CREATE TABLE IF NOT EXISTS sesiones (
    token       TEXT PRIMARY KEY,
    tenant      TEXT NOT NULL,
    usuario     TEXT NOT NULL,
    rol         TEXT NOT NULL,
    creada_en   TEXT NOT NULL,
    vence_en    TEXT NOT NULL,
    revocada    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_sesiones_usuario ON sesiones (tenant, usuario);
