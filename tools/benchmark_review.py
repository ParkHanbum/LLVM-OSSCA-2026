"""Shared presentation of the completed paired-data review and attribution."""
import csv
import json
from collections import Counter
from html import escape

LABELS = {
    'decrease': '평균 감소 방향 유지',
    'increase': '평균 증가 방향 유지',
    'mixed': '순서·구간 확인 필요',
}
ASSET = 'assets/benchmarks/review/'


def e(value):
    return escape(str(value), quote=True)


def pct(value):
    return ('+' if value >= 0 else '−') + f'{abs(value):.3f}%'


def load(root):
    source = root / 'content/benchmarks/review'
    review = json.loads((source / 'repeat-analysis.json').read_text())
    links = json.loads((source / 'contribution-links.json').read_text())
    with (source / 'paired-observations.csv').open(encoding='utf-8-sig', newline='') as handle:
        flags = {(p['mode'], p['case_id'], int(p['pair'])): p['retained_in_main_trim'] == 'True' for p in csv.DictReader(handle)}
    return review, links, flags


def owner_refs(links, row):
    groups = []
    for author, identities in row['author_PRs'].items():
        refs = []
        for identity in identities:
            pr = links['PRs'][identity]
            refs.append('<a href="' + e(pr['url']) + '" title="' + e(pr['title']) + '">' + e(pr['label']) + '</a>')
        groups.append('<span class="review-owner">' + e(author) + ' ' + ' · '.join(refs) + '</span>')
    return '<br>'.join(groups)


def summary_counts(review):
    counts = Counter(r['direction_in_this_run'] for r in review['results'])
    return '<div class="review-counts" aria-label="이번 기록의 평균 방향">' + ''.join(
        '<div class="review-' + key + '"><b>' + str(counts[key]) + '<span>개 입력</span></b><strong>' + LABELS[key] + '</strong></div>'
        for key in ['decrease', 'increase', 'mixed']) + '</div><p class="small-note">AB·BA 실행 순서, 측정 전반·후반, 0/1/2쌍 제외 집계와 벤치별 재표집 참고 구간을 함께 확인했습니다. 이 분류는 이번 기록 안의 평균 방향입니다. 모든 개별 쌍에서 같은 결과가 나왔다는 뜻은 아닙니다.</p>'


def representatives(review, links, target='benchmarks.html#case-'):
    by_case = {r['case_id']: r for r in review['results']}
    linked = {r['case_id']: r for r in links['cases']}
    identities = ['png-photo-gray4-aloe-1282x1110', 'sqlite-json', 'duckdb-parquet', 'duckdb-datepart']
    result = '<div class="review-cards">'
    for identity in identities:
        row, contribution = by_case[identity], linked[identity]
        result += '<article class="review-card"><small>' + e(contribution['display_label']) + '</small><b>' + pct(row['reported_trim1_reduction']) + '</b><strong>user CPU 시간 감소 · ' + str(row['faster_pairs']) + '/' + str(row['pairs']) + '쌍</strong><p>' + owner_refs(links, contribution) + '</p><p class="review-path"><code>' + e(contribution['execution_summary']) + '</code></p><small>AB ' + pct(row['by_order']['AB']) + ' / BA ' + pct(row['by_order']['BA']) + '<br>전반 ' + pct(row['by_half'][0]) + ' / 후반 ' + pct(row['by_half'][1]) + '</small><a class="review-detail-link" href="' + e(target + identity) + '">모든 반복 측정과 실행 경로 ↗</a></article>'
    return result + '</div>'


