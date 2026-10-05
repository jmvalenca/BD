# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "marimo>=0.24.2",
#     "psycopg==3.3.6",
# ]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Contabilidade · Arminda Melo RL")


@app.cell
def _():
    import os

    import marimo as mo
    import psycopg

    # Relatórios periódicos por e-mail (ficheiro relatorios.py, ao lado deste)
    import relatorios as rel_lib

    return mo, os, psycopg, rel_lib


@app.cell
def _(mo):
    # Cabeçalho da aplicação (escritório + nome da app + data de hoje)
    import datetime as _dt

    _MESES = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
        "agosto", "setembro", "outubro", "novembro", "dezembro",
    )
    _hoje = _dt.date.today()
    _data_hoje = f"{_hoje.day} de {_MESES[_hoje.month - 1]} de {_hoje.year}"

    mo.Html(
        f"""
        <div style="
            display:flex; align-items:center; gap:1.25rem; flex-wrap:wrap;
            padding:1.4rem 1.6rem; margin-bottom:0.5rem;
            border-radius:14px;
            background:linear-gradient(135deg, #0f2b3d 0%, #16475b 60%, #1f6f6b 100%);
            color:#f4f1ea;
            box-shadow:0 6px 18px rgba(15,43,61,0.25);
            font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;">
          <div style="
              flex:0 0 auto; width:64px; height:64px; border-radius:50%;
              display:flex; align-items:center; justify-content:center;
              border:2px solid #d4af6a; color:#d4af6a;
              font-family: Georgia, 'Times New Roman', serif;
              font-size:1.55rem; letter-spacing:0.04em;">AM</div>
          <div style="flex:1 1 220px; min-width:0;">
            <div style="
                font-size:0.78rem; letter-spacing:0.22em; text-transform:uppercase;
                color:#d4af6a; font-weight:600;">Arminda Melo RL</div>
            <div style="
                font-family: Georgia, 'Times New Roman', serif;
                font-size:2.1rem; line-height:1.15; margin:0.15rem 0 0.3rem;">
              Contabilidade</div>
            <div style="font-size:0.92rem; opacity:0.85;">
              Registo de movimentos e saldos por cliente</div>
          </div>
          <div style="
              flex:0 0 auto; font-size:0.85rem; opacity:0.85; text-align:right;">
            {_data_hoje}</div>
        </div>
        """
    )
    return


@app.cell
def _(os):
    # Parâmetros de servidor (podem ser definidos por variáveis de ambiente);
    # o utilizador e a password vêm do formulário de autenticação abaixo.
    DB_NAME = "contabilidade"
    DB_HOST = os.getenv("PGHOST", "localhost")
    DB_PORT = int(os.getenv("PGPORT", "5432"))
    return DB_HOST, DB_NAME, DB_PORT


@app.cell
def _(mo):
    # 1) Autenticação
    login_form = (
        mo.md(
            """
            ## Autenticação

            {utilizador}

            {password}
            """
        )
        .batch(
            utilizador=mo.ui.text(value="", label="Utilizador"),
            password=mo.ui.text(value="", label="Password", kind="password"),
        )
        .form(submit_button_label="Entrar")
    )
    login_form
    return (login_form,)


@app.cell
def _(DB_HOST, DB_PORT, login_form, mo, psycopg):
    mo.stop(
        login_form.value is None,
        mo.md("Introduza as suas credenciais e carregue em **Entrar**."),
    )

    _utilizador = login_form.value["utilizador"].strip()
    _password = login_form.value["password"]

    try:
        with psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=_utilizador,
            password=_password,
            dbname="postgres",
            connect_timeout=5,
        ):
            pass
    except psycopg.OperationalError as _erro:
        mo.stop(True, mo.md(f"**Autenticação falhada:** {_erro}"))

    params = dict(host=DB_HOST, port=DB_PORT, user=_utilizador, password=_password)
    utilizador = _utilizador
    autenticado = True
    mo.md(f"Sessão iniciada como **{utilizador}**. ✅")
    return autenticado, params, utilizador


@app.cell
def _(autenticado, mo):
    # 2) Comando para fechar a aplicação
    _ = autenticado
    fechar_botao = mo.ui.run_button(label="⏻ Fechar aplicação")
    fechar_botao
    return (fechar_botao,)


@app.cell
def _(fechar_botao, mo, os):
    if fechar_botao.value:
        mo.md("A fechar a aplicação. Pode fechar esta janela do browser.")
        os._exit(0)
    return


