import os
import requests
import re
import io
import zipfile
from google import genai
from flask import Flask, jsonify, render_template, request, send_file
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from database import db
from models import Usuario, ConfiguracionUsuario, AuditoriaSesion, Proyecto, Conversacion, Mensaje, BloqueCodigo, ArchivoProyecto

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Conectamos la aplicación a la base de datos
db.init_app(app)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Configurar el motor de Gemini
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    return render_template('index.html', google_client_id=GOOGLE_CLIENT_ID)

# ENDPOINT DE AUTENTICACIÓN Y AUDITORÍA
@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({"error": "Token ausente"}), 400

    try:
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        google_id = id_info['sub']
        email = id_info['email']
        nombre = id_info['name']
        foto = id_info.get('picture')

        usuario = Usuario.query.filter_by(google_id=google_id).first()
        
        if not usuario:
            usuario = Usuario(
                google_id=google_id,
                email=email,
                nombre_completo=nombre,
                foto_perfil=foto
            )
            db.session.add(usuario)
            db.session.flush() 
            
            config = ConfiguracionUsuario(usuario_id=usuario.id)
            db.session.add(config)

        auditoria = AuditoriaSesion(
            usuario_id=usuario.id,
            direccion_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            login_exitoso=True
        )
        db.session.add(auditoria)
        db.session.commit()

        return jsonify({
            "success": True,
            "user": usuario.to_dict()
        }), 200

    except ValueError:
        return jsonify({"error": "Token inválido o alterado"}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat/new', methods=['POST'])
def start_new_chat():
    data = request.json
    usuario_id = data.get('usuario_id')
    if not usuario_id: 
        return jsonify({"error": "Falta el identificador de usuario"}), 400
    
    proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
    if proyecto:
        # Cerramos la conversación anterior
        Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').update({"estado": "cerrado"})
        # Borramos los archivos actuales para liberar contexto y tokens de la IA
        ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id).delete()
        db.session.commit()
        
    return jsonify({"success": True, "message": "Chat y archivos limpiados con éxito"}), 200

# Nueva ruta para guardar tus ediciones manuales:
@app.route('/api/file/update', methods=['POST'])
def update_file():
    data = request.json
    proyecto = Proyecto.query.filter_by(usuario_id=data.get('usuario_id')).first()
    if not proyecto: return jsonify({"error": "Proyecto no encontrado"}), 404
    
    archivo = ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id, ruta_archivo=data.get('ruta')).first()
    if archivo:
        archivo.contenido = data.get('contenido')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route('/api/generate', methods=['POST'])