def contribution_section(links, target='benchmarks.html#case-', section_id='mentee-bench-links'):
    html = '<section class="doc-section review-contributions" id="' + e(section_id) + '"><div class="eyebrow">MENTEE / PR / EXECUTED CHANGE</div><h2>어떤 멘티의 기여와 연결되는가</h2><p>평균 감소 방향이 유지된 12개 입력은 멘티 4명의 PR 7개와 연결됩니다. 작성자는 개인 최종보고서와 팀 보고서로 대조했습니다. PR과 실행 경로는 원본 검증표의 변경 함수·명령 기록으로 연결했습니다.</p><p>감소율은 해당 입력을 수행한 패치 빌드의 관측값입니다. 여러 PR이 함께 관련된 입력은 공동 영향으로 표시했습니다. 관련 PR이 하나인 입력도 그 PR만의 속도 기여율을 분리해 측정한 결과는 아닙니다.</p><div class="article-tools"><a href="' + ASSET + 'contribution-links.csv" download>멘티·PR·벤치 연결표 CSV</a><a href="' + ASSET + 'contribution-links.json" download>연결 근거 JSON</a></div><div class="table-wrap review-link-table"><table><caption>user CPU 시간 감소율은 원보고 주 집계 · 감소 쌍 수는 원시 쌍 전체</caption><thead><tr><th scope="col">입력</th><th scope="col">감소율 / 감소 쌍</th><th scope="col">멘티 · PR</th><th scope="col">실행 확인 경로 / 영향 범위</th></tr></thead><tbody>'
    for row in links['cases']:
        scope = row['relationship'] + (' · 파생 코드 변화' if row['derived_code_change'] else '')
        html += '<tr data-contribution-case="' + e(row['case_id']) + '"><th scope="row"><a href="' + e(target + row['case_id']) + '">' + e(row['display_label']) + '</a><small>' + e(row['input']) + '</small></th><td class="review-number">' + pct(row['reduction']) + '<br>' + str(row['faster_pairs']) + '/' + str(row['pairs']) + '쌍</td><td>' + owner_refs(links, row) + '</td><td><code>' + e(row['execution_summary']) + '</code><small>' + e(scope) + '</small></td></tr>'
    html += '</tbody></table></div><p class="small-note">포크 #2는 최진범의 <a href="https://github.com/ThePo1es/llvm-project/pull/2">ThePo1es/llvm-project PR #2</a>입니다. 같은 압축 라이브러리를 호출하는 Node·DuckDB·Brotli의 경로를 독립적인 알고리즘 개선 수로 더하지 않습니다.</p><details class="archive-details review-pr-details"><summary>PR 7개의 변경 내용과 작성자 대조 근거</summary><div class="review-pr-list">'
    for pr in sorted(links['PRs'].values(), key=lambda p: (p['author'], int(p['id']))):
        html += '<article><h3>' + e(pr['author']) + ' <a href="' + e(pr['url']) + '">' + e(pr['label']) + '</a></h3><p>' + e(pr['short_description']) + '</p><small>' + e(pr['author_source']) + '</small></article>'
    html += '</div></details><p class="small-note">OpenSSL KDF는 암호 처리와 결과 서식 경로가 함께 포함됩니다. Brotli·GMP의 파생 코드 변화는 각각 스택 저장 명령과 스택 크기 변화입니다. 압축·제곱근 알고리즘을 새로 작성한 효과로 설명하지 않습니다.</p></section>'
    return html


