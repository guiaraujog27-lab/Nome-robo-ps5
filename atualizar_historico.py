import json
import os
from datetime import datetime

RESULTADO = "resultado.json"
HISTORICO = "historico.json"


def carregar_arquivo(nome, padrao):
    if not os.path.exists(nome):
        return padrao

    try:
        with open(nome, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        return padrao


def main():

    resultado = carregar_arquivo(
        RESULTADO,
        {}
    )

    historico = carregar_arquivo(
        HISTORICO,
        []
    )

    ofertas = resultado.get(
        "ofertas",
        []
    )

    validas = [
        oferta
        for oferta in ofertas
        if oferta.get("preco") is not None
    ]

    if not validas:
        print("Nenhum preço novo para registrar.")
        return

    menor = min(
        validas,
        key=lambda x: x["preco"]
    )

    registro = {
        "data": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "timestamp": datetime.now().isoformat(),
        "produto": resultado.get(
            "produto",
            "PS5 Slim Digital 1TB"
        ),
        "preco": menor["preco"],
        "loja": menor.get(
            "loja",
            "Não informado"
        ),
        "url": menor.get(
            "url",
            ""
        )
    }

    # Evita registrar exatamente o mesmo preço
    # da mesma loja em consultas consecutivas.

    if historico:

        ultimo = historico[-1]

        if (
            ultimo.get("preco") == registro["preco"]
            and ultimo.get("loja") == registro["loja"]
        ):
            print("Preço igual ao último registro.")
            return

    historico.append(registro)

    # Mantém os últimos 500 registros
    historico = historico[-500:]

    with open(
        HISTORICO,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            historico,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    print("Histórico atualizado.")
    print(
        f"Menor preço: R$ {menor['preco']:.2f}"
    )


if __name__ == "__main__":
    main()