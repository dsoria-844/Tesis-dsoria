"""Usuarios y contraseñas comunes de ataques de diccionario contra SSH/Telnet (uso solo en laboratorio)."""
from __future__ import annotations

import random

USUARIOS = ["root", "admin", "ubuntu", "test", "oracle", "pi", "user", "postgres", "git", "ftpuser",
            "guest", "support", "ec2-user", "debian", "centos", "www", "deploy", "jenkins"]

BASE = ["123456", "password", "admin", "12345678", "qwerty", "123456789", "12345", "1234", "111111",
        "1234567", "dragon", "123123", "baseball", "abc123", "football", "monkey", "letmein",
        "shadow", "master", "666666", "qwertyuiop", "123321", "mustang", "1234567890", "michael",
        "654321", "superman", "1qaz2wsx", "7777777", "121212", "000000", "qazwsx", "123qwe",
        "killer", "trustno1", "jordan", "jennifer", "zxcvbnm", "asdfgh", "hunter", "buster",
        "soccer", "harley", "batman", "andrew", "tigger", "sunshine", "iloveyou", "2000", "charlie",
        "robert", "thomas", "hockey", "ranger", "daniel", "starwars", "klaster", "112233", "george",
        "computer", "michelle", "jessica", "pepper", "1111", "zxcvbn", "555555", "11111111",
        "131313", "freedom", "777777", "pass", "maggie", "159753", "aaaaaa", "ginger", "princess",
        "joshua", "cheese", "amanda", "summer", "love", "ashley", "nicole", "chelsea", "biteme",
        "matthew", "access", "yankees", "987654321", "dallas", "austin", "thunder", "taylor",
        "matrix", "root", "toor", "raspberry", "ubnt", "default", "changeme", "support", "oracle"]


def passwords(n: int, rng: random.Random) -> list[str]:
    """n contraseñas distintas: la lista base y variaciones típicas (sufijos numéricos, mayúsculas)."""
    pool = list(BASE)
    sufijos = ["1", "12", "123", "!", "2024", "2025", "2026", "@123", "#1"]
    for b in BASE:
        for s in sufijos:
            pool.append(b + s)
            pool.append(b.capitalize() + s)
    rng.shuffle(pool)
    out, vistos = [], set()
    for p in pool:
        if p not in vistos:
            vistos.add(p)
            out.append(p)
        if len(out) >= n:
            return out
    while len(out) < n:  # si hace falta más, se agregan variantes numéricas
        p = f"{rng.choice(BASE)}{rng.randint(1000, 99999)}"
        if p not in vistos:
            vistos.add(p)
            out.append(p)
    return out


def pairs(n: int, rng: random.Random, usuarios: list[str] | None = None) -> list[tuple[str, str]]:
    """n pares (usuario, contraseña) distintos."""
    us = usuarios or USUARIOS
    pw = passwords(max(1, -(-n // len(us))) + 5, rng)
    todos = [(u, p) for p in pw for u in us]
    rng.shuffle(todos)
    return todos[:n]
