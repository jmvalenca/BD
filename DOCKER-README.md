# Arrancar a aplicação com Docker

Na 1.ª vez, crie o ficheiro `.env` com a password do PostgreSQL
(o `.env` não vai para o Git):

```bash
cp .env.example .env   # e edite a password
```

Depois arranque os containers (PostgreSQL + backup + servidor marimo) com:

```bash
docker compose up --build -d
```

Depois abre <http://localhost:2718> e faz login com um utilizador da base de
dados (ex.: `postgres` com a password definida em `POSTGRES_PASSWORD` no `.env`).

- A base de dados `contabilidade` é criada automaticamente na 1.ª execução
  a partir do `docker/init.sql` (com a tabela `movimentos` e o trigger de saldo).
- Os dados persistem no volume `pgdata`; `docker compose down -v` apaga tudo.
- Para criar mais utilizadores (a app autentica-se diretamente no PostgreSQL):

```bash
docker compose exec db psql -U postgres -c \
  "CREATE ROLE contabilidade LOGIN PASSWORD 'segredo'"
docker compose exec db psql -U postgres -d contabilidade -c \
  "GRANT SELECT, INSERT, UPDATE, DELETE ON movimentos TO contabilidade"
```

## Backups

O container `backup` faz um backup diário da base de dados `contabilidade`
a partir da **01:00 (hora de Lisboa)** para a pasta **`backups/`** do projeto
(visível no Finder e incluída no Time Machine; não vai para o Git).

- Um ficheiro por dia: `backups/contabilidade_AAAA-MM-DD.sql.gz`; são
  mantidos os 30 mais recentes.
- Se o Mac estava desligado/a dormir à 01:00, o backup do dia é feito logo
  que o Docker volte a arrancar.
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
