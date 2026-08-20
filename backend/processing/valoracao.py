import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)

# Plataformas cujo valor é calculado por alcance (CPM: R$/mil impressões)
_PLATAFORMAS_CPM = {
    "Twitter", "Instagram", "Facebook", "YouTube", "Telegram", "TikTok",
    "TV", "Radio",
}
# Plataformas cujo valor vem da tabela de veículos (mídia tradicional)
_PLATAFORMAS_TABELA = {"Web", "Impresso"}

COLLECTION_TABELA = "tabela_midia"
DOCUMENTO_GERAL = "geral"


class Valorador:
    """Calcula o valor financeiro espontâneo (R$) de cada clipping.

    Regras:
      - Redes sociais / YouTube / Telegram: valor = alcance × (CPM / 1000).
      - Web (notícia): valor = tabela do veículo (R$/matéria); fallback para
        `valor_padrao_portal` quando o veículo não está cadastrado.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.cpm: dict = {}
        self.veiculos: dict = {}
        self.valor_padrao_portal: float = 400.0
        self._carregar()

    def _carregar(self) -> None:
        try:
            ref = self.db.collection(COLLECTION_TABELA).document(DOCUMENTO_GERAL)
            dados = ref.get()
            if dados.exists:
                data = dados.to_dict()
                self.cpm = data.get("cpm", {}) or {}
                self.veiculos = data.get("veiculos", {}) or {}
                self.valor_padrao_portal = float(
                    data.get("valor_padrao_portal", self.valor_padrao_portal)
                )
                logger.info(
                    "Tabela de valoração carregada: %d CPM, %d veículos.",
                    len(self.cpm), len(self.veiculos),
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Falha ao carregar tabela de valoração: %s", e)

    def _valor_por_cpm(self, plataforma: str, alcance: int) -> float:
        cpm = self.cpm.get(plataforma, 0.0)
        return round((int(alcance or 0) * cpm) / 1000.0, 2)

    def _valor_por_veiculo(self, veiculo: str) -> float:
        if not veiculo:
            return self.valor_padrao_portal
        chave = veiculo.strip().lower()
        registro = self.veiculos.get(chave)
        if registro:
            return float(registro.get("valor_referencia", self.valor_padrao_portal))
        return self.valor_padrao_portal

    def valor_estimado(self, plataforma: str, alcance: int = 0, veiculo: str = "") -> float:
        if plataforma in _PLATAFORMAS_CPM:
            return self._valor_por_cpm(plataforma, alcance)
        if plataforma in _PLATAFORMAS_TABELA:
            return self._valor_por_veiculo(veiculo)
        return 0.0

    def aplicar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        valores = []
        for _, row in df.iterrows():
            veiculo = (row.get("metadados") or {}).get("veiculo", "") if isinstance(
                row.get("metadados"), dict
            ) else ""
            if not veiculo:
                veiculo = row.get("autor", "") or ""
            valores.append(
                self.valor_estimado(
                    row.get("plataforma", ""),
                    int(row.get("alcance") or 0),
                    veiculo,
                )
            )
        df["valor_estimado"] = valores
        logger.info("Valoração aplicada: total R$ %.2f em %d clippings.",
                    float(df["valor_estimado"].sum()), len(df))
        return df