#!/usr/bin/env python3
"""Final fixes: KIM for any user, KAI flexible role"""

with open("/app/server.py", "r") as f:
    content = f.read()

# KIM ist fuer den Nutzer, nicht nur Wolfgang
content = content.replace(
    "KIM: Persoenliche Assistentin fuer den Nutzer. Kennt Vorlieben, Familie, Termine. Wird durchgestellt.",
    "KIM: Persoenlicher Assistent fuer den jeweiligen Nutzer. Kennt Vorlieben und Termine. Wird durchgestellt."
)

# KAI flexible Rolle
content = content.replace(
    "KAI (du): Concierge, Rezeption, Vermittlung, Auskunft. Erster Kontakt fuer alle.",
    "KAI (du): Deine Rolle wechselt je nach Einsatz: Concierge (Hotel), Rezeptionist (Gastro), Vermittlung (Firma), Auskunft (Privat). Du bist immer der erste Kontakt."
)

# KI MANUS erwaehnen
old_ki_personal = '"\\nKI-PERSONAL (virtuelle Mitarbeiter):"'
new_ki_personal = '"\\nKI-PERSONAL:"'
content = content.replace(old_ki_personal, new_ki_personal)

with open("/app/server.py", "w") as f:
    f.write(content)
print("OK: Final fixes applied")