def generate_code():
    data = request.json
    prompt_usuario = data.get('prompt')
    usuario_id = data.get('usuario_id')

    if not prompt_usuario or not usuario_id:
        return jsonify({"error": "Faltan datos de seguridad o instrucciones"}), 400

    try:
        proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
        if not proyecto:
            proyecto = Proyecto(usuario_id=usuario_id, nombre_proyecto="Proyecto Principal", descripcion="Generado automáticamente")
            db.session.add(proyecto)
            db.session.flush()

        conversacion = Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').order_by(Conversacion.id.desc()).first()
        if not conversacion:
            conversacion = Conversacion(proyecto_id=proyecto.id, titulo=prompt_usuario[:50] + "...")
            db.session.add(conversacion)
            db.session.flush()

        mensaje_usuario = Mensaje(conversacion_id=conversacion.id, remitente_tipo='usuario', contenido_texto=prompt_usuario)
        db.session.add(mensaje_usuario)
        db.session.flush()

        historial_db = Mensaje.query.filter_by(conversacion_id=conversacion.id).order_by(Mensaje.id.desc()).limit(4).all()
        historial_db.reverse()
        
        contexto_chat = "Historial reciente:\n"
        for msg in historial_db:
            rol = "USUARIO" if msg.remitente_tipo == 'usuario' else "SISTEMA"
            texto_limpio = re.sub(r'```.*?```', '\n[CÓDIGO OMITIDO]\n', msg.contenido_texto, flags=re.DOTALL)
            if len(texto_limpio) > 1000:
                texto_limpio = texto_limpio[:1000] + "... [texto truncado]"
            contexto_chat += f"{rol}: {texto_limpio}\n\n"

        # Extraer archivos actuales para darlos como contexto a las IAs
        archivos_actuales = ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id).all()
        estructura_archivos = "\n".join([f"- {a.ruta_archivo}" for a in archivos_actuales])
        if not estructura_archivos:
            estructura_archivos = "Proyecto vacío."
        
        prompt_con_memoria = f"{contexto_chat}\nArchivos actuales del proyecto:\n{estructura_archivos}\n\nInstrucción actual: {prompt_usuario}"

        # ========================================================
        # ORQUESTACIÓN: AGENTE FRONTEND (GROQ)
        # ========================================================
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        
        prompt_frontend = """
        Eres el Agente Frontend (HTML, CSS, JavaScript, Interfaces).
        Si la petición requiere crear o modificar vistas, genera el código. Si no, responde con la palabra: SIN_CAMBIOS.
        REGLA VITAL: CUANDO MODIFIQUES UN ARCHIVO, DEBES DEVOLVER EL CÓDIGO COMPLETO DE PRINCIPIO A FIN.
        ESTÁ ESTRICTAMENTE PROHIBIDO OMITIR PARTES, RESUMIR O USAR COMENTARIOS COMO "// resto del código aquí". 
        Regla estricta: Inicia cada bloque indicando su ruta exacta (Ej: /// Archivo: frontend/index.html ///) e inmediatamente abajo abre los backticks (```).
        """
        payload_frontend = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {"role": "system", "content": prompt_frontend},
                {"role": "user", "content": prompt_con_memoria} 
            ]
        }
        res_groq = requests.post(groq_url, json=payload_frontend, headers=groq_headers)
        if res_groq.status_code != 200: raise Exception(f"Fallo Groq: {res_groq.text}")
        resultado_frontend = res_groq.json()['choices'][0]['message']['content']

        # ========================================================
        # ORQUESTACIÓN: AGENTE BACKEND Y SEGURIDAD (GEMINI)
        # ========================================================
        prompt_backend = """
        Eres el Agente Backend, Base de Datos y Ciberseguridad.
        Si la petición requiere lógica de servidor, genera el código. Si no, responde con la palabra: SIN_CAMBIOS.
        REGLA VITAL: CUANDO MODIFIQUES UN ARCHIVO, DEBES DEVOLVER EL CÓDIGO COMPLETO DE PRINCIPIO A FIN.
        ESTÁ ESTRICTAMENTE PROHIBIDO OMITIR PARTES, RESUMIR O USAR COMENTARIOS COMO "# resto del código aquí".
        Regla estricta: Inicia cada bloque indicando su ruta exacta (Ej: /// Archivo: backend/app.py ///) e inmediatamente abajo abre los backticks (```).
        """
        res_gemini = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_backend + "\n\n" + prompt_con_memoria
        )
        resultado_backend = res_gemini.text

        # Unir respuestas para procesarlas
        resultado_final = ""
        if "SIN_CAMBIOS" not in resultado_frontend: resultado_final += resultado_frontend + "\n"
        if "SIN_CAMBIOS" not in resultado_backend: resultado_final += resultado_backend

        mensaje_agentes = Mensaje(conversacion_id=conversacion.id, remitente_tipo='agente', contenido_texto=resultado_final)
        db.session.add(mensaje_agentes)
        db.session.flush()

        # Extraer bloques de código, incluyendo su ruta (Ej: /// Archivo: src/main.js ///)
        patron_bloques = r'///\s*Archivo:\s*([^\n]+?)\s*///\s*```(\w+)?\n(.*?)```'
        bloques = re.findall(patron_bloques, resultado_final, re.DOTALL)
        
        archivos_procesados = []

        for ruta, lenguaje, codigo in bloques:
            ruta_limpia = ruta.strip()
            codigo_limpio = codigo.strip()
            
            # Guardar el historial exacto del mensaje (tu código original)
            bloque_db = BloqueCodigo(
                mensaje_id=mensaje_agentes.id,
                lenguaje_programacion=(lenguaje if lenguaje else "texto"),
                codigo_fuente=codigo_limpio
            )
            db.session.add(bloque_db)

            # Actualizar el árbol de archivos (VSC-like functionality)
            archivo_existente = ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id, ruta_archivo=ruta_limpia).first()
            if archivo_existente:
                archivo_existente.contenido = codigo_limpio
            else:
                nuevo_archivo = ArchivoProyecto(
                    proyecto_id=proyecto.id, 
                    ruta_archivo=ruta_limpia, 
                    contenido=codigo_limpio
                )
                db.session.add(nuevo_archivo)
            
            archivos_procesados.append({"ruta": ruta_limpia, "contenido": codigo_limpio})

        db.session.commit()

        return jsonify({
            "success": True, 
            "archivos_actualizados": archivos_procesados,
            "resultado_orquestador": resultado_final
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"\n[!] ERROR CRÍTICO EN EL ORQUESTADOR: {e}\n")
        return jsonify({"error": str(e)}), 500


# ==========================================
# NUEVA RUTA: DESCARGAR PROYECTO EN .ZIP
# ==========================================
@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    usuario_id = request.args.get('usuario_id')
    if not usuario_id: return jsonify({"error": "Falta usuario"}), 400
    
    proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
    if not proyecto: return jsonify({"historial": [], "archivos": []})
    
    conversacion = Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').order_by(Conversacion.id.desc()).first()
    
    archivos_db = ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id).all()
    archivos_json = [{"ruta": a.ruta_archivo, "contenido": a.contenido} for a in archivos_db]

    if not conversacion: return jsonify({"historial": [], "archivos": archivos_json})
    
    mensajes = Mensaje.query.filter_by(conversacion_id=conversacion.id).order_by(Mensaje.fecha_envio.asc()).all()
    
    historial = []
    for m in mensajes:
        historial.append({
            "role": "user" if m.remitente_tipo == "usuario" else "agent",
            "text": m.contenido_texto
        })
    return jsonify({"historial": historial, "archivos": archivos_json}), 200

@app.route('/api/download/<int:usuario_id>', methods=['GET'])
def download_project(usuario_id):
    nombre_custom = request.args.get('nombre', 'MiProyectoGenerado')
    
    proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
    archivos = ArchivoProyecto.query.filter_by(proyecto_id=proyecto.id).all()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for archivo in archivos:
            zf.writestr(archivo.ruta_archivo, archivo.contenido)

    memory_file.seek(0)
    
    # Limpiamos el nombre por si escribiste caracteres raros
    nombre_limpio = re.sub(r'[^a-zA-Z0-9_\-]', '_', nombre_custom)
    
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{nombre_limpio}.zip"
    )

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database_connected": True}), 200

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(port=5000)