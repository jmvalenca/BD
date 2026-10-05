"""Relatórios periódicos (diários, semanais ou mensais) enviados por e-mail.

Este ficheiro tem dois papéis:

1. Módulo usado pela aplicação marimo (movimentos.py) para criar a tabela
   "relatorios", gerar o CSV e enviar um relatório a pedido ("Enviar agora").
2. Serviço (container "relatorios" no docker-compose): corre em ciclo e, todos
   os dias a partir da HORA_ENVIO (hora de Lisboa), envia cada relatório ativo
   cujo último período completo ainda não foi enviado:

     - diário  -> o dia de ontem
     - semanal -> a semana anterior (segunda a domingo), enviada à segunda-feira
     - mensal  -> o mês anterior, enviado no dia 1

   Se o Mac estava desligado/a dormir, o relatório em falta é enviado logo que o
   serviço volte a arrancar (só o período completo mais recente). Em caso de
   erro tenta de novo 15 minutos depois; o erro fica registado na tabela.

O e-mail é enviado pelo SMTP do Gmail (smtp.gmail.com:465, SSL), com as
credenciais das variáveis de ambiente GMAIL_USER e GMAIL_APP_PASSWORD (uma
"palavra-passe de app" do Google — não a password normal da conta).

Uso como serviço:  python relatorios.py
"""

import csv
import datetime as dt
import io
import os
import re
import smtplib
import ssl
import sys
import time
from decimal import Decimal
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row, tuple_row

FUSO = ZoneInfo("Europe/Lisbon")
FREQUENCIAS = {"diario": "diário", "semanal": "semanal", "mensal": "mensal"}
LIMITES = ("credito", "debito", "saldo")
COLUNAS_CSV = [
    "id",
    "cliente",
    "descricao",
    "credito (€)",
    "debito (€)",
    "entrada",
    "data & hora",
    "saldo (€)",
    "correção",
]
_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")

# Tabela de configuração dos relatórios. Só o "postgres" (dono) lhe acede:
# um relatório envia dados para fora, por isso não é dado acesso a PUBLIC.
SQL_TABELA = """
CREATE TABLE IF NOT EXISTS relatorios (
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
    entrada_min       DATE,
    entrada_max       DATE,
    ativo             BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_por        TEXT        NOT NULL DEFAULT current_user,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_periodo    DATE,
    ultimo_envio      TIMESTAMPTZ,
    ultimo_erro       TEXT
);
COMMENT ON TABLE relatorios IS
    'Relatórios periódicos (CSV por e-mail) — enviados pelo serviço relatorios.py';
COMMENT ON COLUMN relatorios.destinatario IS
    'Um ou mais endereços de e-mail, separados por vírgula';
COMMENT ON COLUMN relatorios.ultimo_periodo IS
    'Data de início do último período enviado (evita envios repetidos)';
-- tabelas criadas antes do filtro por data de entrada
ALTER TABLE relatorios ADD COLUMN IF NOT EXISTS entrada_min DATE;
ALTER TABLE relatorios ADD COLUMN IF NOT EXISTS entrada_max DATE;
REVOKE ALL ON relatorios FROM PUBLIC;
"""

# Coluna "entrada" da tabela movimentos: data da transação a que o movimento
# se refere. Nunca pode ser posterior à data do registo ("data&hora", em hora
# de Lisboa). Idempotente: acrescenta a coluna a bases de dados antigas e
# preenche-a, nos movimentos já existentes, com a data do registo.
SQL_ENTRADA = """
ALTER TABLE movimentos ADD COLUMN IF NOT EXISTS entrada DATE;
UPDATE movimentos
   SET entrada = ("data&hora" AT TIME ZONE 'Europe/Lisbon')::date
 WHERE entrada IS NULL;
ALTER TABLE movimentos
    ALTER COLUMN entrada SET DEFAULT (now() AT TIME ZONE 'Europe/Lisbon')::date,
    ALTER COLUMN entrada SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'movimentos_entrada_anterior_ao_registo') THEN
        ALTER TABLE movimentos ADD CONSTRAINT movimentos_entrada_anterior_ao_registo
            CHECK (entrada <= ("data&hora" AT TIME ZONE 'Europe/Lisbon')::date);
    END IF;
END $$;
COMMENT ON COLUMN movimentos.entrada IS
    'Data da transação a que o movimento se refere (não posterior à data do registo)';
CREATE INDEX IF NOT EXISTS idx_movimentos_entrada ON movimentos (entrada);
"""


