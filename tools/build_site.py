"""Build the complete static site from reviewed, publication-ready content.

This step uses only the Python standard library. It does not read Discord exports,
raw attachments, the private extraction folder, or any external service.
"""
from pathlib import Path
from collections import Counter
from html import escape
from html.parser import HTMLParser
import hashlib, json, re, shutil
import reader
import build_results
import build_benchmarks

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'
DATE='2026-10-16'
A=json.loads((ROOT/'content/articles.json').read_text())
S=json.loads((ROOT/'content/sources.json').read_text())
BY_ID={a['id']:a for a in A}
S_BY_ART={a['id']:[s for s in S if s['article']==a['id']]for a in A}
AUTHORS=sorted({a['author']for a in A})
AREAS=sorted({v for a in A for v in a['areas']})
KINDS=['기존 패치 분석','기여 과정','실험·제안']
ASSET_VERSIONS={name:hashlib.sha256((ROOT/'theme'/name).read_bytes()).hexdigest()[:12]for name in ['site.css','site.js']}

class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
def plain(markup):
    p=PlainText();p.feed(markup);return ' '.join(p.parts)

def e(s):return escape(str(s),quote=True)
def inline(t):
    return ''.join('<code>'+e(part)+'</code>'if i%2 else e(part) for i,part in enumerate(t.split('`')))
