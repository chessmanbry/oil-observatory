'use strict';

const element = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));

let catalogue;
let selectedCategory = '全部';
let requestNumber = 0;

function statusTag(topic) {
  const style = topic.status === '已審閱' ? 'approved' : 'pending';
  return `<span class="status-tag ${style}">${escapeHTML(topic.status)}</span>`;
}

function sourceList(sources) {
  if (!sources.length) return '<p class="secondary-note">正式出處將隨已審閱答案列出。</p>';
  return `<ol class="source-list">${sources.map(source => {
    const url = /^https:\/\//.test(source.url) ? source.url : '#';
    return `<li><a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.title)}</a><small>${escapeHTML(source.doi || source.organization || '')}</small></li>`;
  }).join('')}</ol>`;
}

function topicCard(topic) {
  const note = topic.rank ? `樣本排名 ${topic.rank} · 散播主張 ${topic.spread_count} 筆` : topic.common_claim;
  return `<article class="topic-card">
    <div class="topic-card-top"><span class="category-label">${escapeHTML(topic.category)}</span>${statusTag(topic)}</div>
    <h3>${escapeHTML(topic.question)}</h3>
    <p>${topic.rank ? '' : '待查證說法｜'}${escapeHTML(note)}</p>
    <a href="#topic/${encodeURIComponent(topic.id)}">查看說法與證據</a>
  </article>`;
}

function populateHome() {
  const meta = catalogue.meta;
  const stats = [
    [meta.topic_count, '候選議題'],
    [meta.reviewed_count, '已審閱答案'],
    [meta.sample_count, '已覆核真實樣本'],
    [meta.ranked_count ? `${meta.ranked_count} 題` : '待建立', '正式 Top 20']
  ];
  element('home-stats').innerHTML = stats.map(([number, label]) =>
    `<div class="overview-stat"><strong>${escapeHTML(number)}</strong><span>${escapeHTML(label)}</span></div>`
  ).join('');
  element('preview-notice').hidden = catalogue.topics.every(topic => topic.origin !== 'editorial_demo');
  const marks = ['◇', '≈', '○', '♨', '▱', '⌘'];
  element('category-grid').innerHTML = meta.categories.map((category, index) => {
    const total = catalogue.topics.filter(topic => topic.category === category).length;
    return `<button class="category-tile" data-category="${escapeHTML(category)}"><span class="category-mark" aria-hidden="true">${marks[index]}</span><span><strong>${escapeHTML(category)}</strong><small>${total} 個候選議題</small></span></button>`;
  }).join('');
  element('featured-topics').innerHTML = catalogue.topics.slice(0, 3).map(topicCard).join('');
  element('category-filters').innerHTML = ['全部', ...meta.categories].map(category =>
    `<button data-filter-category="${escapeHTML(category)}" aria-pressed="${selectedCategory === category}">${escapeHTML(category)}</button>`
  ).join('');
  const questions = catalogue.topics.slice(0, 3);
  element('question-suggestions').innerHTML = questions.map(topic =>
    `<button data-question="${escapeHTML(topic.question)}">${escapeHTML(topic.question)}</button>`
  ).join('');
  element('reviewed-summary').textContent = `目前收錄 ${meta.reviewed_count} 份已審閱答案。`;
}

