-- Executar ligado à base de dados "contabilidade":
--   psql -U postgres -d contabilidade -f alterar_tabela.sql

-- 1) Nova coluna com o momento de criação de cada linha
ALTER TABLE movimentos
    ADD COLUMN "data&hora" TIMESTAMPTZ NOT NULL DEFAULT now();

-- 2) Nova coluna com o saldo acumulado (crédito - débito desta linha e de todas as anteriores)
ALTER TABLE movimentos
    ADD COLUMN saldo NUMERIC(14,2);

-- 3) Preencher o saldo das linhas já existentes, pela ordem de "data&hora"
--    (ctid como desempate para linhas com o mesmo instante)
WITH ordenado AS (
    SELECT ctid,
           SUM(credito - debito) OVER (
               ORDER BY "data&hora", ctid
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS saldo_calc
    FROM movimentos
)
UPDATE movimentos m
SET saldo = o.saldo_calc
FROM ordenado o
WHERE m.ctid = o.ctid;

ALTER TABLE movimentos
    ALTER COLUMN saldo SET NOT NULL;

-- 4) Função e trigger que calculam automaticamente o saldo de cada nova linha,
--    a partir do saldo da linha anterior mais recente
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

DROP TRIGGER IF EXISTS trg_calcular_saldo ON movimentos;
CREATE TRIGGER trg_calcular_saldo
    BEFORE INSERT ON movimentos
    FOR EACH ROW
    EXECUTE FUNCTION calcular_saldo();

COMMENT ON COLUMN movimentos."data&hora" IS 'Momento de criação da linha (preenchido automaticamente)';
COMMENT ON COLUMN movimentos.saldo IS 'Saldo acumulado (credito - debito) até esta linha, inclusive';
