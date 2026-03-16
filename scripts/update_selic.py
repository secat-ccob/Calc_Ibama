import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dados" / "selic-rfb.json"

URL_SICALC = "https://sicalc.receita.fazenda.gov.br/sicalc/selic/consulta"

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


def fetch(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def parse_sicalc(html: str):
    # Exemplo esperado:
    # Última Selic disponível (02/2026) 1.00
    m1 = re.search(
        r'Última\s+Selic\s+disponível\s*\((\d{2}/\d{4})\)\s*([0-9]+(?:[.,][0-9]+)?)',
        html,
        re.IGNORECASE
    )

    # Exemplo esperado:
    # Percentual em 03/2026 1.00
    m2 = re.search(
        r'Percentual\s+em\s+(\d{2}/\d{4})\s*([0-9]+(?:[.,][0-9]+)?)',
        html,
        re.IGNORECASE
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
        "taxas": {}
    }


def main():
    base = carregar_base_existente()

    if "taxas" not in base or not isinstance(base["taxas"], dict):
        base["taxas"] = {}

    html = fetch(URL_SICALC)
    ultima_comp, ultima_taxa, comp_prov, taxa_prov = parse_sicalc(html)

    base["ultimaCompetencia"] = ultima_comp
    base["ultimaTaxa"] = ultima_taxa
    base["competenciaProvisoria"] = comp_prov
    base["taxaProvisoria"] = taxa_prov

    # Atualiza / preserva histórico
    base["taxas"][mm_aaaa_para_iso(ultima_comp)] = ultima_taxa
    base["taxas"][mm_aaaa_para_iso(comp_prov)] = taxa_prov

    # Ordena as competências
    base["taxas"] = dict(sorted(base["taxas"].items()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(base, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Base atualizada com sucesso usando apenas o Sicalc")


if __name__ == "__main__":
    main()
