"""Render the application archive with the October 18 raw-data review."""
import benchmark_review as review_page
import build_pr229086
from benchmark_review import e, pct


def build(root, data, wrap, icon, *, table, figure, header, script_json):
    review, links, flags = review_page.load(root)
    originals = {c['case_id']: c for c in data['conditions']}
    rows = review['results']
    by_id = {r['case_id']: r for r in rows}
    asset = 'assets/benchmarks/'
    body = '<article class="article archive-article">' + header(
        '벤치마크 전체 결과',
        '실제 입력의 반복 측정값과 실행된 변경을 함께 모았습니다.<br>벤치별 재검토 결과에서 멘티의 PR과 실행 경로까지 이어서 확인할 수 있습니다.',
        ['기존 입력 측정 2026-10-16 · 재검토 2026-10-18', 'PR 229086 실험 추가 2026-10-22', 'Ryzen 9 3900X'],
        tools='<button type="button" data-print>' + icon('print') + '인쇄 / PDF</button>')
    body += '<nav class="archive-jump" aria-label="벤치마크 목차"><a href="#pr229086">PR 229086 · 새 실험</a><a href="#overview">42개 입력 재검토</a><a href="#mentee-bench-links">멘티·PR 연결</a><a href="#all-cases">42개 입력 전체</a><a href="#method">측정·재검토 방법</a><a href="#earlier-studies">이전 실험</a><a href="#evidence">수치 다운로드</a></nav>'
    body += build_pr229086.entry(build_pr229086.load(root))
    body += '<div class="archive-stat-grid"><div><b>42</b><span>실제 패치 비교 입력</span><small>27개 주 분석 프로젝트 + OpenCV 별도</small></div><div><b>2,480</b><span>A/B 측정 쌍 전체</span><small>동일 실행 파일 A/A 대조 60쌍은 별도</small></div><div><b>5,080</b><span>대조한 원시 관측 행</span><small>숫자 열·쌍별 비율·재검토 집계 다운로드</small></div></div>'
    body += '<section class="doc-section" id="overview"><div class="eyebrow">2026-10-18 / PAIRED OBSERVATION REVIEW</div><h2>선정한 입력에서 관측한 변화</h2><p>추가 제공된 원시 측정으로 42개 입력을 다시 검토했습니다. 대표 감소율은 원보고의 주 집계입니다. 실행 순서·측정 전후반·집계 방식과 벤치별 참고 구간을 함께 확인해 이번 기록 안의 평균 방향을 정리했습니다.</p>'
    body += review_page.representatives(review, links, '#case-')
    body += review_page.summary_counts(review)
    body += '<aside class="note"><strong>수치를 읽는 방법</strong>양수는 user CPU 시간 감소, 음수는 시간 증가입니다. 대표 감소율은 각 꼬리 1쌍을 제외한 B/A 비율의 산술평균으로 계산했습니다. 감소 쌍 수와 AB·BA·전후반 비교는 모든 원시 쌍을 사용했습니다. 같은 분류 안에서도 SQLite 59/60쌍과 Hyperscan 35/60쌍처럼 개별 쌍의 결과는 다릅니다.</aside>'
    body += '<h3>시간이 늘어난 결과도 함께 확인</h3><div class="review-regressions">'
    for identity in ['bzip2-source-decode', 'jpegxl-lossless']:
        row = by_id[identity]
        body += '<article><strong>' + e(row['project']) + '</strong><b>' + pct(row['reported_trim1_reduction']) + '</b><p>' + str(row['slower_pairs']) + '/' + str(row['pairs']) + '쌍에서 user CPU 시간 증가</p><a href="#case-' + e(identity) + '">입력과 모든 반복 측정 ↓</a></article>'
    body += '</div><p class="small-note">42개 조건 모두 선택한 PR로 달라진 기계어가 실제 입력에서 실행됐고 A/B 출력 검증을 통과한 조건입니다. 여러 PR과 공유 라이브러리의 영향이 함께 들어 있습니다. 패치 빌드의 관측값을 개별 PR의 단독 속도 기여율로 나누지 않습니다.</p>'
    body += '<details class="archive-details"><summary>원보고의 목록별 평균·선정 원칙·원래 요약 차트 3개</summary><p>원보고 기준 관측 평균은 PR 영향 범위 우선 20개 프로젝트 +0.334% (1.00335×), 처리 성능 영향 가능성 우선 20개 프로젝트 +0.155% (1.00155×)입니다. 두 목록 중 13개가 겹칩니다. 합집합 27개의 동일 가중 관측 평균은 +0.112%입니다. OpenCV 2조건과 libarchive USTAR 생성의 순회 준비 기능은 프로젝트 평균에서 제외했습니다.</p><p>A/B 시간은 조건별 평균의 산술평균이며, 프로젝트·목록 감소율에는 비율의 기하평균을 사용했습니다. 이 집계는 각 입력에서 쌍별 비율의 산술평균을 쓰는 방식과 구분합니다. 목록은 측정 결과를 얻기 전에 고정했습니다.</p>'
    for name, label in [('pr_breadth', 'PR 영향 범위 우선'), ('processing_potential', '처리 성능 영향 가능성 우선')]:
        body += '<h4>' + label + '</h4><p>' + ' · '.join(e(v) for v in data['selection']['cohorts'][name]) + '</p>'
    body += '<p>목록 고정 시점(UTC): <code>' + e(data['selection']['frozen_utc']) + '</code>. 첫 목록은 실행된 변경과 관련된 PR의 다양성, 둘째 목록은 코덱·문자열·DB·암호 등의 처리 특성을 기준으로 삼았습니다.</p><p class="small-note">아래 원래 차트에는 당시의 공통 잡음 기준과 판정이 남아 있습니다. 현재의 벤치별 평균 방향 재검토는 위 요약과 아래 입력별 표를 봐 주세요.</p>'
    for filename, title in [('01-pr_breadth.svg', 'PR 영향 범위 우선 20개 프로젝트'), ('02-processing_potential.svg', '처리 성능 영향 가능성 우선 20개 프로젝트'), ('03-all-features.svg', '42개 입력의 원래 집계 전체')]:
        body += figure(asset + 'charts/' + filename, title, '2026-10-16 원보고 차트 · 당시 공통 기준의 표기 보존')
    body += '</details></section>'
    body += review_page.contribution_section(links, '#case-')
    body += '<section class="doc-section" id="all-cases"><div class="eyebrow">ALL 42 INPUT CONDITIONS</div><h2>모든 입력의 수치와 반복 측정 차트</h2><p>프로젝트·멘티 이름·PR 번호·함수로 검색할 수 있습니다. 평균 방향 필터는 2026-10-18 재검토 기준입니다. 각 입력에는 모든 원시 쌍의 새 차트와 수치표, 원래 차트와 검증 기록을 함께 실었습니다.</p>'
    body += '<div class="archive-filter" data-archive-filter><label>검색<input type="search" data-archive-search placeholder="예: 최진범, 214933, Parquet" aria-label="벤치마크 검색"></label><label>프로젝트<select data-archive-project><option value="">전체 프로젝트</option>' + ''.join('<option>' + e(v) + '</option>' for v in sorted({r['project'] for r in rows})) + '</select></label><label>이번 기록의 평균 방향<select data-archive-status><option value="">전체 입력</option>' + ''.join('<option value="' + key + '">' + label + '</option>' for key, label in review_page.LABELS.items()) + '</select></label><button type="button" data-archive-reset>초기화</button><span data-archive-count aria-live="polite">42 / 42</span></div>'
    table_rows = []
    for row in rows:
        case = originals[row['case_id']]
        direction = row['direction_in_this_run']
        table_rows.append(['<a href="#case-' + e(row['case_id']) + '">' + e(row['project']) + '</a><small>' + e(case['feature']) + '</small>', f'{case["user"]["A"]:.6f}', f'{case["user"]["B"]:.6f}', '<span class="review-number review-' + direction + '">' + pct(row['reported_trim1_reduction']) + '</span>', str(row['faster_pairs']) + '/' + str(row['pairs']), '<span class="review-status review-' + direction + '">' + review_page.LABELS[direction] + '</span>'])
    body += '<div class="review-all-table">' + table(['프로젝트 / 입력', 'A user (초)', 'B user (초)', '원보고 감소율', '감소 쌍 / 전체', '이번 기록의 평균 방향'], table_rows, 'A/B 시간은 원보고 주 집계 · 감소 쌍 수는 제외 없는 원시 쌍 전체', row_ids=[r['case_id'] for r in rows]) + '</div><p class="small-note">감소율은 쌍별 비율의 평균으로 계산합니다. 표의 A/B 집계 시간을 단순히 나눈 값과 다를 수 있습니다. 모든 쌍의 정확한 수치는 각 입력의 표와 CSV에서 확인할 수 있습니다.</p><p class="archive-empty" data-archive-empty hidden>조건에 맞는 결과가 없습니다. 검색어나 필터를 바꿔 보세요.</p>'
    search = []
    for i, row in enumerate(rows, 1):
        case = originals[row['case_id']]
        direction = row['direction_in_this_run']
        known = [links['PRs'][identity] for identity in case['PR_transformations'] if identity in links['PRs']]
        authors = ' '.join(pr['author'] for pr in known)
        search.append({'id': row['case_id'], 'project': row['project'], 'status': direction, 'text': ' '.join([row['project'], row['case_id'], case['feature'], case['PRs'], case['scope'], authors] + [f.get('function', '') for f in case['functions']])})
        body += '<article class="archive-case" id="case-' + e(row['case_id']) + '" data-archive-case="' + e(row['case_id']) + '"><header><div><small>INPUT ' + str(i).zfill(2) + ' / 42</small><h3>' + e(row['project']) + '</h3><p>' + e(case['feature']) + '</p></div><div><span class="review-status review-' + direction + '">' + review_page.LABELS[direction] + '</span><b class="archive-change review-' + direction + '">' + pct(row['reported_trim1_reduction']) + '</b></div></header>'
        body += review_page.case_details(row, links, flags)
        body += '<details class="archive-details"><summary>원보고 차트·측정 조건·실행된 변경·검증 기록</summary><p><strong>2026-10-16 당시 공통 기준의 판정:</strong> ' + e(case['verdict']) + '</p><p class="small-note">원래 판정과 차트 표기는 기록으로 보존했습니다. 위의 평균 방향은 2026-10-18 원시 쌍 재검토 결과입니다.</p>'
        body += figure(asset + 'charts/' + case['chart'], row['project'] + ' ' + case['feature'] + '의 원래 차트', str(case['pairs']) + '쌍 측정 · 원보고 주 집계 ' + str(case['used_pairs']) + '쌍 · ' + case['repetitions'])
        body += '<p><strong>실행 영향 범위:</strong> ' + e(case['scope']) + '</p><p><strong>집계:</strong> ' + ('별도 기능 표 · 프로젝트 평균 제외' if case['mean_role'] == 'feature appendix' else '프로젝트 평균 포함') + ' · 쌍 비율 CV ' + f'{case["pair_cv"]:.3f}%' + ' · B/A ' + f'{case["ratio"]:.7f}' + ' · 배율 ' + f'{case["speedup"]:.6f}' + '×</p>'
        body += table(['지표', 'A', 'B'], [[label, f'{case[key]["A"]:.6f} s', f'{case[key]["B"]:.6f} s'] for key, label in [('user', 'user CPU'), ('system', 'system CPU'), ('elapsed', '명령 실행 elapsed')]])
        body += table(['각 꼬리에서 제외한 쌍 수', 'user CPU 시간 감소율'], [[str(n), f'{v:+.4f}%'] for n, v in enumerate(case['sensitivity'])])
        body += '<h4>변경 함수에 관련된 PR</h4><ul>'
        for number, pr in case['PR_transformations'].items():
            author = links['PRs'].get(number, {}).get('author')
            label = ('포크 #2' if number == '2' else 'PR #' + number)
            body += '<li>' + (e(author) + ' · ' if author else '') + '<a href="' + e(pr['url']) + '">' + e(label) + '</a> · ' + e(pr['title']) + '</li>'
        body += '</ul><p class="small-note">작성자 이름은 최종보고서로 대조한 PR에 표시했습니다. 관련 PR 목록은 단독 속도 기여율을 뜻하지 않습니다.</p>'
        body += table(['관련 PR', '함수 / 심벌', '실행된 변경 명령 또는 확인 내용'], [[e(f.get('pr', '')), '<code>' + e(f.get('function') or f.get('symbol', '')) + '</code>', '<code>' + e(f.get('changed_operation_or_instruction', '')) + '</code>'] for f in case['functions']])
        body += '<p><strong>검증 방식(원문):</strong> ' + e(case['verification']) + '</p><h4>검증 근거의 원래 파일 식별자</h4><ul class="archive-identifiers">' + ''.join('<li><code>' + e(v) + '</code></li>' for v in case['evidence']) + '</ul><p class="small-note">위 목록은 원래 검증표의 상대 경로입니다. 해당 경로를 사이트의 다운로드 링크로 표시하지 않았습니다. 공개한 쌍별·관측별 수치는 아래 자료 범위에서 받을 수 있습니다.</p></details></article>'
    body += '<script type="application/json" id="archive-search-data">' + script_json(search) + '</script></section>'
    body += '<section class="doc-section" id="method"><div class="eyebrow">MEASUREMENT & REVIEW METHOD</div><h2>측정 환경과 재검토 방법</h2><p>A는 기준 실행 파일, B는 패치를 적용한 실행 파일입니다. 42개 실제 입력을 A/B 쌍으로 실행했습니다. libpng는 20쌍, 나머지 41개 입력은 60쌍입니다. AB와 BA 순서를 번갈아 실행했습니다. 주 지표는 user CPU 시간이며, CLI 반복에는 프로세스 시작 비용도 포함됩니다. elapsed는 준비 시간을 제외한 명령 실행 구간의 합입니다.</p><p>Ryzen 9 3900X에서 CPU 0에 고정하고 짝을 이루는 CPU 12를 오프라인으로 설정했습니다. boost를 끄고 3,000 MHz를 요청했습니다. 관측 부하 주파수 중앙값은 2,969.491 MHz, 최저·최고는 2,958.103 / 2,992.151 MHz, 최고 온도는 55.25°C입니다. CPU 고정은 다른 작업의 접근까지 막는 독점을 뜻하지 않습니다.</p>'
    body += review_page.methods(review, flags)
    body += '<details class="archive-details"><summary>원측정의 반복 수 확대 기준과 환경 차트 2개</summary><p>GMP·Hermes·libpng에서 각각 20쌍의 A/A 대조를 했습니다. 최대 비율 표준편차 0.8533%의 3배를 공통 선별 기준으로 썼습니다. 효과가 그보다 작거나 쌍 비율 CV가 0.5%를 넘으면 방향과 관계없이 한 번, 총 60쌍까지 늘렸습니다. 아래 두 차트는 원래 환경·잡음 기록입니다.</p>'
    body += figure(asset + 'charts/46-AA-noise.svg', '세 A/A 대조의 원래 비율 변동과 시간 드리프트', '동일 코드 대조군 · 원보고의 반복 수 결정 기준')
    body += figure(asset + 'charts/47-environment.svg', '측정 중 주파수·온도와 집계 범위', '주파수·온도 원래 그래프') + '</details></section>'
    body += '<section class="doc-section" id="earlier-studies"><div class="eyebrow">EARLIER INDEPENDENT STUDIES</div><h2>이전에 수행한 실험도 따로 보관했습니다</h2><p>호스트·입력·비교 시점이 다른 실험은 각각의 페이지에서 읽습니다. 서로 다른 실험의 개선율을 합산하거나 평균내지 않습니다.</p><div class="archive-study-grid"><a href="benchmarks/pr19.html"><small>2026-10-05 · AMD EPYC 9V74</small><h3>19개 PR 성능 검증</h3><p>실제 test-suite, 추출 함수, 합성 커널, 컴파일 비용. 19개 PR별 판단과 보고서의 모든 문장·표를 수록했습니다.</p><strong>보고서 전문과 차트 4장 ↗</strong></a><a href="benchmarks/backend.html"><small>2026-10-05–06 · 코드 생성 비교</small><h3>PR #228359 전체 코퍼스</h3><p>241개 프로젝트, 39,371개 모듈, 78,742개 비교. 성공·실패 전부와 ISA 모델 결과를 볼 수 있습니다.</p><strong>프로젝트별 전체 실행 기록 ↗</strong></a></div></section>'
    body += '<section class="doc-section" id="evidence"><div class="eyebrow">SOURCES / NUMERIC DOWNLOADS</div><h2>원시 수치와 연결 근거 다운로드</h2><p>2026-10-18 추가된 benchmark-detail-log에서 원시 관측 5,080행과 쌍별 비율 2,540행을 대조했습니다. 공개 CSV에는 모든 행의 측정 수치·입력·순서와 집계 포함 여부를 옮겼습니다. 서버 경로·명령·실행 태그·상세 환경 및 실행 로그 본문은 생략했습니다. 열의 범위와 단위는 공개 열·단위·해시 정보에서 확인할 수 있습니다.</p>'
    body += review_page.downloads() + review_page.provenance(review)
    body += '<h3>원래 보고값과 별도 실험의 자료 범위</h3><p>기존 results.zip의 차트 47개, 검증표의 42개 조건, 변경 함수·명령·관련 PR과 제외·수정 이력도 그대로 보관했습니다. 아래 원보고 집계표는 차트 보고값이며 위 원시 수치 CSV와 구분합니다. 이전 19개 PR 보고서가 언급한 405행 원시 CSV는 이번 추가 묶음에도 포함되지 않았습니다. 사이트를 고치며 새 벤치마크는 실행하지 않았습니다.</p><div class="article-tools"><a href="' + asset + 'application-summary.csv" download>원보고 42개 조건 집계 CSV</a><a href="' + asset + 'applications.json" download>원래 조건·검증표 JSON</a></div><details class="archive-details"><summary>제외·대체·예비 후보와 조건별 수정 이력</summary><p>검증표에 기록된 원문을 유지했습니다. 제외된 조건을 효과 0의 측정 행으로 만들지 않습니다.</p>'
    for item in data['selection']['not_selected']:
        body += '<h4>' + e(item['project']) + '</h4><p>' + e(item['reason']) + '</p>'
    body += '<h4>조건별 폐기·수정 이력</h4><ul>' + ''.join('<li>' + e(item) + '</li>' for item in data['review_history']) + '</ul></details><p class="small-note">원본 results.zip SHA-256: <code>' + e(data['source']['sha256']) + '</code>. 최신 집계와 이전 실험을 멘티 제출 자료 36개에 합산하지 않았습니다.</p></section></article>'
    (root / 'docs/benchmarks.html').write_text(wrap('벤치마크 전체 결과', body, active='benchmarks', main_class='archive-main', edited=build_pr229086.PUBLISHED, description='LLVM 42개 입력 재검토와 PR 229086 BlazeFace 추론 벤치마크: 원시 수치, Add 진단, 멘티·PR·실행 경로와 원래 차트 47개.'))
