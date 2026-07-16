import html
import re
import unicodedata
from datetime import date, datetime, timedelta

import scrapy
from scrapy import Selector


FORMATOS_DATA = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
)


def compactar_texto(valor):
    return re.sub(r"\s+", " ", html.unescape(str(valor or ""))).strip()


def limpar_html(valor):
    if not valor:
        return ""
    valor = str(valor).replace("\\/", "/")
    seletor = Selector(text=f"<div>{valor}</div>", type="html")
    return compactar_texto(" ".join(seletor.xpath("//div//text()").getall()))


def limitar_texto(valor, limite=2000):
    valor = compactar_texto(valor)
    if len(valor) <= limite:
        return valor
    return valor[: limite - 3].rstrip() + "..."


def normalizar_texto(valor):
    decomposed = unicodedata.normalize("NFD", str(valor or ""))
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def extrair_contexto(texto, tema, limite=900):
    texto = limpar_html(texto)
    if len(texto) <= limite:
        return texto

    normalizado = normalizar_texto(texto)
    candidatos = [normalizar_texto(tema)]
    candidatos.extend(
        palavra
        for palavra in normalizar_texto(tema).split()
        if len(palavra) >= 5
    )
    posicao = next((normalizado.find(valor) for valor in candidatos if valor and valor in normalizado), 0)
    inicio = max(0, posicao - limite // 3)
    fim = min(len(texto), inicio + limite)
    inicio = max(0, fim - limite)

    trecho = texto[inicio:fim].strip()
    if inicio:
        trecho = "... " + trecho
    if fim < len(texto):
        trecho += " ..."
    return trecho


def converter_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(str(valor).strip(), formato).date()
        except (TypeError, ValueError):
            continue
    return None


def dividir_periodo(inicio, fim, maximo_dias=365):
    atual = inicio
    while atual <= fim:
        final_janela = min(atual + timedelta(days=maximo_dias), fim)
        yield atual, final_janela
        atual = final_janela + timedelta(days=1)


class DiarioSpider(scrapy.Spider):
    estado = ""

    def __init__(self, temas=None, data_inicial=None, data_final=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.temas = list(temas or [])
        self.data_inicial = converter_data(data_inicial)
        self.data_final = converter_data(data_final)

        if not self.temas:
            raise ValueError("Informe pelo menos um tema para a pesquisa.")
        if not self.data_inicial or not self.data_final:
            raise ValueError("As datas inicial e final sao obrigatorias.")
        if self.data_inicial > self.data_final:
            raise ValueError("A data inicial nao pode ser posterior a data final.")

    def resultado(self, link, tema, data_publicacao, titulo, descricao):
        data_publicacao = converter_data(data_publicacao)
        return {
            "Estado": self.estado,
            "link": compactar_texto(link),
            "tema": tema,
            "data": data_publicacao.isoformat() if data_publicacao else "",
            "titulo": limitar_texto(titulo or "Diário Oficial", 500),
            "descrição": limitar_texto(descricao or "", 2000),
        }
