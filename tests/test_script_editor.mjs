import test from 'node:test';
import assert from 'node:assert/strict';
import {paragraphs,paragraphAt,replaceSelection,previewDocument} from '../skills/corporate-training-motion/workbench/script-editor-model.js';

test('selected-text replacement preserves all unselected words and rejects concurrent edits',()=>{
  const text='先核对订单，再核对商品。\n\n信息不符先暂停。'; const start=2,end=6;
  const selection={snapshot:text,start,end,text:text.slice(start,end)};
  assert.equal(replaceSelection(text,selection,'检查订单'),text.slice(0,start)+'检查订单'+text.slice(end));
  assert.throws(()=>replaceSelection('新增文字'+text,selection,'建议'),/已改变/);
});
test('paragraph selection spans the current paragraph, including multiline text',()=>{
  const text='第一段\n同一段第二行\n\n第二段';
  assert.equal(paragraphs(text).length,2);assert.equal(paragraphAt(text,6).text,'第一段\n同一段第二行');
  assert.equal(paragraphAt('# 课程标题\n正文第一行\n正文第二行',8).text,'正文第一行\n正文第二行');
});
test('live preview uses real scene bindings and leaves the production document untouched',()=>{
  const base='先核对订单。\n\n再核对商品编码。';
  const original={fields:[{id:'f1',sceneId:'s1',text:'先核对订单。'}],captions:[{id:'c1',sceneId:'s1',text:'先核对订单'}],scenes:[{id:'s1',sourceStartFrame:30}],holds:[]};
  const value=previewDocument(original,base,'先检查订单。\n\n再核对商品编码。',2);
  assert.equal(value.document.fields[0].text,'先检查订单。');assert.equal(value.document.captions[0].text,'先检查订单');assert.equal(value.scene.id,'s1');
  assert.equal(original.fields[0].text,'先核对订单。');assert.equal(original.captions[0].text,'先核对订单');
  const structural=previewDocument(original,base,'新增段落\n\n'+base,0);assert.equal(structural.needsBinding,true);assert.equal(structural.mapped,0);
});

test('reordered or repeated paragraphs require fresh bindings rather than changing another scene',()=>{
  const doc={fields:[{id:'f1',text:'相同段落',sceneId:'s1'},{id:'f2',text:'相同段落',sceneId:'s2'}],captions:[],scenes:[]};
  const ambiguous=previewDocument(doc,'相同段落\n\n相同段落','修改一段\n\n相同段落');
  assert.equal(ambiguous.mapped,0);assert.equal(ambiguous.document.fields[0].text,'相同段落');
  const reordered=previewDocument(doc,'先核对订单\n\n再核对编码','再核对编码\n\n先核对订单');
  assert.equal(reordered.needsBinding,true);assert.equal(reordered.mapped,0);
});
