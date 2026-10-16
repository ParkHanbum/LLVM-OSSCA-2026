"""Add reading-order HTML and figure crops without shortening the submitted text.

Run prepare, recognize the generated image jobs with recognize_text.swift on macOS,
then run finish. OCR is an additional reading aid; page images remain authoritative.
The publication build itself needs only the checked-in JSON and images.
"""
from __future__ import annotations
import argparse, json, re, statistics, shutil, io
from pathlib import Path
from html import escape
from collections import Counter
import pdfplumber
from PIL import Image, ImageStat
from lxml import html
from convert_sources import clean, redact_boxes

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.작업자료'
DOCS=ROOT/'docs'
MONO=re.compile(r'mono|menlo|consolas|courier|inconsolata',re.I)

def bounds(items):
    return (min(c['x0']for c in items),min(c['top']for c in items),
            max(c['x1']for c in items),max(c['bottom']for c in items))

def cuts(items,axis):
    lo,hi=('x0','x1')if axis=='x'else('top','bottom')
    spans=sorted((c[lo],c[hi])for c in items)
    end=spans[0][1];gaps=[]
    for start,stop in spans[1:]:
        if start>end:gaps.append((start-end,(start+end)/2))
        end=max(end,stop)
    return gaps

def reading_regions(chars,depth=0):
    """Whitespace cuts keep side-by-side before/after examples separate."""
    if len(chars)<8 or depth>18:return [chars]
    x0,t,x1,b=bounds(chars)
    size=statistics.median(c['size']for c in chars)
    xs=[(g,p)for g,p in cuts(chars,'x')if g>max(13,size*1.2) and x0+35<p<x1-35]
    ys=[(g,p)for g,p in cuts(chars,'y')if g>max(7,size*.65)]
    # A wide gutter is a column break. Otherwise detach headings before columns.
    if xs:
        _,p=max(xs)
        left=[c for c in chars if (c['x0']+c['x1'])/2<p]
        right=[c for c in chars if (c['x0']+c['x1'])/2>=p]
        if len(left)>3 and len(right)>3:
            return reading_regions(left,depth+1)+reading_regions(right,depth+1)
    if ys:
        _,p=max(ys)
        top=[c for c in chars if (c['top']+c['bottom'])/2<p]
        bottom=[c for c in chars if (c['top']+c['bottom'])/2>=p]
        if top and bottom:return reading_regions(top,depth+1)+reading_regions(bottom,depth+1)
    return [chars]

def lines_from_chars(chars):
    rows=[]
    for c in sorted(chars,key=lambda c:(round(c.get('baseline',c['bottom']),1),c['x0'])):
        base=c.get('baseline',c['bottom'])
        if rows and abs(base-rows[-1]['base'])<=max(1.6,c['size']*.10):
            rows[-1]['chars'].append(c)
        else:rows.append({'base':base,'chars':[c]})
    lines=[]
    left=min((c['x0']for c in chars if c['text'].strip()),default=0)
    for row in rows:
        cs=sorted(row['chars'],key=lambda c:c['x0']);text='';prev=None
        widths=[c['x1']-c['x0']for c in cs if c['text'].strip()]
        step=statistics.median(widths)if widths else 6
        mono=sum(len(c['text'])for c in cs if MONO.search(c.get('fontname','')))/max(1,sum(len(c['text'])for c in cs))>.5
        for c in cs:
            if prev:
                gap=c['x0']-prev['x1']
                if gap>max(1.4,step*.38) and not text.endswith(' ')and not c['text'].startswith(' '):
                    text+=' '*max(1,round(gap/step)) if mono else ' '
            text+=c['text'];prev=c
        text=clean(text).strip()
        if not text:continue
        box=bounds(cs)
        # Keep literal code as code even in slide decks that use a proportional font.
        code=mono or bool(re.match(r'^(?:[%@][\w.]+\s*=|define\b|declare\b|ret\b|;\s*(?:CHECK|RUN)|(?:const |auto |if \(|return |} |\{|#include)|[\w.]+:\s*$)',text))
        visible=[c for c in cs if c['text'].strip()]
        visible_box=bounds(visible)if visible else box
        lines.append({'text':text,'mono':code,'size':max(c['size']for c in cs),
                      'box':box,'indent':max(0,round((box[0]-left)/max(step,3)))})
        lines[-1]['indent']=max(0,round((visible_box[0]-left)/max(step,3)))
    return lines

