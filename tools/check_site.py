"""Verify the generated GitHub Pages directory without extra dependencies."""
from pathlib import Path
from collections import Counter
from html.parser import HTMLParser
from html import escape
from urllib.parse import urlsplit,unquote,parse_qs
import csv,hashlib,json,re,sys
import reader
from check_review import check_review
from check_pr229086 import check_pr229086

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs'
errors=[]
class Page(HTMLParser):
    def __init__(self,path):
        super().__init__(convert_charrefs=True);self.path=path;self.ids=set();self.links=[];self.h1=0;self.lang=None;self.title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html':self.lang=a.get('lang')
        if tag=='title':self.title=True
        if tag=='h1':self.h1+=1
        if 'id'in a:
            if a['id']in self.ids:errors.append(f'{self.path.relative_to(SITE)}: duplicate id {a["id"]}')
            self.ids.add(a['id'])
        for name in ['href','src']:
            if a.get(name):self.links.append(a[name])
        if tag=='img'and not a.get('alt'):errors.append(f'{self.path.relative_to(SITE)}: image without alternative text')
        if tag in ['iframe','object','embed','base']:errors.append(f'{self.path.relative_to(SITE)}: unsupported embedded element {tag}')
        for key in a:
            if key.lower().startswith('on'):errors.append(f'{self.path.relative_to(SITE)}: inline event handler {key}')

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
def text(markup):
    p=Text();p.feed(markup);return ''.join(p.parts)
def glyphs(markup):return Counter(c for c in text(markup)if not c.isspace())

def check_full_content(sources):
    figures=0;tables=0
    for s in sources:
        target=SITE/'sources'/(s['id']+'.html');rendered=target.read_text()
        if '<details class="transcript">'in rendered:errors.append(s['id']+': old hidden transcript reader')
        for page in s['pages']:
            marker='data-source="'+s['id']+'" data-page="'+str(page['n'])+'"'
            if marker not in rendered:errors.append(s['id']+': missing full page '+str(page['n']))
            if not text(page.get('body','')).strip():errors.append(s['id']+': empty full text body '+str(page['n']))
            # Compare the exact submitted body to the generated reader, before adding
            # navigation or captions. Namespace changes must not remove any text.
            expected=reader.body_with_headings(s,page)[0]
            if expected not in rendered:errors.append(s['id']+': full body is not present verbatim')
            for figure in page.get('figures',[]):
                figures+=1
                if figure['image']not in rendered:errors.append(s['id']+': missing figure')
                dest=(SITE/'sources'/figure['image']).resolve()
                if not dest.is_file():errors.append(s['id']+': missing figure image')
            tables+=page.get('native_tables',0)
    results=json.loads((ROOT/'content/results.json').read_text())
    if {p['author']for p in results['participants']}!={s['author']for s in sources}:errors.append('Results omit a participant')
    if {sid for p in results['participants']for sid in p['sources']}!={s['id']for s in sources}:errors.append('Results omit a source document')
    original=next(s for s in sources if s['id']==results['benchmark_source'])['pages'][0]['body']
    original_text=text(original)
    for series in results['series']:
        for row in series['rows']:
            if not(0<row['after']<=row['before']):errors.append('Invalid runtime data')
            for key in ['before','after']:
                if f'{row[key]:.3f}'not in original_text:errors.append('Runtime value does not match source')
    if not(SITE/'results.html').is_file():errors.append('Missing contribution results page')
    return figures,tables

