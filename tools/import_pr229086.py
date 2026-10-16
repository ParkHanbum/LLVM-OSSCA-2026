"""Import supplied PR 229086 records without executing the benchmark scripts."""
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'content/benchmarks/pr229086'
PRIVATE = re.compile(r'file:///|/(?:Users|home)/|discord\.com/channels|libfile_[A-Za-z0-9]+')
RUN_FILES = {
    'clean-aa': 'n60-aa-result.json',
    'clean-ab': 'n60-clean-result.json',
    'profile-aa': 'n60-profile-aa-result.json',
    'diagnostic-add': 'n60-profile-result.json',
    'initial-clean-ab': 'initial-clean-result.json',
    'initial-profile-aa': 'initial-profile-aa-result.json',
    'interleaved-profile-aa': 'interleaved-profile-aa-result.json',
    'interleaved-profile-ab': 'interleaved-profile-result.json',
}
MANIFEST_FIELDS = ['model', 'threads', 'affinity', 'ort', 'numpy', 'onnx', 'mode',
                   'experiment', 'pairs', 'sample_min_seconds', 'order', 'warmup',
                   'profile_enabled', 'counts_instrumented', 'library_sha256',
                   'raw_sha256', 'frozen_sha256', 'custom_sha256', 'input_sha256',
                   'clean_aa_tolerance', 'timing_note', 'bootstrap', 'time_start_ns',
                   'script_sha256', 'protocol_change_reason',
                   'diagnostic_only_after_failed_profile_AA',
                   'causal_performance_inference_allowed', 'profile_AA_gate_passed',
                   'failed_profile_AA_sha256']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write_json(name, value):
    (DEST / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def rows_for(run):
    samples = run.get('profile_samples') or run['samples']
    result = []
    for i in range(run['manifest']['pairs']):
        sides = {s['side']: s for s in samples if s['pair'] == i}
        assert set(sides) == {0, 1}
        metric = 'add_us_per_inference' if run['manifest']['profile_enabled'] else 'wall_ms_per_inference'
        before, after = sides[0], sides[1]
        a, b = before[metric], after[metric]
        result.append({'pair': i + 1, 'order': 'AB' if i % 2 == 0 else 'BA',
                       'before': a, 'after': b, 'reduction_percent': 100 * (1 - b / a)})
    return result


def run(source):
    original_prior = load(source / 'n60-analysis/n60-summary.json')
    latest = load(source / 'n60-analysis/n60-with-diagnostic-summary.json')
    prior = latest['prior_clean_60_pairs_unchanged']
    # The latest summary updates one collection-status sentence after the
    # diagnostic run. The preceding measurements and estimates are unchanged.
    assert {k: v for k, v in original_prior.items() if k != 'collection_limits'} == {k: v for k, v in prior.items() if k != 'collection_limits'}
    assert {k: v for k, v in original_prior['collection_limits'].items() if k != 'new_n60_profile_AB'} == {k: v for k, v in prior['collection_limits'].items() if k != 'new_n60_profile_AB'}
    diagnostic = latest['diagnostic_Add_60_pairs']
    abi = load(source / 'abi-check.json')
    for name, record in abi.items():
        if name.endswith(('.so', '.o')):
            assert digest(source / 'evidence/kernel-adapter' / name) == record['sha256']

    runs = {}
    for identity, filename in RUN_FILES.items():
        original = load(source / 'pc/blazeface-t1' / filename)
        m = original['manifest']
        assert len(original['samples']) == 2 * m['pairs']
        assert m['threads'] == 1 and m['affinity'] == [4]
        assert all(s['wall_ns'] >= 100_000_000 for s in original['samples'])
        record = {'manifest': {k: m[k] for k in MANIFEST_FIELDS if k in m},
                  'samples': [{k: v for k, v in s.items() if k != 'selected_kernel_address'} for s in original['samples']],
                  'source_filename': filename, 'time_end_ns': original['time_end_ns']}
        for key in ['profile_samples', 'wall', 'add', 'model_run', 'counts', 'profile_summary', 'stability', 'clean_counter_calls_after_measurement']:
            if key in original:
                value = original[key]
                if key == 'profile_samples':
                    value = [{k: v for k, v in s.items() if k != 'selected_kernel_address'} for s in value]
                record[key] = value
        record['plot_pairs'] = rows_for(record)
        runs[identity] = record

    assert runs['clean-aa']['stability']['passed'] is True
    assert runs['profile-aa']['stability']['passed'] is False
    assert runs['diagnostic-add']['manifest']['causal_performance_inference_allowed'] is False
    failed_aa_sha = digest(source / 'pc/blazeface-t1/n60-profile-aa-result.json')
    assert failed_aa_sha == diagnostic['failed_AA_sha256_unchanged']
    assert failed_aa_sha == runs['diagnostic-add']['manifest']['failed_profile_AA_sha256']
    for metric, keys in [('wall_primary', ('before', 'after')), ('AA_wall_control', ('before', 'after'))]:
        identity = 'clean-ab' if metric == 'wall_primary' else 'clean-aa'
        values = sorted(p['after'] / p['before'] for p in runs[identity]['plot_pairs'])
        for trim, expected in enumerate(prior[metric]['sensitivity']):
            subset = values[trim:len(values) - trim]
            assert math.isclose(100 * (1 - sum(subset) / len(subset)), expected['time_reduction_percent'], abs_tol=1e-10)

    prep = load(source / 'pc/blazeface-t1/preparation.json')
    freeze = load(source / 'pc/blazeface-t1/freeze.json')
    validation = load(source / 'pc/blazeface-t1/validation.json')
    assert prep['only_add_domain_op_changed'] and prep['initializers_byte_identical']
    assert not prep['graph_reoptimized_after_substitution']
    assert len(prep['quantized_adds']) == freeze['add_nodes'] == 31
    assert validation['all_outputs_bitwise_equal']
    assert digest(source / 'pc/blazeface-t1/input.npy') == prep['input_sha256']
    assert all(r['manifest']['input_sha256'] == prep['input_sha256'] for r in runs.values())
    assert all(r['manifest']['frozen_sha256'] == prep['frozen_sha256'] for r in runs.values())

    DEST.mkdir(exist_ok=True)
    csv_names = ['aa-60-pairs.csv', 'clean-60-pairs.csv', 'profile-aa-60-pairs.csv', 'diagnostic-add-60-pairs.csv']
    for name in csv_names:
        path = source / 'n60-analysis' / name
        assert not PRIVATE.search(path.read_text())
        with path.open(newline='') as handle:
            assert len(list(csv.DictReader(handle))) == 60
        shutil.copyfile(path, DEST / name)
    fields = ['run', 'metric', 'unit', 'pair', 'order', 'before', 'after', 'reduction_percent']
    with (DEST / 'initial-12-pair-records.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for identity in list(RUN_FILES)[4:]:
            profile = runs[identity]['manifest']['profile_enabled']
            for row in runs[identity]['plot_pairs']:
                writer.writerow({'run': identity, 'metric': 'Add' if profile else 'wall', 'unit': 'us/inf' if profile else 'ms/inf', **row})

    clean = {k: prior[k] for k in ['experiment', 'effect_definition', 'bootstrap_definition',
             'wall_primary', 'user_cpu_separate', 'system_cpu_separate', 'AA_wall_control',
             'n60_clean_original_geomean_statistic', 'historical_12_pairs_separate',
             'profile_AA_gate', 'all_pairs_retained', 'no_timing_retry']}
    clean['cpu_collection_limits'] = {k: prior['collection_limits'][k] for k in ['n60_AA_user_system_separation', 'n60_clean_user_system_separation', 'profile_user_system_scope']}
    diag = {k: v for k, v in diagnostic.items() if k != 'manifest'}
    start = min(r['manifest']['time_start_ns'] for r in runs.values())
    end = max(r['time_end_ns'] for r in runs.values())
    kst = timezone(timedelta(hours=9))
    data = {
        'PR': {'number': 229086, 'url': 'https://github.com/llvm/llvm-project/pull/229086',
               'title': '[VectorCombine] Compose fixed shuffles through widening bitcasts',
               'author_handle': 'hunterhhunter'},
        'published': '2026-10-22',
        'measured_start_KST': datetime.fromtimestamp(start / 1e9, kst).isoformat(),
        'measured_end_KST': datetime.fromtimestamp(end / 1e9, kst).isoformat(),
        'scope': 'BlazeFace back W8A8 256×256, batch 1, 1 thread. Same frozen ONNX Runtime session and adapter; switch only the supplied before/after MLAS AVX2 QLinearAdd kernel outside timed blocks. Not a full patched ORT rebuild.',
        'clean_analysis': clean, 'diagnostic_analysis': diag,
        'clean_and_AA_not_rerun': latest['no_clean_rerun'] and latest['no_AA_retry'],
        'no_independent_microbenchmark': latest['no_independent_microbench'],
        'no_new_measurement_for_publication': True,
        'runs': runs,
        'frozen_graph': {k: v for k, v in freeze.items() if k != 'raw'},
        'preparation': prep, 'validation': validation,
        'Add_node_shapes': load(source / 'pc/blazeface-t1/n60-profile-add-shapes.json'),
        'model_sources': [{**{k: v for k, v in s.items() if k != 'path'}, 'filename': Path(s['path']).name} for s in load(source / 'model-sources.json')],
        'binary_identity': {name: {'sha256': v['sha256'], **({'loaded': v['loaded']} if 'loaded' in v else {})} for name, v in abi.items() if name.endswith(('.so', '.o'))},
        'source_files': [{'name': str(p.relative_to(source)), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(source.rglob('*')) if p.is_file()],
    }
    write_json('summary.json', data)
    shutil.copyfile(source / 'requirements.lock', DEST / 'requirements.lock.txt')
    for name in ['custom_add.cpp', 'custom_add_switch.cpp']:
        shutil.copyfile(source / 'evidence/kernel-adapter' / name, DEST / (name + '.txt'))
    (DEST / 'DATA-SCOPE.txt').write_text(
        'PR #229086 · 공개 데이터 범위\n\n'
        'N=60의 A/A wall, A/B wall, 프로파일 A/A, 진단용 Add A/B는 각각 60쌍을 유지합니다.\n'
        '처음 12쌍 실험 4개는 별도로 보관합니다. N=60과 합산하지 않습니다.\n'
        'summary.json에는 총 8개 실행의 표본 576개, 구간별 집계, 검증·입력·커널 해시와 Add 노드 형상이 있습니다.\n'
        '프로파일 표본은 같은 측정 표본에 Add/model_run 집계를 연결한 것이므로 추가 관측으로 세지 않습니다.\n'
        '진단용 Add A/B는 앞선 프로파일 A/A의 CV 5.411%가 기준 5%를 넘긴 후 수집됐습니다. 인과적 개선 근거로 사용하지 않습니다.\n'
        '프로파일의 user/system CPU는 전체 교차 실행 쌍의 공유 시간입니다. A/B 개별 CPU 시간으로 나누지 않습니다.\n'
        '모델 가중치, 입력 이미지, 실행 바이너리, 인터프리터, 전체 ORT 노드 trace·개별 추론 trace는 배포하지 않습니다.\n'
        '서버 절대 경로와 실행 중 커널 주소는 공개 JSON에서 제외했습니다. 측정 수치는 변경하지 않았습니다.\n'
        '이 페이지를 만들며 추론·벤치마크를 다시 실행하지 않았습니다.\n')
    for p in DEST.iterdir():
        assert not PRIVATE.search(p.read_text(encoding='utf-8-sig')), 'Private metadata: ' + p.name
    write_json('exports.json', {'source': 'pr229086-benchmark', 'published': data['published'],
               'files': [{'name': p.name, 'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(DEST.iterdir()) if p.name != 'exports.json']})
    print('Imported PR 229086: four N=60 series, four historical N=12 series, 576 original samples; no inference executed.')


if __name__ == '__main__':
    run(Path(sys.argv[1]))
