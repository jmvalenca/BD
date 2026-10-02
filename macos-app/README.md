# Movimentos — aplicação macOS

App nativa (SwiftUI) para usar a aplicação **Movimentos** neste Mac ou a partir de outro Mac,
ligando-se por SSH ao servidor onde corre o Docker (Colima).

## Compilar

    cd macos-app
    ./build.sh

Requisitos: Xcode Command Line Tools (`xcode-select --install`) e acesso SSH
por chave à máquina do servidor (`ssh-copy-id utilizador@servidor`).

## Ícone

O `build.sh` gera o ícone da app a partir de `icone.png` (1024×1024;
`icone.svg` é o desenho original). Para usar outro ícone, substitua o
`icone.png` e volte a correr `./build.sh`. Se o Dock continuar a mostrar o
ícone antigo: `killall Dock`.

## Usar

Ao abrir, a app pergunta **onde está o servidor** (Enter escolhe a opção usada
da última vez; para trocar depois, use **Mudar…**):

- **Servidor local** — o Docker (Colima) corre neste Mac.
  1. Confirme a **pasta do repo** neste Mac (por omissão `~/Public/BD`).
  2. **Arrancar servidor** — corre o `arrancar.sh` do repo: arranca o Colima,
     se preciso, e `docker compose up -d --build`.
  3. **Abrir no browser** — abre <http://localhost:2718> assim que a
     aplicação responde.

- **Servidor remoto** — o Docker (Colima) corre noutro Mac, acedido por SSH.
  1. Confirme o **servidor** (utilizador@host) e a **pasta do repo** no servidor.
  2. **Arrancar servidor** — corre o `arrancar.sh` no servidor, por SSH.
  3. **Ligar** — cria o túnel SSH (porto 2718) e abre o browser assim que a
     aplicação responde.
  4. **Desligar** — fecha o túnel.

Em ambos os casos o Colima tem de estar instalado na máquina do servidor
(ver `DOCKER-README.md`). O modo e as definições são guardados entre utilizações.
