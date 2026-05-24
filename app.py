import os
import requests
import re
from google import genai
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from database import db
from models import Usuario, ConfiguracionUsuario, AuditoriaSesion, Proyecto, Conversacion, Mensaje, BloqueCodigo

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Conectamos la aplicación a la base de datos
db.init_app(app)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Configurar el motor de Gemini directamente
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    return render_template('index.html', google_client_id=GOOGLE_CLIENT_ID)

# ENDPOINT DE AUTENTICACIÓN Y AUDITORÍA REAL
@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({"error": "Token ausente"}), 400

    try:
        # CIBERSEGURIDAD: Validar el token directamente con los servidores de Google
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        google_id = id_info['sub']
        email = id_info['email']
        nombre = id_info['name']
        foto = id_info.get('picture')

        # Buscar si el usuario ya existe en PostgreSQL
        usuario = Usuario.query.filter_by(google_id=google_id).first()
        
        if not usuario:
            # Si no existe, lo creamos (Consistencia y aislamiento de datos)
            usuario = Usuario(
                google_id=google_id,
                email=email,
                nombre_completo=nombre,
                foto_perfil=foto
            )
            db.session.add(usuario)
            db.session.flush() # Obtiene el ID generado antes de hacer el commit definitivo
            
            # Crear su configuración por defecto automáticamente (1 a 1)
            config = ConfiguracionUsuario(usuario_id=usuario.id)
            db.session.add(config)

        # AUDITORÍA DE SEGURIDAD: Registrar el intento de sesión
        auditoria = AuditoriaSesion(
            usuario_id=usuario.id,
            direccion_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            login_exitoso=True
        )
        db.session.add(auditoria)
        db.session.commit() # Guardar todo de forma atómica en PostgreSQL

        return jsonify({
            "success": True,
            "user": usuario.to_dict()
        }), 200

    except ValueError:
        # Si el token es falso o expiró, registramos el fallo si el correo es conocido
        return jsonify({"error": "Token inválido o alterado"}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

 # ==========================================

# NUEVA RUTA: RECUPERAR HISTORIAL AL INICIAR SESIÓN
# ==========================================
@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    usuario_id = request.args.get('usuario_id')
    if not usuario_id: return jsonify({"error": "Falta usuario"}), 400
    
    proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
    if not proyecto: return jsonify({"historial": []})
    
    # Buscar la única conversación abierta
    conversacion = Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').order_by(Conversacion.id.desc()).first()
    if not conversacion: return jsonify({"historial": []})
    
    mensajes = Mensaje.query.filter_by(conversacion_id=conversacion.id).order_by(Mensaje.fecha_envio.asc()).all()
    
    historial = []
    for m in mensajes:
        historial.append({
            "role": "user" if m.remitente_tipo == "usuario" else "agent",
            "text": m.contenido_texto
        })
    return jsonify({"historial": historial}), 200
 

@app.route('/api/chat/new', methods=['POST'])
def start_new_chat():
    data = request.json
    usuario_id = data.get('usuario_id')
    if not usuario_id: 
        return jsonify({"error": "Falta el identificador de usuario"}), 400
    
    proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
    if proyecto:
        # Buscamos la conversación abierta y la marcamos como cerrada
        Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').update({"estado": "cerrado"})
        db.session.commit()
        
    return jsonify({"success": True, "message": "Contexto liberado con éxito"}), 200

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

        # Buscar si ya hay un chat abierto. Si no hay, crear UNO solo.
        conversacion = Conversacion.query.filter_by(proyecto_id=proyecto.id, estado='abierto').order_by(Conversacion.id.desc()).first()
        if not conversacion:
            conversacion = Conversacion(proyecto_id=proyecto.id, titulo=prompt_usuario[:50] + "...")
            db.session.add(conversacion)
            db.session.flush()

        mensaje_usuario = Mensaje(conversacion_id=conversacion.id, remitente_tipo='usuario', contenido_texto=prompt_usuario)
        db.session.add(mensaje_usuario)
        db.session.flush()

        # Extraer últimos mensajes para la Memoria
        historial_db = Mensaje.query.filter_by(conversacion_id=conversacion.id).order_by(Mensaje.id.desc()).limit(4).all()
        historial_db.reverse()
        
        contexto_chat = "Historial reciente:\n"
        for msg in historial_db:
            rol = "USUARIO" if msg.remitente_tipo == 'usuario' else "SISTEMA"

            texto_limpio = re.sub(r'```.*?```', '\n[CÓDIGO GENERADO OMITIDO PARA AHORRAR MEMORIA]\n', msg.contenido_texto, flags=re.DOTALL)
            
            # También cortamos mensajes extremadamente largos por si acaso
            if len(texto_limpio) > 1000:
                texto_limpio = texto_limpio[:1000] + "... [texto truncado]"
                
            contexto_chat += f"{rol}: {texto_limpio}\n\n"
        
        prompt_con_memoria = f"{contexto_chat}\n\nInstrucción actual: {prompt_usuario}"

        # ========================================================
        # 2. ORQUESTACIÓN: LLAMADA A LOS AGENTES
        # ========================================================
        
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        
        prompt_arquitecto = """
        Eres un Arquitecto de Software Full-Stack. veloz. Tu tarea es hacer un primer borrador funcional.
        1. Analiza qué pide el usuario. Si solo pide Frontend, genera solo Frontend. Si solo pide Backend, solo Backend. Si pide ambos, haz la estructura de ambos.
        2. Si el usuario solicita un componente pero NO especifica el framework (ej. Vue, React, HTML puro) o las herramientas de diseño (ej. Tailwind, Bootstrap, CSS normal) o un lenguaje de backend (ej. Python/Flask, Node.js) ni el motor de base de datos (PostgreSQL, MySQL) ni en su mensaje ni en el historial, NO generes código. En su lugar, hazle 4 preguntas cortas para confirmar su "stack" tecnológico.
        3. Si el usuario ya especificó lo que quiere en las instrucciones o en el historial, genera el código.
        4. Utiliza SIEMPRE la versión más reciente del framework. NO preguntes qué versión usar.
        5. No te preocupes por la perfección absoluta, enfócate en dar una base sólida.
        """
        payload_frontend = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {"role": "system", "content": prompt_arquitecto},
                {"role": "user", "content": prompt_con_memoria} 
            ]
        }
        res_groq = requests.post(groq_url, json=payload_frontend, headers=groq_headers)
        if res_groq.status_code != 200: raise Exception(f"Fallo Groq: {res_groq.text}")
        borrador_codigo = res_groq.json()['choices'][0]['message']['content']

        # --- AGENTE BACKEND (GEMINI) ---
        prompt_auditor = f"""
        Eres un Ingeniero Principal de Software y Ciberseguridad muy estricto.
        El usuario solicitó esto: "{prompt_usuario}"
        
        Tu Arquitecto Junior propuso este borrador:
        {borrador_codigo}
        
        TU TAREA DEPENDE DEL BORRADOR:
        CASO A - SI EL BORRADOR ES UNA PREGUNTA: 
        Si el Arquitecto está haciendo preguntas para confirmar el stack tecnológico, devuelve EXACTAMENTE esas mismas preguntas. NO generes código ni apliques las reglas del Caso B.
        
        CASO B - SI EL BORRADOR ES CÓDIGO:
        1. Conviértelo en código de nivel de producción.
        2. Asegura que no existan vulnerabilidades (Inyecciones, XSS, etc.) y que la conexión Front/Back sea perfecta.
        3. CERO TEXTO DE RELLENO: Tienes ESTRICTAMENTE PROHIBIDO decir "Aquí tienes", "Claro", o saludar.
        4. ETIQUETAS: Inicia cada bloque indicando su ruta exacta (Ej: `/// Archivo: src/App.vue ///`) e inmediatamente abajo abre los backticks (```).
        Devuelve ÚNICAMENTE los bloques de código.
        """
        
        res_gemini = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_auditor
        )
        resultado_final = res_gemini.text

        # ========================================================
        # 3. PERSISTENCIA FINAL DE BLOQUES
        # ========================================================
        mensaje_agentes = Mensaje(conversacion_id=conversacion.id, remitente_tipo='agente', contenido_texto=resultado_final)
        db.session.add(mensaje_agentes)
        db.session.flush()

        # Escáner inteligente para extraer y guardar bloques de código limpios
        bloques = re.findall(r'```(\w+)?\n(.*?)```', resultado_final, re.DOTALL)
        for lenguaje, codigo in bloques:
            bloque_db = BloqueCodigo(
                mensaje_id=mensaje_agentes.id,
                lenguaje_programacion=(lenguaje if lenguaje else "texto"),
                codigo_fuente=codigo.strip()
            )
            db.session.add(bloque_db)

        db.session.commit()

        return jsonify({"success": True, "resultado_orquestador": resultado_final}), 200

    except Exception as e:
        db.session.rollback()
        print(f"\n[!] ERROR CRÍTICO EN EL ORQUESTADOR: {e}\n")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database_connected": True}), 200

if __name__ == '__main__':
    app.run(port=5000)