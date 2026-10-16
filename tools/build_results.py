"""Render source-linked measurements with their units, controls and scope."""
import json
from html import escape
from pathlib import Path
import benchmark_review as review_page

def e(s):return escape(str(s),quote=True)

def chart(series):
    maximum=max(row['before']for row in series['rows'])
    out='<section class="benchmark-panel" id="'+series['id']+'" data-benchmark-panel><h3>'+e(series['label'])+' · 실행 시간</h3><p class="chart-unit">단위: ns/회 · 15회 중앙값 · 짧을수록 빠름</p><div class="bar-chart" role="list" aria-label="'+e(series['label'])+' 최적화 전후 실행 시간 비교">'
    for row in series['rows']:
        control=row.get('control',False)
        out+='<div class="chart-row'+(' is-control'if control else'')+'" role="listitem"><div class="chart-row-title"><strong>'+e(row['label'])+'</strong><span>'+('대조군'if control else str(row['change'])+'% 시간 감소')+'</span></div>'
        for key,label in [('before','이전'),('after','PR 적용')]:
            width=row[key]/maximum*100
            out+='<div class="bar-line"><span>'+label+'</span><div class="bar-track" aria-hidden="true"><i class="bar '+key+'" style="width:'+f'{width:.3f}'+'%"></i></div><b>'+f'{row[key]:.3f}'+'</b></div>'
        if control:out+='<p class="control-note">생성 코드가 같거나 기존에도 최적화되는 사례입니다. 작은 차이는 개선으로 주장하지 않습니다.</p>'
        out+='</div>'
    out+='</div><details class="chart-table" open><summary>정확한 측정값</summary><div class="table-wrap"><table><thead><tr><th>사례</th><th>이전 ns/회</th><th>PR ns/회</th><th>자료의 시간 감소율</th></tr></thead><tbody>'
    for row in series['rows']:
        out+='<tr><th scope="row">'+e(row['label'])+'</th><td>'+f'{row["before"]:.3f}'+'</td><td>'+f'{row["after"]:.3f}'+'</td><td>'+('대조군'if row.get('control')else str(row['change'])+'%')+'</td></tr>'
    return out+'</tbody></table></div></details></section>'