def pair_chart(row):
    values = row['pair_reductions']
    low, high = min(0., min(values)), max(0., max(values))
    span = max(high - low, .1)
    low -= span * .12
    high += span * .12
    left, right, top, bottom = 68, 892, 20, 198
    xx = lambda i: left + i * (right - left) / (len(values) - 1)
    yy = lambda value: bottom - (value - low) / (high - low) * (bottom - top)
    identity = 'pair-chart-' + row['case_id']
    parts = ['<figure class="review-chart"><div class="review-plot-scroll" tabindex="0" aria-label="쌍별 차트. 좁은 화면에서는 가로로 스크롤할 수 있습니다."><svg viewBox="0 0 920 250" role="img" aria-labelledby="' + identity + '-title ' + identity + '-desc"><title id="' + identity + '-title">' + e(row['project']) + ' · 원시 측정 ' + str(row['pairs']) + '쌍 전체</title><desc id="' + identity + '-desc">측정 순서에 따른 user CPU 시간 감소율입니다. 양수는 시간 감소입니다. 채운 점은 AB, 빈 점은 BA 순서입니다. 정확한 값은 아래 모든 쌍 표에 있습니다.</desc><rect width="920" height="250" fill="#fff"/>']
    for tick in range(5):
        value = low + (high - low) * tick / 4
        y = yy(value)
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#e0e3dc" stroke-width="1"/><text x="59" y="{y+4:.2f}" text-anchor="end">{value:.2f}%</text>')
    parts.append(f'<line x1="{left}" y1="{yy(0):.2f}" x2="{right}" y2="{yy(0):.2f}" stroke="#657078" stroke-width="1.1"/>')
    points = ' '.join(f'{xx(i):.2f},{yy(value):.2f}' for i, value in enumerate(values))
    parts.append('<polyline points="' + points + '" fill="none" stroke="#b1b9b5" stroke-width=".9"/>')
    for i, (value, order, times) in enumerate(zip(values, row['pair_orders'], row['pair_cpu_seconds'])):
        fill, stroke = ('#28715f', '#28715f') if order == 'AB' else ('#fff', '#a13d28')
        tip = f'{i+1}쌍 · {order} · {pct(value)} · A {times[0]:.6f}s / B {times[1]:.6f}s'
        parts.append(f'<circle class="review-point" cx="{xx(i):.2f}" cy="{yy(value):.2f}" r="3.2" fill="{fill}" stroke="{stroke}" stroke-width="1.3"><title>{e(tip)}</title></circle>')
    for i in [0, len(values) // 2 - 1, len(values) - 1]:
        parts.append(f'<text x="{xx(i):.2f}" y="220" text-anchor="middle">{i+1}</text>')
    parts.append('<text x="480" y="243" text-anchor="middle">측정 쌍 순서 · 양수: 시간 감소 / 음수: 시간 증가</text></svg></div><figcaption><span class="review-marker-ab">● AB</span> A 다음 B 실행 <span class="review-marker-ba">○ BA</span> B 다음 A 실행 · 점은 모든 원시 쌍, 선은 측정 순서 연결입니다.</figcaption></figure>')
    return ''.join(parts)


def pair_table(row, flags, mode='AB'):
    html = '<details class="archive-details review-pair-table"><summary>모든 ' + str(row['pairs']) + '쌍의 수치 보기 · 제외 없음</summary><div class="table-wrap"><table><caption>CSV의 0번 쌍을 웹에서는 1번으로 표시합니다. 원보고 포함 여부와 관계없이 모든 쌍을 표시합니다.</caption><thead><tr><th scope="col">쌍</th><th scope="col">순서</th><th scope="col">A user (초)</th><th scope="col">B user (초)</th><th scope="col">감소율</th><th scope="col">원보고 주 집계</th></tr></thead><tbody>'
    for i, (value, order, times) in enumerate(zip(row['pair_reductions'], row['pair_orders'], row['pair_cpu_seconds'])):
        retained = flags[(mode, row['case_id'], i)]
        html += '<tr><th scope="row">' + str(i + 1) + '</th><td>' + order + '</td><td>' + f'{times[0]:.6f}' + '</td><td>' + f'{times[1]:.6f}' + '</td><td>' + pct(value) + '</td><td>' + ('포함' if retained else '꼬리 제외') + '</td></tr>'
    return html + '</tbody></table></div></details>'


def case_details(row, links, flags):
    failure = []
    checks = row['consistency_checks']
    if not checks['AB_and_BA_same_direction']:
        failure.append('AB와 BA의 평균 방향이 다릅니다.')
    if not checks['first_and_second_half_same_direction']:
        failure.append('전반과 후반의 평균 방향이 다릅니다.')
    if not checks['trim0_1_2_same_direction']:
        failure.append('꼬리 제외 수에 따라 평균 방향이 달라집니다.')
    if not checks['interval_excludes_zero']:
        failure.append('재표집 참고 구간에 0이 포함됩니다.')
    if not failure:
        failure.append('실행 순서·전후반·꼬리 제외 수와 참고 구간에서 평균 방향이 유지됐습니다.')
    html = '<div class="review-case-data"><h4>원시 쌍 재검토 · 2026-10-18</h4><p>시간 감소 ' + str(row['faster_pairs']) + '/' + str(row['pairs']) + '쌍 · 시간 증가 ' + str(row['slower_pairs']) + '쌍 · 동일 ' + str(row['equal_pairs']) + '쌍. ' + ' '.join(failure) + '</p>'
    connected = next((r for r in links['cases'] if r['case_id'] == row['case_id']), None)
    if connected:
        html += '<p class="review-case-owner">' + owner_refs(links, connected) + '<br><code>' + e(connected['execution_summary']) + '</code> · ' + e(connected['relationship']) + (' · 파생 코드 변화' if connected['derived_code_change'] else '') + '</p>'
    html += pair_chart(row)
    facts = [
        ('원보고 감소율 · 각 꼬리 1쌍 제외', pct(row['reported_trim1_reduction'])),
        ('전체 쌍 평균 · 제외 없음', pct(row['all_pairs_reduction'])),
        ('AB / BA 평균', pct(row['by_order']['AB']) + ' / ' + pct(row['by_order']['BA'])),
        ('전반 / 후반 평균', pct(row['by_half'][0]) + ' / ' + pct(row['by_half'][1])),
        ('양 끝 0 / 1 / 2쌍 제외', ' / '.join(pct(x) for x in row['trim_sensitivity'])),
        ('연속 시간 구간별 평균', ' / '.join(pct(x) for x in row['time_block_reductions'])),
        ('재표집 참고 범위', ' ~ '.join(pct(x) for x in row['interval_envelope'])),
        ('블록 길이별 95% 구간', ' · '.join(str(c['block_length']) + '쌍: ' + pct(c['low']) + ' ~ ' + pct(c['high']) for c in row['block_intervals'])),
        ('elapsed 전체 쌍 평균 감소율 · 보조 지표', pct(row['elapsed_all_pairs_reduction'])),
    ]
    html += '<details class="archive-details"><summary>순서별 집계·집계 민감도·재표집 구간</summary><dl class="review-facts">' + ''.join('<dt>' + e(k) + '</dt><dd>' + e(v) + '</dd>' for k, v in facts) + '</dl></details>'
    return html + pair_table(row, flags) + '</div>'


def methods(review, flags):
    html = '<div class="review-method"><h3>벤치별 반복 측정을 다시 읽은 방법</h3><p>원보고의 공통 약 2.56% 기준은 A/A 대조 중 최대 쌍 비율 표준편차 0.8533%의 3배입니다. 개별 쌍의 흔들림과 평균의 불확실성은 다릅니다. 이번에는 각 입력의 모든 쌍을 사용해 평균 방향이 실행 순서와 시간 구간에 따라 달라지는지 확인했습니다.</p><ol><li>원시 관측 5,080행과 쌍별 비율 2,540행을 대조했습니다. 모든 A/B CPU 시간, 입력·쌍 번호·실행 순서, 기대 반환 코드와 최종 집계를 확인했습니다.</li><li>주 지표는 user CPU 시간의 쌍별 비율 R = B/A입니다. 감소율은 100 × (1 − 비율의 산술평균)입니다. 화면의 대표 감소율은 원보고와 같은 각 꼬리 1쌍 제외 집계를 유지했습니다.</li><li>안정성 검토에는 제외하지 않은 원시 쌍 전체를 썼습니다. AB·BA 순서별 평균과 전반·후반 평균, 양 끝 0/1/2쌍 제외 집계의 방향을 비교했습니다.</li><li>연속 2·4·6·10쌍을 묶는 원형 블록 재표집을 각각 20,000회 수행했습니다. 시작 위치를 두 쌍의 경계로 맞춰 AB/BA 균형과 인접 측정의 순서를 보존했습니다. 각 95% 백분위 구간 중 최소 하한과 최대 상한을 참고 범위로 표시했습니다.</li><li>참고 범위가 0의 한쪽에 있고, AB·BA·전후반·0/1/2쌍 제외 집계가 모두 같은 방향일 때 평균 방향 유지로 요약했습니다.</li></ol><p class="small-note">자료를 받은 뒤 수행한 사후 안정성 분석입니다. 벤치별 탐색적 참고 구간이며 42항목의 동시 검정 보정이나 독립 재실행을 대신하지 않습니다. 블록 길이마다 얻은 구간을 합친 범위는 단일 95% 신뢰구간으로 표시하지 않습니다. <a href="https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm">NIST 쌍별 관측 분석</a>과 <a href="https://www.nist.gov/publications/calculation-uncertainty-mean-autocorrelated-measurements?pub_id=151800">자기상관과 평균 불확실성 설명</a>을 참고했습니다.</p><h3>동일 실행 파일 A/A 대조</h3><p>같은 A 실행 파일끼리 비교한 세 대조 입력은 재표집 참고 범위에 모두 0이 포함됐습니다. 각 20쌍을 따로 확인할 수 있습니다.</p><div class="table-wrap"><table><thead><tr><th scope="col">입력</th><th scope="col">전체 쌍 평균 감소율</th><th scope="col">재표집 참고 범위</th><th scope="col">쌍 수</th></tr></thead><tbody>'
    for row in review['AA_controls']:
        html += '<tr><th scope="row">' + e(row['case_id']) + '</th><td>' + pct(row['all_pairs_reduction']) + '</td><td>' + ' ~ '.join(pct(x) for x in row['interval_envelope']) + '</td><td>' + str(row['pairs']) + '</td></tr>'
    html += '</tbody></table></div>'
    for row in review['AA_controls']:
        html += '<h4>' + e(row['project']) + ' · ' + e(row['input']) + '</h4>' + pair_table(row, flags, 'AA')
    return html + '</div>'


def downloads():
    files = [('repeat-summary.csv', '42개 입력 재검토 CSV'), ('contribution-links.csv', '멘티·PR 연결 CSV'), ('paired-observations.csv', '2,540쌍 수치 CSV'), ('raw-measurements.csv', '원시 관측 수치 5,080행 CSV'), ('repeat-analysis.json', '재검토 전체 JSON'), ('export-info.json', '공개 열·단위·해시 정보')]
    return '<div class="article-tools review-downloads">' + ''.join('<a href="' + ASSET + name + '" download>' + label + '</a>' for name, label in files) + '</div>'


def provenance(review):
    return '<details class="archive-details"><summary>원자료 대조와 파일 SHA-256</summary><p>원시 CPU 시간으로 다시 계산한 2,540개 쌍별 비율이 원본과 일치했습니다. 42개 입력의 0/1/2쌍 제외 집계도 재현했습니다. 집계 감소율의 최대 부동소수점 차이는 약 2.22 × 10⁻¹⁴ 퍼센트포인트입니다. 새 측정은 실행하지 않았고 원시 파일을 변경하지 않았습니다.</p><ul>' + ''.join('<li>' + e(s['name']) + '<code class="review-hash">' + e(s['sha256']) + '</code></li>' for s in review['sources']) + '</ul></details>'
