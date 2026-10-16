"""Publish existing measurements, preserving study boundaries and all outcomes."""
import csv
import hashlib
import json
import re
import shutil
import build_pr229086
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


def e(value):
    return escape(str(value), quote=True)


def table(headers, rows, caption='', row_ids=None):
    return '<div class="table-wrap">' + ('<table><caption>' + e(caption) + '</caption>' if caption else '<table>') + '<thead><tr>' + ''.join('<th scope="col">' + e(v) + '</th>' for v in headers) + '</tr></thead><tbody>' + ''.join('<tr' + (' data-archive-index="' + e(row_ids[i]) + '"' if row_ids else '') + '>' + ''.join('<td>' + str(v) + '</td>' for v in row) + '</tr>' for i, row in enumerate(rows)) + '</tbody></table></div>'


def figure(path, title, caption='', eager=False):
    return '<figure class="archive-figure"><a href="' + e(path) + '"><img src="' + e(path) + '" alt="' + e(title) + '" width="1280" height="720" loading="' + ('eager' if eager else 'lazy') + '"></a><figcaption><span>' + e(caption or title) + '</span><a href="' + e(path) + '">크게 보기 ↗</a></figcaption></figure>'


def script_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def header(title, lead, meta, prefix='', tools=''):
    return '<header class="article-header"><div class="eyebrow">OUR BENCHMARK ARCHIVE / LLVM</div><h1>' + e(title) + '</h1><p class="article-lead">' + lead + '</p><div class="article-meta">' + ''.join('<span>' + e(s) + '</span>' for s in meta) + '</div><div class="article-tools"><a href="' + prefix + 'benchmarks.html">벤치마크 전체 결과</a><a href="' + prefix + 'results.html">멘티들의 기여 결과</a>' + tools + '</div></header>'


def build_applications(root, data, wrap, icon):
    import build_reviewed_applications
    build_reviewed_applications.build(root, data, wrap, icon, table=table,
                                     figure=figure, header=header, script_json=script_json)


def build_report(root, report, wrap):
    body = '<article class="article archive-article">' + header('19개 PR 성능 검증 · 전체 보고서', '실제 LLVM test-suite와 원본 함수, 타깃 커널을 독립적으로 측정한 기록입니다. 보고서 본문과 모든 표를 그대로 읽을 수 있습니다.', ['보고서 기준 2026-10-05 UTC', 'AMD EPYC 9V74 · 공유 Linux x86-64', '본문·표 183개 블록'], '../')
    body += '<aside class="note"><strong>최신 재측정과 별개의 실험</strong>이 보고서의 추출 함수·합성 커널 결과는 최신 Ryzen 실험의 전체 앱 작업 결과와 비교 조건이 다릅니다. 19개 PR 포트폴리오의 17개 프로그램 평균은 세 비교 모두 95% 구간에 변화 없음이 포함됐습니다. 큰 합성 개선율을 전체 프로그램의 개선율로 읽지 않습니다.</aside><p class="small-note">보고서가 언급한 405행 원시 CSV는 제공된 자료에서 확인되지 않았습니다. 이 페이지는 보고서에 있는 모든 문장·표와 차트 4장을 수록하며, 405개 상세 관측을 복원했다고 주장하지 않습니다.</p>'
    headings = []
    for i, block in enumerate(report['blocks']):
        if block.get('heading'):
            headings.append((i, block['text'], block['heading']))
    body += '<details class="archive-details" open><summary>전체 보고서 목차</summary><nav class="archive-report-toc">' + ''.join('<a href="#report-' + str(i) + '"' + (' class="sub"' if level > 1 else '') + '>' + e(title) + '</a>' for i, title, level in headings) + '</nav></details>'
    body += '<section class="doc-section"><h2>보고서 원래 차트 4장</h2>'
    for i, filename in enumerate(report['charts'], 1):
        body += figure('../assets/benchmarks/report-charts/' + filename, '19개 PR 검증 보고서 원래 성능 차트 ' + str(i), '원래 차트 ' + str(i) + ' / 4 · 해석과 수치는 아래 전문 참조')
    body += '</section><div class="archive-report-full">'
    for i, block in enumerate(report['blocks']):
        if block['kind'] == 'table':
            body += '<div class="archive-report-block" data-report-block="' + str(i) + '">' + table(block['rows'][0], [[e(c).replace('\n', '<br>') for c in row] for row in block['rows'][1:]]) + '</div>'
        elif block.get('heading'):
            level = min(4, block['heading'] + 1)
            pr = re.match(r'PR (\d+)\s', block['text'])
            link = ' <a class="archive-pr-link" href="https://github.com/llvm/llvm-project/pull/' + pr[1] + '">PR 보기 ↗</a>' if pr else ''
            body += '<h' + str(level) + ' id="report-' + str(i) + '" data-report-block="' + str(i) + '">' + e(block['text']) + link + '</h' + str(level) + '>'
        else:
            body += '<p data-report-block="' + str(i) + '">' + e(block['text']).replace('\n', '<br>') + '</p>'
    body += '</div><section class="doc-section"><h2>원본 자료 식별</h2>' + ''.join('<p><code>' + e(s['filename']) + '</code><br><small>SHA256 ' + e(s['sha256']) + '</small></p>' for s in report['sources']) + '<p><a href="../assets/benchmarks/pr19-report.json" download>보고서 전체 본문·표 JSON</a></p></section></article>'
    (root / 'docs/benchmarks/pr19.html').write_text(wrap('19개 PR 성능 검증 · 전체 보고서', body, '../', active='benchmarks', main_class='archive-main'))