def criar_tabela(conn):
    """Cria a tabela "relatorios", se não existir (idempotente)."""
    conn.execute(SQL_TABELA)


def garantir_coluna_entrada(conn):
    """Acrescenta a coluna "entrada" aos movimentos, se faltar (idempotente)."""
    conn.execute(SQL_ENTRADA)


# ---------------------------------------------------------------- períodos


def hoje_lisboa():
    return dt.datetime.now(FUSO).date()


def periodo_anterior(frequencia, hoje):
    """Último período COMPLETO antes de `hoje`: (início, fim), fim exclusivo."""
    if frequencia == "diario":
        return hoje - dt.timedelta(days=1), hoje
    if frequencia == "semanal":
        segunda = hoje - dt.timedelta(days=hoje.weekday())
        return segunda - dt.timedelta(days=7), segunda
    if frequencia == "mensal":
        primeiro = hoje.replace(day=1)
        return (primeiro - dt.timedelta(days=1)).replace(day=1), primeiro
    raise ValueError(f"frequência desconhecida: {frequencia!r}")


def fim_do_periodo(frequencia, inicio):
    """Fim (exclusivo) do período que começa em `inicio`."""
    if frequencia == "diario":
        return inicio + dt.timedelta(days=1)
    if frequencia == "semanal":
        return inicio + dt.timedelta(days=7)
    return (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def descrever_periodo(frequencia, inicio, fim):
    if frequencia == "diario":
        return inicio.strftime("%d/%m/%Y")
    if frequencia == "mensal":
        return inicio.strftime("%m/%Y")
    return f"{inicio:%d/%m/%Y} a {fim - dt.timedelta(days=1):%d/%m/%Y}"


# ----------------------------------------------------------- validação


def ler_data(texto):
    """Converte "2026-10-05", "05/10/2026", "5-10-2026" ou "05.10.2026" numa
    data. Texto vazio devolve None; formato inválido lança ValueError."""
    texto = (texto or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    # "2026-10-05 14:30:00" (p. ex. de um CSV exportado): fica só a data
    try:
        return dt.datetime.fromisoformat(texto).date()
    except ValueError:
        raise ValueError(
            f"data inválida: {texto!r} (use AAAA-MM-DD ou DD/MM/AAAA)"
        ) from None


def validar_destinatarios(texto):
    """Devolve a lista de endereços (separados por , ou ;) ou lança ValueError."""
    enderecos = [e.strip() for e in re.split(r"[,;]", texto or "") if e.strip()]
    if not enderecos:
        raise ValueError("indique pelo menos um endereço de e-mail")
    invalidos = [e for e in enderecos if not _EMAIL_RE.match(e)]
    if invalidos:
        raise ValueError("endereço(s) inválido(s): " + ", ".join(invalidos))
    return enderecos


# ------------------------------------------------------------ seleção


def selecionar(conn, rel, inicio, fim):
    """Movimentos do período [inicio, fim[ (datas de Lisboa) que respeitam os
    filtros do relatório. Sem filtros: todos os movimentos do período."""
    condicoes = [
        "\"data&hora\" >= (%s::date)::timestamp AT TIME ZONE 'Europe/Lisbon'",
        "\"data&hora\" <  (%s::date)::timestamp AT TIME ZONE 'Europe/Lisbon'",
    ]
    parametros = [inicio, fim]
    if (rel.get("cliente") or "").strip():
        condicoes.append("lower(cliente) = lower(%s)")
        parametros.append(rel["cliente"].strip())
    if rel.get("apenas_correcoes"):
        condicoes.append('"correção" = TRUE')
    for coluna in LIMITES:
        for sufixo, operador in (("min", ">="), ("max", "<=")):
            valor = rel.get(f"{coluna}_{sufixo}")
            if valor is not None:
                condicoes.append(f"{coluna} {operador} %s")
                parametros.append(valor)
    if rel.get("entrada_min") is not None:
        condicoes.append("entrada >= %s")
        parametros.append(rel["entrada_min"])
    if rel.get("entrada_max") is not None:
        condicoes.append("entrada <= %s")
        parametros.append(rel["entrada_max"])
    sql = (
        "SELECT id, cliente, descricao, credito, debito, entrada, "
        '"data&hora", saldo, "correção" '
        "FROM movimentos WHERE " + " AND ".join(condicoes) + ' ORDER BY "data&hora", id'
    )
    with conn.cursor(row_factory=tuple_row) as cur:
        return cur.execute(sql, parametros).fetchall()


def gerar_csv(linhas):
    """CSV no mesmo formato da exportação da app (pode ser reimportado).
    Codificado em UTF-8 com BOM, para o Excel mostrar bem os acentos."""
    saida = io.StringIO()
    escritor = csv.writer(saida)
    escritor.writerow(COLUNAS_CSV)
    for rid, cliente, descricao, credito, debito, entrada, data_hora, saldo, correcao in linhas:
        escritor.writerow(
            [
                rid,
                cliente,
                descricao or "",
                f"{credito:.2f}",
                f"{debito:.2f}",
                entrada.isoformat(),
                data_hora.astimezone(FUSO).strftime("%Y-%m-%d %H:%M:%S"),
                f"{saldo:.2f}",
                correcao,
            ]
        )
    return saida.getvalue().encode("utf-8-sig")


def descrever_filtros(rel):
    partes = []
    if (rel.get("cliente") or "").strip():
        partes.append(f"cliente = {rel['cliente'].strip()}")
    if rel.get("apenas_correcoes"):
        partes.append("apenas correções")
    for coluna in LIMITES:
        mn, mx = rel.get(f"{coluna}_min"), rel.get(f"{coluna}_max")
        if mn is not None and mx is not None:
            partes.append(f"{coluna} entre {mn} e {mx} €")
        elif mn is not None:
            partes.append(f"{coluna} ≥ {mn} €")
        elif mx is not None:
            partes.append(f"{coluna} ≤ {mx} €")
    dmn, dmx = rel.get("entrada_min"), rel.get("entrada_max")
    if dmn is not None and dmx is not None:
        partes.append(f"entrada entre {dmn:%d/%m/%Y} e {dmx:%d/%m/%Y}")
    elif dmn is not None:
        partes.append(f"entrada desde {dmn:%d/%m/%Y}")
    elif dmx is not None:
        partes.append(f"entrada até {dmx:%d/%m/%Y}")
    return "; ".join(partes) if partes else "todos os movimentos"


# --------------------------------------------------------------- e-mail


def enviar_email(destinatarios, assunto, corpo, nome_ficheiro, conteudo):
    utilizador = os.getenv("GMAIL_USER", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not utilizador or not password:
        raise RuntimeError(
            "GMAIL_USER e GMAIL_APP_PASSWORD não estão definidos (ficheiro .env)."
        )
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    porta = int(os.getenv("SMTP_PORT", "465"))

    msg = EmailMessage()
    msg["From"] = utilizador
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = assunto
    msg.set_content(corpo)
    msg.add_attachment(
        conteudo, maintype="text", subtype="csv", filename=nome_ficheiro
    )

    if porta == 465:
        with smtplib.SMTP_SSL(host, porta, context=ssl.create_default_context(), timeout=30) as s:
            s.login(utilizador, password)
            s.send_message(msg)
    else:  # 587 (STARTTLS) ou servidor de testes local
        with smtplib.SMTP(host, porta, timeout=30) as s:
            if porta == 587:
                s.starttls(context=ssl.create_default_context())
            if os.getenv("SMTP_SEM_LOGIN") != "1":
                s.login(utilizador, password)
            s.send_message(msg)


def enviar_relatorio(conn, rel, hoje=None):
    """Gera e envia o relatório do último período completo e regista o envio.
    Devolve (n.º de movimentos, descrição do período)."""
    hoje = hoje or hoje_lisboa()
    inicio, fim = periodo_anterior(rel["frequencia"], hoje)
    linhas = selecionar(conn, rel, inicio, fim)
    periodo = descrever_periodo(rel["frequencia"], inicio, fim)
    total_credito = sum((l[3] for l in linhas), Decimal("0"))
    total_debito = sum((l[4] for l in linhas), Decimal("0"))
    freq = FREQUENCIAS[rel["frequencia"]]
    slug = re.sub(r"[^a-z0-9]+", "_", rel["nome"].lower()).strip("_") or "relatorio"

    corpo = (
        f"Relatório {freq} «{rel['nome']}» — Arminda Melo RL\n\n"
        f"Período: {periodo}\n"
        f"Seleção: {descrever_filtros(rel)}\n"
        f"Movimentos: {len(linhas)}\n"
        f"Crédito total: {total_credito:.2f} €\n"
        f"Débito total: {total_debito:.2f} €\n\n"
        "Os movimentos seguem em anexo (CSV).\n"
    )
    enviar_email(
        validar_destinatarios(rel["destinatario"]),
        f"Relatório {freq} «{rel['nome']}» — {periodo}",
        corpo,
        f"relatorio_{slug}_{inicio:%Y-%m-%d}.csv",
        gerar_csv(linhas),
    )
    conn.execute(
        "UPDATE relatorios SET ultimo_periodo = %s, ultimo_envio = now(), "
        "ultimo_erro = NULL WHERE id = %s",
        (inicio, rel["id"]),
    )
    conn.commit()
    return len(linhas), periodo


# --------------------------------------------------------------- serviço


def _log(texto, erro=False):
    agora = dt.datetime.now(FUSO).strftime("%F %T")
    print(f"[{agora}] {texto}", file=sys.stderr if erro else sys.stdout, flush=True)


def ciclo(conn, falhas, hoje=None):
    """Envia os relatórios em falta. `falhas` guarda {id: instante da última
    falha}, para só voltar a tentar ESPERA_ERRO segundos depois."""
    hoje = hoje or hoje_lisboa()
    espera = int(os.getenv("ESPERA_ERRO", "900"))
    relatorios = conn.execute(
        "SELECT * FROM relatorios WHERE ativo ORDER BY id"
    ).fetchall()
    conn.commit()
    for rel in relatorios:
        inicio, _ = periodo_anterior(rel["frequencia"], hoje)
        if rel["ultimo_periodo"] is not None and rel["ultimo_periodo"] >= inicio:
            continue  # já enviado
        if time.monotonic() - falhas.get(rel["id"], -espera) < espera:
            continue  # falhou há pouco tempo
        try:
            n, periodo = enviar_relatorio(conn, rel, hoje)
            falhas.pop(rel["id"], None)
            _log(f"Relatório #{rel['id']} «{rel['nome']}» ({periodo}): "
                 f"{n} movimento(s) enviados para {rel['destinatario']}.")
        except Exception as erro:  # noqa: BLE001 — registar e continuar
            conn.rollback()
            falhas[rel["id"]] = time.monotonic()
            conn.execute(
                "UPDATE relatorios SET ultimo_erro = %s WHERE id = %s",
                (f"{dt.datetime.now(FUSO):%F %T}: {erro}", rel["id"]),
            )
            conn.commit()
            _log(f"ERRO no relatório #{rel['id']} «{rel['nome']}»: {erro}; "
                 f"nova tentativa daqui a {espera // 60} min.", erro=True)


def main():
    hora_envio = int(os.getenv("HORA_ENVIO", "7"))
    _log(f"Serviço de relatórios iniciado (envios a partir das {hora_envio:02d}:00, "
         "hora de Lisboa).")
    if not os.getenv("GMAIL_USER") or not os.getenv("GMAIL_APP_PASSWORD"):
        _log("AVISO: GMAIL_USER/GMAIL_APP_PASSWORD não definidos — "
             "os envios vão falhar até serem definidos no .env.", erro=True)
    falhas = {}
    conn = None
    while True:
        try:
            if conn is None or conn.closed:
                # PGHOST, PGUSER, PGPASSWORD vêm do ambiente
                conn = psycopg.connect(dbname="contabilidade", row_factory=dict_row)
                garantir_coluna_entrada(conn)
                criar_tabela(conn)
                conn.commit()
            if dt.datetime.now(FUSO).hour >= hora_envio:
                ciclo(conn, falhas)
        except psycopg.Error as erro:
            _log(f"ERRO de base de dados: {erro}", erro=True)
            if conn is not None:
                conn.close()
            conn = None
        time.sleep(60)


if __name__ == "__main__":
    main()
