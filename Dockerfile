FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gate: um build com os testes a falhar não chega a produção.
# 17 Set 2026 — sem `status` no payload, este serviço dizia "Payment: Cash
# Only" a clientes que já tinham pago (reserva 133, 500 EUR). O operador lê o
# PDF, assume que recebeu, e factura-nos o valor cheio.
RUN pip install --no-cache-dir pytest \
    && python -m pytest tests/ -q -p no:cacheprovider \
    && pip uninstall -y pytest

ENV PORT=8080
ENV FLASK_APP=main.py
CMD ["bash", "start.sh"]
