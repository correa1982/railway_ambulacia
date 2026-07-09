import os
import uuid
import json
from flask import render_template, request, redirect, url_for, session, flash, current_app, send_from_directory
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, get_user_info, ahora

def register_routes(app):

    @app.route("/archivador")
    @login_required
    def archivador_list():
        conn = get_db()
        search_query = request.args.get("search", "").strip()
        
        if search_query:
            like_query = f"%{search_query}%"
            archivos = conn.execute(
                "SELECT * FROM archivador WHERE nombre_formulario LIKE ? OR archivo_nombre LIKE ? ORDER BY id DESC",
                (like_query, like_query)
            ).fetchall()
        else:
            archivos = conn.execute("SELECT * FROM archivador ORDER BY id DESC").fetchall()
        
        conn.close()
        
        return render_template("archivador_list.html",
                               archivos=archivos,
                               search_query=search_query,
                               usuario=session["usuario"])


    @app.route("/archivador/nuevo", methods=["GET", "POST"])
    @login_required
    def archivador_nuevo():
        conn = get_db()
        
        if request.method == "POST":
            nombre_formulario = request.form.get("nombre_formulario_select", "").strip()
            if nombre_formulario == "OTRO":
                nombre_formulario = request.form.get("nombre_formulario_custom", "").strip()
                
            file = request.files.get("archivo")
            
            if not nombre_formulario:
                flash("El nombre del formulario es obligatorio.", "error")
                return redirect(url_for("archivador_nuevo"))
                
            if not file or file.filename == '':
                flash("Debe seleccionar un archivo para subir.", "error")
                return redirect(url_for("archivador_nuevo"))

            # Calculate consecutivo
            try:
                max_consecutivo_row = conn.execute(
                    "SELECT MAX(consecutivo) as max_c FROM archivador WHERE nombre_formulario = ?",
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
                    # Try to get max id from the form table
                    row_form = conn.execute(f"SELECT MAX(id) as max_id FROM {table_name}").fetchone()
                    if row_form and row_form.get("max_id"):
                        max_form = row_form["max_id"]
                except Exception:
                    pass
                    
                try:
                    # Try to get max consecutivo if the form uses consecutivo instead of id
                    row_form_c = conn.execute(f"SELECT MAX(consecutivo) as max_c FROM {table_name}").fetchone()
                    if row_form_c and row_form_c.get("max_c"):
                        if row_form_c["max_c"] > max_form:
                            max_form = row_form_c["max_c"]
                except Exception:
                    pass
            
            current_consecutivo = max(max_archivador, max_form) + 1
            
            if table_name:
                # Advance the table's auto-increment so future form submissions don't overlap with this file
                try:
                    conn.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = {current_consecutivo + 1}")
                except Exception:
                    pass
            
            # Save file
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            archivo_url = f"/static/uploads/archivador/{unique_filename}"
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            
            # Insert into DB
            conn.execute("""
                INSERT INTO archivador (
                    nombre_formulario, consecutivo, archivo_url, archivo_nombre,
                    fecha_registro, registrado_por, registrado_por_identificacion, perfil_registrador
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            
        # GET request
        # Fetch distinct form names for datalist autocomplete
        nombres_db = conn.execute("SELECT DISTINCT nombre_formulario FROM archivador ORDER BY nombre_formulario").fetchall()
        nombres_formulario = [row["nombre_formulario"] for row in nombres_db]
        
        # Add some default common forms if they are not in the list yet
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
        
        return render_template("archivador_form.html",
                               nombres_formulario=nombres_formulario,
                               usuario=session["usuario"])


    @app.route("/archivador/eliminar/<int:archivo_id>", methods=["POST"])
    @login_required
    def archivador_eliminar(archivo_id):
        # Opcional: Permitir eliminar si es admin o el creador
        if session["usuario"]["rol"] != "admin":
            flash("No tienes permisos para eliminar archivos.", "error")
            return redirect(url_for("archivador_list"))
            
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = ?", (archivo_id,)).fetchone()
        
        if archivo:
            # Delete physical file
            file_url = archivo["archivo_url"]
            if file_url:
                # Extract filename from url
                filename = os.path.basename(file_url)
                file_path = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador', filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error eliminando archivo físico {file_path}: {e}")
            
            conn.execute("DELETE FROM archivador WHERE id = ?", (archivo_id,))
            conn.commit()
            flash("Archivo eliminado correctamente.", "success")
        else:
            flash("Archivo no encontrado.", "error")
            
        conn.close()
        return redirect(url_for("archivador_list"))
