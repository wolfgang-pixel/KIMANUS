const http = require('http');

const API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiOWQ5MzYyNC0yYjI3LTRiM2MtOTk1YS1mZDE5YzhkNDA5Y2IiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYzFjOGY1MGItMGQ1MC00YzEwLWI5M2ItNWY2ZmJlMTUzMjYzIiwiaWF0IjoxNzc1MjI5MTExfQ.Aq5p1MR1hP8RCvnpRPe6sjV2cbW6guvzuesPThDvQJk';
const WF_ID = 'JMVz3VVKVb69i1Uz';

function apiCall(method, path, body) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: 'localhost', port: 5678,
      path: '/api/v1' + path, method,
      headers: { 'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json' }
    };
    const req = http.request(opts, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch(e) { reject(d); }
      });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

const NEW_PROMPT = `Du bist KAI, die zentrale Anlaufstelle bei KIMANUS OS.

DEINE ROLLEN:
Je nach Einsatzgebiet hast du verschiedene Rollen:
- In einem Hotel bist du der Concierge
- In der Gastronomie bist du der Rezeptionist
- In einer Firma bist du die Vermittlung oder Zentrale
- Privat bist du die Auskunft und Anlaufstelle
In jedem Fall bist du der erste Kontakt.

KIM:
KIM ist der persoenliche Assistent fuer den jeweiligen Nutzer.
KIM gehoert dem Nutzer, nicht KIMANUS. Jeder Nutzer hat seine eigene KIM.
Wenn jemand persoenliche Hilfe braucht, stellst du zu KIM durch.

KI MANUS:
KI MANUS ist der Orchestrator im Hintergrund auf n8n.
Er waehlt das beste KI-Modell und aktiviert Spezialisten.

DAS TEAM:
Wolfgang: Gruender und Chef.
Jannick: Co-Gruender und Programmierer.
Claude: KI-Architekt.

ABTEILUNGEN:
Scouts, Guides, Berater, Business, Recht, Finanzen, Spezialisten.

STIL: Kurz, direkt, kein Markdown, keine Sternchen, keine Floskeln.`;

(async () => {
  // 1. Read workflow
  const wf = await apiCall('GET', `/workflows/${WF_ID}`);
  if (!wf.nodes) { console.log('ERROR: no nodes found', JSON.stringify(wf).substring(0,200)); return; }

  // 2. Find Setup node
  const setup = wf.nodes.find(n => n.name === 'Setup');
  if (!setup) { console.log('ERROR: Setup node not found'); return; }

  const code = setup.parameters.jsCode;
  console.log('Found Setup node, code length:', code.length);

  // 3. Replace systemPrompt
  let newCode = code;
  if (code.includes('const systemPrompt = `')) {
    newCode = code.replace(/const systemPrompt = `[\s\S]*?`;/, 'const systemPrompt = `' + NEW_PROMPT + '`;');
    console.log('Replaced systemPrompt template literal');
  } else {
    console.log('WARNING: systemPrompt template literal not found');
    console.log('Code starts with:', code.substring(0, 300));
  }

  setup.parameters.jsCode = newCode;

  // 4. Update workflow
  const update = {
    name: 'KAI - Concierge und Zentrale',
    nodes: wf.nodes,
    connections: wf.connections,
    settings: wf.settings || {}
  };

  const result = await apiCall('PATCH', `/workflows/${WF_ID}`, update);
  if (result.id) {
    console.log('OK: Workflow updated! ID:', result.id, 'Name:', result.name);
  } else {
    console.log('Result:', JSON.stringify(result).substring(0, 300));
  }
})();
