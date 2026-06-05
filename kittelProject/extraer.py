import fitz
import json
import re
import gzip
import os

pdf_path = os.path.join(os.path.dirname(__file__), "Diccionario TeologicoDelNT- Kittel.pdf")
output_path = os.path.join(os.path.dirname(__file__), "datos.json.gz")

doc = fitz.open(pdf_path)

GREEK_RE = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
HEADER_RE = re.compile(r'^[\u0370-\u03FF\u1F00-\u1FFF].*?\[[^\]]+\]')
BRACKET_RE = re.compile(r'\[([^\]]+)\]')
PAGE_NUM_RE = re.compile(r'^\d+\s*$')
PAGE_BREAK_RE = re.compile(r'\[p\s+\d+[^\]]*\]')

def extract_lines(doc, start_page=8, end_page=1071):
    items = []
    for i in range(start_page, end_page):
        page = doc[i]
        text = page.get_text()
        for line in text.split('\n'):
            s = line.strip()
            if s and not PAGE_NUM_RE.match(s):
                s = PAGE_BREAK_RE.sub('', s).strip()
                if s:
                    items.append((i + 1, s))
    return items

def is_header(line):
    return bool(HEADER_RE.match(line))

def is_continuation(line):
    return bool(GREEK_RE.match(line) and BRACKET_RE.search(line) and len(line) < 100)

def parse_spanish(line):
    words = []
    for m in BRACKET_RE.findall(line):
        for p in m.split(','):
            p = p.strip()
            if p and len(p) > 1:
                words.append(p)
    return words

def parse_greek(line):
    parts = re.split(r'\[[^\]]+\]', line)
    greek = []
    for part in parts:
        part = part.strip().rstrip(',').strip()
        if part and GREEK_RE.search(part):
            greek.append(part)
    return greek

print("Extrayendo texto...")
items = extract_lines(doc)
print(f"  Líneas: {len(items)}")

entries = []
current = None
header_lines = []
entry_pages = set()

for page, line in items:
    if is_header(line):
        if current:
            text = ' '.join(current['tl'])
            text = re.sub(r'\s+', ' ', text).strip()
            current['t'] = text
            if text:
                entries.append(current)
            current = None
            header_lines = []
            entry_pages = set()

        header_lines.append(line)
        h = ' '.join(header_lines)
        entry_pages.add(page)
        current = {
            'g': parse_greek(h),
            'e': list(dict.fromkeys(parse_spanish(h))),
            'ps': page,
            'tl': []
        }
    elif current:
        entry_pages.add(page)
        if is_continuation(line):
            header_lines.append(line)
            h = ' '.join(header_lines)
            current['g'] = parse_greek(h)
            current['e'] = list(dict.fromkeys(parse_spanish(h)))
        else:
            current['tl'].append(line)

if current:
    text = ' '.join(current['tl'])
    text = re.sub(r'\s+', ' ', text).strip()
    current['t'] = text
    if text:
        entries.append(current)

print(f"  Entradas: {len(entries)}")
print(f"  Términos griegos: {sum(len(e['g']) for e in entries)}")
print(f"  Traducciones: {sum(len(e['e']) for e in entries)}")

data = [{
    'g': ', '.join(e['g']),
    'e': e['e'],
    't': e['t'],
    'p': e['ps']
} for e in entries]

json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with gzip.open(output_path, 'wt', encoding='utf-8') as f:
    f.write(json_str)

raw = len(json_str)
comp = os.path.getsize(output_path)
print(f"\nTamaño: {raw/1024/1024:.1f} MB → comprimido: {comp/1024/1024:.1f} MB")

doc.close()
print("¡Listo!")
