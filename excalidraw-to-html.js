// Excalidraw zu HTML Konverter v2
// Liest .excalidraw und erzeugt HTML mit Prozent-Positionierung
// Usage: node excalidraw-to-html.js <datei.excalidraw>

const fs = require('fs');
const file = process.argv[2];
if (!file) { console.log('Usage: node excalidraw-to-html.js <datei.excalidraw>'); process.exit(1); }

const data = JSON.parse(fs.readFileSync(file, 'utf8'));
const glas = data.elements.find(e => e.id === 'glas');
const W = glas.width;
const H = glas.height;

console.log(`Glasplatte: ${W}x${H}px\n`);

// Alle Rechtecke (ausser Glasplatte) = Kaertchen
const cards = data.elements.filter(e => e.type === 'rectangle' && e.id !== 'glas' && !e.isDeleted);
// Alle Texte mit containerId = Icons (in Kaertchen)
const icons = data.elements.filter(e => e.type === 'text' && e.containerId && !e.isDeleted);
// Alle Texte ohne containerId die mit 'l' starten = Labels
const labels = data.elements.filter(e => e.type === 'text' && !e.containerId && e.id && e.id.startsWith('l') && !e.isDeleted);
// Header
const header = data.elements.find(e => e.type === 'text' && e.id === 'hdr' && !e.isDeleted);

console.log(`Gefunden: ${cards.length} Kaertchen, ${icons.length} Icons, ${labels.length} Labels\n`);

// Header in Prozent
if (header) {
  const hx = ((header.x / W) * 100).toFixed(1);
  const hy = ((header.y / H) * 100).toFixed(1);
  const hfs = ((header.fontSize / H) * 100).toFixed(1);
  console.log(`Header "${header.text}": left:${hx}% top:${hy}% fontSize:${hfs}%`);
}

// Kaertchen in Prozent
console.log('\n--- KAERTCHEN (Prozent von Glasplatte) ---');
cards.forEach((card, i) => {
  const icon = icons.find(t => t.containerId === card.id);
  // Label finden: naechster Label-Text unterhalb des Kaertchens
  const cardBottom = card.y + card.height;
  const label = labels.find(l => Math.abs(l.x - card.x) < 30 && l.y > cardBottom - 5 && l.y < cardBottom + 50);

  const left = ((card.x / W) * 100).toFixed(1);
  const top = ((card.y / H) * 100).toFixed(1);
  const w = ((card.width / W) * 100).toFixed(1);
  const h = ((card.height / H) * 100).toFixed(1);
  const labelTop = label ? (((label.y) / H) * 100).toFixed(1) : '?';
  const labelFs = label ? ((label.fontSize / W) * 100).toFixed(1) : '?';

  console.log(`[${i}] ${icon?.text||'?'} "${label?.text||'?'}" | left:${left}% top:${top}% w:${w}% h:${h}% | label-top:${labelTop}% label-fs:${labelFs}%`);
});

// HTML Output
console.log('\n--- HTML (kopieren in buildBackCards) ---');
let html = '';
if (header) {
  const hx = ((header.x / W) * 100).toFixed(1);
  const hy = ((header.y / H) * 100).toFixed(1);
  const hfs = Math.round(header.fontSize);
  html += `<div style="position:absolute;left:${hx}%;top:${hy}%;font-size:${hfs}px;font-weight:700;color:rgba(255,255,255,0.45);letter-spacing:3px;text-transform:uppercase">${header.text}</div>\n`;
}

cards.forEach((card, i) => {
  const icon = icons.find(t => t.containerId === card.id);
  const cardBottom = card.y + card.height;
  const label = labels.find(l => Math.abs(l.x - card.x) < 30 && l.y > cardBottom - 5 && l.y < cardBottom + 50);

  const left = ((card.x / W) * 100).toFixed(1);
  const top = ((card.y / H) * 100).toFixed(1);
  const w = ((card.width / W) * 100).toFixed(1);
  const h = ((card.height / H) * 100).toFixed(1);
  const labelTop = label ? (((label.y) / H) * 100).toFixed(1) : (((card.y + card.height + 2) / H) * 100).toFixed(1);

  html += `<div style="position:absolute;left:${left}%;top:${top}%;width:${w}%;height:${h}%;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:22px;cursor:pointer">${icon?.text||''}</div>\n`;
  html += `<div style="position:absolute;left:${left}%;top:${labelTop}%;width:${w}%;text-align:center;font-size:11px;font-weight:600;color:rgba(255,255,255,0.4)">${label?.text||''}</div>\n`;
});

console.log(html);
