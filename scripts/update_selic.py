#!/usr/bin/env python3
from __future__ import annotations
import json, re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

UA = 'Mozilla/5.0'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dados' / 'selic-rfb.json'


def fetch(url: str) -> str:
    req = Request(url, headers={'User-Agent': UA})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='ignore')


def parse_marcca(html: str) -> dict:
    taxas = {}
    for m in re.finditer(r'<tr[^>]*>\s*(.*?)</tr>', html, flags=re.I | re.S):
        row = m.group(1)
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, flags=re.I | re.S)
        if len(cells) < 3:
            continue
        plain = [re.sub(r'<[^>]+>', ' ', c) for c in cells]
        plain = [' '.join(c.replace('&nbsp;', ' ').split()) for c in plain]
        if not re.fullmatch(r'\d{4}', plain[0].strip()):
            continue
        ano = int(plain[0].strip())
        if not (1995 <= ano <= 2035):
            continue
        for idx, val in enumerate(plain[1:13], start=1):
            bruto = val.replace('%', '').strip()
            if bruto in {'', '-', 'x', 'X', '×'}:
                continue
            bruto = bruto.replace('.', '').replace(',', '.')
            try:
                taxas[f'{ano}-{idx:02d}'] = float(bruto)
            except ValueError:
                pass
    if not taxas:
        raise RuntimeError('Não foi possível extrair a tabela histórica da Marcca')
    return taxas


def parse_sicalc(html: str):
    texto = re.sub(r'<[^>]+>', ' ', html)
    texto = ' '.join(texto.split())
    p1 = re.search(r'Última\s+Selic\s+disponível\s*\(?\s*(\d{2}/\d{4})\s*\)?\s*([0-9]+[\.,][0-9]+)', texto, flags=re.I)
    p2 = re.search(r'Percentual\s+em\s*(\d{2}/\d{4})\s*([0-9]+[\.,][0-9]+)', texto, flags=re.I)
    if not (p1 and p2):
        raise RuntimeError('Não foi possível extrair os percentuais do Sicalc')
    return (
        p1.group(1), float(p1.group(2).replace('.', '').replace(',', '.')),
        p2.group(1), float(p2.group(2).replace('.', '').replace(',', '.')),
    )


def load_existing():
    if OUT.exists():
        return json.loads(OUT.read_text(encoding='utf-8'))
    return {'taxas': {}}


def main():
    existing = load_existing()
    taxas = dict(existing.get('taxas', {}))
    taxas.update(parse_marcca(fetch('https://www.marcca.com.br/selic__rfb_.html')))
    ultima_comp, ultima_taxa, comp_prov, taxa_prov = parse_sicalc(fetch('https://sicalc.receita.fazenda.gov.br/sicalc/selic/consulta'))
    ult_mes, ult_ano = ultima_comp.split('/')
    taxas[f'{ult_ano}-{ult_mes}'] = ultima_taxa
    prov_mes, prov_ano = comp_prov.split('/')
    taxas[f'{prov_ano}-{prov_mes}'] = taxa_prov
    payload = {
        'ultimaCompetencia': ultima_comp,
        'ultimaTaxa': ultima_taxa,
        'competenciaProvisoria': comp_prov,
        'taxaProvisoria': taxa_prov,
        'fonte': 'Atualizado automaticamente por GitHub Actions a partir de Sicalc/Receita e Marcca',
        'atualizadoEm': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'taxas': dict(sorted(taxas.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Base atualizada com {len(payload["taxas"])} competências')


if __name__ == '__main__':
    main()
