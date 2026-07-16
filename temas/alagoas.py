import json

import scrapy

from temas.base import DiarioSpider, extrair_contexto, limpar_html


class AlagoasSpider(DiarioSpider):
    name = "alagoas"
    estado = "Alagoas"
    endpoint = "https://diario.imprensaoficial.al.gov.br/apinova/api/editions/searchES"
    pagina_tamanho = 50

    async def start(self):
        for tema in self.temas:
            yield self._request(tema, pagina=1, coletados=0)

    def _request(self, tema, pagina, coletados):
        corpo = {
            "keywords": tema,
            "range": [self.data_inicial.isoformat(), self.data_final.isoformat()],
            "edition_number": "",
            "searchType": "frase_exata",
            "order": "novo",
        }
        url = f"{self.endpoint}?page={pagina}&bucket_size={self.pagina_tamanho}"
        return scrapy.Request(
            url,
            method="POST",
            body=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            callback=self.parse_resultados,
            cb_kwargs={"tema": tema, "pagina": pagina, "coletados": coletados},
        )

    def parse_resultados(self, response, tema, pagina, coletados):
        dados = response.json().get("result") or {}
        registros = dados.get("items") or []
        total_info = dados.get("total_rows") or 0
        total = total_info.get("value", 0) if isinstance(total_info, dict) else total_info

        for registro in registros:
            edicao_id = registro.get("edition_id")
            numero_pagina = registro.get("page_number")
            numero_edicao = registro.get("edition_number") or "sem número"
            destaques = registro.get("highlight") or []
            descricao = extrair_contexto(" ".join(destaques), tema)
            titulo = f"Diário Oficial nº {numero_edicao} - página {numero_pagina}"
            link = (
                "https://diario.imprensaoficial.al.gov.br/apinova/api/editions/"
                f"viewPdf/{edicao_id}#page={numero_pagina}"
            )
            yield self.resultado(
                link,
                tema,
                registro.get("publication_date"),
                titulo,
                limpar_html(descricao),
            )

        coletados += len(registros)
        if registros and coletados < int(total or 0):
            yield self._request(tema, pagina + 1, coletados)
