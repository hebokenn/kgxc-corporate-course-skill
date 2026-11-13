import test from 'node:test';import assert from 'node:assert/strict';
import {overviewModel} from '../skills/corporate-training-motion/workbench/production-overview.js';
test('missing evidence never implies acceptance',()=>{const x=overviewModel({artifacts:{pilot:[{available:true}]}});assert.equal(x.evidence,'尚无通过记录');assert.deepEqual(x.materials,[]);});
test('read source dispositions and reasons without inventing coverage',()=>{const x=overviewModel({source_coverage:{report:{points:[{id:'p',disposition:'omitted',reason:'重复'}]}}});assert.equal(x.materials[0].status,'未使用');assert.equal(x.materials[0].reason,'重复');});
test('actual status wins over guesses',()=>{assert.equal(overviewModel({},'pilot',{label:'正在编码'}).activity,'正在编码');});

import {createProductionOverview,confirmationStageStatus,confirmationHistory,nextAction} from '../skills/corporate-training-motion/workbench/production-overview.js';
test('the pilot page names an action, and active feedback takes priority over confirmation',()=>{
 const pending={stage:'pilot',id:'p1'};
 const data={pending_confirmations:[pending],confirmation_display:{stage:'pilot',question_id:'p1',status:'visible'}};
 assert.equal(nextAction(data,'pilot').title,'看完后确认');
 assert.match(nextAction(data,'sources').detail,/顶部「有声小样」/);
 const editing={...data,confirmation_display:{...data.confirmation_display,editing_feedback:true}};
 assert.deepEqual(nextAction(editing,'pilot'),{title:'正在填写修改意见',detail:'在右侧写清楚要改什么，再提交给 AI。',tone:'action',kicker:'当前'});
});
test('only backend pending and approval facts produce action/confirmed states',()=>{
 const data={gates:[{id:'pilot',status:'ready'}],ai_review:{enabled:true,nodes:{pilot:{status:'awaiting_confirmation',passed:true}}},artifacts:{pilot:[{available:true}]}};
 assert.deepEqual(confirmationStageStatus(data,'pilot'),{id:'blocked',text:'已生成 · 尚未达到确认条件'});
 assert.deepEqual(confirmationHistory(data,'pilot'),[]);
 data.pending_confirmations=[{stage:'pilot',id:'ask-one'}];
 assert.equal(confirmationStageStatus(data,'pilot').id,'queued');
 data.confirmation_display={stage:'pilot',question_id:'old',status:'visible'};
 assert.equal(confirmationStageStatus(data,'pilot').id,'queued');
 data.confirmation_display.question_id='ask-one';
 assert.equal(confirmationStageStatus(data,'pilot').id,'waiting');
 assert.equal(nextAction(data,'sources').title,'完整看完三段有声小样');
 data.confirmation_display.status='error';
 assert.equal(confirmationStageStatus(data,'pilot').id,'retry');
 data.confirmation_display.status='deferred';
 assert.equal(confirmationStageStatus(data,'pilot').id,'paused');
 data.confirmation_display.status='visible';
 data.ai_review.nodes.pilot.status='stale';
 assert.equal(confirmationStageStatus(data,'pilot').id,'stale');
 data.ai_review.nodes.pilot.status='awaiting_confirmation';data.ai_review.nodes.pilot.user_confirmed=true;
 assert.equal(confirmationStageStatus(data,'pilot').id,'confirmed');
});
test('records preserve distinct choices and legacy requires a bound receipt',()=>{
 const data={confirmation_records:[{stage:'script',id:'one',status:'deferred',evidence:'稍后确认'},{stage:'script',id:'two',status:'confirmed',evidence:'明确答复'},{stage:'pilot',id:'ask',status:'changes_requested'}]};
 assert.deepEqual(confirmationHistory(data,'script').map(x=>x.status),['deferred','confirmed']);
 assert.deepEqual(confirmationHistory({ai_review:{nodes:{script:{confirmation:{actor:'human',run_id:'run'}}}}},'script'),[]);
 const bound={ai_review:{nodes:{script:{confirmation:{actor:'human',run_id:'run',artifact_hashes:['bound-hash']}}}}};
 assert.equal(confirmationHistory(bound,'script')[0].id,'run');
});
class FakeNode{
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.events={};}
 append(...children){this.children.push(...children);}
 insertBefore(item,ref){this.children.splice(this.children.indexOf(ref),0,item);}
 replaceChildren(...children){this.children=children;}
 setAttribute(k,v){this.attributes[k]=v;}
 addEventListener(k,fn){this.events[k]=fn;}
 contains(node){return this===node||this.children.some(child=>child.contains?.(node));}
}
test('hover and focus preview history, click pins across refresh, Escape unpins',()=>{
 const document={createElement:(tag)=>new FakeNode(tag)},target=new FakeNode('main');
 const view=createProductionOverview({document});view.mount(target);view.mountHistory(target);
 const data={pending_confirmations:[{stage:'script',id:'ask'}],confirmation_records:[{stage:'script',id:'older',status:'confirmed',evidence:'已确认旧稿'}]};
 view.update(data,'script',{});
 const [card]=target.children[1].children[1].children[0].children,[,wrap]=card.children,[toggle,panel]=wrap.children;
 assert.equal(card.dataset.state,'queued');assert.equal(panel.hidden,true);
 wrap.events.pointerenter();assert.equal(panel.hidden,false);
 wrap.events.pointerleave();assert.equal(panel.hidden,true);
 wrap.events.focusin();assert.equal(panel.hidden,false);
 toggle.events.click();assert.equal(toggle.attributes['aria-pressed'],'true');
 wrap.events.focusout({relatedTarget:null});assert.equal(panel.hidden,false);
 view.update(data,'script',{label:'更新'});
 assert.equal(panel.hidden,false);
 wrap.events.keydown({key:'Escape',stopPropagation(){}});assert.equal(panel.hidden,true);
});

