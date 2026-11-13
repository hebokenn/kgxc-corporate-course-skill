// Built with the same workbench modules, without a second implementation.
export function mountNative(host,{sourceURL,resourceBase,fetch,onMessage}){
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
