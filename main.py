import argparse
from datetime import datetime
from pathlib import Path

from scrapy.crawler import CrawlerProcess

from config import ARQUIVO_SAIDA, DATA_FINAL, DATA_INICIAL, ESTADOS, TEMAS
from exportador import exportar_excel
from pipelines import RESULTADOS, limpar_resultados
from temas.alagoas import AlagoasSpider
from temas.bahia import BahiaSpider
from temas.ceara import CearaSpider
from temas.maranhao import MaranhaoSpider
from temas.paraiba import ParaibaSpider
from temas.pernambuco import PernambucoSpider
from temas.piaui import PiauiSpider
from temas.rio_grande_do_norte import RioGrandeDoNorteSpider
from temas.sergipe import SergipeSpider


ARANHAS = {
    "AL": AlagoasSpider,
    "BA": BahiaSpider,
    "CE": CearaSpider,
    "MA": MaranhaoSpider,
    "PB": ParaibaSpider,
    "PE": PernambucoSpider,
    "PI": PiauiSpider,
    "RN": RioGrandeDoNorteSpider,
    "SE": SergipeSpider,
}


def data_iso(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError as erro:
        raise argparse.ArgumentTypeError("Use datas no formato AAAA-MM-DD.") from erro


def argumentos():
    parser = argparse.ArgumentParser(
        description="Pesquisa os Diários Oficiais dos estados do Nordeste."
    )
    parser.add_argument("--inicio", type=data_iso, default=DATA_INICIAL)
    parser.add_argument("--fim", type=data_iso, default=DATA_FINAL)
    parser.add_argument(
        "--tema",
        action="append",
        dest="temas",
        help="Tema de pesquisa. Repita a opção para informar vários temas.",
    )
    parser.add_argument(
        "--estado",
        action="append",
        dest="estados",
        choices=sorted(ARANHAS),
        help="Sigla do estado. Repita a opção para executar mais de um.",
    )
    parser.add_argument("--saida", default=ARQUIVO_SAIDA, help="Caminho do arquivo XLSX.")
    return parser.parse_args()


def executar(inicio, fim, temas, estados, saida):
    if inicio > fim:
        raise ValueError("A data inicial não pode ser posterior à data final.")

    temas = [tema.strip() for tema in temas if tema and tema.strip()]
    if not temas:
        raise ValueError("Informe pelo menos um tema de pesquisa.")

    estados_invalidos = set(estados) - set(ARANHAS)
    if estados_invalidos:
        raise ValueError(f"Estados inválidos: {', '.join(sorted(estados_invalidos))}")

    limpar_resultados()
    processo = CrawlerProcess(
        settings={
            "LOG_LEVEL": "INFO",
            "TELNETCONSOLE_ENABLED": False,
            "ROBOTSTXT_OBEY": False,
            "COOKIES_ENABLED": True,
            "CONCURRENT_REQUESTS": 8,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
            "DOWNLOAD_DELAY": 0.2,
            "DOWNLOAD_TIMEOUT": 120,
            "RETRY_TIMES": 2,
            "USER_AGENT": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
            ),
            "ITEM_PIPELINES": {"pipelines.ColetaPipeline": 300},
        }
    )

    for sigla in estados:
        processo.crawl(
            ARANHAS[sigla],
            temas=temas,
            data_inicial=inicio,
            data_final=fim,
        )

    processo.start()
    caminho, quantidade = exportar_excel(RESULTADOS, Path(saida))
    print(f"Concluído: {quantidade} registros salvos em {caminho}")
    return caminho, quantidade


def main():
    args = argumentos()
    executar(
        inicio=args.inicio,
        fim=args.fim,
        temas=args.temas or TEMAS,
        estados=args.estados or ESTADOS,
        saida=args.saida,
    )


if __name__ == "__main__":
    main()
