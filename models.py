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