def render_lines(lines,base_size=15):
    blocks=[];code=[];para=[];last=None
    def flush_code():
        if code:blocks.append('<pre><code>'+escape('\n'.join(code))+'</code></pre>');code.clear()
    def flush_para():
        if para:blocks.append('<p>'+escape(' '.join(para))+'</p>');para.clear()
    for line in lines:
        txt=line['text'];box=line['box']
        if line.get('mono'):
            flush_para();code.append(' '*min(32,line.get('indent',0))+txt)
        else:
            flush_code()
            if line.get('size',base_size)>base_size*1.45 and len(txt)<180:
                flush_para();blocks.append('<h3>'+escape(txt)+'</h3>')
            elif re.match(r'^[•●▪◆✓✔→➜]|^(?:\d+[.)]|[-–])\s',txt):
                flush_para();blocks.append('<p class="source-bullet">'+escape(txt)+'</p>')
            else:
                gap=box[1]-last['box'][3]if last else 0
                if gap>base_size*.7:flush_para()
                para.append(txt)
        last=line
    flush_code();flush_para()
    return ''.join(blocks)

def inside(char,box):
    x=(char['x0']+char['x1'])/2;y=(char['top']+char['bottom'])/2
    return box[0]<=x<=box[2]and box[1]<=y<=box[3]

def native_page_body(pg,chars,size):
    used=set();tables=[]
    for table in pg.find_tables():
        header=[b for b in table.rows[0].cells if b is not None]
        normalized=None
        if len(header)>=2:
            # Underlined links can create false nested cells. Reconstruct the
            # regular header columns and first-column row edges instead.
            first=header[0]
            row_edges=sorted({round(v,5)for row in table.rows for cell in row.cells if cell and abs(cell[0]-first[0])<1 and abs(cell[2]-first[2])<1 for v in [cell[1],cell[3]]})
            borders=sorted({round((r['top']+r['bottom'])/2,5)for r in pg.rects
                            if r['height']<2 and abs(r['x0']-first[0])<1 and abs(r['x1']-first[2])<1
                            and table.bbox[1]-2<=r['top']<=table.bbox[3]+2})
            if len(borders)>=3:row_edges=borders
            if len(row_edges)>=3:
                normalized=[]
                for top,bottom in zip(row_edges,row_edges[1:]):
                    cells=[]
                    for col in header:
                        cells.append((col[0],top,col[2],bottom))
                    normalized.append(cells)
        rows=[];seen=set();assigned=set()
        for row_cells in normalized if normalized else [row.cells for row in table.rows]:
            cells=[]
            for box in row_cells:
                if box is None or box in seen:continue
                seen.add(box)
                cc=[c for c in chars if c['_i']not in assigned and inside(c,box)]
                if cc:
                    assigned.update(c['_i']for c in cc)
                    cells.append(render_lines(lines_from_chars(cc),size))
                else:cells.append('')
            if any(cells):
                if len(cells)==2 and not cells[0]and rows and len(rows[-1])==2:
                    rows[-1][1]+=cells[1]
                else:rows.append(cells)
        if len(rows)<2 or sum(sum(bool(c)for c in row)>=2 for row in rows)<2:continue
        body='<div class="table-wrap"><table>'+''.join('<tr>'+''.join('<'+('th'if i==0 else'td')+'>'+c+'</'+('th'if i==0 else'td')+'>'for c in row)+'</tr>'for i,row in enumerate(rows))+'</table></div>'
        x0,t,x1,b=table.bbox
        tables.append(dict(x0=x0,top=t,x1=x1,bottom=b,size=size,html=body))
        used.update(assigned)
    normal=[c for c in chars if c['_i']not in used]
    objects=normal+tables;out=[]
    for region in reading_regions(objects)if objects else []:
        native=[c for c in region if 'html'not in c]
        for table in sorted((c for c in region if 'html'in c),key=lambda c:c['top']):
            before=[c for c in native if c['top']<table['top']]
            native=[c for c in native if c['top']>=table['top']]
            if before:out.append('<div class="pdf-region">'+render_lines(lines_from_chars(before),size)+'</div>')
            out.append(table['html'])
        if native:out.append('<div class="pdf-region">'+render_lines(lines_from_chars(native),size)+'</div>')
    return ''.join(out),len(tables)

