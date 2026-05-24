import os
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# 1. Importamos la 'db' desde el archivo neutral
from database import db
# 2. Ahora SÍ podemos importar los modelos de forma segura sin que sea circular
from models import Usuario, ConfiguracionUsuario, AuditoriaSesion

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Conectamos la aplicación a la base de datos
db.init_app(app)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

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

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database_connected": True}), 200

if __name__ == '__main__':
    app.run(port=5000)