def check_benchmarks():
    source=ROOT/'content/benchmarks'
    data=json.loads((source/'applications.json').read_text())
    cases=data['conditions'];page=(SITE/'benchmarks.html').read_text()
    if len(cases)!=42 or len({c['case_id']for c in cases})!=42:errors.append('Application benchmark coverage is incomplete')
    if Counter(c['status']for c in cases)!={'uncertain':40,'improved':1,'regressed':1}:errors.append('Application benchmark verdicts changed')
    chart_files=list((SITE/'assets/benchmarks/charts').glob('*.svg'))
    if len(chart_files)!=47:errors.append('Benchmark charts are incomplete')
    for chart in chart_files:
        if chart.read_bytes()!=(source/'charts'/chart.name).read_bytes():errors.append('Original benchmark chart changed: '+chart.name)
        if 'assets/benchmarks/charts/'+chart.name not in page:errors.append('Unlinked benchmark chart: '+chart.name)
    for case in cases:
        if 'data-archive-case="'+case['case_id']+'"'not in page:errors.append('Missing application condition: '+case['case_id'])
        for key in ['A','B']:
            if abs((1-case['ratio'])*100-case['reduction'])>0.0006:errors.append('Application ratio direction mismatch')
            if f'{case["user"][key]:.6f}'not in page:errors.append('Missing exact application time')
        if len(case['sensitivity'])!=3 or case['used_pairs']!=case['pairs']-2:errors.append('Benchmark aggregation record incomplete')
        # Validate source provenance, including the fork's independently numbered PR.
        for number,item in case['PR_transformations'].items():
            expected='https://github.com/'+('ThePo1es/llvm-project'if number=='2'else'llvm/llvm-project')+'/pull/'+number
            if item['url']!=expected:errors.append('Incorrect PR repository provenance')
    report=json.loads((source/'pr19-report.json').read_text())
    report_page=(SITE/'benchmarks/pr19.html').read_text()
    if len(report['blocks'])!=183:errors.append('19-PR report block count changed')
    for i,block in enumerate(report['blocks']):
        if 'data-report-block="'+str(i)+'"'not in report_page:errors.append('Missing full report block')
        cells=[block['text']]if block['kind']=='paragraph'else[c for row in block['rows']for c in row]
        for value in cells:
            if escape(value,quote=True).replace('\n','<br>')not in report_page:errors.append('19-PR report text was removed')
    counts=Counter();projects=set();modules=set()
    for profile in ['avx2-v3','avx512-v4']:
        public=SITE/'assets/benchmarks/backend'/(profile+'.csv')
        if public.read_bytes()!=(source/'backend'/(profile+'.csv')).read_bytes():errors.append('Backend published CSV differs from reviewed data')
        with public.open(newline='')as handle:
            for row in csv.DictReader(handle):
                counts[(profile,row['status'])]+=1;projects.add(row['path'].split('/')[1]);modules.add(row['path'])
                if row['status']=='identical'and not(row['before_assembly_sha256']and row['before_assembly_sha256']==row['after_assembly_sha256']and row['before_returncode']==row['after_returncode']=='0'):errors.append('Backend identical status lacks equal successful outputs')
    expected={('avx2-v3','identical'):39116,('avx2-v3','codegen_error'):255,('avx512-v4','identical'):39222,('avx512-v4','codegen_error'):149}
    if counts!=expected or len(projects)!=241 or len(modules)!=39371:errors.append('Backend coverage or error accounting changed')
    if len(list((SITE/'benchmarks/projects').glob('*.html')))!=241:errors.append('Missing backend project pages')
    return dict(application_conditions=len(cases),application_charts=len(chart_files),pr_report_blocks=len(report['blocks']),backend_projects=len(projects),backend_pairs=sum(counts.values()),review=check_review(ROOT,SITE,errors),PR229086=check_pr229086(ROOT,SITE,errors))

