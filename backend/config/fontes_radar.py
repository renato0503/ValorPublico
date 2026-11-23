"""Fontes oficiais do radar de propaganda publica (Mato Grosso).

Lista curada e verificada (HTTP 200 + conteudo extraivel) das fontes
institucionais usadas pelo radar:

  CUIABA          Prefeitura de Cuiaba + Camara Municipal de Cuiaba
  VARZEAGRANDE    Prefeitura de Varzea Grande (feed oficial, transparencia, DOE)
  ALMT / ESTADO   Assembleia Legislativa (al.mt.gov.br: portal, midia/texto e
                  agenda), DOE-MT/IOnews, Secom-MT, CGE-MT e Transparencia MT

Todas as fontes sao publicas e nao exigem autenticacao. Os itens coletados
sao marcados com `classe = propaganda_publica` e servem tanto para o radar
(transparencia/prova) quanto para o compliance eleitoral (uso de simbolos
publicos - art. 40 da Lei 9.504/1997).

Observacao sobre a ALMT: o dominio institucional oficial e
``https://www.al.mt.gov.br`` (verificado HTTP 200 em 23/11/2026). Os
dominios antigos almt.leg.br / assembleia.mt.gov.br / almt.mt.gov.br seguem
sem resolver, mas o portal atual publica deputados, noticias (midia/texto) e
a agenda da Assembleia. O radar tambem mantem o DOE-MT (IOnews) e a Secom-MT.
"""

FONTES_CUIABA = [
    "https://www.cuiaba.mt.gov.br/noticias",
    "https://www.cuiaba.mt.gov.br/",
    "https://www.camaracuiaba.mt.gov.br/",
]

FONTES_VARZEAGRANDE = [
    "https://www.varzeagrande.mt.gov.br/feed",
    "https://www.varzeagrande.mt.gov.br/transparencia",
    "https://www.varzeagrande.mt.gov.br/diario-oficial",
]

FONTES_ALMT_ESTADO = [
    "https://www.al.mt.gov.br/",
    "https://www.al.mt.gov.br/midia/texto",
    "https://www.al.mt.gov.br/parlamento/agenda/assembleia",
    "https://www.iomat.mt.gov.br/clipping",
    "https://www.iomat.mt.gov.br/",
    "https://www.secom.mt.gov.br/inicio",
    "https://www.secom.mt.gov.br/noticias",
    "https://www.cge.mt.gov.br/noticias",
    "https://www.transparencia.mt.gov.br/",
]

# Lista completa (padrao do radar)
FONTES_RADAR_PADRAO = FONTES_CUIABA + FONTES_VARZEAGRANDE + FONTES_ALMT_ESTADO

# Alias por entidade (permite filtrar o radar por orgao/escopo)
FONTES_POR_ENTIDADE = {
    "cuiaba": FONTES_CUIABA,
    "varzea-grande": FONTES_VARZEAGRANDE,
    "almt": FONTES_ALMT_ESTADO,
    "estado-mt": FONTES_ALMT_ESTADO,
}
