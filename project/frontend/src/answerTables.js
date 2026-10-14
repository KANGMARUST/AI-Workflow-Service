function cells(line) {
  let value = line.trim();
  if (value.startsWith('|')) value = value.slice(1);
  if (value.endsWith('|') && !value.endsWith('\\|')) value = value.slice(0, -1);
  if (!value.includes('|')) return null;
  const result = [];
  let cell = '';
  for (let index = 0; index < value.length; index += 1) {
    if (value[index] === '\\' && value[index + 1] === '|') {
      cell += '|';
      index += 1;
    } else if (value[index] === '|') {
      result.push(cell.trim());
      cell = '';
    } else {
      cell += value[index];
    }
  }
  result.push(cell.trim());
  return result;
}

export function parseAnswerBlocks(answer) {
  const lines = answer.split(/\r?\n/);
  const blocks = [];
  let prose = [];
  const flush = () => {
    const text = prose.join('\n').trim();
    if (text) blocks.push({ type: 'text', text });
    prose = [];
  };

  for (let index = 0; index < lines.length;) {
    const headers = cells(lines[index]);
    const divider = index + 1 < lines.length ? cells(lines[index + 1]) : null;
    if (!headers || headers.length < 2 || !headers.every(Boolean) || !divider ||
        divider.length !== headers.length || !divider.every(cell => /^:?-{3,}:?$/.test(cell))) {
      prose.push(lines[index]);
      index += 1;
      continue;
    }
    const rows = [];
    let next = index + 2;
    while (next < lines.length) {
      const row = cells(lines[next]);
      if (!row || row.length !== headers.length) break;
      rows.push(row);
      next += 1;
    }
    if (!rows.length) {
      prose.push(lines[index]);
      index += 1;
      continue;
    }
    flush();
    blocks.push({ type: 'table', headers, rows });
    index = next;
  }
  flush();
  return blocks;
}
