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
