import re
from urllib.parse import quote

import scrapy

from temas.base import DiarioSpider, compactar_texto, converter_data, extrair_contexto, limpar_html


class PiauiSpider(DiarioSpider):
    name = "piaui"
    estado = "Piauí"
    busca_url = "https://www.diario.pi.gov.br/doe/Api/buscaavancada.json"
    detalhe_url = "https://www.diario.pi.gov.br/doe/Api/visualizarnota.json"
    referer = "https://www.diario.pi.gov.br/doe/busca"

    async def start(self):
        for tema in self.temas:
            yield scrapy.FormRequest(
                self.busca_url,
                formdata={"filter_texto": tema},
                headers={"Referer": self.referer, "X-Requested-With": "XMLHttpRequest"},
                callback=self.parse_busca,
                cb_kwargs={"tema": tema},
            )

    def parse_busca(self, response, tema):
        registros = response.json().get("resposta") or []
        for registro in registros:
            dados_diario = registro.get("dadosDiario") or ""
            data_match = re.search(r"(\d{2}/\d{2}/\d{4})", dados_diario)
            data_publicacao = converter_data(data_match.group(1)) if data_match else None
            if not data_publicacao or not (self.data_inicial <= data_publicacao <= self.data_final):
                continue

            uuid = registro.get("nota")
            anexo = registro.get("anexodiario") or ""
            if not uuid or not anexo:
                continue

            categoria_match = re.search(r'em\s+<i>["“](.*?)["”]</i>', dados_diario, re.IGNORECASE)
            categoria = limpar_html(categoria_match.group(1)) if categoria_match else "Diário Oficial"
            link = (
                "https://www.diario.pi.gov.br/doe/files/diarios/anexo/"
                f"{quote(anexo, safe='/%')}"
            )
            yield scrapy.FormRequest(
                self.detalhe_url,
                formdata={"uuid": str(uuid)},
                headers={"Referer": self.referer, "X-Requested-With": "XMLHttpRequest"},
                callback=self.parse_detalhe,
                cb_kwargs={
                    "tema": tema,
                    "data_publicacao": data_publicacao,
                    "categoria": categoria,
                    "link": link,
                },
                dont_filter=True,
            )

    def parse_detalhe(self, response, tema, data_publicacao, categoria, link):
        nota = response.json().get("nota") or {}
        titulo_info = nota.get("titulo_nota") or {}
        if isinstance(titulo_info, list):
            titulo_info = titulo_info[0] if titulo_info else {}
        titulo_base = (
            titulo_info.get("texto") if isinstance(titulo_info, dict) else titulo_info
        ) or categoria
        numero_nota = nota.get("n_nota")
        titulo = compactar_texto(titulo_base)
        if numero_nota:
            titulo = f"{titulo} - nota {numero_nota}"

        data_nota = converter_data(nota.get("dia")) or data_publicacao
        descricao = extrair_contexto(nota.get("texto") or "", tema)
        yield self.resultado(link, tema, data_nota, titulo, descricao)