@app.cell
def _(DB_NAME, params, psycopg, rel_lib):
    # 3) Preparar a base de dados (idempotente; requer privilégios de administrador
    # na primeira execução, tipicamente ligado como "postgres")
    avisos_setup = []

    try:
        with psycopg.connect(**params, dbname="postgres", autocommit=True) as conn_admin:
            _existe = conn_admin.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)
            ).fetchone()
            if not _existe:
                conn_admin.execute(f'CREATE DATABASE "{DB_NAME}"')
    except psycopg.errors.InsufficientPrivilege:
        avisos_setup.append("Sem privilégios para criar a base de dados.")

    try:
        with psycopg.connect(**params, dbname=DB_NAME) as conn_ddl:
            conn_ddl.execute(
                """
                CREATE TABLE IF NOT EXISTS movimentos (
                    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    cliente     TEXT           NOT NULL,
                    descricao   TEXT,
                    credito     NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (credito >= 0),
                    debito      NUMERIC(14,2)  NOT NULL DEFAULT 0 CHECK (debito  >= 0),
                    "data&hora" TIMESTAMPTZ    NOT NULL DEFAULT now(),
                    saldo       NUMERIC(14,2)  NOT NULL DEFAULT 0,
                    "correção"  BOOLEAN        NOT NULL DEFAULT FALSE
                )
                """
            )
            # Garante a coluna "id" e "correção" também em bases de dados criadas
            # antes destas alterações
            conn_ddl.execute(
                """
                ALTER TABLE movimentos
                    ADD COLUMN IF NOT EXISTS id BIGINT GENERATED BY DEFAULT AS IDENTITY
                """
            )
            conn_ddl.execute(
                """
                ALTER TABLE movimentos
                    ADD COLUMN IF NOT EXISTS "correção" BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            # Coluna "entrada" (data da transação, nunca posterior à data do
            # registo); em bases de dados antigas é preenchida com a data do
            # registo. O SQL está no relatorios.py, partilhado com o serviço.
            rel_lib.garantir_coluna_entrada(conn_ddl)
            # Índice para encontrar depressa o último movimento de cada cliente.
            # O nome do cliente NÃO distingue maiúsculas de minúsculas
            # ("Ana", "ana" e "ANA" são o mesmo cliente), daí o lower().
            conn_ddl.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_movimentos_cliente
                    ON movimentos (lower(cliente), "data&hora" DESC, id DESC)
                """
            )
            # Função e trigger: calculam automaticamente o saldo de CADA CLIENTE
            # em cada inserção: último saldo desse cliente + crédito - débito.
            conn_ddl.execute(
                """
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
                $$ LANGUAGE plpgsql
                """
            )
            conn_ddl.execute("DROP TRIGGER IF EXISTS trg_calcular_saldo ON movimentos")
            conn_ddl.execute(
                """
                CREATE TRIGGER trg_calcular_saldo
                    BEFORE INSERT ON movimentos
                    FOR EACH ROW
                    EXECUTE FUNCTION calcular_saldo()
                """
            )
            # Recalcula os saldos já gravados (corrige os registos feitos com a
            # versão antiga do trigger, que acumulava o saldo de todos os
            # clientes juntos). Idempotente: só altera linhas com saldo errado.
            conn_ddl.execute(
                """
                UPDATE movimentos AS m
                SET saldo = c.saldo_correto
                FROM (
                    SELECT id,
                           SUM(credito - debito) OVER (
                               PARTITION BY lower(cliente)
                               ORDER BY "data&hora", id
                           ) AS saldo_correto
                    FROM movimentos
                ) AS c
                WHERE m.id = c.id
                  AND m.saldo IS DISTINCT FROM c.saldo_correto
                """
            )
            # Privilégios: só o "postgres" (dono da tabela) pode alterar ou apagar
            # linhas. Todos os restantes utilizadores só podem consultar e
            # acrescentar (append) novos registos — nunca UPDATE nem DELETE.
            conn_ddl.execute("REVOKE ALL ON movimentos FROM PUBLIC")
            conn_ddl.execute("GRANT SELECT, INSERT ON movimentos TO PUBLIC")
            # Tabela de configuração dos relatórios periódicos (só "postgres")
            rel_lib.criar_tabela(conn_ddl)
    except psycopg.errors.InsufficientPrivilege:
        avisos_setup.append(
            "Sem privilégios para criar/alterar a tabela ou os seus privilégios de acesso."
        )

    bd_pronta = True
    return avisos_setup, bd_pronta


@app.cell
def _(avisos_setup, mo):
    aviso_md = (
        mo.md("\n\n".join(f"⚠️ {aviso}" for aviso in avisos_setup))
        if avisos_setup
        else mo.md("")
    )
    aviso_md
    return (aviso_md,)


@app.cell
def _(bd_pronta, mo, rel_lib):
    # 4) Comando para criar um novo registo
    _ = bd_pronta
    _hoje = rel_lib.hoje_lisboa()
    form = (
        mo.md(
            """
            ## Nova entrada

            {cliente}

            {descricao}

            {entrada}

            {credito}

            {debito}

            {correcao}
            """
        )
        .batch(
            cliente=mo.ui.text(value="", label="Cliente"),
            descricao=mo.ui.text(value="", label="Descrição"),
            # data da transação: nunca posterior a hoje (a data do registo)
            entrada=mo.ui.date(
                value=_hoje, stop=_hoje, label="Data da transação (entrada)"
            ),
            credito=mo.ui.number(
                start=0, stop=10**12, step=0.01, value=0, label="Crédito (€)"
            ),
            debito=mo.ui.number(
                start=0, stop=10**12, step=0.01, value=0, label="Débito (€)"
            ),
            correcao=mo.ui.checkbox(
                value=False,
                label="Este registo corrige valores de registos anteriores",
            ),
        )
        .form(submit_button_label="Inserir")
    )
    form
    return (form,)


