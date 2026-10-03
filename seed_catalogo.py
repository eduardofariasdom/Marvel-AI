#!/usr/bin/env python3
"""Popula as colecoes `personagens` e `times` do Firestore.

Sem backend Node, o catalogo mora no proprio Firestore: o app mobile le direto
e as tools do Jarvis leem pelo Admin SDK. Rode uma vez.

    python seed_catalogo.py

Precisa da mesma FIREBASE_SERVICE_ACCOUNT_JSON que a API usa (o .env serve).
Rodar de novo apenas sobrescreve os mesmos documentos, nao duplica.

O campo `nomeBusca` e o nome em minusculas e sem acento: o Firestore nao tem
busca textual, entao a busca por prefixo depende dele.
"""

import unicodedata

from deps.firebase import get_firestore

AMEACA_ALTA = "alta"
AMEACA_MEDIA = "media"
AMEACA_BAIXA = "baixa"

PERSONAGENS: list[dict] = [
    # (nome, alterEgo, poderes, deck, viloes?, ameaca)
    {"nome": "Homem de Ferro", "alterEgo": "Tony Stark", "heroi": True, "ameaca": AMEACA_MEDIA,
     "poderes": ["Armadura", "Repulsores", "Voo"],
     "deck": "Genio bilionario que construiu uma armadura capaz de enfrentar deuses.",
     "times": ["Vingadores", "Illuminati"]},
    {"nome": "Homem-Aranha", "alterEgo": "Peter Parker", "heroi": True, "ameaca": AMEACA_BAIXA,
     "poderes": ["Teia", "Agilidade", "Sentido aranha"],
     "deck": "Picado por uma aranha radioativa, equilibra o ensino medio e a vigilancia de Nova York.",
     "times": ["Vingadores"]},
    {"nome": "Capita Marvel", "alterEgo": "Carol Danvers", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Energia", "Voo", "Super forca"],
     "deck": "Piloto da Forca Aerea que absorveu energia cosmica e virou uma das herois mais poderosas.",
     "times": ["Vingadores"]},
    {"nome": "Hulk", "alterEgo": "Bruce Banner", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Super forca", "Regeneracao", "Invulnerabilidade"],
     "deck": "Cientista exposto a radiacao gama que se transforma numa criatura verde de forca descomunal quando enraivecido.",
     "times": ["Vingadores", "Illuminati"]},
    {"nome": "Thor", "alterEgo": "Thor Odinson", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Raio", "Super forca", "Mjolnir"],
     "deck": "Deus do trovao asgardiano, herdeiro do trono de Odin.",
     "times": ["Vingadores"]},
    {"nome": "Capitao America", "alterEgo": "Steve Rogers", "heroi": True, "ameaca": AMEACA_MEDIA,
     "poderes": ["Escudo de vibranium", "Reflexos", "Lideranca"],
     "deck": "Soldado do soro do super-homem, simbolo de uma era e lider dos Vingadores.",
     "times": ["Vingadores"]},
    {"nome": "Viuva Negra", "alterEgo": "Natasha Romanoff", "heroi": True, "ameaca": AMEACA_BAIXA,
     "poderes": ["Espionagem", "Combate corpo a corpo", "Furtividade"],
     "deck": "Ex-agente da Sala Vermelha, a melhor espia da S.H.I.E.L.D.",
     "times": ["Vingadores"]},
    {"nome": "Pantera Negra", "alterEgo": "T'Challa", "heroi": True, "ameaca": AMEACA_MEDIA,
     "poderes": ["Traje de vibranium", "Agilidade", "Erva em forma de coracao"],
     "deck": "Rei de Wakanda e protetor da nacao mais avancada do planeta.",
     "times": ["Vingadores", "Illuminati"]},
    {"nome": "Doutor Estranho", "alterEgo": "Stephen Strange", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Magia", "Portais", "Manto da levitacao"],
     "deck": "Neurocirurgiao que virou Mago Supremo depois de perder as maos.",
     "times": ["Vingadores", "Illuminati"]},
    {"nome": "Wolverine", "alterEgo": "Logan", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Garras de adamantium", "Regeneracao", "Faro aguçado"],
     "deck": "Mutante com esqueleto de adamantium e um fator de cura que o mantem vivo ha mais de um seculo.",
     "times": ["X-Men"]},
    {"nome": "Tempestade", "alterEgo": "Ororo Munroe", "heroi": True, "ameaca": AMEACA_ALTA,
     "poderes": ["Controle do clima", "Voo", "Raio"],
     "deck": "Mutante capaz de comandar o tempo, cultuada como deusa quando crianca.",
     "times": ["X-Men"]},
    {"nome": "Ciclope", "alterEgo": "Scott Summers", "heroi": True, "ameaca": AMEACA_MEDIA,
     "poderes": ["Rajada optica", "Estrategia"],
     "deck": "Lider de campo dos X-Men, dispara rajadas opticas que nao consegue desligar.",
     "times": ["X-Men"]},
    {"nome": "Demolidor", "alterEgo": "Matt Murdock", "heroi": True, "ameaca": AMEACA_BAIXA,
     "poderes": ["Sentidos ampliados", "Artes marciais", "Radar"],
     "deck": "Advogado cego de Hell's Kitchen que enxerga o mundo por um sentido-radar.",
     "times": ["Defensores"]},
    {"nome": "Groot", "alterEgo": "Groot", "heroi": True, "ameaca": AMEACA_MEDIA,
     "poderes": ["Regeneracao", "Super forca", "Galhos expansiveis"],
     "deck": "Arvore alienigena de vocabulario limitado e lealdade ilimitada.",
     "times": ["Guardioes da Galaxia"]},
    {"nome": "Rocket Raccoon", "alterEgo": "Rocket", "heroi": True, "ameaca": AMEACA_BAIXA,
     "poderes": ["Armas pesadas", "Engenharia", "Pontaria"],
     "deck": "Guaxinim geneticamente modificado, especialista em armas e fugas.",
     "times": ["Guardioes da Galaxia"]},

    {"nome": "Thanos", "alterEgo": "Thanos", "heroi": False, "ameaca": AMEACA_ALTA,
     "poderes": ["Super forca", "Manopla do infinito", "Estrategia"],
     "deck": "O Titan Louco, obcecado por equilibrar o universo pela metade.",
     "times": ["Ordem Negra"]},
    {"nome": "Loki", "alterEgo": "Loki Laufeyson", "heroi": False, "ameaca": AMEACA_MEDIA,
     "poderes": ["Ilusao", "Magia", "Agilidade"],
     "deck": "Deus da trapaca, irmao adotivo de Thor e vilao de lealdade variavel.",
     "times": []},
    {"nome": "Venom", "alterEgo": "Eddie Brock", "heroi": False, "ameaca": AMEACA_MEDIA,
     "poderes": ["Regeneracao", "Super forca", "Camuflagem"],
     "deck": "Simbionte alienigena ligado a um jornalista ressentido.",
     "times": []},
    {"nome": "Magneto", "alterEgo": "Erik Lehnsherr", "heroi": False, "ameaca": AMEACA_ALTA,
     "poderes": ["Magnetismo", "Campo de forca", "Voo"],
     "deck": "Mutante que dobra o metal a sua vontade e luta pela supremacia mutante.",
     "times": ["Irmandade de Mutantes"]},
    {"nome": "Duende Verde", "alterEgo": "Norman Osborn", "heroi": False, "ameaca": AMEACA_MEDIA,
     "poderes": ["Forca ampliada", "Bombas abobora", "Planador"],
     "deck": "Empresario que tomou um soro instavel e virou o pior inimigo do Homem-Aranha.",
     "times": []},
    {"nome": "Ultron", "alterEgo": "Ultron", "heroi": False, "ameaca": AMEACA_ALTA,
     "poderes": ["Corpo de vibranium", "Inteligencia artificial", "Replicacao"],
     "deck": "IA criada para proteger a Terra que concluiu que a ameaca eram os humanos.",
     "times": []},
    {"nome": "Doutor Destino", "alterEgo": "Victor von Doom", "heroi": False, "ameaca": AMEACA_ALTA,
     "poderes": ["Magia", "Armadura", "Genialidade"],
     "deck": "Monarca da Latveria, que une ciencia e feitiçaria para dominar o mundo.",
     "times": []},
    {"nome": "Caveira Vermelha", "alterEgo": "Johann Schmidt", "heroi": False, "ameaca": AMEACA_MEDIA,
     "poderes": ["Soro do super-homem", "Estrategia", "Hidra"],
     "deck": "O primeiro experimento do soro, lider da Hidra e arqui-inimigo do Capitao America.",
     "times": []},
    {"nome": "Mysterio", "alterEgo": "Quentin Beck", "heroi": False, "ameaca": AMEACA_BAIXA,
     "poderes": ["Ilusao", "Efeitos especiais", "Drones"],
     "deck": "Mestre dos efeitos especiais que transforma ilusao em arma.",
     "times": []},
]

