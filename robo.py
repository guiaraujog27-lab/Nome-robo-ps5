import os
import json
import re
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


# ==========================================================
# ROBÔ DE PREÇOS V9
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
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
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
# NORMALIZAÇÃO
# ==========================================================

def normalizar(texto):
    if not texto:
        return ""

    texto = texto.lower()

    substituicoes = {
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

    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)

    texto = re.sub(r"[^a-z0-9]+", " ", texto)

    return " ".join(texto.split())


# ==========================================================
# PALAVRAS IMPORTANTES
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

    palavras = [
        p for p in palavras
        if p not in ignorar and len(p) >= 2
    ]

    return palavras


# ==========================================================
# RELEVÂNCIA DO PRODUTO
# ==========================================================

def pontuacao_produto(titulo, produto):
    titulo_normalizado = normalizar(titulo)

    palavras = palavras_produto(produto)

    if not palavras:
        return 0

    pontos = 0

    for palavra in palavras:

        # Palavra encontrada exatamente
        if palavra in titulo_normalizado.split():
            pontos += 3

        # Palavra encontrada dentro do texto
        elif palavra in titulo_normalizado:
            pontos += 1

    # Para PS5, PlayStation 5 também conta
    if "ps5" in normalizar(produto):
        if (
            "playstation 5" in titulo_normalizado
            or "playstation5" in titulo_normalizado
        ):
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

                valor = valor.strip()

                numero = float(
                    valor
                    .replace(".", "")
                    .replace(",", ".")
                )

                # Evita valores absurdos
                if 1 <= numero <= 100000:
                    valores.append(round(numero, 2))

            except ValueError:
                continue

    return valores


# ==========================================================
# EXTRAIR PREÇO JSON-LD
# ==========================================================

def extrair_jsonld(soup, produto):

    encontrados = []

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:

        try:

            conteudo = script.string

            if not conteudo:
                continue

            dados = json.loads(conteudo)

        except Exception:
            continue

        objetos = []

        if isinstance(dados, list):
            objetos.extend(dados)

        elif isinstance(dados, dict):

            objetos.append(dados)

            if isinstance(
                dados.get("@graph"),
                list
            ):
                objetos.extend(
                    dados["@graph"]
                )

        for objeto in objetos:

            if not isinstance(objeto, dict):
                continue

            tipo = str(
                objeto.get("@type", "")
            ).lower()

            if (
                "product" not in tipo
                and "productgroup" not in tipo
            ):
                continue

            nome = objeto.get("name", "")

            score = pontuacao_produto(
                nome,
                produto
            )

            if score <= 0:
                continue

            offers = objeto.get("offers")

            if isinstance(offers, dict):
                offers = [offers]

            if not isinstance(offers, list):
                continue

            for offer in offers:

                if not isinstance(
                    offer,
                    dict
                ):
                    continue

                preco = offer.get(
                    "price"
                )

                if preco is None:
                    continue

                try:

                    preco = float(
                        str(preco)
                        .replace(",", ".")
                    )

                    if 1 <= preco <= 100000:

                        encontrados.append({
                            "titulo": nome,
                            "preco": round(
                                preco,
                                2
                            ),
                            "score": score + 10,
                        })

                except ValueError:
                    continue

    return encontrados


# ==========================================================
# EXTRAIR OFERTAS DOS CARDS
# ==========================================================

def extrair_cards(soup, produto):

    candidatos = []

    # Procura elementos que normalmente representam
    # produtos em páginas de loja.
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

    elementos = []

    for seletor in seletores:

        try:
            elementos.extend(
                soup.select(seletor)
            )
        except Exception:
            continue

    # Remove duplicados
    vistos = set()

    for elemento in elementos:

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

        score = pontuacao_produto(
            texto,
            produto
        )

        # Se não parece ser o produto,
        # ignora completamente.
        if score < 3:
            continue

        precos = extrair_precos(
            texto
        )

        if not precos:
            continue

        # Dentro do CARD do produto,
        # podemos pegar o menor preço.
        preco = min(precos)

        candidatos.append({
            "titulo": texto[:300],
            "preco": preco,
            "score": score,
        })

    return candidatos


# ==========================================================
# EXTRAIR META TAGS
# ==========================================================

def extrair_meta(soup, produto):

    candidatos = []

    titulo = ""

    meta_title = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        }
    )

    if meta_title:
        titulo = meta_title.get(
            "content",
            ""
        )

    if not titulo and soup.title:
        titulo = soup.title.get_text(
            " ",
            strip=True
        )

    score = pontuacao_produto(
        titulo,
        produto
    )

    if score <= 0:
        return []

    metas = [
        {
            "property": "product:price:amount"
        },
        {
            "property": "og:price:amount"
        },
        {
            "name": "product:price:amount"
        },
    ]

    for atributos in metas:

        meta = soup.find(
            "meta",
            attrs=atributos
        )

        if not meta:
            continue

        valor = meta.get("content")

        if not valor:
            continue

        try:

            valor = float(
                str(valor)
                .replace(".", "")
                .replace(",", ".")
            )

            if 1 <= valor <= 100000:

                candidatos.append({
                    "titulo": titulo,
                    "preco": round(
                        valor,
                        2
                    ),
                    "score": score + 5,
                })

        except ValueError:
            continue

    return candidatos


# ==========================================================
# ESCOLHER MELHOR OFERTA
# ==========================================================

def escolher_melhor(candidatos):

    if not candidatos:
        return None

    # Primeiro prioriza relevância.
    candidatos.sort(
        key=lambda x: (
            x["score"],
            -x["preco"]
        ),
        reverse=True
    )

    melhor_score = candidatos[0]["score"]

    melhores = [
        x
        for x in candidatos
        if x["score"] >= melhor_score
    ]

    # Entre produtos igualmente relevantes,
    # pega o menor preço.
    melhores.sort(
        key=lambda x: x["preco"]
    )

    return melhores[0]


# ==========================================================
# TÍTULO
# ==========================================================

def extrair_titulo(soup, produto):

    meta = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        }
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
    print(
        f"Consultando: {nome_loja}"
    )
    print(url)

    try:

        resposta = requests.get(
            url,
            headers=HEADERS,
            timeout=25
        )

        print(
            f"Status: {resposta.status_code}"
        )

        if resposta.status_code == 403:

            return {
                "loja": nome_loja,
                "status": "bloqueada",
                "erro": "HTTP 403",
                "url": url,
            }

        if resposta.status_code != 200:

            return {
                "loja": nome_loja,
                "status": "erro",
                "erro": (
                    f"HTTP "
                    f"{resposta.status_code}"
                ),
                "url": url,
            }

        soup = BeautifulSoup(
            resposta.text,
            "html.parser"
        )

        titulo_pagina = extrair_titulo(
            soup,
            produto
        )

        candidatos = []

        # 1. JSON-LD
        candidatos.extend(
            extrair_jsonld(
                soup,
                produto
            )
        )

        # 2. Cards de produtos
        candidatos.extend(
            extrair_cards(
                soup,
                produto
            )
        )

        # 3. Meta tags
        candidatos.extend(
            extrair_meta(
                soup,