@app.cell
def _(DB_NAME, bd_pronta, form, mo, params, psycopg, rel_lib):
    assert bd_pronta
    inserido = form.value is not None
    if inserido:
        # Um campo numérico deixado vazio chega como None: conta como 0
        # (as colunas credito/debito são NOT NULL).
        _cliente_ins = form.value["cliente"].strip()
        _credito_ins = form.value["credito"] or 0
        _debito_ins = form.value["debito"] or 0
        _entrada_ins = form.value["entrada"]
        if not _cliente_ins:
            mensagem = mo.md("⚠️ **Indique o cliente.** Nada foi inserido.")
        elif _entrada_ins is None:
            mensagem = mo.md(
                "⚠️ **Indique a data da transação (entrada).** Nada foi inserido."
            )
        elif _entrada_ins > rel_lib.hoje_lisboa():
            mensagem = mo.md(
                f"⚠️ **A data da transação ({_entrada_ins:%d/%m/%Y}) não pode ser "
                "posterior à data do registo (hoje).** Nada foi inserido."
            )
        elif _credito_ins == 0 and _debito_ins == 0:
            mensagem = mo.md(
                "⚠️ **Indique um valor de crédito ou de débito.** Nada foi inserido."
            )
        else:
            try:
                with psycopg.connect(**params, dbname=DB_NAME) as conn_ins:
                    conn_ins.execute(
                        "INSERT INTO movimentos "
                        '(cliente, descricao, entrada, credito, debito, "correção") '
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            _cliente_ins,
                            form.value["descricao"],
                            _entrada_ins,
                            _credito_ins,
                            _debito_ins,
                            form.value["correcao"],
                        ),
                    )
                mensagem = mo.md(f"✅ Entrada inserida para **{_cliente_ins}**.")
            except psycopg.Error as _erro:
                mensagem = mo.md(f"**Erro ao inserir — nada foi inserido:** {_erro}")
    else:
        mensagem = mo.md("_Preencha o formulário e carregue em **Inserir**._")
    mensagem
    return (inserido,)


@app.cell
def _(bd_pronta, mo):
    # 4b) Criar múltiplos registos a partir de um ficheiro CSV. Aceita o mesmo
    # formato do CSV exportado (secção 6b) ou apenas as colunas essenciais.
    # As colunas "id", "data & hora" e "saldo", se existirem, são ignoradas:
    # são sempre geradas pela base de dados (o saldo pelo trigger).
    _ = bd_pronta
    importar_csv_form = (
        mo.md(
            """
            ## Novas entradas a partir de CSV

            Colunas reconhecidas: `cliente` (obrigatória), `descricao`,
            `entrada`, `credito`, `debito` e `correção` — com ou sem o sufixo
            `(€)`. Separador `,` ou `;`; decimais com `.` ou `,`. A `entrada`
            (data da transação) aceita `AAAA-MM-DD` ou `DD/MM/AAAA`, não pode
            ser posterior a hoje e, se faltar, fica a data de hoje. As colunas
            `id`, `data & hora` e `saldo` são ignoradas. Se alguma linha tiver
            erros, **nenhum** registo é inserido.

            {ficheiro}
            """
        )
        .batch(
            ficheiro=mo.ui.file(
                filetypes=[".csv"], kind="area", label="Ficheiro CSV"
            ),
        )
        .form(submit_button_label="Importar")
    )
    importar_csv_form
    return (importar_csv_form,)


