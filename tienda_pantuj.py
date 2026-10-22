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
        self.conn = None
        self.cursor = None
        try:
            self.conn = psycopg2.connect(self.db_url, connect_timeout=10)
            self.cursor = self.conn.cursor()
            self.crear_tablas()
        except Exception as e:
            if self.conn:
                self.conn.close()
            raise RuntimeError(f"No se pudo conectar con Neon: {e}") from e

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
# 2. APLICACIÓN PRINCIPAL FLET ADAPTATIVA (PC Y MÓVIL)
# ==========================================================================
def main(page: ft.Page):
    page.title = "Tienda Pantuj - Control Cloud"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 6
    page.spacing = 6
    page.adaptive = True

    db = Database()
    
    C_CELESTE_PRINCIPAL = ft.colors.CYAN_700
    C_GRIS_FONDO = ft.colors.GREY_100
    C_GRIS_BORDE = ft.colors.GREY_300
    C_TEXTO_NEGRO = ft.colors.BLACK
    C_BLANCO = ft.colors.WHITE

    def mostrar_snack(mensaje: str, es_error=False):
        color_bg = ft.colors.RED_700 if es_error else C_CELESTE_PRINCIPAL
        snack = ft.SnackBar(
            content=ft.Text(mensaje, color=C_BLANCO, weight=ft.FontWeight.BOLD),
            bgcolor=color_bg,
            duration=2500
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def iniciar_sistema_tienda():
        page.clean()

        estado = {
            "fecha": datetime.date.today(),
            "carrusel_list": [],
            "carrusel_idx": 0,
            "tiene_deuda_previa": False,
            "edit_client_id": None,
            "edit_venta_id": None
        }

        def es_dia_congelado():
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            db.cursor.execute("SELECT 1 FROM cierres WHERE fecha_corta=%s", (fecha_str,))
            return db.cursor.fetchone() is not None

        def cerrar_dialogo_seguro(dlg):
            try:
                dlg.open = False
                page.update()
            except Exception as ex:
                print(f"No se pudo cerrar el diálogo: {ex}")

        txt_titulo = ft.Text("🏪 Tienda Pantuj", size=15, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)
        lbl_fecha = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)
        
        badge_estado = ft.Container(padding=ft.padding.symmetric(horizontal=4, vertical=2), border_radius=4)
        lbl_badge_texto = ft.Text("", color=C_BLANCO, weight=ft.FontWeight.BOLD, size=9)
        badge_estado.content = lbl_badge_texto

        lbl_caja_total = ft.Text("Caja: Q 0.00", size=13, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_banner_texto = ft.Text("", size=11, weight=ft.FontWeight.W_500, color=ft.colors.GREY_800)
        
        container_alerta_cierres = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.WHITE, size=14),
                ft.Text("⚠️ Días recientes sin cerrar caja.", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD, size=10)
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.colors.RED_800,
            padding=3,
            border_radius=4,
            visible=False
        )

        lista_activos_movil = ft.ListView([], expand=True, spacing=6)
        dt_activos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Detalle", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Real", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Debe", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
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
                        ft.Text("🟢 Cobros del Día", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        lista_activos_movil if page.width <= 700 else ft.ListView([dt_activos], expand=True),
                    ], expand=True),
                    expand=3, padding=6, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("⚫ Lista Negra / Ausentes", size=12, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_inactivos], expand=True),
                    ], expand=True),
                    expand=2, padding=6, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                )
            ], expand=True, spacing=6),
            padding=2, expand=True
        )

        tf_edit_v_prod = ft.TextField(label="Detalle / Producto", border_radius=8)
        tf_edit_v_pagado = ft.TextField(label="Pagado / Real (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        tf_edit_v_pendiente = ft.TextField(label="Pendiente / Debe (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        lbl_edit_v_info = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)

        dialog_editar_venta = ft.AlertDialog(
            title=ft.Text("✏️ Modificar Cobro del Día", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([lbl_edit_v_info, tf_edit_v_prod, tf_edit_v_pagado, tf_edit_v_pendiente], width=300, height=220, spacing=6),
                padding=2
            ),
            actions=[]
        )

        def abrir_modal_editar_venta(v_id, cliente_nombre, prod, pagado, pendiente):
            if es_dia_congelado():
                mostrar_snack("Caja congelada hoy. No se puede modificar.", es_error=True)
                return
            cerrar_dialogo_seguro(dialog_editar_venta)
            estado["edit_venta_id"] = v_id
            lbl_edit_v_info.value = f"Cliente: {cliente_nombre}"
            tf_edit_v_prod.value = prod
            tf_edit_v_pagado.value = str(pagado)
            tf_edit_v_pendiente.value = str(pendiente)

            def guardar_edicion_venta(e):
                try:
                    p_nuevo = float(tf_edit_v_pagado.value)
                    pend_nuevo = float(tf_edit_v_pendiente.value)
                    if p_nuevo < 0 or pend_nuevo < 0:
                        raise ValueError()
                except ValueError:
                    mostrar_snack("Los montos deben ser numéricos válidos.", es_error=True)
                    return

                prod_nuevo = tf_edit_v_prod.value.strip()
                total_nuevo = p_nuevo + pend_nuevo

                try:
                    db.cursor.execute("""
                        UPDATE ventas SET producto=%s, total=%s, pagado=%s, pendiente=%s WHERE id=%s
                    """, (prod_nuevo, total_nuevo, p_nuevo, pend_nuevo, estado["edit_venta_id"]))
                    db.conn.commit()
                    cerrar_dialogo_seguro(dialog_editar_venta)
                    mostrar_snack("Cobro actualizado correctamente.")
                    refrescar_pantallas()
                except Exception as ex:
                    db.conn.rollback()
                    mostrar_snack(f"Error al actualizar: {ex}", es_error=True)

            dialog_editar_venta.actions = [
                ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo_seguro(dialog_editar_venta)),
                ft.ElevatedButton("Guardar", on_click=guardar_edicion_venta, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
            ]
            if dialog_editar_venta not in page.overlay:
                page.overlay.append(dialog_editar_venta)
            dialog_editar_venta.open = True
            page.update()

        tf_fondo_base = ft.TextField(label="Fondo Inicial (Q)", width=150, keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        lbl_arqueo_fondo = ft.Text("Fondo Inicial: Q 0.00", size=11)
        lbl_arqueo_ventas = ft.Text("Ventas Directas: Q 0.00", size=11)
        lbl_arqueo_abonos = ft.Text("Abonos Cobrados: Q 0.00", size=11, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_arqueo_gastos = ft.Text("Retiros/Gastos: - Q 0.00", size=11, color=ft.colors.RED_700)
        lbl_arqueo_total_fisico = ft.Text("TOTAL ESPERADO: Q 0.00", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO)

        dt_abonos_hoy = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cliente", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Concepto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        def guardar_fondo_base(e):
            if es_dia_congelado():
                mostrar_snack("La caja está cerrada hoy.", es_error=True)
                return
            try:
                monto = float(tf_fondo_base.value) if tf_fondo_base.value else 0.0
                if monto < 0:
                    raise ValueError()
                fecha_str = estado["fecha"].strftime("%Y-%m-%d")
                db.cursor.execute("INSERT INTO fondo_caja (fecha_corta, monto) VALUES (%s, %s) ON CONFLICT (fecha_corta) DO UPDATE SET monto = EXCLUDED.monto", (fecha_str, monto))
                db.conn.commit()
                mostrar_snack("Fondo inicial asignado.")
                refrescar_pantallas()
            except ValueError:
                mostrar_snack("Ingresa un monto válido y positivo.", es_error=True)

        tab_caja = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("💵 Base Inicial y Cuadre", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.Row([tf_fondo_base, ft.ElevatedButton("Asignar", on_click=guardar_fondo_base, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)]),
                        ft.Divider(color=C_GRIS_BORDE),
                        lbl_arqueo_fondo, lbl_arqueo_ventas, lbl_arqueo_abonos, lbl_arqueo_gastos,
                        ft.Divider(color=C_GRIS_BORDE), lbl_arqueo_total_fisico
                    ], spacing=4),
                    padding=8, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("💰 Abonos de Hoy", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_abonos_hoy], expand=True)
                    ], expand=True),
                    expand=True, padding=8, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                )
            ], expand=True, spacing=6),
            padding=2, expand=True
        )

        tf_cli_nombre = ft.TextField(label="Nombre Completo", border_radius=8)
        tf_cli_servicio = ft.TextField(label="Servicio Predeterminado", border_radius=8)
        tf_cli_precio = ft.TextField(label="Tarifa Estándar (Q)", border_radius=8, keyboard_type=ft.KeyboardType.NUMBER)
        tf_cli_notas = ft.TextField(label="Notas / Contacto", multiline=True, min_lines=2, max_lines=3, border_radius=8)
        tf_cli_buscar = ft.TextField(label="🔍 Buscar Cliente", border_radius=8, expand=True, on_change=lambda e: cargar_tabla_clientes())

        lista_clientes_movil = ft.ListView([], expand=True, spacing=6)

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
                content=ft.Column([tf_cli_nombre, tf_cli_servicio, tf_cli_precio, tf_cli_notas], width=300, height=240, spacing=6),
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
        lbl_hist_cli_info = ft.Text("", size=11, weight=ft.FontWeight.W_500)

        dialog_historial = ft.AlertDialog(
            title=ft.Text("📜 Historial", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([lbl_hist_cli_info, ft.Divider(color=C_GRIS_BORDE), ft.ListView([dt_historial_cli], expand=True)], width=320, height=280, spacing=4),
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
                ft.ElevatedButton("Guardar", on_click=ejecutar_guardar_cliente, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
            ]
            if dialog_cliente not in page.overlay:
                page.overlay.append(dialog_cliente)
            dialog_cliente.open = True
            page.update()

        def ejecutar_guardar_cliente(e):
            nombre = tf_cli_nombre.value.strip() if tf_cli_nombre.value else ""
            servicio = tf_cli_servicio.value.strip() if tf_cli_servicio.value else ""
            try:
                precio = float(tf_cli_precio.value) if tf_cli_precio.value else 0.0
                if precio < 0:
                    raise ValueError()
            except ValueError:
                mostrar_snack("La tarifa debe ser un número válido.", es_error=True)
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
                tf_cli_nombre.value = ""
                tf_cli_servicio.value = ""
                tf_cli_precio.value = ""
                tf_cli_notas.value = ""
                
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
                                ft.DataCell(ft.Text(f"Q {v[3]:.2f}", color=ft.colors.RED_700 if v[3] > 0 else ft.colors.GREEN_700)),
                            ])
                        )
                if dialog_historial not in page.overlay:
                    page.overlay.append(dialog_historial)
                dialog_historial.open = True
                page.update()
            except Exception as ex:
                mostrar_snack(f"Error cargando historial: {ex}", es_error=True)

        tab_clientes = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.ElevatedButton("➕ Agregar", icon=ft.icons.ADD, on_click=lambda e: abrir_modal_cliente(), bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO),
                    tf_cli_buscar
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=6),
                ft.Divider(color=C_GRIS_BORDE),
                lista_clientes_movil if page.width <= 700 else ft.ListView([dt_clientes], expand=True)
            ], expand=True),
            padding=6, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, expand=True
        )

        tf_gas_desc = ft.TextField(label="Descripción del Gasto", border_radius=8)
        tf_gas_monto = ft.TextField(label="Monto Retirado (Q)", border_radius=8, keyboard_type=ft.KeyboardType.NUMBER)

        dt_gastos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Descripción", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[]
        )

        def guardar_gasto_click(e):
            if es_dia_congelado():
                mostrar_snack("Caja congelada hoy.", es_error=True)
                return
            desc = tf_gas_desc.value.strip() if tf_gas_desc.value else ""
            if not desc:
                mostrar_snack("Escribe la descripción del gasto.", es_error=True)
                return
            try:
                monto = float(tf_gas_monto.value) if tf_gas_monto.value else 0.0
                if monto <= 0:
                    raise ValueError()
            except ValueError:
                mostrar_snack("Monto de gasto inválido.", es_error=True)
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
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("💸 Salida de Efectivo", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        tf_gas_desc, tf_gas_monto,
                        ft.ElevatedButton("💾 Registrar Gasto", icon=ft.icons.MONEY_OFF, on_click=guardar_gasto_click, bgcolor=ft.colors.GREY_800, color=C_BLANCO)
                    ], spacing=6),
                    padding=8, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("📋 Egresos de Hoy", size=13, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
                        ft.Divider(color=C_GRIS_BORDE),
                        ft.ListView([dt_gastos], expand=True)
                    ], expand=True),
                    expand=True, padding=8, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                )
            ], expand=True, spacing=6),
            padding=2, expand=True
        )

        lbl_total_deudas_global = ft.Text("Pendiente Global: Q 0.00", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.RED_700)

        # Componentes persistentes de la pestaña de deudas para evitar errores en el re-renderizado
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
        lista_deudas_movil = ft.ListView([], expand=True, spacing=6)
        contenedor_cuerpo_deudas = ft.Container(expand=True)

        tab_deudas = ft.Container(
            content=ft.Column([
                ft.Row([
                    lbl_total_deudas_global,
                    ft.IconButton(icon=ft.icons.REFRESH, on_click=lambda e: cargar_tabla_deudas(), tooltip="Actualizar")
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color=C_GRIS_BORDE),
                contenedor_cuerpo_deudas,
            ], expand=True),
            padding=6, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO, expand=True
        )

        tf_hist_inicio = ft.TextField(label="Desde (YYYY-MM-DD)", value=datetime.date.today().strftime("%Y-%m-01"), expand=True, border_radius=8)
        tf_hist_fin = ft.TextField(label="Hasta (YYYY-MM-DD)", value=datetime.date.today().strftime("%Y-%m-%d"), expand=True, border_radius=8)

        dt_resumen_macro = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Concepto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Monto", weight=ft.FontWeight.BOLD)),
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
                    ft.DataRow(cells=[ft.DataCell(ft.Text("(=) SALDO NETO")), ft.DataCell(ft.Text(f"Q {balance_neto:.2f}", weight=ft.FontWeight.BOLD))]),
                    ft.DataRow(cells=[ft.DataCell(ft.Text("(*) Por Cobrar (Fiado)")), ft.DataCell(ft.Text(f"Q {t_pendientes:.2f}"))]),
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
                            ft.DataCell(ft.Text(st, color=ft.colors.GREEN_700 if "Cerrado" in st else ft.colors.RED_700)),
                        ])
                    )

                page.update()
            except Exception as ex:
                mostrar_snack(f"Error procesando: {ex}", es_error=True)

        tab_historial = ft.Container(
            content=ft.Column([
                ft.Row([tf_hist_inicio, tf_hist_fin], spacing=4),
                ft.ElevatedButton("📊 Procesar Reporte", icon=ft.icons.ANALYTICS, on_click=procesar_historial_rango, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO),
                ft.Divider(color=C_GRIS_BORDE),
                ft.Container(
                    content=ft.Column([ft.Text("📊 Métricas", size=12, weight=ft.FontWeight.BOLD), dt_resumen_macro]),
                    padding=4, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8
                ),
                ft.Container(
                    content=ft.Column([ft.Text("📅 Días", size=12, weight=ft.FontWeight.BOLD), ft.ListView([dt_cronologico], expand=True)], expand=True),
                    expand=True, padding=4, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8
                )
            ], expand=True, spacing=4),
            padding=2, expand=True
        )

        tf_abono_monto = ft.TextField(label="Monto de Abono (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        lbl_abono_info = ft.Text("", size=12, weight=ft.FontWeight.BOLD)

        dialog_abono = ft.AlertDialog(
            title=ft.Text("💰 Registrar Abono", weight=ft.FontWeight.BOLD),
            content=ft.Column([lbl_abono_info, tf_abono_monto], height=100, spacing=6),
            actions=[]
        )

        def abrir_dialogo_abono(v_id, cliente_nombre, pendiente_actual):
            cerrar_dialogo_seguro(dialog_abono)
            tf_abono_monto.value = ""

            def ejecutar_abono(e):
                try:
                    abono = float(tf_abono_monto.value)
                    db.cursor.execute("SELECT pendiente FROM ventas WHERE id=%s", (v_id,))
                    fila_saldo = db.cursor.fetchone()
                    saldo_actual = float(fila_saldo[0]) if fila_saldo else 0.0
                    if abono <= 0 or abono > saldo_actual:
                        raise ValueError()
                except (ValueError, TypeError):
                    mostrar_snack("Monto inválido o mayor al saldo actual.", es_error=True)
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
                ft.ElevatedButton("Aplicar", on_click=ejecutar_abono, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
            ]
            if dialog_abono not in page.overlay:
                page.overlay.append(dialog_abono)
            dialog_abono.open = True
            page.update()

        lbl_car_idx = ft.Text("", size=10, italic=True)
        lbl_car_name = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=C_CELESTE_PRINCIPAL)
        lbl_car_info = ft.Text("", size=11)
        lbl_car_alerta = ft.Text("", size=10, color=ft.colors.RED_700, weight=ft.FontWeight.BOLD)

        tf_car_desc = ft.TextField(label="Detalle del Trabajo", border_radius=8)
        tf_car_total = ft.TextField(label="Total (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        tf_car_pago = ft.TextField(label="Efectivo en Caja (Q)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)
        tf_car_abono_v = ft.TextField(label="Abono a Deuda Anterior (Q)", value="0.00", keyboard_type=ft.KeyboardType.NUMBER, border_radius=8)

        col_form_carrusel = ft.Column([tf_car_desc, tf_car_total, tf_car_pago, lbl_car_alerta, tf_car_abono_v], visible=False, spacing=4)
        col_preg_carrusel = ft.Column([], visible=True, spacing=4)

        dialog_carrusel = ft.AlertDialog(
            title=ft.Row([ft.Text("⚡ Carrusel", weight=ft.FontWeight.BOLD), lbl_car_idx], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content=ft.Container(
                content=ft.Column([lbl_car_name, lbl_car_info, ft.Divider(color=C_GRIS_BORDE), col_preg_carrusel, col_form_carrusel], width=280, height=300, spacing=4),
                padding=2
            ),
            actions=[]
        )

        def cargar_cliente_carrusel():
            if not estado["carrusel_list"] or estado["carrusel_idx"] >= len(estado["carrusel_list"]):
                cerrar_dialogo_seguro(dialog_carrusel)
                mostrar_snack("🎉 ¡Clientes de hoy procesados!")
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
                lbl_car_alerta.value = f"⚠️ Deuda anterior: Q {deuda_total:.2f}"
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

                if tot < 0 or pag < 0 or pag > tot or abono_v < 0:
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
            ft.ElevatedButton("🟢 TRABAJÓ HOY", on_click=lambda e: mostrar_formulario_carrusel(), bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO),
            ft.ElevatedButton("⚫ AUSENTE", on_click=lambda e: carrusel_marcar_inactivo(), bgcolor=ft.colors.GREY_800, color=C_BLANCO),
        ]

        def actualizar_botones_carrusel():
            if col_form_carrusel.visible:
                dialog_carrusel.actions = [
                    ft.TextButton("⬅️ Volver", on_click=lambda e: cargar_cliente_carrusel()),
                    ft.ElevatedButton("💾 Guardar", on_click=lambda e: registrar_operacion_carrusel(), bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
                ]
            else:
                dialog_carrusel.actions = [
                    ft.IconButton(icon=ft.icons.ARROW_BACK, on_click=lambda e: nav_carrusel(-1)),
                    ft.IconButton(icon=ft.icons.ARROW_FORWARD, on_click=lambda e: nav_carrusel(1)),
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
                if dialog_carrusel not in page.overlay:
                    page.overlay.append(dialog_carrusel)
                dialog_carrusel.open = True
                cargar_cliente_carrusel()
            except Exception as ex:
                mostrar_snack(f"Error en carrusel: {ex}", es_error=True)

        def cargar_tabla_activos_inactivos():
            dt_activos.rows.clear()
            lista_activos_movil.controls.clear()
            dt_inactivos.rows.clear()
            fecha_str = estado["fecha"].strftime("%Y-%m-%d")

            try:
                db.cursor.execute("""
                    SELECT v.id, c.nombre, v.producto, v.pagado, v.pendiente 
                    FROM ventas v JOIN clientes c ON v.cliente_id = c.id WHERE v.fecha_corta=%s
                """, (fecha_str,))
                for r in db.cursor.fetchall():
                    v_id, c_nombre, prod, pag, pend = r

                    def editar_venta_fn(e, vid=v_id, name=c_nombre, p=prod, pg=pag, pn=pend):
                        abrir_modal_editar_venta(vid, name, p, pg, pn)

                    def borrar_venta_fn(e, vid=v_id, name=c_nombre):
                        if es_dia_congelado():
                            mostrar_snack("Caja congelada hoy.", es_error=True)
                            return
                        try:
                            db.cursor.execute("DELETE FROM ventas WHERE id=%s", (vid,))
                            db.conn.commit()
                            mostrar_snack(f"Registro de '{name}' eliminado.")
                            refrescar_pantallas()
                        except Exception as ex:
                            db.conn.rollback()
                            mostrar_snack(f"Error: {ex}", es_error=True)

                    if page.width <= 700:
                        card_item = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"{c_nombre}", weight=ft.FontWeight.BOLD, size=13, color=C_TEXTO_NEGRO),
                                    ft.Text(f"Q {pag:.1f} (Debe: Q {pend:.1f})", weight=ft.FontWeight.BOLD, size=12, color=ft.colors.RED_700 if pend > 0 else C_CELESTE_PRINCIPAL)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Detalle: {prod}", size=11, color=ft.colors.GREY_700),
                                ft.Row([
                                    ft.IconButton(icon=ft.icons.EDIT, icon_size=16, icon_color=C_CELESTE_PRINCIPAL, on_click=editar_venta_fn, tooltip="Editar"),
                                    ft.IconButton(icon=ft.icons.DELETE, icon_size=16, icon_color=ft.colors.RED_600, on_click=borrar_venta_fn, tooltip="Eliminar"),
                                ], alignment=ft.MainAxisAlignment.END, spacing=0)
                            ], spacing=2),
                            padding=6,
                            margin=ft.margin.symmetric(vertical=2),
                            border=ft.border.all(1, C_GRIS_BORDE),
                            border_radius=6,
                            bgcolor=C_BLANCO
                        )
                        lista_activos_movil.controls.append(card_item)
                    else:
                        dt_activos.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(c_nombre, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(prod, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {pag:.1f}", color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {pend:.1f}", color=ft.colors.RED_700 if pend > 0 else C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Row([
                                    ft.IconButton(icon=ft.icons.EDIT, icon_size=16, icon_color=C_CELESTE_PRINCIPAL, on_click=editar_venta_fn, tooltip="Editar"),
                                    ft.IconButton(icon=ft.icons.DELETE, icon_size=16, icon_color=ft.colors.RED_600, on_click=borrar_venta_fn, tooltip="Eliminar"),
                                ], spacing=0))
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
                            ft.DataCell(ft.ElevatedButton("↺", on_click=restaurar_inactivo_fn, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)),
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
            lista_clientes_movil.controls.clear()
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

                    if page.width <= 700:
                        card_item = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"#{c_id} - {nombre}", weight=ft.FontWeight.BOLD, size=13, color=C_TEXTO_NEGRO),
                                    ft.Text(f"Q {precio:.2f}", weight=ft.FontWeight.BOLD, size=13, color=C_CELESTE_PRINCIPAL)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Servicio: {servicio}", size=11, color=ft.colors.GREY_700),
                                ft.Row([
                                    ft.IconButton(icon=ft.icons.REMOVE_RED_EYE, icon_size=16, icon_color=C_CELESTE_PRINCIPAL, on_click=ver_hist_fn, tooltip="Historial"),
                                    ft.IconButton(icon=ft.icons.EDIT, icon_size=16, icon_color=ft.colors.GREY_700, on_click=editar_fn, tooltip="Editar"),
                                    ft.IconButton(icon=ft.icons.DELETE, icon_size=16, icon_color=ft.colors.RED_600, on_click=borrar_fn, tooltip="Eliminar"),
                                ], alignment=ft.MainAxisAlignment.END, spacing=0)
                            ], spacing=2),
                            padding=6,
                            margin=ft.margin.symmetric(vertical=2),
                            border=ft.border.all(1, C_GRIS_BORDE),
                            border_radius=6,
                            bgcolor=C_BLANCO
                        )
                        lista_clientes_movil.controls.append(card_item)
                    else:
                        nuevas_filas.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(str(c_id), color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(nombre, color=C_TEXTO_NEGRO, weight=ft.FontWeight.BOLD)),
                                ft.DataCell(ft.Text(servicio, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {precio:.2f}", color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Row([
                                    ft.IconButton(icon=ft.icons.REMOVE_RED_EYE, icon_color=C_CELESTE_PRINCIPAL, on_click=ver_hist_fn, tooltip="Historial"),
                                    ft.IconButton(icon=ft.icons.EDIT, icon_color=ft.colors.GREY_700, on_click=editar_fn, tooltip="Editar"),
                                    ft.IconButton(icon=ft.icons.DELETE, icon_color=ft.colors.RED_600, on_click=borrar_fn, tooltip="Eliminar"),
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
                            ft.DataCell(ft.IconButton(icon=ft.icons.DELETE, icon_color=ft.colors.RED_600, on_click=eliminar_gasto_fn, tooltip="Borrar")),
                        ])
                    )
            except Exception as ex:
                print(f"Error gastos: {ex}")

        def cargar_tabla_deudas():
            dt_deudas.rows.clear()
            lista_deudas_movil.controls.clear()
            
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

                    if page.width <= 700:
                        card_deuda = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"{cliente}", weight=ft.FontWeight.BOLD, size=13, color=C_TEXTO_NEGRO),
                                    ft.Text(f"Debe: Q {pendiente:.2f}", weight=ft.FontWeight.BOLD, size=13, color=ft.colors.RED_700)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Detalle: {producto} ({fecha})", size=11, color=ft.colors.GREY_700),
                                ft.Row([
                                    ft.ElevatedButton("💰 Abonar", icon=ft.icons.PAYMENTS, icon_size=14, on_click=abono_fn, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
                                ], alignment=ft.MainAxisAlignment.END)
                            ], spacing=2),
                            padding=6,
                            margin=ft.margin.symmetric(vertical=2),
                            border=ft.border.all(1, C_GRIS_BORDE),
                            border_radius=6,
                            bgcolor=C_BLANCO
                        )
                        lista_deudas_movil.controls.append(card_deuda)
                    else:
                        dt_deudas.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(str(v_id), color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(fecha, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(cliente, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(producto, color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {total:.2f}", color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {pagado:.2f}", color=C_TEXTO_NEGRO)),
                                ft.DataCell(ft.Text(f"Q {pendiente:.2f}", color=ft.colors.RED_700, weight=ft.FontWeight.BOLD)),
                                ft.DataCell(ft.ElevatedButton("💰", on_click=abono_fn, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)),
                            ])
                        )

                lbl_total_deudas_global.value = f"Pendiente Global: Q {suma_global:.2f}"

                if page.width <= 700:
                    if not deudas:
                        lista_deudas_movil.controls.append(
                            ft.Container(
                                content=ft.Text("No hay deudas pendientes.", size=14, color=C_TEXTO_NEGRO),
                                padding=12, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                            )
                        )
                    contenedor_cuerpo_deudas.content = lista_deudas_movil
                else:
                    contenedor_cuerpo_deudas.content = ft.ListView([dt_deudas], expand=True)

                page.update()
            except Exception as ex:
                print(f"Error deudas: {ex}")
                contenedor_cuerpo_deudas.content = ft.Container(
                    content=ft.Text(f"Error al cargar deudas: {ex}", size=13, color=ft.colors.RED_700),
                    padding=12, border=ft.border.all(1, C_GRIS_BORDE), border_radius=8, bgcolor=C_BLANCO
                )
                page.update()

        def verificar_cierres_olvidados():
            hoy = datetime.date.today()
            limite_antiguedad = hoy - datetime.timedelta(days=5)
            hoy_str = hoy.strftime("%Y-%m-%d")
            limite_str = limite_antiguedad.strftime("%Y-%m-%d")
            try:
                db.cursor.execute("""
                    SELECT DISTINCT fecha_corta FROM ventas WHERE fecha_corta >= %s AND fecha_corta < %s AND fecha_corta NOT IN (SELECT fecha_corta FROM cierres)
                    UNION SELECT DISTINCT fecha_corta FROM gastos WHERE fecha_corta >= %s AND fecha_corta < %s AND fecha_corta NOT IN (SELECT fecha_corta FROM cierres)
                """, (limite_str, hoy_str, limite_str, hoy_str))
                olvidados = db.cursor.fetchall()
                container_alerta_cierres.visible = len(olvidados) > 0
            except Exception as ex:
                print(f"Error cierres: {ex}")

        def refrescar_pantallas(e=None):
            try:
                db.conn.rollback()
            except:
                pass

            fecha_str = estado["fecha"].strftime("%Y-%m-%d")
            lbl_fecha.value = fecha_str

            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            lbl_banner_texto.value = f"📅 {dias[estado['fecha'].weekday()]} {estado['fecha'].day}/{meses[estado['fecha'].month - 1]}"

            if es_dia_congelado():
                badge_estado.bgcolor = ft.colors.RED_700
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

        btn_carrusel = ft.ElevatedButton("⚡ Carrusel", icon=ft.icons.FLASHLIGHT_ON, on_click=abrir_carrusel_click, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
        btn_cerrar_caja = ft.ElevatedButton("🔒 Cerrar", icon=ft.icons.LOCK, on_click=ejecutar_cierre_dia, bgcolor=ft.colors.GREY_800, color=C_BLANCO)
        btn_abrir_caja = ft.ElevatedButton("🔓 Reabrir", icon=ft.icons.LOCK_OPEN, on_click=ejecutar_apertura_dia, bgcolor=ft.colors.ORANGE_800, color=C_BLANCO, visible=False)
        btn_sync = ft.IconButton(icon=ft.icons.SYNC, icon_color=C_CELESTE_PRINCIPAL, on_click=refrescar_pantallas, tooltip="Sincronizar Datos")

        header_bar = ft.Container(
            content=ft.Row([
                txt_titulo,
                ft.Row([
                    ft.IconButton(icon=ft.icons.ARROW_BACK_IOS, icon_size=12, on_click=lambda e: cambiar_dia(-1)),
                    lbl_fecha,
                    ft.IconButton(icon=ft.icons.ARROW_FORWARD_IOS, icon_size=12, on_click=lambda e: cambiar_dia(1)),
                    badge_estado,
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=2),
                ft.Row([lbl_caja_total, btn_sync], spacing=2)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=6, bgcolor=C_GRIS_FONDO, border_radius=8, border=ft.border.all(1, C_GRIS_BORDE)
        )

        action_bar = ft.Container(
            content=ft.Row([lbl_banner_texto, ft.Row([btn_carrusel, btn_cerrar_caja, btn_abrir_caja], spacing=4)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=2
        )

        tab_views = [tab_inicio, tab_caja, tab_clientes, tab_gastos, tab_deudas, tab_historial]
        content_area = ft.Container(content=tab_views[0], expand=True)

        def cambiar_pestana(e):
            idx = int(e.control.data)
            content_area.content = tab_views[idx]
            if idx == 0:
                cargar_tabla_activos_inactivos()
            elif idx == 2:
                cargar_tabla_clientes()
            elif idx == 4:
                cargar_tabla_deudas()
            
            all_btns = nav_buttons_pc.controls if page.width > 700 else (nav_row_1.controls + nav_row_2.controls)
            for i, btn in enumerate(all_btns):
                btn.bgcolor = C_CELESTE_PRINCIPAL if i == idx else C_GRIS_FONDO
                btn.color = C_BLANCO if i == idx else C_TEXTO_NEGRO
            page.update()

        nav_buttons_pc = ft.Row([
            ft.ElevatedButton("📊 Hoy", on_click=cambiar_pestana, data=0, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO),
            ft.ElevatedButton("💵 Caja", on_click=cambiar_pestana, data=1, bgcolor=C_GRIS_FONDO, color=C_TEXTO_NEGRO),
            ft.ElevatedButton("👤 Clientes", on_click=cambiar_pestana, data=2, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO),
            ft.ElevatedButton("💸 Gastos", on_click=cambiar_pestana, data=3, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO),
            ft.ElevatedButton("🔴 Deudas", on_click=cambiar_pestana, data=4, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO),
            ft.ElevatedButton("📋 Reportes", on_click=cambiar_pestana, data=5, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO),
        ], spacing=6)

        nav_row_1 = ft.Row([
            ft.ElevatedButton("📊 Hoy", on_click=cambiar_pestana, data=0, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO, expand=True),
            ft.ElevatedButton("💵 Caja", on_click=cambiar_pestana, data=1, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO, expand=True),
            ft.ElevatedButton("👤 Clientes", on_click=cambiar_pestana, data=2, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO, expand=True),
        ], spacing=4)

        nav_row_2 = ft.Row([
            ft.ElevatedButton("💸 Gastos", on_click=cambiar_pestana, data=3, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO, expand=True),
            ft.ElevatedButton("🔴 Deudas", on_click=cambiar_pestana, data=4, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO, expand=True),
            ft.ElevatedButton("📋 Reportes", on_click=cambiar_pestana, data=5, bgcolor=C_GRIS_BORDE, color=C_TEXTO_NEGRO, expand=True),
        ], spacing=4)

        nav_container_mobile = ft.Column([nav_row_1, nav_row_2], spacing=4)

        contenedor_menu = ft.Container(
            content=nav_buttons_pc if page.width > 700 else nav_container_mobile
        )

        main_layout = ft.Column([
            header_bar,
            container_alerta_cierres,
            action_bar,
            contenedor_menu,
            ft.Container(content=content_area, expand=True)
        ], expand=True, spacing=6)

        def ajustar_vista_por_tamano(e=None):
            es_movil = page.width <= 700
            contenedor_menu.content = nav_container_mobile if es_movil else nav_buttons_pc
            cargar_tabla_deudas()
            page.update()

        page.on_resize = ajustar_vista_por_tamano
        page.clean()
        page.add(main_layout)
        refrescar_pantallas()

    tf_user = ft.TextField(label="Usuario", width=260, border_radius=8)
    tf_pass = ft.TextField(label="Contraseña", width=260, password=True, can_reveal_password=True, border_radius=8)
    lbl_error_login = ft.Text("", color=ft.colors.RED_700, weight=ft.FontWeight.BOLD, size=13)

    def validar_login(e):
        usuario = tf_user.value.strip() if tf_user.value else ""
        password = tf_pass.value.strip() if tf_pass.value else ""
        
        if usuario == os.environ.get("APP_USER", "admin") and password == os.environ.get("APP_PASSWORD", "pantuj2026"):
            iniciar_sistema_tienda()
        else:
            lbl_error_login.value = "❌ Credenciales incorrectas"
            page.update()

    container_login = ft.Container(
        content=ft.Column([
            ft.Text("🔐 Acceso Tienda Pantuj", size=22, weight=ft.FontWeight.BOLD, color=C_TEXTO_NEGRO),
            ft.Text("Control en la Nube", size=13, color=ft.colors.GREY_700),
            ft.Divider(color=C_GRIS_BORDE),
            tf_user,
            tf_pass,
            lbl_error_login,
            ft.ElevatedButton("Ingresar", on_click=validar_login, bgcolor=C_CELESTE_PRINCIPAL, color=C_BLANCO)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        expand=True
    )

    page.add(container_login)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    ft.app(target=main, view=None, host="0.0.0.0", port=port)