def jscript(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def icon(name):
    paths={
      'search':'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
      'menu':'<path d="M4 6h16M4 12h16M4 18h16"/>',
      'book':'<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v15"/>',
      'print':'<path d="M7 8V3h10v5M7 17H3V9h18v8h-4M7 14h10v7H7z"/>',
      'link':'<path d="m9 15 6-6M7 11l-3 3a4 4 0 0 0 6 6l3-3M11 7l3-3a4 4 0 0 1 6 6l-3 3"/>',
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true">'+paths[name]+'</svg>'

def block(b):
    kind=b[0]
    if kind=='p':return '<p>'+inline(b[1])+'</p>'
    if kind in ['list','steps']:
        tag='ul' if kind=='list'else'ol'
        return f'<{tag}>'+''.join('<li>'+inline(t)+'</li>'for t in b[1])+f'</{tag}>'
    if kind=='code':return '<div class="code-wrap"><div class="code-label">'+e(b[1].upper())+'</div><pre><code>'+e(b[2])+'</code></pre></div>'
    if kind=='note':return '<aside class="note"><strong>읽을 때 확인할 점</strong>'+inline(b[1])+'</aside>'
    if kind=='table':return '<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>'for c in b[1])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>'for c in row)+'</tr>'for row in b[2])+'</tbody></table></div>'
    raise ValueError(kind)

def sidebar(prefix,current):
    items=[]
    for author in AUTHORS:
        articles=[a for a in A if a['author']==author]
        opened=any(a['id']==current for a in articles)
        links=''.join('<li><a href="'+prefix+'articles/'+a['id']+'.html"'+(' aria-current="page"'if a['id']==current else'')+'>'+e(a['title'])+'</a></li>'for a in articles)
        items.append('<details'+(' open'if opened else'')+'><summary>'+e(author)+'<span class="count">'+str(len(articles)).zfill(2)+'</span></summary><ul>'+links+'</ul></details>')
    return '<aside class="site-sidebar" id="site-navigation" aria-label="문서 탐색"><a class="side-home" href="'+prefix+'index.html">'+icon('book')+'모든 기술 문서</a><div class="nav-label">작성자별 문서</div><nav class="author-nav">'+''.join(items)+'</nav><div class="side-footer">2026 오픈소스 컨트리뷰션 아카데미<br>LLVM 멘티 자료 · '+str(len(A))+'개 주제<br><a href="'+prefix+'about.html">문서의 구성과 편집 기준</a></div></aside>'

def wrap(title,body,prefix='',active='articles',current='',main_class='home-main',edited=None,description='LLVM 멘티의 이슈 분석, 구현 과정, 검증 기록을 정리한 한국어 기술 문서입니다.'):
    nav=[('articles','문서','index.html'),('results','기여 결과','results.html'),('benchmarks','벤치마크','benchmarks.html'),('sources','자료','sources/index.html'),('glossary','용어','glossary.html'),('about','편집 기준','about.html')]
    navhtml=''.join('<a href="'+prefix+u+'" class="nav-'+k+(' active" aria-current="page"'if k==active else'"')+'>'+label+'</a>'for k,label,u in nav)
    css='assets/site.css?v='+ASSET_VERSIONS['site.css'];js='assets/site.js?v='+ASSET_VERSIONS['site.js']
    return '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="'+e(description)+'"><meta name="theme-color" content="#fbfaf7"><title>'+e(title)+' · LLVM 멘티 기술 문서</title><link rel="icon" href="'+prefix+'assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="'+prefix+css+'"><script defer src="'+prefix+js+'"></script></head><body id="top"'+(' class="results-view"'if active=='results'else(' class="benchmarks-view"'if active=='benchmarks'else''))+'><a class="skip" href="#content">본문으로 이동</a><header class="site-header"><button type="button" class="menu-toggle" data-menu aria-label="문서 탐색 메뉴" aria-controls="site-navigation" aria-expanded="false">'+icon('menu')+'</button><a class="brand" href="'+prefix+'index.html"><span class="brand-mark" aria-hidden="true">L</span><span>LLVM 멘티 기술 문서<small>MENTEE TECHNICAL NOTES / 2026</small></span></a><nav class="header-nav" aria-label="주 메뉴">'+navhtml+'</nav></header>'+sidebar(prefix,current)+'<button type="button" class="nav-shade" data-close-menu aria-label="문서 탐색 메뉴 닫기"></button><main id="content" class="site-main '+main_class+'">'+body+'<footer class="site-footer"><span>LLVM 멘티 자료를 바탕으로 정리한 한국어 기술 문서<br>문서 편집일 '+(edited or DATE)+' · 성과와 검증 수치는 각 원자료 작성 시점 기준</span><span><a href="'+prefix+'about.html">편집 기준과 출처</a><br><a href="'+prefix+'sources/index.html">원자료 36개 보기</a></span></footer></main><a class="back-top" href="#top" aria-label="맨 위로">↑</a></body></html>\n'

def options(values):return ''.join('<option value="'+e(v)+'">'+e(v)+'</option>'for v in values)
def filters(source=False):
    html='<div class="filter-box" role="search"><div class="search-wrap">'+icon('search')+'<input class="search-input" data-search type="search" autocomplete="off" placeholder="주제, 작성자, 이슈·PR 번호로 검색" aria-label="문서 검색"><button class="clear-search" type="button" data-clear-search aria-label="검색어 지우기" hidden>×</button></div><div class="filter-row"><label class="select-label" for="author">작성자</label><select id="author" data-filter="author"><option value="">전체 작성자</option>'+options(AUTHORS)+'</select>'
    if source:
        html+='<label class="select-label" for="format">형식</label><select id="format" data-filter="format"><option value="">모든 원본 형식</option>'+options(['PDF','PPTX','HTML','MD','DOCX'])+'</select>'
    else:
        html+='<label class="select-label" for="area">분야</label><select id="area" data-filter="areas"><option value="">모든 분야</option>'+options(AREAS)+'</select><label class="select-label" for="kind">활동</label><select id="kind" data-filter="kind"><option value="">모든 활동</option>'+options(KINDS)+'</select>'
    html+='<button class="filter-reset" type="button" data-reset>필터 초기화</button></div><p class="search-help">문서 본문과 연결된 원자료의 텍스트도 함께 검색합니다. 예: nsz, 223246, 김지환</p></div>'
    return html

def empty():return '<div class="empty-state" data-empty hidden><strong>조건에 맞는 문서가 없습니다.</strong>검색어를 줄이거나 필터를 초기화해 보세요.<br><button type="button" data-reset>전체 문서 보기</button></div>'

def chips(a):
    return '<div class="chips"><span class="chip kind">'+e(a['kind'])+'</span>'+''.join('<span class="chip">'+e(v)+'</span>'for v in a['areas'])+''.join('<span class="ref-chip">#'+str(n)+'</span>'for n in a['issues'][:1])+''.join('<span class="ref-chip">PR #'+str(n)+'</span>'for n in a['prs'][:1])+'</div>'

def source_variant(s):
    variants={
     'CLAMP_PATCH_REPORT.md':'로컬 패치 보고서',
     'llvm_issue_213189_ppt.pdf':'제안·검증 발표자료 · 16쪽',
     'llvm_issue_27_analysis.docx':'상세 분석 보고서',
     'llvm_issue_27_analysis_edited.docx':'그림을 추가한 수정 보고서',
     'llvm_issue_27_presentation.pdf':'실전 사례·후속 구현 발표자료 · 18쪽',
     '223246.md':'성능 측정·회귀 분석 브리핑',
     'LLVM_PR223246__strlen.pptx':'발표자료 · 16장 A',
     'LLVM_PR_.pptx':'발표자료 · 16장 B',
     'llvm_strlen_pr_presentation.pptx':'발표자료 · 11장',
    }
    return variants.get(s['filename'],s['format']+' 원자료'+(' · '+str(len(s['pages']))+('장'if s['format']=='PPTX'else'쪽')if s['format']in['PDF','PPTX']else''))

def source_text(s):return '\n'.join(page.get('text','')+' '+plain(page.get('body',''))+' '+plain(page.get('native_body',''))+' '+plain(page.get('image_text',''))+' '+' '.join(f.get('text','')for f in page.get('figures',[])) for page in s['pages'])

def source_list(a,prefix='../'):
    items=[]
    for s in S_BY_ART[a['id']]:
        items.append('<li><span class="format">'+s['format']+'</span><div><a href="'+prefix+'sources/'+s['id']+'.html">'+e(source_variant(s))+'</a><small>'+e(s['filename'])+'</small></div></li>')
    return '<ul class="source-list">'+''.join(items)+'</ul><p class="source-caption">각 자료는 별도의 버전입니다. 같은 주제라도 구현 상태·설명 범위·수치가 다를 수 있습니다.</p>'

def home():
    search=[];rows=[]
    for i,a in enumerate(A):
        core=' '.join(plain(block(b))for sec in a['sections']for b in sec['blocks'])
        text=' '.join([a['title'],a['summary'],a['author'],a['kind'],' '.join(a['areas']),' '.join(map(str,a['issues']+a['prs'])),core]+[source_text(s)for s in S_BY_ART[a['id']]])
        search.append({'id':a['id'],'author':a['author'],'areas':a['areas'],'kind':a['kind'],'text':text})
        versions='<div class="row-versions">'+''.join('<a href="sources/'+s['id']+'.html"><span>'+s['format']+'</span> '+e(source_variant(s))+'</a>'for s in S_BY_ART[a['id']])+'</div>'
        rows.append('<article class="doc-row" data-doc-row="'+a['id']+'"><div class="doc-number">'+str(i+1).zfill(2)+'</div><div><h2><a href="articles/'+a['id']+'.html">'+e(a['title'])+'</a></h2><p>'+e(a['summary'])+'</p>'+chips(a)+versions+'</div><div class="row-author">'+e(a['author'])+'<small>전문 '+str(len(S_BY_ART[a['id']]))+'개</small></div></article>')
    body='<header class="page-hero"><div class="eyebrow">2026 OSS CONTRIBUTION ACADEMY / LLVM</div><h1>멘티가 쓴 과정,<br><em>처음부터 끝까지.</em></h1><p>문제 분석부터 코드, 실험, 검증과 시행착오까지 담았습니다.<br>36개 문서의 전문과 그림을 이곳에서 바로 읽을 수 있습니다.</p><div class="stats"><span><b>36</b>개 문서 전문</span><span><b>17</b>명의 자료</span><span><b>403</b>쪽·슬라이드</span></div><a class="results-entry" href="results.html">멘티들의 기여 결과 · 성능 차트 보기 <span aria-hidden="true">↗</span></a></header>'+filters()+'<div class="document-list"><div class="result-line"><span>29개 주제 · 초안과 수정본을 포함한 전문 36개</span><span class="result-count" data-result-count aria-live="polite">29 / 29</span></div>'+''.join(rows)+empty()+'</div><script id="search-data" type="application/json">'+jscript(search)+'</script>'
    (OUT/'index.html').write_text(wrap('모든 문서',body))
    (OUT/'search-index.json').write_text(json.dumps(search,ensure_ascii=False,separators=(',',':')))

def toc(items):return '<nav aria-label="이 문서의 목차">'+''.join('<a href="#'+e(id)+'">'+e(title)+'</a>'for id,title in items)+'</nav>'

def reader_page(s,a,topic=False):
    group=S_BY_ART[a['id']]
    title=a['title'] if topic else s['title']+' · '+source_variant(s)
    headings=reader.headings(s)+[('source-materials','문서 전문과 버전'),('references','관련 이슈와 PR')]
    nav=toc(headings)
    header='<div class="breadcrumb"><a href="../index.html">문서</a><span>/</span>'+e(a['author'])+'</div><div class="article-layout"><article class="article"><header class="article-header"><div class="eyebrow">COMPLETE DOCUMENT / '+s['format']+'</div><h1>'+e(a['title'])+'</h1><p class="article-lead">'+inline(a['summary'])+'</p><div class="article-meta"><strong>자료 '+e(a['author'])+'</strong><span>'+e(a['kind'])+'</span><span>'+e(source_variant(s))+'</span><span>전문 수록</span></div><div class="article-tools"><button type="button" data-font aria-pressed="false">글자 크게</button><button type="button" data-print>'+icon('print')+'인쇄 / PDF</button><a href="#source-materials">'+icon('link')+'다른 버전 보기</a></div></header>'
    versions=''
    if len(group)>1:
        versions='<div class="version-nav"><strong>같은 주제의 문서 '+str(len(group))+'개</strong>'+source_list(a)+'</div>'
    intro='<p class="complete-notice">'+e(s['filename'])+'의 전체 내용입니다. 설명·코드·표·검증 기록을 생략하지 않고 옮겼습니다.'+(' 그림 안의 문자 인식 결과에는 기호 오류가 있을 수 있어 이미지도 함께 제공합니다.'if s['format']=='PDF'else'')+'</p>'
    header+=intro+versions+reader.controls(s)+'<details class="mobile-toc"><summary>이 문서의 목차</summary>'+nav+'</details>'
    content=reader.sections(s)
    # Keep the earlier explanatory notes as secondary help, after the complete text.
    content+='<section class="doc-section" id="editor-notes"><details class="editor-notes"><summary>핵심 원리와 편집 주석</summary><div>'+''.join('<h3 id="'+e(section['id'])+'">'+e(section['title'])+'</h3>'+''.join(block(b)for b in section['blocks'])for section in a['sections'])+'</div></details></section>'
    refs='<section class="doc-section" id="references"><h2>관련 이슈와 PR</h2>'
    refs+=('<ul class="reference-list">'+''.join('<li><a href="'+e(r['url'])+'" rel="noopener noreferrer">'+e(r['label'])+'</a></li>'for r in a['refs'])+'</ul>')if a['refs']else'<p>자료에 기재된 공개 링크는 본문에서 확인할 수 있습니다.</p>'
    refs+='<p class="small-note">구현·병합 상태와 측정값은 해당 제출 자료의 작성 시점 기준입니다.</p></section>'
    versions='<section class="doc-section" id="source-materials"><h2>문서 전문과 버전</h2>'+source_list(a)+'</section>'
    body=header+content+versions+refs+'</article><aside class="article-toc"><strong>이 문서에서</strong>'+nav+'<p class="small-note"><a href="../glossary.html">기술 용어 확인하기 ↗</a></p></aside></div>'
    return wrap(title,body,'../',active='articles'if topic else'sources',current=a['id'],main_class='source-page article-main',description=a['summary'])

def article_pages():
    dest=OUT/'articles';dest.mkdir(exist_ok=True)
    canonical={'clamp-nan':'s008','strlen-constant-selection':'s025'}
    for a in A:
        group=S_BY_ART[a['id']]
        s=next((s for s in group if s['id']==canonical.get(a['id'])),group[0])
        (dest/(a['id']+'.html')).write_text(reader_page(s,a,True))

def source_pages():
    dest=OUT/'sources';dest.mkdir(exist_ok=True);rows=[];search=[]
    for s in S:
        a=BY_ID[s['article']];variant=source_variant(s)
        rows.append('<article class="doc-row" data-doc-row="'+s['id']+'"><div class="format">'+s['format']+'</div><div><h2><a href="'+s['id']+'.html">'+e(s['title'])+'</a></h2><p>'+e(s['filename'])+'</p><div class="chips"><span class="chip">'+e(variant)+'</span><span class="chip kind">전문</span></div></div><div class="row-author">'+e(s['author'])+'</div></article>')
        search.append({'id':s['id'],'author':s['author'],'format':s['format'],'text':s['title']+' '+s['filename']+' '+s['author']+' '+source_text(s)})
        (dest/(s['id']+'.html')).write_text(reader_page(s,a))
    body='<header class="page-hero"><div class="eyebrow">COMPLETE DOCUMENT LIBRARY</div><h1>36개 문서의 전문,<br>각 버전의 기록.</h1><p>PDF, PPTX, HTML, Markdown, DOCX의 전체 내용을 읽을 수 있습니다.<br>같은 주제의 초안과 수정본도 각각 수록했습니다.</p></header>'+filters(True)+'<div class="document-list source-catalog"><div class="result-line"><a href="../index.html">← 주제별로 보기</a><span class="result-count" data-result-count aria-live="polite">36 / 36</span></div>'+''.join(rows)+empty()+'</div><script id="search-data" type="application/json">'+jscript(search)+'</script>'
    (dest/'index.html').write_text(wrap('문서 전문과 버전',body,'../',active='sources'))

TERMS=[
('LLVM IR','LLVM의 중간 표현이다. 프론트엔드가 만든 프로그램을 공통 최적화와 백엔드가 처리할 수 있는 명령어로 나타낸다.'),
('InstCombine','작은 IR 패턴을 더 단순하거나 정해진 형태로 바꾸는 패스다. 최종 기계어를 직접 선택하는 단계와 구분한다.'),
('InstSimplify','새 명령어를 만들지 않고 기존 값이나 상수로 바꿀 수 있는지 판단하는 단순화 계층이다.'),
('ValueTracking','IR 값의 범위, 비트, 값 사이의 관계 등을 분석하는 공용 기능이다. 여러 최적화가 이 정보를 사용한다.'),
('fold','조건을 만족하는 식을 더 단순한 표현으로 바꾸는 규칙이다. 이 문서에서는 단순화 또는 정규화 규칙을 뜻한다.'),
('canonicalization','같은 의미를 표현하는 여러 모양을 후속 최적화가 다루기 쉬운 정해진 형태로 정리하는 것이다.'),
('PatternMatch','LLVM IR의 구조와 조건을 선언적으로 검사하는 도구다. m_Value, m_OneUse 같은 matcher를 조합한다.'),
('SSA value','한 번 정의한 값을 가리킨다. matcher에서 같은 값이라는 조건은 보통 비슷한 이름이 아니라 같은 IR 값을 뜻한다.'),
('one-use / multi-use','현재 값의 사용 횟수가 하나인지 여러 개인지 구분한다. 새 식으로 바꾼 뒤 기존 계산이 사라지는지에 영향을 준다.'),
('select','조건에 따라 두 값 중 하나를 선택한다. 선택하지 않은 값의 poison은 결과로 전달하지 않는다.'),
('PHI','제어 흐름이 합쳐지는 지점에서 실제로 들어온 경로에 대응하는 값을 선택한다.'),
('poison','명령어의 의미 조건을 위반한 경우에 생길 수 있는 값이다. 즉시 프로그램 전체가 실패한다는 뜻과 구분한다.'),
('undef','사용 시점에 선택할 수 있는 정의되지 않은 값을 나타낸다. 같은 SSA 이름의 일반 입력값과 같은 안정성을 가정하지 않는다.'),
('freeze','poison 또는 undef를 임의의 고정된 정상 값으로 만든다. 선택 경로가 가리던 poison을 새 식이 노출할 때 필요할 수 있다.'),
('refinement','원본이 허용하는 동작을 보존하면서 더 구체적인 결과로 바꾸는 관계다. 원본의 정의된 결과를 poison으로 바꾸는 것은 허용되지 않는다.'),
('demanded bits','현재 결과를 계산하는 데 실제로 필요한 비트다. 쓰지 않는 비트의 차이는 해당 사용처의 결과에 영향을 주지 않을 수 있다.'),
('DemandedElts','vector에서 필요한 원소를 나타내는 마스크다. 마스크의 폭은 분석 대상 타입의 원소 수와 맞아야 한다.'),
('fast-math flags','부동소수점 최적화에 추가 가정을 허용하는 플래그다. 모든 플래그를 같은 가정으로 취급하지 않는다.'),
('nsz','부동소수점 최적화에서 +0과 -0의 차이를 무시할 수 있게 하는 플래그다.'),
('nnan / ninf','각각 NaN과 무한대가 없다는 관련 가정을 허용한다. 어떤 명령어에 붙었는지와 위반 시 의미를 함께 확인한다.'),
('nuw / nsw','정수 연산에서 각각 unsigned·signed wrap을 허용하지 않는 조건이다. trunc에 붙으면 입력의 가능한 범위를 제한할 수 있다.'),
('nneg','zext 입력이 음수가 아님을 나타내는 조건이다. 전제를 만족하면 같은 입력의 sext와 결과가 같을 수 있다.'),
('intrinsic','LLVM이 의미를 알고 처리하는 내장 연산 호출이다. 이름이 비슷한 일반 라이브러리 함수와 처리 경로가 다를 수 있다.'),
('libcall','일반 라이브러리 함수 호출이다. IR의 단순한 연산이 특정 타깃에서 함수 호출로 내려가면 비용이 늘 수 있다.'),
('Alive2','LLVM IR 변환의 정확성을 형식적으로 확인하는 도구다. 성공, 반례, 시간 초과와 지원 범위를 구분한다.'),
('opt / llc','opt는 IR 최적화 패스를 실행하는 도구다. llc는 IR에서 타깃 기계어를 만드는 백엔드 도구다.'),
('lit / FileCheck','lit은 테스트를 실행한다. FileCheck는 출력에 기대하는 패턴이 나타나는지 검사한다.'),
('llvm-mca','CPU scheduling model로 코드 블록의 실행 비용을 추정하는 도구다. 실제 응용 프로그램의 실행 시간 측정과 구분한다.'),
('Block RThroughput','같은 블록을 반복할 때 모델이 추정한 처리 간격이다. 다른 조건이 같을 때 작은 값이 더 높은 처리량을 나타낸다.'),
('NFC','No Functional Change의 약자다. 기능이나 출력 동작을 바꾸지 않는 변경이라는 뜻이다.'),
('denormal / FTZ','denormal은 0에 매우 가까운 비정규 부동소수점 값이다. FTZ는 일부 작은 결과를 0으로 처리하는 모드다.'),
('saturation / wraparound','포화는 범위 밖 결과를 최솟값·최댓값으로 제한한다. wraparound는 정해진 비트 폭의 나머지 값으로 돌아간다.'),
('scale / zero point','양자화에서 정수 값과 원래 값 사이의 변환에 쓰는 배율과 기준점이다. 서로 다른 입력은 보정 없이 바로 더할 수 없다.'),
]

def auxiliary_pages():
    terms='<dl class="term-grid">'+''.join('<div class="term" id="term-'+str(i+1)+'"><dt>'+e(t)+'</dt><dd>'+e(d)+'</dd></div>'for i,(t,d)in enumerate(TERMS))+'</dl>'
    body='<article class="article"><header class="article-header"><div class="eyebrow">TERMINOLOGY</div><h1>같은 개념에는<br>같은 용어를 씁니다.</h1><p class="article-lead">기술 이름과 코드 식별자는 원래 표기를 유지합니다. 아래 설명은 이 문서집을 읽는 데 필요한 범위의 뜻입니다.</p></header>'+terms+'<section class="doc-section" style="margin-top:35px"><h2>공식 문서</h2><ul><li><a href="https://llvm.org/docs/LangRef.html">LLVM Language Reference</a></li><li><a href="https://llvm.org/docs/Passes.html">LLVM Passes</a></li><li><a href="https://llvm.org/docs/CommandGuide/llvm-mca.html">llvm-mca 문서</a></li></ul></section></article>'
    (OUT/'glossary.html').write_text(wrap('기술 용어',body,active='glossary',main_class='prose-main'))
    body='<article class="article"><header class="article-header"><div class="eyebrow">EDITORIAL GUIDE</div><h1>자료를 읽기 위한<br>편집 기준.</h1><p class="article-lead">멘티 자료의 기술 내용을 한국어 문서로 다시 구성했습니다. 근거와 적용 조건을 함께 읽을 수 있도록 정리했습니다.</p></header>'
    secs=[
      secdata('scope','수록 범위',[pblock('17명의 문서 36개를 전문으로 수록했습니다. 29개 주제로 탐색하고, 같은 주제의 초안·수정본·발표자료를 각각 열 수 있습니다.'),pblock('PDF 23개, PPTX 5개, HTML 3개, Markdown 3개, DOCX 2개입니다. 멘토 계정이 직접 게시한 자료와 별도의 채팅 캡처 이미지는 이 문서집에 넣지 않았습니다.'),pblock('작성자 표기는 원자료와 게시자를 대조한 결과입니다. 게시자가 곧 모든 내용을 독립적으로 작성했다는 보장은 아닙니다. 자료에 나온 멘토·리뷰어·도구의 도움도 구분했습니다.')]),
      secdata('writing','ASD-STE100 원칙의 한국어 적용',[pblock('ASD-STE100은 영문 기술 문서의 작성 규칙과 통제 어휘를 제공하는 표준입니다. 이 문서집은 한국어를 유지하며 안내·해설·결과 페이지에 명료한 문장과 일관된 용어의 원칙을 적용했습니다.'),['list',['한 문장에는 한 가지 핵심 내용을 적습니다.','한 문단에는 하나의 주제를 설명합니다.','주어와 적용 조건을 분명히 적습니다.','절차는 한 단계씩 번호로 나눕니다.','같은 개념에는 같은 용어를 씁니다.','코드, 명령어와 식별자는 원래 표기를 유지합니다.']],pblock('원문 전문은 작성자의 설명과 표현을 보존합니다. 글을 짧게 만들기 위해 내용을 삭제하지 않습니다. 한국어 문서의 영문 통제 사전 적합성이나 공식 인증을 주장하지 않습니다.'),['p','공식 표준: https://www.asd-ste100.org/about_STE.html']]),
      secdata('evidence','성과와 검증의 표기',[pblock('기존 패치 분석, 기여 과정, 실험·제안을 구분합니다. 연결된 PR이 모두 자료 작성자의 신규 PR이라는 뜻은 아닙니다.'),pblock('구현, 테스트, 병합 상태와 측정 수치는 각 원자료의 기록입니다. 문서 변환 중 LLVM 빌드·벤치마크를 새로 실행하거나 모든 PR의 현재 상태를 다시 조회한 결과는 아닙니다.'),pblock('Alive2의 의미 검증, IR 변화, 기계어 변화, llvm-mca의 정적 추정과 실제 실행 시간은 별도로 표시합니다. 성공한 작은 예제의 수치를 전체 응용 프로그램의 개선율로 바꾸지 않습니다.')]),
      secdata('preservation','문서 전문과 페이지 배치',[pblock('문서를 열면 요약 대신 전문을 바로 읽을 수 있습니다. 각 버전의 내용·구현 상태·수치를 합치거나 최신 상태로 바꾸지 않았습니다. 기존의 짧은 해설은 전문 뒤의 핵심 원리와 편집 주석에서 별도로 제공합니다.'),pblock('PDF의 본문은 읽기 순서·코드 블록·표를 나누고 그림을 함께 제공합니다. 스크린샷과 이미지 속 글자는 로컬 문자 인식으로 옮겼습니다. PDF 336쪽과 PPTX 67장의 원래 페이지 이미지도 모두 포함합니다. 본문과 그림 보기, 원래 페이지 배치 보기를 바꿀 수 있습니다.'),pblock('이미지 문자 인식과 일부 PDF 글꼴의 코드 기호는 정확하지 않을 수 있습니다. 이 경우 페이지 배치나 그림을 함께 확인할 수 있습니다. DOCX·Markdown·HTML의 원문 단락·표·코드·그림도 전문으로 수록했습니다.'),pblock('원자료에서 번호나 식의 경계, 집계가 달라지는 부분은 편집 주석으로 밝혔습니다. 미첨부 작업 파일 링크에는 미첨부 표시를 붙였습니다. 제출되지 않은 측정 로그와 스크립트는 새로 만들어 채우지 않았습니다.')]),
      secdata('privacy','웹 문서에 포함한 정보',[pblock('문서의 작성자 이름과 기술 내용, 공개 이슈·PR 링크를 제공합니다. Discord 대화, 계정 식별번호, 아바타와 게시자 대조표는 배포 파일에 넣지 않았습니다.'),pblock('발견한 개인 연락처와 사용자 홈 디렉터리 경로는 본문과 페이지 이미지에서 생략했습니다. 원본 첨부파일 자체는 변경하지 않았습니다.')]),
      secdata('attribution','출처와 저작물 표기',[pblock('각 문서의 출처는 해당 멘티의 제출 자료입니다. 코드 발췌와 공개 리뷰는 연결된 LLVM 프로젝트의 원문을 함께 확인할 수 있습니다.'),pblock('원자료의 권리는 각 작성자와 해당 저작권자에게 있습니다. LLVM 코드에는 프로젝트의 Apache-2.0 WITH LLVM-exception 라이선스를 확인하세요.'),['p','LLVM 라이선스: https://llvm.org/LICENSE.txt']]),
    ]
    for s in secs:
        body+='<section class="doc-section" id="'+s['id']+'"><h2>'+s['title']+'</h2>'
        for b in s['blocks']:
            if b[0]=='p' and 'https://' in b[1]:
                text,url=b[1].split('https://',1);body+='<p>'+e(text)+'<a href="https://'+e(url)+'">공식 문서 보기 ↗</a></p>'
            else:body+=block(b)
        body+='</section>'
    body+='</article>'
    (OUT/'about.html').write_text(wrap('편집 기준',body,active='about',main_class='prose-main'))

def pblock(t):return ['p',t]
def secdata(id,title,blocks):return dict(id=id,title=title,blocks=blocks)

def run():
    if len(A)!=29 or len(S)!=36:raise RuntimeError('Reviewed document counts changed. Review the catalog before building.')
    for a in A:
        if set(a['sources'])!={s['path']for s in S_BY_ART[a['id']]}:raise RuntimeError('Unmatched source: '+a['id'])
    (OUT/'assets').mkdir(parents=True,exist_ok=True)
    for f in ['site.css','site.js']:shutil.copyfile(ROOT/'theme'/f,OUT/'assets'/f)
    (OUT/'assets/favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" rx="5" fill="#a84625"/><path d="M12 9h5v20h13v4H12z" fill="#fff"/></svg>')
    (OUT/'.nojekyll').touch()
    home();article_pages();source_pages();auxiliary_pages();build_results.build(ROOT,wrap,icon);build_benchmarks.build(ROOT,wrap,icon)
    manifest=dict(title='LLVM 멘티 기술 문서',edited=DATE,articles=len(A),sources=len(S),participants=len(AUTHORS),full_text=True,results='results.html',formats=dict(Counter(s['format']for s in S)),documents=[{k:s[k]for k in ['id','filename','author','article','format','sha256']}for s in S])
    manifest['benchmarks']={'page':'benchmarks.html','application_conditions':42,'application_charts':47,'pr_report':19,'backend_projects':241,'backend_pairs':78742}
    review=json.loads((ROOT/'content/benchmarks/review/repeat-analysis.json').read_text())
    manifest['edited']=max(DATE,review['created'])
    manifest['benchmarks'].update(reviewed=review['created'],AB_pairs=2480,AA_pairs=60,raw_observations=5080,mean_direction={'decrease':12,'increase':12,'mixed':18},linked_mentees=4,linked_PRs=7)
    import build_pr229086
    pr229086=build_pr229086.load(ROOT)
    manifest['edited']=max(manifest['edited'],pr229086['published'])
    manifest['benchmarks']['additional_studies']=[{'PR':229086,'page':'benchmarks/pr229086.html','published':pr229086['published'],'model':'BlazeFace back W8A8','threads':1,'N60_series':4,'historical_N12_series':4,'samples':576}]
    (OUT/'catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Built {len(A)} articles + {len(S)} source pages; {len(list(OUT.rglob("*.html")))} HTML files.')

if __name__=='__main__':run()