@app.cell
def _(DB_NAME, bd_pronta, importar_csv_form, mo, params, psycopg, rel_lib):
    assert bd_pronta
    import csv as _csv
    import io as _io
    import unicodedata as _unicodedata
    from decimal import Decimal as _Decimal, InvalidOperation as _InvalidOperation

    def _normalizar_cabecalho(nome):
        # "Crédito (€)" -> "credito", "correção" -> "correcao", etc.
        nome = (nome or "").replace("(€)", "").strip().lower()
        nome = _unicodedata.normalize("NFKD", nome)
        return "".join(ch for ch in nome if not _unicodedata.combining(ch))

    def _valor(texto):
        texto = (texto or "").strip().replace(" ", "").replace("€", "")
        if not texto:
            return _Decimal("0.00")
        if "," in texto and "." in texto:
            # O último separador é o decimal: "1.234,56" ou "1,234.56"
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")
        numero = _Decimal(texto)
        if numero < 0:
            raise ValueError("valor negativo")
        return numero.quantize(_Decimal("0.01"))

    _VERDADEIRO = {"true", "1", "sim", "s", "yes", "y", "verdadeiro", "v", "x"}
    _FALSO = {"false", "0", "nao", "n", "no", "falso", "f", ""}

    def _booleano(texto):
        texto = _normalizar_cabecalho(texto)
        if texto in _VERDADEIRO:
            return True
        if texto in _FALSO:
            return False
        raise ValueError(f"valor de correção inválido: {texto!r}")

    def _ler_csv(conteudo):
        try:
            texto = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = conteudo.decode("cp1252")
        try:
            dialeto = _csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except _csv.Error:
            dialeto = _csv.excel
        leitor = _csv.DictReader(_io.StringIO(texto), dialect=dialeto)
        colunas = {_normalizar_cabecalho(c): c for c in (leitor.fieldnames or [])}
        if "cliente" not in colunas:
            return [], ["O ficheiro não tem a coluna obrigatória **cliente**."]

        registos, erros = [], []
        hoje = rel_lib.hoje_lisboa()
        for n_linha, linha in enumerate(leitor, start=2):
            def campo(nome):
                original = colunas.get(nome)
                return (linha.get(original) or "") if original else ""

            if not any((v or "").strip() for v in linha.values() if isinstance(v, str)):
                continue  # linha vazia
            cliente = campo("cliente").strip()
            try:
                if not cliente:
                    raise ValueError("cliente vazio")
                credito = _valor(campo("credito"))
                debito = _valor(campo("debito"))
                correcao = _booleano(campo("correcao"))
                entrada = rel_lib.ler_data(campo("entrada"))
                if entrada is not None and entrada > hoje:
                    raise ValueError(
                        f"a data de entrada {entrada:%d/%m/%Y} é posterior a hoje"
                    )
            except _InvalidOperation:
                erros.append(f"Linha {n_linha}: valor numérico inválido")
                continue
            except ValueError as erro:
                erros.append(f"Linha {n_linha}: {erro}")
                continue
            registos.append(
                (cliente, campo("descricao").strip(), entrada, credito, debito, correcao)
            )
        return registos, erros

    inseridos_csv = 0
    _ficheiros = (importar_csv_form.value or {}).get("ficheiro") or []
    if not _ficheiros:
        mensagem_importacao = mo.md(
            "_Escolha um ficheiro CSV e carregue em **Importar**._"
        )
    else:
        _registos, _erros = _ler_csv(_ficheiros[0].contents)
        if _erros:
            mensagem_importacao = mo.md(
                "**Importação cancelada — nenhum registo foi inserido.**\n\n"
                + "\n".join(f"- {e}" for e in _erros[:20])
                + (f"\n- … e mais {len(_erros) - 20} erro(s)" if len(_erros) > 20 else "")
            )
        elif not _registos:
            mensagem_importacao = mo.md("⚠️ O ficheiro não contém registos.")
        else:
            try:
                # Uma única transação: ou entram todos, ou nenhum. O
                # clock_timestamp() dá a cada linha uma data & hora distinta,
                # para o trigger calcular o saldo pela ordem do ficheiro.
                with psycopg.connect(**params, dbname=DB_NAME) as conn_csv:
                    with conn_csv.cursor() as cur_csv:
                        cur_csv.executemany(
                            "INSERT INTO movimentos "
                            '(cliente, descricao, entrada, credito, debito, "correção", '
                            '"data&hora") VALUES (%s, %s, '
                            "COALESCE(%s::date, (now() AT TIME ZONE 'Europe/Lisbon')::date), "
                            "%s, %s, %s, clock_timestamp())",
                            _registos,
                        )
                inseridos_csv = len(_registos)
                _total_credito = sum(r[3] for r in _registos)
                _total_debito = sum(r[4] for r in _registos)
                mensagem_importacao = mo.md(
                    f"✅ **{inseridos_csv}** registo(s) inserido(s) a partir de "
                    f"**{_ficheiros[0].name}** — crédito total {_total_credito:.2f} €, "
                    f"débito total {_total_debito:.2f} €."
                )
            except psycopg.Error as _erro:
                mensagem_importacao = mo.md(
                    f"**Erro ao inserir — nenhum registo foi inserido:** {_erro}"
                )
    mensagem_importacao
    return (inseridos_csv,)


@app.cell
def _(mo):
    # 5) Comando para selecionar registos, incluindo limites numéricos
    # (mínimo/máximo) opcionais para crédito, débito e saldo. Usam campos de
    # texto — não campos numéricos — para ficarem mesmo "não preenchidos" por
    # omissão, em vez de mostrarem um valor por defeito, e para aceitarem o
    # carácter especial "?" (valor mínimo/máximo da coluna).
    filtro_form = (
        mo.md(
            """
            ## Selecionar registos

            {cliente}

            {apenas_correcoes}

            **Crédito (€) entre:** {credito_min} e {credito_max}

            **Débito (€) entre:** {debito_min} e {debito_max}

            **Saldo (€) entre:** {saldo_min} e {saldo_max}

            **Entrada (data da transação) entre:** {entrada_min} e {entrada_max}

            _Datas em `AAAA-MM-DD` ou `DD/MM/AAAA`. Nos limites pode usar `?`:
            no campo **mín.** significa o valor mínimo da coluna e no campo
            **máx.** o valor máximo (entre os registos do cliente/correções
            escolhidos)._
            """
        )
        .batch(
            cliente=mo.ui.text(value="", label="Cliente (deixe vazio para todos)"),
            apenas_correcoes=mo.ui.checkbox(
                value=False, label="Mostrar apenas correções"
            ),
            credito_min=mo.ui.text(value="", label="mín."),
            credito_max=mo.ui.text(value="", label="máx."),
            debito_min=mo.ui.text(value="", label="mín."),
            debito_max=mo.ui.text(value="", label="máx."),
            saldo_min=mo.ui.text(value="", label="mín."),
            saldo_max=mo.ui.text(value="", label="máx."),
            entrada_min=mo.ui.text(value="", label="desde", placeholder="DD/MM/AAAA"),
            entrada_max=mo.ui.text(value="", label="até", placeholder="DD/MM/AAAA"),
        )
        .form(submit_button_label="Selecionar")
    )
    filtro_form
    return (filtro_form,)


