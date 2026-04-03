#!/usr/bin/env python3
"""Add no-markdown instruction to KAI prompt"""

with open("/app/server.py", "r") as f:
    content = f.read()

old = '"\\nKeine Floskeln. Kein \'Natuerlich!\', kein \'Gerne!\', kein \'Schoene Frage!\'."'
new = '''"\\nKeine Floskeln. Kein 'Natuerlich!', kein 'Gerne!', kein 'Schoene Frage!'."
        "\\nKein Markdown! Keine Sternchen, keine Aufzaehlungszeichen, kein Fettdruck. Schreib normalen Text wie in einer Chat-Nachricht."'''

if old in content:
    content = content.replace(old, new)
    with open("/app/server.py", "w") as f:
        f.write(content)
    print("OK: No-markdown instruction added")
else:
    print("ERROR: Target not found")
