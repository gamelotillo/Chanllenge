# Dockerfile para Api.py (Multi-Stage Build con Imagen Base Forzada)
#
# OBJETIVO: Instalar dependencias compiladas y luego ELIMINAR las herramientas de compilación
# y sus dependencias vulnerables del entorno final. Se usa la ruta de Python 3.14.

# --------------------------
# ETAPA 1: BUILDER (Compilación)
# --------------------------
# Usamos la imagen base solicitada. Esta etapa contiene las herramientas de compilación.
FROM gamelotillo/python_fixed:latest AS builder

# 1. Instalar dependencias de compilación (requeridas para librerías como numpy, cryptography, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    git && \
    # Limpieza de caché
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copiar requirements.txt e instalar dependencias de Python
# Esto genera el entorno de site-packages compilado que copiaremos a la etapa final.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación (solo Api.py)
COPY Api.py .


# --------------------------
# ETAPA 2: PRODUCTION (Ejecución Limpia)
# --------------------------
# Usamos la misma imagen base, pero la limpiaremos drásticamente.
FROM gamelotillo/python_fixed:latest AS production

# Establecer el directorio de trabajo
WORKDIR /app

# 3. Copiar SÓLO los archivos esenciales del 'builder'
# CRÍTICO: Copiamos la carpeta de site-packages de Python 3.14 y el archivo Api.py.
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
# *** CORRECCIÓN CRÍTICA: COPIAR LOS EJECUTABLES DE PYTHON (donde está uvicorn) ***
COPY --from=builder /usr/local/bin /usr/local/bin
# ********************************************************************************
COPY --from=builder /app/Api.py /app/


# --- Inicio de la Limpieza Crítica ---
# 4. LIMPIEZA CRÍTICA: Desinstalar Paquetes de Compilación y Vulnerabilidades
# Eliminamos build-essential y sus dependencias transitorias.
RUN apt-get update && \
    # 4.1. Eliminar paquetes de compilación con --purge para borrar archivos de configuración
    apt-get remove --purge -y \
    gcc \
    g++ \
    build-essential \
    git && \
    # 4.2. autoremove elimina dependencias instaladas que ya no son necesarias (como linux-libc-dev)
    apt-get autoremove -y && \
    # 4.3. Limpieza final
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# --- Fin de la Limpieza Crítica ---

# 5. Configuración de seguridad (usuario no-root)
RUN groupadd -r apiuser && useradd -r -g apiuser apiuser

# Crear directorio para datos y dar permisos
RUN mkdir -p /app/data && chown -R apiuser:apiuser /app

# Cambiar a usuario no-root
USER apiuser

EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "Api:app", "--host", "0.0.0.0", "--port", "8000"]