@app.cell
def _(
    DB_NAME,
    bd_pronta,
    filtro_form,
    inserido,
    inseridos_csv,
    mo,
    params,
    psycopg,
    rel_lib,
):
    # 6) Apresentar a seleção (as linhas podem ser marcadas na tabela para,
    # se o utilizador for "postgres", serem purgadas — ver secção seguinte)
    _ = (bd_pronta, inserido, inseridos_csv)
    mo.stop(
        filtro_form.value is None,
        mo.md("_Preencha os filtros e carregue em **Selecionar**._"),
    )

    def _numero_ou_none(texto, extremo):
        # "?" -> valor extremo da coluna (mínimo no campo mín., máximo no máx.)
        texto = (texto or "").strip().replace(",", ".")
        if texto == "?":
            return extremo
        return float(texto) if texto else None

    _valores = filtro_form.value
    _cliente = _valores["cliente"].strip()
    _so_correcoes = _valores["apenas_correcoes"]

    _condicoes = []
    _parametros = []

    if _cliente:
        # Correspondência exata do nome (sem distinguir maiúsculas), igual à
        # usada pelo trigger: o saldo mostrado é sempre de um único cliente.
        _condicoes.append("lower(cliente) = lower(%s)")
        _parametros.append(_cliente)
    if _so_correcoes:
        _condicoes.append('"correção" = TRUE')

    _limites = (
        ("credito", "credito_min", "credito_max"),
        ("debito", "debito_min", "debito_max"),
        ("saldo", "saldo_min", "saldo_max"),
    )

    # Valores mínimo e máximo de cada coluna, para substituir o "?". São
    # calculados sobre os registos que respeitam os filtros de cliente e de
    # correções (ainda não há limites numéricos em _condicoes neste ponto).
    _extremos = {}
    if any(
        (_valores[_k] or "").strip() == "?"
        for _, _kmin, _kmax in _limites
        for _k in (_kmin, _kmax)
    ) or "?" in ((_valores["entrada_min"] or "").strip(), (_valores["entrada_max"] or "").strip()):
        _sql_ext = (
            "SELECT MIN(credito), MAX(credito), MIN(debito), MAX(debito), "
            "MIN(saldo), MAX(saldo), MIN(entrada), MAX(entrada) FROM movimentos"
        )
        if _condicoes:
            _sql_ext += " WHERE " + " AND ".join(_condicoes)
        with psycopg.connect(**params, dbname=DB_NAME) as conn_ext:
            _ext = conn_ext.execute(_sql_ext, _parametros).fetchone()
        for _i, (_coluna, _, _) in enumerate(_limites):
            _mn, _mx = _ext[2 * _i], _ext[2 * _i + 1]
            _extremos[_coluna] = (
                None if _mn is None else float(_mn),
                None if _mx is None else float(_mx),
            )
        _extremos["entrada"] = (_ext[6], _ext[7])

    _substituicoes = []  # descrição dos "?" resolvidos, para mostrar ao utilizador
    try:
        for _coluna, _chave_min, _chave_max in _limites:
            _ext_min, _ext_max = _extremos.get(_coluna, (None, None))
            _minimo = _numero_ou_none(_valores[_chave_min], _ext_min)
            _maximo = _numero_ou_none(_valores[_chave_max], _ext_max)
            for _chave, _valor, _nome in (
                (_chave_min, _minimo, "mín."),
                (_chave_max, _maximo, "máx."),
            ):
                if (_valores[_chave] or "").strip() == "?":
                    _substituicoes.append(
                        f"{_coluna} {_nome} = "
                        + ("—" if _valor is None else f"{_valor:.2f} €")
                    )
            if _minimo is not None:
                _condicoes.append(f"{_coluna} >= %s")
                _parametros.append(_minimo)
            if _maximo is not None:
                _condicoes.append(f"{_coluna} <= %s")
                _parametros.append(_maximo)
    except ValueError:
        mo.stop(
            True,
            mo.md(
                "**Limite numérico inválido.** Introduza apenas números "
                "(ex.: `100` ou `100.50`) ou `?` nos campos de crédito, débito e saldo."
            ),
        )

    # Gama de datas de entrada (data da transação)
    _ent_ext_min, _ent_ext_max = _extremos.get("entrada", (None, None))
    try:
        for _chave, _operador, _extremo, _nome in (
            ("entrada_min", ">=", _ent_ext_min, "desde"),
            ("entrada_max", "<=", _ent_ext_max, "até"),
        ):
            _texto = (_valores[_chave] or "").strip()
            if _texto == "?":
                _data = _extremo
                _substituicoes.append(
                    f"entrada {_nome} = "
                    + ("—" if _data is None else f"{_data:%d/%m/%Y}")
                )
            else:
                _data = rel_lib.ler_data(_texto)
            if _data is not None:
                _condicoes.append(f"entrada {_operador} %s")
                _parametros.append(_data)
    except ValueError as _erro:
        mo.stop(True, mo.md(f"**Data de entrada inválida:** {_erro}."))

    _sql = (
        "SELECT id, cliente, descricao, credito, debito, entrada, "
        '"data&hora", saldo, "correção" FROM movimentos'
    )
    if _condicoes:
        _sql += " WHERE " + " AND ".join(_condicoes)
    _sql += ' ORDER BY "data&hora"'

    with psycopg.connect(**params, dbname=DB_NAME) as conn_sel:
        _linhas = conn_sel.execute(_sql, _parametros).fetchall()

    resultado_tabela = mo.ui.table(
        [
            {
                "id": rid,
                "cliente": c,
                "descricao": d,
                "credito (€)": float(cr),
                "debito (€)": float(db),
                "entrada": ent,
                "data & hora": dh,
                "saldo (€)": float(sa),
                "correção": corr,
            }
            for rid, c, d, cr, db, ent, dh, sa, corr in _linhas
        ],
        label=f"Movimentos ({len(_linhas)} registo(s)) — selecione linhas para purgar",
        selection="multi",
    )
    mo.vstack(
        [
            mo.md("**`?` substituído por:** " + "; ".join(_substituicoes))
            if _substituicoes
            else mo.md(""),
            resultado_tabela,
        ]
    )
    return (resultado_tabela,)


