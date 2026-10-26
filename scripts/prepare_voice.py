"""Install only the selected pinned model and prove that profile with real audio."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import wave


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--skill',type=Path,required=True);p.add_argument('--profile');a=p.parse_args()
    from huggingface_hub import snapshot_download
    sys.path.insert(0,str(a.skill/'scripts'))
    spec=importlib.util.spec_from_file_location('course_tts',a.skill/'scripts/qwen3_tts.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    current=json.loads(a.config.read_text()) if a.config.exists() else {}
    configuration=adapter.resolve(current,a.profile,library=a.config.parent/'voices')
    model=adapter.CATALOG['models'][configuration['mode']]
    folder=a.data/'voice';folder.mkdir(parents=True,exist_ok=True)
    local=Path(configuration['model']).expanduser()
    # Preserve a valid user model folder; otherwise fetch this profile only.
    if not local.is_dir():
        local=Path(snapshot_download(configuration['model_repository'],revision=configuration['model_revision'],local_dir=folder/('model-'+configuration['mode']),token=False))
    configuration.update(model=str(local.resolve()),python=sys.executable)
    paths=configuration.setdefault('model_paths',{});paths[configuration['mode']]=configuration['model']
    check_config=folder/'install-voice-config.json';check_config.write_text(json.dumps(configuration,ensure_ascii=False,indent=2)+'\n')
    config_hash=hashlib.sha256(check_config.read_bytes()).hexdigest();proof=folder/'setup-proof.json';audio=folder/'setup-test.wav';sidecar=audio.with_suffix('.wav.json')
    previous=json.loads(proof.read_text()) if proof.exists() else {}
    valid=previous.get('configuration_sha256')==config_hash and audio.is_file() and previous.get('audio_sha256')==hashlib.sha256(audio.read_bytes()).hexdigest()
    if not valid:
        for file in [audio,sidecar,audio.with_name('setup-test.raw.wav')]:
            if file.exists():file.unlink()
        text=folder/'setup-test.txt';text.write_text('现在计算客流 一百位顾客中有二十位成交 转化率是百分之二十\n')
        subprocess.run([sys.executable,str(a.skill/'scripts/qwen3_tts.py'),'--config',str(check_config),'--voice-library',str(a.config.parent/'voices'),'--text-file',str(text),'--out',str(audio)],check=True)
        meta=json.loads(sidecar.read_text())
        if meta['profile']!=configuration['profile']:raise ValueError('配音探针与所选声音不一致')
        with wave.open(str(audio),'rb') as w:
            if not .2<w.getnframes()/w.getframerate()<45:raise ValueError('配音自检时长异常')
        result=dict(status='pass',configuration_sha256=config_hash,model_revision=configuration['model_revision'],profile=meta['profile'],voice_id=meta['voice_id'],speed=meta['speed'],delivery_rate=meta['delivery_rate'],duration_seconds=meta['duration_seconds'],audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest())
        proof.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    a.config.parent.mkdir(parents=True,exist_ok=True)
    if a.config.exists() and a.profile:
        import datetime,shutil
        shutil.copy2(a.config,a.config.with_name('voice.backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json'))
    # Same selected profile, now with resolved local paths. No implicit profile migration.
    a.config.write_text(json.dumps(configuration,ensure_ascii=False,indent=2)+'\n')
    print('Qwen3-TTS '+configuration['profile']+' 已通过实际短句生成检查；音色与完整内容仍需试听。')


if __name__=='__main__':main()
