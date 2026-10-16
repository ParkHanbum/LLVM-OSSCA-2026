"""Check the new public experiment against retained numeric observations."""
import csv
import hashlib
import json
import math
from collections import Counter


def check_pr229086(root, site, errors):
    source = root / 'content/benchmarks/pr229086'
    public = site / 'assets/benchmarks/pr229086'
    data = json.loads((public / 'summary.json').read_text())
    exports = json.loads((public / 'exports.json').read_text())
    for record in exports['files']:
        file = public / record['name']
        if hashlib.sha256(file.read_bytes()).hexdigest() != record['sha256'] or file.read_bytes() != (source / record['name']).read_bytes():
            errors.append('PR229086 public export changed: ' + record['name'])
    runs = data['runs']
    if len(runs) != 8 or sum(len(r['samples']) for r in runs.values()) != 576:
        errors.append('PR229086 original sample coverage changed')
    csv_map = {'clean-aa': 'aa-60-pairs.csv', 'clean-ab': 'clean-60-pairs.csv', 'profile-aa': 'profile-aa-60-pairs.csv', 'diagnostic-add': 'diagnostic-add-60-pairs.csv'}
    for identity, run in runs.items():
        n = run['manifest']['pairs']
        if n != (60 if identity in csv_map else 12) or len(run['samples']) != n * 2:
            errors.append('PR229086 run sample count mismatch')
        raw = {(s['pair'], s['side']): s for s in run['samples']}
        observed = {(s['pair'], s['side']): s for s in (run.get('profile_samples') or run['samples'])}
        if len(raw) != n * 2 or len(observed) != n * 2:
            errors.append('PR229086 duplicate/missing sample identity')
        field = 'add_us_per_inference' if run['manifest']['profile_enabled'] else 'wall_ms_per_inference'
        for row in run['plot_pairs']:
            i = row['pair'] - 1
            if row['order'] != ('AB' if i % 2 == 0 else 'BA'):
                errors.append('PR229086 plot order changed')
            a, b = observed[(i, 0)], observed[(i, 1)]
            if row['before'] != a[field] or row['after'] != b[field] or abs(row['reduction_percent'] - 100 * (1 - b[field] / a[field])) > 1e-10:
                errors.append('PR229086 chart point disagrees with observation')
            for side in [0, 1]:
                sample = raw[(i, side)]
                if not math.isclose(sample['wall_ns'] / sample['iterations'] / 1e6, sample['wall_ms_per_inference'], abs_tol=1e-10):
                    errors.append('PR229086 elapsed/iteration conversion changed')
        if identity in csv_map:
            with (public / csv_map[identity]).open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            if len(rows) != 60:
                errors.append('PR229086 CSV does not retain all 60 pairs')
            for i, row in enumerate(rows):
                for side, prefix in [(0, 'before'), (1, 'after')]:
                    if not math.isclose(float(row[prefix + '_wall_ns']), raw[(i, side)]['wall_ns'], abs_tol=0):
                        errors.append('PR229086 CSV/JSON raw time mismatch')
                    if run['manifest']['profile_enabled'] and not math.isclose(float(row[prefix + '_add_us_per_inference']), observed[(i, side)]['add_us_per_inference'], abs_tol=1e-10):
                        errors.append('PR229086 CSV/JSON Add mismatch')

    clean = data['clean_analysis']
    for identity, key in [('clean-ab', 'wall_primary'), ('clean-aa', 'AA_wall_control')]:
        rows = runs[identity]['plot_pairs']
        reported = clean[key]
        for side in ['before', 'after']:
            if abs(sum(r[side] for r in rows) / len(rows) - reported['mean_' + side]) > 1e-10:
                errors.append('PR229086 headline mean disagrees with all samples')
        ratios = sorted(r['after'] / r['before'] for r in rows)
        for trim, estimate in enumerate(reported['sensitivity']):
            selected = ratios[trim:len(ratios)-trim]
            if abs(100 * (1 - sum(selected) / len(selected)) - estimate['time_reduction_percent']) > 1e-10:
                errors.append('PR229086 trimmed estimator cannot be reproduced')
        counts = Counter('faster' if r['after'] < r['before'] else 'slower' if r['after'] > r['before'] else 'equal' for r in rows)
        if any(counts[k] != reported['all_pair_directions'][k] for k in ['faster', 'slower', 'equal']):
            errors.append('PR229086 paired directions changed')
    if runs['clean-aa']['stability']['passed'] is not True or runs['profile-aa']['stability']['passed'] is not False:
        errors.append('PR229086 A/A gate status changed')
    if runs['diagnostic-add']['manifest']['causal_performance_inference_allowed'] is not False:
        errors.append('PR229086 diagnostic provenance lost')
    if any(s.get('process_user_cpu_ns') is not None or s.get('process_system_cpu_ns') is not None for s in runs['clean-aa']['samples']):
        errors.append('PR229086 missing A/A CPU split was imputed')
    for p in range(60):
        samples = [s for s in runs['diagnostic-add']['samples'] if s['pair'] == p]
        for field in ['pair_process_user_cpu_ns', 'pair_process_system_cpu_ns']:
            if samples[0][field] != samples[1][field]:
                errors.append('PR229086 pair-shared CPU scope changed')
    profile = data['diagnostic_analysis']
    ratios = sorted(p['after'] / p['before'] for p in runs['diagnostic-add']['plot_pairs'])[1:-1]
    if abs(sum(ratios) / len(ratios) - profile['trimmed_mean_R']) > 1e-12:
        errors.append('PR229086 Add aggregate changed')
    for side in [0, 1]:
        observations = [s for s in runs['diagnostic-add']['profile_samples'] if s['side'] == side]
        count = sum(s['iterations'] for s in observations)
        total_add = sum(s['add_us_per_inference'] * s['iterations'] for s in observations)
        total_model = sum(s['model_run_us_per_inference'] * s['iterations'] for s in observations)
        reported = profile['profile_summary'][side]
        if count != reported['inferences'] or abs(total_add / count - reported['mean_add_us_per_inference']) > 1e-8 or abs(100 * total_add / total_model - reported['add_share_of_same_profile_model_run_percent']) > 1e-10:
            errors.append('PR229086 profile weighting/denominator mismatch')
    counts = profile['actual_counts']
    shapes = data['Add_node_shapes']
    elements = sum(math.prod(next(iter(s['output_type_shape'][0].values()))) for s in shapes.values())
    if len(shapes) != 31 or counts['calls'] != 31 * counts['inferences'] or counts['elements'] != elements * counts['inferences']:
        errors.append('PR229086 shape and actual count accounting disagree')
    if data['PR']['url'] != 'https://github.com/llvm/llvm-project/pull/229086' or not data['validation']['all_outputs_bitwise_equal']:
        errors.append('PR229086 identity/output evidence changed')
    page = (site / 'benchmarks/pr229086.html').read_text()
    if page.count('class="pr229086-observation"') != 480:
        errors.append('PR229086 chart observations are incomplete')
    if set(runs) != set(__import__('re').findall(r'data-pr229086-run="([^"]+)"', page)):
        errors.append('PR229086 native pair tables omit a run')
    for marker in ['진단 참고값 · 프로파일 A/A 기준 미통과', '모델 내부 교체 실험', '5.411', '576', '미수집']:
        if marker not in page:
            errors.append('PR229086 scope marker missing: ' + marker)
    if 'benchmarks/pr229086.html' not in (site / 'benchmarks.html').read_text():
        errors.append('PR229086 page is not linked from archive')
    if any(p.suffix in ['.so', '.o', '.npy', '.onnx'] for p in public.rglob('*')):
        errors.append('PR229086 private/binary input copied to public site')
    return {'page': 'benchmarks/pr229086.html', 'N60_series': 4, 'historical_N12_series': 4, 'original_samples': 576, 'Add_nodes': 31, 'profile_AA_passed': False, 'diagnostic_only': True}
