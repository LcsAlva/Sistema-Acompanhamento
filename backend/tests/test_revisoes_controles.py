from backend.models import ControleDocumento, LdDocumento, SigemDocumento
from backend.services import revisoes_service as svc


def test_tipo_controle_documento_classifica_civil():
    assert svc.tipo_controle_documento(
        codigo_documento="DE-001",
        titulo="Estrutura de concreto - formas e armaduras",
        disciplina="CIVIL",
    ) == "Construcao civil - Armadura"
    assert svc.tipo_controle_documento(
        codigo_documento="DE-002",
        titulo="Fundacao - locacao e planta baixa",
        disciplina="CIVIL",
    ) == "Construcao civil - m3 de concreto"
    assert svc.tipo_controle_documento(
        codigo_documento="DE-003",
        titulo="Estrutura metalica - cortes e detalhes",
        disciplina="CIVIL",
    ) == "Construcao civil - Estrutura metalica"


def test_tipo_controle_documento_preserva_tubulacao():
    assert svc.tipo_controle_documento(
        codigo_documento="IS-5275.00-2221-200-E6G-001",
        titulo="Isometrico de tubulacao",
        disciplina="Tubulacao",
    ) == "Tubulacao - Tubos e conexoes"
    assert svc.tipo_controle_documento(
        codigo_documento="LI-5275.00-2221-293-E6G-001",
        titulo="Lista de suportes",
        disciplina="Tubulacao",
    ) == "Tubulacao - Suportes"


def test_classificar_controles_pendentes_cria_apenas_novos(db):
    db.add_all([
        LdDocumento(
            codigo_documento="DE-CIVIL-001",
            titulo="Fundacao - formas e armaduras",
            disciplina="CIVIL",
            revisao="0",
            status="SEM WORKFLOW",
            a4_equivalente=8,
        ),
        SigemDocumento(
            codigo_documento="DE-CIVIL-001",
            revisao="0",
            status="SEM WORKFLOW",
            nivel_1="DOCUMENTACAO TECNICA",
            nivel_4="CIVIL",
        ),
        SigemDocumento(
            codigo_documento="DE-ELAB-001",
            revisao="0",
            status="EM ELABORACAO",
            nivel_1="DOCUMENTACAO TECNICA",
            nivel_4="CIVIL",
        ),
    ])
    db.commit()

    resultado = svc.classificar_controles_pendentes(db, fonte="sigem")
    assert resultado["candidatos"] == 1
    assert resultado["criados"] == 1
    assert db.query(ControleDocumento).count() == 1

    controle = db.query(ControleDocumento).one()
    assert controle.documento_origem == "DE-CIVIL-001"
    assert controle.controle_aplicavel == "Construcao civil - Armadura"
    assert controle.setor == "Engenharia"

    resultado_2 = svc.classificar_controles_pendentes(db, fonte="sigem")
    assert resultado_2["criados"] == 0
    assert resultado_2["ignorados_ja_classificados"] == 1
    assert db.query(ControleDocumento).count() == 1


def test_listar_quantitativos_controles_resume_por_disciplina(db):
    db.add(LdDocumento(
        codigo_documento="DE-CIVIL-002",
        titulo="Fundacao - locacao",
        disciplina="CIVIL",
        revisao="A",
        status="SEM WORKFLOW",
        a4_equivalente=8,
    ))
    db.add(ControleDocumento(
        codigo_controle="CTRL-DE-CIVIL-002-001",
        documento_origem="DE-CIVIL-002",
        revisao_documento="A",
        controle_aplicavel="Construcao civil - m3 de concreto",
        setor="Engenharia",
        area="CIVIL",
        status_controle="Aberto",
    ))
    db.add(SigemDocumento(
        codigo_documento="DE-CIVIL-002",
        revisao="A",
        status="SEM WORKFLOW",
        nivel_1="DOCUMENTAÇÃO TÉCNICA",
        nivel_4="CIVIL",
    ))
    db.commit()

    data = svc.listar_quantitativos_controles(db)

    assert data["resumo_disciplinas"][0]["disciplina"] == "CIVIL"
    assert data["resumo_disciplinas"][0]["controles"] == 1
    assert data["resumo_disciplinas"][0]["documentos"] == 1
    assert data["resumo_disciplinas"][0]["a4_total"] == 8
    assert data["planilha"][0]["unidade_principal"] == "m3"
    assert data["planilha"][0]["a4_equivalente"] == 8
    assert data["planilha"][0]["quantidade_extraida"] is None


def test_listar_controle_completo_usa_dados_existentes_sem_inventar(db):
    db.add(LdDocumento(
        codigo_documento="IS-5275.00-2221-200-E6G-001",
        titulo="Isometrico de tubulacao",
        disciplina="TUBULACAO",
        revisao="B",
        status="SEM WORKFLOW",
    ))
    db.add(SigemDocumento(
        codigo_documento="IS-5275.00-2221-200-E6G-001",
        revisao="B",
        status="POSTADO",
        nivel_1="DOCUMENTACAO TECNICA",
        nivel_4="TUBULACAO",
    ))
    db.add(ControleDocumento(
        codigo_controle="CTRL-IS-001",
        documento_origem="IS-5275.00-2221-200-E6G-001",
        revisao_documento="B",
        controle_aplicavel="Tubulacao - Tubos e conexoes",
        setor="Engenharia",
        area="Area 200",
        status_controle="Aberto",
    ))
    db.commit()

    data = svc.listar_controle_completo(db)

    assert data["resumo"]["controles"] == 1
    linha = data["linhas"][0]
    assert linha["codigo_documento"] == "IS-5275.00-2221-200-E6G-001"
    assert linha["area"] == "Area 200"
    assert linha["isometrico"] == "IS-5275.00-2221-200-E6G-001"
    assert linha["quantidade_prevista"] is None
    assert linha["material_disponivel"] == "Nao informado"
