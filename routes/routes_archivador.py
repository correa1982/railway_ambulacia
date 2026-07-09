import os
import uuid
from flask import render_template, request, redirect, url_for, session, flash, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, ahora, get_user_info

CATEGORIAS = [
    "Administrativo",
    "Médico",
    "Legal",
    "Operativo",
    "Capacitación",
    "Mantenimiento",
    "Otro"
]

def register_routes(app):
    @app.route("/archivador")
    @login_required
    def archivador_list():
        conn = get_db()
        search_query = request.args.get("search", "").strip()
        categoria_filter = request.args.get("categoria", "").strip()
        fecha_desde = request.args.get("fecha_desde", "").strip()
        fecha_hasta = request.args.get("fecha_hasta", "").strip()

        where = "1=1"
        params = []

        if search_query:
            where += " AND (nombre_formulario LIKE ? OR archivo_nombre LIKE ? OR descripcion LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

        if categoria_filter:
            where += " AND categoria = ?"
            params.append(categoria_filter)

        if fecha_desde:
            where += " AND fecha_documento >= ?"
            params.append(fecha_desde)

        if fecha_hasta:
            where += " AND fecha_documento <= ?"
            params.append(fecha_hasta)

        archivos = conn.execute(f"SELECT * FROM archivador WHERE {where} ORDER BY id DESC", params).fetchall()
        conn.close()

        return render_template(
            "archivador.html",
            archivos=archivos,
            search_query=search_query,
            categoria_filter=categoria_filter,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            categorias=CATEGORIAS
        )

    @app.route("/archivador/nuevo", methods=["GET", "POST"])
    @login_required
    def archivador_nuevo():
        conn = get_db()
        if request.method == "POST":
            nombre_formulario_select = request.form.get("nombre_formulario_select", "").strip()
            if nombre_formulario_select == "Otro":
                nombre_formulario = request.form.get("nombre_formulario_otro", "").strip()
            else:
                nombre_formulario = nombre_formulario_select

            categoria = request.form.get("categoria", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            fecha_documento = request.form.get("fecha_documento", "").strip()
            files = request.files.getlist("archivo")

            # Filter out empty files
            files = [f for f in files if f and f.filename]

            if not nombre_formulario or not files:
                msg = "Debes ingresar un nombre de formulario y seleccionar al menos un archivo."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": msg, "redirect": url_for("archivador_nuevo")}), 400
                flash(msg, "error")
                return redirect(url_for("archivador_nuevo"))

            try:
                max_consecutivo_row = conn.execute(
                    "SELECT MAX(consecutivo) as max_c FROM archivador"
                ).fetchone()
                current_consecutivo = (max_consecutivo_row["max_c"] or 0) + 1
            except Exception:
                current_consecutivo = 1

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
            os.makedirs(upload_folder, exist_ok=True)
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            count = 0

            for file in files:
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)

                archivo_url = f"/static/uploads/archivador/{unique_filename}"

                conn.execute("""
                    INSERT INTO archivador (
                        nombre_formulario, consecutivo, archivo_url, archivo_nombre,
                        fecha_registro, registrado_por, registrado_por_identificacion, perfil_registrador,
                        categoria, descripcion, fecha_documento
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nombre_formulario,
                    current_consecutivo + count,
                    archivo_url,
                    filename,
                    now_str,
                    session["usuario"]["nombre"],
                    session["usuario"]["identificacion"],
                    perfil,
                    categoria or None,
                    descripcion or None,
                    fecha_documento or None
                ))
                count += 1

            conn.commit()
            conn.close()

            if count == 1:
                msg = f"Archivo subido correctamente. Consecutivo: #{current_consecutivo}"
            else:
                msg = f"{count} archivos subidos correctamente. Consecutivos: #{current_consecutivo} - #{current_consecutivo + count - 1}"

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": True, "message": msg, "redirect": url_for("archivador_list")})

            flash(msg, "success")
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

        return render_template(
            "archivador_nuevo.html",
            nombres_formulario=nombres_formulario,
            categorias=CATEGORIAS,
            archivo=None
        )

    @app.route("/archivador/editar/<int:id>", methods=["GET", "POST"])
    @login_required
    def archivador_editar(id):
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = ?", (id,)).fetchone()

        if not archivo:
            flash("Archivo no encontrado.", "error")
            conn.close()
            return redirect(url_for("archivador_list"))

        if request.method == "POST":
            nombre_formulario = request.form.get("nombre_formulario", "").strip()
            categoria = request.form.get("categoria", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            fecha_documento = request.form.get("fecha_documento", "").strip()
            file = request.files.get("archivo")

            if not nombre_formulario:
                flash("El nombre del formulario es obligatorio.", "error")
                return redirect(url_for("archivador_editar", id=id))

            archivo_url = archivo["archivo_url"]
            archivo_nombre = archivo["archivo_nombre"]

            if file and file.filename:
                # Delete old file
                old_path = os.path.join(current_app.root_path, archivo["archivo_url"].lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)

                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)
                archivo_url = f"/static/uploads/archivador/{unique_filename}"
                archivo_nombre = filename

            conn.execute("""
                UPDATE archivador SET
                    nombre_formulario = ?, categoria = ?, descripcion = ?,
                    fecha_documento = ?, archivo_url = ?, archivo_nombre = ?
                WHERE id = ?
            """, (
                nombre_formulario,
                categoria or None,
                descripcion or None,
                fecha_documento or None,
                archivo_url,
                archivo_nombre,
                id
            ))

            conn.commit()
            conn.close()

            flash("Documento actualizado correctamente.", "success")
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

        return render_template(
            "archivador_nuevo.html",
            nombres_formulario=nombres_formulario,
            categorias=CATEGORIAS,
            archivo=archivo
        )

    @app.route("/archivador/eliminar/<int:id>", methods=["POST"])
    @login_required
    def archivador_eliminar(id):
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = ?", (id,)).fetchone()
        if not archivo:
            flash("Archivo no encontrado.", "error")
            return redirect(url_for("archivador_list"))

        file_path = os.path.join(current_app.root_path, archivo["archivo_url"].lstrip('/'))
        if os.path.exists(file_path):
            os.remove(file_path)

        conn.execute("DELETE FROM archivador WHERE id = ?", (id,))
        conn.commit()
        conn.close()

        flash("Archivo eliminado correctamente.", "success")
        return redirect(url_for("archivador_list"))
