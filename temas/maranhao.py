import re
from urllib.parse import urlencode

import scrapy
from scrapy import Selector

from temas.base import DiarioSpider, compactar_texto, converter_data, extrair_contexto


class MaranhaoSpider(DiarioSpider):
    name = "maranhao"
    estado = "Maranhão"
    endpoint = "https://www.diariooficial.ma.gov.br/ajax.busca.php"

    async def start(self):
        for tema in self.temas:
            yield self._request(tema, scroll_id="", pagina=1)

    def _request(self, tema, scroll_id, pagina):
        parametros = {
            "termo": tema,
            "sigla": "",
            "datai": self.data_inicial.isoformat(),
            "dataf": self.data_final.isoformat(),
            "scrollId": scroll_id,
        }
        return scrapy.Request(
            f"{self.endpoint}?{urlencode(parametros)}",
            callback=self.parse_resultados,
            cb_kwargs={"tema": tema, "scroll_id": scroll_id, "pagina": pagina},
            dont_filter=bool(scroll_id),
        )

    def parse_resultados(self, response, tema, scroll_id, pagina):
        busca = (response.json().get("busca") or {})
        fragmento = busca.get("es_html") or ""
        seletor = Selector(text=fragmento, type="html")

        for card in seletor.css("div.card"):
            data_texto = compactar_texto(" ".join(card.css("#dataPub ::text").getall()))
            data_match = re.search(r"(\d{2}/\d{2}/\d{4})", data_texto)
            data_publicacao = converter_data(data_match.group(1)) if data_match else None
            if not data_publicacao or not (self.data_inicial <= data_publicacao <= self.data_final):
                continue

            onclick = card.css("[onclick*='setModal']::attr(onclick)").get() or ""
            argumentos = re.findall(r"'((?:\\'|[^'])*)'", onclick)
            codigo = argumentos[2] if len(argumentos) > 2 else ""
            pagina_diario = argumentos[4] if len(argumentos) > 4 else ""
            if not pagina_diario:
                texto_card = compactar_texto(card.xpath("string(.)").get())
                pagina_match = re.search(r"Página:\s*(\d+)", texto_card, re.IGNORECASE)
                pagina_diario = pagina_match.group(1) if pagina_match else ""

            if not codigo:
                continue

            titulo_base = compactar_texto(
                " ".join(card.css("strong.text-primary ::text").getall())
            ) or (argumentos[0] if argumentos else "Diário Oficial")
            paragrafos = [
                compactar_texto(paragrafo.xpath("string(.)").get())
                for paragrafo in card.css("p.card-text")
            ]
            descricao = next(
                (texto for texto in paragrafos if texto and not texto.lower().startswith("página:")),
                "",
            )
            titulo = f"{titulo_base} - página {pagina_diario}" if pagina_diario else titulo_base
            link = f"https://www.diariooficial.ma.gov.br/download.php?arq={codigo}"
            if pagina_diario:
                link += f"#page={pagina_diario}"

            yield self.resultado(
                link,
                tema,
                data_publicacao,
                titulo,
                extrair_contexto(descricao, tema),
            )

        novo_scroll = busca.get("scrollId") or ""
        continuar = busca.get("btnLoad")
        if isinstance(continuar, str):
            continuar = continuar.lower() not in {"false", "0", "nao", "não", ""}
        if fragmento and continuar and novo_scroll and novo_scroll != scroll_id and pagina < 1000:
            yield self._request(tema, novo_scroll, pagina + 1)