def build(root,wrap,icon):
    data=json.loads((root/'content/results.json').read_text())
    review,links,_=review_page.load(root)
    body='<article class="article results-article"><header class="article-header"><div class="eyebrow">MENTEE CONTRIBUTION RESULTS / LLVM</div><h1>멘티들의 기여 결과</h1><p class="article-lead">실행 시간, 정확성 검증과 API 구현을 함께 정리했습니다. 반복 측정에서 관측한 변화가 어떤 멘티의 PR과 실행 경로로 이어지는지 확인할 수 있습니다.</p><div class="article-meta"><span>17명의 제출 자료</span><span>원시 측정 재검토 2026-10-18</span><span>기존 구현·검증 기록 유지</span></div><div class="article-tools"><button type="button" data-print>'+icon('print')+'인쇄 / PDF</button><a href="sources/index.html">문서 전문 36개 보기</a></div></header>'
    body+='<nav class="results-jump" aria-label="결과 페이지 목차"><a href="#performance-review">반복 측정 결과</a><a href="#mentee-bench-links">멘티·PR 연결</a><a href="#validation">테스트 결과</a><a href="#implementation">구현 결과</a><a href="#runtime">이전 합성 실험</a><a href="#reproduction">기존 패치 분석</a><a href="#participants">멘티별 문서</a></nav><a class="benchmark-entry" href="benchmarks.html"><span><strong>우리가 벤치마크한 전체 결과</strong><small>42개 입력의 모든 반복 측정 · 원래 차트 47개 · 측정 환경과 재검토 방법</small></span><span aria-hidden="true">↗</span></a>'
    body+='<section class="doc-section" id="performance-review"><div class="eyebrow">2026-10-18 / PAIRED OBSERVATION REVIEW</div><h2>실제 입력에서 관측한 실행 시간 변화</h2><p>추가로 받은 원시 관측 5,080행을 쌍별 기록과 대조했습니다. 패치 비교는 42개 입력·2,480쌍, 동일 실행 파일 A/A 대조는 3개 입력·60쌍입니다. 아래 감소율은 원보고의 주 집계를 유지하고, 실행 순서와 전후반 비교에는 모든 쌍을 사용했습니다.</p>'+review_page.representatives(review,links)+review_page.summary_counts(review)+'<p>SQLite는 59/60쌍, libpng는 20/20쌍에서 시간이 줄었습니다. 반대로 bzip2와 JPEG XL은 각각 60/60쌍에서 시간이 늘었습니다. 전체 관측값과 입력별 집계는 <a href="benchmarks.html#all-cases">42개 입력 상세</a>에서 확인할 수 있습니다.</p><p class="small-note">주 지표는 user CPU 시간입니다. 양수는 시간 감소, 음수는 시간 증가입니다. 평균 방향 유지 기준과 재표집 범위는 <a href="benchmarks.html#method">측정·재검토 방법</a>에 적었습니다. 다른 입력·장비의 성능이나 개별 PR의 단독 기여율로 확대하지 않습니다.</p></section>'
    body+=review_page.contribution_section(links)
    body+='<section class="doc-section" id="validation"><div class="eyebrow">TEST RESULTS</div><h2>테스트와 검증 결과</h2><p>제출 자료에 보고한 주요 테스트 결과입니다. 각 수치는 아래에 적힌 검증 범위에 해당합니다.</p><div class="test-results-grid">'
    tests=[
        ('정하람 · 문자열 길이 접기','19 / 19','통과','strlen·wcslen 및 optimization remarks','원본 PR의 11개 통과·8개 실패에서, 공통 fixpoint 문제 수정 후 19개 모두 통과했습니다.','s025'),
        ('정하람 · 확장 회귀 검사','2,263','통과','92개 미지원 · 실패 0개','InstCombine·InstSimplify·SCCP·remarks 총 2,355개 중 92개는 미지원으로 분류했습니다.','s025'),
        ('임승현 · DemandedElts','28 / 28','통과','FPclass 테스트','AMDGPU 4,921개 테스트의 통과와 27개 파일의 출력 동일성도 보고했습니다.','s020'),
        ('최진범 · ValueTracking','22개','회귀 테스트','양성 17개 · 음성 5개','두 nonzero 추론 규칙의 적용·제외 조건을 검사했습니다. Alive2 예시 2개도 검증했습니다.','s034')
    ]
    for author,value,status,scope,detail,sid in tests:
        body+='<article class="test-result-card"><small>'+e(author)+'</small><div class="test-value"><b>'+e(value)+'</b><span>'+e(status)+'</span></div><h3>'+e(scope)+'</h3><p>'+e(detail)+'</p><a href="sources/'+sid+'.html">테스트 근거와 전문 ↗</a></article>'
    body+='</div><p class="small-note">fmemopen의 11개 테스트, clang-tidy 크래시 회귀 검사 등은 아래 <a href="#implementation">구현 결과</a>와 각 멘티의 전문에서 확인할 수 있습니다.</p></section>'
    body+='<section class="doc-section" id="implementation"><div class="eyebrow">IMPLEMENTATION & VALIDATION</div><h2>구현과 품질 개선 결과</h2><div class="validation-grid">'
    cards=[
      ('정지현 · PMADDUBSW','3개 연산 → 1개','두 PMADD와 ADD를 한 PMADD로 결합한다. 0인 곱과 signed i16 오버플로·포화 조건을 검사한다. 128/256/512비트를 다룬다. 실행 시간 비율은 측정하지 않았다.','s023'),
      ('임승현 · DemandedElts','마스크 폭 문제 3곳 수정','NFC 전달 경로를 복구했다. 27개 파일의 출력 동일성, FPclass 28/28·AMDGPU 4,921개 테스트를 보고했다. 향후 최적화를 가능하게 하는 기반 작업이다.','s020'),
      ('정하람 · 문자열 길이 접기','관련 19개 테스트 통과','원본에서 11개 통과·8개 실패하던 공통 fixpoint 문제를 수정했다. 확장 검증은 2,263개 통과·92개 미지원·실패 0개다. 실패 8개를 서로 다른 버그 8개로 세지 않는다.','s025'),
      ('정지현 · fmemopen','메모리 스트림 API와 11개 테스트','고정 버퍼의 용량·위치·읽기·쓰기 경계를 구현했다. 소스의 병합 기록까지 제공한다. 새로운 API의 사용 가능성이 핵심 결과다.','s024'),
      ('최진범 · ValueTracking','27줄 · 22개 테스트','vector 증가량의 nonzero 추론 규칙 2개를 추가했다. 양성 17개·음성 5개와 Alive2 예시를 검증했다. 불필요한 분기를 없애는 조건을 공용 분석에 반영했다.','s034'),
      ('최진범 · umask','래퍼·진입점·3개 아키텍처 등록','실패하지 않는 시스콜의 반환 형식을 기존 구현과 맞췄다. CMake와 공개 헤더를 연결하고 프로세스 마스크를 복원하는 테스트를 작성했다.','s036'),
      ('이하동 · LLVM / clang-tidy','값 추론 보완·크래시 수정','urem 이후 값 관계를 공용 ValueTracking에 반영했다. clang-tidy에서는 미해석 예외 명세를 검사해 크래시를 막고 회귀 테스트와 릴리스 노트를 추가했다.','s016'),
      ('김준영 · clamp 정규화','로컬 구현과 반례 추적','NaN·부호 있는 0·poison·경계 순서 등 변환의 전제를 검토했다. aggregate 크래시와 잘못된 비교 제약을 수정한 과정이 남아 있다. upstream 전체 앱 성능으로 환산하지 않는다.','s008')
    ]
    for author,value,detail,sid in cards:
        body+='<article class="validation-card"><small>'+e(author)+'</small><h3>'+e(value)+'</h3><p>'+e(detail)+'</p><a href="sources/'+sid+'.html">구현·검증 전문 ↗</a></article>'
    body+='</div></section>'
    body+='<section class="doc-section" id="runtime"><div class="eyebrow">EARLIER INDEPENDENT SYNTHETIC STUDY / 2026-09-15</div><h2>이전 합성 실험 · 상수 문자열 길이 계산</h2><p>다음은 macOS arm64에서 별도로 수행한 합성 실험입니다. 위의 Ryzen 실제 입력 재측정과 환경·작업이 다릅니다. C++ O2의 8.8% 감소 등 원자료의 모든 수치를 그대로 보관했습니다.</p><p>정하람 멘티 자료에서 다룬 <a href="https://github.com/llvm/llvm-project/pull/223246">PR #223246</a>은 중첩된 select·PHI의 모든 경로에서 문자열 길이를 알 수 있을 때, 문자열 포인터를 고른 뒤 <code>strlen</code>을 호출하던 코드를 상수 길이를 고르는 코드로 바꿉니다. <a href="sources/s025.html">측정 방법·전체 결과·회귀 수정 보고서 ↗</a></p>'
    body+='<div class="measurement-context"><strong>측정 조건</strong><p>2026-09-15 · macOS arm64 · opt의 호스트 CPU 표시 apple-m1. 동일한 Clang 22.1.8 frontend, LLVM 24 개발 버전 opt의 전체 O2/O3 파이프라인과 동일 llc를 사용했습니다. 함수별 실행 파일·noinline·LTO 없음·런타임 입력·독립 checksum 검증을 적용했습니다.</p><p>100,000회 준비 실행 후 C는 20,000,000회, C++ 메시지 생성은 2,000,000회 측정했습니다. 순서를 섞어 15회 반복한 중앙값이며 루프와 함수 호출 비용을 포함합니다. CPU·클록 고정은 하지 않았습니다.</p></div>'
    body+='<div class="chart-legend"><span><i class="legend-before"></i>이전 커밋</span><span><i class="legend-after"></i>PR 적용</span><small>대조군을 함께 표시합니다.</small></div><div class="benchmark-tabs" role="group" aria-label="벤치마크 선택">'+''.join('<button type="button" data-benchmark="'+s['id']+'" aria-pressed="'+str(i==0).lower()+'">'+e(s['label'])+'</button>'for i,s in enumerate(data['series']))+'</div>'
    body+=''.join(chart(s)for s in data['series'])
    body+='<aside class="note"><strong>수치가 뜻하는 범위</strong>실제 서비스나 전체 앱을 측정한 결과가 아니라 합성 벤치마크입니다. C++ 메시지 작업에는 문자열 생성·할당·복사·해시가 포함되지만 서버 I/O는 없습니다. 일반적인 동적 strlen을 모두 빠르게 한다는 뜻은 아닙니다. 막대는 표의 반올림된 시간으로 그렸고, 감소율은 제출 자료의 표기값을 사용했습니다.</aside><details class="measurement-details"><summary>비교 커밋과 측정 중 발견한 문제</summary><p>부모 커밋 <code>d283a555109576cd92b35a88b4d110166043fb77</code>과 PR 커밋 <code>ae605b914df994b7cfb0b1b98c5469bdc9093389</code>을 비교했습니다. 기존 테스트 회귀를 수정한 로컬 버전도 C O2/O3·C++ O2의 최적화 IR이 원본 PR과 바이트 단위로 같았습니다.</p><p>처음 모든 함수를 한 실행 파일에 넣었을 때 대조군에서 약 25%의 차이가 나타났습니다. 함수별로 분리한 재측정에서 그 차이가 사라졌고, 이 페이지는 최종 분리 측정만 사용합니다. 원시 로그와 스크립트의 링크는 자료에 있으나 첨부파일 묶음에는 포함되지 않았습니다. 문서 변환 중 재측정한 값은 아닙니다.</p></details></section>'
    body+='<section class="doc-section" id="reproduction"><div class="eyebrow">STUDY & REPRODUCTION</div><h2>기존 패치를 학습하며 확인한 효과</h2><p>아래는 기존 LLVM 패치를 분석·재현한 자료입니다. 멘티가 새로 제출한 최적화의 실행 시간 성과로 합산하지 않습니다. llvm-mca는 CPU 모델을 사용한 정적 추정 도구입니다.</p><div class="reproduction-grid">'
    for item in data['reproductions']:
        maximum=item['before']
        body+='<article class="reproduction-card"><span class="chip">기존 패치 분석</span><h3>'+e(item['author'])+' · '+e(item['title'])+'</h3><p class="chart-unit">'+e(item['metric'])+' · '+e(item['unit'])+'</p>'
        for key,label in [('before','이전'),('after','이후')]:
            body+='<div class="bar-line"><span>'+label+'</span><div class="bar-track" aria-hidden="true"><i class="bar '+key+'" style="width:'+str(item[key]/maximum*100)+'%"></i></div><b>'+f'{item[key]:.1f}'+'</b></div>'
        body+='<p>'+e(item['detail'])+'</p><a href="sources/'+item['source']+'.html">'+e(item['author'])+'의 분석 전문 ↗</a></article>'
    body+='</div><p class="small-note">각 카드 안에서만 전후를 비교하세요. 타깃·입력·모델이 다른 자료끼리 감소율로 순위를 매기지 않습니다. 명령어·µops·cycles는 서로 다른 지표입니다. <a href="sources/s001.html">SeokHun의 다중 타깃 비교</a>에는 RISC-V 명령어 수가 그대로인 사례도 있습니다.</p></section>'
    body+='<section class="doc-section" id="participants"><div class="eyebrow">ALL 17 PARTICIPANTS</div><h2>멘티별 결과와 전체 문서</h2><p>개별 제출자의 자료를 기준으로 정리했습니다. 멘토·리뷰어의 도움과 기존 패치 분석은 독립적인 신규 기여와 구분해서 읽을 수 있도록 표시했습니다.</p><div class="participant-results">'
    for item in data['participants']:
        body+='<article class="participant-result"><div><h3>'+e(item['author'])+'</h3><span class="chip">'+e(item['kind'])+'</span></div><div><p>'+e(item['result'])+'</p><div class="participant-links">'+''.join('<a href="sources/'+sid+'.html">문서 '+str(i+1)+' 전문 ↗</a>'for i,sid in enumerate(item['sources']))+'</div></div></article>'
    body+='</div></section><p class="small-note">출처: 멘티 제출 자료 36개, 작성자 대조에 사용한 최종보고서·팀 보고서, 추가 제공된 benchmark-detail-log. 구현·검증 기록과 이전 합성 차트는 제출 자료의 보고값이며, 최신 안정성 분석은 제공된 원시 측정의 재검토입니다. LLVM 벤치마크를 새로 실행하지 않았습니다.</p></article>'
    (root/'docs/results.html').write_text(wrap('멘티들의 기여 결과',body,active='results',main_class='results-main',edited=review['created'],description='LLVM 멘티들의 최적화 성능 차트, 구현·정확성 검증, 기존 패치 학습 결과와 17명의 전체 자료.'))