function filterTopics() {
  const query = element('topic-query').value.trim().toLowerCase();
  const status = element('topic-status').value;
  let topics = catalogue.topics.filter(topic => {
    const text = [topic.question, topic.common_claim, ...topic.search_terms].join(' ').toLowerCase();
    return (selectedCategory === '全部' || topic.category === selectedCategory)
      && (!query || text.includes(query))
      && (status !== 'reviewed' || topic.status === '已審閱')
      && (status !== 'ranked' || topic.rank !== null);
  });
  if (status === 'ranked') topics = [...topics].sort((a, b) => a.rank - b.rank);
  element('topic-result-count').textContent = `找到 ${topics.length} 個議題${status === 'all' ? ' · 候選議題尚未形成正式排名' : ''}`;
  if (topics.length) {
    element('topic-results').innerHTML = topics.map(topicCard).join('');
  } else {
    let message = '試著換個關鍵詞，或選擇其他分類。';
    let title = '這個範圍尚無內容';
    if (status === 'ranked') {
      title = '正式 Top 20 正在建立';
      message = '完成真實樣本標註與雙方審閱後，將呈現依散播筆數排序的結果。';
    }
    if (status === 'reviewed') {
      title = '這個範圍尚無已審閱內容';
      message = '審閱完成的答案與出處會出現在這裡。';
    }
    element('topic-results').innerHTML = `<div class="empty-state"><h2>${title}</h2><p>${message}</p></div>`;
  }
  document.querySelectorAll('[data-filter-category]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.filterCategory === selectedCategory));
  });
}

function populateMethods() {
  const meta = catalogue.meta;
  element('method-content').innerHTML = `
    <div class="method-grid">
      <section class="method-card"><h2>資料從哪裡來</h2>
        <h3>Cofacts 真的假的</h3><p>以公開資料涵蓋提交至 Cofacts 的 LINE 轉傳訊息。正式樣本須保留取得時間與來源紀錄。</p>
        <h3>YouTube 留言</h3><p>研究目標為近兩年食用油相關影片中，觀看數最高的前 ${meta.youtube_target} 支。先排除廣告與品牌官方頻道，再蒐集留言。</p>
        <p>影片與創作者清單列於研究報告附件，網站以議題與渠道彙整呈現。</p>
      </section>
      <section class="method-card"><h2>範圍與目前進度</h2>
        <p>資料期間 ${escapeHTML(meta.date_from)} 至 ${escapeHTML(meta.date_to)}。以繁體中文、會煮飯的讀者為主要範圍。</p>
        <p>已覆核真實樣本 ${meta.sample_count} 筆，議題標註 ${meta.annotation_count} 筆。已審閱答案 ${meta.reviewed_count} 份，正式排名 ${meta.ranked_count} 題。</p>
        <p>目前的候選議題為編輯建立的示範，供確認頁面與流程。資料蒐集與內容審閱仍待完成。</p>
      </section>
    </div>
    <section class="method-card"><h2>同一個議題，分開看三種表態</h2>
      <div class="table-scroll"><table><thead><tr><th>標註類型</th><th>判讀方式</th></tr></thead><tbody>
      <tr><td>散播主張</td><td>傳遞某項事實或健康主張，後續對照官方或學術資料。</td></tr>
      <tr><td>提出疑問</td><td>以提問方式表達需求，保留問題而不判定對錯。</td></tr>
      <tr><td>反駁或澄清</td><td>反駁相關主張或提供補充與更正資訊。</td></tr></tbody></table></div>
      <p>文字不同但意義相同的說法由研究人員歸入同一議題。確認和官方或研究資料存在落差、且完成審閱後，才標為迷思。</p>
    </section>
    <div class="method-grid method-wide">
      <section class="method-card"><h2>排名與比例怎麼算</h2>
        <p>本版採樣本中散播主張的筆數排序，同筆資料依渠道與紀錄 ID 去重，同分依議題 ID 排序。最多顯示 ${meta.ranking_limit || 20} 題。</p>
        <p>渠道比例以該議題在該渠道的已覆核筆數作為分母。單筆資料可涉及不同議題，各議題筆數可能重疊。</p>
        <p>樣本取決於關鍵詞、平台涵蓋、影片篩選與可取得的留言。Cofacts 的收錄量和 YouTube 留言數反映不同的資料來源特性，不能直接推論全體消費者的想法。</p>
      </section>
      <section class="method-card"><h2>答案與隱私如何管理</h2>
        <p>正確說法須附官方或學術出處，由指導老師與公司完成內容及法規審閱後提供。修改答案或來源會使舊審閱失效，暫時下架可立即撤回。</p>
        <p>網站只顯示概括改寫的說法、審閱內容與彙整數據。網友帳號、可辨識原文、品牌評論與個別創作者資料保留在公開頁之外。</p>
        <p>問答以已審閱問句及同義問法查找固定答案。沒有對應內容時，明確告知尚未收錄。</p>
      </section>
    </div>`;
}

