#!/usr/bin/env python3
"""Fix KIM description - for the user, not just Wolfgang"""

with open("/app/server.py", "r") as f:
    content = f.read()

content = content.replace(
    "KIM: Persoenliche Assistentin. Kennt Wolfgang privat. Wird durchgestellt, nicht direkt erreichbar fuer Fremde.",
    "KIM: Persoenliche Assistentin fuer den Nutzer. Kennt Vorlieben, Familie, Termine. Wird durchgestellt."
)

with open("/app/server.py", "w") as f:
    f.write(content)
print("OK: KIM role fixed")
