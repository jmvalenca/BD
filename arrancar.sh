#!/bin/bash
# Arranca a aplicação Movimentos neste Mac:
#   1. o Colima (a máquina virtual onde corre o Docker), se ainda não estiver ativo;
#   2. os containers (PostgreSQL + backup + marimo) com docker compose.
#
# Usado pela app macOS (modo local, e no modo remoto por SSH), mas também
# pode ser corrido à mão:  ./arrancar.sh
set -euo pipefail
cd "$(dirname "$0")"

# Apps abertas pelo Finder e sessões SSH não interativas não têm o
# Homebrew no PATH: acrescentá-lo aqui (Apple Silicon e Intel).
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

erro() { echo "Erro: $*" >&2; exit 1; }

command -v colima >/dev/null || erro "o Colima não está instalado (brew install colima docker docker-compose)."
command -v docker >/dev/null || erro "o cliente docker não está instalado (brew install docker docker-compose)."
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null; then
    COMPOSE=(docker-compose)
else
    erro "o docker compose não está instalado (brew install docker-compose; ver DOCKER-README.md)."
fi
[ -f .env ] || erro "falta o ficheiro .env (cp .env.example .env e defina a password)."

if ! colima status >/dev/null 2>&1; then
    echo "A arrancar o Colima…"
    colima start
fi

# Usar sempre o Docker do Colima (e não um Docker Desktop que ainda exista).
unset DOCKER_HOST
export DOCKER_CONTEXT=colima

"${COMPOSE[@]}" up -d --build
echo "Servidor ativo: http://localhost:2718"
