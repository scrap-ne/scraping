from temas._sdoe import SdoeSpider


class RioGrandeDoNorteSpider(SdoeSpider):
    name = "rio_grande_do_norte"
    estado = "Rio Grande do Norte"
    api_url = "https://deirn.sdoe.com.br/diariooficial/public/search"
    web_url = "https://deirn.sdoe.com.br/diariooficialweb/"
    codigo_diario = 121
