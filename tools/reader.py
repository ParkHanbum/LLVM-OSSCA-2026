"""Complete document readers shared by topic URLs and individual version URLs."""
from html import escape
from html.parser import HTMLParser
import re

def e(value):return escape(str(value),quote=True)

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def body_with_headings(s,page):
    text=re.sub(r'(?m)^[ \t]+$','',page.get('body',''));prefix=s['id']+'-p'+str(page['n'])+'-'
    ids=re.findall(r'\bid="([^"]+)"',text)
    for old in ids:
        text=text.replace('id="'+old+'"','id="'+prefix+old+'"').replace('href="#'+old+'"','href="#'+prefix+old+'"')
    headings=[];n=0
    def heading(m):
        nonlocal n
        n+=1;attrs=m[2];idmatch=re.search(r'\bid="([^"]+)"',attrs)
        key=idmatch[1]if idmatch else prefix+'heading-'+str(n)
        if not idmatch:attrs+=' id="'+key+'"'
        p=Text();p.feed(m[3]);title=' '.join(p.parts).strip()
        if m[1]in['2','3']:headings.append((key,title[:65]))
        return '<h'+m[1]+attrs+'>'+m[3]+'</h'+m[1]+'>'
    text=re.sub(r'<h([2-5])([^>]*)>(.*?)</h\1>',heading,text,flags=re.S)
    return text,headings

def headings(s):
    if len(s['pages'])==1 and not s['pages'][0].get('image'):
        _,items=body_with_headings(s,s['pages'][0])
        return items or [('page-1','본문')]
    return [('page-'+str(p['n']),str(p['n']).zfill(2)+' · '+p['title'][:36]+('…'if len(p['title'])>36 else''))for p in s['pages']]

def controls(s):
    if not any(p.get('image')for p in s['pages']):return ''
    return '<div class="reading-mode" role="group" aria-label="문서 읽기 방식"><span>읽기 방식</span><button type="button" data-reading="text" aria-pressed="true">본문과 그림</button><button type="button" data-reading="layout" aria-pressed="false">원래 페이지 배치</button><small>두 보기 모두 이 페이지에서 확인할 수 있습니다.</small></div>'

def sections(s):
    out=[]
    for page in s['pages']:
        n=page['n'];title=page['title'];body,_=body_with_headings(s,page)
        out.append('<section class="doc-section full-source-section" data-source="'+s['id']+'" data-page="'+str(n)+'" id="page-'+str(n)+'">')
        if len(s['pages'])>1:
            out.append('<div class="page-marker"><span>'+s['format']+' · '+str(n).zfill(2)+' / '+str(len(s['pages'])).zfill(2)+'</span></div>')
            # Body retains every original heading; the extracted running title is a locator.
            out.append('<h2 class="page-title">'+e(title)+'</h2>')
        out.append('<div class="reading-text"><div class="source-body">'+body+'</div>')
        if page.get('image_text'):
            out.append('<div class="recognized-section"><h3>이미지 안의 내용</h3><p class="recognition-note">문자 인식으로 옮긴 텍스트입니다. 식과 기호는 페이지 배치와 함께 확인하세요.</p>'+page['image_text']+'</div>')
        for i,figure in enumerate(page.get('figures',[])):
            out.append('<figure class="source-figure"><a href="'+figure['image']+'"><img src="'+figure['image']+'" width="'+str(figure['width'])+'" height="'+str(figure['height'])+'" alt="'+e(f'{s["author"]} 자료 {n}쪽의 코드·설명 그림 {i+1}')+'" loading="lazy" decoding="async"></a><figcaption>'+str(n)+'쪽 · 그림 '+str(i+1)+' <a href="'+figure['image']+'">확대해서 보기 ↗</a></figcaption>')
            if figure.get('text'):
                out.append('<details class="figure-transcript" open><summary>그림 안의 텍스트 · 문자 인식</summary><pre>'+e(figure['text'])+'</pre><p class="recognition-note">이미지에서 읽은 문자입니다. 코드 기호는 그림에서 확인하세요.</p></details>')
            out.append('</figure>')
        if page.get('native_body'):
            out.append('<details class="native-layer"><summary>PDF 문자층의 내용도 확인하기</summary><div class="source-body">'+page['native_body']+'</div></details>')
        if page.get('links'):
            out.append('<div class="page-links"><h3>이 페이지에 연결된 자료</h3><ul>'+''.join('<li><a href="'+e(link['url'])+'" rel="noopener noreferrer">'+e(link['text'])+'</a></li>'for link in page['links'])+'</ul></div>')
        out.append('</div>')
        if page.get('image'):
            opened=bool(page.get('raster_full')or page.get('conversion_note'))
            out.append('<details class="page-layout"'+(' open'if opened else'')+' data-original-open="'+str(opened).lower()+'"><summary>'+e('페이지 배치·기호·도식 확인하기')+'</summary>')
            if page.get('conversion_note'):out.append('<p class="recognition-note">'+e(page['conversion_note'])+'</p>')
            if page.get('reading_method')=='ocr':out.append('<p class="recognition-note">아래 본문은 문자 인식으로 옮겼습니다. 원래 슬라이드를 함께 제공합니다.</p>')
            out.append('<figure class="source-facsimile"><a href="'+page['image']+'" aria-label="'+e(f'{s["filename"]} {n}쪽 확대')+'"><img src="'+page['image']+'" alt="'+e(f'{s["title"]} · {n}쪽 전체 페이지')+'" loading="lazy" decoding="async" width="1440" height="'+str(round(page['ratio']*1440))+'"></a><figcaption><span>'+e(s['filename'])+' · '+str(n)+'/'+str(len(s['pages']))+(' · 연락처·로컬 경로 생략'if page.get('redacted')else'')+'</span><a href="'+page['image']+'">확대해서 보기 ↗</a></figcaption></figure></details>')
        out.append('</section>')
    return ''.join(out)
