import platform
import psutil
import socket
import json
import requests
import sys
import datetime
import logging
import os
import time

# Configurar logging
logging.basicConfig(filename='agent.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def collect_system_info():
    # IP local
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        ip = "127.0.0.1"
        logging.warning("No se pudo obtener IP, usando fallback.")
    
    # Procesador
    cpu_info = {
        'count': psutil.cpu_count(),
        'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        'model': platform.processor() or "Desconocido"
    }
    
    # Procesos (top 10 por CPU)
    processes = []
    try:
        for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), 
                          key=lambda p: p.info['cpu_percent'], reverse=True)[:10]:
            processes.append(proc.info)
    except psutil.AccessDenied:
        logging.error("Permisos insuficientes para procesos.")
    
    # Usuarios
    users = [user._asdict() for user in psutil.users()]
    
    # SO
    os_info = {
        'name': platform.system(),
        'version': platform.version(),
        'release': platform.release()
    }
    
    return {
        'ip': ip,
        'cpu': cpu_info,
        'processes': processes,
        'users': users,
        'os': os_info,
        'timestamp': datetime.datetime.now().isoformat()
    }

def send_to_api(data, api_url, retries=3, backoff=2):
    for attempt in range(retries):
        try:
            response = requests.post(api_url, json=data, timeout=10)
            if response.status_code == 200:
                print("Datos enviados exitosamente.")
                logging.info("Envío exitoso.")
                return True
            else:
                print(f"Error HTTP: {response.status_code}")
                logging.error(f"Error HTTP: {response.status_code}")
        except Exception as e:
            print(f"Error en envío: {e}")
            logging.error(f"Error: {e}")
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    logging.error("Fallo tras reintentos.")
    return False

if __name__ == "__main__":
    api_url = os.getenv('API_URL', sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000/send')
    info = collect_system_info()
    success = send_to_api(info, api_url)
    if success:
        print(json.dumps(info, indent=2))
    else:
        print("Fallo en envío. Datos locales:")
        print(json.dumps(info, indent=2))