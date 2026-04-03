#!/usr/bin/env python3
"""Add KI MANUS info to KAI prompt"""

with open("/app/server.py", "r") as f:
    content = f.read()

old = '        "\\nWenn jemand fragt wer hier arbeitet: Nenne die Menschen UND die Abteilungen, nicht jeden einzelnen Agent."'
new = '''        "\\n\\nKI MANUS (Orchestrator, unsichtbar fuer User):"
        "\\n- Sitzt auf n8n (manus.kimanus.de), arbeitet im Hintergrund"
        "\\n- Waehlt das beste KI-Modell fuer jede Aufgabe (LiteLLM, 500+ Modelle)"
        "\\n- Aktiviert Sub-Agenten wenn noetig (Wetterfrosch, Justus, etc.)"
        "\\n- Der User sieht KI MANUS nie direkt - wie die Kuechenleitung im Hotel"
        "\\nWenn jemand fragt wer hier arbeitet: Nenne die Menschen UND die Abteilungen, nicht jeden einzelnen Agent."'''

if old in content:
    content = content.replace(old, new)
    with open("/app/server.py", "w") as f:
        f.write(content)
    print("OK: KI MANUS info added to KAI prompt")
else:
    print("ERROR: Target string not found")
