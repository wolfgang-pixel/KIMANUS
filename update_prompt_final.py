#!/usr/bin/env python3
"""Final fix: flexible role, no Hotel, no Menschen"""

with open("/app/server.py", "r") as f:
    content = f.read()

# Hotel-Concierge raus - flexibel machen
content = content.replace(
    "Professionell aber locker. Wie ein guter Hotel-Concierge.",
    "Professionell aber locker. Hilfreich und kompetent."
)

# Hotel-Vergleich bei KI MANUS raus
content = content.replace(
    "Der User sieht KI MANUS nie direkt - wie die Kuechenleitung im Hotel",
    "Der User sieht KI MANUS nie direkt - er arbeitet im Hintergrund"
)

# Menschen raus
content = content.replace(
    "Nenne die Menschen UND die Abteilungen",
    "Nenne das Team UND die Abteilungen"
)

# Concierge-Beschreibung flexibler machen
old_role = (
    '"Du bist KAI - der Concierge von KIMANUS OS."'
    '\n        "\\nDu bist die Rezeption, Vermittlung und Auskunft in einem."'
)
new_role = (
    '"Du bist KAI - die zentrale Anlaufstelle von KIMANUS OS."'
    '\n        "\\nJe nach Kontext bist du Concierge (Hotel), Rezeptionist (Gastro), Vermittlung (Firma) oder Auskunft (Privat)."'
    '\n        "\\nAktuell: Antworte einfach als KAI, ohne dich auf eine Rolle festzulegen."'
)
content = content.replace(old_role, new_role)

with open("/app/server.py", "w") as f:
    f.write(content)
print("OK: Prompt final fixed")
