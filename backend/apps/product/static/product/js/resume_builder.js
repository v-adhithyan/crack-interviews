/* No personal resume content is written to localStorage or sent to third parties. */
(() => {
  'use strict';
  const root = document.getElementById('resume-builder');
  if (!root) return;
  const initial = JSON.parse(document.getElementById('resume-initial').textContent);
  let content = initial.content, title = initial.title, revision = initial.revision;
  let generation = 0, savedGeneration = 0, saving = false, conflict = false;
  let saveTimer, previewTimer, previewSequence = 0, previewController;
  const fields = document.getElementById('resume-fields');
  const status = document.getElementById('save-status');
  const error = document.getElementById('save-error');
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const schemas = {
    skills: {label: ['Group', 80], items: ['Skills', 1200, true]},
    experience: {company: ['Company', 150], role: ['Role', 150], context: ['Industry / location', 180], dates: ['Dates', 100], bullets: ['Achievements — one bullet per line', 8000, true]},
    education: {school: ['School', 180], degree: ['Degree', 180], location: ['Location', 120], dates: ['Dates', 100]},
  };
  const limits = {skills: 12, experience: 15, education: 10};
  const labels = {skills: 'Skills', experience: 'Work history', education: 'Education'};
  const node = (tag, text, parent) => {const el = document.createElement(tag); if (text) el.textContent = text; if (parent) parent.append(el); return el;};
  function message(text) {error.textContent = text; error.hidden = !text;}
  function updateActions() {
    const dirty = generation !== savedGeneration || saving || conflict;
    root.querySelectorAll('.rb-actions button').forEach(button => {button.disabled = dirty;});
    document.getElementById('save-draft').disabled = saving || conflict;
    root.querySelectorAll('input[name=revision]').forEach(input => {input.value = String(revision);});
  }
  function changed() {
    generation++; previewSequence++; // Invalidate responses immediately, even before debounce fires.
    clearTimeout(saveTimer); clearTimeout(previewTimer);
    if (!conflict) {status.textContent = 'Unsaved changes'; saveTimer = setTimeout(save, 900);}
    previewTimer = setTimeout(preview, 350);
    updateActions();
  }
  function input(parent, label, value, max, multiline, onChange) {
    const wrap = node('label', label, parent);
    const el = node(multiline ? 'textarea' : 'input', '', wrap);
    el.value = value; el.maxLength = max;
    el.addEventListener('input', () => {onChange(el.value); changed();});
    return el;
  }
  function button(parent, label, handler) {const el = node('button', label, parent); el.type = 'button'; el.addEventListener('click', handler); return el;}
  function section(label) {const el = node('fieldset', '', fields); node('legend', label, el); return el;}
  function renderFields() {
    fields.replaceChildren();
    input(fields, 'Draft title (not printed)', title, 120, false, value => {title = value;});
    const contact = section('Contact details');
    const contactFields = {name: ['Full name',120], headline:['Headline / availability',180], email:['Email',254], phone:['Phone',60], location:['Location',120], website:['Website / LinkedIn',200]};
    Object.entries(contactFields).forEach(([key, [label,max]]) => input(contact,label,content.contact[key],max,false,value => {content.contact[key]=value;}));
    input(section('Professional summary'), 'Summary', content.summary, 3000, true, value => {content.summary=value;});
    Object.entries(schemas).forEach(([key,schema]) => {
      const group = section(labels[key]);
      content[key].forEach((entry,index) => {
        const row = node('div', '', group); row.className = 'rb-entry';
        node('h3', `${labels[key]} ${index+1}`, row);
        Object.entries(schema).forEach(([field,[label,max,multi]]) => input(row,label,entry[field],max,multi,value => {entry[field]=value;}));
        const actions = node('div','',row); actions.className='rb-entry-actions';
        button(actions,'Move up',() => {if(index>0){[content[key][index-1],content[key][index]]=[entry,content[key][index-1]];changed();renderFields();}}).disabled=index===0;
        button(actions,'Move down',() => {if(index<content[key].length-1){[content[key][index+1],content[key][index]]=[entry,content[key][index+1]];changed();renderFields();}}).disabled=index===content[key].length-1;
        button(actions,'Remove',() => {if(window.confirm('Remove this entry?')){content[key].splice(index,1);changed();renderFields();}});
      });
      button(group,`Add ${labels[key].toLowerCase()}`,() => {content[key].push(Object.fromEntries(Object.keys(schema).map(k=>[k,''])));changed();renderFields();}).disabled=content[key].length>=limits[key];
    });
  }
  async function post(url, body, signal) {
    const response = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},credentials:'same-origin',body:JSON.stringify(body),signal});
    if(response.redirected) throw new Error('Your session expired. Keep a recovery copy before signing in again.');
    const data = await response.json().catch(()=>({detail:'Request failed. Check your connection and try Save again.'}));
    if(!response.ok){const err=new Error(data.detail || 'Unable to save.');err.status=response.status;throw err;}
    return data;
  }
  async function save() {
    clearTimeout(saveTimer);
    if(saving || conflict || generation===savedGeneration) return;
    saving=true; const sentGeneration=generation;
    status.textContent='Saving…'; message(''); updateActions();
    let success=false;
    try {
      const result=await post(root.dataset.save,{title,content,revision});
      revision=result.revision; savedGeneration=sentGeneration; success=true;
      document.getElementById('conflict-actions').hidden=true;
      status.textContent=generation===savedGeneration?'Saved':'Unsaved changes';
    } catch(err) {
      conflict=err.status===409;
      status.textContent=conflict?'Conflict — not saved':'Save failed'; message(err.message);
      document.getElementById('conflict-actions').hidden=false;
    } finally {
      saving=false; updateActions();
      if(success && generation!==savedGeneration) saveTimer=setTimeout(save,200);
    }
  }
  async function preview() {
    const sequence=++previewSequence;
    if(previewController) previewController.abort();
    previewController=new AbortController();
    document.getElementById('preview-status').textContent='Updating preview…';
    try {
      const result=await post(root.dataset.preview,{content},previewController.signal);
      if(sequence!==previewSequence) return;
      document.getElementById('resume-preview').srcdoc=result.html;
      document.getElementById('preview-status').textContent='';
    } catch(err) {
      if(sequence===previewSequence && err.name!=='AbortError') document.getElementById('preview-status').textContent=`Preview not updated: ${err.message}`;
    }
  }
  fields.addEventListener('submit',event=>{event.preventDefault();save();});
  document.getElementById('save-draft').addEventListener('click',save);
  document.getElementById('recovery').addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify({title,content,revision},null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='resume-recovery.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  document.getElementById('reload-draft').addEventListener('click',()=>{if(window.confirm('Load the latest saved draft? Unsaved edits here will be discarded. Download a recovery copy first.')){savedGeneration=generation;window.location.reload();}});
  root.querySelectorAll('.rb-actions form').forEach(form=>form.addEventListener('submit',event=>{
    if(generation!==savedGeneration || saving || conflict){event.preventDefault();message('Save your changes before exporting.');}
    else if(form.id==='use-resume' && !window.confirm('Replace the resume currently selected for analysis with this saved draft?'))event.preventDefault();
  }));
  root.querySelectorAll('[data-panel]').forEach(el=>{if(el.tagName==='BUTTON')el.addEventListener('click',()=>{root.querySelector('.rb-workspace').dataset.panel=el.dataset.panel;root.querySelectorAll('.rb-tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b===el)));});});
  window.addEventListener('beforeunload',event=>{if(generation!==savedGeneration || saving){event.preventDefault();event.returnValue='';}});
  // Keep an A4-width iframe viewport, scaling the whole page to fit the panel.
  const previewFrame=document.getElementById('resume-preview');
  const previewPanel=root.querySelector('.rb-preview');
  function fitPreview() {
    const width=previewPanel.clientWidth;
    if(!width)return;
    const scale=Math.min(1,width/794);
    previewFrame.style.width='794px';
    previewFrame.style.height=`${window.innerHeight*0.75/scale}px`;
    previewFrame.style.zoom=String(scale);
  }
  new ResizeObserver(fitPreview).observe(previewPanel);
  window.addEventListener('resize',fitPreview);
  renderFields();updateActions();preview();fitPreview();
})();
