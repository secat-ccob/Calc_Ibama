import json
import re
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dados" / "selic-rfb.json"

URL_SICALC = "https://sicalc.receita.fazenda.gov.br/sicalc/selic/consulta"
URL_BC_TEMPLATE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4390/dados?formato=json&dataInicial={ini}&dataFinal={fim}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def fetch_text(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")

def fetch_json(url: str):
    return json.loads(fetch_text(url))

def limpar_html(html: str) -> str:
    texto = unescape(html)
    texto = re.sub(r"(?is)<script.*?>.*?</script>", " ", texto)
    texto = re.sub(r"(?is)<style.*?>.*?</style>", " ", texto)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

def parse_sicalc(html: str):
    texto = limpar_html(html)

    m1 = re.search(
        r"Última\s+Selic\s+disponível\s*\((\d{2}/\d{4})\)\s*([0-9]+(?:[.,][0-9]+)?)",
        texto,
        re.IGNORECASE,
    )
    m2 = re.search(
        r"Percentual\s+em\s+(\d{2}/\d{4})\s*([0-9]+(?:[.,][0-9]+)?)",
        texto,
        re.IGNORECASE,
    )

    if not m1 or not m2:
        raise RuntimeError("Não foi possível localizar os percentuais no Sicalc")

    ultima_comp = m1.group(1)
    ultima_taxa = float(m1.group(2).replace(",", "."))
    comp_prov = m2.group(1)
    taxa_prov = float(m2.group(2).replace(",", "."))

    return ultima_comp, ultima_taxa, comp_prov, taxa_prov

def mm_aaaa_para_iso(comp: str) -> str:
    mm, aaaa = comp.split("/")
    return f"{aaaa}-{mm}"

def carregar_base_existente():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "ultimaCompetencia": "",
        "ultimaTaxa": 0.0,
        "competenciaProvisoria": "",
        "taxaProvisoria": 0.0,
        "taxas": {},
    }

def dateranges():
    # API do BCB pode exigir filtros por período; usar janelas <= 10 anos evita erro
    ranges = [
        ("01/02/1995", "31/12/2004"),
        ("01/01/2005", "31/12/2014"),
        ("01/01/2015", "31/12/2024"),
    ]
    today = date.today()
    last = f"{today.day:02d}/{today.month:02d}/{today.year}"
    ranges.append(("01/01/2025", last))
    return ranges

def carregar_historico_bcb():
    taxas = {}
    for ini, fim in dateranges():
        url = URL_BC_TEMPLATE.format(ini=ini, fim=fim)
        dados = fetch_json(url)
        for item in dados:
            dd, mm, aaaa = item["data"].split("/")
            chave = f"{aaaa}-{mm}"
            taxas[chave] = float(str(item["valor"]).replace(",", "."))
    return dict(sorted(taxas.items()))

def main():
    base = carregar_base_existente()

    base["taxas"] = carregar_historico_bcb()

    html = fetch_text(URL_SICALC)
    ultima_comp, ultima_taxa, comp_prov, taxa_prov = parse_sicalc(html)

    base["ultimaCompetencia"] = ultima_comp
    base["ultimaTaxa"] = ultima_taxa
    base["competenciaProvisoria"] = comp_prov
    base["taxaProvisoria"] = taxa_prov

    # Sobrescreve o fechamento mais recente e a competência provisória
    # com os valores lidos diretamente do Sicalc
    base["taxas"][mm_aaaa_para_iso(ultima_comp)] = ultima_taxa
    base["taxas"][mm_aaaa_para_iso(comp_prov)] = taxa_prov

    base["taxas"] = dict(sorted(base["taxas"].items()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Base atualizada com histórico completo do BCB + competências vigentes do Sicalc")
    print(f"Total de competências gravadas: {len(base['taxas'])}")

if __name__ == "__main__":
    main()
