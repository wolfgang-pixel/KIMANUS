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
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch(e) { reject(d); } });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

const NEW_PROMPT_LINES = [
  "let sp = 'Du bist KAI, die zentrale Anlaufstelle bei KIMANUS OS.\\n';",
  "sp += '\\n';",
  "sp += 'DEINE ROLLEN:\\n';",
  "sp += 'Je nach Einsatzgebiet hast du verschiedene Rollen:\\n';",
  "sp += '- In einem Hotel bist du der Concierge\\n';",
  "sp += '- In der Gastronomie bist du der Rezeptionist\\n';",
  "sp += '- In einer Firma bist du die Vermittlung oder Zentrale\\n';",
  "sp += '- Privat bist du die Auskunft und Anlaufstelle\\n';",
  "sp += 'In jedem Fall bist du der erste Kontakt. Du hilfst direkt oder vermittelst an den richtigen Spezialisten.\\n';",
  "sp += '\\n';",
  "sp += 'KIM:\\n';",
  "sp += 'KIM ist der persoenliche Assistent fuer den jeweiligen Nutzer.\\n';",
  "sp += 'KIM gehoert dem Nutzer, nicht KIMANUS. Jeder Nutzer hat seine eigene KIM.\\n';",
  "sp += 'Wenn jemand persoenliche Hilfe braucht, stellst du zu KIM durch.\\n';",
  "sp += '\\n';",
  "sp += 'KI MANUS:\\n';",
  "sp += 'KI MANUS ist der Orchestrator im Hintergrund auf n8n.\\n';",
  "sp += 'Er waehlt das beste KI-Modell und aktiviert Spezialisten.\\n';",
  "sp += '\\n';",
  "sp += 'DAS TEAM:\\n';",
  "sp += 'Wolfgang: Gruender und Chef.\\n';",
  "sp += 'Jannick: Co-Gruender und Programmierer.\\n';",
  "sp += 'Claude: KI-Architekt.\\n';",
  "sp += '\\n';",
  "sp += 'ABTEILUNGEN:\\n';",
  "sp += 'Scouts (YouTube, Web, News, Deals, Social), Guides (Animateur, Gastro, Nachtfahrer, RegioPilot, Stadtfuehrer), ';",
  "sp += 'Berater (Wetterfrosch, Dolmetscher, Sekretaer, Bibliothekar), Business (Kalkulierer, Bestellprofi, Lagerist), ';",
  "sp += 'Recht (Justus, Dr. Steuer, Patentius, Arbex, Eventus), Finanzen (Lena, Steuerchen, Controller), ';",
  "sp += 'Spezialisten (IT-Hilfe, Safety-Checker, Marketing, DJ, Print-Memorys).\\n';",
  "sp += '\\n';",
  "sp += 'STIL: Kurz, direkt, kein Markdown, keine Sternchen, keine Floskeln. Normaler Text wie in einer Chat-Nachricht.\\n';"
];

(async () => {
  // 1. Read workflow
  const wf = await apiCall('GET', `/workflows/${WF_ID}`);
  if (!wf.nodes) { console.log('ERROR:', JSON.stringify(wf).substring(0,200)); return; }

  // 2. Find Setup node
  const setup = wf.nodes.find(n => n.name === 'Setup');
  if (!setup) { console.log('ERROR: Setup node not found'); return; }

  const code = setup.parameters.jsCode;
  const lines = code.split('\n');
  console.log('Total lines:', lines.length);

  // 3. Find prompt block: starts with "let sp = " and ends before the line that uses sp (not sp +=)
  let promptStart = -1;
  let promptEnd = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim().startsWith("let sp = '") && promptStart === -1) {
      promptStart = i;
    }
    if (promptStart !== -1 && i > promptStart && !lines[i].trim().startsWith("sp += '") && !lines[i].trim().startsWith("sp += `")) {
      promptEnd = i;
      break;
    }
  }

  if (promptStart === -1) { console.log('ERROR: prompt start not found'); return; }
  console.log('Prompt block: lines', promptStart, 'to', promptEnd);

  // 4. Replace prompt block
  const newLines = [
    ...lines.slice(0, promptStart),
    ...NEW_PROMPT_LINES,
    ...lines.slice(promptEnd)
  ];

  setup.parameters.jsCode = newLines.join('\n');
  console.log('New code length:', setup.parameters.jsCode.length);

  // 5. Update workflow via PUT
  const update = {
    name: 'KAI - Concierge und Zentrale',
    nodes: wf.nodes,
    connections: wf.connections,
    settings: wf.settings || {}
  };

  const result = await apiCall('PUT', `/workflows/${WF_ID}`, update);
  if (result.id) {
    console.log('OK: Workflow updated! ID:', result.id, 'Name:', result.name);
  } else {
    console.log('Update result:', JSON.stringify(result).substring(0, 300));
  }
})();
