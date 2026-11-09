# Atacante de laboratorio: Nmap, Hydra y script propio (paramiko). Contexto de build: raíz del repo.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends hydra nmap ca-certificates \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir paramiko==3.4.1
WORKDIR /attack
COPY services/app/hp/tools/wordlist.py /attack/wordlist.py
COPY tools/attacker/attack.py /attack/attack.py
COPY tools/attacker/runner.py /attack/runner.py
# listas para Hydra
RUN python - <<'PY'
import random, wordlist
r = random.Random(1)
open('/attack/users.txt','w').write("\n".join(wordlist.USUARIOS)+"\n")
open('/attack/pass.txt','w').write("\n".join(wordlist.passwords(500, r))+"\n")
PY
ENTRYPOINT ["python", "/attack/attack.py"]
