import psycopg2
import datetime
import os
import shutil
import csv
import flet as ft

# ==========================================================================
# 1. BASE DE DATOS - POSTGRESQL (NEON)
# ==========================================================================
class Database:
    def __init__(self):
        self.db_url = "postgresql://neondb_owner:npg_k95jPxErNLgZ@ep-holy-cherry-b8dz8gf1.c-14.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        try:
            self.conn = psycopg2.connect(self.db_url)
            self.cursor = self.conn.cursor()
            self.crear_tablas()
        except Exception as e:
            print(f"Error de conexión a Neon: {e}")

    def crear_tablas(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT UNIQUE,
                    servicio TEXT,
                    precio REAL DEFAULT 0,
                    notas TEXT
                );
                CREATE TABLE IF NOT EXISTS ventas (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
                    producto TEXT,
                    total REAL,
                    pagado REAL,
                    pendiente REAL,
                    fecha_corta TEXT,
                    fecha_iso TEXT
                );
                CREATE TABLE IF NOT EXISTS gastos (
                    id SERIAL PRIMARY KEY,
                    descripcion TEXT,
                    monto REAL,
                    fecha_corta TEXT
                );
                CREATE TABLE IF NOT EXISTS blacklist (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
                    fecha_corta TEXT,
                    motivo TEXT
                );
                CREATE TABLE IF NOT EXISTS cierres (
                    fecha_corta TEXT PRIMARY KEY,
                    fondo_inicial REAL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS fondo_caja (
                    fecha_corta TEXT PRIMARY KEY,
                    monto REAL DEFAULT 0
                );
            """)
            self.conn.commit()
        except Exception as e:
            print(f"Error al crear tablas en Neon: {e}")

# ==========================================================================
# 2. APLICACIÓN PRINCIPAL FLET CON LOGIN Y ADAPTACIÓN MÓVIL
# ==========================================================================
def main(page: ft.Page):
    page.title = "Tienda Pantuj - Control Cloud"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 10
    page.spacing = 8
    page.window.width = 1280
    page.window.height = 880
    page.window.min_width = 360
    page.window.min_height = 600

    db = Database()
    
    C_CELESTE_PRINCIPAL = ft.Colors.CYAN_700
    C_GRIS_FONDO = ft.Colors.GREY_100
    C_GRIS_BORDE = ft.Colors.GREY_300
    C_TEXTO_NEGRO = ft.Colors.BLACK
    C_BLANCO = ft.Colors.WHITE

    def mostrar_snack(mensaje: str, es_error=False):
        color_bg = ft.Colors.RED_700 if es_error else C_CELESTE_PRINCIPAL
        snack = ft.SnackBar(
            content=ft.Text(mensaje, color=C_BLANCO, weight=ft.FontWeight.BOLD),
            bgcolor=color_bg,
            duration=2500
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # ======================================================================
    # PANTALLA PRINCIPAL DE LA TIENDA
    # ======================================================================
    def iniciar_sistema_tienda():
        page.clean()

        estado = {
            "fecha": datetime.date.today(),
            "carrusel_list": [],
            "carrusel_idx": 0,
            "tiene_deuda_previa": False,
            "edit_client_id": None
        }

        def es_dia_congelado():
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            db.cursor.execute("SELECT 1 FROM cierres WHERE fecha_corta=%s", (fecha_str,))
            return db.cursor.fetchone() is not None

        def cerrar_dialogo_seguro(dlg):
            dlg.open = False
            if dlg in page.overlay:
                page.overlay.remove(dlg)
            page.update()

        txt_titulo = ft.Text("🏪 Tienda Pantuj", size=20, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)
        lbl_fecha = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)
        
        badge_estado = ft.Container(padding=ft.Padding(8, 4, 8, 4), border_radius=6)
        lbl_badge_texto = ft.Text("", color=C_BLANCO, weight=ft.FontWeight.BOLD, size=11)
        badge_estado.content = lbl_badge_texto

        lbl_caja_total = ft.Text("Caja: Q 0.00", size=16, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_banner_texto = ft.Text("", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_800)
        
        container_alerta_cierres = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.WHITE, size=18),
                ft.Text("⚠️ Días pasados sin CERRAR CAJA.", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=12)
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.Colors.RED_800,
            padding=6,
            border_radius=6,
            visible=False
        )

        # PESTAÑA 1: OPERACIONES DIARIAS
        dt_activos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Detalle", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Real (Q)", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Debe (Q)", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        dt_inactivos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Inactivo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Motivo", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        tab_inicio = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("🟢 Cobros del Día", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_activos], expand=True),
                    ]),
                    expand=3, padding=10, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("⚫ Lista Negra / Ausentes", size=14, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_inactivos], expand=True),
                    ]),
                    expand=2, padding=10, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                )
            ], expand=True, spacing=8),
            padding=2, expand=True
        )

        # PESTAÑA 2: ARQUEO Y CAJA
        tf_fondo_base = ft.TextField(label="Fondo Inicial (Q)", width=180, keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        lbl_arqueo_fondo = ft.Text("Fondo Inicial: Q 0.00", size=13)
        lbl_arqueo_ventas = ft.Text("Ventas Directas: Q 0.00", size=13)
        lbl_arqueo_abonos = ft.Text("Abonos Cobrados: Q 0.00", size=13, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_arqueo_gastos = ft.Text("Retiros/Gastos: - Q 0.00", size=13, color=ft.Colors.RED_700)
        lbl_arqueo_total_fisico = ft.Text("TOTAL ESPERADO: Q 0.00", size=16, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)

        dt_abonos_hoy = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Concepto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto (Q)", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        def guardar_fondo_base(e):
            if es_dia_congelado():
                mostrar_snack("La caja está cerrada hoy.", es_error=True)
                return
            try:
                monto = float(tf_fondo_base.value) if tf_fondo_base.value else 0.0
                fecha_str = estado["fecha"].strftime("%Y-%m-%d")
                db.cursor.execute("INSERT INTO fondo_caja (fecha_corta, monto) VALUES (%s, %s) ON CONFLICT (fecha_corta) DO UPDATE SET monto = EXCLUDED.monto", (fecha_str, monto))
                db.conn.commit()
                mostrar_snack("Fondo inicial asignado.")
                refrescar_pantallas()
            except ValueError:
                mostrar_snack("Ingresa un monto numérico válido.", es_error=True)

        tab_caja = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("💵 Base Inicial", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                            ft.Divider(color=C_GRIS_BORDE),
                            ft.Row([tf_fondo_base, ft.Button("Asignar", on_click=guardar_fondo_base, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))]),
                            ft.Divider(color=C_GRIS_BORDE),
                            ft.Text("📊 Cuadre Físico", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                            lbl_arqueo_fondo, lbl_arqueo_ventas, lbl_arqueo_abonos, lbl_arqueo_gastos,
                            ft.Divider(color=C_GRIS_BORDE), lbl_arqueo_total_fisico
                        ], spacing=8),
                        width=360, padding=12, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("💰 Abonos de Hoy", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                            ft.Divider(color=C_GRIS_BORDE),
                            ft.ListView([dt_abonos_hoy], expand=True)
                        ]),
                        expand=True, padding=12, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                    )
                ], expand=True, spacing=10)
            ], expand=True),
            padding=2, expand=True
        )

        # PESTAÑA 3: CLIENTES
        tf_cli_nombre = ft.TextField(label="Nombre Completo", border_radius=8)
        tf_cli_servicio = ft.TextField(label="Servicio Predeterminado", border_radius=8)
        tf_cli_precio = ft.TextField(label="Tarifa Estándar (Q)", border_radius=8, keyboard_type=ft.KeyboardType.NUMBER)
        tf_cli_notas = ft.TextField(label="Notas / Contacto", multiline=True, min_lines=2, max_lines=3, border_radius=8)
        tf_cli_buscar = ft.TextField(label="🔍 Buscar Cliente", border_radius=8, width=250, on_change=lambda e: cargar_tabla_clientes())

        dt_clientes = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Nombre", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Servicio", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Tarifa", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        dialog_cliente = ft.AlertDialog(
            title=ft.Text("👤 Formulario de Cliente", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([tf_cli_nombre, tf_cli_servicio, tf_cli_precio, tf_cli_notas], width=350, height=260, spacing=8),
                padding=2
            ),
            actions=[]
        )

        dt_historial_cli = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Detalle")),
                ft.DataColumn(ft.Text("Pagado")),
                ft.DataColumn(ft.Text("Debe")),
            ],
            rows=[]
        )
        lbl_hist_cli_info = ft.Text("", size=12, weight=ft.FontWeight.W_500)

        dialog_historial = ft.AlertDialog(
            title=ft.Text("📜 Historial", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([lbl_hist_cli_info, ft.Divider(color=C_GRIS_BORDE), ft.ListView([dt_historial_cli], expand=True)], width=450, height=320, spacing=6),
                padding=2
            ),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo_seguro(dialog_historial))]
        )

        def abrir_modal_cliente(cid=None, nombre="", servicio="", precio="", notas=""):
            cerrar_dialogo_seguro(dialog_cliente)
            cerrar_dialogo_seguro(dialog_historial)

            estado["edit_client_id"] = cid
            tf_cli_nombre.value = nombre
            tf_cli_servicio.value = servicio
            tf_cli_precio.value = str(precio) if precio != "" else ""
            tf_cli_notas.value = notas

            dialog_cliente.title.value = "✏️ Editar Cliente" if cid else "➕ Nuevo Cliente"
            dialog_cliente.actions = [
                ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo_seguro(dialog_cliente)),
                ft.Button("Guardar", on_click=ejecutar_guardar_cliente, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))
            ]
            page.overlay.append(dialog_cliente)
            dialog_cliente.open = True
            page.update()

        def ejecutar_guardar_cliente(e):
            nombre = tf_cli_nombre.value.strip() if tf_cli_nombre.value else ""
            servicio = tf_cli_servicio.value.strip() if tf_cli_servicio.value else ""
            try:
                precio = float(tf_cli_precio.value) if tf_cli_precio.value else 0.0
            except ValueError:
                mostrar_snack("La tarifa debe ser numérica.", es_error=True)
                return

            if not nombre or not servicio:
                mostrar_snack("Nombre y servicio obligatorios.", es_error=True)
                return

            notas = tf_cli_notas.value.strip() if tf_cli_notas.value else ""
            try:
                if estado["edit_client_id"]:
                    db.cursor.execute("UPDATE clientes SET nombre=%s, servicio=%s, precio=%s, notas=%s WHERE id=%s",
                                      (nombre, servicio, precio, notas, estado["edit_client_id"]))
                    mostrar_snack("Cliente actualizado.")
                else:
                    db.cursor.execute("INSERT INTO clientes (nombre, servicio, precio, notas) VALUES (%s, %s, %s, %s)",
                                      (nombre, servicio, precio, notas))
                    mostrar_snack("Cliente guardado.")
                db.conn.commit()
                cerrar_dialogo_seguro(dialog_cliente)
                cargar_tabla_clientes()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error al guardar: {ex}", es_error=True)

        def ver_historial_cliente(cid, nombre, notas):
            cerrar_dialogo_seguro(dialog_historial)
            cerrar_dialogo_seguro(dialog_cliente)

            dt_historial_cli.rows = []
            lbl_hist_cli_info.value = f"Cliente: {nombre}\nNotas: {notas if notas else 'Ninguna'}"
            try:
                db.cursor.execute("SELECT fecha_corta, producto, pagado, pendiente FROM ventas WHERE cliente_id=%s ORDER BY id DESC", (cid,))
                ventas = db.cursor.fetchall()
                if not ventas:
                    dt_historial_cli.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text("Sin registros")), ft.DataCell(ft.Text("-")), ft.DataCell(ft.Text("-")), ft.DataCell(ft.Text("-"))]))
                else:
                    for v in ventas:
                        dt_historial_cli.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(v[0])),
                                ft.DataCell(ft.Text(v[1])),
                                ft.DataCell(ft.Text(f"Q {v[2]:.2f}")),
                                ft.DataCell(ft.Text(f"Q {v[3]:.2f}", color=ft.Colors.RED_700 if v[3] > 0 else ft.Colors.GREEN_700)),
                            ])
                        )
                page.overlay.append(dialog_historial)
                dialog_historial.open = True
                page.update()
            except Exception as ex:
                mostrar_snack(f"Error cargando historial: {ex}", es_error=True)

        tab_clientes = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Button("➕ Agregar", icon=ft.Icons.ADD, on_click=lambda e: abrir_modal_cliente(), style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)),
                    tf_cli_buscar
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color=C_GRIS_BORDE),
                ft.ListView([dt_clientes], expand=True)
            ], expand=True),
            padding=10, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, expand=True
        )

        # PESTAÑA 4: GASTOS
        tf_gas_desc = ft.TextField(label="Descripción del Gasto", border_radius=8)
        tf_gas_monto = ft.TextField(label="Monto Retirado (Q)", border_radius=8, keyboard_type=ft.KeyboardType.NUMBER)

        dt_gastos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Descripción", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto (Q)", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        def guardar_gasto_click(e):
            if es_dia_congelado():
                mostrar_snack("Caja congelada hoy.", es_error=True)
                return
            desc = tf_gas_desc.value.strip() if tf_gas_desc.value else ""
            try:
                monto = float(tf_gas_monto.value) if tf_gas_monto.value else 0.0
            except ValueError:
                mostrar_snack("Monto inválido.", es_error=True)
                return

            if not desc or monto <= 0:
                mostrar_snack("Datos de gasto incompletos.", es_error=True)
                return

            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            try:
                db.cursor.execute("INSERT INTO gastos (descripcion, monto, fecha_corta) VALUES (%s, %s, %s)", (desc, monto, fecha_str))
                db.conn.commit()
                tf_gas_desc.value = ""
                tf_gas_monto.value = ""
                mostrar_snack("Gasto registrado.")
                refrescar_pantallas()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error: {ex}", es_error=True)

        tab_gastos = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("💸 Salida de Efectivo", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        tf_gas_desc, tf_gas_monto,
                        ft.Button("💾 Registrar Gasto", icon=ft.Icons.MONEY_OFF, on_click=guardar_gasto_click, style=ft.ButtonStyle(bgcolor=ft.Colors.GREY_800, color=C_BLANCO))
                    ], spacing=10),
                    width=320, padding=12, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("📋 Egresos de Hoy", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_gastos], expand=True)
                    ]),
                    expand=True, padding=12, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                )
            ], expand=True, spacing=10),
            padding=2, expand=True
        )

        # PESTAÑA 5: DEUDAS
        lbl_total_deudas_global = ft.Text("Pendiente Global: Q 0.00", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700)

        dt_deudas = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Detalle", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Pagado", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Debe", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        tab_deudas = ft.Container(
            content=ft.Column([
                ft.Row([
                    lbl_total_deudas_global,
                    ft.IconButton(icon=ft.Icons.REFRESH, on_click=lambda e: cargar_tabla_deudas(), tooltip="Actualizar")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color=C_GRIS_BORDE),
                ft.ListView([dt_deudas], expand=True)
            ], expand=True),
            padding=10, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, expand=True
        )

        # PESTAÑA 6: HISTORIAL + EXCEL
        tf_hist_inicio = ft.TextField(label="Desde (YYYY-MM-DD)", value=datetime.date.today().strftime("%Y-%m-01"), width=150, border_radius=8)
        tf_hist_fin = ft.TextField(label="Hasta (YYYY-MM-DD)", value=datetime.date.today().strftime("%Y-%m-%d"), width=150, border_radius=8)

        dt_resumen_macro = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Concepto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto (Q)", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        dt_cronologico = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Ingreso", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        def procesar_historial_rango(e):
            f_ini = tf_hist_inicio.value.strip()
            f_fin = tf_hist_fin.value.strip()
            try:
                db.cursor.execute("SELECT SUM(pagado) FROM ventas WHERE fecha_corta BETWEEN %s AND %s", (f_ini, f_fin))
                t_ingresos = db.cursor.fetchone()[0] or 0.0

                db.cursor.execute("SELECT SUM(monto) FROM gastos WHERE fecha_corta BETWEEN %s AND %s", (f_ini, f_fin))
                t_gastos = db.cursor.fetchone()[0] or 0.0

                db.cursor.execute("SELECT SUM(pendiente) FROM ventas WHERE fecha_corta BETWEEN %s AND %s", (f_ini, f_fin))
                t_pendientes = db.cursor.fetchone()[0] or 0.0

                balance_neto = t_ingresos - t_gastos

                dt_resumen_macro.rows = [
                    ft.DataRow(cells=[ft.DataCell(ft.Text("(+) Bruto Recaudado")), ft.DataCell(ft.Text(f"Q {t_ingresos:.2f}"))]),
                    ft.DataRow(cells=[ft.DataCell(ft.Text("(-) Egresos / Retiros")), ft.DataCell(ft.Text(f"Q {t_gastos:.2f}"))]),
                    ft.DataCell(cells=[ft.DataCell(ft.Text("(=) SALDO NETO")), ft.DataCell(ft.Text(f"Q {balance_neto:.2f}", weight=ft.FontWeight.BOLD))]),
                    ft.DataCell(cells=[ft.DataCell(ft.Text("(*) Por Cobrar (Fiado)")), ft.DataCell(ft.Text(f"Q {t_pendientes:.2f}"))]),
                ]

                db.cursor.execute("""
                    SELECT DISTINCT fecha_corta FROM ventas WHERE fecha_corta BETWEEN %s AND %s
                    UNION SELECT fecha_corta FROM gastos WHERE fecha_corta BETWEEN %s AND %s ORDER BY fecha_corta ASC
                """, (f_ini, f_fin, f_ini, f_fin))

                dias = db.cursor.fetchall()
                dt_cronologico.rows = []
                for d in dias:
                    f_dia = d[0]
                    db.cursor.execute("SELECT SUM(pagado) FROM ventas WHERE fecha_corta=%s", (f_dia,))
                    ing_d = db.cursor.fetchone()[0] or 0.0

                    db.cursor.execute("SELECT 1 FROM cierres WHERE fecha_corta=%s", (f_dia,))
                    st = "🔒 Cerrado" if db.cursor.fetchone() else "⚠️ ABIERTO"

                    dt_cronologico.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(f_dia)),
                            ft.DataCell(ft.Text(f"Q {ing_d:.2f}")),
                            ft.DataCell(ft.Text(st, color=ft.Colors.GREEN_700 if "Cerrado" in st else ft.Colors.RED_700)),
                        ])
                    )

                exportar_reporte_excel(f_ini, f_fin, t_ingresos, t_gastos, balance_neto, t_pendientes)
                page.update()
            except Exception as ex:
                mostrar_snack(f"Error procesando: {ex}", es_error=True)

        def exportar_reporte_excel(f_ini, f_fin, ingresos, gastos, neto, pendientes):
            folder = "reportes_excel"
            if not os.path.exists(folder):
                os.makedirs(folder)
            archivo_path = f"{folder}/reporte_{f_ini}_a_{f_fin}.csv"
            
            try:
                with open(archivo_path, mode="w", newline="", encoding="utf-8-sig") as file:
                    writer = csv.writer(file, delimiter=";")
                    writer.writerow(["REPORTE FINANCIERO - TIENDA PANTUJ"])
                    writer.writerow(["Rango", f"Desde {f_ini} hasta {f_fin}"])
                    writer.writerow([])
                    writer.writerow(["RESUMEN", "MONTO"])
                    writer.writerow(["(+) Bruto", f"{ingresos:.2f}"])
                    writer.writerow(["(-) Gastos", f"{gastos:.2f}"])
                    writer.writerow(["(=) Neto", f"{neto:.2f}"])
                    writer.writerow(["(*) Fiado", f"{pendientes:.2f}"])

                mostrar_snack(f"📊 ¡Excel CSV guardado en {archivo_path}!")
            except Exception as ex:
                mostrar_snack(f"Error exportando: {ex}", es_error=True)

        tab_historial = ft.Container(
            content=ft.Column([
                ft.Row([
                    tf_hist_inicio, tf_hist_fin,
                    ft.Button("📊 Procesar / Excel", icon=ft.Icons.ANALYTICS, on_click=procesar_historial_rango, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)),
                ], alignment=ft.MainAxisAlignment.START, spacing=10),
                ft.Divider(color=C_GRIS_BORDE),
                ft.Row([
                    ft.Container(
                        content=ft.Column([ft.Text("📊 Métricas", size=14, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO), dt_resumen_macro]),
                        expand=1, padding=8, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8
                    ),
                    ft.Container(
                        content=ft.Column([ft.Text("📅 Días", size=14, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO), ft.ListView([dt_cronologico], expand=True)]),
                        expand=1, padding=8, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                    )
                ], expand=True, spacing=10)
            ], expand=True),
            padding=10, border=ft.Border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, clip_behavior=ft.ClipBehavior.ANTI_ALIAS, expand=True
        )

        # DIÁLOGO ABONO
        tf_abono_monto = ft.TextField(label="Monto de Abono (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        lbl_abono_info = ft.Text("", size=13, weight=ft.FontWeight.BOLD)

        dialog_abono = ft.AlertDialog(
            title=ft.Text("💰 Registrar Abono", weight=ft.FontWeight.BOLD),
            content=ft.Column([lbl_abono_info, tf_abono_monto], height=110, spacing=8),
            actions=[]
        )

        def abrir_dialogo_abono(v_id, cliente_nombre, pendiente_actual):
            cerrar_dialogo_seguro(dialog_abono)
            tf_abono_monto.value = ""

            def ejecutar_abono(e):
                try:
                    abono = float(tf_abono_monto.value)
                    if abono <= 0 or abono > pendiente_actual:
                        raise ValueError()
                except ValueError:
                    mostrar_snack("Monto inválido o mayor al saldo.", es_error=True)
                    return

                fecha_str = estado["fecha"].strftime("%Y-%m-%d")
                fecha_iso = datetime.datetime.now().isoformat()

                try:
                    db.cursor.execute("UPDATE ventas SET pagado = pagado + %s, pendiente = pendiente - %s WHERE id = %s", (abono, abono, v_id))
                    db.cursor.execute("SELECT cliente_id, producto FROM ventas WHERE id=%s", (v_id,))
                    c_id, prod_original = db.cursor.fetchone()

                    db.cursor.execute("""
                        INSERT INTO ventas (cliente_id, producto, total, pagado, pendiente, fecha_corta, fecha_iso)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (c_id, f"Abono a: {prod_original}", 0.0, abono, 0.0, fecha_str, fecha_iso))

                    db.conn.commit()
                    cerrar_dialogo_seguro(dialog_abono)
                    mostrar_snack(f"Abono de Q {abono:.2f} registrado.")
                    refrescar_pantallas()
                except Exception as ex:
                    db.conn.rollback()
                    mostrar_snack(f"Error en abono: {ex}", es_error=True)

            lbl_abono_info.value = f"Cliente: {cliente_nombre}\nDeuda: Q {pendiente_actual:.2f}"
            dialog_abono.actions = [
                ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo_seguro(dialog_abono)),
                ft.Button("Aplicar", on_click=ejecutar_abono, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))
            ]
            page.overlay.append(dialog_abono)
            dialog_abono.open = True
            page.update()

        # CARRUSEL
        lbl_car_idx = ft.Text("", size=11, italic=True)
        lbl_car_name = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_car_info = ft.Text("", size=13)
        lbl_car_alerta = ft.Text("", size=12, color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD)

        tf_car_desc = ft.TextField(label="Detalle del Trabajo", border_radius=8)
        tf_car_total = ft.TextField(label="Total (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        tf_car_pago = ft.TextField(label="Efectivo en Caja (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        tf_car_abono_v = ft.TextField(label="Abono a Deuda Anterior (Q)", value="0.00", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)

        col_form_carrusel = ft.Column([tf_car_desc, tf_car_total, tf_car_pago, lbl_car_alerta, tf_car_abono_v], visible=False, spacing=8)
        col_preg_carrusel = ft.Column([], visible=True, spacing=8)

        dialog_carrusel = ft.AlertDialog(
            title=ft.Row([ft.Text("⚡ Carrusel Diario", weight=ft.FontWeight.BOLD), lbl_car_idx], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                content=ft.Column([lbl_car_name, lbl_car_info, ft.Divider(color=C_GRIS_BORDE), col_preg_carrusel, col_form_carrusel], height=340, width=380, spacing=8),
                padding=2
            ),
            actions=[]
        )

        def cargar_cliente_carrusel():
            if not estado["carrusel_list"] or estado["carrusel_idx"] >= len(estado["carrusel_list"]):
                cerrar_dialogo_seguro(dialog_carrusel)
                mostrar_snack("¡Clientes de hoy procesados!")
                refrescar_pantallas()
                return

            cli = estado["carrusel_list"][estado["carrusel_idx"]]
            c_id, c_name, c_serv, c_price, c_notes = cli

            lbl_car_idx.value = f"Cliente {estado['carrusel_idx'] + 1} de {len(estado['carrusel_list'])}"
            lbl_car_name.value = c_name
            lbl_car_info.value = f"Servicio: {c_serv}\nTarifa: Q {c_price:.2f}\nNotas: {c_notes if c_notes else 'Ninguna'}"

            tf_car_desc.value = c_serv
            tf_car_total.value = str(c_price)
            tf_car_pago.value = str(c_price)
            tf_car_abono_v.value = "0.00"

            db.cursor.execute("SELECT SUM(pendiente) FROM ventas WHERE cliente_id=%s", (c_id,))
            res_deuda = db.cursor.fetchone()
            deuda_total = res_deuda[0] if res_deuda and res_deuda[0] else 0.0

            if deuda_total > 0:
                estado["tiene_deuda_previa"] = True
                lbl_car_alerta.value = f"⚠️ Deuda anterior pendiente: Q {deuda_total:.2f}"
                lbl_car_alerta.visible = True
                tf_car_abono_v.visible = True
            else:
                estado["tiene_deuda_previa"] = False
                lbl_car_alerta.visible = False
                tf_car_abono_v.visible = False

            col_preg_carrusel.visible = True
            col_form_carrusel.visible = False
            actualizar_botones_carrusel()
            page.update()

        def mostrar_formulario_carrusel():
            col_preg_carrusel.visible = False
            col_form_carrusel.visible = True
            actualizar_botones_carrusel()
            page.update()

        def carrusel_marcar_inactivo():
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            cli = estado["carrusel_list"][estado["carrusel_idx"]]
            try:
                db.cursor.execute("INSERT INTO blacklist (cliente_id, fecha_corta, motivo) VALUES (%s, %s, %s)", (cli[0], fecha_str, "Ausente"))
                db.conn.commit()
                estado["carrusel_list"].pop(estado["carrusel_idx"])
                if estado["carrusel_idx"] >= len(estado["carrusel_list"]):
                    estado["carrusel_idx"] = max(0, len(estado["carrusel_list"]) - 1)
                cargar_cliente_carrusel()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error: {ex}", es_error=True)

        def registrar_operacion_carrusel():
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            fecha_iso = datetime.datetime.now().isoformat()
            cli = estado["carrusel_list"][estado["carrusel_idx"]]
            c_id = cli[0]

            try:
                desc = tf_car_desc.value.strip() if tf_car_desc.value else ""
                tot = float(tf_car_total.value)
                pag = float(tf_car_pago.value)
                abono_v = float(tf_car_abono_v.value) if (estado["tiene_deuda_previa"] and tf_car_abono_v.value) else 0.0

                if tot < 0 or pag < 0 or abono_v < 0:
                    raise ValueError()
            except ValueError:
                mostrar_snack("Valores numéricos inválidos.", es_error=True)
                return

            pendiente_hoy = max(0.0, tot - pag)

            try:
                db.cursor.execute("""
                    INSERT INTO ventas (cliente_id, producto, total, pagado, pendiente, fecha_corta, fecha_iso)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (c_id, desc, tot, pag, pendiente_hoy, fecha_str, fecha_iso))

                if abono_v > 0:
                    db.cursor.execute("SELECT id, pendiente FROM ventas WHERE cliente_id=%s AND pendiente > 0 ORDER BY id ASC", (c_id,))
                    deudas_viejas = db.cursor.fetchall()
                    por_abonar = abono_v
                    for v_id, v_pend in deudas_viejas:
                        if por_abonar <= 0: break
                        if por_abonar >= v_pend:
                            db.cursor.execute("UPDATE ventas SET pagado = pagado + %s, pendiente = 0 WHERE id = %s", (v_pend, v_id))
                            por_abonar -= v_pend
                        else:
                            db.cursor.execute("UPDATE ventas SET pagado = pagado + %s, pendiente = pendiente - %s WHERE id = %s", (por_abonar, por_abonar, v_id))
                            por_abonar = 0

                    db.cursor.execute("""
                        INSERT INTO ventas (cliente_id, producto, total, pagado, pendiente, fecha_corta, fecha_iso)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (c_id, f"Abono a deudas de {cli[1]}", 0.0, abono_v, 0.0, fecha_str, fecha_iso))

                db.conn.commit()
                estado["carrusel_list"].pop(estado["carrusel_idx"])
                if estado["carrusel_idx"] >= len(estado["carrusel_list"]):
                    estado["carrusel_idx"] = max(0, len(estado["carrusel_list"]) - 1)
                cargar_cliente_carrusel()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error al guardar: {ex}", es_error=True)

        def nav_carrusel(delta):
            nuevo_idx = estado["carrusel_idx"] + delta
            if 0 <= nuevo_idx < len(estado["carrusel_list"]):
                estado["carrusel_idx"] = nuevo_idx
                cargar_cliente_carrusel()

        col_preg_carrusel.controls = [
            ft.Button("🟢 TRABAJÓ HOY", on_click=lambda e: mostrar_formulario_carrusel(), style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO), width=350),
            ft.Button("⚫ AUSENTE", on_click=lambda e: carrusel_marcar_inactivo(), style=ft.ButtonStyle(bgcolor=ft.Colors.GREY_800, color=C_BLANCO), width=350),
        ]

        def actualizar_botones_carrusel():
            if col_form_carrusel.visible:
                dialog_carrusel.actions = [
                    ft.TextButton("⬅️ Volver", on_click=lambda e: cargar_cliente_carrusel()),
                    ft.Button("💾 Guardar", on_click=lambda e: registrar_operacion_carrusel(), style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))
                ]
            else:
                dialog_carrusel.actions = [
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: nav_carrusel(-1)),
                    ft.IconButton(icon=ft.Icons.ARROW_FORWARD, on_click=lambda e: nav_carrusel(1)),
                    ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo_seguro(dialog_carrusel))
                ]

        def abrir_carrusel_click(e):
            if es_dia_congelado():
                mostrar_snack("Caja congelada hoy.", es_error=True)
                return

            cerrar_dialogo_seguro(dialog_carrusel)
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            try:
                db.cursor.execute("""
                    SELECT id, nombre, servicio, precio, notas FROM clientes 
                    WHERE id NOT IN (SELECT cliente_id FROM ventas WHERE fecha_corta=%s)
                    AND id NOT IN (SELECT cliente_id FROM blacklist WHERE fecha_corta=%s)
                    ORDER BY nombre ASC
                """, (fecha_str, fecha_str))
                estado["carrusel_list"] = db.cursor.fetchall()

                if not estado["carrusel_list"]:
                    mostrar_snack("🎉 ¡Todos los clientes ya fueron procesados!")
                    return

                estado["carrusel_idx"] = 0
                page.overlay.append(dialog_carrusel)
                dialog_carrusel.open = True
                cargar_cliente_carrusel()
            except Exception as ex:
                mostrar_snack(f"Error en carrusel: {ex}", es_error=True)

        # CARGAR TABLAS Y DATOS
        def cargar_tabla_activos_inactivos():
            dt_activos.rows = []
            dt_inactivos.rows = []
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")

            try:
                db.cursor.execute("""
                    SELECT v.id, c.nombre, v.producto, v.pagado, v.pendiente 
                    FROM ventas v JOIN clientes c ON v.cliente_id = c.id WHERE v.fecha_corta=%s
                """, (fecha_str,))
                for r in db.cursor.fetchall():
                    dt_activos.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(r[1], color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(r[2], color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {r[3]:.2f}", color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {r[4]:.2f}", color=ft.Colors.RED_700 if r[4] > 0 else C_TEXTO_NEGRO)),
                        ])
                    )

                db.cursor.execute("""
                    SELECT b.id, c.nombre, b.motivo FROM blacklist b 
                    JOIN clientes c ON b.cliente_id = c.id WHERE b.fecha_corta=%s
                """, (fecha_str,))
                for r in db.cursor.fetchall():
                    b_id, c_nombre, motivo = r

                    def restaurar_inactivo_fn(e, bid=b_id, name=c_nombre):
                        if es_dia_congelado():
                            mostrar_snack("Caja congelada.", es_error=True)
                            return
                        try:
                            db.cursor.execute("DELETE FROM blacklist WHERE id=%s", (bid,))
                            db.conn.commit()
                            mostrar_snack(f"'{name}' restaurado.")
                            refrescar_pantallas()
                        except Exception as ex:
                            db.conn.rollback()
                            mostrar_snack(f"Error: {ex}", es_error=True)

                    dt_inactivos.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(b_id), color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(c_nombre, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(motivo, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Button("↺", on_click=restaurar_inactivo_fn, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))),
                        ])
                    )
            except Exception as ex:
                print(f"Error cargando día: {ex}")

        def cargar_datos_caja():
            dt_abonos_hoy.rows = []
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")

            try:
                db.cursor.execute("SELECT monto FROM fondo_caja WHERE fecha_corta=%s", (fecha_str,))
                row_f = db.cursor.fetchone()
                fondo_monto = row_f[0] if row_f else 0.0
                tf_fondo_base.value = str(fondo_monto)
                lbl_arqueo_fondo.value = f"Fondo Inicial: Q {fondo_monto:.2f}"

                db.cursor.execute("SELECT SUM(pagado) FROM ventas WHERE fecha_corta=%s AND producto NOT LIKE 'Abono%%'", (fecha_str,))
                v_sum = db.cursor.fetchone()[0] or 0.0
                lbl_arqueo_ventas.value = f"Ventas Directas: Q {v_sum:.2f}"

                db.cursor.execute("""
                    SELECT c.nombre, v.producto, v.pagado FROM ventas v 
                    JOIN clientes c ON v.cliente_id = c.id 
                    WHERE v.fecha_corta=%s AND v.producto LIKE 'Abono%%'
                """, (fecha_str,))
                abonos_filas = db.cursor.fetchall()
                abonos_sum = 0.0

                for ab in abonos_filas:
                    abonos_sum += ab[2]
                    dt_abonos_hoy.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(ab[0], color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(ab[1], color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {ab[2]:.2f}", color=C_CELESTE_PRINCIPAL, weight=ft.FontWeight.BOLD)),
                        ])
                    )
                lbl_arqueo_abonos.value = f"Abonos Cobrados: Q {abonos_sum:.2f}"

                db.cursor.execute("SELECT SUM(monto) FROM gastos WHERE fecha_corta=%s", (fecha_str,))
                g_sum = db.cursor.fetchone()[0] or 0.0
                lbl_arqueo_gastos.value = f"Retiros/Gastos: - Q {g_sum:.2f}"

                total_esperado = fondo_monto + v_sum + abonos_sum - g_sum
                lbl_arqueo_total_fisico.value = f"TOTAL ESPERADO: Q {total_esperado:.2f}"
                lbl_caja_total.value = f"Caja: Q {(v_sum + abonos_sum - g_sum):.2f}"
            except Exception as ex:
                print(f"Error caja: {ex}")

        def cargar_tabla_clientes():
            dt_clientes.rows.clear()
            busqueda = f"%{tf_cli_buscar.value.strip()}%" if tf_cli_buscar.value else "%"
            try:
                db.cursor.execute("SELECT id, nombre, servicio, precio, notas FROM clientes WHERE nombre ILIKE %s ORDER BY nombre ASC", (busqueda,))
                filas_db = db.cursor.fetchall()
                
                nuevas_filas = []
                for r in filas_db:
                    c_id, nombre, servicio, precio, notas = r

                    def editar_fn(e, cid=c_id, n=nombre, s=servicio, p=precio, nt=notas):
                        abrir_modal_cliente(cid, n, s, p, nt)

                    def borrar_fn(e, cid=c_id, n=nombre):
                        try:
                            db.cursor.execute("DELETE FROM clientes WHERE id=%s", (cid,))
                            db.conn.commit()
                            cargar_tabla_clientes()
                            mostrar_snack(f"Cliente '{n}' eliminado.")
                        except Exception as ex:
                            db.conn.rollback()
                            mostrar_snack(f"Error: {ex}", es_error=True)

                    def ver_hist_fn(e, cid=c_id, n=nombre, nt=notas):
                        ver_historial_cliente(cid, n, nt)

                    nuevas_filas.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(c_id), color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(nombre, color=C_TEXTO_NEGRO, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(servicio, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {precio:.2f}", color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Row([
                                ft.IconButton(icon=ft.Icons.REMOVE_RED_EYE, icon_color=C_CELESTE_PRINCIPAL, on_click=ver_hist_fn, tooltip="Historial"),
                                ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.GREY_700, on_click=editar_fn, tooltip="Editar"),
                                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_600, on_click=borrar_fn, tooltip="Eliminar"),
                            ], spacing=0)),
                        ])
                    )
                dt_clientes.rows = nuevas_filas
                page.update()
            except Exception as ex:
                print(f"Error clientes: {ex}")

        def cargar_tabla_gastos():
            dt_gastos.rows = []
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            try:
                db.cursor.execute("SELECT id, descripcion, monto FROM gastos WHERE fecha_corta=%s", (fecha_str,))
                for r in db.cursor.fetchall():
                    g_id, desc, monto = r

                    def eliminar_gasto_fn(e, gid=g_id):
                        if es_dia_congelado():
                            mostrar_snack("Caja congelada.", es_error=True)
                            return
                        try:
                            db.cursor.execute("DELETE FROM gastos WHERE id=%s", (gid,))
                            db.conn.commit()
                            refrescar_pantallas()
                            mostrar_snack("Gasto eliminado.")
                        except Exception as ex:
                            db.conn.rollback()
                            mostrar_snack(f"Error: {ex}", es_error=True)

                    dt_gastos.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(g_id), color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(desc, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {monto:.2f}", color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_600, on_click=eliminar_gasto_fn, tooltip="Borrar")),
                        ])
                    )
            except Exception as ex:
                print(f"Error gastos: {ex}")

        def cargar_tabla_deudas():
            dt_deudas.rows = []
            try:
                db.cursor.execute("""
                    SELECT v.id, v.fecha_corta, c.nombre, v.producto, v.total, v.pagado, v.pendiente 
                    FROM ventas v JOIN clientes c ON v.cliente_id = c.id WHERE v.pendiente > 0 ORDER BY v.id DESC
                """)
                deudas = db.cursor.fetchall()
                suma_global = 0.0
                for r in deudas:
                    v_id, fecha, cliente, producto, total, pagado, pendiente = r
                    suma_global += pendiente

                    def abono_fn(e, vid=v_id, cname=cliente, pend=pendiente):
                        abrir_dialogo_abono(vid, cname, pend)

                    dt_deudas.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(str(v_id), color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(fecha, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(cliente, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(producto, color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {total:.2f}", color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {pagado:.2f}", color=C_TEXTO_NEGRO)),
                            ft.DataCell(ft.Text(f"Q {pendiente:.2f}", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Button("💰", on_click=abono_fn, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))),
                        ])
                    )
                lbl_total_deudas_global.value = f"Pendiente Global: Q {suma_global:.2f}"
            except Exception as ex:
                print(f"Error deudas: {ex}")

        def verificar_cierres_olvidados():
            hoy_str = datetime.date.today().strftime("%Y-%m-%d")
            try:
                db.cursor.execute("""
                    SELECT DISTINCT fecha_corta FROM ventas WHERE fecha_corta < %s AND fecha_corta NOT IN (SELECT fecha_corta FROM cierres)
                    UNION SELECT DISTINCT fecha_corta FROM gastos WHERE fecha_corta < %s AND fecha_corta NOT IN (SELECT fecha_corta FROM cierres)
                """, (hoy_str, hoy_str))
                olvidados = db.cursor.fetchall()
                container_alerta_cierres.visible = len(olvidados) > 0
            except Exception as ex:
                print(f"Error cierres: {ex}")

        def refrescar_pantallas():
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            lbl_fecha.value = fecha_str

            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            lbl_banner_texto.value = f"📅 {dias[estado['fecha'].weekday()]} {estado['fecha'].day}/{meses[estado['fecha'].month - 1]}/{estado['fecha'].year}"

            if es_dia_congelado():
                badge_estado.bgcolor = ft.Colors.RED_700
                lbl_badge_texto.value = "🔒 CERRADO"
                btn_carrusel.disabled = True
                btn_cerrar_caja.visible = False
                btn_abrir_caja.visible = True
            else:
                badge_estado.bgcolor = C_CELESTE_PRINCIPAL
                lbl_badge_texto.value = "🟢 ABIERTO"
                btn_carrusel.disabled = False
                btn_cerrar_caja.visible = True
                btn_abrir_caja.visible = False

            verificar_cierres_olvidados()
            cargar_tabla_activos_inactivos()
            cargar_datos_caja()
            cargar_tabla_gastos()
            cargar_tabla_deudas()
            page.update()

        def cambiar_dia(delta):
            estado["fecha"] += datetime.timedelta(days=delta)
            refrescar_pantallas()

        def ir_a_hoy(e):
            estado["fecha"] = datetime.date.today()
            refrescar_pantallas()

        def ejecutar_cierre_dia(e):
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            try:
                db.cursor.execute("SELECT id, nombre FROM clientes")
                all_clients = db.cursor.fetchall()
                faltantes = []

                for c_id, c_name in all_clients:
                    db.cursor.execute("SELECT 1 FROM ventas WHERE cliente_id=%s AND fecha_corta=%s", (c_id, fecha_str))
                    has_v = db.cursor.fetchone()
                    db.cursor.execute("SELECT 1 FROM blacklist WHERE cliente_id=%s AND fecha_corta=%s", (c_id, fecha_str))
                    has_b = db.cursor.fetchone()
                    if not has_v and not has_b:
                        faltantes.append(c_name)

                if faltantes:
                    mostrar_snack(f"🚫 Faltan clientes por procesar hoy.", es_error=True)
                    return

                db.cursor.execute("INSERT INTO cierres (fecha_corta) VALUES (%s) ON CONFLICT (fecha_corta) DO NOTHING", (fecha_str,))
                db.conn.commit()
                mostrar_snack("🔒 Caja cerrada con éxito.")
                refrescar_pantallas()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error cerrando: {ex}", es_error=True)

        def ejecutar_apertura_dia(e):
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            try:
                db.cursor.execute("DELETE FROM cierres WHERE fecha_corta=%s", (fecha_str,))
                db.conn.commit()
                mostrar_snack("🔓 Caja reabierta.")
                refrescar_pantallas()
            except Exception as ex:
                db.conn.rollback()
                mostrar_snack(f"Error abriendo: {ex}", es_error=True)

        def toggle_theme(e):
            if page.theme_mode == ft.ThemeMode.LIGHT:
                page.theme_mode = ft.ThemeMode.DARK
                btn_theme.icon = ft.Icons.LIGHT_MODE
            else:
                page.theme_mode = ft.ThemeMode.LIGHT
                btn_theme.icon = ft.Icons.DARK_MODE
            page.update()

        btn_carrusel = ft.Button("⚡ Carrusel", icon=ft.Icons.FLASHLIGHT_ON, on_click=abrir_carrusel_click, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))
        btn_cerrar_caja = ft.Button("🔒 Cerrar", icon=ft.Icons.LOCK, on_click=ejecutar_cierre_dia, style=ft.ButtonStyle(bgcolor=ft.Colors.GREY_800, color=C_BLANCO))
        btn_abrir_caja = ft.Button("🔓 Reabrir", icon=ft.Icons.LOCK_OPEN, on_click=ejecutar_apertura_dia, style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_800, color=C_BLANCO), visible=False)
        btn_theme = ft.IconButton(icon=ft.Icons.DARK_MODE, on_click=toggle_theme, tooltip="Tema")

        header_bar = ft.Container(
            content=ft.Row([
                txt_titulo,
                ft.Row([
                    ft.IconButton(icon=ft.Icons.ARROW_BACK_IOS, icon_size=16, on_click=lambda e: cambiar_dia(-1)),
                    lbl_fecha,
                    ft.IconButton(icon=ft.Icons.ARROW_FORWARD_IOS, icon_size=16, on_click=lambda e: cambiar_dia(1)),
                    badge_estado,
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                lbl_caja_total
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=8, bgcolor=C_GRIS_FONDO, border_radius=8, border=ft.Border.all(1, C_GRIS_BORDE)
        )

        action_bar = ft.Container(
            content=ft.Row([lbl_banner_texto, ft.Row([btn_carrusel, btn_cerrar_caja, btn_abrir_caja], spacing=6)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=4
        )

        tab_views = [tab_inicio, tab_caja, tab_clientes, tab_gastos, tab_deudas, tab_historial]
        content_area = ft.Container(content=tab_views[0], expand=True)

        def cambiar_pestana(idx):
            content_area.content = tab_views[idx]
            if idx == 2:
                cargar_tabla_clientes()
            for i, btn in enumerate(nav_buttons.controls):
                btn.style = ft.ButtonStyle(
                    bgcolor=C_CELESTE_PRINCIPAL if i == idx else C_GRIS_FONDO,
                    color=C_BLANCO if i == idx else C_TEXTO_NEGRO
                )
            page.update()

        nav_buttons = ft.Row([
            ft.Button("📊 Hoy", on_click=lambda e: cambiar_pestana(0), style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)),
            ft.Button("💵 Caja", on_click=lambda e: cambiar_pestana(1), style=ft.ButtonStyle(bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO)),
            ft.Button("👤 Clientes", on_click=lambda e: cambiar_pestana(2), style=ft.ButtonStyle(bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO)),
            ft.Button("💸 Gastos", on_click=lambda e: cambiar_pestana(3), style=ft.ButtonStyle(bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO)),
            ft.Button("🔴 Deudas", on_click=lambda e: cambiar_pestana(4), style=ft.ButtonStyle(bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO)),
            ft.Button("📋 Reportes", on_click=lambda e: cambiar_pestana(5), style=ft.ButtonStyle(bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO)),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

        page.add(header_bar, container_alerta_cierres, action_bar, nav_buttons, content_area)
        refrescar_pantallas()

    # ======================================================================
    # 3. LOGIN SEGURO INICIAL
    # ======================================================================
    tf_user = ft.TextField(label="Usuario", width=260, border_radius=8)
    tf_pass = ft.TextField(label="Contraseña", width=260, password=True, can_reveal_password=True, border_radius=8)
    lbl_error_login = ft.Text("", color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD, size=13)

    def validar_login(e):
        usuario = tf_user.value.strip() if tf_user.value else ""
        password = tf_pass.value.strip() if tf_pass.value else ""
        
        if usuario == "admin" and password == "pantuj2026":
            iniciar_sistema_tienda()
        else:
            lbl_error_login.value = "❌ Credenciales incorrectas"
            page.update()

    container_login = ft.Container(
        content=ft.Column([
            ft.Text("🔐 Acceso Tienda Pantuj", size=22, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
            ft.Text("Control en la Nube", size=13, color=ft.Colors.GREY_700),
            ft.Divider(color=C_GRIS_BORDE),
            tf_user,
            tf_pass,
            lbl_error_login,
            ft.Button("Ingresar", on_click=validar_login, style=ft.ButtonStyle(bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO))
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.Alignment(0, 0),
        expand=True
    )

    page.add(container_login)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    ft.run(main, host="0.0.0.0", port=port)