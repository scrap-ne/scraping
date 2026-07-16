from urllib.parse import quote

import scrapy

from temas.base import DiarioSpider, extrair_contexto


class BuscaNovaSpider(DiarioSpider):
    base_url = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas_vistas = set()
        self._resultados_vistos = set()

    async def start(self):
        for tema in self.temas:
            yield self._request(tema, pagina=0, coletados=0)

    def _request(self, tema, pagina, coletados):
        termo = quote(f'"{tema}"', safe="")
        url = (
            f"{self.base_url}/busca/busca/buscar/query/{pagina}/"
            f"di:{self.data_inicial.isoformat()}/df:{self.data_final.isoformat()}/"
            f"?1=1&q={termo}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_resultados,
            cb_kwargs={"tema": tema, "pagina": pagina, "coletados": coletados},
        )

    def parse_resultados(self, response, tema, pagina, coletados):
        dados = response.json()
        hits_info = dados.get("hits") or {}
        registros = hits_info.get("hits") or []
        total_info = hits_info.get("total") or 0
        total = total_info.get("value", 0) if isinstance(total_info, dict) else total_info

        assinatura = tuple(
            registro.get("_id")
            or (
                (registro.get("_source") or {}).get("diario_id"),
                (registro.get("_source") or {}).get("pagina"),
            )
            for registro in registros
        )
        chave_pagina = (tema, assinatura)
        if registros and chave_pagina in self._paginas_vistas:
            self.logger.warning(
                "Pagina repetida interrompida para %r na pagina %s.", tema, pagina
            )
            return
        if registros:
            self._paginas_vistas.add(chave_pagina)

        for registro in registros:
            origem = registro.get("_source") or {}
            numero_pagina = origem.get("pagina") or registro.get("pagina") or 1
            diario_id = origem.get("diario_id") or registro.get("diario_id")
            chave_resultado = (tema, diario_id, numero_pagina)
            if chave_resultado in self._resultados_vistos:
                continue
            self._resultados_vistos.add(chave_resultado)

            destaques = registro.get("highlight") or {}
            conteudo = destaques.get("conteudo") or destaques.get("content") or []
            if isinstance(conteudo, str):
                conteudo = [conteudo]

            titulo_base = registro.get("suplemento") or registro.get("diario") or "Diário Oficial"
            titulo = f"{titulo_base} - página {numero_pagina}"
            data_publicacao = str(origem.get("data") or "")[:10]
            data_pesquisa = data_publicacao.replace("-", "")
            termo_publico = quote(f'"{tema}"', safe="")
            link = (
                f"{self.base_url}/buscanova/#/p=1&q={termo_publico}"
                f"&di={data_pesquisa}&df={data_pesquisa}"
                f"&edicao={diario_id}&pagina={numero_pagina}"
            )
            yield self.resultado(
                link,
                tema,
                data_publicacao,
                titulo,
                extrair_contexto(" ".join(conteudo), tema),
            )

        coletados += len(registros)
        if registros and coletados < int(total or 0):
            yield self._request(tema, pagina + 1, coletados)
