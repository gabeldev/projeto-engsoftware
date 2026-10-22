"""Gera HTML de impressão com a biblioteca padrão; Chrome converte em PDF."""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = '''@page {size:A4; margin:19mm 18mm;} body {font:10pt Arial,sans-serif;
line-height:1.45;color:#202a35;} h1 {font-size:20pt;color:#193c57;} h2 {font-size:14pt;
color:#193c57;break-after:avoid;} p {margin:7pt 0;} pre {white-space:pre-wrap;
font:9pt Arial,sans-serif;} section {break-before:page;} section:first-child {break-before:auto;}
.report {font-size:10pt;} .report h1 {font-size:20pt;}'''


def render(path):
    lines = path.read_text().splitlines()
    result, paragraph = [], []

    def flush():
        if paragraph:
            result.append('<p>' + escape(' '.join(paragraph)).replace('`', '') + '</p>')
            paragraph.clear()

    for line in lines:
        if line.startswith('#'):
            flush()
            level = min(len(line) - len(line.lstrip('#')), 3)
            result.append(f'<h{level}>{escape(line.lstrip("# "))}</h{level}>')
        elif not line.strip():
            flush()
        else:
            paragraph.append(line)
    flush()
    return '\n'.join(result)


def document(sections):
    return '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Agendamento de monitorias — A2</title><style>' + CSS + '</style><body>' + ''.join(sections) + '</body></html>'


if __name__ == '__main__':
    files = ['docs/relatorio-execucao.md', 'docs/historias.md', 'Escopo_inicial.md',
             'docs/documentacao-final.md', 'docs/testes.md']
    sections = ['<section>' + render(ROOT / name) + '</section>' for name in files]
    (ROOT / 'docs/entrega-final.html').write_text(document(sections))
    (ROOT / 'docs/relatorio-execucao.html').write_text(document([
        '<section class="report">' + render(ROOT / files[0]) + '</section>']))

    (ROOT / 'docs/parte-1.html').write_text(document(['<section>' + render(ROOT / 'docs/parte-1.md') + '</section>']))
