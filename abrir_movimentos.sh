#!/usr/bin/env bash
#
# abrir_movimentos.sh  —  script para o UTILIZADOR EXTERNO (macOS / Linux)
#
# Liga-se por SSH ao computador da base de dados, arranca lá a aplicação
# Marimo "movimentos.py" (através do iniciar_movimentos.sh) e abre a
# interface no browser DESTE computador, através de um túnel SSH.
#
# Uso:
#   ./abrir_movimentos.sh                      # usa os valores por omissão abaixo
#   ./abrir_movimentos.sh outro_user@outro-host
#   PORTA_LOCAL=3000 ./abrir_movimentos.sh
#
# Para terminar: Ctrl+C nesta janela, ou o botão "Fechar aplicação" na app.
#
# Requisitos neste computador: ssh e curl (já vêm com macOS e Linux).
# Requisitos no servidor: "Início de sessão remoto" (SSH) ativo e o uv
# instalado — ver iniciar_movimentos.sh.

set -euo pipefail

# ---- Configuração (pode ser alterada por variáveis de ambiente) -----------
DESTINO="${1:-${DESTINO:-josevalenca@mbp-de-jose}}"
SCRIPT_REMOTO="${SCRIPT_REMOTO:-~/Library/CloudStorage/Dropbox/BD/iniciar_movimentos.sh}"
PORTA_REMOTA="${PORTA_REMOTA:-2718}"   # porto do marimo no servidor
PORTA_LOCAL="${PORTA_LOCAL:-2718}"     # porto a usar no browser deste computador
ESPERA_MAX="${ESPERA_MAX:-180}"        # segundos (o 1.º arranque instala dependências)
# ---------------------------------------------------------------------------

for cmd in ssh curl; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Erro: falta o comando '$cmd'." >&2; exit 1; }
done

porta_ocupada() { curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$1" ; }

# Se o porto local já estiver em uso (p.ex. outra app), procura o seguinte livre.
while porta_ocupada "$PORTA_LOCAL" || { command -v lsof >/dev/null && lsof -iTCP:"$PORTA_LOCAL" -sTCP:LISTEN >/dev/null 2>&1; }; do
    PORTA_LOCAL=$((PORTA_LOCAL + 1))
done

URL="http://localhost:${PORTA_LOCAL}"

abrir_browser() {
    if [[ "$(uname)" == "Darwin" ]]; then open "$1"               # macOS
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1  # Linux
    else echo "Abra manualmente: $1"; fi
}

# Em segundo plano: espera que a app responda através do túnel e abre o browser.
(
    for ((i = 0; i < ESPERA_MAX; i++)); do
        sleep 1
        if porta_ocupada "$PORTA_LOCAL"; then
            echo
            echo ">>> Aplicação disponível em $URL — a abrir o browser..."
            abrir_browser "$URL"
            exit 0
        fi
    done
    echo ">>> A aplicação não respondeu em ${ESPERA_MAX}s. Veja as mensagens acima." >&2
) &
VIGIA=$!
trap 'kill "$VIGIA" 2>/dev/null || true' EXIT

echo "A ligar a $DESTINO e a arrancar a aplicação Movimentos..."
echo "(túnel: $URL  ->  servidor 127.0.0.1:$PORTA_REMOTA)"
echo

# -tt: cria um terminal remoto, para que Ctrl+C / fechar a ligação termine
#      também a aplicação no servidor.
# ExitOnForwardFailure: falha logo se o túnel não puder ser criado.
ssh -tt \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -L "${PORTA_LOCAL}:127.0.0.1:${PORTA_REMOTA}" \
    "$DESTINO" \
    "PORT=${PORTA_REMOTA} bash ${SCRIPT_REMOTO}"
