from temas._buscanova import BuscaNovaSpider


class SergipeSpider(BuscaNovaSpider):
    name = "sergipe"
    estado = "Sergipe"
    base_url = "https://iose.se.gov.br"