import {materialRows} from '../skills/corporate-training-motion/workbench/production-overview.js';
test('material list does not infer a photo is used because it was uploaded or its text was retained',()=>{
  const sources=[{id:'s1',title:'门店.jpg',location:'source/门店.jpg',available:true},{id:'s2',title:'制度',location:'source/制度.pdf',available:true}];
  const projection=[{id:'s2',source_id:'s2',status:'unverified',source_points:[{id:'point',disposition:'retained'}]}];
  const rows=materialRows(projection,sources);
  assert.equal(rows.length,2);
  assert.equal(rows.find(r=>r.id==='s1').kind,'image');
  assert.ok(rows.every(r=>r.status==='unverified'&&!r.placements.length));
 const ref=materialRows([{id:'s2',source_id:'s2',kind:'file',status:'unverified',source_points:[{id:'point',disposition:'retained'}]}]);
 assert.equal(ref[0].status,'reference');
 assert.deepEqual(ref[0].placements,[]);
});
test('only properly bound current-media placements are linkable',()=>{
  const real={stage:'final',artifact_path:'exports/current.mp4',artifact_sha256:'1'.repeat(64),start_seconds:24.4,end_seconds:26.6};
  const falseTime={...real,start_seconds:28},falsePath={...real,artifact_path:'../other.mp4'},falseBinding={...real,artifact_sha256:'old'};
  const [used,unused]=materialRows([{id:'yes',status:'used',placements:[real,falseTime,falsePath,falseBinding]},{id:'no',status:'unused',path:'../../x',placements:[real]}]);
  assert.deepEqual(used.placements,[real]);assert.deepEqual(unused.placements,[]);assert.equal(unused.path,null);
});

test('registered input and delivery sibling paths are linkable without permitting other traversal',()=>{
  const bound={stage:'final',artifact_path:'../delivery/成片.mp4',artifact_sha256:'a'.repeat(64),start_seconds:0,end_seconds:2};
  const [row]=materialRows([{id:'safe',path:'../inputs/实拍照片.jpg',status:'used',placements:[bound]}]);
  assert.equal(row.path,'../inputs/实拍照片.jpg');assert.deepEqual(row.placements,[bound]);
  for(const path of ['../other/file','../inputs/../private','../delivery/./other','../delivery//other','../delivery/','/absolute','../inputs/dir\\other'])assert.equal(materialRows([{id:'unsafe',path}])[0].path,null,path);
});
