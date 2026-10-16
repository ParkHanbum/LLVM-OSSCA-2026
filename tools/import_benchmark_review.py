"""Import the completed review; export measurement fields without server metadata.

Usage: python3 tools/import_benchmark_review.py REVIEW_WORK_DIR RAW_LOG_DIR
This does not execute workloads or change the original input files.
"""
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'content/benchmarks/review'
PRIVATE = re.compile(r'file:///|/(?:Users|home)/|discord\.com/channels|cdn\.discordapp\.com/attachments')
PAIRED_FIELDS = ['mode', 'case_id', 'project', 'input', 'pair', 'order',
                 'a_user_seconds', 'b_user_seconds', 'user_ratio',
                 'a_elapsed_seconds', 'b_elapsed_seconds', 'elapsed_ratio',
                 'retained_in_main_trim']
RAW_FIELDS = ['mode', 'case_id', 'project', 'input', 'pair', 'side', 'order',
              'variant', 'command_repeats', 'user_cpu_seconds', 'system_cpu_seconds',
              'elapsed_seconds', 'max_rss_kib', 'voluntary_context_switches',
              'involuntary_context_switches', 'actual_exit_codes', 'expected_returncodes',
              'preparation_excluded_from_user_CPU', 'preparation_excluded_from_elapsed']


def write_csv(name, fields, rows):
    with (DEST / name).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def run(work, logs):
    review = json.loads((work / 'repeat_analysis.json').read_text())
    links = json.loads((work / 'contribution_links.json').read_text())
    for item in review['sources']:
        digest = hashlib.sha256((logs / item['name']).read_bytes()).hexdigest()
        assert digest == item['sha256'], 'Source changed: ' + item['name']
    with (logs / 'paired-ratios.csv').open(newline='') as handle:
        pairs = list(csv.DictReader(handle))
    with (logs / 'raw-observations.csv').open(newline='') as handle:
        raw = list(csv.DictReader(handle))
    assert len(raw) == 5080 and len(pairs) == 2540
    assert Counter(p['mode'] for p in pairs) == {'AB': 2480, 'AA': 60}
    by_tag = {r['tag']: r for r in raw}
    assert len(by_tag) == len(raw)
    used_tags = set()
    for pair in pairs:
        for side in ['a', 'b']:
            tag = pair[side + '_tag']
            assert tag not in used_tags
            used_tags.add(tag)
            assert float(pair[side + '_user_seconds']) == float(by_tag[tag]['user_cpu_seconds'])
        ratio = float(pair['b_user_seconds']) / float(pair['a_user_seconds'])
        assert math.isclose(ratio, float(pair['user_ratio']), abs_tol=1e-14)
    assert used_tags == set(by_tag)
    for row in review['results'] + review['AA_controls']:
        mode = 'AB' if row in review['results'] else 'AA'
        selected = sorted((p for p in pairs if p['mode'] == mode and p['case_id'] == row['case_id']), key=lambda p: int(p['pair']))
        assert len(selected) == row['pairs']
        assert [p['order'] for p in selected] == row['pair_orders']
        for p, values in zip(selected, row['pair_cpu_seconds']):
            assert values == [float(p['a_user_seconds']), float(p['b_user_seconds'])]
    assert Counter(r['direction_in_this_run'] for r in review['results']) == {'decrease': 12, 'increase': 12, 'mixed': 18}
    assert {c['case_id'] for c in links['cases']} == {r['case_id'] for r in review['results'] if r['direction_in_this_run'] == 'decrease'}
    DEST.mkdir(exist_ok=True)
    shutil.copyfile(work / 'repeat_analysis.json', DEST / 'repeat-analysis.json')
    shutil.copyfile(work / 'contribution_links.json', DEST / 'contribution-links.json')
    write_csv('paired-observations.csv', PAIRED_FIELDS, pairs)
    write_csv('raw-measurements.csv', RAW_FIELDS, raw)
    summary_fields = ['case_id', 'project', 'input', 'reported_trim1_reduction_percent',
                      'all_pairs_reduction_percent', 'faster_pairs', 'slower_pairs', 'equal_pairs',
                      'pairs', 'AB_reduction_percent', 'BA_reduction_percent',
                      'first_half_reduction_percent', 'second_half_reduction_percent',
                      'interval_low_percent', 'interval_high_percent', 'direction_in_this_run', 'related_PRs']
    summary = []
    for r in review['results']:
        summary.append({**{k: r[k] for k in ['case_id', 'project', 'input', 'faster_pairs', 'slower_pairs', 'equal_pairs', 'pairs', 'direction_in_this_run']},
                        'reported_trim1_reduction_percent': r['reported_trim1_reduction'],
                        'all_pairs_reduction_percent': r['all_pairs_reduction'],
                        'AB_reduction_percent': r['by_order']['AB'], 'BA_reduction_percent': r['by_order']['BA'],
                        'first_half_reduction_percent': r['by_half'][0], 'second_half_reduction_percent': r['by_half'][1],
                        'interval_low_percent': r['interval_envelope'][0], 'interval_high_percent': r['interval_envelope'][1], 'related_PRs': r['PRs']})
    write_csv('repeat-summary.csv', summary_fields, summary)
    link_fields = ['case_id', 'project', 'input', 'reduction_percent', 'faster_pairs', 'pairs', 'mentee_PRs', 'PR_urls', 'execution_summary', 'relationship', 'derived_code_change', 'isolated_speed_contribution_measured']
    connected = []
    for r in links['cases']:
        connected.append({**{k: r[k] for k in ['case_id', 'project', 'input', 'faster_pairs', 'pairs', 'execution_summary', 'relationship', 'derived_code_change', 'isolated_speed_contribution_measured']},
                          'reduction_percent': r['reduction'],
                          'mentee_PRs': ' / '.join(author + ': ' + ', '.join(links['PRs'][p]['label'] for p in ids) for author, ids in r['author_PRs'].items()),
                          'PR_urls': ' / '.join(links['PRs'][p]['url'] for p in r['PRs'])})
    write_csv('contribution-links.csv', link_fields, connected)
    metadata = {
        'reviewed': review['created'], 'source': 'benchmark-detail-log',
        'scope': '원시 파일에서 측정 수치와 입력·순서·반환 코드 열을 그대로 옮겼습니다. 서버 경로·명령·태그·환경 및 실행 로그 본문은 포함하지 않았습니다.',
        'units': {'user_cpu_seconds': '초', 'system_cpu_seconds': '초', 'elapsed_seconds': '초', 'max_rss_kib': 'KiB', 'reduction_percent': '100 × (1 − B/A 쌍 비율의 산술평균)'},
        'pair_number': 'CSV의 pair는 0부터 시작합니다. 웹 표와 차트는 같은 순서에 1을 더해 표시합니다.',
        'AA': '동일한 A 실행 파일끼리의 대조입니다. side A/B는 쌍에서의 역할이며 코드 변형을 뜻하지 않습니다.',
        'trim': 'retained_in_main_trim은 원보고에서 비율이 가장 작은 쌍과 가장 큰 쌍을 각각 하나 제외한 주 집계의 포함 여부입니다. 재검토는 전체 쌍을 사용했습니다.',
        'source_sha256': review['sources'], 'exports': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.iterdir()) if p.name != 'export-info.json'}
    }
    (DEST / 'export-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    for path in DEST.iterdir():
        assert not PRIVATE.search(path.read_text(encoding='utf-8-sig')), 'Private metadata: ' + path.name
    print('Imported 42 reviewed inputs, 12 contribution links, 2,540 pairs and 5,080 numeric observations.')


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
