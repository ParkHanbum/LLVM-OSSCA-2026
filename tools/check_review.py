"""Cross-check public review files against observations and source provenance."""
import csv
import hashlib
import json
import math
import re
from collections import Counter


def check_review(root, site, errors):
    source = root / 'content/benchmarks/review'
    public = site / 'assets/benchmarks/review'
    review = json.loads((public / 'repeat-analysis.json').read_text())
    links = json.loads((public / 'contribution-links.json').read_text())
    manifest = json.loads((public / 'export-info.json').read_text())
    for name, digest in manifest['exports'].items():
        path = public / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append('Review export digest mismatch: ' + name)
    for path in source.iterdir():
        if path.read_bytes() != (public / path.name).read_bytes():
            errors.append('Review export is stale: ' + path.name)

    def csv_rows(name):
        with (public / name).open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))

    pairs = csv_rows('paired-observations.csv')
    raw = csv_rows('raw-measurements.csv')
    summary = csv_rows('repeat-summary.csv')
    connected = csv_rows('contribution-links.csv')
    if len(raw) != 5080 or Counter(p['mode'] for p in pairs) != {'AB': 2480, 'AA': 60}:
        errors.append('Published measurement coverage changed')
    observations = {(r['mode'], r['case_id'], int(r['pair']), r['side']): r for r in raw}
    if len(observations) != 5080:
        errors.append('Published observations have duplicate/missing identities')
    by_pair = {(p['mode'], p['case_id'], int(p['pair'])): p for p in pairs}
    for pair in pairs:
        identity = pair['mode'], pair['case_id'], int(pair['pair'])
        for side in ['A', 'B']:
            r = observations.get((*identity, side))
            if not r or float(r['user_cpu_seconds']) != float(pair[side.lower() + '_user_seconds']):
                errors.append('Published raw/paired CPU times disagree: ' + pair['case_id'])
            elif json.loads(r['actual_exit_codes']) and not set(json.loads(r['actual_exit_codes'])).issubset(set(json.loads(r['expected_returncodes']))):
                errors.append('Unexpected measurement return code')
        if not math.isclose(float(pair['b_user_seconds']) / float(pair['a_user_seconds']), float(pair['user_ratio']), abs_tol=1e-14):
            errors.append('Published ratio cannot be reproduced')
    for mode, rows in [('AB', review['results']), ('AA', review['AA_controls'])]:
        for row in rows:
            case = row['case_id']
            selected = [by_pair[(mode, case, i)] for i in range(row['pairs'])]
            ratios = [float(p['user_ratio']) for p in selected]
            cuts = sorted(ratios)
            mean = lambda values: sum(values) / len(values)
            for trim, expected in enumerate(row['trim_sensitivity']):
                actual = (1 - mean(cuts[trim:len(cuts)-trim])) * 100
                if abs(actual - expected) > 1e-10:
                    errors.append('Review aggregate cannot be reproduced: ' + case)
            faster = sum(r < 1 for r in ratios)
            if faster != row['faster_pairs'] or [p['order'] for p in selected] != row['pair_orders']:
                errors.append('Review pair order/count disagrees: ' + case)
            times = [[float(p['a_user_seconds']), float(p['b_user_seconds'])] for p in selected]
            if times != row['pair_cpu_seconds']:
                errors.append('Chart times differ from observations: ' + case)
            for order in ['AB', 'BA']:
                value = 100 * (1 - mean([r for r, p in zip(ratios, selected) if p['order'] == order]))
                if abs(value - row['by_order'][order]) > 1e-10:
                    errors.append('AB/BA review mismatch: ' + case)
            for i, half in enumerate([ratios[:len(ratios)//2], ratios[len(ratios)//2:]]):
                if abs(100 * (1 - mean(half)) - row['by_half'][i]) > 1e-10:
                    errors.append('Half-run review mismatch: ' + case)
            retained = [float(p['user_ratio']) for p in selected if p['retained_in_main_trim'] == 'True']
            if len(retained) != row['pairs'] - 2 or abs(100 * (1 - mean(retained)) - row['reported_trim1_reduction']) > 1e-10:
                errors.append('Original trim membership changed: ' + case)
    if Counter(r['direction_in_this_run'] for r in review['results']) != {'decrease': 12, 'increase': 12, 'mixed': 18}:
        errors.append('Unexpected review direction counts')
    if any(not r['interval_envelope'][0] <= 0 <= r['interval_envelope'][1] for r in review['AA_controls']):
        errors.append('A/A controls do not include zero')
    decreases = {r['case_id']: r for r in review['results'] if r['direction_in_this_run'] == 'decrease'}
    if len(summary) != 42 or len(connected) != 12 or {r['case_id'] for r in links['cases']} != set(decreases):
        errors.append('Contribution/review summary coverage changed')
    if len(links['PRs']) != 7 or {p['author'] for p in links['PRs'].values()} != {'최진범', '정지현', '이하동', '정하람'}:
        errors.append('Contribution author/PR coverage changed')
    for identity, pr in links['PRs'].items():
        expected = 'https://github.com/' + ('ThePo1es/llvm-project' if identity == '2' else 'llvm/llvm-project') + '/pull/' + identity
        if pr['url'] != expected:
            errors.append('Incorrect contribution PR repository')
    for r in links['cases']:
        expected = decreases[r['case_id']]
        if r['isolated_speed_contribution_measured'] or abs(r['reduction'] - expected['reported_trim1_reduction']) > 1e-12:
            errors.append('Unsupported isolated PR speed claim or changed result')
        if r['faster_pairs'] != expected['faster_pairs'] or r['pairs'] != expected['pairs']:
            errors.append('Attribution pair counts disagree')
        if set(r['PRs']) != set(expected['PRs'].split(',')):
            errors.append('Attribution PR association changed')
    for name in ['results.html', 'benchmarks.html']:
        markup = (site / name).read_text()
        if set(re.findall(r'data-contribution-case="([^"]+)"', markup)) != set(decreases):
            errors.append('Page omits contribution-linked inputs: ' + name)
        for pr in links['PRs'].values():
            if pr['url'] not in markup:
                errors.append('Page omits PR hyperlink: ' + name)
        if '원시 측정 재검토 2026-10-18' not in markup and '재검토 2026-10-18' not in markup:
            errors.append('Missing review date: ' + name)
    markup = (site / 'benchmarks.html').read_text()
    if markup.count('class="review-point"') != 2480:
        errors.append('Raw-series charts omit observations')
    search = json.loads(re.search(r'id="archive-search-data">(.*?)</script>', markup).group(1))
    if len(search) != 42 or Counter(r['status'] for r in search) != {'decrease': 12, 'increase': 12, 'mixed': 18}:
        errors.append('Search uses stale verdicts')
    for row in links['cases']:
        record = next(r for r in search if r['id'] == row['case_id'])
        if not all(name in record['text'] for name in row['authors']):
            errors.append('Mentee name missing from search index')
    return dict(reviewed=review['created'],AB_pairs=2480,AA_pairs=60,raw_observations=5080,mean_direction={'decrease':12,'increase':12,'mixed':18},linked_mentees=4,linked_PRs=7,linked_inputs=12)