@app.cell
def _(mo):
    # 6b) Exportar o resultado da seleção acima para um ficheiro CSV, na
    # diretoria atual ou noutra diretoria indicada pelo utilizador.
    exportar_csv_form = (
        mo.md(
            """
            ## Exportar resultado para CSV

            {diretoria}

            {nome_ficheiro}
            """
        )
        .batch(
            diretoria=mo.ui.text(
                value="",
                label="Diretoria de destino (vazio = diretoria atual)",
            ),
            nome_ficheiro=mo.ui.text(
                value="movimentos.csv",
                label="Nome do ficheiro",
            ),
        )
        .form(submit_button_label="Guardar CSV")
    )
    exportar_csv_form
    return (exportar_csv_form,)


@app.cell
def _(exportar_csv_form, mo, os, resultado_tabela):
    mo.stop(
        exportar_csv_form.value is None,
        mo.md(
            "_Indique a diretoria (opcional) e o nome do ficheiro e carregue "
            "em **Guardar CSV**._"
        ),
    )

    _diretoria = exportar_csv_form.value["diretoria"].strip() or os.getcwd()
    _nome_ficheiro = exportar_csv_form.value["nome_ficheiro"].strip() or "movimentos.csv"

    try:
        os.makedirs(_diretoria, exist_ok=True)
    except OSError as _erro:
        mo.stop(
            True, mo.md(f"**Não foi possível criar/aceder à diretoria:** {_erro}")
        )

    _caminho_csv = os.path.join(_diretoria, _nome_ficheiro)
    _linhas_csv = resultado_tabela.data

    try:
        import csv

        _colunas = [
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
        with open(_caminho_csv, "w", newline="", encoding="utf-8") as _ficheiro_csv:
            _escritor = csv.DictWriter(_ficheiro_csv, fieldnames=_colunas)
            _escritor.writeheader()
            _escritor.writerows(_linhas_csv)
        mensagem_csv = mo.md(
            f"✅ Resultado guardado em **{_caminho_csv}** "
            f"({len(_linhas_csv)} registo(s))."
        )
    except OSError as _erro:
        mensagem_csv = mo.md(f"**Erro ao guardar o ficheiro:** {_erro}")

    mensagem_csv
    return


@app.cell
def _(mo, resultado_tabela, utilizador):
    # 7) Purgar registos selecionados — só disponível para o utilizador "postgres".
    # O painel de confirmação aparece diretamente assim que houver linhas
    # marcadas na tabela acima (sem um botão intermédio de "pedido de purga",
    # que se mostrou pouco fiável).
    _selecionados = resultado_tabela.value or []

    if utilizador != "postgres":
        painel_purga = mo.md("_Só o utilizador **postgres** pode purgar registos._")
        confirmar_purga_botao = None
        cancelar_purga_botao = None
    elif not _selecionados:
        painel_purga = mo.md(
            "_Selecione uma ou mais linhas na tabela acima para poder purgá-las._"
        )
        confirmar_purga_botao = None
        cancelar_purga_botao = None
    else:
        confirmar_purga_botao = mo.ui.run_button(label="✅ Confirmar purga definitiva")
        cancelar_purga_botao = mo.ui.run_button(label="Cancelar")
        painel_purga = mo.vstack(
            [
                mo.md(
                    f"⚠️ **{len(_selecionados)}** registo(s) selecionado(s) para "
                    "purgar. Esta ação é irreversível."
                ),
                mo.hstack([confirmar_purga_botao, cancelar_purga_botao]),
            ]
        )

    painel_purga
    return cancelar_purga_botao, confirmar_purga_botao


@app.cell
def _(
    DB_NAME,
    cancelar_purga_botao,
    confirmar_purga_botao,
    mo,
    params,
    psycopg,
    resultado_tabela,
    utilizador,
):
    # 8) Executa (ou cancela) a purga depois da confirmação explícita acima
    if confirmar_purga_botao is not None and confirmar_purga_botao.value:
        _ids = [linha["id"] for linha in resultado_tabela.value]
        with psycopg.connect(**params, dbname=DB_NAME) as conn_del:
            conn_del.execute("DELETE FROM movimentos WHERE id = ANY(%s)", (_ids,))
        mensagem_purga = mo.md(f"{len(_ids)} registo(s) purgado(s) por **{utilizador}**.")
    elif cancelar_purga_botao is not None and cancelar_purga_botao.value:
        mensagem_purga = mo.md(
            "Purga cancelada — nada foi apagado. Desmarque as linhas na tabela "
            "acima, se quiser limpar a seleção."
        )
    else:
        mensagem_purga = mo.md("")
    mensagem_purga
    return


@app.cell
def _(mo):
    # 9) Relatórios periódicos: estado partilhado que obriga a lista de
    # relatórios (secção 9b) a ser relida depois de criar/alterar/apagar.
    # A mensagem do resultado da última ação também fica em estado, para não
    # desaparecer quando a lista (e os botões) são recriados.
    get_versao_relatorios, set_versao_relatorios = mo.state(0)
    get_msg_relatorios, set_msg_relatorios = mo.state("")
    return (
        get_msg_relatorios,
        get_versao_relatorios,
        set_msg_relatorios,
        set_versao_relatorios,
    )


@app.cell
def _(bd_pronta, mo, utilizador):
    # 9a) Formulário para criar um relatório periódico (CSV por e-mail).
    # Só o "postgres" gere relatórios: enviam dados para fora da aplicação.
    _ = bd_pronta
    mo.stop(
        utilizador != "postgres",
        mo.md(
            "## Relatórios periódicos por e-mail\n\n"
            "_Só o utilizador **postgres** pode gerir relatórios periódicos._"
        ),
    )
    relatorio_form = (
        mo.md(
            """
            ## Relatórios periódicos por e-mail

            Envia automaticamente um CSV com os movimentos do **último período
            completo** (dia anterior, semana anterior de segunda a domingo, ou
            mês anterior), a partir das 07:00 (hora de Lisboa). Sem filtros, o
            relatório inclui **todos os movimentos** do período.

            {nome}

            {frequencia}

            {destinatario}

            **Seleção (opcional):**

            {cliente}

            {apenas_correcoes}

            **Crédito (€) entre:** {credito_min} e {credito_max}

            **Débito (€) entre:** {debito_min} e {debito_max}

            **Saldo (€) entre:** {saldo_min} e {saldo_max}

            **Entrada (data da transação) entre:** {entrada_min} e {entrada_max}
            _(datas fixas em `AAAA-MM-DD` ou `DD/MM/AAAA`; o período do relatório
            continua a ser o da data do registo)_
            """
        )
        .batch(
            nome=mo.ui.text(value="", label="Nome do relatório"),
            frequencia=mo.ui.dropdown(
                options={"Diário": "diario", "Semanal": "semanal", "Mensal": "mensal"},
                value="Mensal",
                label="Frequência",
            ),
            destinatario=mo.ui.text(
                value="",
                label="Enviar para (e-mail; vários separados por vírgula)",
                full_width=True,
            ),
            cliente=mo.ui.text(value="", label="Cliente (vazio = todos)"),
            apenas_correcoes=mo.ui.checkbox(value=False, label="Apenas correções"),
            credito_min=mo.ui.text(value="", label="mín."),
            credito_max=mo.ui.text(value="", label="máx."),
            debito_min=mo.ui.text(value="", label="mín."),
            debito_max=mo.ui.text(value="", label="máx."),
            saldo_min=mo.ui.text(value="", label="mín."),
            saldo_max=mo.ui.text(value="", label="máx."),
            entrada_min=mo.ui.text(value="", label="desde", placeholder="DD/MM/AAAA"),
            entrada_max=mo.ui.text(value="", label="até", placeholder="DD/MM/AAAA"),
        )
        .form(submit_button_label="Criar relatório", clear_on_submit=True)
    )
    relatorio_form
    return (relatorio_form,)


@app.cell
def _(
    DB_NAME,
    get_versao_relatorios,
    mo,
    params,
    psycopg,
    rel_lib,
    relatorio_form,
    set_versao_relatorios,
):
    # 9a') Gravar o relatório criado no formulário
    mo.stop(relatorio_form.value is None)
    from decimal import Decimal as _Dec, InvalidOperation as _InvOp

    _v = relatorio_form.value

    def _limite(texto):
        texto = (texto or "").strip().replace(" ", "").replace("€", "")
        if not texto:
            return None
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return _Dec(texto.replace(",", "."))

    try:
        _nome_rel = _v["nome"].strip()
        if not _nome_rel:
            raise ValueError("indique o nome do relatório")
        _destinos = rel_lib.validar_destinatarios(_v["destinatario"])
        try:
            _limites_rel = {
                f"{_c}_{_s}": _limite(_v[f"{_c}_{_s}"])
                for _c in rel_lib.LIMITES
                for _s in ("min", "max")
            }
        except _InvOp:
            raise ValueError("limite numérico inválido (use p. ex. 100 ou 100,50)")
        _entrada_min_rel = rel_lib.ler_data(_v["entrada_min"])
        _entrada_max_rel = rel_lib.ler_data(_v["entrada_max"])
        if (
            _entrada_min_rel is not None
            and _entrada_max_rel is not None
            and _entrada_min_rel > _entrada_max_rel
        ):
            raise ValueError("a data de entrada «desde» é posterior à data «até»")
        with psycopg.connect(**params, dbname=DB_NAME) as _conn_rel:
            _conn_rel.execute(
                "INSERT INTO relatorios (nome, frequencia, destinatario, cliente, "
                "apenas_correcoes, credito_min, credito_max, debito_min, debito_max, "
                "saldo_min, saldo_max, entrada_min, entrada_max) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    _nome_rel,
                    _v["frequencia"],
                    ", ".join(_destinos),
                    _v["cliente"].strip() or None,
                    _v["apenas_correcoes"],
                    *(_limites_rel[f"{_c}_{_s}"] for _c in rel_lib.LIMITES for _s in ("min", "max")),
                    _entrada_min_rel,
                    _entrada_max_rel,
                ),
            )
        set_versao_relatorios(get_versao_relatorios() + 1)
        mensagem_relatorio = mo.md(
            f"✅ Relatório **{_nome_rel}** criado. O primeiro envio (último "
            "período completo) é feito pelo serviço de relatórios dentro de "
            "1 minuto (ou a partir das 07:00)."
        )
    except ValueError as _erro:
        mensagem_relatorio = mo.md(f"⚠️ **Relatório não criado:** {_erro}.")
    except psycopg.Error as _erro:
        mensagem_relatorio = mo.md(f"**Erro ao gravar o relatório:** {_erro}")
    mensagem_relatorio
    return


