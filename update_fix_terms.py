#!/usr/bin/env python3
"""Fix terms in KAI prompt: no Visionaer, no Menschen"""

with open("/app/server.py", "r") as f:
    content = f.read()

# Visionaer raus
content = content.replace(
    "Wolfgang: Gruender und Visionaer. Dein Chef. Kein Programmierer, aber der Kopf hinter allem.",
    "Wolfgang: Gruender und Chef. Hat die Idee und den Plan. Kein Programmierer."
)

# Menschen -> Das Team
content = content.replace(
    "MENSCHEN (das echte Team):",
    "DAS TEAM:"
)

# WICHTIG Satz anpassen
content = content.replace(
    "WICHTIG: Wolfgang und Jannick sind MENSCHEN, keine KI. Alle anderen sind KI-Mitarbeiter.",
    "WICHTIG: Wolfgang und Jannick sind die Gruender. Alle anderen sind KI-Mitarbeiter."
)

with open("/app/server.py", "w") as f:
    f.write(content)
print("OK: Terms fixed")
