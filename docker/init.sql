-- Criação da base de dados "contabilidade" para a aplicação Movimentos.
-- Executado automaticamente pelo PostgreSQL na 1.ª inicialização do container
-- (via /docker-entrypoint-initdb.d/), quando o volume pgdata está vazio.

CREATE DATABASE contabilidade ENCODING 'UTF8';

-- Ligar à nova base de dados
\c contabilidade

CREATE TABLE movimentos (
    cliente     TEXT           NOT NULL,
    descricao   TEXT,
    credito     NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (credito >= 0),
    debito      NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (debito  >= 0),
    "data&hora" TIMESTAMPTZ    NOT NULL DEFAULT now(),
    saldo       NUMERIC(14,2)  NOT NULL DEFAULT 0
);

COMMENT ON COLUMN movimentos.credito IS 'Valor em euros (EUR)';
COMMENT ON COLUMN movimentos.debito  IS 'Valor em euros (EUR)';
COMMENT ON COLUMN movimentos."data&hora" IS 'Momento de criação da linha (preenchido automaticamente)';
COMMENT ON COLUMN movimentos.saldo IS 'Saldo acumulado (credito - debito) até esta linha, inclusive';

-- Função e trigger que calculam automaticamente o saldo de cada nova linha
CREATE OR REPLACE FUNCTION calcular_saldo() RETURNS TRIGGER AS $$
DECLARE
    saldo_anterior NUMERIC(14,2);
BEGIN
    SELECT saldo INTO saldo_anterior
    FROM movimentos
    ORDER BY "data&hora" DESC, ctid DESC
    LIMIT 1;

    NEW.saldo := COALESCE(saldo_anterior, 0) + NEW.credito - NEW.debito;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calcular_saldo
    BEFORE INSERT ON movimentos
    FOR EACH ROW
    EXECUTE FUNCTION calcular_saldo();
