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

    return mo, os, psycopg


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
def _(DB_NAME, params, psycopg):
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
def _(bd_pronta, mo):
    # 4) Comando para criar um novo registo
    _ = bd_pronta
    form = (
        mo.md(
            """
            ## Nova entrada

            {cliente}

            {descricao}

            {credito}

            {debito}

            {correcao}
            """
        )
        .batch(
            cliente=mo.ui.text(value="", label="Cliente"),
            descricao=mo.ui.text(value="", label="Descrição"),
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
def _(DB_NAME, bd_pronta, form, mo, params, psycopg):
    assert bd_pronta
    inserido = form.value is not None
    if inserido:
        with psycopg.connect(**params, dbname=DB_NAME) as conn_ins:
            conn_ins.execute(
                'INSERT INTO movimentos (cliente, descricao, credito, debito, "correção") '
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    form.value["cliente"].strip(),
                    form.value["descricao"],
                    form.value["credito"],
                    form.value["debito"],
                    form.value["correcao"],
                ),
            )
        mensagem = mo.md(f"Entrada inserida para **{form.value['cliente']}**.")
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
            `credito`, `debito` e `correção` — com ou sem o sufixo `(€)`.
            Separador `,` ou `;`; decimais com `.` ou `,`. As colunas `id`,
            `data & hora` e `saldo` são ignoradas. Se alguma linha tiver
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
def _(DB_NAME, bd_pronta, importar_csv_form, mo, params, psycopg):
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
            except _InvalidOperation:
                erros.append(f"Linha {n_linha}: valor numérico inválido")
                continue
            except ValueError as erro:
                erros.append(f"Linha {n_linha}: {erro}")
                continue
            registos.append(
                (cliente, campo("descricao").strip(), credito, debito, correcao)
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
                            '(cliente, descricao, credito, debito, "correção", "data&hora") '
                            "VALUES (%s, %s, %s, %s, %s, clock_timestamp())",
                            _registos,
                        )
                inseridos_csv = len(_registos)
                _total_credito = sum(r[2] for r in _registos)
                _total_debito = sum(r[3] for r in _registos)
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

            _Nos limites pode usar `?`: no campo **mín.** significa o valor
            mínimo da coluna e no campo **máx.** o valor máximo (entre os
            registos do cliente/correções escolhidos)._
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
        )
        .form(submit_button_label="Selecionar")
    )
    filtro_form
    return (filtro_form,)


@app.cell
def _(
    DB_NAME, bd_pronta, filtro_form, inserido, inseridos_csv, mo, params, psycopg
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
    ):
        _sql_ext = (
            "SELECT MIN(credito), MAX(credito), MIN(debito), MAX(debito), "
            "MIN(saldo), MAX(saldo) FROM movimentos"
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

    _sql = (
        'SELECT id, cliente, descricao, credito, debito, "data&hora", saldo, "correção" '
        "FROM movimentos"
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
                "data & hora": dh,
                "saldo (€)": float(sa),
                "correção": corr,
            }
            for rid, c, d, cr, db, dh, sa, corr in _linhas
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


if __name__ == "__main__":
    app.run()
