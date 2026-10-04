#!/usr/bin/env python3
"""Junta valores JSON multilinha do .env numa linha so.

O formato .env e linha a linha: colar um JSON formatado quebra a variavel,
porque so a primeira linha e lida. Este script acha os valores que comecam
com { ou [ , junta ate fechar, e regrava minificado.

    python formatar_env.py            # arruma o .env
    python formatar_env.py outro.env  # arruma outro arquivo

Nao imprime nenhum valor: so os nomes das variaveis e o que mudou.
"""

import json
import re
import sys
from pathlib import Path

CAMPOS_SERVICE_ACCOUNT = ("type", "project_id", "private_key", "client_email", "token_uri")


def equilibrado(texto: str) -> bool:
    """Diz se chaves e colchetes fecham, ignorando o que esta dentro de string."""
    nivel = 0
    em_string = False
    escapando = False
    for c in texto:
        if escapando:
            escapando = False
            continue
        if c == "\\":
            escapando = True
        elif c == '"':
            em_string = not em_string
        elif not em_string:
            if c in "{[":
                nivel += 1
            elif c in "}]":
                nivel -= 1
    return nivel == 0


def formatar(caminho: Path) -> int:
    """Regrava o arquivo com os JSON em uma linha. Devolve quantos juntou."""
    linhas = caminho.read_text(encoding="utf-8").split("\n")
    saida: list[str] = []
    juntados = 0
    i = 0

    while i < len(linhas):
        linha = linhas[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", linha)

        if not m or not m.group(2).lstrip().startswith(("{", "[")):
            saida.append(linha)
            i += 1
            continue

        nome, valor = m.group(1), m.group(2)

        # Acumula ate o JSON fechar (ou ate o arquivo acabar).
        fim = i
        while not equilibrado(valor) and fim + 1 < len(linhas):
            fim += 1
            valor += linhas[fim].strip()

        try:
            dados = json.loads(valor)
        except json.JSONDecodeError as e:
            print(f"  {nome}: nao e JSON valido ({e.msg}) - deixei como estava")
            saida.append(linha)
            i += 1
            continue

        saida.append(f"{nome}={json.dumps(dados, separators=(',', ':'))}")
        if fim > i:
            juntados += 1
            print(f"  {nome}: juntei {fim - i + 1} linhas em 1")
        else:
            print(f"  {nome}: ja estava em uma linha")

        if isinstance(dados, dict):
            faltam = [c for c in CAMPOS_SERVICE_ACCOUNT if not dados.get(c)]
            if "private_key" in dados:
                print(f"    parece uma service account valida ({len(dados)} campos)")
            elif "project_info" in dados or "mobilesdk_app_id" in str(dados):
                print("    ATENCAO: isto e um google-services.json (config do app),")
                print("    nao uma service account. Faltam: " + ", ".join(faltam))

        i = fim + 1

    caminho.write_text("\n".join(saida), encoding="utf-8", newline="\n")
    return juntados


def main() -> None:
    alvo = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if not alvo.is_file():
        sys.exit(f"{alvo} nao existe.")

    print(f"Formatando {alvo}:")
    juntados = formatar(alvo)
    print(f"\n{juntados} variavel(is) reunida(s) em uma linha.")


if __name__ == "__main__":
    main()