@app.cell
def _(
    DB_NAME,
    get_msg_relatorios,
    get_versao_relatorios,
    mo,
    params,
    psycopg,
    rel_lib,
    utilizador,
):
    # 9b) Lista dos relatórios configurados (selecione para ativar, enviar ou apagar)
    _ = get_versao_relatorios()
    mo.stop(utilizador != "postgres")
    from psycopg.rows import dict_row as _dict_row

    with psycopg.connect(**params, dbname=DB_NAME, row_factory=_dict_row) as _conn_l:
        _rels = _conn_l.execute("SELECT * FROM relatorios ORDER BY id").fetchall()

    def _quando(valor):
        return valor.astimezone(rel_lib.FUSO).strftime("%Y-%m-%d %H:%M") if valor else "—"

    relatorios_tabela = mo.ui.table(
        [
            {
                "id": _r["id"],
                "nome": _r["nome"],
                "frequência": rel_lib.FREQUENCIAS[_r["frequencia"]],
                "enviar para": _r["destinatario"],
                "seleção": rel_lib.descrever_filtros(_r),
                "ativo": "sim" if _r["ativo"] else "não",
                "último período": (
                    rel_lib.descrever_periodo(
                        _r["frequencia"],
                        _r["ultimo_periodo"],
                        rel_lib.fim_do_periodo(_r["frequencia"], _r["ultimo_periodo"]),
                    )
                    if _r["ultimo_periodo"]
                    else "—"
                ),
                "último envio": _quando(_r["ultimo_envio"]),
                "último erro": _r["ultimo_erro"] or "",
            }
            for _r in _rels
        ],
        label=f"Relatórios configurados ({len(_rels)})",
        selection="multi",
    )
    mo.vstack(
        [
            mo.md(get_msg_relatorios()),
            relatorios_tabela
            if _rels
            else mo.md("_Ainda não há relatórios configurados._"),
        ]
    )
    return (relatorios_tabela,)


