FROM python:3.12-slim

# Definir diretório de trabalho
WORKDIR /app

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema e ferramentas OCR (Tesseract)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copiar apenas os requisitos primeiro para cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o projeto
COPY . .

# Expor a porta
EXPOSE 8000

# Comando para rodar a aplicação
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
