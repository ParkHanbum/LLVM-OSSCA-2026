"""Import existing measurements. Never execute or regenerate a benchmark.

Run with the document runtime, giving the three source paths explicitly.
The ordinary site builder only reads the reviewed content written here.
"""
import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'content' / 'benchmarks'
LOCAL_PATH = re.compile(r'/(?:Users|home)/[^\s<>"\']+')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, data):
    (DEST / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def comments(svg):
    from html import unescape
    return [unescape(s.strip()) for s in re.findall(r'<!--(.*?)-->', svg, re.S)]


def read_cases(path):
    charts = DEST / 'charts'
    charts.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        original = json.loads(archive.read('qualification-matrix.json'))
        from lxml import html
        review = html.fromstring(archive.read('qualification-review.html'))
        history_heading = review.xpath('//h2[contains(., "조건별 폐기·수정 이력")]')[0]
        original['review_history'] = [' '.join(li.itertext()).strip() for li in history_heading.getnext().xpath('./li')]
        cases = original['conditions']
        files = sorted(n for n in archive.namelist() if n.startswith('charts/') and n.endswith('.svg'))
        assert len(files) == 47 and len(cases) == 42
        for filename in files:
            raw = archive.read(filename)
            text = raw.decode()
            assert not LOCAL_PATH.search(text)
            tree = ET.fromstring(text)
            for element in tree.iter():
                assert element.tag.split('}')[-1] not in ('script', 'foreignObject')
                for key, value in element.attrib.items():
                    assert not key.lower().startswith('on')
                    if key.split('}')[-1] == 'href':
                        assert value.startswith('#'), (filename, value)
            (charts / Path(filename).name).write_bytes(raw)
        for case in cases:
            filename = next(n for n in files if n.endswith('-' + case['case_id'] + '.svg'))
            strings = comments(archive.read(filename).decode())
            text = '\n'.join(strings)
            case['chart'] = Path(filename).name
            case['chart_text'] = strings
            patterns = {
                'user': r'A user ([\d.]+)s\s+B user ([\d.]+)s',
                'system': r'A system ([\d.]+)s\s+B system ([\d.]+)s',
                'elapsed': r'A elapsed ([\d.]+)s\s+B elapsed ([\d.]+)s',
            }
            for metric, pattern in patterns.items():
                values = re.search(pattern, text)
                assert values, (case['case_id'], metric)
                case[metric] = {'A': float(values[1]), 'B': float(values[2])}
            ratio = re.search(r'B/A ([\d.]+)\s+속도 ([\d.]+)x', text)
            count = re.search(r'(\d+)쌍, 주 집계 (\d+)쌍\s+\|\s+user CPU 감소율 ([+−-]?[\d.]+)%', text)
            uncertainty = re.search(r'elapsed 감소율 ([+−-]?[\d.]+)% / 쌍 비율 CV ([\d.]+)%', text)
            assert ratio and count and uncertainty, case['case_id']
            case.update(ratio=float(ratio[1]), speedup=float(ratio[2]), pairs=int(count[1]), used_pairs=int(count[2]), reduction=float(count[3]), elapsed_reduction=float(uncertainty[1]), pair_cv=float(uncertainty[2]))
            case['sensitivity'] = [float(s.replace('%', '').replace('−', '-')) for s in strings[strings.index('집계 규칙 민감도') - 3:strings.index('집계 규칙 민감도')]]
            verdict = next(s for s in strings if s in ['A/A 잡음 또는 쌍별 불확실성 범위', '시간 감소: 잡음·쌍 오차 기준 밖', '저하: 잡음·쌍 오차 기준 밖'])
            case['verdict'] = verdict
            case['status'] = 'uncertain' if verdict.startswith('A/A') else ('improved' if case['reduction'] > 0 else 'regressed')
            case['repetitions'] = next(s for s in strings if s.startswith('명령 반복'))
            # Evidence filenames remain useful identifiers, but unavailable private
            # server paths must not become broken public links.
            case['evidence'] = [s.split('/local-remeasure/', 1)[-1] for s in case['evidence']]
            case['evidence_available'] = False
        assert Counter(c['status'] for c in cases) == {'uncertain': 40, 'improved': 1, 'regressed': 1}
        save('applications.json', {'source': {'filename': path.name, 'sha256': sha(path), 'chart_count': 47, 'raw_observation_files_included': False}, **original})


def read_report(path, pdf):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(path)
    blocks = []
    for element in doc.element.body:
        if element.tag == qn('w:p'):
            paragraph = Paragraph(element, doc)
            if not paragraph.text.strip():
                continue
            block = {'kind': 'paragraph', 'text': paragraph.text}
            if paragraph.style.name.startswith('Heading '):
                block['heading'] = int(paragraph.style.name.split()[-1])
            blocks.append(block)
        elif element.tag == qn('w:tbl'):
            blocks.append({'kind': 'table', 'rows': [[c.text for c in row.cells] for row in Table(element, doc).rows]})
    assert len(blocks) == 183
    sources = [{'filename': path.name, 'sha256': sha(path)}]
    images = []
    if pdf:
        import pypdfium2
        document = pypdfium2.PdfDocument(pdf)
        folder = DEST / 'report-charts'
        folder.mkdir(exist_ok=True)
        for index in range(len(document)):
            image = document[index].render(scale=1.65).to_pil()
            name = f'pr19-{index + 1}.png'
            image.save(folder / name, optimize=True)
            images.append(name)
        sources.append({'filename': pdf.name, 'sha256': sha(pdf)})
    save('pr19-report.json', {'sources': sources, 'blocks': blocks, 'charts': images, 'raw_405_rows_included': False})


def read_backend(packet):
    folder = DEST / 'backend'
    folder.mkdir(exist_ok=True)
    fields = ['path', 'profile', 'status', 'source_sha256', 'normalized_sha256', 'removed_profile_attributes', 'before_assembly_sha256', 'after_assembly_sha256', 'before_returncode', 'after_returncode', 'before_seconds', 'after_seconds', 'changed_functions', 'before_diagnostic', 'after_diagnostic']
    counts = Counter()
    handles = {}
    writers = {}
    for profile in ['avx2-v3', 'avx512-v4']:
        handle = (folder / (profile + '.csv')).open('w', newline='')
        handles[profile] = handle
        writers[profile] = csv.DictWriter(handle, fieldnames=fields)
        writers[profile].writeheader()
    source = packet / '2026-10-05-backend-results.jsonl'
    with source.open() as handle:
        for line in handle:
            record = json.loads(line)
            result = {k: record.get(k, '') for k in fields[:6]}
            counts[(record['profile'], record['status'])] += 1
            result['changed_functions'] = json.dumps(record.get('changed_functions', []), ensure_ascii=False)
            for variant in ['before', 'after']:
                item = record['variants'][variant]
                for key in ['assembly_sha256', 'returncode', 'seconds']:
                    result[variant + '_' + key] = item.get(key, '')
                diagnostic = ''
                if item.get('stderr_artifact'):
                    stderr = packet / item['stderr_artifact']
                    if stderr.is_file():
                        # Keep the full compiler diagnostic; remove local machine
                        # paths and stack addresses that do not explain the result.
                        diagnostic = LOCAL_PATH.sub('[local-path]', stderr.read_text(errors='replace'))
                result[variant + '_diagnostic'] = diagnostic
            writers[record['profile']].writerow(result)
    for handle in handles.values():
        handle.close()
    assert sum(counts.values()) == 78742
    assert counts[('avx2-v3', 'identical')] == 39116
    assert counts[('avx512-v4', 'identical')] == 39222
    assert counts[('avx2-v3', 'codegen_error')] == 255
    assert counts[('avx512-v4', 'codegen_error')] == 149
    mca = json.loads((packet / '2026-10-06-isa-cost-metrics-v2.json').read_text())
    for item in mca:
        for value in item['variants'].values():
            value.pop('command', None)
    supplement = []
    for name, method in [('2026-10-06-feature-supplement-v2-results.jsonl', 'minimal_optional_features'), ('2026-10-06-source-features-supplement-results.jsonl', 'source_features')]:
        for line in (packet / name).read_text().splitlines():
            record = json.loads(line)
            record = json.loads(LOCAL_PATH.sub('[local-path]', json.dumps(record, ensure_ascii=False)))
            record['method'] = method
            supplement.append(record)
    save('backend-summary.json', {'source': {'filename': source.name, 'sha256': sha(source)}, 'counts': [{'profile': p, 'status': s, 'count': c} for (p, s), c in sorted(counts.items())], 'closure': json.loads((packet / '2026-10-06-closure-verification.json').read_text()), 'mca': mca, 'supplement': supplement})
    for file in folder.iterdir():
        assert file.stat().st_size < 25 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--applications', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--report-charts', type=Path)
    parser.add_argument('--backend', type=Path, required=True)
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    read_cases(args.applications)
    read_report(args.report, args.report_charts)
    read_backend(args.backend)
    print('Imported 42 application conditions / 47 charts, complete 19-PR report, and 78,742 backend records.')


if __name__ == '__main__':
    main()
