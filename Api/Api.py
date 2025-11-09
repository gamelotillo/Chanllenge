from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import aiofiles
import logging
from datetime import datetime
import csv
import io

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI(title="System Info API")

class SystemInfo(BaseModel):
    ip: str
    agent_id: Optional[str] = None
    cpu: dict
    processes: List[dict]
    users: List[dict]
    os: dict
    timestamp: str

async def save_to_json(data_entry, filename):
    try:
        if os.path.exists(filename):
            async with aiofiles.open(filename, 'r') as f:
                content = await f.read()
                existing = json.loads(content) if content else []
            existing.append(data_entry)
        else:
            existing = [data_entry]
        async with aiofiles.open(filename, 'w') as f:
            await f.write(json.dumps(existing, indent=2))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando JSON: {e}")

@app.post("/send")
async def receive_info(info: SystemInfo):
    timestamp_str = info.timestamp.replace(":", "-")
    filename = f"system_data_{timestamp_str}.json"
   
    data_entry = info.dict()
    data_entry['received_at'] = datetime.now().isoformat()
    await save_to_json(data_entry, filename)
   
    return {"status": "success", "filename": filename}

async def search_json_files(ip: str) -> List[dict]:
    results = []
    for file in os.listdir('.'):
        if not (file.startswith("system_data_") and file.endswith(".json")):
            continue
        try:
            async with aiofiles.open(file, 'r') as f:
                content = await f.read()
                data = json.loads(content) if content else []
                results.extend(entry for entry in data if entry['ip'] == ip)
        except Exception as e:
            logging.warning(f"Error al procesar el archivo {file}, se omitirá: {e}")
            continue
    return results

def get_all_data_from_json() -> List[dict]:
    """Obtiene todos los datos de los archivos JSON"""
    results = []
    for file in os.listdir('.'):
        if not (file.startswith("system_data_") and file.endswith(".json")):
            continue
        try:
            with open(file, 'r') as f:
                content = f.read()
                data = json.loads(content) if content else []
                results.extend(data)
        except Exception as e:
            logging.warning(f"Error al procesar el archivo {file}, se omitirá: {e}")
            continue
    return results

@app.get("/query")
async def query_info(ip: str = Query(..., description="IP a consultar")):
    results = await search_json_files(ip)
   
    if not results:
        raise HTTPException(status_code=404, detail="IP no encontrada")
    return {"results": results}

@app.get("/download/json")
async def download_json(ip: Optional[str] = None):
    """Descarga todos los datos o filtrados por IP en formato JSON"""
    if ip:
        results = await search_json_files(ip)
    else:
        results = get_all_data_from_json()
   
    if not results:
        raise HTTPException(status_code=404, detail="No hay datos disponibles")
   
    json_str = json.dumps(results, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
    )