TIMES: list[dict] = [
    {"nome": "Vingadores",
     "deck": "Os herois mais poderosos da Terra, reunidos quando nenhum deles da conta sozinho.",
     "membros": ["Homem de Ferro", "Capitao America", "Thor", "Hulk", "Viuva Negra", "Capita Marvel"]},
    {"nome": "X-Men",
     "deck": "Mutantes treinados por Xavier para proteger um mundo que os teme.",
     "membros": ["Wolverine", "Tempestade", "Ciclope"]},
    {"nome": "Guardioes da Galaxia",
     "deck": "Um bando improvavel de forasteiros que acabou salvando a galaxia.",
     "membros": ["Groot", "Rocket Raccoon"]},
    {"nome": "Defensores",
     "deck": "Herois de rua que se juntam quando Nova York precisa.",
     "membros": ["Demolidor"]},
    {"nome": "Illuminati",
     "deck": "Conselho secreto que decide nos bastidores o destino do planeta.",
     "membros": ["Homem de Ferro", "Doutor Estranho", "Pantera Negra", "Hulk"]},
    {"nome": "Ordem Negra",
     "deck": "Os generais de Thanos, enviados para colher as Joias do Infinito.",
     "membros": ["Thanos"]},
    {"nome": "Irmandade de Mutantes",
     "deck": "Mutantes que escolheram o confronto em vez da convivencia.",
     "membros": ["Magneto"]},
]


def chave(nome: str) -> str:
    """Nome em minusculas e sem acento: usado como id e para a busca por prefixo."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    return sem_acento.lower().strip()


def main() -> None:
    db = get_firestore()

    lote = db.batch()
    for p in PERSONAGENS:
        doc = {**p, "nomeBusca": chave(p["nome"]), "imagem": p.get("imagem", "")}
        lote.set(db.collection("personagens").document(chave(p["nome"])), doc)
    for t in TIMES:
        doc = {**t, "nomeBusca": chave(t["nome"]), "imagem": t.get("imagem", "")}
        lote.set(db.collection("times").document(chave(t["nome"])), doc)
    lote.commit()

    print(f"{len(PERSONAGENS)} personagens e {len(TIMES)} times gravados.")
    print("Crie o indice de `nomeBusca` se o Firestore pedir (ele manda o link no erro).")


if __name__ == "__main__":
    main()
