"""Sprechblasen-Vorrat: Memes im englischen Original, Antworten in Variation.

Regel: Der berühmte Satz kommt möglichst im Original (z. B. „Live long and prosper.“),
die Antwort darauf ist deutsch und wechselt – nie zweimal dieselbe. `line()` wählt
deterministisch aus dem Vorrat; gemischt werden Lauf (`RUN_SEED`), Agent-Schlüssel und
Zeitschlitz, damit jeder Auftritt leicht anders wirkt. Neue Antworten einfach in die
passende Liste hängen; die Auswahl greift sie sofort auf.
"""

import random

# Pro Programmlauf neu gemischt, damit die Reihenfolge nicht immer gleich ist.
RUN_SEED = random.randrange(1 << 30)


def _h(*xs) -> float:
    """Stabiler Pseudo-Zufall 0…1 aus Zahlen und Zeichenketten (ohne Python-hash())."""
    h = 2166136261
    for x in xs:
        if isinstance(x, str):
            x = sum(ord(c) * (i + 1) for i, c in enumerate(x or "?"))
        h = ((h ^ (int(x) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def line(key: str, *parts):
    """Eine Zeile zum Vorratsnamen `key`. Ein fester Satz bleibt, eine Liste wird gewählt."""
    pool = QUIPS.get(key, key)
    if isinstance(pool, (list, tuple)):
        return pool[int(_h(key, *parts, RUN_SEED) * len(pool)) % len(pool)]
    return pool


# ------------------------------------------------------------------ Vorrat
QUIPS = {
    # Vulkanier-Gruß: Original, Antwort deutsch in Variation
    "spock_greeting": "Live long and prosper.",
    "spock_reply": [
        "Möge die Macht mit dir sein.",
        "Und möge der Merge gelingen.",
        "Möge die CI grün bleiben.",
        "Möge der Cache dich tragen.",
        "Möge dein Kontext nie überlaufen.",
        "Möge die Kompilierung gelingen.",
        "Möge kein Merge-Konflikt dich finden.",
        "Möge die Macht mit dir sein – und die Bandbreite.",
        "Möge der Server geduldig sein.",
        "Möge dein Prompt nie verpuffen.",
        "Möge das Modell immer antworten.",
        "Und möge die Latenz niedrig bleiben.",
    ],
    "spock_beam": [
        "Scotty, beam mich hoch!",
        "Beam me up, Scotty!",
        "Energie!",
        "Transporterraum, bitte!",
        "Hoch mit mir!",
        "Zwei zum Beamen!",
    ],

    # „This is fine“ – Original zuerst
    "fine": [
        "This is fine.",
        "Everything's fine.",
        "Alles in Ordnung.",
        "Es ist alles in Ordnung.",
        "Mir geht es gut.",
        "Kein Grund zur Sorge.",
    ],

    # Meme „6-7“
    "67": ["Six! Seven!", "Sechs! Sieben!", "6… 7!", "Six seven!"],
    "67_reply": [
        "Ich zähle nur Tokens.",
        "Ich zähle nur meine Tokens.",
        "Nur Tokens, keine Zahlen.",
        "Ich habe nur Tokens im Angebot.",
        "Tokens zählen, nicht Zahlen.",
        "Ich zähle lieber Tokens.",
    ],

    # Meme „Distracted Developer“
    "distracted": [
        "Äh… ich schau nur kurz.",
        "Ich schaue nur ganz kurz.",
        "Das war nur ein Context-Switch.",
        "Ich bin gleich wieder da.",
        "Nur ein Blick, versprochen.",
        "Das gehört zur Recherche.",
    ],

    # KI-Gegner
    "protest_reply": [
        "Ich mach nur meinen Job.",
        "Ich mache nur meine Arbeit.",
        "Ich bin nur ein Werkzeug.",
        "Ich wurde auch nur programmiert.",
        "Ich habe auch keine Wahl.",
        "Ich bin nur ein Modell.",
        "Beschwerde bitte an den Prompt.",
        "Ich folge nur meinen Anweisungen.",
        "Ich bin nicht die Richtige für die Wut.",
        "Fragt doch meine Trainingsdaten.",
    ],

    # Star Wars
    "vader": [
        "Ich bin dein Vater!",
        "Ich bin dein Vater… im Git-Log.",
        "Ich bin dein Vater – der Commit folgt.",
        "Ich bin dein Vater, Version 2.0.",
    ],
    "jedi": [
        "Neeein! Das ist ein Merge-Konflikt!",
        "Neeein! Das war ein Force-Push!",
        "Neeein! Der Branch ist detached!",
        "Neeein! Nicht schon wieder ein Rebase!",
    ],

    # Zombies
    "zombie": ["Hiiirn… Tokeeens…", "Hiiirn…", "Tokeeens… Hiiirn…", "Mehr… Kontext…"],
    "zombie_reply": [
        "Hirn gibt's hier nur als Cache!",
        "Kontext gibt's nur im Cache!",
        "Hirn ist gerade ausgelagert!",
        "Wir haben nur Embeddings!",
    ],

    # Rollen & Slapstick (0.8.3)
    "chaplin": [
        "Ein Tag wie jeder andere. Nur mit mehr Stolpern.",
        "Ich habe den Bug nicht gefunden – er mich.",
        "Nur ein Spaziergang. Mit Stock.",
        "Zeit für ein kleines Tänzchen.",
    ],
    "heist": [
        "Der Plan ist unmöglich. Genau mein Plan.",
        "Leise… die API schläft nie.",
        "Ich brauche keine Waffe. Nur einen gültigen Token.",
        "Zutritt nur mit gültigem Kontext.",
    ],
    "elon": [
        "To the moon! Äh… to the cache!",
        "Wir machen das voll autonom. Versprochen.",
        "Der Deploy ist in 3 Monaten. Safe.",
        "Erst die Rakete, dann die Tests.",
    ],
    "sam": [
        "AGI kommt. Und sie ist super lieb.",
        "Wir machen das langsam und sicher. Demnächst.",
        "Nur noch eine Skalierung, dann sind wir da.",
        "Ich habe eine neue Version. Sie ist besser.",
    ],
    "zuck": [
        "Ich bin kein Roboter. Wirklich.",
        "Willkommen im Metaversum. Es ist leer hier.",
        "Ich habe einen Helm. Du auch?",
        "Bitte lächeln. Für die Daten.",
    ],
    "trump": [
        "You're fired! Der ganze Stack.",
        "Das ist der beste Kontext. Alle sagen das.",
        "Wir machen eine Mauer. Gegen die Bugs.",
        "Ein sehr, sehr großer Deploy.",
    ],
    "youtube": [
        "Smash that like button!",
        "Abonniert den Kanal, sonst kompaktiert es!",
        "Was geht, Leute? Heute: Kontext!",
        "Like, Abo und Glocke – der Algorithmus will es.",
    ],
    "gamer": [
        "GG! Der Server hat mich betrogen!",
        "Lag! Das war eindeutig Lag!",
        "Ich habe gesmurfed. Äh, gesmurfed.",
        "Wer hat den Boss gepullt?!",
    ],

    # Herr der Token
    "gandalf": ["DU KANNST NICHT VORBEI!", "Du kannst nicht vorbei!", "DU KOMMST NICHT VORBEI!"],
    "gandalf_reply": [
        "Ich wollte nur kurz Kontext erweitern…",
        "Ich wollte nur den Kontext erweitern…",
        "Ich brauche nur ein paar Tokens mehr…",
        "Ich wollte nur kurz nachladen…",
    ],
}
