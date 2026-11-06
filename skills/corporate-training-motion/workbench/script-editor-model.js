// Pure transcript operations shared by the editor and its regression checks.
export function paragraphs(text) {
  const result = []; let current;
  const finish = () => { if (current) result.push({...current,text:text.slice(current.start,current.end)}); current = undefined; };
  for (const match of text.matchAll(/[^\n]+/g)) {
    if (!match[0].trim() || /^\s*#{1,6}\s/.test(match[0])) { finish(); continue; }
    if (current && /\n\s*\n/.test(text.slice(current.end,match.index))) finish();
    if (!current) current = {start:match.index,end:match.index+match[0].length};
    else current.end = match.index+match[0].length;
  }
  finish();
  return result;
}
export function paragraphAt(text, caret) {
  const items = paragraphs(text);
  return items.find(p => p.start <= caret && caret <= p.end) || items.find(p => p.start > caret) || items.at(-1);
}
export function replaceSelection(text, selection, replacement) {
  if (text !== selection.snapshot || text.slice(selection.start, selection.end) !== selection.text) {
    throw Error('逐字稿在生成建议期间已改变，请重新选择后生成；建议仍保留在下方。');
  }
  return text.slice(0, selection.start) + replacement + text.slice(selection.end);
}
const normal = value => value.normalize('NFKC').replace(/[\s\p{P}\p{S}]/gu, '');
export function previewDocument(document, original, edited, caret = 0) {
  const doc = structuredClone(document), before = paragraphs(original), after = paragraphs(edited);
  const selected = paragraphAt(edited, caret);
  let sceneId, mapped = 0;
  // A structural rewrite needs fresh scene bindings from production, never a guessed paragraph offset.
  if (before.length !== after.length) return {document: doc, mapped, selected, needsBinding: true};
  if (after.some((p,i) => before.some((old,j) => i !== j && normal(p.text) === normal(old.text) && normal(p.text) !== normal(before[i].text)))) {
    return {document: doc, mapped, selected, needsBinding: true};
  }
  for (let i = 0; i < before.length; i++) {
    const old = before[i], next = after[i], normalized = normal(old.text);
    if (!normalized) continue;
    if (before.filter(p => normal(p.text) === normalized).length !== 1) continue;
    const cues = (doc.captions || []).filter(c => {
      const n = normal(c.text);
      return n && normalized.includes(n) && before.filter(p => normal(p.text).includes(n)).length === 1;
    });
    const fields = (doc.fields || []).filter(f => normal(f.text || '') === normalized);
    if (selected?.start === next.start) sceneId = cues[0]?.sceneId || fields[0]?.sceneId;
    if (old.text === next.text) continue;
    for (const field of fields) { field.text = next.text; mapped++; }
    if (cues.length) {
      const value = next.text.replace(/[\p{P}\r\n]/gu, '').trim();
      const weights = cues.map(c => Math.max(1, [...c.text].length)), total = weights.reduce((a,b) => a+b,0);
      const chars = [...value]; let position = 0;
      cues.forEach((cue,j) => { const end = j === cues.length - 1 ? chars.length : Math.round(chars.length * weights.slice(0,j+1).reduce((a,b)=>a+b,0) / total); cue.text = chars.slice(position,end).join(''); position = end; });
      mapped += cues.length;
    }
  }
  const scene = doc.scenes?.find(s => s.id === sceneId);
  return {document: doc, mapped, selected, scene, needsBinding: edited !== original && !mapped};
}
