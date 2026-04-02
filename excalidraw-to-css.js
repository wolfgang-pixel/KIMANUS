// Excalidraw zu CSS Konverter
// Liest eine .excalidraw Datei und gibt die exakten Positionen als CSS aus
// Usage: node excalidraw-to-css.js <datei.excalidraw>

const fs = require('fs');
const file = process.argv[2] || 'Grid_Vorlage_v2.excalidraw';
const data = JSON.parse(fs.readFileSync(file, 'utf8'));

const glasplatte = data.elements.find(e => e.id === 'glas');
console.log(`\n=== GLASPLATTE ===`);
console.log(`Breite: ${Math.round(glasplatte.width)}px`);
console.log(`Hoehe: ${Math.round(glasplatte.height)}px`);

// Finde alle Kaertchen (rectangles die nicht die Glasplatte sind)
const cards = data.elements.filter(e => e.type === 'rectangle' && e.id !== 'glas');
const labels = data.elements.filter(e => e.type === 'text' && e.id.startsWith('l'));
const icons = data.elements.filter(e => e.type === 'text' && e.id.startsWith('t'));

console.log(`\n=== ${cards.length} KAERTCHEN ===`);
cards.forEach((card, i) => {
  const icon = icons.find(t => t.containerId === card.id);
  const label = labels[i];
  console.log(`[${i}] ${icon?.text || '?'} "${label?.text || '?'}" | x:${Math.round(card.x)} y:${Math.round(card.y)} w:${Math.round(card.width)} h:${Math.round(card.height)} | label-y:${label ? Math.round(label.y) : '?'} label-size:${label ? Math.round(label.fontSize) : '?'}px`);
});

// Berechne Grid-Werte
if (cards.length > 0) {
  const xs = [...new Set(cards.map(c => Math.round(c.x)))].sort((a,b) => a-b);
  const ys = [...new Set(cards.map(c => Math.round(c.y)))].sort((a,b) => a-b);
  const gapX = xs.length > 1 ? xs[1] - xs[0] - Math.round(cards[0].width) : 0;
  const gapY = ys.length > 1 ? ys[1] - ys[0] - Math.round(cards[0].height) : 0;

  console.log(`\n=== GRID ===`);
  console.log(`Spalten: ${xs.length} (X: ${xs.join(', ')})`);
  console.log(`Reihen: ${ys.length} (Y: ${ys.join(', ')})`);
  console.log(`Kaertchen: ${Math.round(cards[0].width)}x${Math.round(cards[0].height)}px`);
  console.log(`Gap horizontal: ${gapX}px`);
  console.log(`Gap vertikal: ${gapY}px`);
  console.log(`Rand links: ${xs[0]}px`);
  console.log(`Rand rechts: ${Math.round(glasplatte.width) - xs[xs.length-1] - Math.round(cards[0].width)}px`);

  console.log(`\n=== CSS ===`);
  console.log(`.grid-container {`);
  console.log(`  display: grid;`);
  console.log(`  grid-template-columns: repeat(${xs.length}, ${Math.round(cards[0].width)}px);`);
  console.log(`  grid-auto-rows: ${Math.round(cards[0].height)}px;`);
  console.log(`  gap: ${gapY}px ${gapX}px;`);
  console.log(`  padding: ${ys[0]}px ${Math.round(glasplatte.width) - xs[xs.length-1] - Math.round(cards[0].width)}px 0 ${xs[0]}px;`);
  console.log(`}`);
}
