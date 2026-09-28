# Funções partilhadas pelos scripts de gestão (não executar diretamente).
# Os comandos SQL correm no container "db" como utilizador postgres.

# ir para a pasta do projeto (onde está o docker-compose.yml)
cd "$(dirname "$0")/.." || exit 1

erro() { echo "Erro: $*" >&2; exit 1; }

# psql_bd BASE [opções psql...]  — SQL pelo stdin
psql_bd() {
    local base="$1"; shift
    if [ -n "${GESTAO_TESTE:-}" ]; then          # só para testes, sem Docker
        psql -X -q -v ON_ERROR_STOP=1 -d "$base" "$@"
    else
        docker compose exec -T db psql -X -q -U postgres -v ON_ERROR_STOP=1 -d "$base" "$@"
    fi
}

verificar_docker() {
    [ -n "${GESTAO_TESTE:-}" ] && return 0
    docker compose ps --status running -q db 2>/dev/null | grep -q . \
        || erro "o container da base de dados não está a correr (docker compose up -d)."
}

# nomes simples: minúsculas, algarismos e _, a começar por letra ou _
validar_nome() {
    [[ "$1" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] \
        || erro "nome inválido '$1' (use minúsculas, algarismos e _, até 63 caracteres)."
    [[ "$1" == postgres || "$1" == pg_* ]] && erro "o utilizador '$1' é reservado."
    return 0
}

existe_utilizador() {
    [ "$(echo "SELECT 1 FROM pg_roles WHERE rolname = '$1'" | psql_bd postgres -At)" = "1" ]
}
