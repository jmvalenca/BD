# Servidor da aplicação Movimentos (marimo + psycopg)
FROM python:3.14-slim

WORKDIR /app

# Dependências declaradas no cabeçalho do movimentos.py
RUN pip install --no-cache-dir \
    "marimo>=0.24.2" \
    "psycopg[binary]==3.3.6"

# Código da aplicação
COPY movimentos.py .

EXPOSE 2718

# --headless : não tenta abrir browser (servidor)
# --no-token: a app já tem o seu próprio ecrã de autenticação (login de BD);
#             remova esta opção se o porto 2718 ficar exposto a redes não confiáveis.
CMD ["marimo", "run", "movimentos.py", \
     "--headless", "--host", "0.0.0.0", "--port", "2718", "--no-token"]
