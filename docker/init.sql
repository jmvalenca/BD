-- Criação da base de dados "contabilidade" para a aplicação Movimentos.
-- Executado automaticamente pelo PostgreSQL na 1.ª inicialização do container
-- (via /docker-entrypoint-initdb.d/), quando o volume pgdata está vazio.
--
-- Mantém-se igual à estrutura criada pelo movimentos.py (célula de setup),
-- para que a base de dados fique correta mesmo antes de o notebook arrancar.

CREATE DATABASE contabilidade ENCODING 'UTF8';

-- Ligar à nova base de dados
\c contabilidade

CREATE TABLE movimentos (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente     TEXT           NOT NULL,
    descricao   TEXT,
    credito     NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (credito >= 0),
    debito      NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (debito  >= 0),
    "data&hora" TIMESTAMPTZ    NOT NULL DEFAULT now(),
    saldo       NUMERIC(14,2)  NOT NULL DEFAULT 0,
    "correção"  BOOLEAN        NOT NULL DEFAULT FALSE
);

COMMENT ON COLUMN movimentos.credito IS 'Valor em euros (EUR)';
COMMENT ON COLUMN movimentos.debito  IS 'Valor em euros (EUR)';
COMMENT ON COLUMN movimentos."data&hora" IS 'Momento de criação da linha (preenchido automaticamente)';
COMMENT ON COLUMN movimentos.saldo IS
    'Saldo acumulado DO CLIENTE (credito - debito) até esta linha, inclusive. Não existe saldo global.';

-- Índice para encontrar depressa o último movimento de cada cliente.
-- O nome do cliente NÃO distingue maiúsculas de minúsculas
-- ("Ana", "ana" e "ANA" são o mesmo cliente), daí o lower().
CREATE INDEX idx_movimentos_cliente
    ON movimentos (lower(cliente), "data&hora" DESC, id DESC);

-- Função e trigger: calculam automaticamente o saldo de CADA CLIENTE
-- em cada inserção: último saldo desse cliente + crédito - débito.
CREATE OR REPLACE FUNCTION calcular_saldo() RETURNS TRIGGER AS $$
DECLARE
    saldo_anterior NUMERIC(14,2);
BEGIN
    -- Bloqueia (até ao fim da transação) inserções concorrentes
    -- para o mesmo cliente, para não lerem ambas o mesmo saldo.
    PERFORM pg_advisory_xact_lock(hashtext(lower(NEW.cliente)));

    SELECT saldo INTO saldo_anterior
    FROM movimentos
    WHERE lower(cliente) = lower(NEW.cliente)
    ORDER BY "data&hora" DESC, id DESC
    LIMIT 1;

    NEW.saldo := COALESCE(saldo_anterior, 0) + NEW.credito - NEW.debito;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calcular_saldo
    BEFORE INSERT ON movimentos
    FOR EACH ROW
    EXECUTE FUNCTION calcular_saldo();

-- Privilégios: só o "postgres" (dono da tabela) pode alterar ou apagar
-- linhas. Todos os restantes utilizadores só podem consultar e
-- acrescentar (append) novos registos — nunca UPDATE nem DELETE.
REVOKE ALL ON movimentos FROM PUBLIC;
GRANT SELECT, INSERT ON movimentos TO PUBLIC;

-- Relatórios periódicos (CSV por e-mail), enviados pelo serviço
-- "relatorios" (relatorios.py, que também cria esta tabela se faltar).
-- Só o "postgres" lhe acede: um relatório envia dados para fora.
CREATE TABLE relatorios (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome              TEXT        NOT NULL,
    frequencia        TEXT        NOT NULL
                      CHECK (frequencia IN ('diario', 'semanal', 'mensal')),
    destinatario      TEXT        NOT NULL,
    cliente           TEXT,
    apenas_correcoes  BOOLEAN     NOT NULL DEFAULT FALSE,
    credito_min       NUMERIC(14,2),
    credito_max       NUMERIC(14,2),
    debito_min        NUMERIC(14,2),
    debito_max        NUMERIC(14,2),
    saldo_min         NUMERIC(14,2),
    saldo_max         NUMERIC(14,2),
    ativo             BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_por        TEXT        NOT NULL DEFAULT current_user,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_periodo    DATE,
    ultimo_envio      TIMESTAMPTZ,
    ultimo_erro       TEXT
);
COMMENT ON COLUMN relatorios.destinatario IS
    'Um ou mais endereços de e-mail, separados por vírgula';
COMMENT ON COLUMN relatorios.ultimo_periodo IS
    'Data de início do último período enviado (evita envios repetidos)';
REVOKE ALL ON relatorios FROM PUBLIC;
