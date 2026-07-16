from temas._sdoe import SdoeSpider


class PernambucoSpider(SdoeSpider):
    name = "pernambuco"
    estado = "Pernambuco"
    api_url = "https://diariooficial.cepe.com.br/diariooficial/public/search"
    web_url = "https://diariooficial.cepe.com.br/diariooficialweb/"
    codigo_diario = 1
