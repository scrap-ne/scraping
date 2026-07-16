RESULTADOS = []


def limpar_resultados():
    RESULTADOS.clear()


class ColetaPipeline:
    def process_item(self, item):
        RESULTADOS.append(dict(item))
        return item
