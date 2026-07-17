# Usamos una imagen de Python ligera y optimizada
FROM python:3.10-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos solo el archivo de requerimientos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalamos las dependencias y gunicorn para producción
RUN pip install --no-cache-dir -r requirements.txt gunicorn psycopg2-binary

# Copiamos el resto del código del proyecto
COPY . .

# Exponemos el puerto interno de la aplicación
EXPOSE 5000

# Comando para arrancar la aplicación con Gunicorn (Optimizado para producción)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]