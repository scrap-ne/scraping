import unittest
from datetime import date
from urllib.parse import parse_qs, urlsplit

from scrapy.http import Response, TextResponse

from temas.pernambuco import PernambucoSpider
from temas.rio_grande_do_norte import RioGrandeDoNorteSpider


class SdoeSpiderLinksTest(unittest.TestCase):
    def setUp(self):
        self.data = date(2025, 4, 11)

    def test_link_busca_aplica_diario_tema_e_data_exata(self):
        spider = RioGrandeDoNorteSpider(
            temas=["Parque tecnológico"],
            data_inicial=self.data,
            data_final=self.data,
        )

        link = spider._link_busca("Parque tecnológico", self.data)
        fragmento = urlsplit(link).fragment
        rota, consulta = fragmento.split("?", 1)
        parametros = parse_qs(consulta)

        self.assertEqual(rota, "/busca-avancada")
        self.assertEqual(parametros["diario"], ["MTIx"])
        self.assertEqual(parametros["inicio"], ["11/04/2025"])
        self.assertEqual(parametros["fim"], ["11/04/2025"])
        self.assertEqual(parametros["palavra"], ["Parque tecnológico"])
        self.assertEqual(parametros["consultar"], ["true"])

    def test_mantem_pdf_quando_servidor_permite_exibicao_inline(self):
        spider = PernambucoSpider(
            temas=["Transformação digital"],
            data_inicial=self.data,
            data_final=self.data,
        )
        request = self._request_verificacao(spider)
        response = Response(
            request.url,
            status=200,
            headers={"Content-Type": "application/pdf"},
            request=request,
        )

        resultado = spider._finalizar_link(response)

        self.assertEqual(resultado["link"], request.meta["link_pdf"])

    def test_usa_busca_quando_pdf_forca_download(self):
        spider = RioGrandeDoNorteSpider(
            temas=["Parque tecnológico"],
            data_inicial=self.data,
            data_final=self.data,
        )
        request = self._request_verificacao(spider)
        response = Response(
            request.url,
            status=200,
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

        resultado = spider._finalizar_link(response)

        self.assertEqual(resultado["link"], request.meta["link_busca"])

    def test_usa_busca_quando_pdf_e_inexistente(self):
        spider = PernambucoSpider(
            temas=["Transformação digital"],
            data_inicial=self.data,
            data_final=self.data,
        )
        request = self._request_verificacao(spider)
        response = Response(request.url, status=404, request=request)

        resultado = spider._finalizar_link(response)

        self.assertEqual(resultado["link"], request.meta["link_busca"])

    def _request_verificacao(self, spider):
        resposta_api = TextResponse(
            "https://example.test/search",
            status=200,
            body=(
                b'{"list":[{"codigo":1,"titulo":"Teste",'
                b'"texto":"Texto","dataPublicacao":"2025-04-11"}],'
                b'"rowCount":1}'
            ),
            headers={"Content-Type": "application/json"},
            encoding="utf-8",
        )
        return next(spider.parse_resultados(resposta_api, spider.temas[0], 0))


if __name__ == "__main__":
    unittest.main()
