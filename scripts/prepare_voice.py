"""Download a pinned public Qwen3 model; no text or credentials leave the machine."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);a=p.parse_args()
    from huggingface_hub import snapshot_download
    model=json.loads((a.root/'config/voice-model.json').read_text());folder=a.data/'voice';folder.mkdir(parents=True,exist_ok=True)
    path=snapshot_download(model['repo'],revision=model['revision'],local_dir=folder/'model',token=False)
    candidate=dict(provider='qwen3_tts',model=str(Path(path).resolve()),python=sys.executable,voice_id='Aiden',language='auto',instruct=None,speed=1.0,temperature=.65,top_p=.9,repetition_penalty=1.05,seed=20261019,max_tokens=4096,stream=False,model_repository=model['repo'],model_revision=model['revision'])
    current=json.loads(a.config.read_text()) if a.config.exists() else {}
    configuration={**candidate,**current}
    check_config=folder/'install-voice-config.json';check_config.write_text(json.dumps(configuration,ensure_ascii=False,indent=2)+'\n')
    config_hash=hashlib.sha256(check_config.read_bytes()).hexdigest();proof=folder/'setup-proof.json';audio=folder/'setup-test.wav';sidecar=audio.with_suffix('.wav.json')
    previous=json.loads(proof.read_text()) if proof.exists() else {}
    valid=previous.get('configuration_sha256')==config_hash and audio.is_file() and previous.get('audio_sha256')==hashlib.sha256(audio.read_bytes()).hexdigest()
    if not valid:
        # Only installer-generated probe files can be replaced, never course audio.
        for file in [audio,sidecar]:
            if file.exists():file.unlink()
        text=folder/'setup-test.txt';text.write_text('酷果星创 Welcome 编号2026\n')
        subprocess.run([sys.executable,str(a.skill/'scripts/qwen3_tts.py'),'--config',str(check_config),'--text-file',str(text),'--out',str(audio)],check=True)
        meta=json.loads(sidecar.read_text())
        if meta['voice_id']!='Aiden' or meta['speed']!=1.0:raise ValueError('已有配音配置未使用Aiden原速 已保留配置 请核对后重跑')
        with wave.open(str(audio),'rb') as w:
            if not .2<w.getnframes()/w.getframerate()<30:raise ValueError('配音自检时长异常')
        result=dict(status='pass',configuration_sha256=config_hash,model_revision=model['revision'],voice_id=meta['voice_id'],speed=meta['speed'],duration_seconds=meta['duration_seconds'],audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())
        proof.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    a.config.parent.mkdir(parents=True,exist_ok=True)
    if not a.config.exists():a.config.write_text(json.dumps(configuration,ensure_ascii=False,indent=2)+'\n')
    print('Qwen3-TTS 已部署并通过 Aiden 原速短句生成检查；模型与检查音频位于用户数据目录。')


if __name__=='__main__':main()
