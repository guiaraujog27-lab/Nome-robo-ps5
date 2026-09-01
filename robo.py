import os
import json
import re
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


# ==========================================================
# ROBÔ DE PREÇOS V8
# ==========================================================

PRODUTO_PADRAO = "PS5 Slim Digital 1TB"

produto = (
    os.getenv("PRODUTO") or PRODUTO_PADRAO
).strip()

try:
    preco_maximo = float(
        os.getenv("PRECO_MAXIMO", "3500")
        .replace(",", ".")
    )
except ValueError:
    preco_maximo = 3500.0


ARQUIVO_RESULTADO = "resultado.json"
ARQUIVO_HISTORICO = "historico.json"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


# ==========================================================
# LOJAS
# ==========================================================

LOJAS = [
    {
        "nome": "KaBuM!",
        "url": lambda p:
            "https://www.kabum.com.br/busca/" + quote(p),
    },

    {
        "nome": "Pichau",
        "url": lambda p:
            "https://www.pichau.com.br/search?q=" + quote(p),
    },

    {
        "nome": "Terabyte",
        "url": lambda p:
            "https://www.terabyteshop.com.br/busca?str=" + quote(p),
    },

    {
        "nome": "Magazine Luiza",
        "url": lambda p:
            "https://www.magazineluiza.com.br/busca/" + quote(p),
    },

    {
        "nome": "Carrefour",
        "url": lambda p:
            "https://www.carrefour.com.br/busca/" + quote(p),
    },

    {
        "nome": "Mercado Livre",
        "url": lambda p:
            "https://lista.mercadolivre.com.br/" + quote(p),
    },

    {
        "nome": "Amazon",
        "url": lambda p:
            "https://www.amazon.com.br/s?k=" + quote(p),
    },
]


# ==========================================================
# PREÇO
# ==========================================================

def extrair_preco(texto):
    if not texto:
        return None

    texto = texto.replace("\xa0", " ")

    padroes = [
        r"R\$\s*([\d\.]+,\d{2})",
        r"R\$\s*([\d]+,\d{2})",
        r"R\$\s*([\d\.]+)",
    ]

    valores = []

    for padrao in padroes:
        encontrados = re.findall(
            padrao,
            texto,
            re.IGNORECASE
        )

        for valor in encontrados:
            try:
                valor = valor.strip()

                if "," in valor:
                    valor = (
                        valor
                        .replace(".", "")
                        .replace(",", ".")
                    )
                else:
                    valor = valor.replace(".", "")

                numero = float(valor)

                if 100 <= numero <= 100000:
                    valores.append(numero)

            except (ValueError, TypeError):
                continue

    if not valores:
        return None

    return round(min(valores), 2)


# ==========================================================
# TÍTULO
# ==========================================================

def extrair_titulo(soup, produto):
    meta = soup.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if meta and meta.get("content"):
        return meta["content"].strip()

    if soup.title:
        titulo = soup.title.get_text(
            " ",
            strip=True
        )

        if titulo:
            return titulo

    return produto


# ==========================================================
# CONSULTAR LOJA
# ==========================================================

def extrair_oferta(url, nome_loja):
    print()
    print(f"Consultando: {nome_loja}")
    print(url)

    try:
        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=25
        )

        print(f"Status: {resposta.status_code}")

        if resposta.status_code == 403:
            return {
                "loja": nome_loja,
                "status": "bloqueada",
                "erro": "HTTP 403",
            }

        if resposta.status_code != 200:
            return {
                "loja": nome_loja,
                "status": "erro",
                "erro": f"HTTP {resposta.status_code}",
            }

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        titulo = extrair_titulo(
            soup,
            produto
        )

        texto = soup.get_text(
            " ",
            strip=True
        )

        preco = extrair_preco(texto)

        if preco is None:
            return {
                "loja": nome_loja,
                "titulo": titulo,
                "url": url,
                "status": "sem_preco",
            }

        return {
            "loja": nome_loja,
            "titulo": titulo,
            "preco": preco,
            "url": url,
            "status": "encontrado",
        }

    except requests.RequestException as erro:
        return {
            "loja": nome_loja,
            "status": "erro",
            "erro": str(erro),
        }

    except Exception as erro:
        return {
            "loja": nome_loja,
            "status": "erro",
            "erro": str(erro),
        }


