# Usamos una versión ligera de Python
FROM python:3.10-slim

# Establecemos el directorio de trabajo
WORKDIR /app

# 1. Copiamos SOLO los requerimientos primero 
# (Esto hace que futuros despliegues sean rapidísimos usando la caché de Docker)
COPY requirements.txt .

# 2. Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copiamos el resto del código del proyecto
COPY . .

# Exponemos el puerto 8080 (es un estándar muy usado para contenedores)
EXPOSE 8080

# Arrancamos directamente tu app de Flask con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]