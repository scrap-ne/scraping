import json
import re
from collections import deque
from datetime import timedelta
from urllib.parse import urlencode, unquote, urlparse

import scrapy

from temas.base import (
    DiarioSpider,
    converter_data,
    dividir_periodo,
    extrair_contexto,
    limpar_html,
)


class ParaibaSpider(DiarioSpider):
    name = "paraiba"
    estado = "Paraíba"
    cse_id = "f748d1f61789e4163"
    cse_script = f"https://cse.google.com/cse.js?cx={cse_id}"
    cse_endpoint = "https://cse.google.com/cse/element/v1"
    portal = "https://auniao.pb.gov.br/"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tarefas = deque()

    async def start(self):
        yield scrapy.Request(
            self.cse_script,
            callback=self.parse_configuracao_cse,
            headers={"Referer": self.portal},
        )

    def parse_configuracao_cse(self, response):
        match = re.search(r"\}\)\((\{.*\})\);\s*$", response.text, re.DOTALL)
        if not match:
            self.logger.error("Nao foi possivel ler a configuracao de busca do portal da Paraiba.")
            return

        configuracao = json.loads(match.group(1))
        for tema in self.temas:
            # O indice incorporado limita cada consulta a 100 resultados.
            for inicio_periodo, fim_periodo in dividir_periodo(
                self.data_inicial, self.data_final, maximo_dias=364
            ):
                self._tarefas.append((tema, inicio_periodo, fim_periodo))

        proxima = self._proxima_tarefa(configuracao)
        if proxima:
            yield proxima

    def _proxima_tarefa(self, configuracao):
        if not self._tarefas:
            return None
        tema, inicio_periodo, fim_periodo = self._tarefas.popleft()
        return self._request_busca(
            tema,
            configuracao,
            inicio=0,
            inicio_periodo=inicio_periodo,
            fim_periodo=fim_periodo,
        )

    def _request_busca(self, tema, configuracao, inicio, inicio_periodo, fim_periodo):
        data_exclusiva_inicial = inicio_periodo - timedelta(days=1)
        data_exclusiva_final = fim_periodo + timedelta(days=1)
        consulta = (
            f'site:auniao.pb.gov.br/servicos/doe/ "{tema}" '
            f"after:{data_exclusiva_inicial.isoformat()} "
            f"before:{data_exclusiva_final.isoformat()}"
        )
        parametros = {
            "rsz": "filtered_cse",
            "num": 10,
            "hl": "pt-BR",
            "source": "gcsc",
            "start": inicio,
            "cselibv": configuracao.get("cselibVersion", ""),
            "cx": self.cse_id,
            "q": consulta,
            "safe": "active",
            "cse_tok": configuracao.get("cse_token", ""),
            "exp": ",".join(configuracao.get("exp") or []),
            "fexp": ",".join(str(valor) for valor in configuracao.get("fexp") or []),
            "rurl": self.portal,
            "callback": "google.search.cse.api1",
        }
        return scrapy.Request(
            f"{self.cse_endpoint}?{urlencode(parametros)}",
            callback=self.parse_resultados,
            headers={"Referer": self.portal},
            cb_kwargs={
                "tema": tema,
                "configuracao": configuracao,
                "inicio": inicio,
                "inicio_periodo": inicio_periodo,
                "fim_periodo": fim_periodo,
            },
        )

    def parse_resultados(
        self, response, tema, configuracao, inicio, inicio_periodo, fim_periodo
    ):
        inicio_json = response.text.find("{")
        fim_json = response.text.rfind("}")
        if inicio_json < 0 or fim_json < inicio_json:
            self.logger.warning("Resposta inesperada do indice de busca da Paraiba para %r.", tema)
            return

        dados = json.loads(response.text[inicio_json : fim_json + 1])
        if dados.get("error"):
            erro = dados["error"]
            self.logger.warning("O indice da Paraiba recusou a consulta de %r: %s", tema, erro)
            if erro.get("code") == 429:
                self._tarefas.clear()
                return
            proxima = self._proxima_tarefa(configuracao)
            if proxima:
                yield proxima
            return

        for registro in dados.get("results") or []:
            link_original = registro.get("unescapedUrl") or registro.get("url") or ""
            link = self._normalizar_link_doe(link_original)
            data_publicacao = self._data_do_link(link)
            if not link or not data_publicacao:
                continue
            if not (inicio_periodo <= data_publicacao <= fim_periodo):
                continue

            titulo = limpar_html(registro.get("title") or "Diário Oficial da Paraíba")
            descricao = extrair_contexto(registro.get("content") or "", tema)
            yield self.resultado(link, tema, data_publicacao, titulo, descricao)

        paginas = (dados.get("cursor") or {}).get("pages") or []
        proximos = sorted(
            int(pagina.get("start"))
            for pagina in paginas
            if str(pagina.get("start", "")).isdigit() and int(pagina["start"]) > inicio
        )
        if proximos and proximos[0] <= 90:
            yield self._request_busca(
                tema,
                configuracao,
                proximos[0],
                inicio_periodo,
                fim_periodo,
            )
        else:
            proxima = self._proxima_tarefa(configuracao)
            if proxima:
                yield proxima

    @staticmethod
    def _normalizar_link_doe(link):
        link = unquote(str(link or ""))
        parsed = urlparse(link)
        if not (parsed.hostname or "").lower().endswith("auniao.pb.gov.br"):
            return ""
        if not parsed.path.lower().startswith("/servicos/doe/"):
            return ""

        pdf = re.match(r"(?i)(.*?\.pdf)(?:/.*)?$", f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
        return pdf.group(1) if pdf else ""

    @staticmethod
    def _data_do_link(link):
        match = re.search(r"(\d{2})-(\d{2})-(\d{4})", link or "")
        if not match:
            return None
        dia, mes, ano = match.groups()
        return converter_data(f"{dia}/{mes}/{ano}")
