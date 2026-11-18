const bootBetterPrompt=()=>{
 const root=document.querySelector('.gradio-container');if(!root||!document.querySelector('#bp-world'))return false;if(root.dataset.bpReady)return true;
 const q=s=>root.querySelector(s),qa=s=>Array.from(root.querySelectorAll(s)),reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const chapters=[
  {no:'CHAPTER ONE',title:'The little café.',subtitle:'好想法，值得慢慢聊。',left:'从一个想法开始',leftSub:'不必想得很完整。把脑海中的画面写下来。',right:'把细节，慢慢补齐',rightSub:'原文自动保留；另外提供 15 项 AI 建议。',kicker:'01 / THE IDEA',rightKicker:'MAKE IT YOURS',quote:'“A good idea starts with a conversation.”',foot:'CAFÉ / IDEAS BREWING',speaker:'咖啡师 · MIA',speech:'先写下你的想法。我会陪你，把细节慢慢补齐。'},
  {no:'CHAPTER TWO',title:'A new direction.',subtitle:'带上喜欢的，调整不满意的。',left:'看看第一张画面',leftSub:'对照你的想法，找出想要调整的地方。',right:'给画面，一个新方向',rightSub:'选问题 → 写意见 → 分析并确认，再处理下一项。',kicker:'02 / THE IMAGE',rightKicker:'REFINE THE DETAILS',quote:'“Small changes. A clearer destination.”',foot:'AIRPORT / NEXT DESTINATION',speaker:'值机员 · MIA',speech:'先选问题，写清楚想法。AI 区分纠正或改目标，确认后再一起修改。'},
  {no:'CHAPTER THREE',title:'Keep what you love.',subtitle:'挑出最喜欢的，留下自己的版本。',left:'每一版，都值得对照',leftSub:'查看当前保留版与新候选，再决定留下哪一张。',right:'挑选你的理想版本',rightSub:'可以继续优化，也可以采用、回退与导出。',kicker:'03 / THE COLLECTION',rightKicker:'YOUR FINAL EDIT',quote:'“Keep the light. Keep the feeling.”',foot:'THE BOUTIQUE / YOUR COLLECTION',speaker:'店员 · MIA',speech:'喜欢哪一版，由你决定。后续修改，我们会继续留在这一页。'}
 ];
 let current=0,opened=false,busy=false,sound=false,audio=null,activeCard=null,previewIndex=-1,worldAPI=null;
 const sceneState=chapters.map(c=>({speaker:c.speaker,speech:c.speech}));
 const text=(selector,value)=>{const el=q(selector);if(el&&el.textContent!==String(value))el.textContent=value};
 function say(speaker,speech){sceneState[current]={speaker,speech};text('#bp-speaker',speaker);text('#bp-speech',speech);worldAPI?.react()}
 function pageSound(){if(!sound)return;try{audio ||= new (window.AudioContext||window.webkitAudioContext)();audio.resume();const osc=audio.createOscillator(),gain=audio.createGain();osc.type='sine';osc.frequency.setValueAtTime(300,audio.currentTime);osc.frequency.exponentialRampToValueAtTime(150,audio.currentTime+.16);gain.gain.setValueAtTime(.025,audio.currentTime);gain.gain.exponentialRampToValueAtTime(.0001,audio.currentTime+.24);osc.connect(gain);gain.connect(audio.destination);osc.start();osc.stop(audio.currentTime+.25)}catch(e){}}
 function open(){if(opened||busy)return;busy=true;opened=true;pageSound();q('#bp-open').disabled=true;worldAPI?.setActive(true);setTimeout(()=>{q('#bp-cover-screen').classList.add('bp-hidden');busy=false;q('#bp-open').disabled=false;root.classList.add('bp-opened')},reduced.matches?0:1400)}
 function close(){if(busy||!opened)return;busy=true;opened=false;pageSound();worldAPI?.setActive(false);q('#bp-cover-screen').classList.remove('bp-hidden');root.classList.remove('bp-opened');setTimeout(()=>{busy=false;q('#bp-open').focus({preventScroll:true})},reduced.matches?0:1400)}
 function unfold(selector){const box=q(selector);if(!box)return;const content=box.querySelector('.label-wrap');const textarea=box.querySelector('textarea'),img=box.querySelector('img');if((textarea&&textarea.offsetParent===null)||(img&&img.offsetParent===null)||box.querySelector(':scope > .hide'))(content||box.querySelector('button'))?.click()}
 function paintPage(i){current=i;const c=chapters[i];root.classList.remove('bp-page-0','bp-page-1','bp-page-2');root.classList.add('bp-page-'+i);for(const [sel,value] of Object.entries({'#bp-scene-no':c.no,'#bp-scene-title':c.title,'#bp-scene-subtitle':c.subtitle,'#bp-left-title':c.left,'#bp-left-subtitle':c.leftSub,'#bp-right-title':c.right,'#bp-right-subtitle':c.rightSub,'#bp-left-kicker':c.kicker,'#bp-right-kicker':c.rightKicker,'#bp-scene-quote':c.quote,'#bp-scene-foot':c.foot,'#bp-left-folio':String(i*2+1).padStart(2,'0'),'#bp-right-folio':String(i*2+2).padStart(2,'0'),'#bp-speaker':sceneState[i].speaker,'#bp-speech':sceneState[i].speech}))text(sel,value);q('#bp-page-number').innerHTML=String(i+1).padStart(2,'0')+' <i>/ 03</i>';q('#bp-prev').disabled=i===0;q('#bp-next').disabled=i===2;qa('#bp-directory [data-page]').forEach(b=>b.setAttribute('aria-current',Number(b.dataset.page)===i?'page':'false'));q('#bp-left').scrollTop=0;q('#bp-right').scrollTop=0;q('#bp-world').setAttribute('aria-label',['可拖动旋转的咖啡馆立体场景','可拖动旋转的机场立体场景','可拖动旋转的服装店立体场景'][i]);if(i===2)unfold('#bp-comparison-images')}
 function go(i){i=Math.max(0,Math.min(2,i));if(busy||i===current)return;pageSound();q('#bp-directory').hidden=true;q('#bp-menu-toggle').setAttribute('aria-expanded','false');if(reduced.matches){paintPage(i);worldAPI?.change(i);return}busy=true;root.classList.add('bp-flipping');worldAPI?.change(i);setTimeout(()=>paintPage(i),380);setTimeout(()=>{root.classList.remove('bp-flipping');busy=false},1050)}
 window.betterPrompt={go,openPlan:()=>{unfold('#pb-first-plan');q('#pb-first-plan')?.scrollIntoView({behavior:reduced.matches?'instant':'smooth',block:'nearest'})}};
 q('#bp-open').onclick=open;q('#bp-close').onclick=close;q('.bp-brand').onclick=e=>{e.preventDefault();if(opened)close();else open()};
 q('#bp-prev').onclick=()=>go(current-1);q('#bp-next').onclick=()=>go(current+1);
 q('#bp-menu-toggle').onclick=()=>{const menu=q('#bp-directory');menu.hidden=!menu.hidden;q('#bp-menu-toggle').setAttribute('aria-expanded',String(!menu.hidden))};qa('#bp-directory [data-page]').forEach(b=>b.onclick=()=>go(Number(b.dataset.page)));
 q('#bp-sound').onclick=()=>{sound=!sound;q('#bp-sound').setAttribute('aria-pressed',String(sound));q('#bp-sound span').textContent=sound?'音效开':'音效关';pageSound()};q('#bp-view').onclick=()=>{worldAPI?.view();pageSound()};
 q('#bp-settings-toggle').onclick=()=>q('#bp-task-settings').classList.toggle('bp-show');
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){q('#bp-directory').hidden=true;q('#bp-menu-toggle').setAttribute('aria-expanded','false')}if(e.target.closest('input,textarea,[contenteditable=true]'))return;if(e.altKey&&e.key==='ArrowRight'){e.preventDefault();go(current+1)}if(e.altKey&&e.key==='ArrowLeft'){e.preventDefault();go(current-1)}});
 // Page-edge dragging is separate from scene orbiting and form interactions.
 let edgeDrag=null;
 const edgeHint=q('#bp-edge-hint');
 function endEdgeDrag(event,cancel=false){
  if(!edgeDrag||event.pointerId!==edgeDrag.id)return;
  const g=edgeDrag;edgeDrag=null;edgeHint.hidden=true;root.classList.remove('bp-edge-dragging');
  if(g.pane.hasPointerCapture(g.id))g.pane.releasePointerCapture(g.id);
  if(!cancel&&g.ready&&!busy&&opened)go(current+g.direction);
 }
 for(const pane of [q('#bp-left'),q('#bp-right')]){
  pane.addEventListener('pointerdown',e=>{
   if(e.button!==0||!e.isPrimary||busy||!opened||!q('#bp-loading').hidden)return;
   if(e.target.closest('input,textarea,button,label,select,a,summary,table,img,canvas,[role="button"],[contenteditable="true"],.pb-index-card,.label-wrap'))return;
   const top=pane.scrollTop<=4,bottom=pane.scrollHeight-pane.clientHeight-pane.scrollTop<=4;
   if(!top&&!bottom)return;
   edgeDrag={id:e.pointerId,pane,x:e.clientX,y:e.clientY,top,bottom,direction:0,ready:false};pane.setPointerCapture(e.pointerId);e.preventDefault();
  });
  pane.addEventListener('pointermove',e=>{
   const g=edgeDrag;if(!g||g.id!==e.pointerId)return;
   const dx=e.clientX-g.x,dy=e.clientY-g.y;g.ready=false;
   if(Math.abs(dy)<12||Math.abs(dx)>Math.abs(dy)*.7){edgeHint.hidden=true;return}
   const direction=dy<0?-1:1,edge=direction<0?g.top:g.bottom;
   if(!edge){edgeHint.hidden=true;return}
   e.preventDefault();root.classList.add('bp-edge-dragging');edgeHint.hidden=false;
   if(current+direction<0||current+direction>2){text('#bp-edge-hint',direction<0?'已经是第一页':'已经是最后一页');return}
   g.direction=direction;g.ready=Math.abs(dy)>=85;
   text('#bp-edge-hint',g.ready?'松开鼠标，前往'+(direction<0?'上一页 ↑':'下一页 ↓'):'继续'+(direction<0?'向上':'向下')+'拖动以翻页');
  });
  pane.addEventListener('pointerup',e=>endEdgeDrag(e));pane.addEventListener('pointercancel',e=>endEdgeDrag(e,true));pane.addEventListener('lostpointercapture',e=>endEdgeDrag(e,true));
 }
 function describeCard(c){const heading=c.querySelector('h3')?.textContent?.replace(/^\d+\.\s*/,'')||'这个细节',checked=c.querySelector('input:checked');let value=checked?.closest('label')?.textContent?.trim()||'';if(checked?.value==='D')value=c.querySelector('textarea')?.value?.trim()||'写下你自己的想法';value=value.replace(/^[ABC]\s*·\s*/,'');return (value||heading).slice(0,62)}
 function expand(c){if(activeCard&&activeCard!==c)activeCard.classList.remove('bp-expanded');activeCard=c;if(c){c.classList.add('bp-expanded');if(current===0)say(chapters[0].speaker,'「'+describeCard(c)+'」好像可以考虑呢……')}}
 const tray=q('#pb-card-tray');tray.addEventListener('pointerover',e=>{const c=e.target.closest('.pb-index-card');if(c&&c!==activeCard)expand(c)});tray.addEventListener('pointerleave',()=>{if(!tray.contains(document.activeElement))expand(null)});tray.addEventListener('click',e=>{const c=e.target.closest('.pb-index-card');if(c)expand(c)});tray.addEventListener('focusin',e=>{const c=e.target.closest('.pb-index-card');if(c)expand(c)});tray.addEventListener('focusout',()=>requestAnimationFrame(()=>{if(!tray.contains(document.activeElement)&&!tray.matches(':hover'))expand(null)}));tray.addEventListener('change',()=>{if(activeCard)expand(activeCard);refreshDOM();pageSound()});
 const chips=q('#pb-fix-chips');chips.addEventListener('change',e=>{const label=e.target.closest('label'),dest=q('#pb-note textarea');if(!label||!dest)return;const title=label.textContent.trim();say(chapters[current].speaker,'先说说「'+title.slice(0,32)+'」想怎么改，保存后再选择下一项。');pageSound();if(!reduced.matches){const a=label.getBoundingClientRect(),b=dest.getBoundingClientRect(),ghost=document.createElement('span');ghost.className='bp-chip-ghost';ghost.textContent=title.slice(0,22);ghost.style.left=a.left+'px';ghost.style.top=a.top+'px';document.body.append(ghost);ghost.animate([{transform:'translate(0,0) scale(1)',opacity:1},{transform:`translate(${b.left-a.left+10}px,${b.top-a.top+10}px) scale(.4)`,opacity:0}],{duration:350,easing:'cubic-bezier(.22,1,.36,1)'}).finished.then(()=>ghost.remove())}requestAnimationFrame(()=>dest.focus({preventScroll:true}))});
 const note=q('#pb-note textarea');if(note){const count=document.createElement('small');count.id='pb-note-count';q('#pb-note').append(count);const countText=()=>text('#pb-note-count',note.value.length+' 字 · 保存后加入修改计划');note.addEventListener('input',countText);countText()}
 function history(){return qa('#pb-history img').filter(i=>i.src&&i.alt).map(i=>({src:i.src,label:i.alt}))}
 const countTimer=setInterval(()=>{if(note)text('#pb-note-count',note.value.length+' 字 · 保存后加入修改计划')},300);
 let lastHistory='';function preview(n){const list=history(),im=q('#pb-main-image img');if(!list[n]||!im)return;previewIndex=n;im.src=list[n].src;q('#pb-main-image').classList.toggle('bp-preview',!list[n].label.includes('已选择'));text('#pb-image-caption',list[n].label+' · 仅预览，采用请到第三页确认');text('#bp-image-folio',list[n].label.split(' · ')[0]+' / '+list.length+' VERSIONS');qa('#bp-version-ribbons button').forEach(b=>b.classList.toggle('bp-selected',Number(b.dataset.index)===n));if(!reduced.matches)im.animate([{opacity:.25,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}],{duration:300,easing:'cubic-bezier(.22,1,.36,1)'})}
 q('#pb-main-image').addEventListener('click',e=>{if(e.target.tagName!=='IMG')return;const h=history(),n=h.findIndex(v=>v.label.includes('已选择'));if(n>0)preview(previewIndex===n-1?n:n-1)});
 let analysisStarted=0,lastAnalysisMarkup='',requestStarted=0,requestFocus=null;
 function beginRequest(title,description='正在使用你已配置的真实接口。'){requestStarted=Date.now();requestFocus=document.activeElement;text('#bp-loading-title',title);text('#bp-loading-description',description);text('#bp-loading-time','正在提交请求…');q('#bp-loading').hidden=false;q('#bp-book').inert=true;q('#bp-controls').inert=true;q('.bp-loading-panel').focus({preventScroll:true})}
 function endRequest(){requestStarted=0;q('#bp-loading').hidden=true;q('#bp-book').inert=false;q('#bp-controls').inert=false;if(requestFocus?.isConnected)requestFocus.focus({preventScroll:true});requestFocus=null}
 window.betterPrompt.endRequest=endRequest;
 for(const [selector,title] of Object.entries({'#pb-generate':'正在生成并检查第一张图片','#bp-retry-image':'正在重新生成并检查图片','#pb-execute':'正在按修改方案优化图片','#bp-save-note':'AI 正在理解修改意见','#bp-supplement-analyze':'AI 正在理解补充内容','#bp-feedback-confirm':'正在保存并按当前目标检查图片','#bp-feedback-recheck':'AI 正在按当前目标重新检查图片','#bp-reevaluate':'AI 正在检查当前图片','#bp-observe':'AI 正在比较两个版本','#bp-reference-image':'正在根据参考图片生成修改版'})){q(selector)?.addEventListener('click',()=>beginRequest(title))}
 function beginAnalysis(){beginRequest('AI 正在分析你的想法','保留原文要求，另外生成 15 项可选建议。');analysisStarted=Date.now();lastAnalysisMarkup=q('#bp-analysis-status')?.innerHTML||'';root.classList.add('bp-analyzing');q('#bp-loading').hidden=false;q('#bp-right').scrollTop=0;text('#bp-loading-time','正在提交请求…')}
 function updateAnalysis(){
  const holder=q('#bp-analysis-status'),markup=holder?.innerHTML||'',state=holder?.querySelector('[data-analysis-state]')?.dataset.analysisState;
  if(markup!==lastAnalysisMarkup){lastAnalysisMarkup=markup;if(state==='loading'&&!analysisStarted)beginAnalysis();else if(state!=='loading'){analysisStarted=0;root.classList.remove('bp-analyzing');endRequest()}}
  if(requestStarted){const seconds=Math.floor((Date.now()-requestStarted)/1000);text('#bp-loading-time',seconds<30?'已等待 '+seconds+' 秒 · 收到结果后自动显示':'已等待 '+seconds+' 秒 · 模型仍在处理，请勿重复提交')}
 }
 q('#bp-analyze').addEventListener('click',beginAnalysis);q('#bp-retry-analysis').addEventListener('click',beginAnalysis);
 const analysisTimer=setInterval(updateAnalysis,500);
 function refreshDOM(){updateAnalysis();const cards=qa('.pb-index-card').filter(c=>!c.classList.contains('hide')&&c.querySelector('h3'));cards.forEach(c=>{c.tabIndex=0;const label=c.querySelector('h3')?.textContent||'需求卡片';if(c.getAttribute('aria-label')!==label)c.setAttribute('aria-label',label)});const suggested=cards.filter(c=>c.classList.contains('pb-ai-card'));text('#bp-card-progress',suggested.length?suggested.filter(c=>c.querySelector('input:checked')).length+' 已选 / '+suggested.length+' 项新增建议':'等待 AI 分析');
  const totals={pass:0,fail:0,uncertain:0};qa('#pb-checks table.table tbody tr').forEach(row=>{const cells=row.querySelectorAll('td'),s=cells[2]?.textContent.trim();if(s in totals)totals[s]++});Object.entries(totals).forEach(([k,v])=>text('#bp-'+k,v));
  const h=history(),key=JSON.stringify(h);if(key!==lastHistory){lastHistory=key;previewIndex=-1;q('#pb-main-image').classList.remove('bp-preview');const holder=q('#bp-version-ribbons');holder.replaceChildren();h.forEach((item,n)=>{const b=document.createElement('button'),im=document.createElement('img');b.type='button';b.dataset.index=String(n);im.src=item.src;im.alt='';b.append(im,document.createTextNode(item.label.split(' · ')[0]));b.title=item.label+' · 仅预览';b.classList.toggle('bp-selected',item.label.includes('已选择'));b.onclick=()=>preview(n);holder.append(b)});const selected=h.find(i=>i.label.includes('已选择'));text('#bp-image-folio',(selected?.label.split(' · ')[0]||'—')+' / '+h.length+' VERSIONS')}
  const prompt=q('#pb-prompt textarea');if(previewIndex<0&&prompt?.value)text('#pb-image-caption',prompt.value.replace(/\[[a-f0-9]+\]/g,'').replace(/\n/g,' · ').slice(0,90)+'…');
 }
 let queued=false;const observer=new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;refreshDOM()})});observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['src','alt']});
 paintPage(0);root.dataset.bpReady='1';refreshDOM();
 try{worldAPI=createBetterWorld({world:q('#bp-world'),coverHost:q('#bp-cover-render'),reduced,onCover:open,onPerson:(actor,n)=>say(actor.name,actor.lines[(n-1)%actor.lines.length])});q('#bp-webgl-status').hidden=true}catch(error){text('#bp-webgl-status','此浏览器未能启用 3D。书页操作仍可使用。');console.error('Better Prompt WebGL initialization failed',error)}
 document.addEventListener('visibilitychange',()=>{});window.addEventListener('pagehide',()=>{worldAPI?.dispose();observer.disconnect();clearInterval(countTimer);clearInterval(analysisTimer)},{once:true});return true;
};
if(!bootBetterPrompt()){let attempts=0;const init=setInterval(()=>{if(bootBetterPrompt()||++attempts>100)clearInterval(init)},100)}
