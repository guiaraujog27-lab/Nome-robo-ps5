import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup


PRODUTO = "PS5 Slim Digital 1TB"
PRECO_MAXIMO = 3500.00


LOJAS = [

    {
        "nome": "KaBuM!",
        "url": "https://www.kabum.com.br/produto/875818/console-sony-playstation-5-slim-edicao-digital-ssd-1tb-controle-sem-fio-dualsense-2-jogos-digitais-1000038894"
    },

    {
        "nome": "Pichau",
        "url": "https://www.pichau.com.br/console-sony-playstation-5-slim-edicao-digital-ssd-1tb-com-controle-sem-fio-dualsense-com-2-jogos-digitais-branco-1000038894"
    }
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 "
        "like Mac OS X) AppleWebKit/605.1.15 "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9"
}


def converter_preco(valor):

    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor)

    texto = texto.replace("R$", "")
    texto = texto.replace("\xa0", " ")
    texto = texto.strip()

    # Exemplo: 3.799,99
    if "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    # Remove caracteres restantes
    texto = re.sub(
        r"[^0-9.]",
        "",
        texto
    )

    try:
        return float(texto)
    except:
        return None


def procurar_jsonld(soup):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        try:

            dados = json.loads(
                script.string or script.get_text()
            )

            lista = dados if isinstance(
                dados,
                list
            ) else [dados]

            for item in lista:

                if not isinstance(item, dict):
                    continue

                if item.get("@type") == "Product":

                    return item

                if "Product" in str(
                    item.get("@type", "")
                ):

                    return item

        except Exception:
            continue

    return None


def consultar_loja(loja):

    print()
    print("🏪 Consultando:", loja["nome"])

    try:

        resposta = requests.get(
            loja["url"],
            headers=HEADERS,
            timeout=30
        )

        print(
            "Status:",
            resposta.status_code
        )

        if resposta.status_code != 200:

            return {
                "loja": loja["nome"],
                "status": "bloqueada",
                "erro": f"HTTP {resposta.status_code}"
            }

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        produto = procurar_jsonld(soup)

        preco = None
        titulo = None

        if produto:

            titulo = produto.get(
                "name"
            )

            oferta = produto.get(
                "offers",
                {}
            )

            if isinstance(oferta, list):
                oferta = oferta[0]

            if isinstance(oferta, dict):

                preco = converter_preco(
                    oferta.get("price")
                )

        # Segunda tentativa:
        # procurar valores monetários no HTML

        if preco is None:

            texto = soup.get_text(
                " ",
                strip=True
            )

            encontrados = re.findall(
                r"R\$\s*[\d\.]+,\d{2}",
                texto
            )

            valores = []

            for valor in encontrados:

                numero = converter_preco(
                    valor
                )

                if numero:

                    # Evita valores absurdos
                    if 1000 <= numero <= 10000:
                        valores.append(numero)

            if valores:

                preco = min(valores)

        resultado = {

            "loja": loja["nome"],

            "titulo": titulo
                or PRODUTO,

            "preco": preco,

            "url": loja["url"],

            "status": (
                "encontrado"
                if preco is not None
                else "preco_nao_encontrado"
            )

        }

        return resultado

    except Exception as erro:

        print(
            "Erro:",
            erro
        )

        return {

            "loja": loja["nome"],

            "status": "erro",

            "erro": str(erro)

        }


def comparar(ofertas):

    validas = [

        oferta
        for oferta in ofertas

        if oferta.get("preco") is not None

    ]

    validas.sort(
        key=lambda x: x["preco"]
    )

    return validas


def salvar(ofertas, validas):

    menor = (
        validas[0]["preco"]
        if validas
        else None
    )

    resultado = {

        "produto": PRODUTO,

        "preco_maximo":
            PRECO_MAXIMO,

        "atualizado":
            datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            ),

        "menor_preco":
            menor,

        "oferta_encontrada":
            (
                menor is not None
                and menor <= PRECO_MAXIMO
            ),

        "ofertas":
            ofertas,

        "ranking":
            validas

    }

    with open(
        "resultado.json",
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            resultado,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    return resultado


def main():

    print()
    print("==============================")
    print("🤖 ROBÔ PS5 V4")
    print("==============================")
    print(
        "🎮",
        PRODUTO
    )
    print(
        "🎯 Limite: R$",
        f"{PRECO_MAXIMO:.2f}"
    )

    ofertas = []

    for loja in LOJAS:

        resultado = consultar_loja(
            loja
        )

        ofertas.append(
            resultado
        )

    validas = comparar(
        ofertas
    )

    resultado = salvar(
        ofertas,
        validas
    )

    print()
    print("==============================")
    print("🏆 RESULTADO")
    print("==============================")

    if not validas:

        print(
            "❌ Nenhum preço foi encontrado."
        )

    else:

        for posicao, oferta in enumerate(
            validas,
            start=1
        ):

            print(
                f"{posicao}º "
                f"{oferta['loja']}: "
                f"R$ {oferta['preco']:.2f}"
            )

        menor = validas[0]["preco"]

        print()

        if menor <= PRECO_MAXIMO:

            print(
                "🔥🔥 OFERTA ENCONTRADA!"
            )

            print(
                f"💰 R$ {menor:.2f}"
            )

        else:

            print(
                "😴 Ainda está acima "
                "do seu limite."
            )

    print()
    print(
        "📄 resultado.json criado."
    )


if __name__ == "__main__":
    main()