def slug(project):
    safe = re.sub(r'[^A-Za-z0-9._-]', '-', project).strip('.') or 'project'
    return safe + '-' + hashlib.sha256(project.encode()).hexdigest()[:8]


def build_backend(root, data, wrap):
    projects = defaultdict(list)
    for file in sorted((root / 'content/benchmarks/backend').glob('*.csv')):
        with file.open(newline='') as handle:
            for row in csv.DictReader(handle):
                projects[row['path'].split('/')[1]].append(row)
    assert len(projects) == 241
    assert sum(map(len, projects.values())) == 78742
    body = '<article class="article archive-article">' + header('PR #228359 · 전체 코드 생성 결과', '241개 프로젝트의 실제 IR 모듈을 두 ISA 프로파일에서 비교했습니다. 모든 모듈의 성공·실패와 전후 출력 해시를 프로젝트별로 볼 수 있습니다.', ['2026-10-05–06', '39,371개 모듈 · 78,742개 비교', '실행 속도 측정과 별도'], '../')
    body += '<div class="archive-stat-grid"><div><b>78,338</b><span>전후 출력이 동일한 비교</span></div><div><b>0</b><span>성공한 비교 중 출력 변경</span></div><div><b>404</b><span>코드 생성 실패</span></div></div><aside class="note"><strong>실패는 동일 출력으로 세지 않습니다</strong>성공한 실제 코퍼스에서는 두 프로파일 모두 변경된 모듈이 없었습니다. 실패한 404개 비교의 영향은 판단할 수 없습니다. 합성 양성 테스트에서는 패치가 동작했지만, 그것을 실제 코퍼스에서 발견한 최적화 수로 세지 않습니다.</aside>'
    body += table(['프로파일', '전체 비교', '동일', '변경', '실패', '시간 초과'], [['x86-64-v3', '39,371', '39,116', '0', '255', '0'], ['x86-64-v4', '39,371', '39,222', '0', '149', '0']])
    body += '<section class="doc-section"><h2>비교 조건과 자료 범위</h2><p>고정한 PR head는 <code>d06b9bff62464719eefe44ff595e19c46759cb1c</code>입니다. 공통 빌드 입력을 맞추고 X86ISelLowering 구현 단위에만 패치를 적용한 로컬 비교입니다. upstream base와 head를 각각 완전히 빌드한 결과는 아닙니다.</p><p>동일 IR에서 CPU·feature·tune 속성만 제거하고 <code>llc -O2 -mtriple=x86_64-unknown-linux-gnu -mcpu=x86-64-v3</code> 또는 <code>x86-64-v4</code>를 사용했습니다. 한 프로파일 이상 성공한 고유 모듈은 39,222개, 두 프로파일 모두 성공한 모듈은 39,116개입니다.</p><p>아래 CSV는 원래 실행 기록의 전체 행에서 결과·해시·반환 코드·진단을 공개용으로 옮긴 자료입니다. 개인 컴퓨터의 절대 경로는 제거했습니다. 수집 중 기록된 compiler 경과 시간은 정식 성능 비교값으로 사용하지 않습니다. 대용량 assembly와 compiler 실행 파일은 이 사이트에 포함하지 않았습니다.</p><div class="article-tools"><a href="../assets/benchmarks/backend/avx2-v3.csv" download>v3 전체 39,371행 CSV</a><a href="../assets/benchmarks/backend/avx512-v4.csv" download>v4 전체 39,371행 CSV</a></div></section>'
    body += '<section class="doc-section"><h2>241개 프로젝트 · 모든 모듈 보기</h2><div class="archive-project-search"><label>프로젝트 찾기<input type="search" data-backend-search placeholder="예: opencv, onnx, llvm" aria-label="코퍼스 프로젝트 검색"></label><span data-backend-count aria-live="polite">241 / 241</span></div>'
    rows = []
    output = root / 'docs/benchmarks/projects'
    output.mkdir(parents=True, exist_ok=True)
    for project, records in sorted(projects.items()):
        filename = slug(project) + '.html'
        counts = Counter(r['status'] for r in records)
        rows.append('<tr data-backend-project="' + e(project.lower()) + '"><td><a href="projects/' + filename + '">' + e(project) + '</a></td><td>' + str(len(records) // 2) + '</td><td>' + str(counts['identical']) + '</td><td>' + str(counts['codegen_error']) + '</td><td><a href="projects/' + filename + '">전체 기록 ↗</a></td></tr>')
        project_body = '<article class="article archive-article">' + header(project + ' · 전체 모듈 비교', '프로젝트의 모든 모듈·프로파일 결과입니다. 동일 출력과 실패를 함께 보여 줍니다.', [str(len(records) // 2) + '개 모듈', str(len(records)) + '개 비교', 'PR #228359'], '../../') + '<p><a href="../backend.html">← 코퍼스 전체 결과</a></p><p class="small-note">A는 패치 이전, B는 패치 이후입니다. 해시 열은 출력 assembly의 SHA256 앞 16자리이며, 전체 64자리와 소스·정규화 IR 해시는 CSV에 있습니다. 실패한 출력의 빈 해시는 일치로 취급하지 않습니다. 함수 목록이 비어 있고 성공한 출력이 같으면 동일로 분류합니다.</p>'
        project_rows = []
        for record in sorted(records, key=lambda r: (r['path'], r['profile'])):
            diagnostics = ''
            for variant, label in [('before', 'A'), ('after', 'B')]:
                if record[variant + '_diagnostic']:
                    diagnostics += '<details class="archive-diagnostic"><summary>' + label + ' 진단 전문</summary><pre>' + e(record[variant + '_diagnostic']) + '</pre></details>'
            project_rows.append([e(record['path'].split('/optimized/', 1)[-1]), e(record['profile']), '<span class="archive-status ' + ('uncertain' if record['status'] == 'identical' else 'regressed') + '">' + ('동일' if record['status'] == 'identical' else '실패') + '</span>' + diagnostics, e(record['before_returncode']) + ' / ' + e(record['after_returncode']), '<code title="' + e(record['before_assembly_sha256']) + '">' + (record['before_assembly_sha256'][:16] or '—') + '</code><br><code title="' + e(record['after_assembly_sha256']) + '">' + (record['after_assembly_sha256'][:16] or '—') + '</code>'])
        project_body += table(['모듈', '프로파일', '결과 / 진단', 'A/B 반환 코드', 'A/B 출력 SHA256'], project_rows) + '</article>'
        (output / filename).write_text(wrap(project + ' · PR 228359 코드 생성', project_body, '../../', active='benchmarks', main_class='archive-main'))
    body += '<div class="table-wrap"><table><thead><tr><th>프로젝트</th><th>고유 모듈</th><th>동일 비교</th><th>실패 비교</th><th>상세</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></section>'
    body += '<section class="doc-section"><h2>양성 테스트와 ISA 모델의 비용</h2><p>상위 테스트 7개 구성과 아래 5개 프로파일·폭 구성을 통과했습니다. 안전한 fixture의 기계어는 10개에서 3개, PMADDUBSW 2개에서 1개, PADDW 1개에서 0개가 됩니다. overflow와 추가 shuffle 대조 조건도 검사했습니다. 아래 llvm-mca 결과는 CPU 모델의 정적 추정이며, ARM64 호스트에서 x86 코드를 실제 실행한 시간은 아닙니다.</p>'
    mca_rows = []
    for item in data['mca']:
        before = item['variants']['before']
        after = item['variants']['after']
        assert before['returncode'] == after['returncode'] == 0
        mca_rows.append([e(item['profile']), str(item['width']), str(before['static']['instructions']) + ' → ' + str(after['static']['instructions']), str(before['mca']['Block RThroughput']) + ' → ' + str(after['mca']['Block RThroughput']), str(before['mca']['Total Cycles']) + ' → ' + str(after['mca']['Total Cycles']), str(before['mca']['Total uOps']) + ' → ' + str(after['mca']['Total uOps'])])
    body += table(['프로파일', '폭 (bit)', '정적 명령어', '역처리량', 'cycles · 100회', 'µops · 100회'], mca_rows) + '<p class="small-note">초기 V1 추출의 CFI 오류로 실패한 MCA 출력은 유효 결과에서 제외했습니다. 위 표는 수정된 V2의 5개 결과 전체입니다.</p></section>'
    body += '<section class="doc-section"><h2>선택적 feature 보완 실행</h2><p>기본 ISA에서 실패한 경우에 별도 feature를 추가한 보완 시도는 200개이며 182개 동일·18개 실패였습니다. 두 보완 방식이 겹치므로 성공한 고유 기본 실패 비교는 170개입니다. 기본 프로파일의 실패 수를 이 값으로 덮어쓰지 않습니다. 외부 아키텍처 222건은 x86으로 변환하지 않고 미실행으로 남겼습니다.</p><details class="archive-details"><summary>보완·미실행 기록 전체 422행</summary>'
    supplemental_rows = []
    for record in data['supplement']:
        supplemental_rows.append([e(record.get('path', record.get('module', ''))), e(record.get('profile', '')), e(record['method']), e(record.get('status', '')), '<details><summary>기록 전체</summary><pre>' + e(json.dumps(record, ensure_ascii=False, indent=2)) + '</pre></details>'])
    body += table(['모듈', '프로파일', '보완 방식', '결과', '전체 필드'], supplemental_rows) + '</details><p><a href="../assets/benchmarks/backend-summary.json" download>ISA·보완 실행·종료 검증 JSON</a></p><p class="small-note">원본 전체 실행 기록 SHA256: <code>' + data['source']['sha256'] + '</code>.</p></section></article>'
    (root / 'docs/benchmarks/backend.html').write_text(wrap('PR 228359 전체 코드 생성 결과', body, '../', active='benchmarks', main_class='archive-main'))


def build(root, wrap, icon):
    source = root / 'content/benchmarks'
    destination = root / 'docs/assets/benchmarks'
    shutil.copytree(source, destination, dirs_exist_ok=True)
    (root / 'docs/benchmarks').mkdir(exist_ok=True)
    data = json.loads((source / 'applications.json').read_text())
    build_applications(root, data, wrap, icon)
    fields = ['case_id', 'project', 'feature', 'PRs', 'mean_role', 'user_A_s', 'user_B_s', 'ratio_B_over_A', 'speedup_A_over_B', 'reduction_percent', 'pairs', 'used_pairs', 'pair_cv_percent', 'status', 'sensitivity_0_pairs_percent', 'sensitivity_1_pairs_percent', 'sensitivity_2_pairs_percent']
    with (destination / 'application-summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in data['conditions']:
            writer.writerow({**{k: case[k] for k in fields[:5]}, 'user_A_s': case['user']['A'], 'user_B_s': case['user']['B'], 'ratio_B_over_A': case['ratio'], 'speedup_A_over_B': case['speedup'], 'reduction_percent': case['reduction'], 'pairs': case['pairs'], 'used_pairs': case['used_pairs'], 'pair_cv_percent': case['pair_cv'], 'status': case['status'], **{'sensitivity_' + str(i) + '_pairs_percent': v for i, v in enumerate(case['sensitivity'])}})
    build_report(root, json.loads((source / 'pr19-report.json').read_text()), wrap)
    build_backend(root, json.loads((source / 'backend-summary.json').read_text()), wrap)
    build_pr229086.build(root, wrap, icon)
