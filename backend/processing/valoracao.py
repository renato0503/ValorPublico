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
      - Impresso: AVPE = centimetragem (cm²) × valor por cm² da base.
      - TV / Rádio: AVPE = duração (s) × valor por minuto da base.

    Alem do valor "de mercado" (valor_estimado), calcula o AVPE
    (Equivalencia de Valor Publicitario) e a centimetragem, que sao as
    metricas exigidas por orgaos publicos e agencies que prestam contas.
    """

    def __init__(self, db) -> None:
        self.db = db
        self.cpm: dict = {}
        self.veiculos: dict = {}
        self.bases_valoracao: dict = {}
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
                self.bases_valoracao = data.get("bases_valoracao", {}) or {}
                self.valor_padrao_portal = float(
                    data.get("valor_padrao_portal", self.valor_padrao_portal)
                )
                logger.info(
                    "Tabela de valoração carregada: %d CPM, %d veículos, %d bases.",
                    len(self.cpm), len(self.veiculos), len(self.bases_valoracao),
                )
        except Exception as e:  # noqa: BLE001
            logger.error("Falha ao carregar tabela de valoração: %s", e)

    def _base(self, tipo: str) -> dict:
        return self.bases_valoracao.get(tipo, {}) or {}

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

    def _valor_por_cm2(self) -> float:
        return float(self._base("impresso").get("valor_por_cm2", 0.0) or 0.0)

    def _valor_por_minuto(self, tipo: str) -> float:
        return float(self._base(tipo).get("valor_por_minuto", 0.0) or 0.0)

    def valor_estimado(self, plataforma: str, alcance: int = 0, veiculo: str = "") -> float:
        if plataforma in _PLATAFORMAS_CPM:
            return self._valor_por_cpm(plataforma, alcance)
        if plataforma in _PLATAFORMAS_TABELA:
            return self._valor_por_veiculo(veiculo)
        return 0.0

    def avpe(
        self,
        plataforma: str,
        veiculo: str = "",
        espaco_cm2: float = 0.0,
        duracao_seg: float = 0.0,
        alcance: int = 0,
    ) -> float:
        """Equivalencia de Valor Publicitario (R$) segundo a base por tipo."""
        if plataforma == "Impresso":
            valor_cm2 = self._valor_por_cm2()
            if valor_cm2 and espaco_cm2:
                return round(espaco_cm2 * valor_cm2, 2)
            return self._valor_por_veiculo(veiculo)
        if plataforma in ("TV", "Radio"):
            valor_min = self._valor_por_minuto("tv" if plataforma == "TV" else "radio")
            if valor_min and duracao_seg:
                return round((duracao_seg / 60.0) * valor_min, 2)
            return self._valor_por_cpm(plataforma, alcance)
        return self.valor_estimado(plataforma, alcance, veiculo)

    def aplicar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        valores = []
        avpes = []
        cm2 = []
        duracoes = []
        for _, row in df.iterrows():
            metadados = row.get("metadados") if isinstance(row.get("metadados"), dict) else {}
            veiculo = metadados.get("veiculo", "") or row.get("autor", "") or ""
            plataforma = row.get("plataforma", "")
            alcance = int(row.get("alcance") or 0)
            espaco_cm2 = float(metadados.get("espaco_cm2") or 0.0)
            duracao_seg = float(metadados.get("duracao_seg") or 0.0)
            if not espaco_cm2 and plataforma == "Impresso":
                espaco_cm2 = round(float(metadados.get("espaco_carac") or 0.0) / 12.0, 2)
            if not duracao_seg and plataforma in ("TV", "Radio", "YouTube"):
                duracao_seg = round(len(str(row.get("texto_limpo") or "")) / 15.0, 1)

            valor = self.valor_estimado(plataforma, alcance, veiculo)
            valores.append(valor)
            avpes.append(self.avpe(plataforma, veiculo, espaco_cm2, duracao_seg, alcance))
            cm2.append(round(espaco_cm2, 2))
            duracoes.append(round(duracao_seg, 1))
        df["valor_estimado"] = valores
        df["valor_avpe"] = avpes
        df["espaco_cm2"] = cm2
        df["duracao_seg"] = duracoes
        logger.info(
            "Valoração aplicada: R$ %.2f em valor de mercado, R$ %.2f em AVPE, %d clippings.",
            float(df["valor_estimado"].sum()), float(df["valor_avpe"].sum()), len(df),
        )
        return df