function channelTable(topic) {
  return `<div class="table-scroll"><table><thead><tr><th>渠道</th><th>樣本數</th><th>散播主張</th><th>提出疑問</th><th>反駁或澄清</th></tr></thead><tbody>${topic.channels.map(channel =>
    `<tr><td>${escapeHTML(channel.name)}</td><td class="numeric">${channel.total}</td>${channel.roles.map(role =>
      `<td class="numeric">${role.count} 筆${role.percent === null ? ' · 尚無比例' : ` · ${role.percent}%`}</td>`
    ).join('')}</tr>`
  ).join('')}</tbody></table></div>`;
}

function populateDetail(id) {
  const topic = catalogue.topics.find(item => item.id === id);
  if (!topic) {
    element('topic-detail').innerHTML = '<div class="empty-state"><h1>找不到這個議題</h1><p>議題可能尚未收錄或已暫時撤回。</p></div>';
    return;
  }
  const ready = topic.status === '已審閱';
  element('topic-detail').innerHTML = `
    <div class="detail-heading"><span class="category-label">${escapeHTML(topic.category)}</span> ${statusTag(topic)}
      <h1>${escapeHTML(topic.question)}</h1>
      <p>${topic.rank ? `樣本排名 ${topic.rank} · ` : ''}${topic.sample_count} 筆已覆核真實樣本${ready ? ` · 審閱日期 ${escapeHTML(topic.reviewed_at)}` : ' · 候選示範議題'}</p>
    </div>
    <section class="detail-section"><h2>常見說法</h2><blockquote class="common-claim">「${escapeHTML(topic.common_claim)}」</blockquote>
      ${ready ? '' : '<p class="secondary-note">以上為編輯撰寫的待查證示範說法。</p>'}</section>
    <section class="detail-section"><h2>哪裡對，哪裡有落差</h2>
      ${ready ? `<p>${escapeHTML(topic.gap || '此題以疑問形式收錄，請參考下方已審閱答案。')}</p>` : '<div class="pending-copy"><p>此議題待完成文獻對照與雙方審閱。判讀時會核對油種、烹調條件、研究對象及結果。</p></div>'}</section>
    <section class="detail-section"><h2>正確說法與出處</h2>
      ${ready ? `<p>${escapeHTML(topic.answer)}</p>${sourceList(topic.sources)}` : '<p class="secondary-note">目前尚未收錄此題的已審閱答案與正式引用。</p>'}</section>
    <section class="detail-section"><h2>不同渠道怎麼討論</h2>${channelTable(topic)}
      <p class="secondary-note">比例的分母為該議題在該渠道的已覆核樣本數，零筆時不計算比例。</p>
      ${topic.representative_summary ? `<h3>代表性內容摘要</h3><p>${escapeHTML(topic.representative_summary)}</p>` : '<p class="secondary-note">代表性內容將在去識別改寫並審閱後呈現。</p>'}</section>
    <div class="detail-actions"><button class="button primary" data-question="${escapeHTML(topic.question)}">用問答查詢這一題</button><a class="button subtle" href="#methods">了解研究方法</a></div>`;
}

