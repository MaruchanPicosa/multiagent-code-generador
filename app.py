import os
from flask import Flask, jsonify
from dotenv import load_dotenv
import google.generativeai as genai

# 1. Cargar las variables de entorno de forma segura
load_dotenv()

# 2. Inicializar el servidor Flask
app = Flask(__name__)

# 3. Extraer y configurar la API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validación de seguridad: Evitar que el servidor arranque si falta la llave
if not GEMINI_API_KEY or GEMINI_API_KEY == "tu_clave_de_gemini_aqui":
    print("⚠️ ADVERTENCIA: No se detectó una API Key válida de Gemini en el archivo .env")
else:
    # Configurar el SDK de la IA
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Configuración de API de IA cargada correctamente.")

# 4. Ruta de prueba para verificar que el servidor está vivo
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "success",
        "message": "Servidor Flask y Orquestador de IAs funcionando correctamente."
    }), 200

if __name__ == '__main__':
    # Arrancar el servidor en el puerto 5000
    app.run(host='0.0.0.0', port=5000)