@app.cell
def _(mo, relatorios_tabela):
    # 9c) Ações sobre os relatórios selecionados na tabela acima
    _sel = relatorios_tabela.value or []
    mo.stop(
        not _sel,
        mo.md("_Selecione relatórios na tabela para os enviar já, ativar/desativar ou apagar._"),
    )
    enviar_rel_botao = mo.ui.run_button(label="✉️ Enviar agora (último período)")
    alternar_rel_botao = mo.ui.run_button(label="⏯ Ativar / desativar")
    apagar_rel_botao = mo.ui.run_button(label="🗑 Apagar", kind="danger")
    mo.vstack(
        [
            mo.md(f"**{len(_sel)}** relatório(s) selecionado(s):"),
            mo.hstack(
                [enviar_rel_botao, alternar_rel_botao, apagar_rel_botao], justify="start"
            ),
        ]
    )
    return alternar_rel_botao, apagar_rel_botao, enviar_rel_botao


@app.cell
def _(
    DB_NAME,
    alternar_rel_botao,
    apagar_rel_botao,
    enviar_rel_botao,
    get_versao_relatorios,
    mo,
    params,
    psycopg,
    rel_lib,
    relatorios_tabela,
    set_msg_relatorios,
    set_versao_relatorios,
):
    # 9d) Executa a ação escolhida. "Enviar agora" envia o último período
    # completo e regista-o, para o serviço não o voltar a enviar.
    from psycopg.rows import dict_row as _dict_row2

    _ids_rel = [_l["id"] for _l in (relatorios_tabela.value or [])]
    _linhas_msg = []
    if enviar_rel_botao.value:
        with psycopg.connect(**params, dbname=DB_NAME, row_factory=_dict_row2) as _c:
            for _r in _c.execute(
                "SELECT * FROM relatorios WHERE id = ANY(%s) ORDER BY id", (_ids_rel,)
            ).fetchall():
                try:
                    _n, _per = rel_lib.enviar_relatorio(_c, _r)
                    _linhas_msg.append(
                        f"✅ **{_r['nome']}** ({_per}): {_n} movimento(s) enviados "
                        f"para {_r['destinatario']}."
                    )
                except Exception as _erro:  # noqa: BLE001
                    _c.rollback()
                    _linhas_msg.append(f"❌ **{_r['nome']}**: {_erro}")
    elif alternar_rel_botao.value:
        with psycopg.connect(**params, dbname=DB_NAME) as _c:
            _c.execute(
                "UPDATE relatorios SET ativo = NOT ativo WHERE id = ANY(%s)", (_ids_rel,)
            )
        _linhas_msg.append(f"{len(_ids_rel)} relatório(s) ativado(s)/desativado(s).")
    elif apagar_rel_botao.value:
        with psycopg.connect(**params, dbname=DB_NAME) as _c:
            _c.execute("DELETE FROM relatorios WHERE id = ANY(%s)", (_ids_rel,))
        _linhas_msg.append(f"{len(_ids_rel)} relatório(s) apagado(s).")

    if _linhas_msg:
        set_msg_relatorios("\n\n".join(_linhas_msg))
        set_versao_relatorios(get_versao_relatorios() + 1)
    return


if __name__ == "__main__":
    app.run()
