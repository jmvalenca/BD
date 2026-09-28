#!/bin/bash
# Remove um utilizador do PostgreSQL.
# - termina as sessões abertas desse utilizador;
# - em cada base de dados, passa os objetos que ele criou para o postgres
#   (os dados NÃO são apagados) e retira-lhe todos os privilégios;
# - apaga o utilizador.
#
# Uso:  gestao/remover_utilizador.sh nome [--sim]
#       --sim  não pede confirmação
set -uo pipefail
source "$(dirname "$0")/comum.sh"

NOME="${1:-}"
[ -z "$NOME" ] && read -rp "Nome do utilizador a remover: " NOME
validar_nome "$NOME"
verificar_docker
existe_utilizador "$NOME" || erro "o utilizador '$NOME' não existe."

if [ "${2:-}" != "--sim" ]; then
    read -rp "Escreva o nome '$NOME' para confirmar a remoção: " CONF
    [ "$CONF" = "$NOME" ] || erro "remoção cancelada."
fi

echo "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = '$NOME'" \
    | psql_bd postgres -At >/dev/null

BASES=$(echo "SELECT datname FROM pg_database WHERE datallowconn" | psql_bd postgres -At) \
    || erro "não foi possível listar as bases de dados."
for BASE in $BASES; do
    psql_bd "$BASE" <<SQL || erro "falhou a limpeza na base '$BASE'."
REASSIGN OWNED BY "$NOME" TO postgres;
DROP OWNED BY "$NOME";
SQL
done

echo "DROP ROLE \"$NOME\";" | psql_bd postgres || erro "não foi possível remover o utilizador."
echo "Utilizador '$NOME' removido."
