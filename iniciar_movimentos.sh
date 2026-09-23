#!/usr/bin/env bash
#
# iniciar_movimentos.sh
#
# Arranca a aplicação Marimo "movimentos.py" no computador onde está a base
# de dados (esta máquina), ligada apenas a localhost. Um utilizador remoto
# invoca este script através de SSH, criando ao mesmo tempo um túnel para o
# porto da aplicação, e depois abre o browser na SUA própria máquina:
#
#   ssh -L 2718:localhost:2718 utilizador@este-computador \
#       'bash ~/caminho/para/iniciar_movimentos.sh'
#
# Neste caso
#   ssh -L 2718:localhost:2718 josevalenca@mbp-de-jose 'bash ~/Library/CloudStorage/Dropbox/BD/iniciar_movimentos.sh'
# ou, mais simples, o utilizador remoto corre o abrir_movimentos.sh (ou .cmd no Windows)
# Enquanto essa ligação SSH estiver aberta, a aplicação fica acessível em
# http://localhost:2718 no computador do utilizador remoto. Fechar a
# ligação SSH (ou o botão "Fechar aplicação" dentro da própria app) termina
# a aplicação.
#
# Requisitos nesta máquina (a da base de dados): apenas o "uv"
# (https://docs.astral.sh/uv/). A própria aplicação declara as suas
# dependências (marimo, psycopg) no cabeçalho do ficheiro movimentos.py, e
# o uv trata de as instalar num ambiente isolado (--sandbox) — não é preciso
# nenhuma instalação prévia de Python, marimo ou psycopg.

set -euo pipefail

# Porto onde a aplicação fica à escuta (tem de corresponder ao "-L" do
# comando ssh acima). Pode ser alterado com: PORT=3000 ./iniciar_movimentos.sh
PORT="${PORT:-2718}"

# Diretoria onde este script (e o movimentos.py) estão guardados.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$DIR/movimentos.py"

if [[ ! -f "$APP" ]]; then
    echo "Erro: não encontrei '$APP'." >&2
    echo "Coloque este script na mesma diretoria do movimentos.py." >&2
    exit 1
fi

# Numa sessão SSH não interativa o PATH é mínimo (não inclui o Homebrew),
# por isso procuramos o uv também nos locais de instalação habituais.
UV="$(command -v uv 2>/dev/null || true)"
for _c in /opt/homebrew/bin/uv /usr/local/bin/uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    [[ -z "$UV" && -x "$_c" ]] && UV="$_c"
done

if [[ -z "$UV" ]]; then
    echo "Erro: o comando 'uv' não está instalado nesta máquina." >&2
    echo "Instale com:  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "Verifique se 'uv' é acessível no PATH $PATH" >&2
    exit 1
fi

echo "A arrancar a aplicação Movimentos em http://127.0.0.1:${PORT}"
echo "(só acessível nesta máquina; use um túnel SSH para aceder remotamente)"
echo "Prima Ctrl+C, ou use o botão 'Fechar aplicação' na própria app, para terminar."
echo

# --sandbox: o marimo lê as dependências declaradas no cabeçalho do próprio
# movimentos.py (bloco "# /// script ... # ///") e cria/usa um ambiente uv
# isolado com elas, sem afetar o resto do sistema.
# --headless: não tenta abrir um browser nesta máquina (não faz sentido
#             numa sessão remota via SSH).
# --host 127.0.0.1: só aceita ligações locais; o acesso remoto é feito
#             exclusivamente através do túnel SSH (-L) usado para chamar
#             este script.
# O marimo --sandbox volta a chamar "uv" internamente, por isso tem de estar no PATH.
export PATH="$(dirname "$UV"):$PATH"

exec "$UV" run --with marimo marimo run "$APP" \
    --sandbox \
    --headless \
    --host 127.0.0.1 \
    --port "$PORT"
