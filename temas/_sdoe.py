import json

import scrapy

from temas.base import DiarioSpider, converter_data, extrair_contexto


class SdoeSpider(DiarioSpider):
    api_url = ""
    web_url = ""
    codigo_diario = 0
    arquivos_url = "https://cepebr-prod.s3.sa-east-1.amazonaws.com"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resultados_vistos = set()

    async def start(self):
        for tema in self.temas:
            yield self._request(tema, primeiro=0)

    def _request(self, tema, primeiro):
        origem = self.web_url.split("/diariooficialweb", 1)[0]
        corpo = {
            "first": primeiro,
            "maxResults": 10,
            "restricoes": {},
            "order": {},
            "palavras": tema,
            "dataInicial": self.data_inicial.strftime("%d/%m/%Y"),
            "dataFinal": self.data_final.strftime("%d/%m/%Y"),
            "intervaloAno": (
                f"{self.data_inicial.strftime('%d/%m/%Y')}-"
                f"{self.data_final.strftime('%d/%m/%Y')}"
            ),
            "codigoDiario": self.codigo_diario,
        }
        return scrapy.Request(
            self.api_url,
            method="POST",
            body=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": origem,
                "Referer": self.web_url,
            },
            callback=self.parse_resultados,
            cb_kwargs={"tema": tema, "primeiro": primeiro},
        )

    def parse_resultados(self, response, tema, primeiro):
        dados = response.json()
        registros = dados.get("list") or []
        total = int(dados.get("rowCount") or 0)

        for registro in registros:
            codigo_publicacao = registro.get("codigo")
            chave_resultado = (tema, codigo_publicacao)
            if chave_resultado in self._resultados_vistos:
                continue
            self._resultados_vistos.add(chave_resultado)

            data_publicacao = converter_data(registro.get("dataPublicacao"))
            if not data_publicacao:
                continue
            data_iso = data_publicacao.isoformat()
            link = (
                f"{self.arquivos_url}/{self.codigo_diario}/arquivos/"
                f"resumoDiario/{data_iso}/{data_iso}.pdf"
            )
            titulo = registro.get("titulo") or registro.get("nomeCategoria") or "Diário Oficial"
            texto = registro.get("texto") or registro.get("resumo") or ""
            yield self.resultado(
                link,
                tema,
                data_publicacao,
                titulo,
                extrair_contexto(texto, tema),
            )

        proximo = primeiro + len(registros)
        if registros and proximo < total:
            yield self._request(tema, proximo)
