import os
import uuid
from flask import render_template, request, redirect, url_for, session, flash, current_app, send_from_directory
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, ahora, get_user_info

def register_routes(app):
    @app.route("/archivador")
    @login_required
    def archivador_list():
        conn = get_db()
        search_query = request.args.get("search", "").strip()
        
        # Filtro de búsqueda
        where = "1=1"
        params = []
        if search_query:
            where = "(nombre_formulario LIKE %s OR archivo_nombre LIKE %s)"
            params = [f"%{search_query}%", f"%{search_query}%"]
            
        archivos = conn.execute(f"SELECT * FROM archivador WHERE {where} ORDER BY id DESC", params).fetchall()
        conn.close()
        return render_template("archivador.html", archivos=archivos, search_query=search_query)

    @app.route("/archivador/nuevo", methods=["GET", "POST"])
    @login_required
    def archivador_nuevo():
        conn = get_db()
        if request.method == "POST":
            nombre_formulario = request.form.get("nombre_formulario", "").strip()
            file = request.files.get("archivo")
            
            if not nombre_formulario or not file or file.filename == "":
                flash("Debes ingresar un nombre de formulario y seleccionar un archivo.", "error")
                return redirect(url_for("archivador_nuevo"))

            # Calculate consecutivo
            try:
                max_consecutivo_row = conn.execute(
                    "SELECT MAX(consecutivo) as max_c FROM archivador WHERE nombre_formulario = %s",
                    (nombre_formulario,)
                ).fetchone()
                max_archivador = max_consecutivo_row["max_c"] or 0
            except Exception:
                max_archivador = 0
                
            # Mapeo de nombre de formulario a nombre de tabla en BD
            form_to_table = {
                "Calif. Atención": "calif_atencion",
                "Seguridad del Paciente": "segur_paciente",
                "Historia Clínica Individual": "pacientes",
                "Atención Vehículo de Intervención": "atencion_vehiculo",
                "Preoperacional Conductores": "preoperacional",
                "Check List TAM": "tam",
                "Check List TAB": "tab",
                "Check List Avanzada": "avanzada",
                "Check List PASB": "pasb",
                "Check List PASM": "pasm",
                "Preoperacional de Equipos": "equipos",
                "Formulario de Eventos": "eventos",
                "Atención Colectiva": "atencion_colectiva"
            }
            
            table_name = form_to_table.get(nombre_formulario)
                
            max_form = 0
            if table_name:
                try:
                    row_form = conn.execute(f"SELECT MAX(id) as max_id FROM {table_name}").fetchone()
                    if row_form and row_form.get("max_id"):
                        max_form = row_form["max_id"]
                except Exception:
                    pass
                    
                try:
                    row_form_c = conn.execute(f"SELECT MAX(consecutivo) as max_c FROM {table_name}").fetchone()
                    if row_form_c and row_form_c.get("max_c"):
                        if row_form_c["max_c"] > max_form:
                            max_form = row_form_c["max_c"]
                except Exception:
                    pass
            
            current_consecutivo = max(max_archivador, max_form) + 1
            
            if table_name:
                try:
                    conn.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = {current_consecutivo + 1}")
                except Exception:
                    pass
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            archivo_url = f"/static/uploads/archivador/{unique_filename}"
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            
            conn.execute("""
                INSERT INTO archivador (
                    nombre_formulario, consecutivo, archivo_url, archivo_nombre,
                    fecha_registro, registrado_por, registrado_por_identificacion, perfil_registrador
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nombre_formulario,
                current_consecutivo,
                archivo_url,
                filename,
                now_str,
                session["usuario"]["nombre"],
                session["usuario"]["identificacion"],
                perfil
            ))
            
            conn.commit()
            conn.close()
            
            flash(f"Archivo subido correctamente. Consecutivo asignado: #{current_consecutivo}", "success")
            return redirect(url_for("archivador_list"))
            
        nombres_db = conn.execute("SELECT DISTINCT nombre_formulario FROM archivador ORDER BY nombre_formulario").fetchall()
        nombres_formulario = [row["nombre_formulario"] for row in nombres_db]
        
        default_forms = [
            "Calif. Atención",
            "Seguridad del Paciente",
            "Historia Clínica Individual",
            "Atención Vehículo de Intervención",
            "Preoperacional Conductores",
            "Check List TAM",
            "Check List TAB",
            "Check List Avanzada",
            "Check List PASB",
            "Check List PASM",
            "Preoperacional de Equipos",
            "Formulario de Eventos",
            "Atención Colectiva"
        ]
        for df in default_forms:
            if df not in nombres_formulario:
                nombres_formulario.append(df)
                
        nombres_formulario.sort()
        conn.close()
        
        return render_template("archivador_nuevo.html", nombres_formulario=nombres_formulario)
        
    @app.route("/archivador/eliminar/<int:id>", methods=["POST"])
    @login_required
    def archivador_eliminar(id):
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = %s", (id,)).fetchone()
        if not archivo:
            flash("Archivo no encontrado.", "error")
            return redirect(url_for("archivador_list"))
            
        file_path = os.path.join(current_app.root_path, archivo["archivo_url"].lstrip('/'))
        if os.path.exists(file_path):
            os.remove(file_path)
            
        conn.execute("DELETE FROM archivador WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        
        flash("Archivo eliminado correctamente.", "success")
        return redirect(url_for("archivador_list"))
