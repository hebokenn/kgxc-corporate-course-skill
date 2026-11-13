"""Build an offline 45-sound audition and a 30-second action/voice-free MP4."""
import argparse,base64,json,math,shutil,subprocess,wave
from pathlib import Path
from array import array
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'skills/corporate-training-motion/assets/sfx/natural-ui-v1'
C=json.loads((P/'palette.json').read_text());roles=list(dict.fromkeys(a['role'] for a in C['assets']))
LABELS={a['role']:a['label'] for a in C['assets']}

def page():
 data=[dict(id=a['id'],role=a['role'],label=a['label'],src='data:audio/wav;base64,'+base64.b64encode((P/a['path']).read_bytes()).decode()) for a in C['assets']]
 cards=''.join('<article><p>'+LABELS[r]+'</p><small>'+r+'</small><div class="samples">'+''.join('<button data-id="'+a['id']+'">试听 '+a['id'].split('-')[-1]+'</button>' for a in data if a['role']==r)+'</div></article>' for r in roles)
 html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>自然界面音效逐项试听</title><style>*{box-sizing:border-box}body{background:#f4f5f1;color:#183c3d;font:17px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;margin:0}main{max-width:1180px;margin:auto;padding:32px 24px 64px}h1{font-size:36px;margin:8px 0}p{margin:6px 0}small,.note{color:#637c7c}.bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:24px 0}button{border:1px solid #b9ceca;border-radius:6px;color:#183c3d;background:white;padding:8px 16px;font:inherit;cursor:pointer}button:hover{border-color:#cf2138}.primary{background:#cf2138;color:white;border-color:#cf2138}.stage{height:255px;border:1px solid #d4dfd9;background:#e8efea;position:relative;display:grid;place-items:center;overflow:hidden}.rail{width:65%;border-bottom:1px solid #abc3bd;position:absolute;top:65%}.block{width:105px;height:105px;background:#cf2138;border-radius:14px;box-shadow:0 12px 0 #bfd0ca;display:grid;place-items:center;color:white;font-size:45px;transform-origin:center;transition:none}.stage small{position:absolute;left:20px;bottom:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin-top:24px}article{background:white;border:1px solid #d4dfd9;padding:15px}article.playing{border-color:#cf2138}article p{font-size:20px}.samples{display:flex;gap:8px;margin-top:12px}.samples button{font-size:14px;padding:7px 11px}input{accent-color:#cf2138}</style><main><p class="note">酷果星创 · natural-ui-v1</p><h1>自然界面音效试听</h1><p>15 类动作 · 45 个常用变体 · 基于 Kenney CC0 界面素材</p><p class="note">先选一类试听，再比较三个变体。这里不含旁白；课程中会按讲话音量避让，并保留练习静音。</p><div class="bar"><button class="primary" id="all">连续试听 15 类</button><button id="stop">停止</button><label>音量 <input id="volume" type="range" min="0" max="1" step=".05" value=".9"></label><span id="now">选择下方音效</span></div><div class="stage" id="stage"><div class="rail"></div><div class="block" id="block">+</div><small id="action">实际素材逐项播放</small></div><section class="grid">CARDS</section><p class="note">原库 100 个 OGG 与许可说明随完整包保留。可以在课程中选择喜欢的声音，再调整音量与动作对齐。</p></main><script>
const sounds=DATA;let current=null,sequence=0,animation=null;const b=document.getElementById('block'),status=document.getElementById('now');const poses={click:[{transform:'scale(1)'},{transform:'scale(.88)'},{transform:'scale(1)'}],build:[{transform:'translateY(-85px)',opacity:0},{transform:'translateY(0)',opacity:1}],move:[{transform:'translateX(-240px)'},{transform:'translateX(240px)'}],'zoom-in':[{transform:'scale(.55)'},{transform:'scale(1.65)'}],'zoom-out':[{transform:'scale(1.65)'},{transform:'scale(.55)'}],appear:[{opacity:0,transform:'scale(.88)'},{opacity:1,transform:'scale(1)'}],disappear:[{opacity:1,transform:'scale(1)'},{opacity:0,transform:'scale(.88)'}],rotate:[{transform:'rotate(-95deg)'},{transform:'rotate(0deg)'}],grow:[{transform:'scaleY(.2)'},{transform:'scaleY(1.6)'}],shrink:[{transform:'scaleY(1.6)'},{transform:'scaleY(.2)'}],reveal:[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)'}],focus:[{filter:'brightness(1)'},{filter:'brightness(1.55)'},{filter:'brightness(1)'}],confirm:[{transform:'scale(.9)'},{transform:'scale(1.07)'},{transform:'scale(1)'}],transition:[{transform:'translateX(-110px)',opacity:0},{transform:'translateX(0)',opacity:1}],warning:[{transform:'translateX(0)'},{transform:'translateX(-10px)'},{transform:'translateX(8px)'},{transform:'translateX(0)'}]};
function halt(){if(current){current.pause();current.onended?.()}if(animation)animation.cancel();document.querySelectorAll('.playing').forEach(x=>x.classList.remove('playing'))}
async function play(s){halt();const el=document.querySelector('[data-id="'+s.id+'"]').closest('article');el.classList.add('playing');status.textContent=s.label+' · '+s.id;document.getElementById('action').textContent=s.role;b.textContent=s.role==='confirm'?'✓':s.role==='warning'?'!':'+';animation=b.animate(poses[s.role],{duration:s.role==='move'?650:450,easing:'cubic-bezier(.2,.75,.25,1)',fill:'forwards'});current=new Audio(s.src);current.volume=Number(document.getElementById('volume').value);const ended=new Promise(resolve=>{current.onended=resolve;current.onerror=resolve});try{await current.play();await ended}catch(e){status.textContent='播放失败 '+e.message}el.classList.remove('playing')}
document.querySelectorAll('[data-id]').forEach(x=>x.onclick=()=>{sequence++;play(sounds.find(s=>s.id===x.dataset.id))});document.getElementById('stop').onclick=()=>{sequence++;halt();status.textContent='已停止'};document.getElementById('all').onclick=async()=>{const token=++sequence;for(const s of sounds.filter(s=>s.id.endsWith('-1'))){if(sequence!==token)break;await play(s);await new Promise(r=>setTimeout(r,950))}if(sequence===token)status.textContent='15 类试听完毕'};document.getElementById('volume').oninput=e=>{if(current)current.volume=Number(e.target.value)};
</script></html>'''.replace('CARDS',cards).replace('DATA',json.dumps(data,ensure_ascii=False))
 (P/'audition.html').write_text(html)
 for name in ['License.txt','source.json']:shutil.copy2(P.parent/'kenney-interface-source'/name,P/name)

def video():
 from PIL import Image,ImageDraw,ImageFont
 output=ROOT/'docs/media/natural-ui-audition.mp4';output.parent.mkdir(parents=True,exist_ok=True)
 # Host font only for rendering the preview; not copied into the distributable.
 candidates=[Path('/System/Library/Fonts/PingFang.ttc'),ROOT/'skills/corporate-training-motion/assets/bookends/brand-font.ttf']
 font_path=next((p for p in candidates if p.is_file()),None)
 font=lambda n:ImageFont.truetype(str(font_path),n) if font_path else ImageFont.load_default()
 f52,f24,f18=font(52),font(24),font(18)
 total=30;fps=30;rate=48000;audio=array('h',[0])*(total*rate)
 for i,r in enumerate(roles):
  a=next(a for a in C['assets'] if a['role']==r)
  with wave.open(str(P/a['path']),'rb') as w:clip=array('h');clip.frombytes(w.readframes(w.getnframes()))
  at=round((i*2+.38)*rate)-a['peakSample']
  for j,v in enumerate(clip):
   if 0<=at+j<len(audio):audio[at+j]=v
 tmp=output.with_suffix('.wav')
 with wave.open(str(tmp),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(audio.tobytes())
 proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','-','-i',str(tmp),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(total),'-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
 for frame in range(total*fps):
  t=frame/fps;i=min(14,int(t//2));r=roles[i];p=min(1,max(0,(t-i*2-.12)/.5));u=1-(1-p)**3
  im=Image.new('RGB',(1280,720),'#f4f5f1');d=ImageDraw.Draw(im);d.text((64,38),'KGXC  /  NATURAL UI  /  15 ACTIONS',font=f24,fill='#657d7b');d.text((64,100),LABELS[r],font=f52,fill='#173b3b');d.text((66,178),r+'   ·   '+f'{i+1:02}/15',font=f24,fill='#657d7b');d.rounded_rectangle((64,245,1216,590),18,fill='#e7eeea');d.line((224,500,1056,500),fill='#b9ccc6',width=2)
  x,y,k,angle,alpha=640,414,1,0,1
  if r=='click':k=1-.14*math.sin(math.pi*u)
  if r=='build':y=330+84*u
  if r=='move':x=400+480*u
  if r=='zoom-in':k=.6+.9*u
  if r=='zoom-out':k=1.5-.9*u
  if r=='appear':alpha=u;k=.86+.14*u
  if r=='disappear':alpha=1-u;k=1-.14*u
  if r=='rotate':angle=-95*(1-u)
  h=110*(.25+1.2*u if r=='grow' else 1.45-1.2*u if r=='shrink' else k);w=110*k
  if r=='warning':x+=10*math.sin(u*math.pi*6)*(1-u)
  block=Image.new('RGBA',(300,300));bd=ImageDraw.Draw(block);col=(206,33,55,round(alpha*255));bd.rounded_rectangle((150-w/2,150-h/2,150+w/2,150+h/2),14,fill=col)
  if r=='confirm':bd.line((123,150,143,170,179,128),fill='white',width=8)
  elif r!='reveal':bd.line((136,150,164,150),fill='white',width=4);bd.line((150,136,150,164),fill='white',width=4)
  if angle:block=block.rotate(angle,resample=Image.Resampling.BICUBIC)
  if r=='reveal':block.paste((0,0,0,0),(round(95+110*u),0,300,300))
  im.paste(block,(round(x-150),round(y-150)),block);d.text((64,626),'Kenney Interface Sounds  ·  CC0  ·  curated 48 kHz WAV',font=f18,fill='#657d7b');d.rectangle((64,672,64+1152*(frame+1)/(total*fps),676),fill='#ce2137');proc.stdin.write(im.tobytes())
 proc.stdin.close();assert proc.wait()==0;tmp.unlink();print(output)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--video',action='store_true');args=a.parse_args();page()
 if args.video:video()
 print('Built offline audition: 45 sounds')
