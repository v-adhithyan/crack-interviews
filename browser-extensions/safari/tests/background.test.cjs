const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../background.js'), 'utf8').replace(/^import .*;\n/, '');
const origin = 'https://www.hackerleap.com';
function setup({permission=true, destination='/app/analysis/12345678-1234-1234-1234-123456789012/'}={}) {
  let listener; const opened=[], stored=[], injections=[];
  const browser={
    runtime:{id:'test', getURL:p=>'safari-web-extension://test/'+p,onMessage:{addListener:fn=>listener=fn}},
    permissions:{contains:async()=>permission},
    tabs:{query:async()=>[{id:1,url:origin+'/app/extension/'}],get:async()=>({id:1,status:'complete'}),create:async v=>opened.push(v)},
    storage:{session:{set:async v=>stored.push(v)}},
    scripting:{executeScript:async options=>{injections.push(options); return [{result:{data:{url:destination,status:'pending'}}}];}}
  };
  vm.runInNewContext(source,{browser,URL,setTimeout,allowedOrigin:value=>{if(value!==origin)throw Error('Unsupported origin');return value;},BRIDGE:'/app/extension/',permissionPattern:()=>origin+'/*'});
  const sender={id:'test',url:browser.runtime.getURL('popup.html')};
  const send=(message,who=sender)=>new Promise(resolve=>{if(listener(message,who,resolve)===false)resolve(null);});
  return {send,opened,stored,injections};
}
test('Safari background handles submission using browser namespace and isolated bridge',async()=>{
  const s=setup();const r=await s.send({type:'submit',origin,body:{request_id:'example'}});
  assert.equal(r.data.status,'pending');assert.equal(s.injections[0].world,'ISOLATED');
  assert.equal(s.opened.length,1);assert.equal(s.stored.length,1);
});
test('Rejects non-popup callers before browser access',async()=>{
  const s=setup();assert.equal(await s.send({type:'submit',origin},{id:'test',url:origin}),null);
  assert.equal(s.injections.length,0);
});
test('Rejects unapproved hosts and revoked access',async()=>{
  const s=setup();assert.match((await s.send({type:'submit',origin:'https://evil.test'})).error,/origin/);
  const denied=setup({permission:false});assert.match((await denied.send({type:'submit',origin})).error,/Connect/);
  assert.equal(denied.injections.length,0);
});
test('Rejects external analysis redirects without opening a tab or saving URL',async()=>{
  const s=setup({destination:'https://evil.test/app/analysis/12345678-1234-1234-1234-123456789012/'});
  assert.match((await s.send({type:'submit',origin})).error,/destination/);
  assert.equal(s.opened.length,0);assert.equal(s.stored.length,0);
});
