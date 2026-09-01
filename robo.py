import os
import json
import re
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


# ==========================================================
# ROBÔ DE PREÇOS V10
# ==========================================================

PRODUTO_PADRAO = "PS5 Slim Digital 1TB"

produto = (os.getenv("PRODUTO") or PRODUTO_PADRAO).strip()

try:
    preco_maximo = float(
        os.getenv("PRECO_MAXIMO", "3500").replace(",", ".")
    )
except ValueError:
    preco_maximo = 3500.0


ARQUIVO_RESULTADO = "resultado.json"
ARQUIVO_HISTORICO = "historico.json"


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
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
# NORMALIZAR TEXTO
# ==========================================================

def normalizar(texto):
    if not texto:
        return ""

    texto = texto.lower()

    mapa = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for antigo, novo in mapa.items():
        texto = texto.replace(antigo, novo)

    texto = re.sub(r"[^a-z0-9]+", " ", texto)

    return " ".join(texto.split())


# ==========================================================
# PALAVRAS DO PRODUTO
# ==========================================================

def palavras_produto(produto):
    texto = normalizar(produto)

    palavras = texto.split()

    ignorar = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "para",
        "com",
        "e",
        "em",
        "a",
        "o",
        "um",
        "uma",
    }

    return [
        palavra
        for palavra in palavras
        if palavra not in ignorar and len(palavra) >= 2
    ]


# ==========================================================
# VERIFICAR SE É O PRODUTO
# ==========================================================

def pontuar_produto(texto, produto):
    texto_normalizado = normalizar(texto)

    if not texto_normalizado:
        return 0

    palavras = palavras_produto(produto)

    pontos = 0

    for palavra in palavras:
        if palavra in texto_normalizado.split():
            pontos += 3

    # Tratamento especial para PS5
    if "ps5" in normalizar(produto):

        if "ps5" in texto_normalizado:
            pontos += 8

        if "playstation 5" in texto_normalizado:
            pontos += 8

    # Digital
    if "digital" in normalizar(produto):
        if "digital" in texto_normalizado:
            pontos += 5

    # 1TB
    if "1tb" in normalizar(produto):
        if "1tb" in texto_normalizado:
            pontos += 5

    return pontos


# ==========================================================
# EXTRAIR PREÇOS
# ==========================================================

def extrair_precos(texto):
    if not texto:
        return []

    texto = texto.replace("\xa0", " ")

    padroes = [
        r"R\$\s*([\d\.]+,\d{2})",
        r"R\$\s*([\d]+,\d{2})",
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
                numero = float(
                    valor
                    .replace(".", "")
                    .replace(",", ".")
                )

                # Faixa razoável para produtos
                if 50 <= numero <= 100000:
                    valores.append(round(numero, 2))

            except ValueError:
                pass

    return valores


# ==========================================================
# EXTRAIR JSON-LD
# ==========================================================

def extrair_jsonld(soup, produto):

    candidatos = []

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:

        try:
            if not script.string:
                continue

            dados = json.loads(script.string)

        except Exception:
            continue

        objetos = []

        if isinstance(dados, dict):
            objetos.append(dados)

            if isinstance(dados.get("@graph"), list):
                objetos.extend(dados["@graph"])

        elif isinstance(dados, list):
            objetos.extend(dados)

        for objeto in objetos:

            if not isinstance(objeto, dict):
                continue

            tipo = str(
                objeto.get("@type", "")
            ).lower()

            if "product" not in tipo:
                continue

            titulo = str(
                objeto.get("name", "")
            ).strip()

            score = pontuar_produto(
                titulo,
                produto
            )

            if score < 8:
                continue

            ofertas = objeto.get("offers")

            if isinstance(ofertas, dict):
                ofertas = [ofertas]

            if not isinstance(ofertas, list):
                continue

            for oferta in ofertas:

                if not isinstance(oferta, dict):
                    continue

                preco = oferta.get("price")

                if preco is None:
                    continue

                try:

                    preco = float(
                        str(preco)
                        .replace(",", ".")
                    )

                    if 50 <= preco <= 100000:

                        candidatos.append({
                            "titulo": titulo,
                            "preco": round(preco, 2),
                            "score": score + 20,
                            "origem": "JSON-LD",
                        })

                except ValueError:
                    continue

    return candidatos


# ==========================================================
# EXTRAIR PRODUTOS DOS CARDS
# ==========================================================

def extrair_cards(soup, produto):

    candidatos = []

    seletores = [
        "[class*='product']",
        "[class*='Product']",
        "[class*='produto']",
        "[class*='Produto']",
        "[class*='card']",
        "[class*='Card']",
        "[data-testid*='product']",
        "[data-testid*='Product']",
    ]

    encontrados = []

    for seletor in seletores:

        try:
            encontrados.extend(
                soup.select(seletor)
            )
        except Exception:
            pass

    vistos = set()

    for elemento in encontrados:

        texto = elemento.get_text(
            " ",
            strip=True
        )

        if not texto:
            continue

        chave = texto[:1000]

        if chave in vistos:
            continue

        vistos.add(chave)

        score = pontuar_produto(
            texto,
            produto
        )

        # Precisa parecer realmente com o produto
        if score < 8:
            continue

        precos = extrair_precos(texto)

        if not precos:
            continue

        preco = min(precos)

        candidatos.append({
            "titulo": texto[:500],
            "preco": preco,
            "score": score,
            "origem": "CARD",
        })

    return candidatos


# ==========================================================
# ESCOLHER MELHOR RESULTADO
# ==========================================================

def escolher_melhor(candidatos):

    if not candidatos:
        return None

    # Remove preços muito suspeitos para PS5
    if "ps5" in normalizar(produto):

        candidatos = [
            item
            for item in candidatos
            if item["preco"] >= 1500
        ]

    if not candidatos:
        return None

    # Primeiro maior confiança
    maior_score = max(
        item["score"]
        for item in candidatos
    )

    candidatos = [
        item
        for item in candidatos
        if item["score"] >= maior_score
    ]

    # Depois menor preço
    candidatos.sort(
        key=lambda item: item["preco"]
    )

    return candidatos[0]


# ==========================================================
# CONSULTAR LOJA
# ==========================================================

def consultar_loja(nome_loja, url):

    print()
    print("-" * 60)
    print(f"Consultando: {nome_loja}")
    print(url)

    try:

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"HTTP: {resposta.status_code}"
        )

        if resposta.status_code == 403:

            return {
                "loja": nome_loja,
                "url": url,
                "status": "bloqueada",
                "erro": "HTTP 403",
            }

        if resposta.status_code != 200:

            return {
                "loja": nome_loja,
                "url": url,
                "status": "erro",
                "erro": f"HTTP {resposta.status_code}",
            }

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        candidatos = []

        # ==================================================
        # MÉTODO 1 - JSON-LD
        # ==================================================

        candidatos.extend(
            extrair_jsonld(
                soup,
                produto
            )
        )

        # ==================================================
        # MÉTODO 2 - CARDS
        # ==================================================

        candidatos.extend(
            extrair_cards(
                soup,
                produto
            )
        )

        melhor = escolher_melhor(
            candidatos
        )

        if melhor is None:

            print(
                "Nenhum produto confiável encontrado."
            )

            return {
                "loja": nome_loja,
                "url": url,
                "status": "sem_preco",
            }

        print(
            f"Produto encontrado: "
            f"{melhor['titulo'][:150]}"
        )

        print(
            f"Preço: R$ "
            f"{melhor['preco']:.2f}"
        )

        print(
            f"Confiança: "
            f"{melhor['score']}"
        )

        return {
            "loja": nome_loja,
            "titulo": melhor["titulo"],
            "preco": melhor["preco"],
            "url": url,
            "status": "encontrado",
            "confianca": melhor["score"],
            "origem": melhor["origem"],
        }

    except requests.RequestException as erro:

        return {
            "loja": nome_loja,
            "url": url,
            "status": "erro",
            "erro": str(erro),
        }

    except Exception as erro:

        return {
            "loja": nome_loja,
            "url": url,
            "status": "erro",
            "erro": str(erro),
        }


