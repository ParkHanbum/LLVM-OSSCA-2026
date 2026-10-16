"""Render the supplied BlazeFace inference and diagnostic observations."""
import json
from datetime import datetime, timedelta, timezone
from html import escape

ASSET = '../assets/benchmarks/pr229086/'
PUBLISHED = '2026-10-22'
LABELS = {
    'clean-aa': '같은 커널 대조 · A/A wall',
    'clean-ab': '계측 없는 추론 · A/B wall',
    'profile-aa': '프로파일 Add 대조 · A/A',
    'diagnostic-add': '진단용 Add 비교 · A/B',
    'initial-clean-ab': '처음 12쌍 · 계측 없는 추론',
    'initial-profile-aa': '처음 12쌍 · 연속 블록 프로파일 A/A',
    'interleaved-profile-aa': '처음 12쌍 · 교차 프로파일 A/A',
    'interleaved-profile-ab': '처음 12쌍 · 교차 프로파일 A/B',
}


def e(value):
    return escape(str(value), quote=True)


def num(value, digits=6):
    return f'{value:,.{digits}f}'


def pct(value, digits=3):
    return ('+' if value >= 0 else '−') + f'{abs(value):.{digits}f}%'


def load(root):
    return json.loads((root / 'content/benchmarks/pr229086/summary.json').read_text())