@app.get("/download/csv")
async def download_csv(ip: Optional[str] = None):
    """Descarga todos los datos o filtrados por IP en formato CSV"""
    if ip:
        results = await search_json_files(ip)
    else:
        results = get_all_data_from_json()
   
    if not results:
        raise HTTPException(status_code=404, detail="No hay datos disponibles")
   
    output = io.StringIO()
    fieldnames = ['ip', 'agent_id', 'cpu_count', 'cpu_frequency', 'os_name', 'os_version', 'timestamp', 'received_at']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
   
    for item in results:
        cpu_data = item.get('cpu', {})
        os_data = item.get('os', {})
        writer.writerow({
            'ip': item['ip'],
            'agent_id': item.get('agent_id', ''),
            'cpu_count': cpu_data.get('count', ''),
            'cpu_frequency': cpu_data.get('frequency', {}).get('current', ''),
            'os_name': os_data.get('name', ''),
            'os_version': os_data.get('version', ''),
            'timestamp': item['timestamp'],
            'received_at': item['received_at']
        })
   
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Dashboard completo con gráficos, procesos, usuarios y alertas"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>System Monitor Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #fff;
                padding: 20px;
            }
            .container { max-width: 1600px; margin: 0 auto; }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
            }
            .header h1 { font-size: 2.5em; margin-bottom: 10px; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
                padding: 25px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 8px 16px rgba(0,0,0,0.3);
                transition: transform 0.3s;
            }
            .stat-card:hover { transform: translateY(-5px); }
            .stat-value {
                font-size: 2.5em;
                font-weight: bold;
                background: linear-gradient(45deg, #4CAF50, #8BC34A);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .stat-label { color: #999; margin-top: 10px; font-size: 0.9em; }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .chart-container {
                background: rgba(45, 45, 45, 0.8);
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 8px 16px rgba(0,0,0,0.3);
            }
            .chart-container h3 {
                margin-bottom: 15px;
                color: #4CAF50;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }
            .table-container {
                background: rgba(45, 45, 45, 0.8);
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 8px 16px rgba(0,0,0,0.3);
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #444;
            }
            th {
                background: #1a1a1a;
                color: #4CAF50;
                font-weight: 600;
            }
            tr:hover { background: rgba(76, 175, 80, 0.1); }
            .alert {
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 5px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .alert-warning {
                background: rgba(255, 152, 0, 0.2);
                border-left: 4px solid #FF9800;
            }
            .alert-danger {
                background: rgba(244, 67, 54, 0.2);
                border-left: 4px solid #F44336;
            }
            .download-section {
                text-align: center;
                padding: 30px;
                background: rgba(45, 45, 45, 0.8);
                border-radius: 10px;
                margin-top: 20px;
            }
            .btn {
                background: linear-gradient(45deg, #4CAF50, #8BC34A);
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                margin: 0 10px;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.4);
            }
            .btn-secondary {
                background: linear-gradient(45deg, #2196F3, #03A9F4);
            }
            .badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .badge-success { background: #4CAF50; color: white; }
            .badge-warning { background: #FF9800; color: white; }
            .badge-danger { background: #F44336; color: white; }
            .search-box {
                margin: 20px 0;
                padding: 15px;
                background: rgba(45, 45, 45, 0.8);
                border-radius: 10px;
            }
            .search-box input {
                width: 100%;
                padding: 12px;
                border: 2px solid #444;
                border-radius: 5px;
                background: #1a1a1a;
                color: #fff;
                font-size: 16px;
            }
            .search-box input:focus {
                outline: none;
                border-color: #4CAF50;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🖥️ System Monitor Dashboard</h1>
                <p>Monitoreo completo en tiempo real del sistema</p>
            </div>
           
            <!-- Estadísticas principales -->
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="totalRecords">0</div>
                    <div class="stat-label">Total Registros</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="activeAgents">0</div>
                    <div class="stat-label">Agentes Activos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avgCpu">0%</div>
                    <div class="stat-label">CPU Promedio</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalProcesses">0</div>
                    <div class="stat-label">Procesos Monitoreados</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="activeUsers">0</div>
                    <div class="stat-label">Usuarios Conectados</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="lastUpdate">-</div>
                    <div class="stat-label">Última Actualización</div>
                </div>
            </div>

            <!-- Alertas -->
            <div class="table-container" id="alertsSection" style="display:none;">
                <h3>⚠️ Alertas del Sistema</h3>
                <div id="alertsContainer"></div>
            </div>

            <!-- Gráficos principales -->
            <div class="grid">
                <div class="chart-container">
                    <h3>📊 Frecuencia CPU en el Tiempo</h3>
                    <canvas id="cpuChart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>💻 Distribución de Sistemas Operativos</h3>
                    <canvas id="osChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <h3>🌐 Actividad por IP</h3>
                <canvas id="ipChart"></canvas>
            </div>

            <!-- Procesos Top por CPU -->
            <div class="table-container">
                <h3>🔥 Procesos con Mayor Uso de CPU</h3>
                <div class="search-box">
                    <input type="text" id="processSearch" placeholder="🔍 Buscar proceso por nombre...">
                </div>
                <table id="processTable">
                    <thead>
                        <tr>
                            <th>Proceso</th>
                            <th>PID</th>
                            <th>CPU %</th>
                            <th>IP / Agente</th>
                            <th>Estado</th>
                            <th>Última vez visto</th>
                        </tr>
                    </thead>
                    <tbody id="processTableBody">
                        <tr><td colspan="6" style="text-align:center; color:#666;">Cargando datos...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Gráfico de procesos -->
            <div class="chart-container">
                <h3>📈 Top 10 Procesos por Consumo de CPU</h3>
                <canvas id="processChart"></canvas>
            </div>

            <!-- Usuarios conectados -->
            <div class="table-container">
                <h3>👥 Usuarios Conectados</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Usuario</th>
                            <th>Terminal</th>
                            <th>Host</th>
                            <th>IP / Agente</th>
                            <th>Conectado desde</th>
                        </tr>
                    </thead>
                    <tbody id="usersTableBody">
                        <tr><td colspan="5" style="text-align:center; color:#666;">Cargando datos...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Histórico de procesos problemáticos -->
            <div class="table-container">
                <h3>⚡ Histórico de Procesos con Alto Consumo (>50% CPU)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Proceso</th>
                            <th>PID</th>
                            <th>CPU %</th>
                            <th>IP</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody id="highCpuTableBody">
                        <tr><td colspan="5" style="text-align:center; color:#666;">Cargando datos...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Descargas -->
            <div class="download-section">
                <h3>📥 Descargar Datos</h3>
                <a href="/download/json" class="btn" download>Descargar JSON</a>
                <a href="/download/csv" class="btn btn-secondary" download>Descargar CSV</a>
            </div>
        </div>

        <script>
            // Configuración de gráficos con Chart.js 4.x
            const cpuCtx = document.getElementById('cpuChart').getContext('2d');
            const osCtx = document.getElementById('osChart').getContext('2d');
            const ipCtx = document.getElementById('ipChart').getContext('2d');
            const processCtx = document.getElementById('processChart').getContext('2d');

            const chartOptions = {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { 
                    legend: { 
                        labels: { color: '#fff' } 
                    } 
                },
                scales: {
                    y: { 
                        beginAtZero: true, 
                        ticks: { color: '#999' }, 
                        grid: { color: '#444' } 
                    },
                    x: { 
                        ticks: { color: '#999' }, 
                        grid: { color: '#444' } 
                    }
                }
            };

            const cpuChart = new Chart(cpuCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Frecuencia CPU (MHz)',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: chartOptions
            });

            const osChart = new Chart(osCtx, {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { labels: { color: '#fff' } } }
                }
            });

            const ipChart = new Chart(ipCtx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Registros por IP',
                        data: [],
                        backgroundColor: '#2196F3'
                    }]
                },
                options: chartOptions
            });

            // CORRECCIÓN: Cambiar horizontalBar por bar con indexAxis: 'y'
            const processChart = new Chart(processCtx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU %',
                        data: [],
                        backgroundColor: 'rgba(255, 152, 0, 0.8)'
                    }]
                },
                options: {
                    indexAxis: 'y',  // ESTO LO HACE HORIZONTAL
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { labels: { color: '#fff' } } },
                    scales: {
                        x: { 
                            beginAtZero: true, 
                            ticks: { color: '#999' }, 
                            grid: { color: '#444' } 
                        },
                        y: { 
                            ticks: { color: '#999' }, 
                            grid: { color: '#444' } 
                        }
                    }
                }
            });

            // Búsqueda de procesos
            document.getElementById('processSearch').addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase();
                const rows = document.querySelectorAll('#processTableBody tr');
                rows.forEach(row => {
                    const processName = row.cells[0]?.textContent.toLowerCase() || '';
                    row.style.display = processName.includes(searchTerm) ? '' : 'none';
                });
            });

            // Función para actualizar dashboard
            async function updateDashboard() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();

                    console.log('Data received:', data); // Debug

                    // Actualizar estadísticas
                    document.getElementById('totalRecords').textContent = data.total_records;
                    document.getElementById('activeAgents').textContent = data.active_agents;
                    document.getElementById('avgCpu').textContent = data.avg_cpu.toFixed(1) + '%';
                    document.getElementById('totalProcesses').textContent = data.total_processes;
                    document.getElementById('activeUsers').textContent = data.active_users;
                    document.getElementById('lastUpdate').textContent = new Date(data.last_update).toLocaleTimeString();

                    // Actualizar alertas
                    if (data.alerts && data.alerts.length > 0) {
                        document.getElementById('alertsSection').style.display = 'block';
                        document.getElementById('alertsContainer').innerHTML = data.alerts.map(alert => 
                            `<div class="alert alert-${alert.type}">
                                <span style="font-size: 1.5em;">${alert.icon}</span>
                                <span>${alert.message}</span>
                            </div>`
                        ).join('');
                    } else {
                        document.getElementById('alertsSection').style.display = 'none';
                    }

                    // Actualizar gráficos
                    cpuChart.data.labels = data.cpu_timeline.labels;
                    cpuChart.data.datasets[0].data = data.cpu_timeline.data;
                    cpuChart.update();

                    osChart.data.labels = data.os_distribution.labels;
                    osChart.data.datasets[0].data = data.os_distribution.data;
                    osChart.update();

                    ipChart.data.labels = data.ip_activity.labels;
                    ipChart.data.datasets[0].data = data.ip_activity.data;
                    ipChart.update();

                    processChart.data.labels = data.top_processes.labels;
                    processChart.data.datasets[0].data = data.top_processes.data;
                    processChart.update();

                    // Actualizar tabla de procesos
                    const processTableBody = document.getElementById('processTableBody');
                    if (data.processes && data.processes.length > 0) {
                        processTableBody.innerHTML = data.processes.map(proc => {
                            const cpuPercent = proc.cpu_percent || 0;
                            const badge = cpuPercent > 70 ? 'danger' : cpuPercent > 40 ? 'warning' : 'success';
                            return `
                                <tr>
                                    <td><strong>${proc.name}</strong></td>
                                    <td>${proc.pid}</td>
                                    <td><span class="badge badge-${badge}">${cpuPercent.toFixed(1)}%</span></td>
                                    <td>${proc.ip}</td>
                                    <td><span class="badge badge-success">Activo</span></td>
                                    <td>${new Date(proc.timestamp).toLocaleString()}</td>
                                </tr>
                            `;
                        }).join('');
                    } else {
                        processTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#666;">No hay datos disponibles</td></tr>';
                    }

                    // Actualizar tabla de usuarios
                    const usersTableBody = document.getElementById('usersTableBody');
                    if (data.users && data.users.length > 0) {
                        usersTableBody.innerHTML = data.users.map(user => `
                            <tr>
                                <td><strong>${user.name}</strong></td>
                                <td>${user.terminal}</td>
                                <td>${user.host}</td>
                                <td>${user.ip}</td>
                                <td>${new Date(user.started * 1000).toLocaleString()}</td>
                            </tr>
                        `).join('');
                    } else {
                        usersTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#666;">No hay usuarios conectados</td></tr>';
                    }

                    // Actualizar tabla de procesos con alto CPU
                    const highCpuTableBody = document.getElementById('highCpuTableBody');
                    if (data.high_cpu_processes && data.high_cpu_processes.length > 0) {
                        highCpuTableBody.innerHTML = data.high_cpu_processes.map(proc => `
                            <tr>
                                <td><strong>${proc.name}</strong></td>
                                <td>${proc.pid}</td>
                                <td><span class="badge badge-danger">${proc.cpu_percent.toFixed(1)}%</span></td>
                                <td>${proc.ip}</td>
                                <td>${new Date(proc.timestamp).toLocaleString()}</td>
                            </tr>
                        `).join('');
                    } else {
                        highCpuTableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#666;">No hay procesos con alto consumo</td></tr>';
                    }

                } catch (error) {
                    console.error('Error actualizando dashboard:', error);
                }
            }

            // Actualizar cada 5 segundos
            updateDashboard();
            setInterval(updateDashboard, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/stats")
async def get_stats():
    """Endpoint completo con estadísticas, procesos, usuarios y alertas"""
    data = get_all_data_from_json()
   
    if not data:
        return {
            "total_records": 0,
            "active_agents": 0,
            "avg_cpu": 0,
            "total_processes": 0,
            "active_users": 0,
            "last_update": datetime.now().isoformat(),
            "cpu_timeline": {"labels": [], "data": []},
            "os_distribution": {"labels": [], "data": []},
            "ip_activity": {"labels": [], "data": []},
            "top_processes": {"labels": [], "data": []},
            "processes": [],
            "users": [],
            "high_cpu_processes": [],
            "alerts": []
        }
   
    # Estadísticas básicas
    total_records = len(data)
    
    # Contar agentes únicos (considerando solo los últimos 5 minutos como activos)
    recent_agents = set()
    cutoff_time = datetime.now().timestamp() - 300  # 5 minutos
    for item in data:
        try:
            item_time = datetime.fromisoformat(item.get('received_at', item.get('timestamp'))).timestamp()
            if item_time > cutoff_time and item.get('agent_id'):
                recent_agents.add(item['agent_id'])
        except:
            if item.get('agent_id'):
                recent_agents.add(item['agent_id'])
    
    unique_agents = len(recent_agents)
   
    # CPU promedio
    cpu_freqs = [item['cpu'].get('frequency', {}).get('current', 0) for item in data if item.get('cpu')]
    avg_cpu = sum(cpu_freqs) / len(cpu_freqs) if cpu_freqs else 0
   
    # Timeline de CPU (últimos 20 registros)
    recent_data = sorted(data, key=lambda x: x['timestamp'])[-20:]
    cpu_timeline = {
        "labels": [item['timestamp'].split('T')[1][:8] for item in recent_data],
        "data": [item['cpu'].get('frequency', {}).get('current', 0) for item in recent_data]
    }
   
    # Distribución de OS (por agente único, no por registro)
    os_by_agent = {}
    for item in data:
        agent_id = item.get('agent_id', item.get('ip'))  # Usar agent_id o IP como fallback
        os_name = item.get('os', {}).get('name', 'Unknown')
        # Solo contar cada agente una vez
        if agent_id:
            os_by_agent[agent_id] = os_name
    
    # Contar cuántos agentes por OS
    os_counts = {}
    for os_name in os_by_agent.values():
        os_counts[os_name] = os_counts.get(os_name, 0) + 1
   
    os_distribution = {
        "labels": list(os_counts.keys()),
        "data": list(os_counts.values())
    }
   
    # Actividad por IP (por agente único, no por registro)
    ip_by_agent = {}
    for item in data:
        agent_id = item.get('agent_id', item.get('ip'))
        ip = item['ip']
        # Guardar la IP de cada agente único
        if agent_id:
            ip_by_agent[agent_id] = ip
    
    # Contar cuántos agentes por IP
    ip_counts = {}
    for ip in ip_by_agent.values():
        ip_counts[ip] = ip_counts.get(ip, 0) + 1
   
    ip_activity = {
        "labels": list(ip_counts.keys()),
        "data": list(ip_counts.values())
    }
    
    # Procesos más recientes y su análisis
    latest_data = sorted(data, key=lambda x: x['timestamp'])[-10:]
    all_processes = []
    for item in latest_data:
        for proc in item.get('processes', []):
            all_processes.append({
                'name': proc.get('name', 'Unknown'),
                'pid': proc.get('pid', 0),
                'cpu_percent': proc.get('cpu_percent', 0),
                'ip': item['ip'],
                'timestamp': item['timestamp']
            })
    
    # Top 10 procesos por CPU
    top_processes_list = sorted(all_processes, key=lambda x: x['cpu_percent'], reverse=True)[:10]
    top_processes = {
        "labels": [f"{p['name']} (PID: {p['pid']})" for p in top_processes_list],
        "data": [p['cpu_percent'] for p in top_processes_list]
    }
    
    # Procesos con alto consumo (>50%)
    high_cpu_processes = [p for p in all_processes if p['cpu_percent'] > 50][:20]
    
    # Total de procesos únicos
    total_processes = len(set(p['name'] for p in all_processes))
    
    # Usuarios conectados (últimos datos)
    all_users = []
    for item in latest_data:
        for user in item.get('users', []):
            user_copy = user.copy()
            user_copy['ip'] = item['ip']
            all_users.append(user_copy)
    
    # Eliminar usuarios duplicados
    unique_users = []
    seen = set()
    for user in all_users:
        key = f"{user.get('name')}-{user.get('terminal')}-{user.get('ip')}"
        if key not in seen:
            seen.add(key)
            unique_users.append(user)
    
    active_users = len(unique_users)
    
    # Generar alertas
    alerts = []
    
    # Alerta de procesos con alto CPU
    critical_processes = [p for p in all_processes if p['cpu_percent'] > 80]
    if critical_processes:
        alerts.append({
            "type": "danger",
            "icon": "🔴",
            "message": f"⚠️ {len(critical_processes)} proceso(s) con CPU crítico (>80%)"
        })
    
    # Alerta de procesos con CPU alto
    warning_processes = [p for p in all_processes if 50 < p['cpu_percent'] <= 80]
    if warning_processes:
        alerts.append({
            "type": "warning",
            "icon": "🟡",
            "message": f"⚠️ {len(warning_processes)} proceso(s) con CPU elevado (50-80%)"
        })
    
    # Alerta si no hay datos recientes
    if data:
        last_timestamp = datetime.fromisoformat(data[-1]['received_at'])
        time_diff = (datetime.now() - last_timestamp).total_seconds()
        if time_diff > 120:  # Más de 2 minutos sin datos
            alerts.append({
                "type": "warning",
                "icon": "⏰",
                "message": f"No se han recibido datos en {int(time_diff/60)} minuto(s)"
            })
    
    return {
        "total_records": total_records,
        "active_agents": unique_agents,
        "avg_cpu": avg_cpu / 1000,  # Convertir MHz a GHz
        "total_processes": total_processes,
        "active_users": active_users,
        "last_update": data[-1]['received_at'] if data else datetime.now().isoformat(),
        "cpu_timeline": cpu_timeline,
        "os_distribution": os_distribution,
        "ip_activity": ip_activity,
        "top_processes": top_processes,
        "processes": top_processes_list,
        "users": unique_users,
        "high_cpu_processes": high_cpu_processes,
        "alerts": alerts
    }