def run():
    if not SITE.is_dir():raise SystemExit('docs/ does not exist. Run tools/build_site.py first.')
    pages={}
    privacy=re.compile(r'file:///|/(?:Users|home)/[^\s<>]+|958556528472895588|cdn\.discordapp\.com/attachments|discord\.com/channels|[A-Za-z]:\\Users\\')
    for p in SITE.rglob('*'):
        if p.is_symlink():errors.append('Symbolic link in publish directory: '+str(p.relative_to(SITE)))
        if p.is_file() and p.stat().st_size>25*1024*1024:errors.append('File exceeds 25 MiB: '+str(p.relative_to(SITE)))
        approved_csv={SITE/'assets/benchmarks/application-summary.csv',SITE/'assets/benchmarks/backend/avx2-v3.csv',SITE/'assets/benchmarks/backend/avx512-v4.csv'}
        approved_csv.update(SITE/'assets/benchmarks/review'/name for name in ['repeat-summary.csv','contribution-links.csv','paired-observations.csv','raw-measurements.csv'])
        approved_csv.update(SITE/'assets/benchmarks/pr229086'/name for name in ['clean-60-pairs.csv','aa-60-pairs.csv','profile-aa-60-pairs.csv','diagnostic-add-60-pairs.csv','initial-12-pair-records.csv'])
        if p.suffix.lower()in['.pdf','.pptx','.docx','.csv']and p not in approved_csv:errors.append('Unexpected raw attachment/audit file: '+str(p.relative_to(SITE)))
        if p.suffix.lower()in['.html','.json','.js','.css','.svg','.csv','.txt']:
            text=p.read_text()
            if privacy.search(text):errors.append('Private chat reference or local path: '+str(p.relative_to(SITE)))
            if 'lvsy@'in text or '[이름 입력]'in text:errors.append('Unremoved contact/placeholder: '+str(p.relative_to(SITE)))
        if p.suffix=='.html':
            obj=Page(p);obj.feed(p.read_text());pages[p.resolve()]=obj
            if obj.lang!='ko':errors.append(str(p.relative_to(SITE))+': missing Korean language metadata')
            if not obj.title:errors.append(str(p.relative_to(SITE))+': missing title')
            if obj.h1!=1:errors.append(str(p.relative_to(SITE))+f': expected one h1, found {obj.h1}')
    checked=0
    for p,obj in pages.items():
        for url in obj.links:
            parts=urlsplit(url)
            if parts.scheme or parts.netloc:
                if parts.scheme not in ['http','https']:errors.append(f'{p.relative_to(SITE)}: unsafe link scheme {url[:70]}')
                continue
            if parts.path.startswith('/'):
                errors.append(f'{p.relative_to(SITE)}: root-relative link breaks project Pages: {url}');continue
            target=(p.parent/unquote(parts.path)).resolve()if parts.path else p
            if parts.path.endswith('/')or target.is_dir():target/= 'index.html'
            if not target.is_relative_to(SITE.resolve())or not target.is_file():
                errors.append(f'{p.relative_to(SITE)}: missing local target {url}');continue
            if target in [(SITE/'assets/site.css').resolve(),(SITE/'assets/site.js').resolve()]:
                expected=hashlib.sha256(target.read_bytes()).hexdigest()[:12]
                if parse_qs(parts.query).get('v')!=[expected]:errors.append(f'{p.relative_to(SITE)}: stale screen asset version')
            checked+=1
            if parts.fragment and target.suffix=='.html':
                if target not in pages or unquote(parts.fragment)not in pages[target].ids:errors.append(f'{p.relative_to(SITE)}: missing anchor {url}')
    manifest=json.loads((SITE/'catalog.json').read_text())
    if (manifest['articles'],manifest['sources'],manifest['participants'])!=(29,36,17):errors.append('Catalog document counts are incorrect')
    if manifest['formats']!={'PDF':23,'PPTX':5,'HTML':3,'MD':3,'DOCX':2}:errors.append('Catalog format counts are incorrect')
    sources=json.loads((ROOT/'content/sources.json').read_text())
    figure_count,table_count=check_full_content(sources)
    benchmarks=check_benchmarks()
    frame_counts={kind:sum(len(s['pages'])for s in sources if s['format']==kind)for kind in ['PDF','PPTX']}
    if frame_counts!={'PDF':336,'PPTX':67}:errors.append('PDF/PPTX source pages are incomplete')
    frames=[page['image']for s in sources for page in s['pages']if page.get('image')]
    if len(frames)!=403 or len(set(frames))!=403:errors.append('Source frame coverage is incomplete')
    if not (SITE/'.nojekyll').exists():errors.append('Missing .nojekyll marker')
    if errors:
        for err in errors:print('ERROR',err)
        raise SystemExit(1)
    size=sum(p.stat().st_size for p in SITE.rglob('*')if p.is_file())
    report=dict(html_pages=len(pages),articles=29,complete_documents=36,participants=17,pdf_pages=336,pptx_slides=67,page_images=403,inline_pdf_figures=figure_count,pdf_tables=table_count,benchmarks=benchmarks,local_links_checked=checked,publish_bytes=size,errors=0)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':run()