def table(headers, rows, caption=''):
    return '<div class="table-wrap pr229086-table"><table>' + ('<caption>' + e(caption) + '</caption>' if caption else '') + '<thead><tr>' + ''.join('<th scope="col">' + e(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<th scope="row">' + str(cell) + '</th>' if i == 0 else '<td>' + str(cell) + '</td>' for i, cell in enumerate(row)) + '</tr>' for row in rows) + '</tbody></table></div>'


def entry(data):
    wall = data['clean_analysis']['wall_primary']
    return '<section class="pr229086-entry" id="pr229086"><div class="eyebrow">ADDED 2026-10-22 / SEPARATE PR STUDY</div><h2>PR #229086 · BlazeFace 추론 60쌍</h2><p>같은 ONNX Runtime 세션에서 MLAS Add의 전후 커널을 교체했습니다. 계측 없는 평균 추론 시간은 <strong>' + num(wall['mean_before'], 3) + ' → ' + num(wall['mean_after'], 3) + ' ms/추론</strong>입니다. 쌍별 비율 주 집계는 ' + pct(wall['primary']['time_reduction_percent']) + ' 시간 감소, 감소한 쌍은 43/60입니다.</p><p class="small-note">전반·후반의 평균 방향 차이와 별도 Add 진단 측정의 A/A 기준 미통과를 함께 수록했습니다. 아래 42개 입력 실험의 집계와는 별도입니다.</p><a class="pr229086-entry-link" href="benchmarks/pr229086.html">추론 시간·Add 진단·모든 쌍·측정 방법 보기 ↗</a></section>'


def plot(run, identity, title, unit, kind='ratio'):
    rows = run['plot_pairs']
    values = [p['reduction_percent'] for p in rows] if kind == 'ratio' else [p[k] for p in rows for k in ['before', 'after']]
    low, high = min(values), max(values)
    if kind == 'ratio':
        low, high = min(0, low), max(0, high)
    span = max(high - low, .1)
    low -= span * .12
    high += span * .12
    left, right, top, bottom = 74, 892, 26, 224
    xx = lambda i: left + (right - left) * i / (len(rows) - 1)
    yy = lambda v: bottom - (v - low) / (high - low) * (bottom - top)
    chart_id = 'pr229086-' + identity + '-' + kind
    parts = ['<figure class="review-chart pr229086-chart"><div class="review-plot-scroll" tabindex="0" aria-label="' + e(title) + '. 좁은 화면에서는 가로로 스크롤할 수 있습니다."><svg viewBox="0 0 920 278" role="img" aria-labelledby="' + chart_id + '-title ' + chart_id + '-desc"><title id="' + chart_id + '-title">' + e(title) + '</title><desc id="' + chart_id + '-desc">모든 ' + str(len(rows)) + '쌍을 측정 순서대로 표시했습니다. 정확한 값은 바로 아래 표와 CSV에서 확인할 수 있습니다.</desc><rect width="920" height="278" fill="#fff"/>']
    for tick in range(5):
        value = low + (high - low) * tick / 4
        y = yy(value)
        parts.append(f'<line x1="{left}" x2="{right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e0e3dc" stroke-width="1"/><text x="64" y="{y+4:.2f}" text-anchor="end">{value:.2f}' + ('%' if kind == 'ratio' else '') + '</text>')
    if kind == 'ratio':
        parts.append(f'<line x1="{left}" x2="{right}" y1="{yy(0):.2f}" y2="{yy(0):.2f}" stroke="#657078" stroke-width="1.1"/>')
        points = ' '.join(f'{xx(i):.2f},{yy(p["reduction_percent"]):.2f}' for i, p in enumerate(rows))
        parts.append('<polyline points="' + points + '" fill="none" stroke="#b1b9b5" stroke-width=".9"/>')
        for i, p in enumerate(rows):
            color = '#28715f' if p['order'] == 'AB' else '#a13d28'
            fill = color if p['order'] == 'AB' else '#fff'
            tip = str(p['pair']) + '쌍 · ' + p['order'] + ' · ' + pct(p['reduction_percent'], 6) + ' · A ' + num(p['before']) + ' / B ' + num(p['after']) + ' ' + unit
            parts.append(f'<circle class="pr229086-observation" cx="{xx(i):.2f}" cy="{yy(p["reduction_percent"]):.2f}" r="3" fill="{fill}" stroke="{color}" stroke-width="1.3"><title>{e(tip)}</title></circle>')
    else:
        for key, label, color in [('before', '이전 A', '#28715f'), ('after', '변경 B', '#a13d28')]:
            points = ' '.join(f'{xx(i):.2f},{yy(p[key]):.2f}' for i, p in enumerate(rows))
            parts.append('<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width=".9"/>')
            for i, p in enumerate(rows):
                fill = color if key == 'before' else '#fff'
                tip = str(p['pair']) + '쌍 · ' + label + ' ' + num(p[key]) + ' ' + unit
                parts.append(f'<circle class="pr229086-observation" cx="{xx(i):.2f}" cy="{yy(p[key]):.2f}" r="2.7" fill="{fill}" stroke="{color}" stroke-width="1.2"><title>{e(tip)}</title></circle>')
    for i in [0, len(rows) // 2 - 1, len(rows) - 1]:
        parts.append(f'<text x="{xx(i):.2f}" y="246" text-anchor="middle">{i+1}</text>')
    axis = '측정 쌍 순서 · ' + ('양수: 시간 감소 / 음수: 시간 증가' if kind == 'ratio' else unit)
    parts.append('<text x="480" y="270" text-anchor="middle">' + e(axis) + '</text></svg></div><figcaption><strong>' + e(title) + '</strong><br>' + ('● AB / ○ BA 실행 순서 · 선은 측정 순서 연결입니다.' if kind == 'ratio' else '<span class="review-marker-ab">● 이전 A</span> / <span class="review-marker-ba">○ 변경 B</span> · 세로축 단위: ' + e(unit)) + '</figcaption></figure>')
    return ''.join(parts)


def pair_table(run, identity):
    profile = run['manifest']['profile_enabled']
    unit = 'µs/추론' if profile else 'ms/추론'
    headings = ['쌍', '순서', 'A ' + unit, 'B ' + unit, '쌍별 감소율']
    profile_rows = {(s['pair'], s['side']): s for s in (run.get('profile_samples') or run['samples'])}
    if profile:
        headings += ['같은 profile의 A model_run µs', 'B model_run µs', 'A Add 비중', 'B Add 비중']
    else:
        headings += ['A 반복 / B 반복', 'A user ms/추론', 'B user ms/추론']
    rows = []
    for p in run['plot_pairs']:
        a, b = profile_rows[(p['pair'] - 1, 0)], profile_rows[(p['pair'] - 1, 1)]
        row = [str(p['pair']), p['order'], num(p['before']), num(p['after']), pct(p['reduction_percent'], 6)]
        if profile:
            row += [num(a['model_run_us_per_inference']), num(b['model_run_us_per_inference']), num(a['add_share_of_model_run_percent'], 6) + '%', num(b['add_share_of_model_run_percent'], 6) + '%']
        else:
            row += [str(a['iterations']) + ' / ' + str(b['iterations'])]
            row += ['미수집' if s.get('process_user_cpu_ns') is None else num(s['process_user_cpu_ns'] / s['iterations'] / 1e6) for s in [a, b]]
        rows.append(row)
    return '<details class="archive-details pr229086-pairs" data-pr229086-run="' + identity + '"><summary>' + str(len(rows)) + '쌍 전체 수치 보기 · 제외 없음</summary>' + table(headings, rows, '모든 쌍의 수치는 원시 표본 전체입니다. 주 집계에서만 각 꼬리 1쌍을 제외합니다.') + '</details>'


def clock_time(ns):
    return datetime.fromtimestamp(ns / 1e9, timezone(timedelta(hours=9))).strftime('%H:%M:%S')


def build(root, wrap, icon):
    data = load(root)
    clean = data['clean_analysis']
    wall = clean['wall_primary']
    diag = data['diagnostic_analysis']
    runs = data['runs']
    body = '<article class="article archive-article pr229086-article"><header class="article-header"><div class="eyebrow">PR #229086 / MODEL INFERENCE EXPERIMENT</div><h1>BlazeFace 추론과<br>Add 커널의 전후 비교</h1><p class="article-lead">VectorCombine의 셔플 결합 패치를 검토하기 위해, 제공된 MLAS AVX2 QLinearAdd 전후 커널을 같은 ONNX Runtime 모델 안에서 비교했습니다.</p><div class="article-meta"><span>2026-10-22 측정 · KST</span><span>BlazeFace back W8A8 · batch 1 · 1스레드</span><span>N=60 · 원시 표본 보존</span></div><div class="article-tools"><a href="../benchmarks.html#pr229086">벤치마크 전체 결과</a><a href="' + e(data['PR']['url']) + '">PR #229086 ↗</a><button type="button" data-print>' + icon('print') + '인쇄 / PDF</button></div></header>'
    body += '<nav class="archive-jump" aria-label="PR 벤치마크 목차"><a href="#clean">추론 시간</a><a href="#diagnostic">Add 진단</a><a href="#controls">A/A 대조</a><a href="#method">측정 방법</a><a href="#validation">출력·실행 검증</a><a href="#history">처음 12쌍</a><a href="#data">전체 수치·출처</a></nav>'
    body += '<section class="doc-section" id="clean"><div class="eyebrow">NO PROFILER / NO COUNTERS</div><h2>계측 없이 측정한 모델 추론 시간</h2><div class="pr229086-metrics"><div><small>전체 60쌍의 평균 wall</small><b>' + num(wall['mean_before'], 3) + ' → ' + num(wall['mean_after'], 3) + '</b><span>ms/추론 · 짧을수록 빠름</span></div><div><small>평균 wall의 역수</small><b>' + num(1000 / wall['mean_before'], 3) + ' → ' + num(1000 / wall['mean_after'], 3) + '</b><span>images/s · batch 1</span></div><div><small>쌍별 비율 주 집계 · 58쌍</small><b>' + pct(wall['primary']['time_reduction_percent']) + '</b><span>시간 감소율 · 감소 쌍 43/60</span></div></div><p>시간과 처리량은 60쌍 전체의 평균으로 표시했습니다. 대표 감소율은 각 쌍의 B/A 비율을 정렬한 뒤 양 끝에서 1쌍씩 제외한 산술평균으로 계산했습니다. 두 계산을 구분해 표시합니다.</p>'
    cpu = clean['user_cpu_separate']
    system = clean['system_cpu_separate']
    body += table(['지표', '이전 A', '변경 B', '단위 / 집계'], [
        ['추론 wall', num(wall['mean_before']), num(wall['mean_after']), 'ms/추론 · 전체 60쌍'],
        ['user CPU', num(cpu['mean_before']), num(cpu['mean_after']), 'ms/추론 · 전체 60쌍'],
        ['system CPU', num(system['mean_before_ms_per_inference'], 9), num(system['mean_after_ms_per_inference'], 9), 'ms/추론 · 0인 표본도 유지'],
        ['처리량', num(1000 / wall['mean_before']), num(1000 / wall['mean_after']), 'images/s · 1000 / 평균 wall'],
    ])
    body += '<p class="small-note">system CPU가 0인 쌍은 A 37개, B 38개입니다. 0을 다른 값으로 채우거나 system CPU 감소율을 계산하지 않았습니다. A/A에서는 user/system을 분리 수집하지 않았고 합계 CPU 시간만 남아 있습니다.</p>'
    body += plot(runs['clean-ab'], 'clean-ab', '모든 60쌍의 모델 추론 wall', 'ms/추론', 'times')
    body += plot(runs['clean-ab'], 'clean-ab', '모든 60쌍의 wall 시간 감소율', 'ms/추론')
    body += pair_table(runs['clean-ab'], 'clean-ab')
    body += '<h3>실행 순서와 전후반을 나누면</h3>'
    group_names = {'AB': 'AB · 이전 다음 변경', 'BA': 'BA · 변경 다음 이전', 'first_30': '처음 30쌍', 'last_30': '마지막 30쌍'}
    body += table(['구간', '쌍 수', 'A wall ms', 'B wall ms', '전체 쌍 평균 감소율', '감소 / 증가 쌍'], [[group_names[p['group']], str(p['n']), num(p['mean_before']), num(p['mean_after']), pct(p['time_reduction_percent'], 6), str(p['faster']) + ' / ' + str(p['slower'])] for p in wall['subgroups_all_pairs_untrimmed']])
    body += '<p>처음 30쌍은 평균 ' + pct(wall['subgroups_all_pairs_untrimmed'][2]['time_reduction_percent']) + ' 감소했고, 마지막 30쌍은 ' + pct(wall['subgroups_all_pairs_untrimmed'][3]['time_reduction_percent']) + '로 방향이 달랐습니다. 아래 블록 길이별 참고 범위도 함께 확인할 수 있습니다.</p><h3>집계 민감도와 블록 재표집</h3>'
    body += table(['각 꼬리 제외', '주 집계 쌍 수', '평균 B/A', '시간 감소율', '속도 배율', '네 구간을 감싼 참고 범위'], [[str(p['trim_each_tail']), str(p['pairs_kept']), num(p['mean_R'], 9), pct(p['time_reduction_percent'], 6), num(p['speed_ratio'], 9) + '×', ' ~ '.join(pct(x, 6) for x in p['envelope_of_four_time_reduction_intervals'])] for p in wall['sensitivity']])
    body += table(['연속 블록 길이', '재표집 수', '주 집계 감소율의 개별 95% 백분위 구간'], [[str(p['block_pairs']) + '쌍', f'{p["resamples"]:,}', ' ~ '.join(pct(x, 6) for x in p['time_reduction_95_percentile_interval'])] for p in wall['primary']['circular_block_bootstrap']])
    body += '<p class="small-note">참고 범위는 블록 2·4·6·10쌍의 개별 구간 중 최소 하한과 최대 상한입니다. 범위 자체를 하나의 95% 신뢰구간으로 표시하지 않습니다. 주 집계의 참고 범위에는 0이 포함됩니다. 표본은 모두 차트·표·CSV에 남아 있습니다.</p></section>'

    prof = diag['profile_summary']
    body += '<section class="doc-section" id="diagnostic"><div class="eyebrow">SEPARATE PROFILING RUN / DIAGNOSTIC REFERENCE</div><h2>모델 내부 Add의 진단 측정</h2><aside class="note pr229086-diagnostic"><strong>진단 참고값 · 프로파일 A/A 기준 미통과</strong>앞선 프로파일 A/A의 pooled CV는 5.411%로, 유지한 기준 5%를 넘었습니다. 이후 별도 요청으로 60쌍을 한 번 수집했습니다. 아래 Add 수치는 인과적 개선 근거로 사용하지 않습니다. 프로파일이 없는 위 모델 추론 측정과 구분합니다.</aside>'
    body += table(['같은 ORT 프로파일의 지표', '이전 A', '변경 B'], [
        ['Add 시간 · µs/추론', num(prof[0]['mean_add_us_per_inference']), num(prof[1]['mean_add_us_per_inference'])],
        ['model_run · µs/추론', num(prof[0]['mean_model_run_us_per_inference']), num(prof[1]['mean_model_run_us_per_inference'])],
        ['Add / 같은 profile model_run', num(prof[0]['add_share_of_same_profile_model_run_percent']) + '%', num(prof[1]['add_share_of_same_profile_model_run_percent']) + '%'],
        ['프로파일에서 집계한 추론 수', f'{prof[0]["inferences"]:,}', f'{prof[1]["inferences"]:,}'],
    ], '각 side의 추론 전체를 가중 집계한 평균 · 단순한 60개 블록 평균과 구분')
    body += '<p>진단 Add의 쌍별 비율 주 집계는 ' + pct(diag['descriptive_time_reduction_percent'], 6) + ' 시간 감소이며, 60쌍 모두 감소 방향이었습니다. Add에는 연산자·어댑터·프로파일러 비용이 포함됩니다. 분모는 같은 프로파일의 model_run입니다. 공통 비용을 임의로 빼지 않았습니다.</p>'
    body += plot(runs['diagnostic-add'], 'diagnostic-add', '진단 참고 · Add 시간 60쌍', 'µs/추론', 'times')
    body += plot(runs['diagnostic-add'], 'diagnostic-add', '진단 참고 · Add 시간 감소율 60쌍', 'µs/추론')
    body += pair_table(runs['diagnostic-add'], 'diagnostic-add')
    body += '<p class="small-note">프로파일의 user/system CPU는 A/B를 교차 실행한 전체 쌍의 공유 시간입니다. 각 side의 CPU 시간으로 나누지 않습니다. 이 자료에는 PMU/PMI 결과와 별도 커널 마이크로벤치가 없습니다.</p></section>'

    body += '<section class="doc-section" id="controls"><div class="eyebrow">UNCHANGED A/A GATES</div><h2>같은 이전 커널을 비교한 A/A 대조</h2><p>계측 없는 A/A는 정해 둔 대조 기준을 통과했습니다. 프로파일 Add A/A는 pooled CV 한 항목을 통과하지 못했습니다. 같은 A 커널을 두 side에 사용한 결과이며, 패치의 효과로 세지 않습니다.</p>'
    aa = runs['clean-aa']['stability']
    paa = runs['profile-aa']['stability']
    body += table(['A/A 항목', '계측 없음 · wall', '프로파일 · Add'], [
        ['원래 기하평균 속도 변화', pct(aa['geomean_paired_speedup_percent'], 6), pct(paa['geomean_paired_speedup_percent'], 6)],
        ['원래 쌍별 bootstrap 95% 구간', ' ~ '.join(pct(x, 6) for x in aa['paired_bootstrap_95ci_percent']), ' ~ '.join(pct(x, 6) for x in paa['paired_bootstrap_95ci_percent'])],
        ['pooled 표본 CV', num(aa['pooled_sample_cv_percent'], 6) + '% / 기준 3%', num(paa['pooled_sample_cv_percent'], 6) + '% / 기준 5%'],
        ['원래 A/A 종합 기준', '통과', '미통과 · pooled CV'],
    ], 'A/A의 원래 기하평균 판정 지표 · 위 주 집계의 산술평균 시간 감소율과 구분')
    rule_labels = [('absolute_geomean_percent', '기하평균 속도 변화의 절댓값', '≤ 1%', '≤ 2%'), ('ci_inside_equivalence_band', '원래 bootstrap 구간의 범위', '−2% ~ +2% 안', '−3% ~ +3% 안'), ('median_absolute_pair_percent', '쌍별 변화 절댓값의 중앙값', '≤ 2%', '≤ 3%'), ('maximum_absolute_pair_percent', '개별 쌍 변화 절댓값의 최댓값', '≤ 5%', '≤ 10%'), ('pooled_sample_cv', 'pooled 표본 CV', '≤ 3%', '≤ 5%')]
    body += '<details class="archive-details"><summary>그대로 유지한 A/A 기준 5개 모두 보기</summary>' + table(['기준', 'wall 기준 / 결과', 'Add 기준 / 결과'], [[label, low + ' · ' + ('통과' if aa['stability_checks'][key] else '미통과'), high + ' · ' + ('통과' if paa['stability_checks'][key] else '미통과')] for key, label, low, high in rule_labels]) + '</details>'
    body += plot(runs['clean-aa'], 'clean-aa', '동일 커널 A/A · wall 시간 감소율', 'ms/추론') + pair_table(runs['clean-aa'], 'clean-aa')
    body += plot(runs['profile-aa'], 'profile-aa', '동일 커널 프로파일 A/A · Add 시간 감소율', 'µs/추론') + pair_table(runs['profile-aa'], 'profile-aa')
    body += '</section>'

    body += '<section class="doc-section" id="method"><div class="eyebrow">EXPERIMENT DESIGN</div><h2>어떻게 측정했는가</h2><p><a href="' + e(data['PR']['url']) + '">PR #229086 · ' + e(data['PR']['title']) + '</a>는 widening bitcast 양옆의 고정 길이 셔플을 합성합니다. 이 실험은 제공된 전후 MLAS AVX2 QLinearAdd 커널 객체를 사용한 모델 내부 교체 실험입니다.</p><ol><li>ONNX Runtime 1.23.2의 CPUExecutionProvider와 ORT_ENABLE_ALL로 원래 모델을 한 번 최적화하고 그래프를 고정했습니다.</li><li>양자화 Add 31개의 domain/op만 어댑터 호출로 바꿨습니다. initializer 바이트는 동일하며, 교체 뒤 그래프를 다시 최적화하지 않았습니다.</li><li>같은 세션·입력·어댑터에서 전후 함수 포인터만 측정 구간 밖에서 선택했습니다. PC에서 LLVM·어댑터·ORT를 새로 컴파일하지 않았습니다.</li><li>각 variant를 최소 30회와 0.5초 동안 준비 실행했습니다. 계측 없는 측정은 side당 최소 0.5초인 연속 블록으로 60쌍을 실행했습니다. AB 다음 BA 순서를 반복했습니다.</li><li>프로파일은 한 번의 추론마다 side를 교차하고 시작 side를 바꿨습니다. 각 side의 누적 추론 시간은 최소 0.25초입니다. Add와 model_run을 같은 ORT 프로파일에서 집계했습니다.</li><li>대표 지표 R은 추론당 B/A 시간입니다. 모든 R을 정렬해 각 꼬리 1쌍만 주 집계에서 제외하고 산술평균을 냈습니다. 감소율은 100 × (1 − 평균 R), 속도 배율은 1 / 평균 R입니다.</li><li>wall의 원형 블록 bootstrap은 연속 2·4·6·10쌍, 짝수 시작 경계, 각 20,000회입니다. 매 재표집 안에서 꼬리 제외를 다시 적용했습니다. seed는 22908660 + 블록 길이입니다.</li></ol>'
    body += table(['환경', '조건'], [
        ['CPU / OS', 'AMD Ryzen 9 3900X · Ubuntu 26.04 · Linux 7.0.0-38'],
        ['CPU 배치', '1스레드 · affinity {4} · batch 1'],
        ['주파수 제어', 'amd-pstate-epp · boost OFF · performance governor · min=max 3,000,000 kHz'],
        ['관측 주파수', '부하 시 약 2.970 GHz · 각 측정 표본의 경계 주파수도 JSON에 보존'],
        ['런타임', 'Python 3.12.15 · ONNX Runtime 1.23.2 · ONNX 1.19.1 · NumPy 2.3.5'],
        ['입력', 'BlazeFace back W8A8 · uint8 [1, 3, 256, 256] · 같은 입력 배열'],
        ['교체 커널', 'MLAS QLinearAdd AVX2 · 같은 어댑터 · 이전/변경 객체'],
        ['계측 없는 추론', '프로파일 OFF · 호출 카운터 OFF · Python/ORT의 정상 호출 비용 포함'],
        ['프로파일 Add', '연산자 + 어댑터 + 프로파일러 비용 포함 · 동일 profile model_run이 분모'],
    ])
    body += '<h3>측정 순서 · 2026-10-22 KST</h3>' + table(['측정', '시작', '끝', '쌍 수'], [[LABELS[k], clock_time(runs[k]['manifest']['time_start_ns']), clock_time(runs[k]['time_end_ns']), '60'] for k in ['clean-aa', 'clean-ab', 'profile-aa', 'diagnostic-add']])
    body += '<p class="small-note">추가 진단을 위해 기존 clean 60쌍이나 A/A 60쌍을 다시 실행하지 않았습니다. A/A 기준을 바꾸거나 이상값을 버리지 않았습니다. 전체 ORT를 패치 컴파일러로 다시 빌드한 비교로 확대하지 않습니다.</p></section>'

    validation = data['validation']
    prep = data['preparation']
    counts = diag['actual_counts']
    body += '<section class="doc-section" id="validation"><div class="eyebrow">OUTPUT & EXECUTED KERNEL CHECKS</div><h2>출력과 실제 Add 실행 확인</h2><p>기준 입력과 seed 1·2의 제한된 입력 변형에서 두 출력이 모두 바이트 단위로 같았습니다. 원래 모델, 고정 그래프, 계측 유무와 전후 커널을 대조한 제공 기록입니다.</p>'
    labels = {'frozen_native': '고정 그래프·기본 커널', 'profile_library=False,variant=0': '계측 없음·이전', 'profile_library=False,variant=1': '계측 없음·변경', 'profile_library=True,variant=0': '계측·이전', 'profile_library=True,variant=1': '계측·변경'}
    body += table(['입력 seed', '비교 구성', '두 출력의 바이트 비교'], [[str(row['seed']), e(labels.get(comp['label'], comp['label'])), '동일' if comp['all_outputs_bitwise_equal'] else '다름'] for row in validation['rows'] for comp in row['comparisons']])
    body += table(['진단 profile의 실제 호출 계수', '기록값'], [['추론 수 · 양 side 합계', f'{counts["inferences"]:,}'], ['Add 호출 수', f'{counts["calls"]:,}'], ['원소 처리 수', f'{counts["elements"]:,}'], ['추론당 호출 / 원소', f'{counts["calls"] // counts["inferences"]} / {counts["elements"] // counts["inferences"]:,}'], ['scalar B 호출', str(counts['scalar_b'])]])
    body += '<p class="small-note">호출 카운터는 프로파일 실행에만 켰습니다. 계측 없는 추론 측정의 시간에서 이 카운터 비용을 빼거나 더하지 않았습니다.</p><details class="archive-details"><summary>교체한 Add 31개와 입력·출력 형상</summary>'
    shapes = data['Add_node_shapes']
    node_rows = []
    for node in prep['quantized_adds']:
        shape = shapes[node['name'] + '_kernel_time']
        describe = lambda items: ' · '.join(dtype + ' ' + str(dims) for item in items for dtype, dims in item.items())
        node_rows.append(['<code>' + e(node['name']) + '</code>', e(node['type']), e(describe(shape['input_type_shape'])), e(describe(shape['output_type_shape']))])
    body += table(['Add 노드', '종류', '입력 형상', '출력 형상'], node_rows) + '</details>'
    body += '<details class="archive-details"><summary>같은 어댑터에서 커널을 고르는 코드</summary><p>선택 함수는 측정 블록 밖에서 호출했습니다. 어댑터가 허용하는 broadcast는 전체 A와 전체 B 또는 scalar B입니다.</p><pre><code>' + e((root / 'content/benchmarks/pr229086/custom_add_switch.cpp.txt').read_text()) + '</code></pre><p><a href="' + ASSET + 'custom_add.cpp.txt" download>공통 어댑터 코드</a> · <a href="' + ASSET + 'custom_add_switch.cpp.txt" download>전후 선택 코드</a></p></details></section>'

    body += '<section class="doc-section" id="history"><div class="eyebrow">EARLIER 12-PAIR RECORDS / KEPT SEPARATE</div><h2>처음 12쌍의 기록</h2><p>처음 측정한 12쌍은 새 60쌍과 합치지 않았습니다. 초기 연속 블록 프로파일 A/A의 실패와, 교차 실행으로 한 번 바꾼 뒤의 A/A·A/B 기록도 남겼습니다.</p><details class="archive-details"><summary>처음 12쌍의 네 실행 전체 보기</summary>'
    history_rows = []
    for key in list(LABELS)[4:]:
        run = runs[key]
        stat = run['stability']
        unit = 'µs/추론 · Add' if run['manifest']['profile_enabled'] else 'ms/추론 · wall'
        verdict = ('통과' if stat['passed'] else '미통과') if run['manifest']['experiment'] == 'AA' else 'A/B 측정'
        history_rows.append([LABELS[key], num(stat['side_mean'][0]), num(stat['side_mean'][1]), unit, pct(stat['geomean_paired_speedup_percent'], 6), ' ~ '.join(pct(x, 6) for x in stat['paired_bootstrap_95ci_percent']), verdict])
    body += table(['실행', 'A 평균', 'B 평균', '단위', '원래 기하평균 속도 변화', '원래 쌍별 bootstrap 95% 구간', 'A/A 대조 상태'], history_rows)
    body += '<p class="small-note">이 표는 원보고의 기하평균 속도 변화입니다. 최신 60쌍의 산술평균 시간 감소율과 같은 지표로 합치지 않습니다. 초기 프로파일 A/A는 한 쌍의 약 16.04% 변화와 구간 범위 기준을 넘겼습니다. 원래 표본과 기준을 유지한 채 실행 교차 방식을 한 번 수정한 이력이 있습니다.</p>'
    for key in list(LABELS)[4:]:
        body += '<h3>' + LABELS[key] + '</h3>' + pair_table(runs[key], key)
    body += '</details></section>'

    body += '<section class="doc-section" id="data"><div class="eyebrow">ALL NUMERIC RECORDS / PROVENANCE</div><h2>전체 수치와 자료 범위</h2><p>각 N=60 실행 4개의 모든 쌍과, 초기 N=12 실행 4개의 원시 표본을 보존했습니다. JSON에는 총 576개의 측정 표본, 구간별 집계, 검증 결과와 그래프·입력·커널 식별 해시가 있습니다. 프로파일 표본은 같은 측정 표본에 Add/model_run 집계를 연결한 것이며 추가 관측 수로 세지 않습니다.</p><div class="article-tools review-downloads">'
    downloads = [('clean-60-pairs.csv', '추론 wall A/B · 60쌍 CSV'), ('aa-60-pairs.csv', 'wall A/A · 60쌍 CSV'), ('diagnostic-add-60-pairs.csv', '진단 Add A/B · 60쌍 CSV'), ('profile-aa-60-pairs.csv', '프로파일 A/A · 60쌍 CSV'), ('initial-12-pair-records.csv', '처음 12쌍 · 4개 실행 CSV'), ('summary.json', '전체 집계·표본·검증 JSON'), ('requirements.lock.txt', '측정 패키지 버전'), ('DATA-SCOPE.txt', '공개 자료 범위'), ('exports.json', '공개 파일 해시')]
    body += ''.join('<a href="' + ASSET + name + '" download>' + label + '</a>' for name, label in downloads) + '</div><p>자료 묶음에는 모델 가중치·인터프리터·전체 ORT 노드 trace와 상세 개별 추론 trace가 없습니다. 제공된 입력 배열과 바이너리는 이 공개 사이트에 넣지 않았습니다. 아래에는 식별 해시를 남겼습니다. 서버 절대 경로와 실행 중 커널 주소는 공개 파일에서 제외했습니다.</p>'
    body += '<p class="small-note">REPRODUCE.txt의 초기 안내에는 MobileNet 실험도 언급됩니다. 이번 폴더에서 관측 행을 확인한 실행은 BlazeFace 1스레드입니다. MobileNet의 모델 출처를 BlazeFace 측정 결과로 합산하지 않았습니다. 최신 Add 진단 상태는 n60-with-diagnostic-summary.json을 기준으로 반영했습니다.</p>'
    identity_rows = [['raw 모델', data['frozen_graph']['raw_sha256']], ['고정 그래프', prep['frozen_sha256']], ['Add 교체 그래프', prep['custom_sha256']], ['측정 입력 배열', prep['input_sha256']]] + [[name, record['sha256']] for name, record in data['binary_identity'].items()]
    body += '<details class="archive-details"><summary>모델·입력·전후 커널 식별 해시</summary>' + table(['대상', 'SHA-256'], [[e(name), '<code class="review-hash">' + e(value) + '</code>'] for name, value in identity_rows]) + '<h3>BlazeFace 모델 출처</h3><ul>'
    for source in data['model_sources']:
        if source.get('url') and 'blazeface' in source['filename']:
            body += '<li><a href="' + e(source['url']) + '">Qualcomm MediaPipe Face Detector · 고정 revision 원본</a><code class="review-hash">' + e(source['sha256']) + '</code></li>'
    body += '</ul></details><details class="archive-details"><summary>제공된 원자료 파일 목록과 해시</summary><p>이 목록은 대조한 원본 파일의 상대 이름입니다. 모든 원본 파일을 웹 다운로드로 제공하는 목록은 아닙니다.</p>' + table(['원자료 상대 이름', '크기 (bytes)', 'SHA-256'], [[e(s['name']), f'{s["bytes"]:,}', '<code class="review-hash">' + e(s['sha256']) + '</code>'] for s in data['source_files']]) + '</details><p class="small-note">원자료: pr229086-benchmark. 이 페이지를 만들며 추론·벤치마크를 다시 실행하지 않았습니다. 앞의 42개 입력 관측값이나 원래 차트도 변경하지 않았습니다.</p></section></article>'
    (root / 'docs/benchmarks/pr229086.html').write_text(wrap('PR 229086 · BlazeFace 모델 추론 벤치마크', body, '../', active='benchmarks', main_class='archive-main', edited=PUBLISHED, description='PR 229086 BlazeFace 1스레드 60쌍 추론 벤치마크: 계측 없는 wall, 진단 Add, A/A 대조, 원시 수치와 검증 근거.'))
