# Imagem do PostgreSQL com o SQL de inicialização embutido.
# Evita bind mounts da pasta do projeto (falham quando o projeto está em
# ~/Library/CloudStorage/... e o Docker Desktop não tem permissão de acesso).
FROM postgres:17
COPY init.sql /docker-entrypoint-initdb.d/01_init.sql
COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh
