# Arrancar a aplicação com Docker (Colima)

O Docker corre no **Colima** (uma máquina virtual leve, sem o Docker Desktop).

## Instalação (uma vez)

```bash
brew install colima docker docker-compose
```

Para o comando `docker compose` funcionar, diga ao Docker onde está o plugin
(o Homebrew mostra esta indicação no fim da instalação). Em `~/.docker/config.json`:

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

Para o Colima arrancar sozinho quando entra no Mac (assim os containers e
o backup diário voltam a correr sem abrir a app):

```bash
brew services start colima
```

Na 1.ª vez, crie também o ficheiro `.env` com a password do PostgreSQL
(o `.env` não vai para o Git):

```bash
cp .env.example .env   # e edite a password
```

## Arrancar

```bash
./arrancar.sh
```

O `arrancar.sh` arranca o Colima (se ainda não estiver a correr) e depois os
containers (PostgreSQL + backup + servidor marimo) com
`docker compose up -d --build`. É o mesmo script que a app macOS usa.
Para parar: `docker compose stop` (e, se quiser, `colima stop`).

Depois abre <http://localhost:2718> e faz login com um utilizador da base de
dados (ex.: `postgres` com a password definida em `POSTGRES_PASSWORD` no `.env`).

- A base de dados `contabilidade` é criada automaticamente na 1.ª execução
  a partir do `docker/init.sql` (com a tabela `movimentos` e o trigger de saldo).
- Os dados persistem no volume `pgdata`; `docker compose down -v` apaga tudo.
- Para criar e remover utilizadores (a app autentica-se diretamente no
  PostgreSQL), use os scripts da pasta `gestao/` — ver abaixo.

## Gestão de utilizadores

Com os containers a correr, na pasta do projeto:

```bash
gestao/criar_utilizador.sh maria      # pede a password (2x, mín. 8 caracteres)
gestao/remover_utilizador.sh maria    # pede confirmação (ou --sim)
```

- O novo utilizador só tem os privilégios públicos: pode ligar-se, mas não
  vê a tabela `movimentos` nem é superutilizador. Para lhe dar acesso:

  ```bash
  docker compose exec db psql -U postgres -d contabilidade -c \
    "GRANT SELECT, INSERT, UPDATE, DELETE ON movimentos TO maria"
  ```

- Ao remover, as sessões abertas do utilizador são terminadas, os seus
  privilégios são retirados e as tabelas que tenha criado passam para o
  `postgres` (os dados não se perdem).

## Backups

O container `backup` faz um backup diário da base de dados `contabilidade`
a partir da **01:00 (hora de Lisboa)** para a pasta **`backups/`** do projeto
(visível no Finder e incluída no Time Machine; não vai para o Git).

- Um ficheiro por dia: `backups/contabilidade_AAAA-MM-DD.sql.gz`; são
  mantidos os 30 mais recentes.
- Se o Mac estava desligado/a dormir à 01:00, o backup do dia é feito logo
  que o Colima volte a arrancar.
- Um backup só é gravado se o `pg_dump` correr sem erros; em caso de falha
  tenta de novo a cada 15 minutos. Ver o registo com
  `docker compose logs backup`.
- `docker compose down -v` apaga a base de dados, mas **não** os backups.

Repor um backup numa base de dados vazia:

```bash
docker compose stop app      # fechar ligações à BD
docker compose exec db dropdb -U postgres contabilidade
docker compose exec db createdb -U postgres contabilidade
gunzip -c backups/contabilidade_AAAA-MM-DD.sql.gz | \
  docker compose exec -T db psql -U postgres -d contabilidade
docker compose start app
```

## Migrar do Docker Desktop para o Colima

Os dados da base de dados (volume `pgdata`) ficam dentro da máquina virtual
do Docker Desktop e **não passam sozinhos** para o Colima. Por isso:

1. **Ainda com o Docker Desktop a correr**, na pasta do projeto, exporte os
   utilizadores e a base de dados:

   ```bash
   docker compose exec -T db pg_dumpall -U postgres --roles-only > backups/migracao_utilizadores.sql
   docker compose exec -T db pg_dump -U postgres contabilidade | gzip > backups/migracao_contabilidade.sql.gz
   gzip -t backups/migracao_contabilidade.sql.gz && echo OK
   docker compose down          # SEM -v
   ```

2. Feche o Docker Desktop e desative "Start Docker Desktop when you sign in"
   (ou desinstale-o).

3. Instale o Colima (ver **Instalação** acima) e arranque:

   ```bash
   ./arrancar.sh
   ```

   Fica uma base de dados `contabilidade` nova e vazia.

4. Reponha os utilizadores e os dados:

   ```bash
   docker compose exec -T db psql -U postgres < backups/migracao_utilizadores.sql
   docker compose stop app
   docker compose exec db dropdb -U postgres contabilidade
   docker compose exec db createdb -U postgres contabilidade
   gunzip -c backups/migracao_contabilidade.sql.gz | \
     docker compose exec -T db psql -U postgres -d contabilidade
   docker compose start app
   ```

   (o aviso `role "postgres" already exists` é normal.)

5. Abra <http://localhost:2718> e confirme os movimentos e os saldos.
