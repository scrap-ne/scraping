from temas._buscanova import BuscaNovaSpider


class BahiaSpider(BuscaNovaSpider):
    name = "bahia"
    estado = "Bahia"
    base_url = "https://dool.egba.ba.gov.br"
