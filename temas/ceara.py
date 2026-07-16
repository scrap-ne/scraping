import re
from urllib.parse import urlencode

import scrapy
from scrapy import Selector

from temas.base import DiarioSpider, compactar_texto, converter_data, dividir_periodo


class CearaSpider(DiarioSpider):
    name = "ceara"
    estado = "Ceará"
    endpoint = "http://pesquisa.doe.seplag.ce.gov.br/doepesquisa/sead.to"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "RETRY_TIMES": 4,
    }

    async def start(self):
        identificador = 0
        for tema in self.temas:
            for inicio, fim in dividir_periodo(self.data_inicial, self.data_final):
                identificador += 1
                yield self._request_inicial(tema, inicio, fim, identificador)

    def _request_inicial(self, tema, inicio, fim, cookiejar):
        parametros = {
            "page": "pesquisaTextual",
            "action": "PesquisarTextual",
            "cmd": "11",
            "flag": "1",
            "dataini": inicio.strftime("%d/%m/%Y"),
            "datafim": fim.strftime("%d/%m/%Y"),
            "numDiario": "",
            "numCaderno": "",
            "numPagina": "",
            "RadioGroup1": "radio3",
            "pesqEx": tema,
        }
        consulta = urlencode(parametros, encoding="latin-1")
        return scrapy.Request(
            f"{self.endpoint}?{consulta}",
            callback=self.parse_resultados,
            meta={
                "cookiejar": cookiejar,
                "tema": tema,
                "inicio_janela": inicio,
                "fim_janela": fim,
                "pagina_busca": 1,
            },
            dont_filter=True,
        )

    def parse_resultados(self, response):
        tema = response.meta["tema"]
        corpo = response.body.decode("latin-1", errors="replace")
        seletor = Selector(text=corpo, type="html")
        linhas = seletor.xpath(
            "//tr[.//a[contains(@href, 'imagens.seplag.ce.gov.br/pdf/')]]"
        )

        for linha in linhas:
            link = linha.css("a::attr(href)").get()
            colunas = [
                compactar_texto(celula.xpath("string(.)").get())
                for celula in linha.xpath("./td")
            ]
            if len(colunas) < 4 or not link:
                continue

            data_publicacao = converter_data(colunas[0])
            if not data_publicacao or not (self.data_inicial <= data_publicacao <= self.data_final):
                continue

            diario, caderno, pagina = colunas[1:4]
            titulo = f"Diário Oficial nº {diario} - caderno {caderno} - página {pagina}"
            descricao = (
                f'Ocorrência de "{tema}" no Diário Oficial nº {diario}, '
                f"caderno {caderno}, página {pagina}."
            )
            yield self.resultado(link, tema, data_publicacao, titulo, descricao)

        onclick = seletor.css("input[name='proxima']::attr(onclick)").get() or ""
        proxima_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)", onclick)
        pagina_atual = int(response.meta.get("pagina_busca", 1))
        texto_pagina = compactar_texto(seletor.xpath("string(//body)").get())
        paginas_match = re.search(
            r"Pagina\s+(\d+)\s+de\s+(\d+)", texto_pagina, re.IGNORECASE
        )
        if paginas_match:
            pagina_atual = int(paginas_match.group(1))
            total_paginas = int(paginas_match.group(2))
        else:
            total_paginas = pagina_atual

        if proxima_match and pagina_atual < total_paginas:
            meta = response.meta.copy()
            meta["pagina_busca"] = pagina_atual + 1
            yield scrapy.Request(
                response.urljoin(proxima_match.group(1)),
                callback=self.parse_resultados,
                meta=meta,
                dont_filter=True,
            )
