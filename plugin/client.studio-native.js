// Generated from the shared workbench; run scripts/build_native_client.py.
window.__ModuleLoader__.load({id:"kgxc-course-plugin",chunk:"client.studio-native.js",factory:()=>{
const modules={};
const STUDIO_HTML="<header><div><p id=\"stage-kicker\">课程工作台</p><h1 id=\"course-title\">正在恢复课程</h1></div><span id=\"save-status\" role=\"status\"></span><details id=\"studio-tools\" class=\"studio-tools\"><summary>课程设置与记录</summary><div id=\"studio-tools-content\"><p class=\"tools-caption\">按需调整，不影响 AI 自动执行</p><button id=\"production-preferences\" disabled>调整制作偏好</button><button id=\"undo\" disabled>撤销上次编辑</button></div></details><button id=\"primary\" class=\"primary\" disabled>正在读取</button></header>\n<section id=\"production-progress\" aria-label=\"制作进度\"><div class=\"progress-heading\"><strong id=\"production-label\" role=\"status\">正在读取制作进度</strong><span id=\"production-owner\">制作状态</span></div><div class=\"production-track\"><progress id=\"production-bar\" max=\"1\" value=\"0\" aria-label=\"当前制作进度\"></progress><span class=\"production-indeterminate\" aria-hidden=\"true\"></span></div><p id=\"production-detail\"></p><details id=\"production-steps\" hidden><summary>查看具体制作步骤与耗时</summary><p id=\"production-issue\" role=\"alert\" hidden></p><ol id=\"production-step-list\"></ol></details></section>\n<div id=\"notice\" role=\"status\" hidden></div><section id=\"proposals\" hidden></section><main id=\"content\" aria-label=\"当前制课阶段\"></main>\n<dialog id=\"rewrite\"><form method=\"dialog\"><div class=\"row\"><h2>修改选中的文字</h2><button value=\"cancel\" aria-label=\"关闭修改建议\">关闭</button></div></form><blockquote id=\"rewrite-selection\"></blockquote><label>希望怎么改<input id=\"rewrite-instruction\" placeholder=\"例如：更口语化，保留事实和步骤\"></label><button id=\"rewrite-generate\">生成建议</button><p id=\"rewrite-status\" role=\"status\"></p><label id=\"rewrite-result\" hidden>AI 建议<textarea id=\"rewrite-suggestion\"></textarea></label><button id=\"rewrite-accept\" class=\"primary\" disabled>采用这段修改</button></dialog>\n";
const STUDIO_CSS=":root{font:14px/1.7 -apple-system,BlinkMacSystemFont,\"PingFang SC\",sans-serif;color:#303640;background:#fafbfc;--line:#e2e5e9;--muted:#828a95;--accent:#466bba}*{box-sizing:border-box}body{margin:0}header{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;background:#fff;border-bottom:1px solid var(--line);padding:15px 24px}header>div{flex:1;min-width:0}h1,h2,h3,p{margin:0}h1{font-size:19px;letter-spacing:-.4px}h2{font-size:16px}h3{font-size:14px}#stage-kicker{font-size:11px;color:var(--muted)}button,input,textarea,select{font:inherit;color:inherit}button{border:1px solid #d4d9e0;background:#fff;border-radius:6px;padding:7px 11px;cursor:pointer}button:hover:not(:disabled){background:#f4f6fa}button:disabled{opacity:.45;cursor:default}.primary{background:#405e94;color:#fff;border-color:#405e94}.primary:hover:not(:disabled){background:#344f82}input,textarea,select{border:1px solid #dce0e6;border-radius:5px;padding:8px 10px;background:#fff;width:100%}textarea{resize:vertical;min-height:90px}label{display:block;color:#646d79;font-size:12px}label>input,label>textarea,label>select{display:block;margin-top:5px;color:#303640}#save-status,.meta{font-size:12px;color:var(--muted)}#notice{padding:11px 24px;background:#fff5e8;color:#8a572a;white-space:pre-wrap}#content{padding:24px;max-width:1500px;margin:auto}.intro{color:#727c89;margin-bottom:22px;max-width:780px}.row{display:flex;gap:10px;align-items:center}.row>.grow{flex:1}.stack{display:flex;flex-direction:column;gap:14px}.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px}.card h3{margin-bottom:8px}.card p{white-space:pre-wrap}.muted{color:var(--muted)}.fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fields>.full{grid-column:1/-1}.unit{margin-bottom:15px}.unit .unit-head{display:flex;gap:10px;align-items:center;margin-bottom:12px}.unit .unit-head strong{font-size:12px;white-space:nowrap;color:#86909c}.unit input.title{font-size:16px;font-weight:600;border-color:transparent;padding-left:0}.unit .unit-head .handle{cursor:grab;color:#8a939d;user-select:none}.unit-actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}.unit-actions button{font-size:12px;padding:5px 8px}.unit.drop{outline:2px solid #6f8ac0}.source-grid{display:grid;grid-template-columns:minmax(180px,280px) 1fr;gap:18px}.source-list{display:flex;flex-direction:column;gap:8px}.source-list button{text-align:left}.source-list button[aria-pressed=true]{border-color:#637fae;background:#f1f5fc}.source-preview{background:#fff;min-height:440px;border:1px solid var(--line);border-radius:8px;overflow:hidden}.source-preview iframe{width:100%;height:65vh;border:0}.source-preview pre{white-space:pre-wrap;padding:20px;margin:0}.source-preview img{max-width:100%;display:block;margin:auto}.ledger{margin-top:22px}.ledger-item{padding:12px 0;border-bottom:1px solid var(--line)}.script-grid{display:grid;grid-template-columns:minmax(280px,1fr) minmax(240px,.85fr);gap:18px}.script-form{display:flex;flex-direction:column;gap:12px}.chapter-text{min-height:50vh;line-height:1.95;font-size:16px;padding:18px;resize:vertical}.counts{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}.screen{aspect-ratio:16/9;position:relative;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}.screen iframe{width:100%;height:100%;border:0}.screen .placeholder{position:absolute;inset:0;padding:7%;display:flex;flex-direction:column;gap:9px;overflow:auto}.screen .placeholder p{white-space:pre-wrap}.screen .placeholder small{color:var(--muted);margin-top:auto}.preview-meta{font-size:12px;color:#828a95;margin-top:8px}.playback{display:flex;align-items:center;gap:8px;margin-top:12px}.playback input{padding:0}.board-grid{display:grid;grid-template-columns:195px minmax(0,1fr);gap:20px}.segment-list{display:flex;flex-direction:column;gap:7px;max-height:75vh;overflow:auto;position:sticky;top:100px;align-self:start}.segment-list button{text-align:left;font-size:12px}.segment-list button[aria-current=true]{border-color:#6e88b5;background:#f1f5fc}.segment-copy{margin:12px 0 20px;border-left:2px solid #bdc7d8;padding-left:13px;color:#697484;white-space:pre-wrap}.alternatives{display:flex;flex-direction:column;gap:14px}.alternative[aria-selected=true]{border-color:#6e88b5;box-shadow:inset 3px 0 #6e88b5}.alternative .detail{margin-top:7px;font-size:13px}.keyframe{margin:12px 0;background:#f7f8fa;padding:12px;border-radius:6px}.keyframe img{max-width:100%;max-height:240px}.sample-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}.sample-grid video,.delivery-video{width:100%;background:#222;border-radius:6px}.sample-grid .meta{margin:8px 0}.feedback{display:flex;flex-direction:column;gap:8px;margin-top:14px}.feedback .row>input{width:100px}.job{display:flex;align-items:center;gap:12px;padding:12px;background:#fff;border:1px solid var(--line);margin-bottom:12px}.job progress{flex:1}.empty{padding:60px 26px;text-align:center;background:#fff;border:1px dashed #d9dfe7;border-radius:8px}.empty p{color:var(--muted);margin-top:10px}.impact{padding:12px 16px;border-left:3px solid #b49a6d;background:#faf7f0;margin-bottom:18px;font-size:12px;color:#806c4c}#proposals{margin:15px 24px}.diff{display:grid;grid-template-columns:1fr 1fr;gap:12px}.diff pre{white-space:pre-wrap;font:13px/1.8 inherit;padding:14px;background:#f7f8fa;max-height:350px;overflow:auto}dialog{border:1px solid #d6dce5;border-radius:10px;width:min(660px,90vw);padding:24px;max-height:85vh;overflow:auto}dialog::backdrop{background:#19233455}dialog .row{justify-content:space-between}dialog label{margin:15px 0}dialog blockquote{white-space:pre-wrap;max-height:150px;overflow:auto;color:#6d7786}dialog textarea{min-height:150px}a{color:var(--accent);text-decoration:none}.file-path{font-size:11px;color:#9299a4;overflow-wrap:anywhere;margin-top:18px}.pill{display:inline-block;font-size:11px;color:#667796;background:#eff3f9;padding:2px 7px;border-radius:4px}.pending{margin-bottom:16px}.pending ul{margin:6px 0;padding-left:20px}@media(max-width:850px){header{padding:12px 16px;flex-wrap:wrap}#content{padding:16px}.source-grid{grid-template-columns:180px 1fr}.script-grid{grid-template-columns:1fr}.board-grid{grid-template-columns:155px 1fr}.fields{grid-template-columns:1fr}.fields>.full{grid-column:auto}}@media(max-width:560px){.source-grid,.board-grid{display:flex;flex-direction:column}.segment-list{position:static;max-height:180px}.source-preview{min-height:300px}.diff{grid-template-columns:1fr}header h1{font-size:16px}header button{font-size:12px;padding:5px 8px}.sample-grid{grid-template-columns:1fr}}\n\n.pdf-controls{display:flex;align-items:center;justify-content:center;gap:14px;padding:10px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0}.source-preview .pdf-controls+img{width:100%;height:auto}.source-preview{max-height:75vh;overflow:auto}\n#production-progress{position:sticky;top:var(--studio-header-height,80px);z-index:4;background:#fff;border-bottom:1px solid var(--line);padding:12px 24px 13px}.progress-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.progress-heading strong{font-size:13px;font-weight:500}.progress-heading span,#production-detail{font-size:11px;color:var(--muted)}#production-bar{display:block;width:100%;height:7px;margin:9px 0 7px;accent-color:#617cae;border:0;border-radius:4px;overflow:hidden}#production-bar::-webkit-progress-bar{background:#edf0f4;border-radius:4px}#production-bar::-webkit-progress-value{background:#617cae;border-radius:4px}#production-bar:indeterminate::-webkit-progress-value{background:#7f95ba}#production-progress[data-state=failed] #production-label{color:#a75f4e}#production-detail{line-height:1.6;white-space:pre-wrap}\n.production-track{position:relative;height:7px;margin:9px 0 7px;background:#edf0f4;border-radius:4px;overflow:hidden}.production-track #production-bar{margin:0}.production-indeterminate{display:none;position:absolute;top:0;left:0;width:22%;height:100%;background:#7a92bd;border-radius:4px;animation:production-indeterminate-slide 1.6s ease-in-out infinite alternate}#production-progress[data-indeterminate=true] .production-indeterminate{display:block}@keyframes production-indeterminate-slide{from{transform:translateX(0)}to{transform:translateX(350%)}}@media(prefers-reduced-motion:reduce){.production-indeterminate{animation:none;left:39%}}\n#production-steps{font-size:12px;margin-top:7px;max-height:230px;overflow:auto}#production-steps summary{cursor:pointer;color:#596b84}#production-step-list{list-style:none;padding:0;margin:8px 0 0}.production-step{display:flex;justify-content:space-between;gap:16px;padding:5px 0;border-top:1px solid var(--line)}.production-step>span:first-child{overflow-wrap:anywhere}.production-step .meta{flex-shrink:0;white-space:nowrap}.production-step[data-status=failed],#production-issue{color:#a6503d}#production-issue{white-space:pre-wrap;font:11px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;padding:8px 10px;background:#fff4ef;border-left:3px solid #b2705f}\n#production-steps[data-historical=true] #production-issue{color:var(--muted);background:#f4f5f7;border-left-color:#a2acb8}\n.production-preferences{width:min(680px,calc(100vw - 36px));max-height:calc(100dvh - 48px);padding:24px}.production-preferences h3{margin-top:15px}.preference-choices{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}.preference-choice{display:flex;align-items:center;gap:12px;text-align:left;padding:12px;min-width:0;min-height:80px}.preference-choice>span{display:flex;flex-direction:column;gap:5px;min-width:0}.preference-choice strong{font-weight:500}.preference-choice small{font-size:11px;line-height:1.6;color:var(--muted)}.preference-choice[aria-checked=true]{border-color:#6c86b5;background:#f1f5fc}.preference-choice img{width:62px;height:100px;object-fit:contain;background:#f5f6fa;border-radius:5px;flex-shrink:0}.preference-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}.preference-error{color:#a6503d;padding:10px 0}.production-preferences textarea{min-height:100px}@media(max-width:520px){.preference-choices{grid-template-columns:1fr}.production-preferences{padding:18px}.preference-choice img{height:82px}.preference-summary{flex-wrap:wrap}}\n.job{display:flex;flex-direction:column;align-items:stretch;min-width:0;max-width:100%;border-radius:8px;gap:8px}.job-heading{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;min-width:0}.job-label{white-space:nowrap;flex-shrink:0;font-size:13px}.job-heading .meta{overflow-wrap:anywhere}.job-progress{display:flex;gap:12px;align-items:center;min-width:0}.job-progress progress{width:100%;min-width:40px}.job-progress span{white-space:nowrap}.job-history{margin:16px 0 22px;min-width:0;max-width:100%}.job-history>summary,.job-diagnostics>summary{cursor:pointer;color:#69778d;font-size:12px}.job-history>.meta{margin:8px 0 12px}.job[data-status=failed]>.job-heading{color:#a6503d}.job-history .job[data-status=failed]>.job-heading{color:#697484}.job-diagnostics{min-width:0;max-width:100%}.job-diagnostics pre{max-height:220px;max-width:100%;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 ui-monospace,monospace;padding:12px;background:#f6f7f9;border-radius:5px}#content,.card,.stack{min-width:0}.production-step>span:first-child{min-width:0}.progress-heading strong{min-width:0;overflow-wrap:anywhere}.progress-heading>span{white-space:nowrap;flex-shrink:0}\nheader{flex-wrap:wrap}header>div{flex:1 1 320px;min-width:min(100%,280px)}header>button,header>#save-status{flex-shrink:0}@media(max-width:850px){header>div{flex-basis:100%}}\n/* Review summaries remain usable in the embedded DSH panel and on small windows. */\n.ai-review-progress{padding:12px 28px;background:#f1f5fa;border-bottom:1px solid #dbe3ec;overflow-wrap:anywhere}\n.ai-review-progress p{margin:4px 0;color:#5c6571}\n.ai-review-dialog{width:min(820px,calc(100vw - 32px));max-height:calc(100dvh - 32px);box-sizing:border-box;padding:26px;border:1px solid #d7dce4;border-radius:12px;overflow-y:auto;color:#2c3036;background:white}\n.ai-review-dialog::backdrop{background:rgba(24,31,43,.32)}\n.ai-review-dialog .row{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}\n.ai-review-dialog h2{font-size:20px;margin:0 0 12px;overflow-wrap:anywhere}\n.ai-review-dialog h3{font-size:15px;margin:18px 0 6px}\n.ai-review-dialog pre,.ai-review-progress pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;font:12px/1.65 ui-monospace,monospace}\n.ai-review-dialog label{display:block;margin-top:16px}\n.ai-review-dialog textarea{box-sizing:border-box;width:100%;font:inherit;margin-top:6px;padding:10px;resize:vertical}\n.review-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}\n.review-items{padding-left:22px;overflow-wrap:anywhere}\n.review-items p{margin:4px 0 10px}\n.review-verdict{font-weight:600;color:#344a68}.review-blocked{color:#9d4334}\n.review-audio-scope{margin:16px 0;padding:14px 16px;border:1px solid #dbe3ec;border-radius:7px;background:#f7f9fc;overflow-wrap:anywhere}\n.review-audio-scope h2,.review-audio-scope h3{margin:0 0 8px}.review-audio-scope p+p{margin-top:8px}\n.review-media-bindings{padding-left:20px}.review-media-bindings li{margin:8px 0;overflow-wrap:anywhere}.review-media-bindings a{display:inline-block}\n.review-media-binding{margin:15px 0;padding-top:12px;border-top:1px solid var(--line);min-width:0}.review-media-binding .file-path{margin:6px 0}.review-media-binding video{display:block;margin-top:10px}\n.ai-review-dialog .review-audio-declaration{display:flex;gap:10px;align-items:flex-start;padding:13px;border:1px solid #c4cfdf;border-radius:6px;background:#f7f9fc;color:#303640;font-size:14px}\n.ai-review-dialog .review-audio-declaration input{display:block;width:18px;height:18px;flex:0 0 18px;padding:0;margin:3px 0 0;accent-color:#405e94}.review-audio-declaration span{min-width:0}\n\n.source-coverage-row{border-top:1px solid #ddd;padding:12px 0;min-width:0}.source-coverage-dialog p,.source-coverage-dialog blockquote{white-space:pre-wrap;overflow-wrap:anywhere}.source-coverage-dialog blockquote{margin:8px 0;padding:8px 12px;border-left:3px solid #ddd;background:#f6f6f6}.source-coverage-dialog h4{margin:8px 0}\n\n/* Production desk: artifacts first, decisions second, machinery on demand. */\n:root{--ink:#191c25;--accent:#2455ee;--studio-header-height:84px;color-scheme:light}\nbody,#native-body{background:#f6f6f8;color:var(--ink);font-family:Inter,\"PingFang SC\",\"Microsoft YaHei\",sans-serif;line-height:1.6}\nheader{padding:22px 28px;gap:14px;background:#fff;border-bottom:1px solid #e9e9ee;box-shadow:none;align-items:center}\nheader>div:first-child{flex:1;min-width:180px}#stage-kicker{display:none}\nh1#course-title{font-size:18px;letter-spacing:-.035em;line-height:1.4;font-weight:650}#save-status{font-size:10px;color:#9296a1;white-space:nowrap}\nbutton{border:1px solid #e2e3e9;border-radius:8px;padding:9px 13px;background:#fff;color:#424655;font:inherit;font-size:12px;transition:background .15s}\nbutton:hover:not(:disabled){background:#f0f2fa}button.primary,#primary{background:#2455ee;border-color:#2455ee;color:#fff;box-shadow:none;font-weight:600}button:disabled{opacity:.45;cursor:not-allowed}\nbutton:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #86a2fa;outline-offset:3px}\n.studio-tools{position:relative;font-size:11px;flex:none}.studio-tools>summary{cursor:pointer;list-style:none;padding:8px;color:#7b8190}.studio-tools>summary::after{content:'⌄';margin-left:8px}\n#studio-tools-content{position:absolute;right:0;top:38px;width:240px;padding:12px;background:#fff;border:1px solid #e4e5ec;border-radius:12px;box-shadow:0 16px 48px #17213f20;z-index:100;display:grid;gap:5px}#studio-tools-content button{text-align:left;border-color:transparent}.tools-caption{display:none}\n#production-progress{position:relative;top:auto;margin:0;padding:13px 28px;background:#fff;border:0;border-bottom:1px solid #ececf1;border-radius:0}.progress-heading strong{font-size:12px;font-weight:500}.progress-heading>span{display:none}.production-track{height:3px;margin-top:10px}#production-bar{height:3px}#production-bar::-webkit-progress-value{background:#2455ee}#production-bar::-moz-progress-bar{background:#2455ee}#production-detail{display:none}#production-progress[data-state=failed] #production-detail,#production-progress[data-state=waiting] #production-detail{display:block;font-size:12px;color:#7c6a48;margin:8px 0 0}#production-steps summary{font-size:11px;color:#8c92a2}\n#content{max-width:1500px;padding:24px 28px 40px;margin:auto}.card{background:#fff;border:1px solid #e7e7ee;border-radius:12px;padding:22px;margin-bottom:16px;box-shadow:none}h2{font-size:19px;letter-spacing:-.025em}h3{font-size:14px}p.meta,.meta{color:#868b98;font-size:11px}label{font-size:12px;color:#686f7d}input,textarea,select{font:inherit;color:#313744;border:1px solid #e2e4eb;border-radius:8px;background:#fff;padding:10px 12px}input:focus,textarea:focus,select:focus{outline:2px solid #b4c6ff;outline-offset:1px}.fields{gap:18px}.unit-head{margin-bottom:18px}.unit-head>strong{font-size:11px;color:#7c87a1;white-space:nowrap}.unit-head .title{font-size:18px;font-weight:600;background:transparent;border:0}.chapter-tools{border-top:1px solid #eeeff4;margin-top:16px;padding-top:12px}.chapter-tools summary{font-size:11px;cursor:pointer;color:#818896}.unit-actions{padding-top:12px;gap:8px;flex-wrap:wrap}\n.live-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:10px}.live-heading h2{margin:0;font-size:16px}.live-status{font-size:11px;color:#8b91a1}.live-visual{position:relative;aspect-ratio:16/9;border:1px solid #e2e4ed;border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 8px 30px #202d4c07}.live-visual>img,.live-visual>video{display:block;width:100%;height:100%;object-fit:contain}.live-caption{position:absolute;bottom:12px;left:12px;max-width:calc(100% - 24px);display:flex;gap:14px;padding:6px 10px;border-radius:6px;background:#ffffffed;border:1px solid #e9eaf0;font-size:10px;color:#737b8c}.live-caption strong{font-weight:500;color:#353d50}.live-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#999faf}.live-empty>span{font-size:38px;color:#c2c9dc}.live-empty h3{font-size:15px;font-weight:500;color:#677086;margin:15px 0 0}.live-empty p{font-size:12px;margin:8px}.live-update{position:absolute;top:12px;right:12px;background:#2455ee;color:white;border:0}\n.live-audio{margin-top:16px;padding:16px 18px;background:#fff;border:1px solid #e5e6ee;border-radius:12px;display:grid;grid-template-columns:40px 1fr minmax(180px,290px);align-items:center;gap:12px}.live-audio h3{margin:0;font-size:12px}.live-audio-title{font-size:12px;color:#656d7d;margin:0}.live-audio audio{width:100%;height:32px}.live-audio-list{grid-column:2/-1;display:flex;gap:8px;overflow-x:auto}.live-audio-list:empty{display:none}.live-audio-list button{font-size:10px;padding:4px 8px;white-space:nowrap}.live-audio-list button[aria-pressed=true]{color:#2455ee;border-color:#bccbff;background:#f2f5ff}\n.live-strip{display:flex;gap:12px;margin:18px 0 24px;overflow-x:auto;padding:3px 3px 10px}.live-thumb{flex:0 0 142px;padding:0;background:#fff;border:1px solid #e0e3ed;border-radius:8px;overflow:hidden;text-align:left}.live-thumb[aria-pressed=true]{outline:2px solid #2455ee;outline-offset:1px}.live-thumb img,.live-video-symbol{display:block;width:100%;height:80px;object-fit:cover;background:#eceff8}.live-video-symbol{text-align:center;line-height:80px;color:#2455ee;font-size:24px}.live-thumb>span:last-child{display:block;font-size:10px;padding:8px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sample-inspection{border-top:1px solid #e2e4ec;padding-top:16px}.sample-inspection>summary{font-size:12px;color:#747d91;cursor:pointer}.sample-inspection[open]>summary{margin-bottom:20px}\n.script-grid{gap:24px}.chapter-text{font-size:15px;line-height:2;min-height:420px;padding:22px;border-radius:12px}.screen{border-radius:12px;overflow:hidden}.placeholder{background:#f1f3f9;color:#46516c;padding:28px}.ai-review-progress{margin:18px 28px;padding:18px;background:#eff3ff;border-radius:12px;border:1px solid #dae3ff}dialog{border:1px solid #e4e6ef;border-radius:16px;box-shadow:0 30px 100px #18204233;padding:26px}dialog::backdrop{background:#121b334a;backdrop-filter:blur(4px)}\n@media(max-width:700px){header{padding:18px;gap:8px;flex-wrap:wrap}h1#course-title{font-size:17px}#content{padding:18px}#production-progress{padding:12px 18px}.live-audio{grid-template-columns:40px 1fr}.live-audio audio{grid-column:1/-1}.live-heading{flex-wrap:wrap}.live-caption span{display:none}.live-thumb{flex-basis:120px}.live-thumb img{height:68px}}\n\n/* V3: outputs first; lifecycle evidence is compact and details stay optional. */\n.production-overview{background:#fff;border:1px solid #e3e7ee;border-radius:18px;padding:22px 24px;margin-bottom:22px;box-shadow:0 5px 24px #17294a05}.overview-now{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.overview-now h2{font-size:19px;letter-spacing:-.4px;margin:0;flex:1}.overview-signal{color:#315cff;font-size:14px}.overview-check{font-size:12px;color:#52647c;background:#f0f4fb;border-radius:20px;padding:7px 12px}.overview-journey{display:flex;list-style:none;gap:4px;padding:0;margin:24px 0 12px}.overview-journey li{flex:1;min-width:0;border-top:3px solid #e6eaf0;padding:12px 4px 0;display:grid;gap:6px}.overview-journey strong{font-size:13px;font-weight:600}.overview-journey span{font-size:12px;color:#748093}.overview-journey .is-current{border-color:#315cff;color:#254ed9}.overview-details{border-top:1px solid #edf0f4;padding-top:14px;font-size:13px;color:#52647c}.overview-details summary{cursor:pointer}.overview-details small{display:block;margin-top:5px;color:#748093}.overview-issue{color:#a74c17}.production-overview~.live-workspace{margin-top:0} @media(max-width:700px){.production-overview{padding:16px}.overview-journey{flex-wrap:wrap}.overview-journey li{flex-basis:29%}.overview-now h2{font-size:17px}}\n/* The overview replaces the old duplicate status strip. */\n#production-progress{display:none}.live-visual img{max-height:420px;object-fit:contain;width:100%}.live-visual{min-height:0}\n.live-visual{aspect-ratio:auto;height:440px}.live-visual>img,.live-visual>video{height:100%;max-height:100%}@media(max-width:700px){.live-visual{height:auto;aspect-ratio:16/9}}\n\n/* Read-only confirmation states: all decisions stay in the right-hand chat. */\n.confirmation-strip{border-top:1px solid #edf0f4;padding:15px 0;margin-top:16px}\n.confirmation-head{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:4px 12px;margin-bottom:10px}\n.confirmation-head h3{font-size:14px;margin:0}.confirmation-head p{color:#52647c;font-size:12px;margin:0}\n.confirmation-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;align-items:start}\n.confirmation-card{background:#f8fafc;border:1px solid #e5eaf1;border-radius:10px;padding:9px 10px;min-width:0}\n.confirmation-card[data-state=\"waiting\"]{background:#eef3ff;border-color:#a8baf7}\n.confirmation-card[data-state=\"confirmed\"],.confirmation-card[data-state=\"delivered\"]{background:#f3faf7;border-color:#cce9da}\n.confirmation-card-head{display:flex;align-items:baseline;gap:2px 8px;flex-wrap:wrap;font-size:13px}\n.confirmation-status{font-size:12px;color:#52647c}.confirmation-card[data-state=\"waiting\"] .confirmation-status{color:#2246b8;font-weight:650}\n.confirmation-record-toggle{background:none;color:#40516a;border:0;border-radius:4px;padding:3px 0;margin-top:2px;font-size:12px;text-align:left}\n.confirmation-record-toggle::after{content:\"▾\";margin-inline-start:5px}.confirmation-record-toggle[aria-pressed=\"true\"]::after{content:\"▴\"}\n.confirmation-record-toggle:focus-visible{outline:2px solid #315cff;outline-offset:3px}\n.confirmation-record-panel{font-size:12px;color:#35465e;overflow-wrap:anywhere}\n.confirmation-record-panel[hidden]{display:none}.confirmation-record-panel p{margin:4px 0 0}\n.confirmation-record-panel ul{list-style:none;margin:4px 0 0;padding:0}.confirmation-record-panel li+li{border-top:1px solid #e5eaf1;margin-top:6px;padding-top:6px}.confirmation-record-panel time{display:block;margin-top:2px;color:#52647c}\n@media(max-width:530px){.confirmation-grid{grid-template-columns:1fr}}\n\n.final-phase{margin-bottom:16px}.final-phase h2{margin:6px 0;font-size:20px}.final-phase p{margin:6px 0}.final-phase-index{display:inline-block;border-radius:20px;padding:4px 8px;background:#eef3ff;color:#2246b8;font-size:12px;font-weight:650}.final-phase-evidence{color:#354e77;font-weight:650}\n\n.material-library{margin-top:14px}.material-library h2{margin:0 0 6px;font-size:19px}\n.material-library p{margin:4px 0}.material-library-totals,.material-library-list,.material-library-placements,.material-library-points ul{list-style:none;margin:0;padding:0}\n.material-library-totals{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.material-library-totals li,.material-library-badge{background:#f0f4f9;color:#435777;border-radius:20px;padding:4px 8px;white-space:nowrap;font-size:12px}\n.material-library-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:8px}\n.material-library-row{min-width:0;border:1px solid #e5eaf1;background:#fafbfe;border-radius:10px;padding:10px 12px;overflow-wrap:anywhere;font-size:13px}.material-library-row[data-status=\"used\"] .material-library-badge{background:#dff3e9;color:#215945}\n.material-library-row[data-status=\"unused\"] .material-library-badge{background:#f2eeee;color:#6c4540}.material-library-item-head{display:flex;align-items:center;gap:8px}.material-library-item-head img{width:44px;height:44px;flex:none;object-fit:cover;border-radius:6px;background:#eaf0f7}\n.material-library-identity{min-width:0;flex:1}.material-library-identity h3{font-size:13px;line-height:1.35;margin:0}.material-library-reason,.material-library-empty{color:#4f617b}.material-library-placements{display:flex;gap:4px 10px;flex-wrap:wrap;margin-top:5px}\n.material-library-points{margin-top:7px;color:#4f617b;font-size:12px}.material-library-points li{border-top:1px solid #e5eaf1;margin-top:5px;padding-top:5px}\n\n/* Put the work first. Production diagnostics and receipt history stay below it. */\n.production-overview{padding:12px 15px;margin-bottom:12px;background:#f7f9fd;box-shadow:none}\n.production-overview[data-tone=\"action\"]{background:#eef3ff;border-color:#a8baf7}\n.overview-now{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 9px;align-items:baseline}\n.overview-now h2{font-size:16px}.overview-next-kicker{font-size:11px;font-weight:650;color:#405684}\n.overview-next-detail{grid-column:2;margin:0;color:#52647c;font-size:12px}\n.overview-history{margin:18px 0;color:#435777;font-size:13px;border-top:1px solid #e5eaf1;padding:10px 0}\n.overview-history>summary{cursor:pointer;font-weight:650}\n.overview-history .confirmation-strip{margin-top:8px;padding:8px 0;border:0}\n.overview-history .overview-details{padding-top:8px}\n.material-library-row[data-status=\"reference\"] .material-library-badge{background:#e8efff;color:#314d8e}\n";
modules["script-editor-model"]=(()=>{
// Pure transcript operations shared by the editor and its regression checks.
function paragraphs(text) {
  const result = []; let current;
  const finish = () => { if (current) result.push({...current,text:text.slice(current.start,current.end)}); current = undefined; };
  for (const match of text.matchAll(/[^\n]+/g)) {
    if (!match[0].trim() || /^\s*#{1,6}\s/.test(match[0])) { finish(); continue; }
    if (current && /\n\s*\n/.test(text.slice(current.end,match.index))) finish();
    if (!current) current = {start:match.index,end:match.index+match[0].length};
    else current.end = match.index+match[0].length;
  }
  finish();
  return result;
}
function paragraphAt(text, caret) {
  const items = paragraphs(text);
  return items.find(p => p.start <= caret && caret <= p.end) || items.find(p => p.start > caret) || items.at(-1);
}
function replaceSelection(text, selection, replacement) {
  if (text !== selection.snapshot || text.slice(selection.start, selection.end) !== selection.text) {
    throw Error('逐字稿在生成建议期间已改变，请重新选择后生成；建议仍保留在下方。');
  }
  return text.slice(0, selection.start) + replacement + text.slice(selection.end);
}
const normal = value => value.normalize('NFKC').replace(/[\s\p{P}\p{S}]/gu, '');
function previewDocument(document, original, edited, caret = 0) {
  const doc = structuredClone(document), before = paragraphs(original), after = paragraphs(edited);
  const selected = paragraphAt(edited, caret);
  let sceneId, mapped = 0;
  // A structural rewrite needs fresh scene bindings from production, never a guessed paragraph offset.
  if (before.length !== after.length) return {document: doc, mapped, selected, needsBinding: true};
  if (after.some((p,i) => before.some((old,j) => i !== j && normal(p.text) === normal(old.text) && normal(p.text) !== normal(before[i].text)))) {
    return {document: doc, mapped, selected, needsBinding: true};
  }
  for (let i = 0; i < before.length; i++) {
    const old = before[i], next = after[i], normalized = normal(old.text);
    if (!normalized) continue;
    if (before.filter(p => normal(p.text) === normalized).length !== 1) continue;
    const cues = (doc.captions || []).filter(c => {
      const n = normal(c.text);
      return n && normalized.includes(n) && before.filter(p => normal(p.text).includes(n)).length === 1;
    });
    const fields = (doc.fields || []).filter(f => normal(f.text || '') === normalized);
    if (selected?.start === next.start) sceneId = cues[0]?.sceneId || fields[0]?.sceneId;
    if (old.text === next.text) continue;
    for (const field of fields) { field.text = next.text; mapped++; }
    if (cues.length) {
      const value = next.text.replace(/[\p{P}\r\n]/gu, '').trim();
      const weights = cues.map(c => Math.max(1, [...c.text].length)), total = weights.reduce((a,b) => a+b,0);
      const chars = [...value]; let position = 0;
      cues.forEach((cue,j) => { const end = j === cues.length - 1 ? chars.length : Math.round(chars.length * weights.slice(0,j+1).reduce((a,b)=>a+b,0) / total); cue.text = chars.slice(position,end).join(''); position = end; });
      mapped += cues.length;
    }
  }
  const scene = doc.scenes?.find(s => s.id === sceneId);
  return {document: doc, mapped, selected, scene, needsBinding: edited !== original && !mapped};
}

return {paragraphs,paragraphAt,replaceSelection,previewDocument};})();
modules["timeline"]=(()=>{
// Source coordinates stay immutable; all playback uses this integer-frame edit list.
const EMPTY=[],cache=new WeakMap();
function displayFrame(f,holds,cuts=EMPTY){return f-cuts.reduce((n,c)=>n+Math.max(0,Math.min(f,c.endFrame)-c.startFrame),0)+holds.filter(h=>h.sourceFrame<=f).reduce((n,h)=>n+h.frames,0)}
function totalFrames(d){return d.sourceDurationFrames-(d.cuts||EMPTY).reduce((n,c)=>n+c.endFrame-c.startFrame,0)+d.holds.reduce((n,h)=>n+h.frames,0)}
function buildSegments(end,holds,cuts){
 const byFrame=new Map(holds.map(h=>[h.sourceFrame,h])),points=[...new Set([0,end,...byFrame.keys(),...cuts.flatMap(c=>[c.startFrame,c.endFrame])])].sort((a,b)=>a-b);let cursor=0,ci=0;const out=[];
 for(let i=0;i<points.length;i++){const a=points[i],h=byFrame.get(a);if(h?.frames){out.push({kind:'hold',startFrame:cursor,endFrame:cursor+h.frames,sourceFrame:Math.max(0,a-1),holdFrame:a,sceneId:h.sceneId});cursor+=h.frames}if(i===points.length-1)break;const b=points[i+1];while(ci<cuts.length&&cuts[ci].endFrame<=a)ci++;if(ci<cuts.length&&cuts[ci].startFrame<=a&&a<cuts[ci].endFrame)continue;out.push({kind:'source',startFrame:cursor,endFrame:cursor+b-a,sourceFrame:a});cursor+=b-a}
 return out;
}
function segments(d){return buildSegments(d.sourceDurationFrames,d.holds,d.cuts||EMPTY)}
function sourceFrame(f,holds,cuts=EMPTY){
 let entry=cache.get(holds);if(!entry||entry.cuts!==cuts){entry={cuts,spans:buildSegments(Infinity,holds,cuts)};cache.set(holds,entry)}
 let lo=0,hi=entry.spans.length-1;while(lo<=hi){const i=(lo+hi)>>1,s=entry.spans[i];if(f<s.startFrame)hi=i-1;else if(f>=s.endFrame)lo=i+1;else return s.sourceFrame+(s.kind==='source'?f-s.startFrame:0)}return 0;
}
function rippleCut(doc,start,end){
 const before=totalFrames(doc);if(!Number.isInteger(start)||!Number.isInteger(end)||start<0||start>=end||end>before||end-start>=before)throw Error('请选择有效裁剪区间，并至少保留一帧课程');
 const d=structuredClone(doc),cuts=[...(d.cuts||[])],removed=new Map();
 for(const s of segments(doc)){const a=Math.max(start,s.startFrame),b=Math.min(end,s.endFrame);if(a>=b)continue;if(s.kind==='hold')removed.set(s.holdFrame,b-a);else cuts.push({startFrame:s.sourceFrame+a-s.startFrame,endFrame:s.sourceFrame+b-s.startFrame})}
 const merged=[];for(const c of cuts.sort((a,b)=>a.startFrame-b.startFrame)){const last=merged.at(-1);if(last&&c.startFrame<=last.endFrame)last.endFrame=Math.max(last.endFrame,c.endFrame);else merged.push(c)}
 d.cuts=merged;d.holds=d.holds.map(h=>({...h,frames:h.frames-(removed.get(h.sourceFrame)||0)})).filter(h=>h.frames>0);
 const move=t=>t<=start?t:t>=end?t-(end-start):start;d.captions=d.captions.map(c=>({...c,startFrame:move(c.startFrame),endFrame:move(c.endFrame)})).filter(c=>c.endFrame>c.startFrame);return d;
}

// One immutable chapter table, measured on the edited display clock (seek-safe).
function chapterProgress(chapter,frame){const a=chapter.display_start,z=chapter.display_end;if(!Number.isFinite(a)||!Number.isFinite(z)||z<=a)throw Error('Invalid chapter display range');return Math.max(0,Math.min(1,(frame-a)/(z-a)))}
function chapterAt(doc,frame){return (doc.chapterTable||[]).find(c=>c.display_start<=frame&&frame<c.display_end)||null}

return {displayFrame,totalFrames,segments,sourceFrame,rippleCut,chapterProgress,chapterAt};})();
modules["activity"]=(()=>{
// Only real interactions, unsaved edits and playback hold the local service open.
// Workflow/job polling deliberately does not count as activity.
function startActivity(isDirty, isPlaying=()=>[...globalThis.document.querySelectorAll('video')].some(v=>!v.paused&&!v.ended),{document=globalThis.document,window=globalThis.window,fetch=globalThis.fetch,location=globalThis.location}={}) {
 if(location.protocol==='file:')return;
 const client=crypto.randomUUID();let last=0,held=false,failures=0;
 async function ping(active=false){
  const dirty=Boolean(isDirty()),playing=Boolean(isPlaying());
  if(!active&&!dirty&&!playing&&!held)return;
  held=dirty||playing;
  try{const r=await fetch('/api/activity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:client,dirty,playing,active})});failures=r.ok?0:failures+1;}
  catch{failures++;}
  if(failures>=2)clearInterval(timer);
 }
 function interaction(){const now=Date.now();if(now-last<10000)return;last=now;void ping(true);}
 for(const name of ['pointerdown','keydown','input'])document.addEventListener(name,interaction);
 const timer=setInterval(()=>{void ping();},30000);
 window.addEventListener('pagehide',()=>{
  clearInterval(timer);
  void fetch('/api/activity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:client,dirty:false,playing:false,active:false}),keepalive:true}).catch(()=>{});
 });
}

return {startActivity};})();
modules["production-progress"]=(()=>{
const ACTIVE=new Set(['queued','rendering','encoding','packaging']);
const activeJobs=jobs=>(jobs||[]).some(job=>ACTIVE.has(job.status));

// Keep failed attempts inspectable without presenting them as the current export.
function productionJobHistory(jobs=[],purpose='final') {
  const list=jobs.filter(job=>job.purpose===purpose);
  const current=list.at(-1)||null;
  const history=list.slice(0,-1).map((job,index)=>{
    const successor=job.status==='failed'?list.slice(index+1).find(next=>next.status==='complete'&&
      (!Number.isFinite(job.revision)||!Number.isFinite(next.revision)||next.revision>=job.revision)):null;
    return {...job,supersededBy:successor?{id:successor.id,revision:successor.revision}:null};
  }).reverse();
  return {current,history};
}

// Derive a recoverable next action only from persisted job facts.
function exportRecovery(jobs=[],stage='final',busy=false) {
  if(busy||activeJobs(jobs)||!['pilot','final'].includes(stage))return null;
  const {current}=productionJobHistory(jobs,stage);
  if(!current||!['failed','cancelled'].includes(current.status))return null;
  const title=stage==='pilot'?'小样':'成片';
  return {job_id:current.id,stage,label:'继续制作'+title,
    summary:(current.status==='failed'?title+'导出没完成':title+'制作已暂停'),
    detail:'已保存的成果会保留。继续时先检查能复用的文件，再补没做完的部分。'};
}

// Percentages describe a measured export job, never an estimate of AI thinking or remaining time.
function productionProgress({stage,busy=false,data={},jobs=[],native}) {
  const list=jobs.length?jobs:data.jobs||[],active=list.filter(job=>ACTIVE.has(job.status)).at(-1);
  if(active){
    const value=Number.isFinite(active.progress)?Math.max(0,Math.min(1,active.progress)):null;
    const title=active.purpose==='pilot'?'有声小样':'整课视频';
    return {label:active.status==='queued'?title+'已进入合成队列':title+'正在渲染与编码'+(value===null?'':' · '+Math.floor(value*100)+'%'),value,
      detail:'进度来自实际合成任务，完成后还会校验成品。',tone:'working'};
  }
  const {current:latest}=productionJobHistory(list,stage);
  if(latest?.status==='failed')return {label:'本次合成未完成',value:0,detail:String(latest.error||'').trim().split('\n').filter(Boolean).at(-1)?.slice(0,240)||'请在右侧查看原因，修正后继续制作。',tone:'failed'};
  if(latest?.status==='cancelled')return {label:'本次合成已暂停，过程文件保留',value:null,detail:String(latest.error||'制作或监督暂停了本次任务；解除暂停后重新制作当前版本。'),tone:'waiting'};
  if(data.release_status?.state==='acceptance_blocked')return {label:'候选保留 · 当前验收受阻',value:null,
    detail:(data.release_status.errors||[]).map(e=>(e.code?e.code+'：':'')+e.message).slice(0,5).join('；')||'当前版本必检证据尚未齐备。',tone:'waiting'};
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.required&&!data.production_preferences.storyboard_current)
    return {label:data.production_preferences.ready?'制作偏好已修改，等待更新对应成果':'待选择课程制作偏好',value:0,detail:'已有视频和历史记录保留；更新相关分镜与音视频后再登记当前结果。',tone:'waiting'};
  if(latest?.status==='complete'&&latest.registration_status==='held')return {label:'候选已生成 · 验收受阻',value:null,detail:'编码完成。当前缺项：'+(latest.contract_pending?.errors||[]).map(e=>e.code||e.message).slice(0,5).join('、')+'。候选可查看，尚未正式交付。',tone:'waiting'};
  const finalGate=data.gates?.find(g=>g.id==='final'),deliveredAt=Date.parse(finalGate?.receipt?.at||'');
  if(finalGate?.status==='delivered'&&Number.isFinite(deliveredAt)&&!busy&&!data.editor?.changed&&list.at(-1)?.status!=='failed'&&(!native?.issue||native.issue.at<deliveredAt))return {label:'整课制作与登记已完成',value:1,detail:'当前成品已通过制作端检查；历史失败保留在折叠记录中，不代表当前制作失败。',tone:'done'};
  const completedAt=latest?.completed_at|| (latest?.id&&native?.last_export?.job_id===latest.id?native.last_export.at:0);
  if(latest?.status==='complete'&&completedAt&&(!native?.issue||native.issue.at<completedAt)&&!data.editor?.changed&&data.gates?.find(g=>g.id===stage)?.status!=='stale')return {label:'候选编码完成 · 待成品审阅',value:null,detail:'当前候选可查看。正式交付与用户验收分别记录。',tone:'waiting'};
  if(native?.available){
    const issue=native.issue,current=native.current;
    if(issue)return {label:issue.label+(issue.count>1?'连续失败 '+issue.count+' 次':'失败')+(native.status==='stopped'?' · 已停止':''),value:0,
      detail:'失败步骤尚未通过，已有成果保留。'+(busy?'AI 仍在执行，请查看下方具体步骤。':'修复后可从当前阶段继续。'),tone:'failed'};
    if(current)return {label:current.label,value:null,detail:(current.subject?current.subject+' · ':'')+'已执行 '+Math.max(0,Math.floor((Date.now()-current.started_at)/1000))+' 秒。',tone:'working'};
    if(busy&&native.waiting_since)return {label:'等待模型安排下一步',value:null,detail:'本次等待 '+Math.max(0,Math.floor((Date.now()-native.waiting_since)/1000))+' 秒；下方保留已完成步骤。',tone:'working'};
    if(native.status==='stopped')return {label:'本轮制作已停止',value:0,detail:'已保存内容保留，可以核对最近步骤后继续。',tone:'waiting'};
  }
  if(busy)return {label:'AI 正在准备课程内容与素材',value:null,detail:latest?.status==='complete'?'视频已合成，AI 正在检查并整理当前结果。':'当前环节没有可准确核算的百分比；合成开始后自动显示实际进度。',tone:'working'};
  const gate=data.gates?.find(g=>g.id===stage);
  if(gate?.status==='stale'||data.editor?.changed&&['script','storyboard','pilot','final'].includes(stage))return {label:'内容已修改，等待更新对应成果',value:0,detail:'保存编辑与确认推进分别处理。',tone:'waiting'};
  if(stage==='sources'&&data.sources?.length)return {label:'已加入 '+data.sources.length+' 份原始资料',value:1,detail:'可核对原件及内容取舍。',tone:'done'};
  if(stage==='outline'&&data.plan?.units?.length)return {label:'已保存 '+data.plan.units.length+' 个章节的大纲',value:1,detail:'生成完成，内容仍由你审阅确认。',tone:'done'};
  if(stage==='script'&&data.editor?.text?.trim())return {label:'分章逐字稿已保存',value:1,detail:'可以手改、选段修改，再确认进入下一步。',tone:'done'};
  if(stage==='storyboard'&&data.storyboard?.segments?.length)return {label:'已保存 '+data.storyboard.segments.length+' 个片段的分镜方案',value:1,detail:gate?.status==='confirmed'?'分镜已确认。':'请选择方案并审阅确认。',tone:'done'};
  if(stage==='pilot'&&gate?.ready)return {label:'三段有声小样已就绪',value:1,detail:gate.status==='confirmed'?'当前小样已确认。':'请播放审阅，确认后再制作整课。',tone:'done'};
  if(stage==='final'&&gate?.status==='delivered')return {label:'整课制作与登记已完成',value:1,detail:'可播放检查并保存当前成品。',tone:'done'};
  if(latest?.status==='complete')return {label:'视频合成已完成 · 100%',value:1,detail:'制作端检查或登记尚待完成，不代表内容已获确认。',tone:'waiting'};
  return {label:'本阶段成果尚未生成',value:0,detail:'前置确认完成后，可以继续制作。',tone:'waiting'};
}

return {activeJobs,productionJobHistory,exportRecovery,productionProgress};})();
modules["production-preferences"]=(()=>{
const OPTIONS={
  customer:[['new','按本课设计新顾客（推荐）','共用可动方法，每课按情境换发型、服装与配色'],['V01','使用短侧分发顾客','眼镜、灰色便装外套；同风格可动人物'],['V02','使用齐肩短发顾客','棕红短发、浅紫圆领上衣；同风格可动人物'],['V03','使用成熟短发顾客','灰鬓短发、米色衬衫；同风格可动人物'],['none','不需要顾客出镜','本课用其他方式讲解']],
  flower_text:[['key-points','适量重点花字（推荐）','突出行动、条件和边界，普通叙述保持简洁'],['minimal','只强调少量关键条件','减少视觉提示'],['off','不加花字','保留正常标题、正文与字幕']],
  sound_effects:[['native','适量提示音（推荐）','沿用已经确定的“叮”和“嘟咚”'],['off','不加提示音','保留正常配音与品牌片头片尾']],
};
const TITLES={customer:'顾客采用什么形象？',flower_text:'重点内容怎样强调？',sound_effects:'要加提示音效吗？'};
const missingProductionChoices=value=>Object.keys(OPTIONS).filter(key=>!OPTIONS[key].some(([id])=>id===value?.choices?.[key]));
function productionPreferenceSummary(value){return Object.keys(OPTIONS).map(key=>({customer:'顾客',flower_text:'花字',sound_effects:'音效'})[key]+'：'+(OPTIONS[key].find(([id])=>id===value?.choices?.[key])?.[1]||'尚未选择')).join('；');}

function createProductionPreferences({getValue,saveChoice,uploadReference,onError,document=globalThis.document,window=globalThis.window}){
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

return {missingProductionChoices,productionPreferenceSummary,createProductionPreferences};})();
modules["source-coverage"]=(()=>{
// Source comparison belongs to the producer and explicit user confirmation.
function sourceCoverageDeclaration(coverage,checked){
  if(!coverage?.required||coverage.confirmed)return undefined;
  if(!checked||!coverage.current||!coverage.report_sha256)throw Error('请先查看当前原件对照，明确确认取舍与新增内容。');
  return {report_sha256:coverage.report_sha256,evidence:'用户明确勾选：已对照当前原件与逐字稿，确认报告中的保留、合并、舍弃及新增内容和理由',source:'workbench-explicit-click'};
}
function createSourceCoveragePanel({getData,action,host,onError,isBusy=()=>false,readOnly=false,document=globalThis.document}){
  const el=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
  let dialog,sending=false;
  const launch=el('button','原件对照');launch.type='button';launch.id='source-coverage-open';(document.getElementById('studio-tools-content')||document.querySelector('header')).append(launch);
  launch.onclick=()=>open();
  function button(text,callback){const node=el('button',text);node.type='button';node.disabled=sending;node.onclick=()=>void Promise.resolve().then(callback).catch(onError);return node;}
  function paint(){
    const coverage=getData()?.source_coverage||{},report=coverage.report||{},stats=coverage.statistics||{};
    dialog.replaceChildren();const head=el('div',undefined,'row');head.append(el('h2','原始资料与当前逐字稿对照'),button('关闭',()=>dialog.close()));dialog.append(head);
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
    dialog.append(el('p','本表由制作端对照原件，独立学员盲审仍只看当前成品。关闭、预选或制作委托均不构成人工确认。逐字稿及原件对照可在右侧问答一起确认。','meta'));
    if(readOnly)return;
    const controls=el('div',undefined,'review-actions');const generate=button('请AI生成／更新当前对照',async()=>{if(sending||isBusy())throw Error('请等待当前保存或制作结束。');sending=true;try{await host('source-coverage',{});dialog.close();}finally{sending=false;}});generate.disabled=sending||isBusy();controls.append(generate);
    const confirm=button('我已对照原件，确认以上取舍与新增',async()=>{if(sending||isBusy())throw Error('请等待当前保存或制作结束。');const declaration=sourceCoverageDeclaration(coverage,true);if(!declaration)return; sending=true;try{await action('source-coverage-confirm',declaration);paint();}finally{sending=false;}});confirm.disabled=sending||isBusy()||!coverage.required||!coverage.current||coverage.confirmed;controls.append(confirm);dialog.append(controls);
  }
  function open(){if(!dialog){dialog=el('dialog',undefined,'ai-review-dialog source-coverage-dialog');dialog.setAttribute('aria-label','原件与逐字稿对照');document.body.append(dialog);}paint();if(!dialog.open)dialog.showModal();}
  function sync(){const value=getData()?.source_coverage;launch.textContent=value?.required&&!value.confirmed?'原件对照 · 待确认':'原件对照';if(dialog?.open)paint();}
  return {open,sync};
}

return {sourceCoverageDeclaration,createSourceCoveragePanel};})();
modules["review-panel"]=(()=>{
// The durable backend owns every request, budget, report and approval.
const {sourceCoverageDeclaration}=modules["source-coverage"];
const RUNNING=new Set(['queued','checking','repairing','rendering','rechecking']);
const labels={script:'教学内容与讲稿',storyboard:'全课分镜与画面节奏',pilot:'实际有声小样',final:'最终交付文件'};
const stages=['script','storyboard','pilot','final'];
const pendingDecision=node=>node?.stage==='storyboard'?!node.passed:!node?.user_confirmed;
const requiresUserAudio=(review,stage)=>['pilot','final'].includes(stage)&&review?.policy?.review_arrangement?.mode==='visual_ai_user_audio';
const usesProducerAudio=(review,stage)=>['pilot','final'].includes(stage)&&review?.policy?.review_arrangement?.mode==='visual_ai_producer_audio';
function audioBinding(node){
  const audio=node?.user_audio_review,hashes=audio?.artifact_sha256s,artifacts=audio?.artifacts;
  if(!Array.isArray(hashes)||!hashes.length||!Array.isArray(artifacts)||artifacts.length!==hashes.length)return null;
  if(!artifacts.every((item,i)=>/^[a-f0-9]{64}$/.test(hashes[i])&&item.sha256===hashes[i]&&item.start_seconds===0&&Number.isFinite(item.end_seconds)&&item.end_seconds>0))return null;
  return {artifact_sha256s:[...hashes],artifacts:artifacts.map(({sha256,start_seconds,end_seconds})=>({sha256,start_seconds,end_seconds})),coverage:'all_stage_videos'};
}
function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
function createReviewPanel({getData,getStage,host,action,save,refresh,onApproved,onState,readOnly=false,onError,isBusy,mediaURL,openSourceCoverage,document=globalThis.document,window=globalThis.window}){
  let state,timer,reading=false,closed=false,dialog,selected,input,draftTimer,lastFocus,sending=false,audioCheck,audioChoice,arrangementDialog,coverageCheck,coverageChoice;
  const shown=new Set();
  const refreshed=new Set();
  const draftKey=node=>'kgxc-review-input:'+String(state?.course_id||getData().course_path||getData().title)+':'+node.stage+':'+node.run.id;
  function localDraft(node){try{return localStorage.getItem(draftKey(node));}catch{return null;}}
  const launch=el('button','检查记录与问题清单');launch.id='ai-review-open';launch.type='button';launch.disabled=true;
  (document.getElementById('studio-tools-content')||document.querySelector('header')).append(launch);
  const arrangementLaunch=el('button','审阅分工');arrangementLaunch.id='review-arrangement-open';arrangementLaunch.type='button';arrangementLaunch.onclick=openArrangement;
  if(!readOnly)launch.before(arrangementLaunch);
  const progress=el('section',undefined,'ai-review-progress');progress.hidden=true;
  document.getElementById('production-progress').after(progress);
  launch.onclick=()=>{const candidate=choose();if(candidate?.run?.id)open(candidate);else if(!readOnly)void startInitial(candidate).catch(onError);};
  function choose(){return state?.nodes[getStage()]||stages.map(s=>state?.nodes[s]).find(n=>n?.run?.id&&pendingDecision(n))||state?.nodes.script;}
  function audioKey(node){return JSON.stringify([node.stage,node.run.id,node.run.fingerprint,node.fingerprint,state?.policy?.review_arrangement?.mode,audioBinding(node)]);}
  function openArrangement(){
    if(!arrangementDialog){arrangementDialog=el('dialog',undefined,'ai-review-dialog review-arrangement');arrangementDialog.setAttribute('aria-label','审阅分工');document.body.append(arrangementDialog);}
    arrangementDialog.replaceChildren(el('h2','审阅分工'),el('p','分工选择只安排本课审阅职责，不代表任何视频已听审、声音已通过或内容已确认。'));
    const label=el('label','本课审阅安排'),select=el('select');select.setAttribute('aria-label','本课审阅安排');
    for(const [value,text] of [['default_full_av','AI 完整视听审阅（沿用默认能力要求）'],['visual_ai_user_audio','由我听音轨，AI审文字与画面'],['visual_ai_producer_audio','配音免人工审核，由制作端自动技术检查']]){const option=el('option',text);option.value=value;select.append(option);}
    select.value=state?.policy?.review_arrangement?.mode||'default_full_av';label.append(select);arrangementDialog.append(label,el('p','选择用户听审时，需完整播放当前全部视频后声明；选择配音免人工审核时，无需逐句试听或音频审批。自动技术检查不等于完整听审，声音自然度及连续音画配合未验证时继续保留关键未知，内容与画面确认仍按原安排。','meta'));
    const controls=el('div',undefined,'review-actions');controls.append(makeButton('取消，不保存分工',()=>arrangementDialog.close()),makeButton('保存审阅分工',async()=>{
      if(sending||isBusy())throw Error('请等待当前检查、制作或保存结束，再调整审阅分工。');
      sending=true;try{await action('review-arrangement',{mode:select.value,evidence:'用户在工作台明确选择并保存审阅分工：'+select.selectedOptions[0].textContent,source:{kind:'ui',id:crypto.randomUUID()}});state=getData().ai_review;audioChoice=null;arrangementDialog.close();}finally{sending=false;}render();
    },true));arrangementDialog.append(controls);arrangementDialog.showModal();
  }
  function checkList(root,items){
    for(const item of items){const row=el('li');row.append(el('strong',item.verdict+' · '+item.label),el('p',item.reason));if(item.evidence?.length){const detail=el('details');detail.append(el('summary','证据与定位'),el('pre',JSON.stringify(item.evidence,null,2)));row.append(detail);}root.append(row);}
  }
  function render(){
    const node=choose(),active=stages.map(s=>state?.nodes[s]).find(n=>RUNNING.has(n?.status));
    const pending=stages.filter(s=>state?.nodes[s]?.run?.id&&pendingDecision(state.nodes[s]));
    launch.textContent=state?.hold?.held?'检查记录 · 课程已暂停':active?'查看检查进度':'检查记录与问题清单';
    launch.disabled=!node?.run?.id; // Internal review creation belongs to the workflow, not a user toolbar.
    progress.hidden=!active;progress.replaceChildren();
    if(active){progress.append(el('strong',labels[active.stage]+' · '+(active.run.events?.at(-1)?.text||'检查中')),el('p','累计 '+Math.floor(active.elapsed_ms/1000)+' 秒；当前未返回的项目保持检查中。'));
      const details=el('details');details.append(el('summary','查看检查、返修与耗时'),el('p','当前整体验收范围：'+(active.run.checklist||[]).map(c=>c.label).join('、')+'。逐项新结论尚未返回时不标记完成。'),el('pre',(active.run.events||[]).map(e=>e.at+' '+e.text).join('\n')));
      if(active.run.repaired?.length)details.append(el('p','已完成局部修改，正在复核：'+active.run.repaired.map(c=>c.path+' · '+c.reason).join('；')));progress.append(details);}
    if(dialog?.open&&selected){const latest=state.nodes[selected.stage];
      if(latest?.run?.id===selected.run?.id){selected=latest;paintDialog(false);}
      else{
        // A newer automatic round may start while an old summary is open.
        // Retain the old input without overwriting the newer round's draft.
        clearTimeout(draftTimer);const old=selected,text=input?.value||'';
        if(!readOnly)void host('review',{review_action:'draft',stage:old.stage,run_id:old.run.id,text}).catch(onError);
        dialog.close();selected=latest;input=null;
      }
    }
    if(readOnly){onState?.();return;}
    for(const stage of stages){const n=state?.nodes[stage];if(stage==='storyboard'||!n?.run?.id||RUNNING.has(n.status)||n.user_confirmed||n.run.dismissed_at||shown.has(n.run.id))continue;
      if(!dialog?.open){shown.add(n.run.id);open(n);}break;}
  }
  function open(node){
    if(!node?.run?.id){if(!readOnly)void startInitial(node).catch(onError);return;}
    if(!dialog){dialog=el('dialog',undefined,'ai-review-dialog');dialog.setAttribute('aria-labelledby','ai-review-title');document.body.append(dialog);
      dialog.addEventListener('cancel',event=>{event.preventDefault();void dismiss();});}
    selected=node;audioChoice=null;coverageChoice=null;lastFocus=document.activeElement;paintDialog(true);if(!dialog.open)dialog.showModal();
  }
  async function persistDraft(){if(!selected||!input)return;clearTimeout(draftTimer);await host('review',{review_action:'draft',stage:selected.stage,run_id:selected.run.id,text:input.value});}
  async function dismiss(){if(readOnly){dialog.close();lastFocus?.focus?.();return;}if(sending)return;try{await persistDraft();await host('review',{review_action:'dismiss',stage:selected.stage,run_id:selected.run.id});audioChoice=null;dialog.close();lastFocus?.focus?.();}catch(error){onError(error);}}
  function makeButton(label,handler,primary=false){const b=el('button',label,primary?'primary':undefined);b.type='button';b.disabled=sending;b.onclick=()=>void Promise.resolve(handler()).catch(onError);return b;}
  function paintDialog(reset){
    const node=selected,run=node.run,report=run.report||{},draft=reset?(localDraft(node)??node.draft):input?.value??node.draft,userAudio=requiresUserAudio(state,node.stage),producerAudio=usesProducerAudio(state,node.stage),binding=userAudio?audioBinding(node):null;
    const key=userAudio?audioKey(node):null;if(reset||audioChoice?.key!==key)audioChoice={key,checked:false};
    const focused=document.activeElement===input,start=input?.selectionStart,end=input?.selectionEnd;
    dialog.replaceChildren();const head=el('div',undefined,'row');head.append(el('h2',getData().title+' · '+labels[node.stage]));head.firstChild.id='ai-review-title';head.append(makeButton(readOnly?'关闭记录':'关闭，稍后处理',dismiss));dialog.append(head);
    dialog.append(el('p','每阶段当前选定方案仅一次盲审；问题一次汇总，后续集中修复并按固定清单验收。未解决项保持待处理。','meta'));
    dialog.append(el('p','审阅版本 '+run.id.slice(0,8)+' · 本轮输入 '+run.fingerprint.slice(0,12)+(run.fingerprint!==node.fingerprint?' · 当前输入 '+node.fingerprint.slice(0,12):''),'meta'));
    if(state?.hold?.held)dialog.append(el('p','课程审阅已暂停：'+state.hold.reason,'review-blocked'));
    dialog.append(el('p',node.status==='stale'?'内容已修改，待以当前证据核验固定清单；不自动增加盲审':node.stage==='storyboard'&&node.passed?'分镜当前清单验收通过，沿用已有选择与制作委托':node.user_confirmed?(userAudio?'AI文字与画面检查通过；当前全部媒体的用户听审与内容确认已记录，尚未据此宣称正式交付':'AI审阅已通过；用户已确认，尚未据此宣称正式交付'):RUNNING.has(node.status)?'本轮仍在检查或修复，请稍候':node.passed?(userAudio?'AI文字与画面审阅通过 · 待你完整听审并确认':'AI审阅通过 · 待你确认'):'仍有阻塞项 · 待处理', 'review-verdict'));
    if(userAudio){
      const scope=el('section',undefined,'review-audio-scope');scope.append(el('h3','文字与画面由 AI 检查，音轨由你听审'),el('p','AI检查文字、静帧与有时间定位的画面序列；画面序列不等于连续播放。音轨和音画配合需由你完整播放当前全部视频后确认。'));
      scope.append(el('p','用户听审：'+({confirmed:'当前全部视频已实际听审',stale:'先前听审对应旧媒体，当前版本待听审',issues_reported:'已记录声音问题，当前版本未确认',pending:'待完整播放当前全部视频'}[node.user_audio_review?.status]||'待取得当前媒体范围'),'review-verdict'));
      if(binding){const files=el('ul',undefined,'review-media-bindings');binding.artifacts.forEach((item,i)=>{const row=el('li','视频 '+(i+1)+' · '+item.start_seconds+'—'+item.end_seconds+' 秒 · SHA-256 '+item.sha256);const file=getData().artifacts?.[node.stage]?.find(f=>f.sha256===item.sha256&&f.available!==false);if(file&&mediaURL){const link=el('a','打开这一版完整视频');link.href=mediaURL(file.path);link.target='_blank';link.rel='noopener';row.append(' ',link);}files.append(row);});scope.append(files);}else scope.append(el('p','尚未取得当前全部视频的完整 SHA 与时长范围，不能作听审声明。','review-blocked'));
      dialog.append(scope);
    }
    if(producerAudio){
      const scope=el('section',undefined,'review-audio-scope');scope.append(el('h3','配音免人工审核，由制作端自动技术检查'),el('p','无需你逐句试听或审核配音。AI只审当前文字、实际帧及其时间顺序和技术事实；自动技术检查绑定当前视频字节。'));
      scope.append(el('p','未执行连续听审：声音自然度、残音、末句及连续音画配合仍未验证；关键未知继续阻断正式放行，内容与画面确认按原安排。','review-verdict'));
      const media=report.inspection?.media||[];if(media.length){const files=el('ul');for(const item of media)files.append(el('li','视频 SHA-256 '+item.sha256+' · 自动音轨技术检查：'+({passed:'通过（仅技术范围）',failed:'发现技术问题',unverified:'未完成'}[item.audio_technical?.status]||'尚未完成')));scope.append(files);}
      dialog.append(scope);
    }
    if(report.summary)dialog.append(el('p',report.summary));if(node.reason)dialog.append(el('p',node.reason,'review-blocked'));
    if(report.learner){const learner=report.learner;dialog.append(el('h3',node.review_cycle?.producer_only?'首次盲审的理解（修复结果见当前清单）':'独立学员的理解'));
      for(const [label,value] of [['内容是什么',learner.about],['讲了什么',learner.what_it_said],['学到了什么',learner.learned],['仍不明白',learner.confusions]])dialog.append(el('p',label+'：'+(Array.isArray(value)?value.join('；'):value||'尚未返回')));}
    const ledger=node.issue_ledger||run.issue_ledger||[];
    if(ledger.length){dialog.append(el('h3','固定问题清单与当前验收'));const issues=el('ul',undefined,'review-items');
      for(const issue of ledger){const row=el('li');row.append(el('strong',issue.id+' · '+({resolved:'已解决',unresolved:'未解决',open:'待验收',not_applicable:'不适用'}[issue.status]||issue.status||'待验收')+' · '+(issue.label||'')));
        row.append(el('p',issue.learning_impact||''),el('p','验收条件：'+(issue.acceptance_condition||'保留原问题依据，待补齐可观察条件')));
        if(issue.acceptance_reason)row.append(el('p',issue.acceptance_reason));
        if(issue.acceptance_evidence?.length){const detail=el('details');detail.append(el('summary','当前验收证据'),el('pre',JSON.stringify(issue.acceptance_evidence,null,2)));row.append(detail);}issues.append(row);}dialog.append(issues);}
    if(run.repaired?.length){dialog.append(el('h3','本轮已经修复'));const list=el('ul');for(const change of run.repaired)list.append(el('li',change.reason+'（'+change.path+'）'));dialog.append(list);}
    const unresolved=(report.items||[]).filter(i=>!['通过','不适用'].includes(i.verdict)&&!(userAudio&&i.responsibility==='user_audio'&&i.verdict==='待用户听审'));
    dialog.append(el('h3',userAudio?'AI职责范围内剩余问题与无法验证项':'剩余问题与无法验证项'));const list=el('ul',undefined,'review-items');checkList(list,unresolved);if(!unresolved.length)list.append(el('li',node.passed?(userAudio?'AI文字与画面范围内无未解决的必检项；音轨仍按用户听审状态处理。':'无未解决的必检项'):'本轮尚未获得完整有效的审阅结果'));dialog.append(list);
    if(report.findings?.length){if(ledger.length)dialog.append(el('h3','首次盲审发现（当前结果见固定清单）'));const findings=el('ul',undefined,'review-items');for(const item of report.findings){const row=el('li');row.append(el('strong',(item.severity?item.severity+' · ':'')+item.problem));if(item.evidence?.length){const details=el('details');details.append(el('summary','问题定位'),el('pre',JSON.stringify(item.evidence,null,2)));row.append(details);}findings.append(row);}dialog.append(findings);}
    if(report.next_step)dialog.append(el('p','AI建议：'+report.next_step));
    const coverage=getData().source_coverage,coverageRequired=node.stage==='script'&&coverage?.required&&!coverage.confirmed;
    const coverageKey=JSON.stringify([coverage?.report_sha256,coverage?.script_sha256,coverage?.sources_sha256,coverage?.current]);
    if(reset||coverageChoice?.key!==coverageKey)coverageChoice={key:coverageKey,checked:false};coverageCheck=null;
    if(coverageRequired){const section=el('section',undefined,'review-audio-scope');section.append(el('h3','原件取舍与新增内容需要人工确认'),el('p','覆盖率按原始业务要点统计，关键规则单列。请查看原件对照后，在本次逐字稿确认中一并提交；不增加盲审。'));
      if(openSourceCoverage)section.append(makeButton('查看原件与逐字稿对照',openSourceCoverage));
      if(readOnly){section.append(el('p','只读对照。请在右侧问答确认当前范围。','meta'));dialog.append(section);}else{
      const label=el('label',undefined,'review-audio-declaration');coverageCheck=el('input');coverageCheck.type='checkbox';coverageCheck.checked=!!coverageChoice.checked;coverageCheck.disabled=!coverage.current||sending||RUNNING.has(node.status)||!!state?.hold?.held;
      const text='已对照当前原件与讲稿，确认保留、合并、舍弃及新增内容和理由';coverageCheck.setAttribute('aria-label',text);label.append(coverageCheck,el('span',text));section.append(label);
      if(!coverage.current)section.append(el('p','尚无与当前原件和稿件一致的完整对照报告，暂不能确认。','review-blocked'));dialog.append(section);}}
    const usage=node.usage||{},tokens=Number.isFinite(usage.totalTokens)?usage.totalTokens:null;
    const unlimited=(state?.policy?.unlimited_counts??node.policy?.unlimited_counts)===true;
    const counts=unlimited?'本轮调用/返修次数暂不限，累计'+node.calls+'调用/'+node.repairs+'返修':'自动返修 '+node.repairs+'/'+node.policy.max_repairs+' 轮 · 调用预算 '+node.calls+'/'+node.policy.max_calls+' 次';
    dialog.append(el('p','累计耗时 '+Math.floor(node.elapsed_ms/1000)+' 秒 · '+counts+' · '+(tokens===null?'用量尚未返回':tokens.toLocaleString()+' tokens')+'。'+(unlimited?'累计调用次数':'预算次数')+'包含已预留尝试；实际推理与用量以明细为准。账户额度比例与费用未由宿主提供。','meta'));
    const evidence=el('details');evidence.append(el('summary','详细验收清单、检查范围与历史证据'));const all=el('ul',undefined,'review-items');checkList(all,report.items||[]);evidence.append(all,el('p','实际检查方法：'+(report.methods||[]).join('、')),el('pre',(report.limitations||[]).join('\n')));
    if(report.inspection)evidence.append(el('pre',JSON.stringify(report.inspection,null,2)));
    if(run.calls?.length){const calls=el('ul');for(const call of run.calls){const invoked=call.model_invoked===false?'模型未调用':call.model_invoked===true?'模型已调用':'调用状态按原记录核对';calls.append(el('li',(call.role||'历史审阅')+' · '+call.status+' · '+(call.execution_phase||'原记录')+' · '+invoked+' · '+(Number.isFinite(call.usage?.totalTokens)?call.usage.totalTokens+' tokens':'用量未返回')));}evidence.append(el('h3','调用与预留明细'),calls);}
    if(report.agent_audit)evidence.append(el('h3','独立审阅身份与只读范围'),el('pre',JSON.stringify(report.agent_audit,null,2)));
    if(report.producer_qa)evidence.append(el('h3','制作端来源核验'),el('pre',JSON.stringify(report.producer_qa,null,2)));
    if(report.supervision)evidence.append(el('h3','监督侦探报告'),el('pre',JSON.stringify(report.supervision,null,2)));
    if(node.legacy)evidence.append(el('p','此为历史知情审阅，不能作为当前独立盲审通过。'));
    if(run.events?.length)evidence.append(el('pre',run.events.map(e=>e.at+' '+e.text).join('\n')));
    if(run.error_history?.length)evidence.append(el('pre',run.error_history.map(e=>e.at+' · '+e.reason+' · '+(e.resolved_by?'执行已由更新成果恢复（'+e.resolution_scope+' / '+e.resolved_by.slice(0,12)+'）':'尚未恢复')).join('\n')));
    if(node.history.length){const history=el('details');history.append(el('summary','历史审阅与失败记录'),el('pre',node.history.map(h=>h.id.slice(0,8)+' · '+h.status+(h.reason?' · '+h.reason:'')+(h.superseded_by?' · 已由 '+h.superseded_by.slice(0,8)+' 成功版本替代':' · 未标记为已解决')).join('\n')));evidence.append(history);}dialog.append(evidence);
    if(readOnly){if(pendingDecision(node)&&node.passed)dialog.append(el('p','需要你确认时，AI 会在右侧对话发起问答。','meta'));return;}
    const label=el('label','审阅重点或修改意见（自动保存）');input=el('textarea');input.value=draft||'';input.rows=3;input.setAttribute('aria-label','审阅重点或修改意见');input.oninput=()=>{try{localStorage.setItem(draftKey(node),input.value);}catch{}clearTimeout(draftTimer);draftTimer=setTimeout(()=>persistDraft().catch(onError),500);};label.append(input);dialog.append(label);
    audioCheck=null;if(userAudio&&!node.user_confirmed){const declaration=el('label',undefined,'review-audio-declaration');audioCheck=el('input');audioCheck.type='checkbox';audioCheck.checked=!!audioChoice.checked;audioCheck.disabled=!binding||sending||RUNNING.has(node.status)||node.status==='stale'||!!state?.hold?.held;
      const text='已完整播放当前全部'+(node.stage==='pilot'?'小样':'成片')+'，声音与音画配合无问题';audioCheck.setAttribute('aria-label',text);declaration.append(audioCheck,el('span',text));dialog.append(declaration,el('p','仅勾选后主动点击本次确认才记录声明；关闭、刷新、超时和选择分工均不代表听审通过。','meta'));}
    const controls=el('div',undefined,'review-actions');
    const confirm=makeButton(node.passed?(node.stage==='storyboard'?'按既有选择继续制作':'确认并进入下一阶段'):'集中修复并验收',()=>node.passed?approve():request('modify',input.value.trim()||'制作端按当前选定方案的固定问题清单集中修复，保留差异与当前证据，逐项定向验收，不重新盲审。'),true);
    const blocked=sending||RUNNING.has(node.status)||state?.hold?.held;
    const disableConfirm=()=>{confirm.disabled=blocked||node.status==='limit_reached'||(node.passed&&coverageRequired&&(!coverage.current||!coverageCheck?.checked))||(userAudio&&node.passed&&(!binding||node.status==='stale'||node.user_confirmed||!audioCheck?.checked));};disableConfirm();if(audioCheck)audioCheck.onchange=()=>{audioChoice={key,checked:audioCheck.checked};disableConfirm();};if(coverageCheck)coverageCheck.onchange=()=>{coverageChoice={key:coverageKey,checked:coverageCheck.checked};disableConfirm();};controls.append(confirm);
    const continueButton=makeButton(node.review_cycle?.blind_review_completed||node.run.blind_report?'继续清单验收':'开始一次盲审',()=>request('continue',input.value));continueButton.disabled=blocked;controls.append(continueButton);
    const modify=makeButton('按意见修改并验收',()=>{if(!input.value.trim())throw Error('请先填写修改意见。');return request('modify',input.value);});modify.disabled=blocked||node.status==='limit_reached';controls.append(modify);
    if(userAudio){const feedback=makeButton('保存声音问题，不确认',async()=>{if(!input.value.trim())throw Error('请先填写具体的声音或音画配合问题。');if(sending)return;sending=true;try{await persistDraft();await action('feedback',{stage:node.stage,time:0,text:input.value});state=getData().ai_review;audioChoice=null;}finally{sending=false;}paintDialog(false);dialog.append(el('p','声音问题已保存；尚未确认或进入下一阶段。','review-blocked'));});feedback.disabled=blocked;controls.append(feedback);}dialog.append(controls);
    if(node.status==='limit_reached'&&!state?.hold?.held){const extension=el('details');extension.append(el('summary','明确追加返修授权'),el('p','保留成果。只有主动点击下方按钮才追加本节点 1 轮定向返修和 2 次调用，不增加盲审次数；沿用当前模型和计费来源。'),makeButton('追加 1 轮返修与 2 次调用',async()=>{await action('review-extend',{stage:node.stage,repairs:1,calls:2,evidence:'用户在审阅窗口明确点击追加1轮返修与2次调用，仅限当前节点固定清单的定向修复和原有模型通道，不增加盲审次数'});await request('continue',input.value);}));dialog.append(extension);}
    if(focused){input.focus();input.setSelectionRange(start,end);}
  }
  async function request(mode,instruction){
    if(state?.hold?.held)throw Error('课程已暂停，请明确恢复后再审阅。');
    if(sending||isBusy())throw Error('请等待当前检查或制作结束，再开始新一轮。');
    sending=true;const stage=selected.stage;
    try{await save();await persistDraft();await host('review',{review_action:mode,stage,request_id:crypto.randomUUID(),instruction});dialog.close();await sync();}
    finally{sending=false;}
  }
  async function startInitial(node){
    if(sending)return;
    if(state?.hold?.held)throw Error('课程已暂停：'+state.hold.reason);
    await save();if(isBusy())throw Error('请等待当前制作或保存结束。');sending=true;
    try{await host('review',{review_action:'continue',stage:node?.stage||'script',request_id:crypto.randomUUID(),instruction:''});await sync();}
    finally{sending=false;}
  }
  async function approve(){
    if(sending)return;const stage=selected.stage,userAudio=requiresUserAudio(state,stage);let declaration;
    const sourceDeclaration=stage==='script'?sourceCoverageDeclaration(getData().source_coverage,!!coverageCheck?.checked&&!!coverageChoice?.checked):undefined;
    if(userAudio){const binding=audioBinding(selected);if(!binding||!audioCheck?.checked||!audioChoice?.checked||audioChoice.key!==audioKey(selected)||selected.status==='stale')throw Error('请完整播放当前全部视频，并明确勾选当前版本的听审声明。');declaration={...binding,listened_completely:true,audio_and_sync_ok:true,evidence:audioCheck.getAttribute('aria-label'),source:{kind:'ui',id:crypto.randomUUID()}};}
    sending=true;
    try{await save();await persistDraft();await action('review-approve',{stage,run_id:selected.run.id,...(declaration?{audio_declaration:declaration}:{}),...(sourceDeclaration?{source_coverage_declaration:sourceDeclaration}:{})});state=getData().ai_review;
      if(userAudio&&!state?.nodes?.[stage]?.user_confirmed)throw Error('本次未取得当前全部媒体的听审与内容确认，保持当前阶段。');
      audioChoice=null;dialog.close();await refresh();await onApproved(stage);}
    finally{sending=false;}
  }
  async function sync(){
    if(closed||reading||document.hidden)return;reading=true;
    try{const result=await host('review',{review_action:'sync',busy:isBusy()});state=result.review;
      const completed=stages.map(s=>state?.nodes?.[s]).filter(n=>n?.run?.completed_at);
      const completionKey=n=>JSON.stringify([n.run.id,n.run.completed_at,n.fingerprint,n.status,n.passed,n.user_confirmed]);
      if(completed.some(n=>!refreshed.has(completionKey(n)))){
        const didRefresh=await refresh();if(didRefresh!==false)for(const n of completed)refreshed.add(completionKey(n));
      }render();}
    finally{reading=false;clearTimeout(timer);if(!closed)timer=setTimeout(()=>sync().catch(onError),3000);}
  }
  window.addEventListener('pagehide',()=>{closed=true;clearTimeout(timer);clearTimeout(draftTimer);});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)void sync().catch(onError);});
  return {sync,open:()=>open(choose()),get state(){return state;}};
}

return {requiresUserAudio,usesProducerAudio,createReviewPanel};})();
modules["live-production"]=(()=>{
// Read-only display of producer-published files. Presence never constitutes acceptance.
function createLiveProduction({document,window,fetch,mediaURL}){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const root=el('section',null,'live-workspace'),head=el('div',null,'live-heading'),title=el('h2','制作现场'),status=el('span','正在读取产物','live-status');
  head.append(title,status);root.append(head);
  const layout=el('div',null,'live-layout'),visual=el('div',null,'live-visual'),audioPane=el('aside',null,'live-audio');layout.append(visual,audioPane);root.append(layout);
  const strip=el('div',null,'live-strip');strip.setAttribute('aria-label','已保存的制作产物');root.append(strip);
  let items=[],selected=null,selectedAudio=null,signature='',timer,reading=false,closed=false,started=false,visibleVersion='';
  const key=x=>x.id||x.path;
  function source(x){return mediaURL(x.path)+'&v='+encodeURIComponent(x.sha256||x.mtime||x.bytes||'');}
  function showVisual(item){
    selected=key(item);visibleVersion=JSON.stringify([item.path,item.mtime,item.sha256]);visual.replaceChildren();
    if(item.kind==='image'){const image=el('img');image.src=source(item);image.alt=item.label||'当前已保存画面';visual.append(image);}
    else{const video=el('video');video.controls=true;video.preload='metadata';video.src=source(item);video.setAttribute('aria-label',item.label||'当前已保存样段');visual.append(video);}
    const caption=el('div',null,'live-caption');caption.append(el('strong',item.label||item.path.split('/').at(-1)),el('span',item.current===false?'历史素材 · 非当前版本':item.kind==='image'?'画面已出 · 未验收':'样段已出 · 未验收'));visual.append(caption);
    const media=visual.querySelector('img,video');media.addEventListener('error',()=>{status.textContent='文件暂时无法读取，稍后自动重试';});
  }
  function showAudio(item){selectedAudio=key(item);const player=audioPane.querySelector('audio');player.src=source(item);audioPane.querySelector('.live-audio-title').textContent=item.label||'已保存音轨';}
  function paint(){
    const pictures=items.filter(x=>x.kind==='image'||x.kind==='video'),sounds=items.filter(x=>x.kind==='audio');
    if(!pictures.length){visual.replaceChildren();const empty=el('div',null,'live-empty');empty.append(el('span','◌'),el('h3','画面生成后，会出现在这里'),el('p','不必等整段视频合成完成。'));visual.append(empty);selected=null;}
    else{const item=pictures.find(x=>key(x)===selected)||pictures[0];if(selected!==key(item)||!visual.querySelector('img,video'))showVisual(item);else if(visibleVersion!==JSON.stringify([item.path,item.mtime,item.sha256])&&!visual.querySelector('.live-update')){const update=el('button','此画面有新版本 · 点击查看','live-update');update.onclick=()=>showVisual(item);visual.append(update);}}
    if(!audioPane.querySelector('audio')){audioPane.append(el('h3','配音'),el('p','等待音轨保存','live-audio-title'));const audio=el('audio');audio.controls=true;audio.preload='metadata';audio.setAttribute('aria-label','试听已保存配音');audio.addEventListener('error',()=>{audioPane.querySelector('.live-audio-title').textContent='此音轨暂时无法播放，请查看文件';});audioPane.append(audio,el('div',null,'live-audio-list'));}
    audioPane.querySelector('audio').hidden=!sounds.length;
    const audioList=audioPane.querySelector('.live-audio-list');audioList.replaceChildren();
    for(const item of sounds){const b=el('button',item.label||item.path.split('/').at(-1));b.setAttribute('aria-pressed',String(key(item)===selectedAudio));b.onclick=()=>{showAudio(item);paintAudioSelection();};audioList.append(b);}
    if(sounds.length&&!sounds.some(x=>key(x)===selectedAudio))showAudio(sounds[0]);
    if(!sounds.length)audioPane.querySelector('.live-audio-title').textContent='配音保存后即可试听';
    strip.replaceChildren();for(const item of pictures){const b=el('button',null,'live-thumb');b.setAttribute('aria-label',item.label||'查看已保存画面');b.setAttribute('aria-pressed',String(key(item)===selected));if(item.kind==='image'){const img=el('img');img.src=source(item);img.alt='';b.append(img);}else b.append(el('span','▶','live-video-symbol'));b.append(el('span',item.label||'样段'));b.onclick=()=>{showVisual(item);paint();};strip.append(b);}
    paintAudioSelection();
  }
  function paintAudioSelection(){for(const [i,b] of [...audioPane.querySelectorAll('.live-audio-list button')].entries())b.setAttribute('aria-pressed',String(key(items.filter(x=>x.kind==='audio')[i])===selectedAudio));}
  async function poll(){if(closed||reading)return;reading=true;try{const response=await fetch('/api/studio/live-media');if(!response.ok)throw Error('无法读取');const value=await response.json();const next=Array.isArray(value.items)?value.items:[];const nextSignature=JSON.stringify(next);if(nextSignature!==signature){signature=nextSignature;items=next;paint();}status.textContent=items.length?'已保存 '+items.length+' 项 · 自动更新':'等待制作端保存产物';}catch{status.textContent='产物连接中断 · 正在重试';}finally{reading=false;clearTimeout(timer);if(!closed)timer=setTimeout(poll,3000);}}
  window.addEventListener('pagehide',()=>{closed=true;clearTimeout(timer);});
  return {mount(target){target.append(root);if(!started){started=true;paint();void poll();}},dispose(){closed=true;clearTimeout(timer);}};
}

return {createLiveProduction};})();
modules["production-overview"]=(()=>{
const confirmationStages=['script','pilot','final'];
const confirmationNames={script:'逐字稿',pilot:'有声小样',final:'成片'};
const running=new Set(['queued','checking','repairing','rendering','rechecking','running']);
function confirmationStageStatus(data={},stage){
  const gate=(data.gates||[]).find(g=>g.id===stage),node=data.ai_review?.nodes?.[stage];
  if(gate?.status==='delivered')return {id:'delivered',text:'已交付'};
  if(node?.status==='stale'||gate?.status==='stale')return {id:'stale',text:'版本已变更'};
  if(node?.user_confirmed||!data.ai_review?.enabled&&gate?.status==='confirmed')return {id:'confirmed',text:'已确认'};
  if(data.ai_review?.hold?.held)return {id:'blocked',text:'已暂停'};
  const pending=(data.pending_confirmations||[]).find(x=>x.stage===stage);
  const display=data.confirmation_display;
  const current=pending&&display?.stage===stage&&display?.question_id===pending.id&&(!display.course_path||display.course_path===data.course_path)?display.status:null;
  if(current==='visible')return {id:'waiting',text:'请在右侧确认'};
  if(current==='failed'||current==='error')return {id:'retry',text:'问答未打开，可在右侧重试'};
  if(current==='deferred'||current==='skipped'||pending?.decision_status==='deferred')return {id:'paused',text:'已暂缓，可在右侧继续'};
  if(current==='changes_requested'||pending?.decision_status==='changes_requested')return {id:'changes',text:'已要求修改，可在右侧补充'};
  if(pending)return {id:'queued',text:'正在准备右侧问答'};
  if(running.has(node?.status))return {id:'checking',text:'AI 正在检查'};
  if(['limit_reached','failed'].includes(node?.status)||node?.run?.id&&node.status==='awaiting_confirmation'&&!node.passed||gate?.status==='blocked')return {id:'blocked',text:'待 AI 处理'};
  const hasCandidate=stage==='script'?!!data.editor?.text?.trim():!!data.artifacts?.[stage]?.some(file=>file.available===true&&/\.mp4$/i.test(file.path||''));
  if(gate?.ready||node?.passed||hasCandidate)return {id:'blocked',text:'已生成 · 尚未达到确认条件'};
  return {id:'pending',text:'未到确认节点'};
}
function compact(value,limit=240){
  return typeof value==='string'?value.trim().slice(0,limit):'';
}
function confirmationHistory(data={},stage){
  const explicit=Array.isArray(data.confirmation_records)?data.confirmation_records.filter(x=>x?.stage===stage&&x.id):[];
  if(explicit.length)return explicit.map(x=>({...x,label:compact(x.label)||confirmationNames[stage],evidence:compact(x.evidence)}));
  // Legacy, version-bound receipts only. Never treat a review pass or the existence of a video as consent.
  const receipt=data.ai_review?.nodes?.[stage]?.confirmation;
  if(!receipt||(!receipt.run_id&&!receipt.sha256)||!receipt.actor||(!receipt.artifact_hashes?.length&&!receipt.sha256))return [];
  return [{stage,id:receipt.run_id||receipt.sha256,status:'confirmed',at:receipt.at||receipt.confirmed_at||'',label:confirmationNames[stage],evidence:compact(receipt.evidence)||'已保留与对应内容版本绑定的确认记录'}];
}
// Read-only projection: never infer acceptance or source usage from file presence.
function overviewModel(data={},stage='pilot',state={}) {
  const gates=(data.gates||[]).map(g=>({id:g.id,status:g.status||'unknown'}));
  const review=data.ai_review?.nodes?.[stage];
  const evidence=review?.passed?'检查已通过':review?.status==='running'?'正在检查':'尚无通过记录';
  const points=data.source_coverage?.report?.points||[];
  return {gates,evidence,activity:state.label||'正在读取制作状态',
    materials:points.map(p=>({label:p.source_quote||p.id,status:({retained:'保留',merged:'合并使用',omitted:'未使用'})[p.disposition]||'待核对',reason:p.reason||'尚未登记理由'})),
    issue:data.release_status?.state==='acceptance_blocked'?(data.release_status.errors||[]).map(e=>e.message).join('；'):null};
}
function nextAction(data={},stage,state={}){
  const text={script:'查看当前讲稿',pilot:'完整看完三段有声小样',final:'查看当前成片'};
  if(data.confirmation_display?.editing_feedback)return {title:'正在填写修改意见',detail:'在右侧写清楚要改什么，再提交给 AI。',tone:'action',kicker:'当前'};
  const visible=data.confirmation_display?.stage;
  if(text[visible]&&confirmationStageStatus(data,visible).id==='waiting'){
    const tab={script:'逐字稿',pilot:'有声小样',final:'后期与成片'}[visible];
    const onPreview=visible===stage&&(visible!=='final'||state.phase!=='body');
    return {title:onPreview?'看完后确认':text[visible],detail:onPreview?'看完当前内容后，在右侧确认或提出修改。':'先到顶部「'+tab+'」查看，看完后在右侧确认。',tone:'action'};
  }
  const target=(data.pending_confirmations||[]).some(item=>item.stage===visible&&item.id===data.confirmation_display?.question_id)?visible:stage,status=confirmationStageStatus(data,target);
  if(['retry','paused','changes'].includes(status.id))return {title:status.text,detail:'已有成果会保留，不会自动确认。',tone:'waiting'};
  if(status.id==='queued')return {title:'正在准备右侧问答',detail:'现在不需要操作，问答打开后再查看。',tone:'waiting'};
  if(state.tone==='working')return {title:state.label||'AI 正在制作',detail:'现在不需要你操作。',tone:'working'};
  if(status.id==='checking')return {title:'AI 正在检查'+(confirmationNames[stage]||'当前成果'),detail:'检查通过后会打开右侧问答。',tone:'working'};
  if(state.recovery)return {title:state.label,detail:state.detail,tone:'waiting'};
  if(state.tone==='failed'||status.id==='blocked')return {title:'当前成果还不能确认',detail:state.detail||'查看下方作品；右侧问答尚未开启。',tone:'waiting'};
  if(stage==='sources')return {title:'加入制作资料',detail:'上传原文件或实拍照片，再查看素材的去向。',tone:'waiting'};
  return {title:state.label||'查看当前作品',detail:state.detail||'',tone:state.tone||'waiting'};
}
function createProductionOverview({document,onCoverage}) {
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const root=el('section',null,'production-overview');root.setAttribute('aria-label','制作提示');
  const head=el('div',null,'overview-now'),title=el('h2'),detail=el('p',null,'overview-next-detail'),kicker=el('span','状态','overview-next-kicker');head.append(kicker,title,detail);root.append(head);
  const archive=el('details',null,'overview-history');
  archive.append(el('summary','确认历史与检查记录'));
  const confirmations=el('section',null,'confirmation-strip');confirmations.setAttribute('aria-label','人工确认状态');
  const confirmationGrid=el('div',null,'confirmation-grid');confirmations.append(confirmationGrid);archive.append(confirmations);
  const details=el('details',null,'overview-details');details.append(el('summary','查看原件取舍及检查问题'));const records=el('div');details.append(records);archive.append(details);
  const views=new Map();
  for(const stage of confirmationStages){
    const card=el('section',null,'confirmation-card'),header=el('div',null,'confirmation-card-head');
    header.append(el('strong',confirmationNames[stage]));const badge=el('span',null,'confirmation-status');header.append(badge);card.append(header);
    const recordWrap=el('div',null,'confirmation-record-wrap'),recordToggle=el('button',null,'confirmation-record-toggle'),recordPanel=el('div',null,'confirmation-record-panel');
    const panelId='confirmation-record-'+stage;recordToggle.type='button';recordToggle.setAttribute('aria-controls',panelId);recordToggle.setAttribute('aria-expanded','false');recordToggle.setAttribute('aria-pressed','false');
    recordPanel.id=panelId;recordPanel.hidden=true;recordWrap.append(recordToggle,recordPanel);card.append(recordWrap);confirmationGrid.append(card);
    let hover=false,focused=false,pinned=false,suppressPreview=false;
    const paint=()=>{
      const shown=pinned||(!suppressPreview&&(hover||focused));
      recordPanel.hidden=!shown;recordToggle.setAttribute('aria-expanded',String(shown));recordToggle.setAttribute('aria-pressed',String(pinned));
    };
    recordWrap.addEventListener('pointerenter',()=>{hover=true;suppressPreview=false;paint();});
    recordWrap.addEventListener('pointerleave',()=>{hover=false;if(!focused)suppressPreview=false;paint();});
    recordWrap.addEventListener('focusin',()=>{focused=true;paint();});
    recordWrap.addEventListener('focusout',event=>{if(!recordWrap.contains(event.relatedTarget)){focused=false;if(!hover)suppressPreview=false;paint();}});
    recordToggle.addEventListener('click',()=>{pinned=!pinned;suppressPreview=!pinned;paint();});
    recordWrap.addEventListener('keydown',event=>{if(event.key==='Escape'){pinned=false;suppressPreview=true;paint();event.stopPropagation();}});
    views.set(stage,{card,badge,recordToggle,recordPanel});
  }
  function updateConfirmations(data){
    for(const [stage,{card,badge,recordToggle,recordPanel}] of views){
      const status=confirmationStageStatus(data,stage),history=confirmationHistory(data,stage);
      card.dataset.state=status.id;badge.textContent=status.text;recordToggle.textContent='确认记录'+(history.length?' · '+history.length:'');
      recordToggle.setAttribute('aria-label',confirmationNames[stage]+'确认记录，点击固定或取消固定');
      const rows=el('ul');
      for(const record of history){
        const state=({confirmed:'已确认',approved:'已确认',declined:'暂不确认',deferred:'稍后确认',changes_requested:'要求修改',revoked:'已失效',stale:'对应旧版本'})[record.status]||'已登记';
        const row=el('li');row.append(el('strong',state));
        const at=record.at?new Date(record.at):null;if(at&&!Number.isNaN(at.valueOf())){const t=el('time',at.toLocaleString());t.dateTime=at.toISOString();row.append(t);}
        const current=data.ai_review?.nodes?.[stage]?.fingerprint;
        if(/^[a-f0-9]{12,}$/i.test(record.fingerprint||'')){
          const historical=current&&current!==record.fingerprint;
          row.append(el('p',(historical?'旧版本 ':'版本 ')+record.fingerprint.slice(0,12)));
        }
        if(record.evidence)row.append(el('p',record.evidence));rows.append(row);
      }
      recordPanel.replaceChildren(history.length?rows:el('p','还没有可核实的确认记录。'));
    }
  }
  function update(data,stage,state){const m=overviewModel(data,stage,state),next=nextAction(data,stage,state);
    root.dataset.tone=next.tone;kicker.textContent=next.kicker||(next.tone==='action'?'下一步':'状态');title.textContent=next.title;detail.textContent=next.detail;
    updateConfirmations(data);
    records.replaceChildren();if(m.issue)records.append(el('p','待处理：'+m.issue,'overview-issue'));
    if(!m.materials.length)records.append(el('p','原件取舍尚未登记。'));
    for(const p of m.materials){const row=el('p');row.append(el('strong',p.status+' · '),el('span',p.label),el('small',p.reason));records.append(row);}
    const b=el('button','查看完整原件对照');b.onclick=onCoverage;records.append(b);
  }
  return {mount:container=>container.append(root),mountHistory:container=>container.append(archive),update};
}

const materialStatuses={
  used:{title:'已出现在视频',description:'已在当前视频中找到这个素材。'},
  unused:{title:'未入片',description:'已记录未放入视频。'},
  reference:{title:'已供讲稿参考',description:'已核对讲稿引用，是否入片尚未核实。'},
  unverified:{title:'还没核对',description:'已入库，尚未核实是否入片。'},
};
function relativeMaterialPath(path){
  if(typeof path!=='string'||!path||path.startsWith('/')||/^[a-z]+:/i.test(path)||path.includes('\\'))return false;
  const clean=path.replace(/^\.\.\/(?:inputs|delivery)\//,'');
  return clean.split('/').every(part=>part&&part!=='.'&&part!=='..');
}
function materialRows(library,sources=[]){
  const provided=Array.isArray(library)?library:[];
  const found=new Set(provided.map(item=>item?.source_id).filter(Boolean));
  const fallback=sources.filter(item=>item?.id&&!found.has(item.id)).map(item=>({id:item.id,source_id:item.id,title:item.title,path:item.location,available:item.available,kind:/\.(png|jpe?g|webp|gif|heic|avif|tiff?)$/i.test(item.location||'')?'image':'file'}));
  return [...provided,...fallback].filter(item=>item?.id).map(item=>{
    const source_points=Array.isArray(item.source_points)?item.source_points.filter(p=>p&&typeof p==='object'):[];
    const status=item.status==='unverified'&&item.kind==='file'&&source_points.some(p=>['retained','merged'].includes(p.disposition))?'reference':Object.hasOwn(materialStatuses,item.status)?item.status:'unverified';
    const placements=(Array.isArray(item.placements)?item.placements:[]).filter(p=>status==='used'&&['pilot','final','body'].includes(p?.stage)&&relativeMaterialPath(p.artifact_path)&&/^[a-f0-9]{64}$/i.test(p.artifact_sha256||'')&&Number.isFinite(p.start_seconds)&&p.start_seconds>=0&&Number.isFinite(p.end_seconds)&&p.end_seconds>p.start_seconds);
    return {...item,status,placements,path:relativeMaterialPath(item.path)?item.path:null,source_points};
  });
}

return {confirmationStageStatus,confirmationHistory,overviewModel,nextAction,createProductionOverview,materialStatuses,materialRows};})();
modules["studio"]=(()=>{
const {createProductionOverview,materialStatuses,materialRows}=modules["production-overview"];
const {createLiveProduction}=modules["live-production"];
const {paragraphAt,replaceSelection,previewDocument}=modules["script-editor-model"];
const {totalFrames,displayFrame}=modules["timeline"];
const {startActivity}=modules["activity"];
const {productionProgress,activeJobs,productionJobHistory,exportRecovery}=modules["production-progress"];
const {createProductionPreferences,productionPreferenceSummary}=modules["production-preferences"];
const {createReviewPanel,requiresUserAudio}=modules["review-panel"];
const {createSourceCoveragePanel}=modules["source-coverage"];

function mountStudio({document=globalThis.document,window=globalThis.window,location=globalThis.location,parent=window.parent,fetch=globalThis.fetch,Audio=globalThis.Audio,resourceBase='',native=false}={}){
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const stage=params.get('stage')||'outline',parentOrigin=params.get('parentOrigin');
const finalPhase=stage==='final'?(params.get('phase')==='body'?'body':'post'):null;
const titles={sources:'资料',outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课交付'};
let data,serial=0,savedSerial=0,saveTask,saveTimer,selectedUnit,selectedSegment,selectedSource,sourcePage=1,hostReady=false,aiBusy=false,selection;
let renderer,previewState,previewFrame=0,playing=false,playEpoch=0,previewTimer,pollTimer,closed=false;
let confirmationDisplay;
let progressJobs=[],progressReading=false,progressError='',nativeProduction,lastNativeIssue,computerExportAt=0;
const pending=new Map(),audio=new Audio();
const confirmationStages=new Set(['script','pilot','final']);
const reviews=createReviewPanel({readOnly:true,document,window,getData:()=>data,getStage:()=>stage,host,action,save,refresh,mediaURL:fileURL,
  openSourceCoverage:()=>sourceCoverage.open(),isBusy:()=>aiBusy||serial!==savedSerial||!!saveTask||activeJobs(progressJobs)||activeJobs(data?.jobs),onError:error=>notice(error.message,true),
  onState:()=>{if(data){primaryState();paintProgress();announce();}}});
const sourceCoverage=createSourceCoveragePanel({readOnly:true,document,getData:()=>data,action,host,onError:error=>notice(error.message,true),isBusy:()=>aiBusy||serial!==savedSerial||!!saveTask||activeJobs(progressJobs)||activeJobs(data?.jobs)});
const productionPreferences=createProductionPreferences({document,window,
  getValue:()=>data?.production_preferences,
  saveChoice:args=>action('production-choice',args),
  onError:error=>notice(error.message,true),
  uploadReference:async file=>{if(file.size>25*1024*1024)throw Error('参考图最大25MB。');const response=await fetch('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name)},body:file});const result=await response.json();if(!response.ok||result.error)throw Error(result.error||'参考图上传未完成');return result;},
});
function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(className)node.className=className;return node;}
function notice(text='',bad=false){$('notice').hidden=!text;$('notice').textContent=text;$('notice').setAttribute('role',bad?'alert':'status');}
function button(label,action,className){const b=el('button',label,className);b.onclick=()=>Promise.resolve(action()).catch(e=>notice(e.message,true));return b;}
function link(path,label){const a=el('a',label);a.href=fileURL(path);a.target='_blank';a.rel='noopener';return a;}
function resourceURL(path){return resourceBase+path;}
function fileURL(path){return resourceURL('/course-file?path=')+encodeURIComponent(path);}
function stamp(seconds){return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(Math.floor(seconds%60)).padStart(2,'0');}
function fullText(sections=data.sections){return sections.some(s=>s.body?.trim())?sections.map((s,i)=>'## '+(i+1)+'. '+s.title+'\n\n'+s.body.trim()).join('\n\n').trim():'';}
function section(){return data.sections.find(s=>s.unit_id===selectedUnit)||data.sections[0];}
function draftKey(){return 'kgxc-studio-draft:'+data.course_id+':'+stage;}
async function api(path,value,headers={}){const response=await fetch(path,value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(value)});const result=await response.json();if(!response.ok||result.error||result.ok===false)throw Error(result.error||'操作未完成');return result;}
function host(action,args={}){if(!hostReady)throw Error('请从 DSH 课程工作台内使用 AI。');const id=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('AI 连接尚未响应，请查看右侧对话。'));},120000);pending.set(id,{resolve,reject,timer});parent.postMessage({type:'kgxc-editor-request',id,action,course_path:data.course_path,...args},parentOrigin);});}
function announce(){if(parent===window||!parentOrigin)return;parent.postMessage({type:'kgxc-editor-ready'},parentOrigin);const waiting_decisions=(data.plan.decisions||[]).filter(d=>(d.gate||'outline')===(stage==='sources'?'outline':stage)&&!['confirmed','delegated'].includes(d.status)).map(d=>({id:d.id,question:d.question,options:d.options}));parent.postMessage({type:'kgxc-studio-state',course_path:data.course_path,stage,phase:finalPhase,revision:data.revision,gates:data.gates,ai_review:{nodes:Object.fromEntries(Object.entries((reviews.state||data.ai_review)?.nodes||{}).map(([key,value])=>[key,{passed:value.passed,user_confirmed:value.user_confirmed,status:value.status}]))},waiting_decisions,pending_confirmations:data.pending_confirmations||[],unsaved_edits:serial!==savedSerial,has_sources:!!data.sources.length,has_outline:!!data.plan.units.length,has_script:!!data.editor.text,has_storyboard:!!data.storyboard?.segments?.length,has_pilot:!!data.artifacts.pilot?.length,has_final:!!data.artifacts.final?.length,dirty:data.editor.changed,producing:activeJobs(progressJobs)||activeJobs(data.jobs)},parentOrigin);}
window.addEventListener('message',async event=>{
  if(event.source!==parent||event.origin!==parentOrigin)return;
  const message=event.data;
  if(message?.type==='kgxc-editor-confirmation'){
    if(data&&message.course_path&&message.course_path!==data.course_path)return;
    confirmationDisplay=message.question_id||message.editing_feedback?{question_id:message.question_id,stage:message.stage,status:message.status,course_path:message.course_path,editing_feedback:message.editing_feedback===true}:null;
    if(data)paintProgress();
    return;
  }
  if(message?.type==='kgxc-editor-production'&&message.course_path===data?.course_path){nativeProduction=message.production;paintProgress();return;}
  if(message?.type==='kgxc-editor-host'){hostReady=true;aiBusy=!!message.running;if(data){primaryState();paintProgress();schedulePoll();void reviews.sync().catch(e=>notice(e.message,true));}return;}
  if(message?.type==='kgxc-editor-busy'){aiBusy=!!message.running;if(data){primaryState();paintProgress();schedulePoll();}return;}
  if(message?.type==='kgxc-editor-refresh'){if(serial===savedSerial&&!saveTask)await refresh();return;}
  if(message?.type==='kgxc-editor-leave'){
    try{await save();parent.postMessage({type:'kgxc-editor-leave-result',id:message.id},parentOrigin);}catch(e){parent.postMessage({type:'kgxc-editor-leave-result',id:message.id,error:e.message},parentOrigin);}return;
  }
  if(message?.type==='kgxc-editor-result'&&pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);clearTimeout(item.timer);if(message.result?.executor==='computer'&&message.result.job){computerExportAt=Date.now();progressJobs=[...progressJobs.filter(j=>j.id!==message.result.job.id),message.result.job];paintProgress();primaryState();announce();schedulePoll();}message.error?item.reject(Error(message.error)):item.resolve(message.result);}
});
function planFields(){return {audience:data.plan.audience,performance_task:data.plan.performance_task,objectives:data.plan.objectives};}
function changed(){serial++;$('save-status').textContent='正在保存…';announce();try{localStorage.setItem(draftKey(),JSON.stringify({baseRevision:data.revision,units:stage==='outline'?data.plan.units:undefined,plan_fields:stage==='outline'?planFields():undefined,sections:stage==='script'?data.sections:undefined}));}catch{}clearTimeout(saveTimer);saveTimer=setTimeout(()=>save().catch(e=>notice(e.message,true)),650);}
async function save(){
  if(saveTask){await saveTask;if(serial!==savedSerial)return save();return;}
  if(serial===savedSerial)return;
  const checkpoint=serial,kind=stage==='outline'?'outline':'sections',payload=stage==='outline'?{units:structuredClone(data.plan.units),plan_fields:structuredClone(planFields())}:{sections:structuredClone(data.sections),baseEditorRevision:data.editor.revision};
  saveTask=api('/api/studio/'+kind,{...payload,baseRevision:data.revision}).then(value=>{
    const localUnits=data.plan.units,localSections=data.sections,localFields=planFields();data=value;savedSerial=checkpoint;
    if(stage==='outline'){data.plan.units=localUnits;Object.assign(data.plan,localFields);}else data.sections=localSections;
    if(serial===checkpoint){try{localStorage.removeItem(draftKey());}catch{}}
    $('save-status').textContent=serial===savedSerial?'已保存':'正在保存…';announce();
  });
  try{await saveTask;}finally{saveTask=null;}
  if(serial!==savedSerial)return save();
}
async function action(name,args={}){await save();data=await api('/api/studio/'+name,{...args,baseRevision:data.revision});serial=savedSerial=0;render();announce();return data;}
async function refresh(){if(closed)return false;const value=await api('/api/studio');if(serial!==savedSerial||saveTask)return false;data=value;render();announce();schedulePoll();return true;}
function paintProgress(){if(!data)return;const native=nativeProduction?.updated_at>=computerExportAt?nativeProduction:undefined;const body=finalPhase==='body'?finalBodyState(data):null,recovery=!body?recoveryState():null,state=recovery?{label:recovery.summary,value:null,detail:recovery.detail,recovery:true,tone:'failed'}:body?{label:body.title,value:null,detail:body.detail,tone:'waiting'}:productionProgress({stage,busy:aiBusy,data,jobs:progressJobs,native});overview.update({...data,ai_review:reviews.state||data.ai_review,confirmation_display:confirmationDisplay},stage,{...state,phase:finalPhase});$('production-progress').dataset.state=state.tone;$('production-progress').dataset.indeterminate=String(state.value===null||!!progressError);$('production-label').textContent=progressError||state.label;$('production-owner').textContent=progressError?'连接异常 · 正在重试':state.tone==='working'?'AI 正在执行 · 无需手动操作':state.tone==='done'?'成果已保存':'制作状态 · 查看当前说明';$('production-detail').textContent=progressError?'当前数据暂未读到，将自动重新连接。':state.detail;$('production-bar').setAttribute('aria-valuetext',progressError||state.label);if(state.value===null||progressError)$('production-bar').removeAttribute('value');else $('production-bar').value=state.value;paintProductionSteps(finalPhase==='body'?undefined:native,state.tone==='done');}
function paintProductionSteps(native,historical=false){
  const panel=$('production-steps'),list=$('production-step-list'),issue=native?.issue,historyOpen=!!list.querySelector('[data-production-history]')?.open,
    openedErrors=new Set([...list.querySelectorAll('details[data-failure-id][open]')].map(node=>node.dataset.failureId));panel.hidden=!native?.available;list.replaceChildren();
  if(!native?.available)return;
  const task={outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课视频'}[native.stage];
  panel.dataset.historical=String(historical);panel.querySelector('summary').textContent=historical?'查看制作步骤与历史记录':(task?'当前'+task+' · ':'')+'查看具体制作步骤与耗时';
  const signature=issue&&issue.key+':'+issue.at;if(signature&&signature!==lastNativeIssue){panel.open=!historical;lastNativeIssue=signature;}
  $('production-issue').hidden=!issue;$('production-issue').setAttribute('role',historical?'status':'alert');$('production-issue').textContent=issue?(historical?'先前检查记录（非当前合成状态）：':'')+(issue.subject?issue.subject+'：':'')+issue.error:'';
  for(const item of (native.items||[]).slice(-6)){
    const row=el('li',null,'production-step'),label=el('span',item.label+(item.subject?' · '+item.subject:'')),status=({running:'执行中',complete:'已完成',failed:'失败',stopped:'已停止'})[item.status]||item.status;
    const seconds=Math.max(0,((item.ended_at||Date.now())-item.started_at)/1000);
    row.dataset.status=item.status;row.append(label,el('span',status+' · '+(seconds<1?seconds.toFixed(1):Math.floor(seconds))+' 秒','meta'));list.append(row);
  }
  if(native.history?.length){
    const container=el('li'),history=el('details',null,'job-history');history.dataset.productionHistory='true';history.open=historyOpen;
    history.append(el('summary','历史失败记录（'+native.history.length+'）'));container.append(history);list.append(container);
    for(const failure of native.history){
      const entry=el('div',null,'job'),replacement=failure.superseded_by;
      entry.append(el('p',(failure.label||'制作步骤')+(failure.subject?' · '+failure.subject:'')),
        el('p',replacement?(Number.isFinite(replacement.workflow_revision)?'已被修订 '+replacement.workflow_revision+' 的成功步骤替代':'已被后续同一步骤的成功执行替代'):'旧任务的未解决记录；不代表当前任务失败','meta'));
      if(replacement)entry.append(el('p','成功步骤：'+replacement.id+(replacement.script_sha256?' · 稿件 SHA '+replacement.script_sha256:''),'meta'));
      const detail=el('details',null,'job-diagnostics');detail.dataset.failureId=failure.id||failure.key;detail.open=openedErrors.has(detail.dataset.failureId);
      detail.append(el('summary','查看保留的错误与时间'),el('pre',(failure.errors?.length?failure.errors:[{at:failure.at,error:failure.error}]).map(value=>new Date(value.at).toLocaleString()+'\n'+value.error).join('\n\n')));
      entry.append(detail);history.append(entry);
    }
  }
}
async function pollProgress(){if(closed||document.hidden||progressReading)return;progressReading=true;const wasActive=activeJobs(progressJobs);try{progressJobs=await api('/api/jobs');progressError='';paintProgress();primaryState();if(wasActive&&!activeJobs(progressJobs)){if(serial===savedSerial&&!playing)await refresh();else{notice('新制作结果已返回。');$('notice').append(button('查看新结果',async()=>{await save();pause();await refresh();}));}announce();}}catch(e){progressError='制作进度连接暂时中断';paintProgress();}finally{progressReading=false;schedulePoll();}}
function schedulePoll(){clearTimeout(pollTimer);if(!closed&&!document.hidden&&(aiBusy||activeJobs(progressJobs)||activeJobs(data?.jobs)))pollTimer=setTimeout(pollProgress,3000);}
new ResizeObserver(()=>document.documentElement.style.setProperty('--studio-header-height',document.querySelector('header').getBoundingClientRect().height+'px')).observe(document.querySelector('header'));
function pendingPanel(root){const relevant=(data.plan.decisions||[]).filter(d=>(d.gate||'outline')===(stage==='sources'?'outline':stage));const waiting=relevant.filter(d=>!['confirmed','delegated'].includes(d.status));const accepted=relevant.filter(d=>['confirmed','delegated'].includes(d.status));if(accepted.length){const summary=el('section',null,'card pending');summary.append(el('h3','已记录的选择'));for(const item of accepted)summary.append(el('p',item.question+'：'+(item.options.find(o=>o.id===item.selected)?.label||item.options.find(o=>o.id===item.selected)?.title||item.selected)));if(stage==='outline')summary.append(button('按已选方案更新大纲建议',()=>host('stage',{target_stage:'outline',instruction:'按已经记录的真实选择复核并更新大纲。保留人工修改，变更先展示建议，不自动确认。'})));root.append(summary);}if(!waiting.length)return;const card=el('section',null,'card pending');card.append(el('h3','本阶段还有待选择事项'));const list=el('ul');for(const item of waiting)list.append(el('li',item.question));card.append(list,el('p','AI 会在右侧对话主动发起问答。','meta'));root.append(card);}
function impactPanel(root){if(!data.impact?.reason)return;const gate=data.gates.find(g=>g.id===stage);if(gate?.status!=='stale'&&!data.editor.changed&&(gate?.ready||['confirmed','delivered'].includes(gate?.status)))return;const box=el('p',data.impact.reason+(data.impact.segment_ids?.length?'；关联 '+data.impact.segment_ids.length+' 个教学片段。':''),'impact');root.append(box);}
function inputField(label,value,onChange,multi=false){const wrap=el('label',label),control=el(multi?'textarea':'input');control.value=value||'';control.oninput=()=>{onChange(control.value);changed();};wrap.append(control);return wrap;}

function materialLibrary(root){
  const rows=materialRows(data.material_library,data.sources);
  const card=el('section',null,'material-library card');
  const title=el('h2','素材库');
  title.id='material-library-title';card.setAttribute('aria-labelledby',title.id);
  card.append(title,el('p','按文件查看用没用、用在哪、为什么。只有核实到当前视频的位置才提供播放定位。','meta'));
  if(!rows.length){card.append(el('p','尚未入库素材。上传资料或实拍图后，可以在这里逐个核对。','material-library-empty'));root.append(card);return;}
  const totals=el('ul',null,'material-library-totals');
  for(const status of Object.keys(materialStatuses)){const total=rows.filter(item=>item.status===status).length;if(total)totals.append(el('li',materialStatuses[status].title+' '+total));}
  card.append(totals);
  const list=el('ul',null,'material-library-list');
  for(const item of rows){
    const row=el('li',null,'material-library-row'),header=el('div',null,'material-library-item-head'),identity=el('div',null,'material-library-identity');
    row.dataset.status=item.status;
    if(item.kind==='image'&&item.path&&item.available===true){const thumb=el('img');thumb.alt='';thumb.loading='lazy';thumb.src=fileURL(item.path);thumb.addEventListener('error',()=>{thumb.hidden=true;},{once:true});header.append(thumb);}
    identity.append(el('h3',item.title||item.path?.split('/').at(-1)||'未命名素材'),el('span',item.kind==='image'?'图片':'文件','meta'));header.append(identity,el('span',materialStatuses[item.status].title,'material-library-badge'));
    row.append(header,el('p',item.reason||materialStatuses[item.status].description,'material-library-reason'));
    if(item.path&&item.available===true)row.append(link(item.path,'查看原文件'));
    if(item.placements.length){
      const uses=el('ul',null,'material-library-placements');
      for(const p of item.placements){
        const label=({pilot:'有声小样',final:'整课成片',body:'主体视频'})[p.stage]+(p.segment_label?' · '+p.segment_label:'');
        const jump=el('a',label+' '+stamp(p.start_seconds)+'–'+stamp(p.end_seconds));
        jump.href=fileURL(p.artifact_path)+'#t='+p.start_seconds+','+p.end_seconds;
        jump.target='_blank';jump.rel='noopener';const place=el('li');place.append(jump);uses.append(place);
      }
      row.append(uses);
    }else if(item.status==='used')row.append(el('p','已登记使用，但暂无可播放的时间定位。','meta'));
    if(item.source_points.length){
      const details=el('details',null,'material-library-points'),points=el('ul');
      details.append(el('summary','原件内容取舍 · '+item.source_points.length+' 项'));
      const labels={retained:'保留',merged:'合并',omitted:'舍弃'};
      for(const p of item.source_points){
        const point=el('li');
        point.append(el('strong',[labels[p.disposition],p.locator].filter(Boolean).join(' · ')||'原件要点'));
        if(p.reason)point.append(el('p',p.reason));points.append(point);
      }
      details.append(points);row.append(details);
    }
    list.append(row);
  }
  card.append(list);root.append(card);
}

function sourcesView(root){
  root.append(el('p','加入原始资料，核对原件摘要、缺口与每项内容的课程去处。','intro'));
  const upload=el('input');upload.type='file';upload.multiple=true;upload.accept='.pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp';upload.hidden=true;
  upload.onchange=async()=>{try{for(const file of upload.files){if(file.size>25*1024*1024)throw Error('单个资料文件最大 25 MB。');const response=await fetch('/api/studio/source',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name),'X-Base-Revision':String(data.revision)},body:file});const result=await response.json();if(!response.ok||result.error)throw Error(result.error);data=result;}render();announce();}catch(e){notice(e.message,true);}finally{upload.value='';}};
  root.append(button('上传原始资料',()=>upload.click()),upload);
  materialLibrary(root);
  if(!data.sources.length){root.append(empty('尚未加入原件','也可以在右侧对话中描述主题，或选择资料文件夹，让 AI 建立课程。'));return;}
  const grid=el('div',null,'source-grid'),list=el('div',null,'source-list'),preview=el('section',null,'source-preview');
  selectedSource=data.sources.find(s=>s.id===selectedSource)?.id||data.sources[0].id;
  for(const source of data.sources){const b=button(source.title,()=>{selectedSource=source.id;sourcePage=1;render();});b.setAttribute('aria-pressed',String(source.id===selectedSource));list.append(b);}
  const source=data.sources.find(s=>s.id===selectedSource);
  if(!source.available)preview.append(el('p','原件已不在工程中；请补充资料。','card'));
  else if(/\.(txt|md|csv)$/i.test(source.location)){const pre=el('pre','正在读取原件…');preview.append(pre);fetch(fileURL(source.location)).then(r=>r.text()).then(text=>pre.textContent=text).catch(e=>pre.textContent=e.message);}
  else if(/\.(png|jpe?g|webp)$/i.test(source.location)){const image=el('img');image.src=fileURL(source.location);image.alt=source.title;preview.append(image);}
  else if(/\.pdf$/i.test(source.location)){if(source.pdf_preview_available){const controls=el('div',null,'pdf-controls'),prev=button('上一页',()=>{sourcePage--;render();}),next=button('下一页',()=>{sourcePage++;render();});prev.disabled=sourcePage<=1;next.disabled=sourcePage>=source.pages;controls.append(prev,el('span','第 '+sourcePage+' / '+source.pages+' 页'),next);const image=el('img');image.src=resourceURL('/api/studio/source-preview?id=')+encodeURIComponent(source.id)+'&page='+sourcePage;image.alt=source.title+' 第'+sourcePage+'页原件';image.onerror=()=>notice('此页预览未能显示，请使用“查看原件文件”打开原件。',true);preview.append(controls,image);}else preview.append(el('p','本机暂未提供 PDF 页预览，可直接打开完整原件。','card'),link(source.location,'打开 PDF 原件'));}
  else preview.append(el('p','此格式保留完整原件，可下载后查看。','card'),link(source.location,'打开 '+source.title));
  list.append(link(source.location,'查看原件文件'));grid.append(list,preview);root.append(grid);
  const ledger=el('section',null,'ledger');ledger.append(el('h2','原件内容怎样进入课程'));
  for(const item of data.plan.source_items||[]){const row=el('div',null,'ledger-item');const refs=(item.source_refs||[]).map(ref=>(data.sources.find(s=>s.id===ref.source_id)?.title||ref.source_id)+(ref.locator?' · '+ref.locator:''));const destinations=(item.unit_ids||[]).map(id=>{const index=data.plan.units.findIndex(u=>u.id===id);return index<0?id:'第'+(index+1)+'章 '+data.plan.units[index].title;});row.append(el('h3',item.title||item.summary||item.id),el('p',item.summary||item.content||(item.key_points||[]).join('\n')),el('p','处理：'+(({core:'纳入主课',reference:'作为参考',appendix:'附录',omit:'本课不采用',omitted:'本课不采用',excluded:'本课不采用',merge:'合并讲解',partial:'采用相关内容',merged:'合并讲解',deferred:'移至后续课程'})[item.disposition]||item.disposition||item.treatment||'待分析'),'meta'));if(refs.length)row.append(el('p','原件位置：'+refs.join('；'),'meta'));if(destinations.length)row.append(el('p','课程去处：'+destinations.join('；'),'meta'));if(item.reason||item.rationale)row.append(el('p','理由：'+(item.reason||item.rationale),'meta'));ledger.append(row);}
  if(!(data.plan.source_items||[]).length)ledger.append(el('p','AI 完成素材诊断后，这里显示采用、删减或移至其他章节的内容与理由。','muted'));
  for(const issue of data.plan.issues||[])ledger.append(el('p','待补充：'+(issue.detail||issue.title||issue.id),'impact'));
  root.append(ledger,el('p','工程位置：'+data.course_path,'file-path'));
}

function outlineView(root){
  root.append(el('p','按章节卡片修改内容。拖动卡片或使用上移、下移；保存会同步关联的讲稿次序，并标出后续需要更新的部分。','intro'));impactPanel(root);
  if(!data.plan.units.length){root.append(empty('大纲尚未生成','点击上方“生成大纲”，AI 会先分析资料并给出可审阅结构。'));return;}
  const intro=el('section',null,'card fields');intro.append(inputField('学习对象',data.plan.audience,value=>data.plan.audience=value),inputField('学习后要完成的工作',data.plan.performance_task,value=>data.plan.performance_task=value));
  const goals=el('details',null,'full');goals.append(el('summary','查看与修改全课学习目标'));for(const objective of data.plan.objectives||[])goals.append(inputField(objective.id,objective.statement,value=>objective.statement=value,true));intro.append(goals);root.append(intro);
  const units=el('div');let dragged;
  data.plan.units.forEach((unit,index)=>{
    const card=el('article',null,'card unit');card.draggable=true;card.dataset.unit=unit.id;
    const head=el('div',null,'unit-head'),handle=el('span','⠿','handle'),title=el('input');handle.title='拖动调整章节顺序';title.className='title';title.setAttribute('aria-label','第'+(index+1)+'章标题');title.value=unit.title;title.oninput=()=>{unit.title=title.value;changed();};head.append(handle,el('strong','第 '+(index+1)+' 章'),title);card.append(head);
    const fields=el('div',null,'fields');fields.append(inputField('核心内容（每行一项）',Array.isArray(unit.content_points)?unit.content_points.join('\n'):unit.content_points||unit.summary,value=>unit.content_points=value.split('\n').map(s=>s.trim()).filter(Boolean),true),inputField('学习活动',unit.activity,value=>unit.activity=value,true),inputField('推荐讲法',unit.teaching_method,value=>unit.teaching_method=value,true),inputField('为什么这样讲',unit.teaching_reason,value=>unit.teaching_reason=value,true));
    const duration=inputField('预计时长（分钟）',unit.duration_minutes??unit.estimated_minutes??'',value=>unit.duration_minutes=value);duration.lastChild.placeholder='尚未估算';fields.append(duration);card.append(fields);
    const objectives=(unit.objective_ids||[]).map(id=>data.plan.objectives.find(o=>o.id===id)?.statement||id);if(objectives.length)card.append(el('p','学习目标：'+objectives.join('；'),'meta'));
    const refs=unit.source_refs?.length?unit.source_refs:(unit.source_ids||[]).map(id=>({source_id:id}));if(refs.length)card.append(el('p','来源：'+refs.map(ref=>(data.sources.find(s=>s.id===ref.source_id)?.title||ref.source_id)+(ref.locator?' · '+ref.locator:'')).join('；'),'meta'));
    const controls=el('div',null,'unit-actions');
    for(const [label,name] of [['在后面加一章','add'],['拆分这一章','split'],['与下一章合并','merge'],['删除这一章','remove']])controls.append(button(label,()=>action(name,{unit_id:unit.id})));
    const move=async offset=>{await save();const order=data.plan.units.map(u=>u.id),a=order.indexOf(unit.id),b=a+offset;if(b<0||b>=order.length)return;[order[a],order[b]]=[order[b],order[a]];await action('reorder',{order});};controls.append(button('上移',()=>move(-1)),button('下移',()=>move(1)));const editMenu=el('details',null,'chapter-tools');editMenu.append(el('summary','调整章节结构'),controls);card.append(editMenu);
    card.ondragstart=event=>{if(event.target.closest('input,textarea,button')){event.preventDefault();return;}dragged=unit.id;event.dataTransfer.setData('text/plain',unit.id);};card.ondragover=event=>{event.preventDefault();card.classList.add('drop');};card.ondragleave=()=>card.classList.remove('drop');card.ondrop=async event=>{event.preventDefault();card.classList.remove('drop');try{await save();const id=dragged||event.dataTransfer.getData('text/plain'),order=data.plan.units.map(u=>u.id);if(!order.includes(id)||id===unit.id)return;order.splice(order.indexOf(id),1);order.splice(order.indexOf(unit.id),0,id);await action('reorder',{order});}catch(e){notice(e.message,true);}};
    units.append(card);
  });root.append(units);
}

function scriptView(root){
  impactPanel(root);
  if(data.editor.text&&!data.mapped){const box=el('section',null,'card');box.append(el('h2','已有讲稿尚未绑定章节'),el('p','原稿完整保留。先让 AI 给出章节绑定建议，审阅后采用；避免按标题猜配。'),el('pre',data.editor.text),button('让 AI 按大纲绑定当前原稿',()=>host('stage',{target_stage:'script',instruction:'保留现有原稿全文，提出按稳定章节身份绑定的分章建议，不删内容，先展示差异。'})));root.append(box);return;}
  if(!data.sections.length){root.append(empty('先确定课程大纲','有了章节后，可以在这里逐章编辑讲稿。'));return;}
  selectedUnit=data.sections.find(s=>s.unit_id===selectedUnit)?.unit_id||data.sections[0].unit_id;
  const grid=el('div',null,'script-grid'),form=el('section',null,'script-form'),preview=el('section');
  const choose=el('select');choose.setAttribute('aria-label','选择讲稿章节');data.sections.forEach((s,i)=>{const option=el('option',(i+1)+'. '+s.title);option.value=s.unit_id;option.selected=s.unit_id===selectedUnit;choose.append(option);});choose.onchange=async()=>{try{await save();selectedUnit=choose.value;pause();render();}catch(e){notice(e.message,true);}};
  const area=el('textarea');area.className='chapter-text';area.id='chapter-script';area.setAttribute('aria-label','当前章节逐字稿');area.value=section().body;area.placeholder='这一章的口播、练习引导与反馈';
  const counts=el('div',null,'counts'),words=el('span'),estimate=el('span');counts.append(words,estimate);
  const count=()=>{const n=[...area.value.replace(/\s/g,'')].length;words.textContent=n+' 字';estimate.textContent='估时约 '+Math.ceil(n/230)+' 分钟（配音后校准）';};count();
  area.oninput=()=>{section().body=area.value;changed();count();pause();clearTimeout(previewTimer);previewTimer=setTimeout(updatePreview,160);};area.onclick=()=>updatePreview();
  const tools=el('div',null,'row');tools.append(button('选择当前段落',()=>{const p=paragraphAt(area.value,area.selectionStart);if(p){area.focus();area.setSelectionRange(p.start,p.end);}}),button('让 AI 修改选中文字',()=>openRewrite(area)));
  form.append(choose,tools,area,counts);const screen=el('div',null,'screen'),waiting=el('div',null,'placeholder');waiting.id='waiting';waiting.append(el('span','逐字稿预览','meta'),el('h2',section().title),el('p',section().body||'开始输入这一章的讲稿。'),el('small','课程动态画面尚未制作'));
  const frame=el('iframe');frame.id='real-preview';frame.title='当前章节实际画面';frame.hidden=true;screen.append(frame,waiting);preview.append(screen,el('p',native?'修改后的实际画面与声音在有声小样阶段检查。':'文字改动即时预览；配音和视频在对应制作阶段更新。','preview-meta'));
  const controls=el('div',null,'playback'),play=button('播放预览',()=>togglePlay());play.id='play';play.disabled=true;const seek=el('input');seek.type='range';seek.min=0;seek.max=1;seek.value=0;seek.id='seek';seek.setAttribute('aria-label','课程预览进度');seek.oninput=()=>{pause();previewFrame=Number(seek.value);paint();};const clock=el('span','00:00');clock.id='preview-time';controls.append(play,seek,clock);preview.append(controls);grid.append(form,preview);root.append(grid);loadPreview().catch(e=>notice(e.message,true));
}
async function openRewrite(area){let start=area.selectionStart,end=area.selectionEnd;if(start===end){const p=paragraphAt(area.value,start);if(!p)return;start=p.start;end=p.end;}selection={snapshot:area.value,text:area.value.slice(start,end),start,end,unit_id:selectedUnit};$('rewrite-selection').textContent=selection.text;$('rewrite-instruction').value='';$('rewrite-result').hidden=true;$('rewrite-accept').disabled=true;$('rewrite-status').textContent='';$('rewrite').showModal();}
$('rewrite-generate').onclick=async()=>{if(!selection)return;try{$('rewrite-generate').disabled=true;$('rewrite-status').textContent='AI 正在生成修改建议…';const result=await host('rewrite',{requestId:crypto.randomUUID(),text:selection.text,instruction:$('rewrite-instruction').value.trim()||'更清楚自然，保留事实和关键步骤',before:selection.snapshot.slice(Math.max(0,selection.start-1200),selection.start),after:selection.snapshot.slice(selection.end,selection.end+1200)});$('rewrite-suggestion').value=result.text;$('rewrite-result').hidden=false;$('rewrite-accept').disabled=false;$('rewrite-status').textContent='核对后采用，只替换选中范围。';}catch(e){$('rewrite-status').textContent=e.message;}finally{$('rewrite-generate').disabled=false;}};
$('rewrite-accept').onclick=()=>{try{const area=$('chapter-script');if(!area||selectedUnit!==selection.unit_id)throw Error('当前章节已切换，请重新选择文字。');area.value=replaceSelection(area.value,selection,$('rewrite-suggestion').value);area.dispatchEvent(new Event('input'));$('rewrite').close();}catch(e){$('rewrite-status').textContent=e.message;}};

async function loadPreview(){if(native)return;renderer=null;previewState=await api('/api/editor');const frame=$('real-preview');if(!frame||!previewState.has_scenes)return;frame.src='/renderer.html?revision='+previewState.document.revision+'&studio='+Date.now();frame.hidden=false;$('waiting').hidden=true;await new Promise((resolve,reject)=>{const end=Date.now()+25000;const check=()=>{if(closed||!frame.isConnected)return resolve();if(frame.contentWindow.ready)return resolve();if(frame.contentWindow.renderError)return reject(Error(frame.contentWindow.renderError));if(Date.now()>end)return reject(Error('画面预览尚未就绪'));setTimeout(check,80);};check();});if(!frame.isConnected)return;renderer=frame.contentWindow.courseRenderer;audio.src='/api/audio?revision='+previewState.document.revision;$('play').disabled=false;await updatePreview();}
async function updatePreview(){const current=section(),area=$('chapter-script');if(!current||!area)return;const waiting=$('waiting');if(waiting){waiting.querySelector('h2').textContent=current.title;waiting.querySelector('p').textContent=paragraphAt(area.value,area.selectionStart)?.text||area.value||'开始输入这一章的讲稿。';}if(!renderer||!previewState)return;const text=fullText(),prefix=data.sections.slice(0,data.sections.findIndex(s=>s.unit_id===selectedUnit)).map((s,i)=>'## '+(i+1)+'. '+s.title+'\n\n'+s.body.trim()).join('\n\n');const caret=(prefix?prefix.length+2:0)+('## '+(data.sections.findIndex(s=>s.unit_id===selectedUnit)+1)+'. '+current.title+'\n\n').length+area.selectionStart;const result=previewDocument(previewState.document,previewState.base_text,text,caret);if(result.scene)previewFrame=displayFrame(result.scene.sourceStartFrame,result.document.holds,result.document.cuts);previewState.currentDoc=result.document;await renderer.load(result.document);audio.muted=text!==previewState.base_text;$('seek').max=totalFrames(result.document)-1;await paint();}
async function paint(){if(!renderer||!previewState?.currentDoc)return;await renderer.drawFrame(previewFrame);if($('seek'))$('seek').value=previewFrame;if($('preview-time'))$('preview-time').textContent=stamp(previewFrame/previewState.currentDoc.fps);}
function pause(){playing=false;audio.pause();if($('play'))$('play').textContent='播放预览';}
function togglePlay(){if(playing){pause();return;}if(!renderer)return;playing=true;playEpoch=performance.now()-previewFrame/previewState.currentDoc.fps*1000;if(!audio.muted){audio.currentTime=previewFrame/previewState.currentDoc.fps;audio.play().catch(()=>{});}$('play').textContent='暂停预览';tick();}
async function tick(){if(!playing||closed)return;previewFrame=Math.min(totalFrames(previewState.currentDoc)-1,Math.floor((performance.now()-playEpoch)/1000*previewState.currentDoc.fps));await paint();if(previewFrame>=totalFrames(previewState.currentDoc)-1)pause();else requestAnimationFrame(tick);}

function storyboardView(root){
  root.append(el('p','每个教学片段比较不同画面表现；静态关键帧只作示意，实际动态画面以小样为准。','intro'));impactPanel(root);
  const segments=data.storyboard?.segments||[];if(!segments.length){root.append(empty('全课分镜尚未生成','确认逐字稿后，AI 将覆盖整课内容，为每段提出至少三种表现方案。'));return;}
  selectedSegment=segments.find(s=>s.id===selectedSegment)?.id||segments[0].id;
  root.append(button('采用全部推荐方案',()=>action('choice',{id:'all',option:'recommended'})));
  const grid=el('div',null,'board-grid'),list=el('nav',null,'segment-list'),detail=el('section');list.setAttribute('aria-label','章节与教学片段');
  segments.forEach((s,i)=>{const unit=data.plan.units.find(u=>u.id===s.unit_id);const b=button((i+1)+'. '+(unit?.title||'')+' · '+s.teaching_goal,()=>{selectedSegment=s.id;render();});b.setAttribute('aria-current',String(s.id===selectedSegment));list.append(b);});
  const current=segments.find(s=>s.id===selectedSegment);detail.append(el('h2',current.teaching_goal),el('blockquote',current.script_excerpt,'segment-copy'));
  const alternatives=el('div',null,'alternatives');for(const option of current.options){const card=el('article',null,'card alternative');card.setAttribute('aria-selected',String(current.selected===option.id));card.append(el('h3',option.method+(current.recommended===option.id?' · 推荐':'')));
    for(const [key,label] of [['opening','开始画面'],['action','画面动作'],['result','最终结果'],['focus','观看焦点'],['feasibility','实现条件'],['cost','制作量'],['risk_note','需检查']])if(option[key])card.append(el('p',label+'：'+option[key],'detail'));
    const keyframe=el('div',null,'keyframe');keyframe.append(el('p','静态画面示意','meta'));if(option.preview_file){if(/\.(png|jpe?g|webp|svg)$/i.test(option.preview_file)){const img=el('img');img.src=fileURL(option.preview_file);img.alt=option.method+'关键帧示意';keyframe.append(img);}else keyframe.append(link(option.preview_file,'查看画面示意'));}else keyframe.append(el('p','尚未生成关键帧；上方为已写入分镜的画面方案。','muted'));card.append(keyframe,button(current.selected===option.id?'已采用这一方案':'采用这一方案',()=>action('choice',{id:current.id,option:option.id}),current.selected===option.id?'primary':undefined));alternatives.append(card);}
  detail.append(alternatives);const refine=el('section',null,'card feedback'),instruction=el('textarea');instruction.placeholder='例如：改成顾客与私教对话，保留本段教学目的';refine.append(el('h3','调整本段画面或视觉风格'),instruction,button('让 AI 给出本段修改建议',()=>host('stage',{target_stage:'storyboard',segment_id:current.id,instruction:instruction.value,user_instruction:instruction.value})));detail.append(refine);grid.append(list,detail);root.append(grid);
}
function timestampFeedback(stageName,segmentId,video,file,interval){
  if(!video||!file?.sha256||!parentOrigin||parent===window)return null;
  return button('这里要改',()=>{
    video.pause();
    const start=interval?.playback_start??0;
    const stop=interval?.playback_end??(Number.isFinite(file.duration_seconds)?file.duration_seconds:video.duration);
    const time=Math.max(start,Math.min(Number.isFinite(stop)?stop:Number.MAX_SAFE_INTEGER,Number(video.currentTime)||start));
    parent.postMessage({type:'kgxc-editor-feedback',course_path:data.course_path,stage:stageName,
      segment_id:segmentId,time:Number(time.toFixed(3)),artifact_path:file.path,artifact_sha256:file.sha256},parentOrigin);
  });
}
function feedbackForm(stageName,segmentId,video,file){
  const history=el('div',null,'feedback-history');
  for(const item of (data.feedback||[]).filter(f=>f.stage===stageName&&f.segment_id===segmentId).slice(-5)){
    const same=!!video&&item.artifact_sha256===file?.sha256;const entry=el('div',null,'card');
    entry.append(el('p',item.text),el('p',item.artifact_sha256?'视频内 '+stamp(item.time)+(same?' · 当前视频':' · 先前视频版本'):'已记录的制作要求','meta'));
    if(same)entry.append(button('定位这条反馈',()=>{video.currentTime=item.time;}));history.append(entry);
  }
  return history;
}
function samplePlayer(file,binding,index){const video=el('video');video.controls=true;video.preload='metadata';video.src=fileURL(file.path)+'#t='+binding.playback_start+','+binding.playback_end;video.setAttribute('aria-label','有声样段 '+(index+1));const start=binding.playback_start,end=binding.playback_end;video.addEventListener('loadedmetadata',()=>video.currentTime=start);video.addEventListener('play',()=>{if(video.currentTime<start||video.currentTime>=end-.04)video.currentTime=start;});video.addEventListener('seeking',()=>{if(video.currentTime<start-.05)video.currentTime=start;else if(video.currentTime>end+.05)video.currentTime=end;});video.addEventListener('timeupdate',()=>{if(!video.paused&&video.currentTime>=end-.035){video.pause();video.currentTime=end;}});return video;}
function mediaReviewScope(root,stageName){
  const review=reviews.state||data.ai_review;if(!requiresUserAudio(review,stageName))return;
  const audio=review.nodes?.[stageName]?.user_audio_review,scope=el('section',null,'card review-audio-scope');scope.append(el('h2','AI审文字与画面，你听音轨'),el('p','AI的静帧和画面序列检查不代表连续播放。请完整播放当前全部'+(stageName==='pilot'?'小样':'成片')+'，在原确认窗口中同时声明声音、音画配合和内容均可接受。'));
  scope.append(el('p','当前听审状态：'+({confirmed:'当前全部视频已实际听审',stale:'媒体已变化，先前声明失效',issues_reported:'已记录声音问题，未确认',pending:'待用户完整听审'}[audio?.status]||'尚未取得完整媒体范围'),'review-verdict'));
  const hashes=audio?.artifact_sha256s||[],ranges=audio?.artifacts||[];
  if(!hashes.length)scope.append(el('p','当前尚无可绑定的完整媒体范围，不能确认听审。','review-blocked'));
  hashes.forEach((sha,index)=>{const range=ranges[index],file=(data.artifacts[stageName]||[]).find(f=>f.sha256===sha&&f.available);const row=el('article',null,'review-media-binding');row.append(el('h3','完整视频 '+(index+1)),el('p','SHA-256 '+sha,'file-path'),el('p',range?.sha256===sha&&Number.isFinite(range.end_seconds)?'完整范围 '+range.start_seconds+'—'+range.end_seconds+' 秒':'时长尚未核对，不能作听审声明。','meta'));
    if(file){row.append(link(file.path,'打开当前完整视频'));if(stageName==='pilot'){const video=el('video');video.controls=true;video.preload='metadata';video.src=fileURL(file.path);video.className='delivery-video';video.setAttribute('aria-label','完整听审小样 '+(index+1));row.append(video);}}else row.append(el('p','这一版本的视频尚不可访问，请刷新核对。','review-blocked'));scope.append(row);});
  root.append(scope);
}
let liveProduction;
const overview=createProductionOverview({document,onCoverage:()=>sourceCoverage.open()});
function liveWorkspace(root){if(!liveProduction)liveProduction=createLiveProduction({document,window,fetch,mediaURL:fileURL});liveProduction.mount(root);}
function samplesView(root){
  const previewRoot=root,inspection=el('details',null,'sample-inspection');inspection.append(el('summary','查看抽样依据、听审范围和制作记录'));root=inspection;
  impactPanel(root);mediaReviewScope(root,'pilot');
  if(data.artifacts.pilot?.some(file=>file.available&&file.current_storyboard)){
    const retry=button('重新合成当前小样',async()=>{retry.disabled=true;try{await host('stage',{target_stage:'pilot'});notice('已提交当前小样制作请求。');}finally{retry.disabled=aiBusy||activeJobs(progressJobs)||activeJobs(data.jobs);}});retry.disabled=aiBusy||activeJobs(progressJobs)||activeJobs(data.jobs);root.append(retry);
  }
  const sampling=data.sampling||{},selections=sampling.selections||[];
  if(!selections.length){previewRoot.append(empty('有声小样还没生成','完成分镜后，会在这里看到三段小样。'));liveWorkspace(previewRoot);previewRoot.append(inspection);return;}
  const overview=el('section',null,'card');overview.append(el('h2','本轮抽样范围'),el('p',sampling.scope||''));if(sampling.uncovered_kinds?.length)overview.append(el('p','尚未覆盖的表现类型：'+sampling.uncovered_kinds.map(k=>({concept:'概念讲解',scenario:'人物情境',operation:'操作演示',practice:'练习与反馈'})[k]||k).join('、'),'impact'));if(sampling.unsampled_high_risk_ids?.length)overview.append(el('p','仍需另行检查 '+sampling.unsampled_high_risk_ids.length+' 个高风险片段。','meta'));root.append(overview);
  const grid=el('div',null,'sample-grid');selections.forEach((selected,index)=>{const segment=data.storyboard.segments.find(s=>s.id===selected.segment_id),card=el('article',null,'card');card.append(el('h2','样段 '+(index+1)+' · '+(segment?.teaching_goal||selected.segment_id)));
    const segmentDetails=el('details',null,'sample-inspection');segmentDetails.append(el('summary','查看本段讲稿与定位反馈'),el('p','抽样原因：'+selected.reason,'meta'));if(segment)segmentDetails.append(el('p',segment.script_excerpt),el('p','画面方案：'+(segment.options.find(o=>o.id===selected.option_id)?.method||selected.option_id),'meta'));
    const file=(data.artifacts.pilot||[]).find(item=>item.available&&item.current_storyboard&&item.bindings?.some(b=>b.segment_id===selected.segment_id&&b.option_id===selected.option_id&&b.playback_complete));const binding=file?.bindings.find(b=>b.segment_id===selected.segment_id);let video;
    if(file){video=samplePlayer(file,binding,index);card.append(video);const note=timestampFeedback('pilot',selected.segment_id,video,file,binding);if(note)card.append(note);card.append(el('p','本段位置 '+stamp(binding.playback_start)+'—'+stamp(binding.playback_end)+'；完整片段 '+(binding.playback_end-binding.playback_start).toFixed(1)+' 秒。','meta'));}else card.append(el('p','本段有声视频尚未生成，或尚未核对与当前分镜的完整对应关系。','impact'));
    segmentDetails.append(el('p','音色与语速：'+(file?.audio_settings?.summary||'暂无单独记录'),'meta'),feedbackForm('pilot',selected.segment_id,video,file,binding));card.append(segmentDetails);grid.append(card);});previewRoot.append(grid);
  if((data.artifacts.pilot||[]).some(file=>file.available&&/\.mp4$/i.test(file.path)&&!file.bindings?.length)){const extra=el('section',null,'card');extra.append(el('h3','已生成、尚待核对对应关系的视频'));for(const file of data.artifacts.pilot.filter(f=>f.available&&/\.mp4$/i.test(f.path)&&!f.bindings?.length)){const video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';extra.append(video);}previewRoot.append(extra);}
  liveWorkspace(previewRoot);previewRoot.append(inspection);
}
function finalBodyState(model){
  const pilot=model.gates?.find(g=>g.id==='pilot');
  const evidence=(model.artifacts?.body||[]).filter(file=>file.available===true&&/\.mp4$/i.test(file.path||''));
  if(evidence.length)return {title:'主体视频已登记',detail:'可播放当前主体视频。',files:evidence};
  if(pilot?.status!=='confirmed')return {title:'等待当前小样确认',detail:'三段有声小样确认后，才开始整课主体制作。',files:[]};
  return {title:'主体进度尚未单独登记',detail:'主体视频完成后会在这里显示。',files:[]};
}
function finalBodyView(root){
  const phase=el('section',null,'final-phase card');
  phase.append(el('span','整课制作 · 第一步','final-phase-index'),el('h2','画面与配音'),el('p','在这里查看整课画面、旁白和主体视频。'));
  const model=finalBodyState(data);
  phase.append(el('p',model.title,'final-phase-evidence'),el('p',model.detail,'meta'));
  for(const file of model.files){const video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';phase.append(video,link(file.path,'查看主体文件'));}
  root.append(phase);
  liveWorkspace(root);
}
function finalView(root){
  if(finalPhase==='body'){finalBodyView(root);return;}
  const phase=el('section',null,'final-phase card');
  phase.append(el('span','整课制作 · 第二步','final-phase-index'),el('h2','后期与成片'),el('p','加入花字和音效后，完整视频会出现在这里。'));
  const files=(data.artifacts.final||[]).filter(f=>f.available);
  root.append(phase);
  impactPanel(root);
  if(!files.length)root.append(empty('成片还没生成','完成后可在这里播放。'));
  for(const file of files){const card=el('section',null,'card');let video;if(/\.mp4$/i.test(file.path)){video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';card.append(video);const note=timestampFeedback('final',undefined,video,file);if(note)card.append(note);if(file.chapters?.length){const jumps=el('div',null,'unit-actions');for(const chapter of file.chapters)jumps.append(button(chapter.title,()=>{video.currentTime=Math.min(chapter.start,Math.max(0,(video.duration||Infinity)-.1));}));card.append(jumps);}else card.append(el('p','此文件没有经过核对的章节定位，仍可直接播放。','meta'));}card.append(link(file.path,'下载当前文件'));if(video){const feedback=el('details',null,'sample-inspection');feedback.append(el('summary','定位反馈'),feedbackForm('final',undefined,video,file));card.append(feedback);}root.append(card);}
  for(const delivery of data.deliveries||[])if(delivery.path||delivery.paths)root.append(el('p','已登记交付：'+(delivery.path||delivery.paths.join('、')),'file-path'));
  const diagnostics=el('details',null,'sample-inspection');diagnostics.append(el('summary','查看成片检查与制作记录'));
  mediaReviewScope(diagnostics,'final');
  const {current,history}=productionJobHistory(progressJobs.length?progressJobs:data.jobs,'final');
  if(current)diagnostics.append(exportJobCard(current,false));
  if(history.length){const archive=el('details',null,'job-history'),failed=history.filter(job=>job.status==='failed').length;archive.append(el('summary','历史制作记录 · '+history.length+' 次'+(failed?'，其中 '+failed+' 次当时未通过':'')));archive.append(el('p','历史文件和错误均保留；下列记录不代表当前任务状态。','meta'));for(const job of history)archive.append(exportJobCard(job,true));diagnostics.append(archive);}
  root.append(diagnostics);
}
function exportJobCard(job,historical){
  const row=el('section',null,'job'),heading=el('div',null,'job-heading');row.dataset.status=job.status;
  let label=({queued:'排队中',rendering:'制作中',encoding:'编码中',packaging:'整理交付',complete:'合成已完成',failed:'本次未通过校验'})[job.status]||job.status;
  if(job.status==='complete'&&job.registration_status==='held')label='候选已生成 · 验收受阻';
  if(historical)label=job.status==='failed'?'历史失败记录':label;
  heading.append(el('strong',(historical?'':'当前任务 · ')+label,'job-label'),el('span',(Number.isFinite(job.revision)?'R'+job.revision+' · ':'')+(job.id||''),'meta'));row.append(heading);
  if(job.status==='complete')row.append(el('p',job.registration_status==='held'?'渲染与编码检查已完成；制作候选尚未登记，需补齐当前制作检查。':'已完成渲染与编码检查。','meta'));
  if(job.registration_status==='held'&&job.contract_pending?.errors?.length){const pending=el('details',null,'job-diagnostics');pending.append(el('summary','当前缺项 · '+job.contract_pending.errors.length+' 项'));for(const issue of job.contract_pending.errors)pending.append(el('p',(issue.code?issue.code+'：':'')+issue.message));row.append(pending);}
  if(!historical&&activeJobs([job])&&typeof job.progress==='number'){const line=el('div',null,'job-progress'),bar=el('progress');bar.max=1;bar.value=Math.max(0,Math.min(1,job.progress));line.append(bar,el('span',Math.floor(bar.value*100)+'%'));row.append(line);}
  if(job.supersededBy)row.append(el('p','后续 '+(Number.isFinite(job.supersededBy.revision)?'R'+job.supersededBy.revision+' ':'')+'导出已通过；本条保留为历史诊断。','meta'));
  if(job.error){const diagnostic=el('details',null,'job-diagnostics');diagnostic.append(el('summary',historical?'查看当时的错误详情':'查看本次错误详情'),el('pre',String(job.error)));row.append(diagnostic);}
  return row;
}
function empty(title,copy){const box=el('section',null,'empty');box.append(el('h2',title),el('p',copy));return box;}
function renderProposals(){const items=(data.proposals||[]).filter(p=>p.status==='open'),root=$('proposals');root.hidden=!items.length;root.replaceChildren();for(const proposal of items){const details=el('details',null,'card');details.append(el('summary','AI 提交了'+(titles[proposal.stage]||proposal.stage)+'修改建议，尚未替换人工内容'));const diff=el('div',null,'diff');const before=proposal.stage==='script'?data.editor.text:readable(data[proposal.stage]||data.plan);const after=proposal.stage==='script'?(proposal.candidate.sections||[]).map(s=>s.body).join('\n\n'):readable(proposal.candidate);diff.append(el('pre','当前内容\n\n'+before),el('pre','AI 建议\n\n'+after));details.append(diff,button('采用这份建议',()=>action('adopt',{id:proposal.id})));root.append(details);}}
function readable(value){if(Array.isArray(value))return value.map(readable).join('\n\n');if(value&&typeof value==='object')return ['title','audience','performance_task','statement','teaching_goal','activity','teaching_method','method','opening','action','result','focus','script_excerpt'].map(k=>value[k]||'').filter(Boolean).join('\n')+'\n'+['content_points','objectives','units','segments','options'].filter(k=>value[k]).map(k=>readable(value[k])).join('\n');return String(value||'');}
function needsGeneration(){return stage==='script'&&!data.editor.text?.trim()||stage==='storyboard'&&!data.storyboard?.segments?.length||stage==='pilot'&&!data.gates.find(g=>g.id==='pilot')?.ready;}
function stageReview(){return reviews.state||data.ai_review;}
function stageConfirmed(id){
  const review=stageReview();
  if(review?.enabled)return review.nodes?.[id]?.user_confirmed===true;
  return data.gates?.some(g=>g.id===id&&['confirmed','delivered'].includes(g.status));
}
function atConfirmationGate(){
  if(!confirmationStages.has(stage))return false;
  if(stageConfirmed(stage))return false;
  if((data.pending_confirmations||[]).some(item=>item.stage===stage))return true;
  const g=data.gates.find(g=>g.id===stage);
  const review=stageReview()?.nodes?.[stage];
  if(g?.status==='stale'||review?.status==='stale')return false;
  return stage==='script'?!!data.editor.text?.trim():!!g?.ready;
}
function recoveryState(){return exportRecovery(progressJobs.length?progressJobs:data.jobs,stage,aiBusy);}
function primaryState(){
  const primary=$('primary'),review=stageReview()?.nodes?.[stage];
  const labels={sources:'生成大纲',outline:data.plan.units.length?'确认大纲，生成逐字稿':'生成大纲',
    script:stageConfirmed('script')?'制作分镜':'生成逐字稿',storyboard:needsGeneration()?'生成全课分镜':'制作三段有声小样',
    pilot:stageConfirmed('pilot')?'制作整课':'继续制作三段有声小样',
    final:stageConfirmed('final')?'保存成片到桌面':'开始制作成片'};
  const rendering=activeJobs(progressJobs)||activeJobs(data.jobs);
  primary.hidden=finalPhase==='body'||atConfirmationGate()||aiBusy||rendering;
  primary.textContent=recoveryState()?.label||(rendering?'视频正在合成…':aiBusy?'AI 正在制作…':labels[stage]);
  primary.disabled=aiBusy||rendering||primary.hidden;
  $('production-preferences').disabled=aiBusy||rendering;
  const prerequisite={script:'outline',storyboard:'script',pilot:'storyboard',final:'pilot'}[stage];
  if(prerequisite&&!data.gates.some(g=>g.id===prerequisite&&g.status==='confirmed'))primary.disabled=true;
  if(stage==='script'&&data.editor.text?.trim()&&!data.mapped)primary.disabled=true;
  if(stage==='storyboard'&&!needsGeneration()&&!data.gates.find(g=>g.id===stage)?.ready)primary.disabled=true;
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.required&&(!data.production_preferences.ready||!data.production_preferences.storyboard_current)){primary.textContent='按制作偏好更新分镜';primary.disabled=primary.hidden||aiBusy||rendering||!data.gates.some(g=>g.id==='script'&&g.status==='confirmed');}
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.choices?.customer==='new'&&!data.production_preferences.new_customer_ready){primary.textContent='设计新增顾客并更新分镜';primary.disabled=primary.hidden||aiBusy||rendering||!data.gates.some(g=>g.id==='script'&&g.status==='confirmed');}
  if(data.ai_review?.enabled&&stage==='storyboard'&&!needsGeneration()&&!review?.passed){primary.textContent='分镜检查由 AI 推进';primary.disabled=true;}
}
function render(){
  if(data.review_context==='qa-simulation')notice('独立验证课程：当前操作记录为技术模拟，不代表正式业务课内容验收。');
  pause();$('course-title').textContent=data.title;$('stage-kicker').textContent=finalPhase==='body'?'画面与配音':finalPhase==='post'?'后期与成片':titles[stage]||'课程工作台';$('save-status').textContent=serial===savedSerial?'已保存':'正在保存…';$('undo').disabled=!data.undo_available;renderProposals();
  const root=$('content');root.replaceChildren();overview.mount(root);({sources:sourcesView,outline:outlineView,script:scriptView,storyboard:storyboardView,pilot:samplesView,final:finalView}[stage]||outlineView)(root);pendingPanel(root);overview.mountHistory(root);
  primaryState();paintProgress();sourceCoverage.sync();
}
$('undo').onclick=()=>action('undo').catch(e=>notice(e.message,true));
$('production-preferences').onclick=()=>productionPreferences.open();
async function runPrimary(){try{
  $('primary').disabled=true;await save();
  const review=stageReview()?.nodes?.[stage],recovery=recoveryState();
  if(finalPhase==='body')return;
  if(atConfirmationGate()){notice('等 AI 在右侧对话发起本节点的确认。');return;}
  if(data.ai_review?.enabled&&stage==='storyboard'&&!needsGeneration()&&!review?.passed)return;
  if(stage==='final'&&stageConfirmed('final')){notice('正在校验并保存成品，过程文件保留…');await host('deliver');return;}
  let target;
  if(stage==='sources'||stage==='outline'&&!data.plan.units.length)target='outline';
  else if(stage==='final'||needsGeneration()||confirmationStages.has(stage)&&!stageConfirmed(stage))target=stage;
  else target={outline:'script',script:'storyboard',storyboard:'pilot',pilot:'final'}[stage];
  if(['storyboard','pilot','final'].includes(target)&&productionPreferences.pending){productionPreferences.open({continueWith:runPrimary});return;}
  if(data.production_preferences?.required&&!data.production_preferences.storyboard_current&&['pilot','final'].includes(target))target='storyboard';
  if(data.production_preferences?.choices?.customer==='new'&&!data.production_preferences.new_customer_ready&&['pilot','final'].includes(target))target='storyboard';
  if(target!==stage&&stage==='outline'&&!needsGeneration()&&data.plan.units.length)await action('confirm',{stage});
  const result=await host('stage',{target_stage:target,context_stage:stage,instruction:(recovery?'恢复当前阶段上次未完成的制作任务 '+recovery.job_id+'。先核对已保存的当前版讲稿、配音、画面和缓存，沿用有效文件，从失败环节继续，不重复生成或重开审阅。':'')+'仅完成本次目标阶段并保存实际成果，随后停在对应审阅页。沿用本会话已核对的原件、环境与有效选择，避免重复建课或重复读取无变化的资料；本机工作台使用插件工具读取，无需互联网网页获取。制作偏好：'+productionPreferenceSummary(data.production_preferences)+'。必须读取production-preferences.json；新增顾客按本课设计不同发型与衣服的同风格多部件vectorActor，先展示实际设计供采用，不能用整张PNG或断手占位；启用花字/音效后检查真实编码并按production_handoff的implementation_review登记，不以计划代替接入。若本课标注为验证课，沿用其技术模拟范围，不代表正式课验收。'});
  notice(result.executor==='computer'?'已复用当前成果提交实际合成任务。':'已交给当前课程的 AI，完成后在对应阶段展示。');
}catch(e){notice(e.message,true);}finally{if($('primary'))primaryState();}}
$('primary').onclick=runPrimary;
window.addEventListener('beforeunload',event=>{if(serial!==savedSerial){event.preventDefault();event.returnValue='';}});
window.addEventListener('pagehide',()=>{closed=true;pause();clearTimeout(pollTimer);clearTimeout(saveTimer);clearTimeout(previewTimer);});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();else if(data)schedulePoll();});
startActivity(()=>serial!==savedSerial||pending.size>0||aiBusy||activeJobs(progressJobs)||activeJobs(data?.jobs),()=>playing,{document,window,fetch,location});
async function boot(){try{data=await api('/api/studio');const recovery=JSON.parse(localStorage.getItem(draftKey())||'null');if(recovery){if(recovery.baseRevision===data.revision){notice('已恢复离开前未保存的编辑，请核对后继续。');if(recovery.units&&stage==='outline'){data.plan.units=recovery.units;Object.assign(data.plan,recovery.plan_fields||{});}if(recovery.sections&&stage==='script')data.sections=recovery.sections;serial=1;}else{notice('发现离开前的编辑；课程已有其他更新。原输入仍保留，请核对后选择恢复。');$('notice').append(button('恢复离开前的编辑',()=>{if(recovery.units){data.plan.units=recovery.units;Object.assign(data.plan,recovery.plan_fields||{});}if(recovery.sections)data.sections=recovery.sections;serial=1;render();}));}}render();announce();schedulePoll();}catch(e){notice(e.message,true);}}
const ready=boot().then(()=>{if(data?.production_preferences?.required&&productionPreferences.pending&&['storyboard','pilot','final'].includes(stage)&&finalPhase!=='body'&&!aiBusy)productionPreferences.open();});

return {ready,dispose(){window.dispatchEvent(new Event('pagehide'));}};
}
if(globalThis.document?.getElementById('course-title'))mountStudio();

return {mountStudio};})();
const {mountStudio}=modules.studio;
// Built with the same workbench modules, without a second implementation.
function mountNative(host,{sourceURL,resourceBase,fetch,onMessage}){
  const root=host.shadowRoot||host.attachShadow({mode:'open'}),controller=new AbortController();
  const layout=':host{display:block;flex:1;min-width:0;min-height:0;width:100%;overflow:auto;container-type:inline-size} @container(max-width:900px){.script-grid,.source-grid,.story-grid{grid-template-columns:minmax(0,1fr)}header{flex-wrap:wrap}header>div{flex-basis:100%}#content{padding:18px}}';
  root.innerHTML='<style>'+STUDIO_CSS.replace(':root',':host')+layout+'</style><div id="native-body">'+STUDIO_HTML+'</div>';
  const body=root.getElementById('native-body'),realDocument=host.ownerDocument;
  const document=new Proxy(realDocument,{get(target,key){
    if(key==='body')return body;
    if(key==='activeElement')return root.activeElement||target.activeElement;
    if(key==='getElementById')return root.getElementById.bind(root);
    if(key==='querySelector')return root.querySelector.bind(root);
    if(key==='querySelectorAll')return root.querySelectorAll.bind(root);
    if(key==='addEventListener')return (name,fn,options={})=>target.addEventListener(name,fn,typeof options==='boolean'?{capture:options,signal:controller.signal}:{...options,signal:controller.signal});
    const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});
  const window=new EventTarget(),parent={postMessage:data=>onMessage(data)};
  const url=new URL(sourceURL),origin=globalThis.location.origin;
  const receive=data=>{
    const event=new Event('message');Object.defineProperties(event,{data:{value:data},source:{value:parent},origin:{value:origin}});window.dispatchEvent(event);
  };
  const resourceFetch=(path,options={})=>{
    const value=String(path),target=value.startsWith(resourceBase)?value:resourceBase+value;
    return fetch(target,{...options,signal:options.signal||controller.signal});
  };
  const view=mountStudio({document,window,parent,fetch:resourceFetch,location:{search:url.search,protocol:url.protocol},resourceBase,native:true});
  return {receive,ready:view.ready,dispose(){view.dispose();controller.abort();root.replaceChildren();}};
}

return {mountNative};
}});
