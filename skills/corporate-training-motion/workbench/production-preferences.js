const OPTIONS={
  customer:[['new','按本课设计新顾客（推荐）','共用可动方法，每课按情境换发型、服装与配色'],['V01','使用短侧分发顾客','眼镜、灰色便装外套；同风格可动人物'],['V02','使用齐肩短发顾客','棕红短发、浅紫圆领上衣；同风格可动人物'],['V03','使用成熟短发顾客','灰鬓短发、米色衬衫；同风格可动人物'],['none','不需要顾客出镜','本课用其他方式讲解']],
  flower_text:[['key-points','适量重点花字（推荐）','突出行动、条件和边界，普通叙述保持简洁'],['minimal','只强调少量关键条件','减少视觉提示'],['off','不加花字','保留正常标题、正文与字幕']],
  sound_effects:[['native','适量提示音（推荐）','沿用已经确定的“叮”和“嘟咚”'],['off','不加提示音','保留正常配音与品牌片头片尾']],
};
const TITLES={customer:'顾客采用什么形象？',flower_text:'重点内容怎样强调？',sound_effects:'要加提示音效吗？'};
export const missingProductionChoices=value=>Object.keys(OPTIONS).filter(key=>!OPTIONS[key].some(([id])=>id===value?.choices?.[key]));
export function productionPreferenceSummary(value){return Object.keys(OPTIONS).map(key=>({customer:'顾客',flower_text:'花字',sound_effects:'音效'})[key]+'：'+(OPTIONS[key].find(([id])=>id===value?.choices?.[key])?.[1]||'尚未选择')).join('；');}

export function createProductionPreferences({getValue,saveChoice,uploadReference,onError,document=globalThis.document,window=globalThis.window}){
  const dialog=document.createElement('dialog');dialog.className='production-preferences';dialog.setAttribute('aria-labelledby','production-preferences-title');document.body.append(dialog);
  let generation=0,busy=false,onReady=null,activeKey=null,mode='summary',alive=true,statusError='';
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  function button(text,run){const n=el('button',text);n.type='button';n.onclick=()=>Promise.resolve(run()).catch(onError);return n;}
  function close(){if(busy)return;generation++;onReady=null;dialog.close();}
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  window.addEventListener('pagehide',()=>{alive=false;generation++;onReady=null;});
  async function choose(key,value,extra={}){
    if(busy)return;busy=true;statusError='';const attempt=generation;render();
    try{
      await saveChoice({key,value,...extra});
      if(!alive||attempt!==generation)return;
      busy=false;const missing=missingProductionChoices(getValue());
      if(mode==='required'&&missing.length){activeKey=missing[0];render();return;}
      if(mode==='required'){
        const next=onReady;onReady=null;dialog.close();generation++;if(next)await next();return;
      }
      activeKey=null;render();
    }catch(error){if(alive&&attempt===generation){busy=false;statusError=error.message;render();onError(error);}}
    finally{if(attempt===generation)busy=false;}
  }
  function render(){
    const value=getValue()||{},missing=missingProductionChoices(value),key=activeKey||missing[0];dialog.replaceChildren();
    const heading=el('div',null,'row');heading.append(el('h2','课程制作偏好'));heading.querySelector('h2').id='production-preferences-title';const exit=button('关闭',close);exit.disabled=busy;heading.append(exit);dialog.append(heading,el('p','选择会保存在这门课程中。点击选项即保存，无需再次提交；关闭窗口不会替你作出选择。','meta'));
    if(statusError){const error=el('p',statusError,'preference-error');error.setAttribute('role','alert');dialog.append(error);}
    if(!activeKey&&mode==='summary'&&!missing.length){
      for(const name of Object.keys(OPTIONS)){const row=el('div',null,'preference-summary');row.append(el('p',({customer:'顾客形象',flower_text:'重点花字',sound_effects:'提示音效'})[name]+'：'+OPTIONS[name].find(([id])=>id===value.choices[name])?.[1]),button('更换',()=>{activeKey=name;render();}));dialog.append(row);}
      dialog.append(el('p','修改后回到分镜更新相关画面与音轨；已有人工作品和历史版本继续保留。','meta'));return;
    }
    activeKey=key;dialog.append(el('p',(Object.keys(OPTIONS).indexOf(key)+1)+' / 3','meta'),el('h3',TITLES[key]));
    const choices=el('div',null,'preference-choices');choices.setAttribute('role','radiogroup');choices.setAttribute('aria-label',TITLES[key]);
    for(const [id,label,detail] of OPTIONS[key]){
      const option=button('',()=>id==='new'?showNewCustomer():choose(key,id));option.className='preference-choice';option.disabled=busy;option.setAttribute('role','radio');option.setAttribute('aria-checked',String(value.choices?.[key]===id));
      if(key==='customer'&&/^V0[123]$/.test(id)){const image=el('img');image.src='/ui-customers/'+id+'.png';image.alt=label;option.append(image);}
      const copy=el('span');copy.append(el('strong',label),el('small',detail));option.append(copy);choices.append(option);
    }
    dialog.append(choices);if(busy)dialog.append(el('p','正在保存本课选择…','meta'));
    if(mode==='summary')dialog.append(button('返回概览',()=>{activeKey=null;render();}));
  }
  function showNewCustomer(){
    if(busy)return;dialog.replaceChildren();const top=el('div',null,'row');top.append(el('h2','新增顾客形象'),button('返回',render));top.querySelector('h2').id='production-preferences-title';dialog.append(top,el('p','描述希望采用的顾客，或上传参考图。AI 会先展示设计，再用于课程。','meta'));
    const label=el('label','希望顾客是什么样子？'),input=el('textarea');input.maxLength=2000;input.placeholder='例如：短卷发、眼镜、浅色衬衫；用同一套可动人物，与其他人区分';input.value=getValue()?.new_customer?.brief||'';label.append(input);dialog.append(label);
    let reference=getValue()?.new_customer?.reference?.path||'';const file=el('input');file.type='file';file.accept='.png,.jpg,.jpeg,.webp';const note=el('p',reference?'已保留本课上传的参考图':'参考图可不上传，由本课情境给出设计方向。','meta');
    const proceed=button('按这个方向设计',()=>choose('customer','new',{brief:input.value,reference_path:reference}));
    file.onchange=async()=>{if(!file.files?.[0])return;proceed.disabled=true;try{const result=await uploadReference(file.files[0]);reference=result.path;note.textContent='已上传：'+file.files[0].name;}catch(error){note.textContent='上传未完成：'+error.message;onError(error);}finally{proceed.disabled=false;}};
    dialog.append(file,note,proceed);
  }
  return {
    open({continueWith=null}={}){generation++;statusError='';onReady=continueWith;mode=continueWith?'required':'summary';activeKey=missingProductionChoices(getValue())[0]||null;render();if(!dialog.open)dialog.showModal();dialog.querySelector('button')?.focus();},
    get pending(){return missingProductionChoices(getValue()).length>0;},
  };
}