def prepare(source):
    WORK.mkdir(exist_ok=True);imgs=WORK/'ocr-pages';imgs.mkdir(exist_ok=True)
    figures=DOCS/'assets/figures';figures.mkdir(exist_ok=True)
    sources=json.loads((ROOT/'content/sources.json').read_text());jobs=[];audit=[]
    for s in sources:
        if s['format']!='PDF':continue
        with pdfplumber.open(source/s['path'])as pdf:
            for pg,page in zip(pdf.pages,s['pages']):
                key=f'{s["id"]}-{page["n"]:03d}'
                original=Image.open(DOCS/page['image'].removeprefix('../')).convert('RGB')
                png=imgs/(key+'.png')
                if not png.exists():original.save(png)
                jobs.append(dict(id=key,path=str(png)))
                redactions=redact_boxes(pg)
                chars=[]
                for ci,c in enumerate(pg.chars):
                    if not c['text']:continue
                    if any(inside(c,b)for b in redactions):continue
                    cc=dict(c);cc['_i']=ci;cc['baseline']=pg.height-c.get('matrix',(0,0,0,0,0,pg.height-c['bottom']))[5]
                    chars.append(cc)
                regions=reading_regions(chars)if chars else []
                size=statistics.median(c['size']for c in chars)if chars else 15
                page['body'],page['native_tables']=native_page_body(pg,chars,size)
                page['native_chars']=len(chars)
                page['links']=[dict(url=link['uri'],text=link['uri'])for link in pg.hyperlinks
                               if link.get('uri','').startswith(('https://','http://'))]
                page['links']=list({link['url']:link for link in page['links']}.values())
                page['figures']=[]
                boxes=[];image_by_box={}
                for im in pg.images:
                    box=(max(0,im['x0']),max(0,im['top']),min(pg.width,im['x1']),min(pg.height,im['bottom']))
                    if box[2]-box[0]<45 or box[3]-box[1]<25:continue
                    if any(sum(abs(a-b)for a,b in zip(box,old))<5 for old in boxes):continue
                    boxes.append(box)
                    image_by_box[box]=im
                for j,box in enumerate(sorted(boxes,key=lambda b:(b[1],b[0]))):
                    scale=original.width/pg.width
                    crop=original.crop(tuple(round(v*scale)for v in box))
                    # Flat code-panel backgrounds contain native text; their text is above.
                    stat=ImageStat.Stat(crop.resize((100,100)))
                    if max(stat.stddev)<3:continue
                    raw_image=None;image_info=image_by_box[box]
                    try:
                        raw=image_info['stream'].get_data()
                        try:raw_image=Image.open(io.BytesIO(raw));raw_image.load()
                        except Exception:
                            iw,ih=image_info['srcsize'];mode='RGB'if len(raw)==iw*ih*3 else'L'if len(raw)==iw*ih else None
                            if mode:raw_image=Image.frombytes(mode,(iw,ih),raw)
                    except Exception:pass
                    if raw_image is not None:
                        flat=max(ImageStat.Stat(raw_image.resize((80,80))).stddev)<2
                        overlay=sum(bool(c['text'].strip())for c in chars if inside(c,box))
                        if flat and overlay>=20:
                            raw_image.close();continue
                    full=(box[2]-box[0])*(box[3]-box[1])/(pg.width*pg.height)>.85
                    if full:
                        page['raster_full']=True
                        # The umask submission is already a complete high-resolution
                        # raster. Retain that original detail instead of downsampling it.
                        if s['id']=='s036'and raw_image is not None and not redactions:
                            raw_image.convert('RGB').save(DOCS/page['image'].removeprefix('../'),'WEBP',quality=94,method=4)
                        if raw_image is not None:raw_image.close()
                        continue
                    if raw_image is not None:
                        aspect=raw_image.width/raw_image.height/(crop.width/crop.height)
                        if .97<aspect<1.03 and raw_image.width*raw_image.height>crop.width*crop.height*1.25 and not image_info['stream'].attrs.get('SMask')and not any(not(b[2]<box[0]or b[0]>box[2]or b[3]<box[1]or b[1]>box[3])for b in redactions):
                            crop=raw_image.convert('RGB')
                        else:raw_image.close()
                    rel=f'assets/figures/{key}-{j+1:02d}.webp';dest=DOCS/rel
                    crop.save(dest,'WEBP',quality=94,method=4)
                    bbox=[round(v,2)for v in box]
                    page['figures'].append(dict(image='../'+rel,box=bbox,
                                               width=crop.width,height=crop.height))
                page['layout_lines']=[line for r in regions for line in lines_from_chars(r)]
                page['page_size']=[pg.width,pg.height]
                audit.append(dict(id=key,native_chars=len(chars),figures=len(page['figures']),redacted=bool(redactions)))
                original.close();pg.close()
        print(s['id'],len(s['pages']),'pages prepared',flush=True)
    (WORK/'expanded-sources.json').write_text(json.dumps(sources,ensure_ascii=False))
    (WORK/'ocr-jobs.json').write_text(json.dumps(jobs))
    (WORK/'coverage-preparation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    print('Prepared',len(jobs),'OCR jobs',flush=True)

def ocr_lines(result,width,height):
    lines=[]
    for row in result.get('lines',[]):
        text=clean(row['text']);box=[row['x']*width,row['y']*height,(row['x']+row['w'])*width,(row['y']+row['h'])*height]
        if not text.strip():continue
        lines.append(dict(text=text,box=box,size=row['h']*height,
                          confidence=row['confidence'],mono=False,indent=0))
    return lines

def order_ocr(lines):
    # Use the same whitespace segmentation as native text, but OCR lines are indivisible.
    objs=[dict(x0=l['box'][0],top=l['box'][1],x1=l['box'][2],bottom=l['box'][3],
               size=l['size'],line=l)for l in lines]
    regions=reading_regions(objs)if objs else []
    return [o['line']for r in regions for o in sorted(r,key=lambda o:(round(o['top']/4),o['x0']))]

def raster_slide_body(page,ocr):
    """Use the original selectable code instead of recognizing C++ punctuation."""
    specs={3:[('// fs/fs_struct.c',1,None)],
           5:[('// syscall_wrappers/umask.h',2,None)],
           6:[('// src/sys/stat/linux/umask.cpp',2,None),('# include/sys/stat.yaml',0,5)],
           7:[('// test/src/sys/stat/umask_test.cpp',1,None),('$ ninja',0,3)]}
    native=page['layout_lines'];blocks=[]
    for prefix,braces,count in specs.get(page['n'],[]):
        start=next((i for i,l in enumerate(native)if l['text'].startswith(prefix)),None)
        if start is None:raise RuntimeError('Missing original code block')
        selected=[];closed=0
        for line in native[start:]:
            selected.append(line)
            if line['text']=='}':closed+=1
            if (count and len(selected)>=count)or(braces and closed>=braces):break
        box=(min(l['box'][0]for l in selected),min(l['box'][1]for l in selected),max(l['box'][2]for l in selected),max(l['box'][3]for l in selected))
        minimum=box[0];step=statistics.median(l['size']for l in selected)*.58
        code='\n'.join(' '*max(0,round((l['box'][0]-minimum)/step))+l['text']for l in selected)
        blocks.append(dict(box=box,html='<pre><code>'+escape(code)+'</code></pre>',size=statistics.median(l['size']for l in selected)))
    text=[l for l in ocr if not any(b['box'][0]-6<=(l['box'][0]+l['box'][2])/2<=b['box'][2]+6 and b['box'][1]-5<=(l['box'][1]+l['box'][3])/2<=b['box'][3]+5 for b in blocks)]
    objects=[dict(x0=l['box'][0],top=l['box'][1],x1=l['box'][2],bottom=l['box'][3],size=l['size'],line=l)for l in text]
    objects +=[dict(x0=b['box'][0],top=b['box'][1],x1=b['box'][2],bottom=b['box'][3],size=b['size'],html=b['html'])for b in blocks]
    output=[]
    for region in reading_regions(objects)if objects else []:
        lines=[]
        for obj in sorted(region,key=lambda c:(round(c['top']/4),c['x0'])):
            if 'html'in obj:
                if lines:output.append(render_lines(lines,statistics.median(l['size']for l in lines)));lines=[]
                output.append(obj['html'])
            else:lines.append(obj['line'])
        if lines:output.append(render_lines(lines,statistics.median(l['size']for l in lines)))
    return ''.join(output)

def finish():
    sources=json.loads((WORK/'expanded-sources.json').read_text())
    results={r['id']:r for line in (WORK/'ocr-results.jsonl').read_text().splitlines()if line.strip()for r in [json.loads(line)]}
    audit=[]
    for s in sources:
        for page in s['pages']:
            if s['format']!='PDF':
                if not page.get('body'):raise RuntimeError('Missing native document body')
                page['reading_method']='native'
                continue
            key=f'{s["id"]}-{page["n"]:03d}';result=results.get(key)
            if not result or result.get('error'):raise RuntimeError('OCR incomplete: '+key)
            width,height=page['page_size'];ocr=ocr_lines(result,width,height)
            # The umask submission has a raster Korean slide plus an incomplete English layer.
            if s['id']=='s036':
                page['native_body']=page['body']
                page['body']='<div class="ocr-body">'+raster_slide_body(page,ocr)+'</div>'
                page['reading_method']='ocr'
                page['raster_full']=True
            else:
                page['reading_method']='native+figures'
                for figure in page.get('figures',[]):
                    b=figure['box']
                    extracted=[l for l in ocr if b[0]<=(l['box'][0]+l['box'][2])/2<=b[2]and b[1]<=(l['box'][1]+l['box'][3])/2<=b[3]]
                    # Keep image text searchable. Original image is displayed alongside it.
                    if extracted:
                        figure['text']='\n'.join(l['text']for l in order_ocr(extracted))
                # Full-page raster material may coexist with a sparse or broken text layer.
                if page.get('raster_full'):
                    ordered=order_ocr(ocr)
                    size=statistics.median(l['size']for l in ordered)if ordered else 15
                    page['image_text']='<div class="ocr-body">'+render_lines(ordered,size)+'</div>'
            # PDF link annotations are content too (including links drawn on screenshots).
            page['ocr_chars']=sum(len(l['text'])for l in ocr)
            page['conversion_note']=('PDF의 글꼴 문자표에서 일부 코드 기호가 다르게 추출됩니다. 코드 기호는 아래 페이지 배치에서 확인하세요.'if s['id']in['s034','s035']else'')
            audit.append(dict(source=s['id'],page=page['n'],native_chars=page['native_chars'],
                              recognized_chars=page['ocr_chars'],figures=len(page.get('figures',[])),
                              reading_method=page['reading_method']))
            page.pop('layout_lines',None);page.pop('page_size',None)
    (ROOT/'content/sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
    used={f['image'].removeprefix('../')for s in sources for p in s['pages']for f in p.get('figures',[])}
    for file in (DOCS/'assets/figures').glob('s???-???-??.webp'):
        if str(file.relative_to(DOCS))not in used:file.unlink()
    (WORK/'coverage-report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    print('Expanded all 36 source documents;',len(audit),'PDF pages,',sum(r['figures']for r in audit),'figures.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','finish']);p.add_argument('--source',type=Path)
    args=p.parse_args()
    if args.mode=='prepare':
        if not args.source:p.error('--source is required for prepare')
        prepare(args.source)
    else:finish()
