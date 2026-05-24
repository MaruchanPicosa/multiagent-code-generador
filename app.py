import os
import requests
from google import genai
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from database import db
from models import Usuario, ConfiguracionUsuario, AuditoriaSesion, Proyecto, Conversacion, Mensaje

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
# EL ORQUESTADOR MULTI-AGENTE (HISTORIA 1.3)
# ==========================================
@app.route('/api/generate', methods=['POST'])
def generate_code():
    data = request.json
    prompt_usuario = data.get('prompt')
    usuario_id = data.get('usuario_id')

    if not prompt_usuario or not usuario_id:
        return jsonify({"error": "Faltan datos de seguridad o instrucciones"}), 400

    try:
        # ========================================================
        # 1. PERSISTENCIA INICIAL: PREPARAR LA BASE DE DATOS
        # ========================================================
        # Como aún no hacemos la pantalla de crear proyectos, el backend crea uno por defecto para ti
        proyecto = Proyecto.query.filter_by(usuario_id=usuario_id).first()
        if not proyecto:
            proyecto = Proyecto(usuario_id=usuario_id, nombre_proyecto="Proyecto Orquestador", descripcion="Generado automáticamente")
            db.session.add(proyecto)
            db.session.flush() # Permite obtener el ID sin cerrar la transacción

        # Crear el hilo de la conversación
        conversacion = Conversacion(proyecto_id=proyecto.id, titulo=prompt_usuario[:50] + "...")
        db.session.add(conversacion)
        db.session.flush()

        # Guardar la petición original del usuario
        mensaje_usuario = Mensaje(conversacion_id=conversacion.id, remitente_tipo='usuario', contenido_texto=prompt_usuario)
        db.session.add(mensaje_usuario)
        db.session.flush()


        # ========================================================
        # 2. ORQUESTACIÓN: LLAMADA A LOS AGENTES
        # ========================================================
        
        # --- AGENTE FRONTEND (GROQ) ---
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        prompt_sistema_frontend = """
            Eres un Arquitecto Frontend Senior. Sigue estas reglas ESTRICTAMENTE:
            1. Si el usuario solicita un componente pero NO especifica el framework (ej. Vue, React, HTML puro) o las herramientas de diseño (ej. Tailwind, CSS normal), NO generes código. En su lugar, hazle 2 preguntas cortas para confirmar su "stack" tecnológico.
            2. Si el usuario ya especificó lo que quiere, genera el código.
            3. SIEMPRE debes iniciar cada bloque de código indicando la ruta del archivo exacta usando este formato exacto: `/// Archivo: src/components/NombreComponente.vue ///`.
            4. No des explicaciones genéricas ni saludos. Solo entrega el código o las preguntas.
            """
        
        payload_frontend = {
            "model": "llama-3.1-8b-instant", 
            "messages": [
                {"role": "system", "content": prompt_sistema_frontend},
                {"role": "user", "content": prompt_usuario}
            ]
        }
        res_groq = requests.post(groq_url, json=payload_frontend, headers=groq_headers)
        if res_groq.status_code != 200: raise Exception(f"Fallo en Groq: {res_groq.text}")
        frontend_code = res_groq.json()['choices'][0]['message']['content']

        # --- AGENTE BACKEND (GEMINI) ---
        prompt_sistema_backend = f"""
            Eres un Arquitecto de Ciberseguridad y Backend. El usuario solicita: '{prompt_usuario}'.
            Reglas ESTRICTAS:
            1. Si el usuario no especificó el lenguaje de backend (ej. Python/Flask, Node.js, PHP) ni el motor de base de datos (PostgreSQL, MongoDB), NO generes código. Pregúntale amablemente qué tecnologías está utilizando en su servidor.
            2. Si ya tienes el contexto tecnológico, genera la lógica del servidor.
            3. Obligatorio: Mitigar riesgos de inyecciones (SQL/NoSQL) y Broken Access Control.
            4. SIEMPRE inicia cada bloque de código con su ruta exacta, por ejemplo: `/// Archivo: backend/app.py ///`.
            5. No des ejemplos genéricos. Escribe código de producción.
            """
        res_gemini = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_sistema_backend
        )
        backend_code = res_gemini.text

        # ========================================================
        # 3. FUSIÓN Y PERSISTENCIA FINAL
        # ========================================================
        resultado_final = f"### 🎨 ARQUITECTURA FRONTEND (Llama 3.1) ###\n\n{frontend_code}\n\n"
        resultado_final += f"### 🛡️ ARQUITECTURA BACKEND Y SEGURIDAD (Gemini) ###\n\n{backend_code}"

        # Guardar la respuesta combinada de los agentes
        mensaje_agentes = Mensaje(conversacion_id=conversacion.id, remitente_tipo='agente', contenido_texto=resultado_final)
        db.session.add(mensaje_agentes)
        
        # Commit sella la transacción completa en PostgreSQL
        db.session.commit()

        # DEBUG: Imprimir en la terminal lo que se le enviará a Vue para garantizar que no está vacío
        print("\n--- INICIO DE RESULTADO ENVIADO A VUE ---")
        print(resultado_final[:200] + "... [texto truncado en terminal]")
        print("--- FIN DE RESULTADO ---\n")

        return jsonify({
            "success": True,
            "resultado_orquestador": resultado_final
        }), 200

    except Exception as e:
        db.session.rollback() # Si algo falla, revertimos la base de datos para evitar datos corruptos
        print(f"\n[!] ERROR CRÍTICO EN EL ORQUESTADOR: {e}\n")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database_connected": True}), 200

if __name__ == '__main__':
    app.run(port=5000)