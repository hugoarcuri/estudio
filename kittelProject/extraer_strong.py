import fitz, json, re, gzip, os

pdf_path = os.path.join(os.path.dirname(__file__), "..", "Diccionario_Strong_de_Palabras_ATyNT.pdf")
output_path = os.path.join(os.path.dirname(__file__), "datos_strong.json.gz")

doc = fitz.open(pdf_path)

ENTRY_RE = re.compile(r'^(\d+)\.\s+(.+)')
PAGE_NUM_RE = re.compile(r'^\d+$')
PAGE_BRACKET_RE = re.compile(r'\[p\s+\d+[^\]]*\]')

HEB_RE = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
GRK_RE = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
WORD_RE = re.compile(r'([\u0590-\u05FF\uFB1D-\uFB4F\u0370-\u03FF\u1F00-\u1FFF]{2,}(?:\s*[\u0590-\u05FF\uFB1D-\uFB4F\u0370-\u03FF\u1F00-\u1FFF]+)*)')
TRANS_RE = re.compile(r'[^A-Za-z\u00C0-\u024F]*([A-Za-z\u00C0-\u024F]+(?:[\s-][A-Za-z\u00C0-\u024F]+)*)\s*;')
SPAN_SPLIT = re.compile(r'(:—|:–|:\u2014|\u2014)\s*')

def has_heb(s):
    return bool(HEB_RE.search(s))

def has_grk(s):
    return bool(GRK_RE.search(s))

def is_real_entry_line(line):
    m = ENTRY_RE.match(line)
    if not m:
        return None
    rest = m.group(2)
    if has_heb(rest) or has_grk(rest):
        return m
    return None

print("Extrayendo entradas de Strong...")
entries = []
current = None

for i in range(doc.page_count):
    page = doc[i]
    text = page.get_text()
    lines = text.split('\n')

    page_has_heb = has_heb(text)
    page_has_grk = has_grk(text)

    if page_has_heb and not page_has_grk:
        lang = 'H'
    elif page_has_grk and not page_has_heb:
        lang = 'G'
    else:
        lang = None

    for raw in lines:
        line = raw.strip()
        if not line or PAGE_NUM_RE.match(line):
            continue
        line = PAGE_BRACKET_RE.sub('', line).strip()
        if not line:
            continue

        m = is_real_entry_line(line)
        if m:
            if current:
                current['d'] = re.sub(r'\s+', ' ', current['d']).strip()
                if current['d']:
                    entries.append(current)

            num = int(m.group(1))
            rest = m.group(2).strip()
            current = {'n': num, 'l': lang or 'H', 'w': '', 't': '', 's': [], 'd': rest, 'p': i + 1}

            # Original word: first Hebrew/Greek block
            wm = WORD_RE.search(rest)
            if wm:
                current['w'] = wm.group(1).strip()

            # Transliteration: after original word, before ;
            after = rest
            if current['w']:
                p = rest.find(current['w']) + len(current['w'])
                after = rest[p:].strip()
            tm = TRANS_RE.match(after)
            if tm:
                current['t'] = tm.group(1).strip()

            # Spanish translations: after :—
            sp = SPAN_SPLIT.split(rest)
            if len(sp) >= 2:
                raw_s = sp[-1].strip()
                raw_s = re.sub(r'\s*(Comp\.|comp\.)\s*\d+.*', '', raw_s)
                raw_s = re.sub(r'\s*V[eé]ase\s*\d+.*', '', raw_s)
                parts = [x.strip().rstrip('.') for x in re.split(r'[,;]', raw_s) if x.strip() and len(x.strip()) > 1]
                if parts:
                    current['s'] = parts

        elif current:
            # Continuation line - extract spanish if not already found
            if not current['s']:
                sp = SPAN_SPLIT.split(line)
                if len(sp) >= 2:
                    raw_s = sp[-1].strip()
                    raw_s = re.sub(r'\s*(Comp\.|comp\.)\s*\d+.*', '', raw_s)
                    raw_s = re.sub(r'\s*V[eé]ase\s*\d+.*', '', raw_s)
                    parts = [x.strip().rstrip('.') for x in re.split(r'[,;]', raw_s) if x.strip() and len(x.strip()) > 1]
                    if parts:
                        current['s'] = parts
            current['d'] += ' ' + line

if current and current.get('d'):
    current['d'] = re.sub(r'\s+', ' ', current['d']).strip()
    if current['d']:
        entries.append(current)

doc.close()

print(f"  Entradas: {len(entries)}")
heb = [e for e in entries if e['l'] == 'H']
grk = [e for e in entries if e['l'] == 'G']
print(f"  Hebreo/Arameo: {len(heb)}   Griego: {len(grk)}")

# Filter: keep only entries with a non-empty word
# and skip Hebrew intro pages (pages 1-11)
entries = [e for e in entries if e['w'] and not (e['l'] == 'H' and e['p'] <= 11)]
# For Greek: find first page with real entries (has Greek word > 1 char)
greek_start = None
for e in entries:
    if e['l'] == 'G' and e['w'] and len(e['w']) > 1:
        greek_start = e['p']
        break
if greek_start:
    entries = [e for e in entries if not (e['l'] == 'G' and e['p'] < greek_start)]

data = [{'n': e['n'], 'l': e['l'], 'w': e['w'], 't': e['t'], 's': e['s'], 'd': e['d'], 'p': e['p']} for e in entries]

json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
with gzip.open(output_path, 'wt', encoding='utf-8') as f:
    f.write(json_str)

raw_mb = len(json_str) / 1024 / 1024
comp_mb = os.path.getsize(output_path) / 1024 / 1024
print(f"  Tamano: {raw_mb:.1f} MB -> comprimido: {comp_mb:.1f} MB")
print("Listo!")