# ==========================================================
# INÍCIO
# ==========================================================

print()
print("=" * 60)
print("ROBÔ DE PREÇOS V8")
print("=" * 60)
print()
print(f"Produto pesquisado: {produto}")
print(f"Preço máximo: R$ {preco_maximo:.2f}")
print()
print("=" * 60)


# ==========================================================
# PESQUISAR
# ==========================================================

ofertas = []

for loja in LOJAS:
    resultado = extrair_oferta(
        loja["url"](produto),
        loja["nome"]
    )

    ofertas.append(resultado)


# ==========================================================
# RANKING
# ==========================================================

validas = [
    oferta
    for oferta in ofertas
    if (
        oferta.get("status") == "encontrado"
        and oferta.get("preco") is not None
    )
]

validas.sort(
    key=lambda item: float(item["preco"])
)

ranking = validas


# ==========================================================
# MENOR PREÇO
# ==========================================================

if ranking:
    menor_preco = ranking[0]["preco"]
else:
    menor_preco = None


oferta_encontrada = (
    menor_preco is not None
    and menor_preco <= preco_maximo
)


# ==========================================================
# DATA
# ==========================================================

agora = datetime.now()

data_formatada = agora.strftime(
    "%d/%m/%Y %H:%M:%S"
)


# ==========================================================
# RESULTADO.JSON
# ==========================================================

resultado = {
    "produto": produto,
    "preco_maximo": preco_maximo,
    "atualizado": data_formatada,
    "menor_preco": menor_preco,
    "oferta_encontrada": oferta_encontrada,
    "ofertas": ofertas,
    "ranking": ranking,
}


with open(
    ARQUIVO_RESULTADO,
    "w",
    encoding="utf-8"
) as arquivo:
    json.dump(
        resultado,
        arquivo,
        ensure_ascii=False,
        indent=2
    )


# ==========================================================
# HISTÓRICO
# ==========================================================

historico = []

if os.path.exists(ARQUIVO_HISTORICO):
    try:
        with open(
            ARQUIVO_HISTORICO,
            "r",
            encoding="utf-8"
        ) as arquivo:
            historico = json.load(arquivo)

        if not isinstance(historico, list):
            historico = []

    except Exception:
        historico = []


if ranking:
    melhor = ranking[0]

    historico.append({
        "data": data_formatada,
        "timestamp": agora.isoformat(),
        "produto": produto,
        "preco": melhor["preco"],
        "loja": melhor["loja"],
        "url": melhor["url"],
    })

    historico = historico[-500:]


with open(
    ARQUIVO_HISTORICO,
    "w",
    encoding="utf-8"
) as arquivo:
    json.dump(
        historico,
        arquivo,
        ensure_ascii=False,
        indent=2
    )


# ==========================================================
# RESULTADO NO TERMINAL
# ==========================================================

print()
print("=" * 60)
print("RESULTADO")
print("=" * 60)
print()


if ranking:

    for indice, oferta in enumerate(
        ranking,
        start=1
    ):
        print(
            f"{indice}º {oferta['loja']}: "
            f"R$ {oferta['preco']:.2f}"
        )

    print()

    print(
        f"Menor preço: R$ {menor_preco:.2f}"
    )

    print(
        f"Limite: R$ {preco_maximo:.2f}"
    )

    if oferta_encontrada:
        print()
        print("🔥 OFERTA ENCONTRADA!")
    else:
        print()
        print("Preço encontrado, mas acima do limite.")

else:

    print(
        "Nenhuma oferta com preço foi encontrada."
    )


print()
print("resultado.json criado.")
print("historico.json atualizado.")
print()