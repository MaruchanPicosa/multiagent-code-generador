from database import db
from datetime import datetime

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=False)
    foto_perfil = db.Column(db.Text)
    estado_cuenta = db.Column(db.String(20), default='activo')
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones binarias para jalar datos de forma limpia
    configuracion = db.relationship('ConfiguracionUsuario', backref='usuario', uselist=False, cascade="all, delete-orphan")
    sesiones = db.relationship('AuditoriaSesion', backref='usuario', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "nombre_completo": self.nombre_completo,
            "foto_perfil": self.foto_perfil,
            "estado_cuenta": self.estado_cuenta
        }

class ConfiguracionUsuario(db.Model):
    __tablename__ = 'configuracion_usuarios'

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True)
    tema_oscuro_activado = db.Column(db.Boolean, default=True)
    framework_favorito_frontend = db.Column(db.String(50), default='Tailwind + Vue')
    framework_favorito_backend = db.Column(db.String(50), default='Flask')

class AuditoriaSesion(db.Model):
    __tablename__ = 'auditoria_sesiones'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    direccion_ip = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text)
    fecha_login = db.Column(db.DateTime, default=datetime.utcnow)
    login_exitoso = db.Column(db.Boolean, nullable=False)

class Proyecto(db.Model):
    __tablename__ = 'proyectos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'))
    nombre_proyecto = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

class Conversacion(db.Model):
    __tablename__ = 'conversaciones'
    id = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id', ondelete='CASCADE'))
    titulo = db.Column(db.String(150), nullable=False)
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='abierto')

class Mensaje(db.Model):
    __tablename__ = 'mensajes'
    id = db.Column(db.Integer, primary_key=True)
    conversacion_id = db.Column(db.Integer, db.ForeignKey('conversaciones.id', ondelete='CASCADE'))
    remitente_tipo = db.Column(db.String(20), nullable=False)
    contenido_texto = db.Column(db.Text, nullable=False)
    fecha_envio = db.Column(db.DateTime, default=datetime.utcnow)

class ColaboradorProyecto(db.Model):
    __tablename__ = 'colaboradores_proyecto'
    id = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id', ondelete='CASCADE'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    rol_acceso = db.Column(db.String(30), nullable=False)
    fecha_invitacion = db.Column(db.DateTime, default=datetime.utcnow)

class RepositorioGit(db.Model):
    __tablename__ = 'repositorios_git'
    id = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id', ondelete='CASCADE'), nullable=False)
    url_repositorio = db.Column(db.String(255), nullable=False)
    proveedor = db.Column(db.String(50), nullable=False)
    rama_principal = db.Column(db.String(50), default='main')
    token_acceso_encriptado = db.Column(db.Text)
    fecha_vinculacion = db.Column(db.DateTime, default=datetime.utcnow)

class PerfilAgente(db.Model):
    __tablename__ = 'perfiles_agentes'
    id = db.Column(db.Integer, primary_key=True)
    nombre_agente = db.Column(db.String(100), nullable=False)
    modelo_ia = db.Column(db.String(50), nullable=False)
    entorno_especialidad = db.Column(db.String(50), nullable=False)
    prompt_sistema_base = db.Column(db.Text)
    temperatura = db.Column(db.Float, default=0.2)
    estado_activo = db.Column(db.Boolean, default=True)

class ReglaAuditoriaSeguridad(db.Model):
    __tablename__ = 'reglas_auditoria_seguridad'
    id = db.Column(db.Integer, primary_key=True)
    agente_id = db.Column(db.Integer, db.ForeignKey('perfiles_agentes.id', ondelete='CASCADE'), nullable=False)
    tipo_vulnerabilidad = db.Column(db.String(100), nullable=False)
    patron_analisis = db.Column(db.Text)
    descripcion_regla = db.Column(db.Text)
    nivel_severidad = db.Column(db.String(20), nullable=False)

class RegistroUsoApi(db.Model):
    __tablename__ = 'registro_uso_api'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'))
    agente_id = db.Column(db.Integer, db.ForeignKey('perfiles_agentes.id', ondelete='SET NULL'))
    tokens_consumidos = db.Column(db.Integer, nullable=False)
    fecha_peticion = db.Column(db.DateTime, default=datetime.utcnow)

class BloqueCodigo(db.Model):
    __tablename__ = 'bloques_codigo'
    id = db.Column(db.Integer, primary_key=True)
    mensaje_id = db.Column(db.Integer, db.ForeignKey('mensajes.id', ondelete='CASCADE'), nullable=False)
    lenguaje_programacion = db.Column(db.String(30), nullable=False)
    codigo_fuente = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)
    advertencias_seguridad = db.Column(db.Text)
    hash_verificacion = db.Column(db.String(64))