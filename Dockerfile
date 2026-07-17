FROM python:3.10-slim

# Instalar Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Copiar configuración de Nginx y activar el sitio
COPY nginx.conf /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Exponer el puerto 80
EXPOSE 80

# Usamos un script simple para arrancar Nginx en segundo plano y Gunicorn en primer plano
CMD service nginx start && gunicorn --bind 0.0.0.0:5000 app:app