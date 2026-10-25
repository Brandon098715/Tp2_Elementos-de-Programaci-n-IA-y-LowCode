# Imagen de la API FastAPI.
# Se construye desde la RAÍZ del proyecto (lo indica compose.yaml),
# porque necesita también la carpeta core/.

FROM python:3.11-slim

# No generar archivos .pyc y mostrar los print() en los logs al instante.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Dependencias primero: Docker reutiliza esta capa si el código cambia pero los requisitos no.
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Código
COPY core/ core/
COPY api/ api/
COPY scripts/ scripts/
COPY data/seed.json data/seed.json

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
