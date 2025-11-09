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
import uuid

# Configurar logging para archivo y consola
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Archivo
file_handler = logging.FileHandler('agent.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# Consola
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def get_real_ip():
    """Obtiene la IP real del host (no localhost)"""
    try:
        # Método 1: Conectar a un servidor externo (no envía datos, solo abre socket)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        # Conectar a DNS de Google (8.8.8.8) en puerto 80
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logging.warning(f"Método 1 falló: {e}")
    
    try:
        # Método 2: Buscar en interfaces de red
        addrs = psutil.net_if_addrs()
        for interface, addr_list in addrs.items():
            # Ignorar loopback y docker
            if interface.startswith(('lo', 'docker', 'br-', 'veth')):
                continue
            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    # Verificar que no sea localhost ni link-local
                    if not ip.startswith(('127.', '169.254.')):
                        logging.info(f"IP encontrada en interfaz {interface}: {ip}")
                        return ip
    except Exception as e:
        logging.warning(f"Método 2 falló: {e}")
    
    try:
        # Método 3: Hostname (puede devolver 127.0.0.1)
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except Exception as e:
        logging.warning(f"Método 3 falló: {e}")
    
    # Fallback
    logging.warning("No se pudo obtener IP real, usando 127.0.0.1")
    return "127.0.0.1"

def collect_system_info(agent_id):
    logging.info("Iniciando recolección de datos")
    
    # Obtener IP real del host
    ip = get_real_ip()
    logging.info(f"IP detectada: {ip}")
    
    cpu_info = {
        'count': psutil.cpu_count(),
        'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        'model': platform.processor() or "Desconocido"
    }
    
    processes = []
    try:
        # Primera llamada para inicializar
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Esperar un momento para que se acumulen datos
        time.sleep(0.1)
        
        # Segunda llamada para obtener el porcentaje real
        process_list = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.info
                # Obtener CPU% con un pequeño intervalo si es 0
                if pinfo['cpu_percent'] == 0:
                    pinfo['cpu_percent'] = proc.cpu_percent(interval=0.1)
                process_list.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Ordenar por CPU y tomar los top 10
        processes = sorted(process_list, key=lambda p: p.get('cpu_percent', 0), reverse=True)[:10]
        
    except psutil.AccessDenied as e:
        logging.error(f"Permisos insuficientes para procesos: {e}")
    except Exception as e:
        logging.error(f"Error recolectando procesos: {e}")
    
    # Usuarios del sistema
    users = []
    try:
        users = [user._asdict() for user in psutil.users()]
    except Exception as e:
        logging.error(f"Error recolectando usuarios: {e}")
    
    # Si no hay usuarios de sistema, intentar obtener info del proceso actual
    if not users:
        try:
            current_process = psutil.Process()
            users = [{
                'name': current_process.username(),
                'terminal': 'container' if os.path.exists('/.dockerenv') else 'local',
                'host': socket.gethostname(),
                'started': current_process.create_time()
            }]
        except Exception as e:
            logging.warning(f"No se pudo obtener info de usuario del proceso: {e}")
    
    os_info = {
        'name': platform.system(),
        'version': platform.version(),
        'release': platform.release(),
        'hostname': socket.gethostname()
    }
    
    data = {
        'ip': ip,
        'agent_id': agent_id,
        'cpu': cpu_info,
        'processes': processes,
        'users': users,
        'os': os_info,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    logging.info(f"Datos recolectados: CPU processes found: {len(processes)}")
    if processes:
        logging.info(f"Top process: {processes[0]['name']} - {processes[0]['cpu_percent']}%")
    
    return data

def send_to_api(data, api_url, retries=3, backoff=2):
    logging.info(f"Enviando datos a {api_url}")
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
    logging.info("Iniciando agente")
    api_url = os.getenv('API_URL', sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000/send')
    interval = int(os.getenv('COLLECT_INTERVAL', 60))
    agent_id = f"{platform.node()}-{uuid.uuid4()}"
    
    logging.info(f"Agent ID: {agent_id}")
    logging.info(f"API URL: {api_url}")
    logging.info(f"Intervalo: {interval}s")
    
    while True:
        try:
            logging.info("Nueva iteración")
            info = collect_system_info(agent_id)
            success = send_to_api(info, api_url)
            if success:
                print(f"✓ Enviado: IP={info['ip']}, {len(info['processes'])} procesos, CPU promedio: {info['cpu'].get('frequency', {}).get('current', 0)} MHz")
            else:
                print("✗ Fallo en envío. Datos locales guardados en log")
                logging.warning(json.dumps(info, indent=2))
        except Exception as e:
            print(f"Error en la recolección: {e}")
            logging.error(f"Error en la recolección: {e}", exc_info=True)
        time.sleep(interval)
