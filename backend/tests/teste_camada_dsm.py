"""Testes locais da Camada DSM (sem Firestore).`n`nUso: python backend/tests/teste_camada_dsm.py`n"""
import sys, json
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from processing.mencao import classificar_mencao, resumir_mencoes
from processing.trecho import extrair_trecho, destacar
from processing.compliance_eleitoral import analisar, resumo as resumo_compliance
from processing.propaganda_publica import detectar, resumo as resumo_radar
from processing.alertas import detectar_alertas, resumir as resumo_alertas
from processing.cobertura import analisar_cobertura, tier_do_veiculo
from processing.enriquecimento import enriquecer_clipping, campos_para_salvar

AGENTE = {"nome_urna": "Fulano de Tal", "termos_de_busca": ["fulano de tal", "vereador fulano"]}

ok = 0
falhas = []

def checa(nome, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  PASS  {nome}")
    else:
        falhas.append(nome)
        print(f"  FAIL  {nome} {extra}")

print("== mencao ==")
t1 = "Fulano de Tal afirmou que o projeto é prioridade. 'Vamos aprobar', disse o vereador."
r1 = classificar_mencao(t1, AGENTE["termos_de_busca"], AGENTE)
checa("deteccao direta", r1["tipo"] == "direta", r1)
checa("papel nao e apenas citada", r1["papel"] in ("protagonista", "porta-voz"), r1)
checa("motivos registrados", len(r1["motivos"]) > 0)

t2 = "A proposito do orcamento municipal, o)(\". Fulano de Tal,"
r2 = classificar_mencao("Segundo o levantamento, oFULANO aparecia em materias do municipio.", AGENTE["termos_de_busca"], AGENTE)
checa("generico vira indeterminada", r2["tipo"] in ("indeterminada", "indireta"), r2)

t3 = "Reunião na Câmara reúneOpcode"
r3 = classificar_mencao("A Câmara de Cuiabá aprovou o projeto de lei do vereador Fulano de Tal.", AGENTE["termos_de_busca"], AGENTE)
checa("citado no titulo -> direta", r3["tipo"] == "direta", r3)

print("== trecho ==")
t4 = "Texto inicial. Fulano de Tal disse que o hospital precisa de reforma. Outra frase qualquer. Mais uma sobre Fulano de Tal."
tr = extrair_trecho(t4, AGENTE["termos_de_busca"])
checa("trecho encontrado", "Fulano" in tr["trecho"], tr)
checa("offsets validos", tr["fim"] >= tr["inicio"] >= 0, tr)
chk = destacar(tr["trecho"], AGENTE["termos_de_busca"])
checa("destaque com <mark>", "<mark>" in chk, chk[:120])

print("== compliance ==")
clip_el = {
    "texto_limpo": "Comício do candidato reúne miles de pessoas com carro de som no centro.",
    "plataforma": "Web",
    "data_publicacao": datetime(2026, 10, 1, 10, 0),
}
ach = analisar(clip_el)
checa("comicio gera apontamento", len(ach) > 0, ach)
print("   ", resumo_compliance(ach))

clip_simbolo = {
    "texto_limpo": "Campanha usa o brasão da prefeitura na peça de propaganda.",
    "plataforma": "Web",
    "data_publicacao": datetime.now(timezone.utc),
}
ach2 = analisar(clip_simbolo)
checa("art.40 (simbolo publico) detectado", any(a["artigo"] == "Art. 40" for a in ach2), ach2)

clip_dia = {
    "texto_limpo": "Candidato distribui adesivos e bandeiras na véspera da eleição.",
    "plataforma": "Twitter",
    "data_publicacao": datetime(2026, 10, 4, 8, 0),
}
ach3 = analisar(clip_dia)
checa("art.39-A no dia da eleicao", any(a["artigo"] == "Art. 39-A" for a in ach3), ach3)

print("== radar propaganda publica ==")
clip_pp = {
    "texto_limpo": "Prefeitura lanza campanha institucional de utilidade pública sobre coleta de lixo.",
    "plataforma": "Web",
    "metadados": {"veiculo": "portal oficial"},
}
rd = detectar(clip_pp)
checa("propaganda institucional detectada", rd["classe"] == "propaganda_publica", rd)
checa("orgao identificado", rd["orgao"] == "prefeitura", rd)

clip_jor = {"texto_limpo": "Vereador.protocolou projeto de lei sobre sanitation na cidade.", "plataforma": "Web"}
rd2 = detectar(clip_jor)
checa("materia journalistica", rd2["classe"] == "materia_journalistica", rd2)

print("== alertas ==")
clip_al = {
    "agente_id": "a1",
    "texto_limpo": "Vereador Fulano de Tal é，电话 Magic.",
    "plataforma": "Web",
    "url": "https://exemplo.com/noticia",
    "sentimento": "negativo",
    "valor_estimado": 3000.0,
    "mencao": {"tipo": "direta", "papel": "protagonista"},
    "trecho": {"trecho": "Vereador Fulano de Tal é总价 Magic"},
    "categorias": ["Seguranca"],
    "metadados": {"veiculo": "gazeta mt"},
    "data_publicacao": datetime.now(timezone.utc),
}
al = detectar_alertas(clip_al, {"valor_alto": 1500, "tier1_veiculos": ["gazeta mt"]})
tipos = {a["tipo"] for a in al}
checa("alerta negativa direta", "NEGATIVA_DIRETA" in tipos, tipos)
checa("alerta valor alto", "VALOR_ALTO" in tipos, tipos)
checa("alerta tier1 negativo", "TIER1_NEGATIVA" in tipos, tipos)
print("   ", resumo_alertas(al))

print("== cobertura / SLA ==")
agora = datetime.now(timezone.utc)
clips = [
    {"data_publicacao": agora - timedelta(hours=2), "created_at": agora,
     "metadados": {"veiculo": "G1"}, "plataforma": "Web", "texto_limpo": "x"},
    {"data_publicacao": agora - timedelta(hours=5), "created_at": agora,
     "metadados": {"veiculo": "Portal local"}, "plataforma": "Web", "texto_limpo": "y"},
    {"data_publicacao": agora - timedelta(hours=1), "created_at": agora,
     "metadados": {"veiculo": "gazeta mt"}, "plataforma": "TV", "texto_limpo": "z"},
]
cov = analisar_cobertura(clips, veiculos_esperados=["g1", "gazeta mt", "Folha"])
checa("sla medio calculado", cov["sla_min_medio"] > 0, cov)
checa("fonte ausente detectada", "folha" in cov["veiculos_ausentes"], cov)
checa("tier do g1 = Tier 1", tier_do_veiculo("G1") == "Tier 1")
print("   ", {k: cov[k] for k in ("total", "pct_cobertura", "sla_min_medio", "sla_min_p95", "por_tier")})

print("== enriquecimento (integracao) ==")
enq = enriquecer_clipping(clip_al, AGENTE)
campos = campos_para_salvar(enq)
checa("campos de inteligencia presentes", all(k in campos for k in ("mencao", "trecho", "compliance", "propaganda_publica")))
checa("tipo_mencao gravado", enq.get("tipo_mencao") == "direta", enq.get("tipo_mencao"))

print("== resumo de mencoes ==")
rm = resumir_mencoes([{"tipo_mencao": "direta"}, {"tipo_mencao": "direta"}, {"tipo_mencao": "indireta"}])
checa("pct direta", rm["pct_direta"] == 66.7, rm)

print()
print(f"RESULTADO: {ok} passaram, {len(falhas)} falharam")
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)


