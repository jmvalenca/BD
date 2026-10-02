# Imagem do PostgreSQL com o SQL de inicialização embutido.
# Evita bind mounts da pasta do projeto (falham quando o projeto está em
# ~/Library/CloudStorage/... e a máquina virtual do Docker não tem acesso).
FROM postgres:17
# tzdata: para os containers poderem usar TZ=Europe/Lisbon
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY init.sql /docker-entrypoint-initdb.d/01_init.sql
COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh
