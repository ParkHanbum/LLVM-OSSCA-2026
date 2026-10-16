/* All controls work without a server API. Text never becomes executable markup. */
(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const menu=$('[data-menu]');
const closeMenu=()=>{document.body.classList.remove('nav-open');menu?.setAttribute('aria-expanded','false');};
menu?.addEventListener('click',()=>{const on=document.body.classList.toggle('nav-open');menu.setAttribute('aria-expanded',String(on));});
$('[data-close-menu]')?.addEventListener('click',closeMenu);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMenu();if(document.activeElement?.closest('.site-sidebar'))menu?.focus();}});

const input=$('[data-search]'),dataEl=$('#search-data');
if(input&&dataEl){
 const data=JSON.parse(dataEl.textContent);const rows=$$('[data-doc-row]');
 const filters=$$('[data-filter]');const count=$('[data-result-count]');const empty=$('[data-empty]');
 const key=t=>t.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g,' ');
 const index=new Map(data.map(d=>[d.id,{...d,search:key(d.text)}]));
 const initial=new URLSearchParams(location.search);input.value=initial.get('q')||'';
 filters.forEach(f=>{const value=initial.get(f.dataset.filter)||'';if([...f.options].some(o=>o.value===value))f.value=value;});
 function update(push=true){
  const words=key(input.value.trim()).split(' ').filter(Boolean);let visible=0;
  rows.forEach(row=>{const d=index.get(row.dataset.docRow);const matches=d&&words.every(w=>d.search.includes(w))&&filters.every(f=>!f.value||(Array.isArray(d[f.dataset.filter])?d[f.dataset.filter].includes(f.value):d[f.dataset.filter]===f.value));row.hidden=!matches;if(matches)visible++;});
  count.textContent=`${visible} / ${rows.length}`;empty.hidden=visible!==0;
  const clear=$('[data-clear-search]');if(clear)clear.hidden=!input.value;
  if(push){const params=new URLSearchParams();if(input.value.trim())params.set('q',input.value.trim());filters.forEach(f=>{if(f.value)params.set(f.dataset.filter,f.value);});try{history.replaceState(null,'',location.pathname+(params.size?'?'+params.toString():'')+location.hash);}catch{}}
 }
 const reset=()=>{input.value='';filters.forEach(f=>f.value='');update();input.focus();};
 input.addEventListener('input',()=>update());filters.forEach(f=>f.addEventListener('change',()=>update()));
 $$('[data-reset]').forEach(b=>b.addEventListener('click',reset));
 $('[data-clear-search]')?.addEventListener('click',()=>{input.value='';update();input.focus();});
 update(false);
}
const font=$('[data-font]');
font?.addEventListener('click',()=>{const on=document.body.classList.toggle('large-text');font.setAttribute('aria-pressed',String(on));font.textContent=on?'기본 크기':'글자 크게';});
$('[data-print]')?.addEventListener('click',()=>window.print());
$$('.source-body table').forEach(table=>{
 if(table.closest('.table-wrap'))return;
 const wrap=document.createElement('div');wrap.className='table-wrap';table.before(wrap);wrap.append(table);
});
$$('.source-body pre').forEach(pre=>{
 if(pre.closest('.code-wrap'))return;
 let code=$('code',pre);if(!code){code=document.createElement('code');code.textContent=pre.textContent;pre.replaceChildren(code);}
 const wrap=document.createElement('div');wrap.className='code-wrap';pre.before(wrap);const label=document.createElement('div');label.className='code-label';label.textContent='원자료 코드';wrap.append(label,pre);
});
$$('.code-wrap').forEach(wrap=>{
 const code=$('pre code',wrap);if(!code)return;const b=document.createElement('button');b.className='copy-code';b.type='button';b.textContent='복사';b.setAttribute('aria-label','코드 복사');wrap.appendChild(b);
 b.addEventListener('click',async()=>{try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(code.textContent);}else{const area=document.createElement('textarea');area.value=code.textContent;area.style.cssText='position:fixed;left:-9999px';document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();if(!ok)throw Error('copy');}b.textContent='복사됨';setTimeout(()=>b.textContent='복사',1600);}catch{b.textContent='복사할 텍스트 선택';const r=document.createRange();r.selectNodeContents(code);const s=window.getSelection();s.removeAllRanges();s.addRange(r);}});
});
$$('[data-reading]').forEach(button=>button.addEventListener('click',()=>{
 const layout=button.dataset.reading==='layout';document.body.classList.toggle('reading-layout',layout);
 $$('[data-reading]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 $$('.page-layout').forEach(detail=>{detail.open=layout||detail.dataset.originalOpen==='true';});
}));
const benchmarkButtons=$$('[data-benchmark]'),benchmarkPanels=$$('[data-benchmark-panel]');
if(benchmarkButtons.length){
 const selectBenchmark=id=>{benchmarkButtons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.benchmark===id)));benchmarkPanels.forEach(p=>p.hidden=p.id!==id);};
 selectBenchmark(benchmarkButtons[0].dataset.benchmark);
 benchmarkButtons.forEach(b=>b.addEventListener('click',()=>selectBenchmark(b.dataset.benchmark)));
 window.addEventListener('beforeprint',()=>benchmarkPanels.forEach(p=>p.hidden=false));
 window.addEventListener('afterprint',()=>selectBenchmark(benchmarkButtons.find(b=>b.getAttribute('aria-pressed')==='true').dataset.benchmark));
}
const tocLinks=$$('.article-toc a'),sections=$$('.article > section[id]');
const archiveData=$('#archive-search-data');
if(archiveData){
 const records=JSON.parse(archiveData.textContent),cards=$$('[data-archive-case]'),indexRows=new Map($$('[data-archive-index]').map(r=>[r.dataset.archiveIndex,r]));
 const normalize=s=>s.normalize('NFKC').toLocaleLowerCase();
 const index=new Map(records.map(r=>[r.id,{...r,search:normalize(r.text)}]));
 const search=$('[data-archive-search]'),project=$('[data-archive-project]'),status=$('[data-archive-status]');
 const update=()=>{let count=0;const words=normalize(search.value.trim()).split(/\s+/).filter(Boolean);cards.forEach(card=>{const r=index.get(card.dataset.archiveCase);const show=words.every(w=>r.search.includes(w))&&(!project.value||project.value===r.project)&&(!status.value||status.value===r.status);card.hidden=!show;indexRows.get(r.id).hidden=!show;if(show)count++;});$('[data-archive-count]').textContent=`${count} / ${cards.length}`;$('[data-archive-empty]').hidden=count!==0;};
 search.addEventListener('input',update);project.addEventListener('change',update);status.addEventListener('change',update);
 $('[data-archive-reset]').addEventListener('click',()=>{search.value='';project.value='';status.value='';update();search.focus();});
 // An index link can point into a currently filtered card. Reveal that card
 // before the browser scrolls to it; do not leave a valid anchor invisible.
 $$('a[href^="#case-"]').forEach(a=>a.addEventListener('click',()=>{const target=document.getElementById(a.hash.slice(1));if(target?.hidden){search.value='';project.value='';status.value='';update();}}));
 const printState=[];
 window.addEventListener('beforeprint',()=>{cards.forEach(c=>{printState.push(c.hidden);c.hidden=false;indexRows.get(c.dataset.archiveCase).hidden=false;});});
 window.addEventListener('afterprint',()=>{cards.forEach((c,i)=>{c.hidden=printState[i]??false;indexRows.get(c.dataset.archiveCase).hidden=c.hidden;});printState.length=0;});
}
const backendSearch=$('[data-backend-search]');
if(backendSearch){const rows=$$('[data-backend-project]');backendSearch.addEventListener('input',()=>{const query=backendSearch.value.trim().toLocaleLowerCase();let count=0;rows.forEach(row=>{row.hidden=!row.dataset.backendProject.includes(query);if(!row.hidden)count++;});$('[data-backend-count]').textContent=`${count} / ${rows.length}`;});}
if(tocLinks.length&&'IntersectionObserver'in window){const observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];if(!visible)return;tocLinks.forEach(a=>{const active=a.hash==='#'+visible.target.id;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});},{rootMargin:'-95px 0px -55% 0px',threshold:0});sections.forEach(s=>observer.observe(s));}
})();
