# Movimentos — aplicação macOS

App nativa (SwiftUI) para usar a aplicação **Movimentos** a partir de outro Mac,
ligando-se por SSH ao servidor onde corre o Docker.

## Compilar

    cd macos-app
    ./build.sh

Requisitos: Xcode Command Line Tools (`xcode-select --install`) e acesso SSH
por chave à máquina do servidor (`ssh-copy-id utilizador@servidor`).

## Usar

1. Abra `Movimentos.app`, confirme o **servidor** (utilizador@host) e a **pasta
   do repo** no servidor.
2. **Arrancar servidor** — corre `docker compose up -d --build` no servidor.
3. **Ligar** — cria o túnel SSH (porto 2718) e abre o browser assim que a
   aplicação responde.
4. **Desligar** — fecha o túnel.

O estado atual e as definições são guardados entre utilizações.
