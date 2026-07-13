# Base image
FROM python:3.12-slim

# Evitar warnings de buffer
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema para pycups
RUN apt-get update && apt-get install -y \
    libcups2-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la app
COPY . .

RUN chmod +x /app/scripts/docker-entrypoint.sh

# Correr como usuario sin privilegios, no como root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Exponer puerto de la API
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Comando para correr el docker
CMD ["/app/scripts/docker-entrypoint.sh"]
