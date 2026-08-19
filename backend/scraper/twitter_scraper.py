import json
from pathlib import Path

from core.logger import get_logger
from scraper.base import AsyncScraper
from scraper.models import TIPO_COMENTARIO, TIPO_POSTAGEM, PLATAFORMA_TWITTER, RawItem

logger = get_logger(__name__)


class TwitterScraper(AsyncScraper):
    """Coleta tweets e respostas via `twscrape`.

    A pesquisa anonima foi encerrada pelo X; o twscrape intercepta o GraphQL
    interno e exige cookies validos de sessao do navegador (auth_token, ct0).

    Contas:
      - `config["contas_twitter"]`: lista de tuplas (username, senha, email)
      - `config["cookies_file"]`: arquivo JSON {username: {auth_token, ct0, ...}}
        aplicado por conta (recomendado — resiste a banimentos por roteamento
        automatico via pool SQLite e rotacao em HTTP 429).
    """

    plataforma = PLATAFORMA_TWITTER

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        cfg = config or {}
        self.contas_twitter: list[tuple] = cfg.get("contas_twitter", [])
        self.cookies_file = cfg.get("cookies_file", "")
        self._api = None

    def _cookies_por_conta(self) -> dict:
        if not self.cookies_file or not Path(self.cookies_file).exists():
            return {}
        return json.loads(Path(self.cookies_file).read_text(encoding="utf-8"))

    async def _api_cliente(self):
        if self._api is None:
            from twscrape import API

            api = API()
            cookies = self._cookies_por_conta()
            for conta in self.contas_twitter:
                usuario, senha, email = conta
                cookies_conta = cookies.get(usuario) or {}
                await api.pool.add_account(
                    usuario, senha, email, "", cookies=cookies_conta or None
                )
            if self.contas_twitter:
                await api.pool.login_all()
            self._api = api
        return self._api

    def _para_item(self, agente: dict, tweet) -> RawItem:
        return RawItem(
            agente_id=agente["id"],
            id_externo=str(tweet.id),
            plataforma=self.plataforma,
            tipo=TIPO_POSTAGEM,
            texto_limpo=tweet.rawContent or "",
            data_publicacao=tweet.date,
            autor=tweet.user.username if tweet.user else "",
            url=f"https://x.com/{tweet.user.username if tweet.user else 'i'}/status/{tweet.id}",
            alcance=int(tweet.viewCount or 0),
            metadados={
                "likes": int(tweet.likeCount or 0),
                "retweets": int(tweet.retweetCount or 0),
                "replies": int(tweet.replyCount or 0),
                "quote": int(tweet.quoteCount or 0),
            },
        )

    async def coletar(self, agente: dict, limite: int = 50) -> list[RawItem]:
        api = await self._api_cliente()
        itens: list[RawItem] = []
        for termo in agente.get("termos_de_busca", []):
            try:
                async for tweet in api.search(termo, limit=limite):
                    itens.append(self._para_item(agente, tweet))
                    if self.incluir_comentarios and tweet.replyCount:
                        async for resposta in api.tweet_replies(tweet.id, limit=limite):
                            itens.append(
                                RawItem(
                                    agente_id=agente["id"],
                                    id_externo=str(resposta.id),
                                    plataforma=self.plataforma,
                                    tipo=TIPO_COMENTARIO,
                                    texto_limpo=resposta.rawContent or "",
                                    data_publicacao=resposta.date,
                                    autor=resposta.user.username if resposta.user else "",
                                    url=f"https://x.com/{resposta.user.username if resposta.user else 'i'}/status/{resposta.id}",
                                    alcance=0,
                                )
                            )
                await self._sleep_async()
            except Exception as e:  # noqa: BLE001
                logger.warning("Twitter: falha no termo '%s' do agente %s: %s", termo, agente["id"], e)
        logger.info("Twitter: %d itens para %s", len(itens), agente["id"])
        return itens