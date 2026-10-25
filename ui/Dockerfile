# Imagen de la interfaz Streamlit.
# Solo necesita la carpeta ui/: habla con la API por HTTP (variable API_URL).

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui/ ui/

EXPOSE 8501

# --server.address=0.0.0.0 para que se pueda acceder desde fuera del contenedor.
CMD ["streamlit", "run", "ui/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
