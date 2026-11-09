// Source comparison belongs to the producer and explicit user confirmation.
export function sourceCoverageDeclaration(coverage,checked){
  if(!coverage?.required||coverage.confirmed)return undefined;
  if(!checked||!coverage.current||!coverage.report_sha256)throw Error('请先查看当前原件对照，明确确认取舍与新增内容。');
  return {report_sha256:coverage.report_sha256,evidence:'用户明确勾选：已对照当前原件与逐字稿，确认报告中的保留、合并、舍弃及新增内容和理由',source:'workbench-explicit-click'};
}
export function createSourceCoveragePanel({getData,action,host,onError,isBusy=()=>false,document=globalThis.document}){
  const el=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
  let dialog,sending=false;
  const launch=el('button','原件对照');launch.type='button';launch.id='source-coverage-open';document.querySelector('header').insertBefore(launch,document.getElementById('primary'));
  launch.onclick=()=>open();
  function button(text,callback){const node=el('button',text);node.type='button';node.disabled=sending;node.onclick=()=>void Promise.resolve().then(callback).catch(onError);return node;}
  function paint(){
    const coverage=getData()?.source_coverage||{},report=coverage.report||{},stats=coverage.statistics||{};
    dialog.replaceChildren();const head=el('div',undefined,'row');head.append(el('h2','原始资料与当前逐字稿对照'),button('关闭，稍后确认',()=>dialog.close()));dialog.append(head);
    dialog.append(el('p','按独立业务要点核对，不按字数或关键词。舍弃项保留在分母；新增内容单独说明理由与依据。原件可在资料页查看。'));
    if(!coverage.required)dialog.append(el('p','当前没有登记原始资料，覆盖率不适用；不显示100%。','meta'));
    else dialog.append(el('p',coverage.confirmed?'当前原件、讲稿与报告的人工确认已记录':coverage.current?'当前对照待人工确认':'请先生成或更新与当前原件、讲稿一致的对照报告',coverage.confirmed?'meta':'review-blocked'));
    if(report.points){
      const rate=stats.rate===null||stats.rate===undefined?'全量覆盖率尚未核实':stats.rate+'%';
      dialog.append(el('h3','原始资料信息覆盖率：'+rate),el('p','登记要点：'+(stats.covered??0)+' / '+(stats.total??0)+' 已覆盖；舍弃 '+(stats.omitted??0)+'；新增 '+(stats.additions??0)+' 项。'));
      if(stats.rate==null&&Number.isFinite(stats.registered_rate))dialog.append(el('p','已登记要点比例：'+stats.registered_rate+'%；此比例不代表已核实全文覆盖。','meta'));
      const critical=stats.critical||{};dialog.append(el('p','关键规则、条件与例外：'+(critical.covered??0)+' / '+(critical.total??0)+' 已覆盖；舍弃 '+(critical.omitted??0)+' 项。',critical.omitted?'review-blocked':'meta'));
      dialog.append(el('p',stats.scope||'比例只反映已登记要点；拆点完整性、语义覆盖、遗漏和新增项是否完整仍需人工对照。','meta'));
      dialog.append(el('h3','原件读取范围'));const sources=el('ul');for(const source of report.source_inventory||[])sources.append(el('li',source.source_id+' · '+source.read_scope+' · '+(source.fully_read?'已登记完整读取':'未完整读取')+(source.unreadable?.length?' · 未辨认：'+source.unreadable.join('；'):'')));dialog.append(sources);
      dialog.append(el('h3','保留、合并与舍弃'));const rows=el('div',undefined,'source-coverage-rows');
      for(const point of report.points){const row=el('section',undefined,'source-coverage-row');row.append(el('h4',point.id+' · '+({retained:'保留',merged:'合并',omitted:'舍弃'}[point.disposition]||point.disposition)+(point.critical?' · 关键要点':'')),el('p','原件：'+point.source_id+' / '+point.locator),el('blockquote',point.source_quote),el('p','讲稿对应：'+(point.script_quotes?.join('\n')||'未纳入当前讲稿')),el('p','取舍理由：'+point.reason));rows.append(row);}dialog.append(rows);
      dialog.append(el('h3','写稿新增内容'));if(!report.additions?.length)dialog.append(el('p','报告未登记新增项，需人工核对是否完整。','meta'));
      for(const item of report.additions||[]){const row=el('section',undefined,'source-coverage-row');row.append(el('h4',item.id+' · '+({example:'教学示例',explanation:'教学解释',external:'外部资料事实'}[item.basis_kind]||item.basis_kind)),el('p',item.location),el('blockquote',item.script_quote),el('p','新增理由：'+item.reason),el('p','依据：'+item.basis));dialog.append(row);}
    }
    for(const reason of coverage.reasons||[])dialog.append(el('p',reason,'meta'));
    dialog.append(el('p','本表由制作端对照原件，独立学员盲审仍只看当前成品。关闭、预选或制作委托均不构成人工确认。可在原逐字稿确认时勾选对照声明，一次提交。','meta'));
    const controls=el('div',undefined,'review-actions');const generate=button('请AI生成／更新当前对照',async()=>{if(sending||isBusy())throw Error('请等待当前保存或制作结束。');sending=true;try{await host('source-coverage',{});dialog.close();}finally{sending=false;}});generate.disabled=sending||isBusy();controls.append(generate);
    const confirm=button('我已对照原件，确认以上取舍与新增',async()=>{if(sending||isBusy())throw Error('请等待当前保存或制作结束。');const declaration=sourceCoverageDeclaration(coverage,true);if(!declaration)return; sending=true;try{await action('source-coverage-confirm',declaration);paint();}finally{sending=false;}});confirm.disabled=sending||isBusy()||!coverage.required||!coverage.current||coverage.confirmed;controls.append(confirm);dialog.append(controls);
  }
  function open(){if(!dialog){dialog=el('dialog',undefined,'ai-review-dialog source-coverage-dialog');dialog.setAttribute('aria-label','原件与逐字稿对照');document.body.append(dialog);}paint();if(!dialog.open)dialog.showModal();}
  function sync(){const value=getData()?.source_coverage;launch.textContent=value?.required&&!value.confirmed?'原件对照 · 待确认':'原件对照';if(dialog?.open)paint();}
  return {open,sync};
}