function route() {
  if (!catalogue) return;
  let hash;
  try { hash = decodeURIComponent(location.hash.slice(1)); } catch { hash = 'home'; }
  const view = hash.startsWith('topic/') ? 'detail' : ['home', 'topics', 'ask', 'methods'].includes(hash) ? hash : 'home';
  document.querySelectorAll('.view').forEach(section => { section.hidden = section.id !== `${view}-view`; });
  document.querySelectorAll('[data-nav]').forEach(link => {
    const active = link.dataset.nav === view || view === 'detail' && link.dataset.nav === 'topics';
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  if (view === 'topics') filterTopics();
  if (view === 'detail') populateDetail(hash.slice('topic/'.length));
  window.scrollTo({top: 0, behavior: 'instant'});
}

async function submitQuestion(question) {
  const currentRequest = ++requestNumber;
  const result = element('answer-result');
  element('question').value = question;
  element('char-count').textContent = `${question.length} / 500 字`;
  location.hash = 'ask';
  result.setAttribute('aria-busy', 'true');
  element('ask-button').disabled = true;
  result.innerHTML = '<div class="answer-block"><p>正在查詢已審閱內容…</p></div>';
  try {
    const response = await fetch('/api/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question})
    });
    const answer = await response.json();
    if (!response.ok) throw new Error(answer.error || '目前無法完成查詢');
    if (currentRequest !== requestNumber) return;
    if (answer.status === 'answered') {
      result.innerHTML = `<div class="answer-block"><span class="status-tag approved">已審閱答案</span><h2>${escapeHTML(answer.question)}</h2><p>${escapeHTML(answer.answer)}</p>${sourceList(answer.sources)}<p class="secondary-note">審閱日期 ${escapeHTML(answer.reviewed_at)}</p><a class="plain-link" href="#topic/${encodeURIComponent(answer.topic_id)}">查看完整對照</a></div>`;
    } else {
      result.innerHTML = `<div class="answer-block"><span class="status-tag pending">尚未收錄</span><h2>${escapeHTML(answer.message)}</h2><p>你可以瀏覽相關議題，或換一個問題查詢。</p>${answer.related_topics.length ? `<ul class="related-list">${answer.related_topics.map(topic => `<li><a href="#topic/${encodeURIComponent(topic.id)}">${escapeHTML(topic.question)}</a> <span class="secondary-note">${escapeHTML(topic.status)}</span></li>`).join('')}</ul>` : '<a href="#topics" class="plain-link">瀏覽候選議題</a>'}</div>`;
    }
  } catch (error) {
    if (currentRequest === requestNumber) result.innerHTML = `<div class="answer-block"><h2>目前無法完成查詢</h2><p>${escapeHTML(error.message)}</p></div>`;
  } finally {
    if (currentRequest === requestNumber) {
      element('ask-button').disabled = false;
      result.setAttribute('aria-busy', 'false');
    }
  }
}

async function init() {
  try {
    const response = await fetch('/api/public');
    if (!response.ok) throw new Error('內容暫時無法讀取，請稍後再試。');
    catalogue = await response.json();
    populateHome();
    populateMethods();
    element('load-status').hidden = true;
    route();
  } catch (error) {
    element('load-status').textContent = error.message;
  }
}

element('hero-form').addEventListener('submit', event => {
  event.preventDefault();
  submitQuestion(element('hero-query').value.trim());
});
element('ask-form').addEventListener('submit', event => {
  event.preventDefault();
  submitQuestion(element('question').value.trim());
});
element('question').addEventListener('input', () => {
  element('char-count').textContent = `${element('question').value.length} / 500 字`;
});
element('topic-query').addEventListener('input', filterTopics);
element('topic-status').addEventListener('change', filterTopics);
element('clear-filters').addEventListener('click', () => {
  selectedCategory = '全部';
  element('topic-query').value = '';
  element('topic-status').value = 'all';
  filterTopics();
});
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.question) submitQuestion(button.dataset.question);
  if (button.dataset.category) {
    selectedCategory = button.dataset.category;
    element('topic-query').value = '';
    element('topic-status').value = 'all';
    location.hash = 'topics';
    filterTopics();
  }
  if (button.dataset.filterCategory) {
    selectedCategory = button.dataset.filterCategory;
    filterTopics();
  }
});
window.addEventListener('hashchange', route);
init();
