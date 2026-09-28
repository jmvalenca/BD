#!/bin/bash
# Cria um utilizador (role com LOGIN) no PostgreSQL, apenas com os
# privilégios concedidos a PUBLIC: pode ligar-se, mas não recebe acesso
# a nenhuma tabela (p. ex. movimentos) nem é superutilizador.
#
# Uso:  gestao/criar_utilizador.sh [nome]
#       (a password é pedida no terminal, sem aparecer no ecrã)
set -uo pipefail
source "$(dirname "$0")/comum.sh"

NOME="${1:-}"
[ -z "$NOME" ] && read -rp "Nome do novo utilizador: " NOME
validar_nome "$NOME"
verificar_docker
existe_utilizador "$NOME" && erro "o utilizador '$NOME' já existe."

read -rsp "Password: " PW; echo
read -rsp "Repita a password: " PW2; echo
[ "$PW" = "$PW2" ] || erro "as passwords não coincidem."
[ ${#PW} -ge 8 ] || erro "a password deve ter pelo menos 8 caracteres."

# password enviada pelo stdin (não fica na linha de comandos nem no histórico)
PW_SQL=$(printf '%s' "$PW" | sed "s/'/''/g")
psql_bd postgres <<SQL || erro "não foi possível criar o utilizador."
CREATE ROLE "$NOME" LOGIN PASSWORD '$PW_SQL'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SQL
unset PW PW2 PW_SQL

echo "Utilizador '$NOME' criado (só com privilégios públicos)."
echo "Para lhe dar acesso aos movimentos, p. ex.:"
echo "  docker compose exec db psql -U postgres -d contabilidade -c 'GRANT SELECT ON movimentos TO $NOME'"