# ==========================================================
# INÍCIO
# ==========================================================

print()
print("=" * 60)
print("ROBÔ DE PREÇOS V10")
print("=" * 60)

print()
print(
    f"Produto pesquisado: {produto}"
)

print(
    f"Preço máximo: R$ {preco_maximo:.2f}"
)

print()
print("=" * 60)


# ==========================================================
# PESQUISA
# ==========================================================

ofertas = []

for loja in LOJAS:

    url = loja["url"](produto)

    resultado = consultar_loja(
        loja["nome"],
        url
    )

    ofertas.append(
        resultado
    )


# ==========================================================
# FILTRAR RESULTADOS
# ==========================================================

ranking = [
    oferta
    for oferta in ofertas
    if (
        oferta.get("status") == "encontrado"
        and oferta.get("preco") is not None
    )
]


# Ordenar pelo preço
ranking.sort(
    key=lambda item: float(
        item["preco"]
    )
)


# ==========================================================
# MENOR PREÇO
# ==========================================================

if ranking:

    menor_preco = ranking[0]["preco"]

    melhor_loja = ranking[0]["loja"]

    melhor_url = ranking[0]["url"]

else:

    menor_preco = None
    melhor_loja = None
    melhor_url = None


# ==========================================================
# OFERTA
# ==========================================================

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
# RESULTADO
# ==========================================================

resultado = {
    "produto": produto,
    "preco_maximo": preco_maximo,
    "atualizado": data_formatada,
    "menor_preco": menor_preco,
    "melhor_loja": melhor_loja,
    "melhor_url": melhor_url,
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

if os.path.exists(
    ARQUIVO_HISTORICO
):

    try:

        with open(
            ARQUIVO_HISTORICO,
            "r",
            encoding="utf-8"
        ) as arquivo:

            historico = json.load(
                arquivo
            )

        if not isinstance(
            historico,
            list
        ):
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
print("RESULTADO FINAL")
print("=" * 60)
print()


if ranking:

    for indice, oferta in enumerate(
        ranking,
        start=1
    ):

        print(
            f"{indice}º "
            f"{oferta['loja']} - "
            f"R$ {oferta['preco']:.2f}"
        )

    print()

    print(
        f"🏆 Menor preço: "
        f"R$ {menor_preco:.2f}"
    )

    print(
        f"🏪 Loja: {melhor_loja}"
    )

    print(
        f"💰 Limite: "
        f"R$ {preco_maximo:.2f}"
    )

    if oferta_encontrada:

        print()
        print(
            "🔥 OFERTA ENCONTRADA!"
        )

    else:

        print()
        print(
            "⚠️ Nenhum preço abaixo "
            "do limite."
        )

else:

    print(
        "❌ Nenhum preço confiável "
        "foi encontrado."
    )


print()
print("=" * 60)
print("Arquivos gerados:")
print("resultado.json")
print("historico.json")
print("=" * 60)
print()