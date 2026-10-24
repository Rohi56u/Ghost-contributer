/* No remote assets, analytics, model calls or HTML injection. */
const $ = (selector) => document.querySelector(selector);
const tokenParams = new URLSearchParams(location.hash.slice(1));
if (tokenParams.has('token')) { sessionStorage.setItem('ghost-token', tokenParams.get('token')); history.replaceState(null, '', '/'); }
const token = sessionStorage.getItem('ghost-token') || '';
let state = null, currentId = null, busy = false;
function element(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function notice(message, error = false) { const n = $('#notice'); n.textContent = message; n.className = 'notice' + (error ? ' error' : ''); n.hidden = false; }
async function api(path, body) {
  const r = await fetch(path, {method: body ? 'POST' : 'GET', headers: {Authorization: 'Bearer ' + token, ...(body ? {'Content-Type': 'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined});
  const data = await r.json(); if (!r.ok) throw new Error(data.error || 'Local operation failed.'); return data;
}
function setBusy(value) { busy = value; document.querySelectorAll('button').forEach(b => b.disabled = value); $('#scan-button').textContent = value ? 'Working locally…' : '✦  Find a small improvement'; }
async function action(body) { if (busy) return; setBusy(true); try { const r = await api('/api/action', body); notice(({noop:'No supported documentation gap found. No changes made.',pending_exists:'Review the existing proposal before generating another.',quiet_hours:'This repository is inside its quiet hours.',committed:'Local commit created. Your current branch is unchanged.',rejected:'Proposal rejected. No source files changed.',pending:'New proposal ready for your review.'})[r.status] || 'Status: ' + r.status); await refresh(); } catch(e) { notice(e.message, true); } finally { setBusy(false); } }
function date(value) { return new Date(value).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
function repo() { return state?.repositories.find(r => r.name === $('#repo-select').value); }
function proposals() { return (state?.proposals || []).filter(p => p.repo === repo()?.name); }
function tag(status) { return element('span', 'tag ' + status, status.replaceAll('_', ' ').toUpperCase()); }
async function refresh() {
  state = await api('/api/status'); const previous = $('#repo-select').value; $('#repo-select').replaceChildren();
  state.repositories.forEach(r => { const o = element('option', '', r.name); o.value = r.name; $('#repo-select').append(o); });
  if (state.repositories.some(r => r.name === previous)) $('#repo-select').value = previous;
  $('#system-status').textContent = state.killed ? 'Stopped' : state.paused ? 'Paused' : 'Local · Ready';
  $('#pause-button').textContent = state.paused || state.killed ? 'Resume' : 'Pause';
  render();
}
function render() {
  const entries = proposals(), pending = entries.filter(p => p.status === 'pending');
  $('#pending-count').textContent = pending.length; $('#queue-count').textContent = pending.length;
  $('#commit-count').textContent = entries.filter(p => p.commit_sha && !['commit_failed','committing'].includes(p.status)).length;
  $('#model-name').textContent = repo()?.model || 'No repository';
  $('#demo-banner').hidden = !entries.some(p => p.fixture);
  const query = $('#search').value.toLowerCase();
  const visible = [...entries].sort((a,b)=>(a.status === 'pending' ? -1 : 1) - (b.status === 'pending' ? -1 : 1)).filter(p => (p.target.path + p.target.symbol + p.status).toLowerCase().includes(query));
  if (!visible.some(p => p.id === currentId)) currentId = visible[0]?.id;
  $('#proposal-list').replaceChildren();
  visible.forEach(p => {
    const b = element('button', 'proposal-item' + (p.id === currentId ? ' selected' : '')); b.append(tag(p.status));
    b.append(element('h3', '', 'Document ' + p.target.symbol), element('p', '', p.target.path));
    const foot = element('div', 'item-bottom'); foot.append(element('span', '', p.fixture ? 'DEMO FIXTURE' : 'AI-ASSISTED'), element('span', '', date(p.created))); b.append(foot);
    b.onclick = () => { currentId = p.id; render(); }; $('#proposal-list').append(b);
  });
  if (!visible.length) $('#proposal-list').append(element('div', 'empty', query ? 'No matching proposals.' : 'No proposals yet.'));
  const selected = visible.find(p => p.id === currentId); if (selected) detail(selected); else emptyDetail();
  renderHistory(); renderPolicy();
}
function emptyDetail() { const box = element('div','empty'); box.append(element('div','empty-icon','◇'),element('h3','','Room for useful work.'),element('p','','Register a clean repository, then find a small improvement.'),element('code','','ghost repo add /path/to/repo')); $('#proposal-detail').replaceChildren(box); }
function detail(p) {
  const card = $('#proposal-detail'); card.replaceChildren();
  const top = element('div','card-top'), row=element('div','card-top-line'); row.append(tag(p.status),element('span','repo-path',p.fixture ? 'FIXED DEMO · NO MODEL CALL' : p.model.tag));
  top.append(row,element('h3','','A little context for ' + p.target.symbol),element('p','repo-path',p.target.path + ' · line ' + p.target.line));card.append(top);
  const rationale=element('div','rationale');rationale.append(element('span','label','WHY THIS CHANGE'),element('span','',p.response.rationale));card.append(rationale);
  const wrap=element('div','diff-wrap'),heading=element('div','diff-heading');heading.append(element('span','',p.target.path),element('span','','1 file · prose only'));wrap.append(heading);
  const code=element('pre','diff'); p.diff.split('\n').forEach(line=>code.append(element('span','line ' + (line.startsWith('+++')||line.startsWith('---')||line.startsWith('@@')?'meta':line.startsWith('+')?'add':line.startsWith('-')?'remove':''),line || ' ')));wrap.append(code);card.append(wrap);
  const evidence=element('div','evidence');evidence.append(element('span','label','EVIDENCE, NOT GUESSWORK'));
  p.response.evidence.forEach(e=>{const d=element('details');d.append(element('summary','',e.path + ' · lines ' + e.start_line + '–' + e.end_line),element('pre','',e.quote));evidence.append(d);});
  evidence.append(element('p','','Uncertainty: ' + p.response.uncertainty));
  const chips=element('div','validation-chips'); ['Schema checked','Source quote matched','Diff bounded','Repeat edit checked'].forEach(label=>chips.append(element('span','','✓ ' + label))); evidence.append(chips);card.append(evidence);
  const actions=element('div','card-actions'),buttons=element('div');
  const download=element('button','text-button','Download diff'); download.onclick=()=>{ const url=URL.createObjectURL(new Blob([p.diff],{type:'text/plain'}));const a=element('a');a.href=url;a.download='ghost-'+p.id+'.patch';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); };actions.append(download);
  if(p.status==='pending') { const reject=element('button','button','Reject'),approve=element('button','button primary','Approve local commit');reject.onclick=()=>action({action:'reject',id:p.id});approve.onclick=()=>{ $('#confirm-branch').textContent=p.branch;$('#confirm-dialog').returnValue='cancel';$('#confirm-dialog').dataset.proposalId=p.id;$('#confirm-dialog').showModal(); };buttons.append(reject,approve); }
  else buttons.append(element('small','',p.commit_sha ? 'Commit ' + p.commit_sha.slice(0,10) : p.status.replaceAll('_',' ')));
  actions.append(buttons);card.append(actions);
}
function renderHistory() {
  const box=$('#history-list');box.replaceChildren();const runs=state.runs.filter(r=>r.repo===repo()?.name);
  runs.forEach(r=>{const row=element('div','history-row'),l=element('div');l.append(element('strong','',r.detail.replaceAll('_',' ')),element('small','',date(r.created)+' · '+r.period));row.append(l,tag(r.status));box.append(row);});
  if(!runs.length)box.append(element('div','empty','Your first run will appear here.'));
  const audit=$('#audit-list');audit.replaceChildren();state.events.slice(0,15).forEach(e=>{const row=element('div','history-row'),l=element('div');l.append(element('strong','',e.action.replaceAll('_',' ')),element('small','',date(e.at)));row.append(l,element('code','',e.id || e.run || e.repo || 'workspace'));audit.append(row);});
}
function renderPolicy() {
  const box=$('#policy-card');box.replaceChildren();const r=repo();if(!r){box.append(element('div','empty','Register a repository from the CLI to begin.'));return;}
  const rows=[['Repository',r.path],['Publishing mode',r.mode],['Model tag',r.model],['Daily schedule',r.at+' · '+r.timezone],['Remote push permission',r.allow_push?'Enabled · explicit CLI action':'Disabled'],['Inference transport','Loopback HTTP only'],['Edit scope','Python docstrings / marked Markdown'],['Source branch protection','Topic branches only']];
  rows.forEach(([a,b])=>{const row=element('div','policy-row');row.append(element('span','',a),element('code','',b));box.append(row);});
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n===b));['review','history','policy'].forEach(v=>$('#'+v+'-view').hidden=v!==b.dataset.view);const names={review:'Review queue',history:'Run history',policy:'Repository policy'};$('#page-label').textContent=names[b.dataset.view];});
$('#repo-select').onchange=()=>{currentId=null;render();};$('#search').oninput=render;
$('#scan-button').onclick=()=>repo()?action({action:'run',repo:repo().name}):notice('Run ghost init and ghost repo add /path/to/repo from your terminal.',true);
$('#refresh-button').onclick=()=>refresh().catch(e=>notice(e.message,true));
$('#pause-button').onclick=()=>action({action:state?.paused||state?.killed?'resume':'pause'});
$('#confirm-dialog').addEventListener('close',()=>{const d=$('#confirm-dialog');if(d.returnValue==='approve' && d.dataset.proposalId)action({action:'approve',id:d.dataset.proposalId});});
refresh().catch(e=>notice(e.message,true));
