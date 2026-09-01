import requests
import json
from datetime import datetime

# ==========================================
# CONFIGURAÇÃO
# ==========================================

PRODUTO = "PS5 Slim Digital 1TB"
PRECO_MAXIMO = 3500.00

API = "https://api.mercadolibre.com/sites/MLB/search"

PARAMETROS = {
    "q": PRODUTO,
    "sort": "price_asc",
    "limit": 20
}

# ==========================================
# BUSCAR MERCADO LIVRE
# ==========================================

def buscar():

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        resposta = requests.get(
            API,
            params=PARAMETROS,
            headers=headers,
            timeout=30
        )

        print("Status da API:", resposta.status_code)

        if resposta.status_code != 200:

            print(
                "⚠️ Mercado Livre recusou a consulta."
            )

            print(
                "O robô continuará funcionando."
            )

            return []

        return resposta.json()

    except Exception as erro:

        print(
            "⚠️ Erro ao consultar Mercado Livre:"
        )

        print(erro)

        return {}


# ==========================================
# FILTRAR RESULTADOS
# ==========================================

def filtrar(dados):

    ofertas = []

    for item in dados.get(
        "results",
        []
    ):

        titulo = item.get(
            "title",
            ""
        )

        preco = item.get(
            "price"
        )

        link = item.get(
            "permalink"
        )

        if not preco or not link:
            continue

        titulo_lower = titulo.lower()

        if "ps5" not in titulo_lower:
            continue

        ofertas.append({

            "titulo": titulo,

            "preco": float(preco),

            "link": link,

            "vendedor":
                item.get(
                    "seller",
                    {}
                ).get(
                    "nickname",
                    "Não informado"
                ),

            "condicao":
                item.get(
                    "condition",
                    "Não informado"
                )

        })

    return sorted(
        ofertas,
        key=lambda x: x["preco"]
    )


# ==========================================
# SALVAR RESULTADO
# ==========================================

def salvar(ofertas):

    resultado = {

        "produto": PRODUTO,

        "preco_maximo":
            PRECO_MAXIMO,

        "atualizado":
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            ),

        "ofertas":
            ofertas[:10]

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


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():

    print()
    print("==============================")
    print("🎮 ROBÔ DE PREÇOS PS5")
    print("==============================")

    print(
        "🔎 Procurando:",
        PRODUTO
    )

    dados = buscar()

    if not dados:

        print()
        print(
            "❌ Não foi possível consultar "
            "o Mercado Livre agora."
        )

        salvar([])

        return

    ofertas = filtrar(dados)

    salvar(ofertas)

    print()

    if not ofertas:

        print(
            "❌ Nenhuma oferta encontrada."
        )

        return

    print(
        "🏆 OFERTAS ENCONTRADAS:"
    )

    print()

    for numero, oferta in enumerate(
        ofertas[:10],
        start=1
    ):

        print(
            f"{numero}. "
            f"{oferta['titulo']}"
        )

        print(
            f"💰 R$ "
            f"{oferta['preco']:.2f}"
        )

        print(
            f"👤 "
            f"{oferta['vendedor']}"
        )

        print(
            f"📦 "
            f"{oferta['condicao']}"
        )

        print(
            f"🔗 "
            f"{oferta['link']}"
        )

        if oferta["preco"] <= PRECO_MAXIMO:

            print(
                "🔥 ABAIXO DO SEU LIMITE!"
            )

        print(
            "----------------------------"
        )


if __name__ == "__main__":

    main()