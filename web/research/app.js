'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const count = (rows, key) => rows.reduce((a, r) => { for (const v of [...new Set(Array.isArray(r[key]) ? r[key] : [r[key]])]) a[v] = (a[v] || 0) + 1; return a; }, {});
const sum = values => values.reduce((a,b)=>a+b,0);
const badge = (text, cls='neutral') => `<span class="pill ${cls}">${esc(text)}</span>`;
const tags = values => `<div class="tags">${values.map(v=>`<span class="tag">${esc(v)}</span>`).join('')}</div>`;
const link = (url, label) => /^https?:\/\//.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : `<span class="meta">${esc(label)}：未提供</span>`;
let data, currentView='overview', filtered={comments:[],claims:[]}, runs=[];
const names = {overview:'輿情總覽',claims:'主張與案例',evidence:'文獻證據庫',lineage:'資料與執行紀錄',settings:'設定與方法'};
const titles = {overview:['把疑慮看清楚，讓依據可追溯。','從網路討論到研究證據，理解每一個關於油的問題。'],claims:['每一段說法，都能回到原文。','保留上下文、態度線索與不確定性，再進行證據判讀。'],evidence:['先讀懂研究，再解讀說法。','候選文獻提供研究脈絡；主題相關不等於支持主張。'],lineage:['看得見的資料處理過程。','追溯來源、排除原因、設定版本與每一次分析。'],settings:['讓研究方法保持透明。','公司可維護關鍵字；設定、程式與網站呈現各自獨立。']};
function toast(message){ $('toast').textContent=message; $('toast').style.display='block'; setTimeout(()=>$('toast').style.display='none',3500); }
async function getJSON(url){const r=await fetch(url);const value=await r.json();if(!r.ok)throw Error(value.error||'讀取失敗');return value;}
async function load(run){
 try {
  data=await getJSON('/api/snapshot'+(run?'?run='+encodeURIComponent(run):''));
  runs=await getJSON('/api/runs');
  const cfg=data.manifest.config_snapshot;
  $('case').innerHTML='<option value="all">全部案例</option>'+cfg.analysis.cases.map(c=>`<option value="${esc(c.id)}">${esc(c.title)}</option>`).join('')+'<option value="other">其他議題</option>';
  $('source').innerHTML='<option value="all">全部來源</option>'+[...new Set(data.comments.map(r=>r.source))].sort().map(s=>`<option>${esc(s)}</option>`).join('');
  $('kind').value=data.manifest.mock_count?'mock':'real';
  $('from').value='';$('to').value='';$('search').value='';
  $('updated').textContent='執行時間 '+new Date(data.manifest.created_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
  $('loading').hidden=true; $('application').hidden=false;
  render();
 } catch(e){$('loading').hidden=false;$('loading').textContent='無法讀取資料：'+e.message;}
}
function selectRows(){
 const mock=$('kind').value==='mock', source=$('source').value, caseId=$('case').value, q=$('search').value.trim().toLocaleLowerCase(), start=$('from').value, end=$('to').value;
 if(start && end && start>end) return {comments:[],claims:[],error:'開始日期不得晚於結束日期。'};
 const eligible=data.comments.filter(r=>r.is_mock===mock && (source==='all'||r.source===source) && (!start||r.day>=start) && (!end||r.day<=end));
 const index=new Map(eligible.map(r=>[r.uid,r]));
 const claims=data.claims.filter(c=>index.has(c.comment_uid) && (caseId==='all'||c.cases.includes(caseId)) && (!q||c.text.toLocaleLowerCase().includes(q)||index.get(c.comment_uid).text.toLocaleLowerCase().includes(q)));
 const ids=new Set(claims.map(c=>c.comment_uid));
 return {comments:eligible.filter(c=>ids.has(c.uid)),claims};
}
function bars(values, limit=6){
 const rows=Object.entries(values).sort((a,b)=>b[1]-a[1]).slice(0,limit), max=Math.max(1,...rows.map(r=>r[1]));
 return rows.length? rows.map(([label,n])=>`<div class="bar-row"><span>${esc(label)}</span><div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:${n/max*100}%"></div></div><b>${n}</b></div>`).join(''):'<div class="empty">目前沒有可呈現的資料</div>';
}
function trend(comments){
 if(!comments.length) return '<div class="empty">目前沒有日期資料</div>';
 const observed=count(comments,'day'), days=Object.keys(observed).sort();
 const lo=new Date(days[0]+'T00:00:00Z'), hi=new Date(days.at(-1)+'T00:00:00Z');
 // 小範圍補零，避免把未蒐集到的日期視為不存在；不等於該日市場聲量為零。
 let entries=[];
 if((hi-lo)/86400000<=120){for(let d=lo;d<=hi;d=new Date(+d+86400000)){const day=d.toISOString().slice(0,10);entries.push([day,observed[day]||0]);}}
 else entries=days.map(day=>[day,observed[day]]);
 const max=Math.max(1,...entries.map(x=>x[1])), width=520, height=150;
 const coords=entries.map(([d,n],i)=>[35+i*(width-55)/Math.max(entries.length-1,1),120-n/max*95,d,n]);
 const line=coords.map(([x,y])=>`${x},${y}`).join(' ');
 return `<svg class="trend" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(entries.map(([d,n])=>`${d} ${n}則`).join('；'))}"><defs><linearGradient id="fade" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#dce6cf" stop-opacity=".8"/><stop offset="100%" stop-color="#dce6cf" stop-opacity=".1"/></linearGradient></defs>${[0,max].map(n=>`<line x1="35" x2="505" y1="${120-n/max*95}" y2="${120-n/max*95}" stroke="#e8ede3"/><text x="12" y="${124-n/max*95}">${n}</text>`).join('')}<polygon points="35,120 ${line} ${coords.at(-1)[0]},120" fill="url(#fade)"/><polyline points="${line}" fill="none" stroke="#50715c" stroke-width="2.5"/>${coords.map(([x,y,d,n])=>`<circle cx="${x}" cy="${y}" r="3.5" fill="#50715c"><title>${d}：${n} 則</title></circle>`).join('')}<text x="35" y="146">${esc(entries[0][0].slice(5))}</text><text x="470" y="146">${esc(entries.at(-1)[0].slice(5))}</text></svg><details><summary>讀取每日數值</summary><div class="meta">${entries.map(([d,n])=>`${d}：${n} 則`).join('；')}</div></details>`;
}
function claimTable(claims, preview=false){
 if(!claims.length)return '<div class="empty"><strong>這個範圍尚無主張</strong>試著調整來源、日期或搜尋條件。</div>';
 const index=new Map(data.comments.map(c=>[c.uid,c]));
 return `<div class="table-wrap"><table><thead><tr><th>主張片段 / 點選追溯</th><th>疑慮分類</th><th>態度線索</th><th>證據判定</th><th>來源</th></tr></thead><tbody>${(preview?claims.slice(0,5):claims).map(c=>{const r=index.get(c.comment_uid);return `<tr><td class="claim-text"><button class="claim-button" data-detail="${esc(c.id)}">${esc(c.text)}</button><div class="subtext">${r.day} · ${esc(r.id)}${r.repeat_count>1?' · 重複文字群組':''}</div></td><td>${tags(c.categories)}</td><td>${esc(c.sentiment)}<div class="subtext">${esc(c.stance)}</div></td><td>${badge(c.decision,c.review_status==='已審核'?'approved':'pending')}<div class="subtext">${esc(c.review_status)}</div></td><td>${esc(r.source)}<div class="subtext">${r.is_mock?'模擬留言':'真實資料'}</div></td></tr>`;}).join('')}</tbody></table></div>`;
}
function overview(){
 const {comments,claims}=filtered, reviewed=claims.filter(c=>c.review_status==='已審核').length, pending=claims.length-reviewed;
 const categories=count(claims,'categories');
 const sentiment=count(claims,'sentiment');
 const cases=data.manifest.config_snapshot.analysis.cases;
 return `<div class="stats"><div class="stat accent"><div class="label">相關留言 <span>COMMENTS</span></div><div class="number">${comments.length}</div><div class="foot">依來源 ID 去重 · 非獨立人數</div></div><div class="stat"><div class="label">主張片段 <span>CLAIMS</span></div><div class="number">${claims.length}</div><div class="foot">一則留言可含多個片段</div></div><div class="stat"><div class="label">待人工審核 <span>REVIEW</span></div><div class="number">${pending}</div><div class="foot">保留提問、轉述與條件不足</div></div><div class="stat"><div class="label">已完成審核 <span>EVIDENCE</span></div><div class="number">${reviewed}</div><div class="foot">附審核人、理由及文獻關聯</div></div></div>
 <div class="grid-two"><section class="card"><div class="card-title"><div><h2>大家在擔心什麼？</h2><p>依主張片段分類，單一片段可複選</p></div>${badge('疑慮分布')}</div>${bars(categories)}<div class="chart-note">計數單位：片段。各分類加總可能大於片段總數。</div></section><section class="card"><div class="card-title"><div><h2>討論如何隨時間變化</h2><p>依留言發布日期統計，台北時區</p></div>${badge($('kind').value==='mock'?'模擬分布':'樣本趨勢')}</div>${trend(comments)}<div class="chart-note">每日相關留言數；樣本數與來源範圍會影響結果，不代表全網聲量。</div></section></div>
 <div class="case-section"><h2>第一階段 · 追蹤案例</h2><span>案例可以重疊，沒有油種健康排名</span></div><div class="cases">${cases.map((c,i)=>{const n=claims.filter(x=>x.cases.includes(c.id));const commentsN=new Set(n.map(x=>x.comment_uid)).size;return `<article class="case-card"><div class="case-number"><span>CASE 0${i+1}</span><span>證據對照</span></div><h3>${esc(c.title)}</h3><p>${esc(c.description)}</p><div class="case-bottom"><span>${commentsN} 則留言</span><span>${n.length} 個片段</span><button class="text-btn" data-case="${esc(c.id)}">查看案例 →</button></div></article>`;}).join('')}</div>
 <div class="grid-two"><section class="card"><div class="card-title"><div><h2>留言態度線索</h2><p>規則初篩，不等同品牌評價或科學結論</p></div></div>${bars(sentiment)}<div class="chart-note">否定與混合語句保留人工判讀；反諷可能造成誤判。</div></section><section class="card"><div class="card-title"><div><h2>族群與行動線索</h2><p>區分本人年齡自述與內容提及長輩</p></div></div>${bars(count(claims,'population'))}<div class="chart-note">${claims.filter(c=>c.mentions_older).length} 個片段提及長輩；${claims.filter(c=>!c.intentions.includes('未明示')&&!c.intentions.includes('語意需人工確認')).length} 個片段含自述消費意圖線索。皆不推論實際購買行為。</div></section></div>
 <section class="card table-card"><div class="card-title"><div><h2>主張追溯</h2><p>從原始留言走到候選文獻</p></div><button class="text-btn" data-go="claims">查看全部 →</button></div>${claimTable(claims,true)}</section>`;
}
function evidence(){
 const candidates=new Set(filtered.claims.flatMap(c=>c.candidate_reference_ids));
 return `<div class="section-note">本頁呈現完整文獻庫（${data.evidence.length} 筆）。標記目前篩選案例有配對的候選來源。書目已核對不等於完成專業評讀；方法說明不能代替油品效果研究。</div><div class="evidence-list">${data.evidence.map(r=>`<article class="card evidence"><div class="evidence-head"><div><div class="evidence-id">${esc(r.id)} · ${r.year}</div><h2>${esc(r.title)}</h2><div class="meta">${esc(r.authors)}</div></div><div>${badge(r.review_status,r.review_status==='已審核'?'approved':'pending')}${candidates.has(r.id)?' '+badge('篩選範圍有配對'):''}</div></div><dl class="facts"><dt>研究類型</dt><dd>${esc(r.study_type)}</dd><dt>研究條件</dt><dd>${esc(r.conditions)}</dd><dt>結果摘要</dt><dd>${esc(r.summary)}</dd><dt>適用限制</dt><dd>${esc(r.limitations)}</dd><dt>資助／衝突</dt><dd>${esc(r.funding)}</dd><dt>核對範圍</dt><dd>${esc(r.verified_scope)}</dd><dt>審核紀錄</dt><dd>${esc(r.reviewer||'尚未指派')} ${esc(r.reviewed_at||'')} ${esc(r.review_note||'')}</dd></dl><div class="evidence-links">${link(r.url,r.doi?'DOI '+r.doi:'原始來源')}${r.source_url!==r.url?link(r.source_url,'書目來源'):''}</div></article>`).join('')}</div>`;
}
function lineage(){
 const m=data.manifest, c=m.counts;
 const reasonNames={retained:'保留相關',duplicate:'重複匯入',excluded:'排除詞命中',irrelevant:'無關鍵詞命中',invalid:'格式或 ID 衝突',out_of_range:'日期範圍外'};
 return `<section class="card" style="margin-bottom:20px"><div class="card-title"><div><h2>執行快照</h2><p>切換紀錄後，各頁面使用該次的設定、文獻及分析結果</p></div></div><label for="run-select" class="meta">選擇執行紀錄</label> <select id="run-select">${runs.map(r=>`<option value="${esc(r.id)}" ${r.id===m.id?'selected':''}>${esc(r.id)} · ${esc(r.source)} · ${r.comment_count} 則</option>`).join('')}</select></section>
 <div class="flow">${[['原始匯入',m.raw_count,'筆紀錄'],['相關留言',m.comment_count,'依來源 ID 去重'],['主張片段',m.claim_count,'保留提問與轉述'],['候選文獻',data.evidence.length,'不是已確認的支持證據']].map(([label,n,note])=>`<div class="flow-item"><span>${label}</span><b>${n}</b><span>${note}</span></div>`).join('')}</div><div class="grid-two"><section class="card"><div class="card-title"><h2>處理結果與排除原因</h2></div>${bars(Object.fromEntries(Object.entries(c).map(([k,v])=>[reasonNames[k]||k,v])),10)}<div class="chart-note">保留與各排除項目合計為原始筆數。原始檔與逐筆原因保存在 data/raw、data/processed。</div></section><section class="card"><div class="card-title"><h2>資料範圍</h2></div><dl class="facts"><dt>來源模式</dt><dd>${esc(m.source)}</dd><dt>網路請求</dt><dd>${m.collection.network_used?'已使用 YouTube API':'無，離線處理'}</dd><dt>模擬／真實</dt><dd>${m.mock_count}／${m.real_count} 則相關留言</dd><dt>蒐集限制</dt><dd>${esc(m.collection.warnings.join('；')||'假設資料或人工匯入，不代表隨機抽樣。')}</dd><dt>引擎版本</dt><dd>${esc(m.engine_version)}</dd></dl></section></div><section class="card"><h2>可追溯版本</h2><dl class="facts"><dt>執行 ID</dt><dd>${esc(m.id)}</dd><dt>輸入 SHA-256</dt><dd>${esc(m.input_hash)}</dd><dt>設定 SHA-256</dt><dd>${esc(m.config_hash)}</dd><dt>文獻 SHA-256</dt><dd>${esc(m.evidence_hash)}</dd></dl><p>設定、文獻或留言變更後，舊審核不會自動套用到新版本。舊執行快照保留原有判斷。</p></section>`;
}
function settings(){
 const cfg=data.manifest.config_snapshot;
 return `<div class="section-note">這是目前執行使用的設定快照，網站保持唯讀。修改本機 config/*.yaml 後執行 python run.py，再重新整理頁面。第一階段只啟用規則分析，不使用雲端 LLM。</div><div class="config-grid">${[['油種關鍵詞','oil_types'],['油品相關詞','oil_terms'],['品牌關鍵詞','brands']].map(([title,key])=>`<section class="card"><div class="card-title"><div><h2>${title}</h2><p>config/keywords.yaml</p></div>${badge(Object.keys(cfg.keywords[key]).length+' 組')}</div>${Object.entries(cfg.keywords[key]).map(([name,aliases])=>`<p><strong>${esc(name)}</strong></p>${tags(aliases)}`).join('')}</section>`).join('')}<section class="card"><div class="card-title"><h2>方法與邊界</h2>${badge('RULES 1.0')}</div><dl class="facts"><dt>中高齡門檻</dt><dd>${cfg.analysis.older_age_threshold} 歲，僅採明確本人自述</dd><dt>情緒與態度</dt><dd>關鍵詞初篩；否定、反諷、轉述需人工確認</dd><dt>查核結果</dt><dd>所有初始片段為待查核；文獻配對不產生自動真偽判定</dd><dt>資料來源</dt><dd>mock、人工 CSV；YouTube 需另設 API 金鑰與影片 ID。PTT、Dcard、FB 無自動爬蟲。</dd><dt>醫學審查</dt><dd>文獻與主張分別審核；留下審核人、日期與理由</dd></dl></section></div><section class="card" style="margin-top:20px"><h2>本機維護指令</h2><pre>python run.py --source mock
python run.py --source csv
python serve.py</pre><details><summary>檢視此次完整設定快照</summary><pre>${esc(JSON.stringify(cfg,null,2))}</pre></details><p>審核指令與 CSV 格式請見隨附 README.md；不應在正式環境沿用假設資料作市場分析。</p></section>`;
}
function render(){
 if(!data)return;
 filtered=selectRows();
 $('breadcrumb').textContent='工作區 / '+names[currentView];
 $('page-title').textContent=titles[currentView][0];$('page-subtitle').textContent=titles[currentView][1];
 document.querySelectorAll('.nav').forEach(b=>{const active=b.dataset.view===currentView;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 const scoped=['overview','claims','evidence'].includes(currentView);
 $('filter-panel').hidden=!scoped;$('filter-summary').hidden=!scoped;$('export').hidden=!['overview','claims'].includes(currentView);
 $('filter-summary').textContent=filtered.error||`${$('kind').value==='mock'?'模擬資料':'真實資料'} · ${filtered.comments.length} 則相關留言 · ${filtered.claims.length} 個主張片段 · 分類可複選，案例可重疊`;
 $('claim-count').textContent=filtered.claims.length;
 const mock=$('kind').value==='mock';
 $('demo-banner').innerHTML=mock?'<strong>模擬案例工作區</strong><span>目前為假設留言，僅供流程驗證，不代表真實市場聲量。科學判斷須經人工審核。</span>':'<strong>真實樣本工作區</strong><span>僅呈現指定來源與範圍內的樣本，不代表全體消費者；未審核結果保留不確定性。</span>';
 $('demo-banner').hidden=!scoped;
 $('content').innerHTML=currentView==='overview'?overview():currentView==='claims'?`<div class="section-note">主張是斷句後的待判讀片段，包含疑問、轉述與消費表態。點選原文可檢查規則依據、候選文獻與審核狀態。</div><section class="card table-card">${claimTable(filtered.claims)}</section>`:currentView==='evidence'?evidence():currentView==='lineage'?lineage():settings();
}
function setView(view){if(!names[view])view='overview';currentView=view;location.hash=view;render();}
function detail(id){
 const c=data.claims.find(x=>x.id===id), r=data.comments.find(x=>x.uid===c.comment_uid);
 const candidates=data.evidence.filter(x=>c.candidate_reference_ids.includes(x.id));
 $('detail-content').innerHTML=`<div class="tags">${badge(r.is_mock?'模擬留言':'真實資料')}${badge(c.review_status,c.review_status==='已審核'?'approved':'pending')}</div><h2>${esc(c.text)}</h2><div class="meta">${esc(r.source)} · ${esc(r.id)} · ${esc(r.published_at)}</div><h3>原始留言與上下文</h3><blockquote>${esc(r.text)}</blockquote><div class="quote-label">${link(r.url,'原始留言')}${r.repeat_count>1?' · 此批次有 '+r.repeat_count+' 則相同文字，來源 ID 不同而保留。':''}</div><h3>分析線索</h3><dl class="facts"><dt>疑慮分類</dt><dd>${tags(c.categories)}</dd><dt>態度與對象</dt><dd>${esc(c.sentiment)} · ${esc(c.stance)}<br>${esc(c.sentiment_target)}（需人工確認）</dd><dt>自述消費意圖</dt><dd>${esc(c.intentions.join('／'))}</dd><dt>族群依據</dt><dd>${esc(c.population)}；${esc(c.age_basis)}。提及長輩：${c.mentions_older?'是':'否'}。</dd><dt>使用條件線索</dt><dd>${esc(c.conditions.join('／')||'未擷取到明確條件，請回看完整原文')}</dd><dt>分類限制</dt><dd>${esc(c.limitations)}</dd></dl><h3>科學證據判讀</h3><div class="review-card">${badge(c.decision,c.review_status==='已審核'?'approved':'pending')}<p>${esc(c.rationale)}</p>${c.reviewer?`<div class="meta">審核人：${esc(c.reviewer)} · ${esc(c.reviewed_at)}<br>正式引用：${esc(c.reference_ids.join('／')||'未附引用')}</div>`:'<div class="meta">目前沒有正式審核結論。以下僅為候選來源。</div>'}</div>${candidates.map(e=>`<div class="mini-evidence"><strong>${esc(e.id)} · ${esc(e.title)}</strong><div>${esc(e.conditions)}</div><div class="meta">限制：${esc(e.limitations)}</div>${link(e.url,'檢視來源')} · ${esc(e.review_status)}</div>`).join('')||'<p class="meta">尚無候選文獻。</p>'}<details><summary>檢視規則命中與追溯 ID</summary><pre>${esc(JSON.stringify({claim_id:c.id,fingerprint:c.fingerprint,keyword_hits:r.hits,rule_basis:c.rule_basis},null,2))}</pre></details><h3>人工審核</h3><p class="meta">由專業人員使用本機命令列審核；網站保持唯讀。判定支持、不支持或有條件成立時，必須引用已審核文獻。</p><pre>python review.py claim ${esc(c.id)} --decision "證據不足" --reviewer "審核人姓名" --rationale "請填入實際評讀理由"</pre>`;
 $('detail').showModal();
}
function exportCSV(){
 const index=new Map(filtered.comments.map(r=>[r.uid,r]));
 const rows=[['主張ID','原始ID','來源','資料類型','日期','主張片段','分類','態度','自述消費意圖','本人年齡標記','提及長輩','查核結果','審核狀態','引用文獻','理由'],...filtered.claims.map(c=>{const r=index.get(c.comment_uid);return [c.id,r.id,r.source,r.is_mock?'模擬':'真實',r.published_at,c.text,c.categories.join('／'),c.sentiment,c.intentions.join('／'),c.population,c.mentions_older?'是':'否',c.decision,c.review_status,c.reference_ids.join('／'),c.rationale];})];
 const safe=v=>{let s=String(v??'');if(/^[\s]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
 const blob=new Blob(['\ufeff'+rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`oil-claims-${$('kind').value}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast(`已匯出 ${filtered.claims.length} 個篩選片段`);
}
for(const id of ['kind','case','source','from','to'])$(id).addEventListener('change',render);
$('search').addEventListener('input',render);
$('reset').addEventListener('click',()=>{$('case').value='all';$('source').value='all';$('from').value='';$('to').value='';$('search').value='';render();});
$('refresh').addEventListener('click',()=>load());
$('export').addEventListener('click',exportCSV);
$('close-detail').addEventListener('click',()=>$('detail').close());
$('content').addEventListener('change',e=>{if(e.target.id==='run-select')load(e.target.value);});
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.view)setView(b.dataset.view);if(b.dataset.go)setView(b.dataset.go);if(b.dataset.detail)detail(b.dataset.detail);if(b.dataset.case){$('case').value=b.dataset.case;setView('claims');}});
window.addEventListener('hashchange',()=>{currentView=names[location.hash.slice(1)]?location.hash.slice(1):'overview';render();});
currentView=names[location.hash.slice(1)]?location.hash.slice(1):'overview';
load();
