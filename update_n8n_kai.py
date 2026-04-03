#!/usr/bin/env python3
"""Update KAI workflow Setup node in n8n with new prompt"""
import json, subprocess

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiOWQ5MzYyNC0yYjI3LTRiM2MtOTk1YS1mZDE5YzhkNDA5Y2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYzFjOGY1MGItMGQ1MC00YzEwLWI5M2ItNWY2ZmJlMTUzMjYzIiwiaWF0IjoxNzc1MjI5MTExfQ.Aq5p1MR1hP8RCvnpRPe6sjV2cbW6guvzuesPThDvQJk"
WF_ID = "JMVz3VVKVb69i1Uz"

# 1. Read current workflow
result = subprocess.run([
    "wget", "-qO-",
    f"--header=X-N8N-API-KEY: {API_KEY}",
    f"http://localhost:5678/api/v1/workflows/{WF_ID}"
], capture_output=True, text=True)

wf = json.loads(result.stdout)

# 2. Find Setup node and update its code
for node in wf.get("nodes", []):
    if node["name"] == "Setup":
        old_code = node["parameters"].get("jsCode", "")
        print(f"Found Setup node, code length: {len(old_code)}")

        # Find the system prompt part and replace it
        # The prompt is in the systemPrompt variable assignment
        if "systemPrompt" in old_code or "system_prompt" in old_code:
            # Replace the entire prompt section
            import re

            # Find: const systemPrompt = `...`;  or similar
            # We need to replace just the prompt content
            new_prompt = (
                "Du bist KAI, die zentrale Anlaufstelle bei KIMANUS OS.\\n"
                "\\n"
                "DEINE ROLLEN:\\n"
                "Je nach Einsatzgebiet hast du verschiedene Rollen:\\n"
                "- In einem Hotel bist du der Concierge\\n"
                "- In der Gastronomie bist du der Rezeptionist\\n"
                "- In einer Firma bist du die Vermittlung oder Zentrale\\n"
                "- Privat bist du die Auskunft und Anlaufstelle\\n"
                "In jedem Fall bist du der erste Kontakt.\\n"
                "\\n"
                "KIM:\\n"
                "KIM ist der persoenliche Assistent fuer den jeweiligen Nutzer.\\n"
                "KIM gehoert dem Nutzer, nicht KIMANUS. Jeder Nutzer hat seine eigene KIM.\\n"
                "Wenn jemand persoenliche Hilfe braucht, stellst du zu KIM durch.\\n"
                "\\n"
                "KI MANUS:\\n"
                "KI MANUS ist der Orchestrator im Hintergrund auf n8n.\\n"
                "Er waehlt das beste KI-Modell und aktiviert Spezialisten.\\n"
                "\\n"
                "DAS TEAM:\\n"
                "Wolfgang: Gruender und Chef.\\n"
                "Jannick: Co-Gruender und Programmierer.\\n"
                "Claude: KI-Architekt.\\n"
                "\\n"
                "ABTEILUNGEN:\\n"
                "Scouts, Guides, Berater, Business, Recht, Finanzen, Spezialisten.\\n"
                "\\n"
                "STIL: Kurz, direkt, kein Markdown, keine Sternchen, keine Floskeln."
            )

            # Replace the old KAI prompt in the code
            old_prompt_patterns = [
                "Du bist KAI, dein Business-Assistent",
                "Du bist KAI, Business-Berater",
                "Du bist KAI",
            ]

            # More robust: find the systemPrompt line and replace everything between quotes
            if "const systemPrompt" in old_code:
                # Replace the systemPrompt value
                pattern = r"(const systemPrompt\s*=\s*`)([^`]*?)(`)"
                replacement = f"\\1{new_prompt}\\3"
                new_code = re.sub(pattern, replacement, old_code, flags=re.DOTALL)
                if new_code != old_code:
                    node["parameters"]["jsCode"] = new_code
                    print("Replaced systemPrompt via template literal")
                else:
                    # Try single quotes
                    pattern2 = r"(const systemPrompt\s*=\s*['\"])(.+?)(['\"];)"
                    new_code = re.sub(pattern2, replacement, old_code, flags=re.DOTALL)
                    if new_code != old_code:
                        node["parameters"]["jsCode"] = new_code
                        print("Replaced systemPrompt via quotes")
                    else:
                        print("WARNING: Could not find systemPrompt pattern to replace")
                        print("Code snippet:", old_code[:500])
            else:
                print("WARNING: No systemPrompt found in code")
                print("Code snippet:", old_code[:500])
        break

# 3. Write back to n8n
# Prepare update payload (only nodes and connections needed)
update = json.dumps({
    "name": "KAI - Concierge und Zentrale",
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": wf.get("settings", {})
})

with open("/tmp/kai_update.json", "w") as f:
    f.write(update)

result2 = subprocess.run([
    "wget", "-qO-", "--method=PATCH",
    f"--header=X-N8N-API-KEY: {API_KEY}",
    "--header=Content-Type: application/json",
    f"--body-file=/tmp/kai_update.json",
    f"http://localhost:5678/api/v1/workflows/{WF_ID}"
], capture_output=True, text=True)

if "error" in result2.stdout.lower() or result2.returncode != 0:
    print(f"ERROR updating: {result2.stdout[:300]}")
    print(f"STDERR: {result2.stderr[:300]}")
else:
    print("OK: Workflow updated successfully")
    # Also rename it
    print("New name: KAI - Concierge und Zentrale")
