#!/usr/bin/env python3
"""Azure Speech adapter. Private config references credentials, never contains keys."""
import argparse
import array
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import wave
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from runtime import config_dir
DEFAULT_CONFIG = config_dir()/'azure.json'

def read_config(path):
    cfg = json.loads(Path(path).read_text())
    if cfg.get('provider') != 'azure' or not re.fullmatch(r'[a-z0-9]+', cfg['region']):
        raise ValueError('Invalid Azure provider/region')
    return cfg

def credential(cfg):
    ref = cfg['credential']
    if ref.get('type') == 'macos_keychain':
        proc = subprocess.run(['security','find-generic-password','-s',ref['service'],
                               '-a',ref['account'],'-w'],capture_output=True,text=True)
        if proc.returncode:
            raise ValueError('Azure Keychain credential unavailable')
        key = proc.stdout.rstrip('\n')
    elif ref.get('type') == 'environment':
        key = os.environ.get(ref['variable'],'')
    else:
        raise ValueError('Unsupported credential reference')
    if not key:
        raise ValueError('Azure credential is empty')
    return key

def request(cfg, path, data=None):
    url=f'https://{cfg["region"]}.tts.speech.microsoft.com/{path}'
    key=credential(cfg)
    if sys.platform=='darwin':
        # macOS curl verifies against system trust; no secret in argv or disk files.
        def quoted(value):
            return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'
        lines=['url = '+quoted(url), 'header = '+quoted('Ocp-Apim-Subscription-Key: '+key),
               'header = "Content-Type: application/ssml+xml"',
               'header = "X-Microsoft-OutputFormat: riff-48khz-16bit-mono-pcm"',
               'user-agent = "corporate-training-motion/1.1"']
        if data is not None: lines.append('data = '+quoted(data.decode('utf-8')))
        timeout_seconds=int(cfg.get('request_timeout_seconds',90))
        if not 10 <= timeout_seconds <= 600:
            raise ValueError('Request timeout must be between 10 and 600 seconds')
        proc=subprocess.run(['/usr/bin/curl','--silent','--show-error','--max-time',str(timeout_seconds),
                             '--write-out','\n%{http_code}','--config','-'],
                            input=('\n'.join(lines)+'\n').encode(),capture_output=True)
        if proc.returncode:
            raise ValueError(f'Azure transport failed (curl {proc.returncode}); not retried')
        body,status=proc.stdout.rsplit(b'\n',1)
        if status!=b'200':
            raise ValueError(f'Azure HTTP {status.decode()}; request not retried')
        return body
    req=urllib.request.Request(url,
        data=data,headers={'Ocp-Apim-Subscription-Key':key,
        'Content-Type':'application/ssml+xml','X-Microsoft-OutputFormat':'riff-48khz-16bit-mono-pcm',
        'User-Agent':'corporate-training-motion/1.1'})
    try:
        with urllib.request.urlopen(req,timeout=int(cfg.get('request_timeout_seconds',90))) as result:
            return result.read()
    except urllib.error.HTTPError as exc:
        # No raw response/headers: they can include sensitive request material.
        raise ValueError(f'Azure HTTP {exc.code}; request not retried') from None
    except (urllib.error.URLError,TimeoutError):
        raise ValueError('Azure network result uncertain; request not retried') from None

def voices(cfg):
    result=json.loads(request(cfg,'cognitiveservices/voices/list'))
    selected=[v for v in result if v.get('ShortName')==cfg['voice']]
    if not selected:
        raise ValueError('Requested voice absent from regional voice list; no fallback used')
    v=selected[0]
    return {k:v[k] for k in ('ShortName','LocalName','Locale','Gender','Status','StyleList','SampleRateHertz') if k in v}

def say(cfg,text,out,ssml=None):
    out=Path(out)
    sidecar=out.with_suffix(out.suffix+'.json')
    if out.exists() or sidecar.exists():
        raise ValueError('Output already exists; not overwriting approved/candidate audio')
    if not text.strip():
        raise ValueError('No text to synthesize')
    if ssml is None:
        ssml=(f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">'
              f'<voice name={quoteattr(cfg["voice"])}>{escape(text)}</voice></speak>')
    else:
        from xml.etree import ElementTree as ET
        root=ET.fromstring(ssml)
        allowed={'speak','voice','p','s','phoneme','break','sub','say-as'}
        nodes=list(root.iter());voices=[n for n in nodes if n.tag.rsplit('}',1)[-1]=='voice']
        if len(voices)!=1 or voices[0].get('name')!=cfg['voice']:
            raise ValueError('SSML must contain exactly the selected voice')
        if any(n.tag.rsplit('}',1)[-1]not in allowed for n in nodes):
            raise ValueError('Unsupported SSML element; no external media allowed')
    # Deliberately omit unsupported prosody/style parameters for first voice verification.
    audio=request(cfg,'cognitiveservices/v1',ssml.encode('utf-8'))
    if not audio.startswith(b'RIFF') or audio[8:12]!=b'WAVE':
        raise ValueError('Azure did not return requested WAV; response suppressed')
    out.parent.mkdir(parents=True,exist_ok=True)
    temporary=out.with_suffix(out.suffix+'.part')
    temporary.write_bytes(audio)
    try:
        with wave.open(str(temporary),'rb') as wav:
            frames=wav.getnframes();rate=wav.getframerate();channels=wav.getnchannels()
            if wav.getsampwidth()!=2 or frames==0 or rate!=48000 or channels!=1:
                raise ValueError('Unexpected or empty WAV format')
            samples=array.array('h',wav.readframes(frames))
        if sys.byteorder!='little': samples.byteswap()
        peak=max(abs(x) for x in samples)
        rms=math.sqrt(sum(x*x for x in samples)/len(samples))
        if peak==0 or rms<1:
            raise ValueError('Silent/near-empty audio; not accepted')
        metadata=dict(provider='azure',region=cfg['region'],requested_voice=cfg['voice'],
                      resolved_model_version=None,duration_sec=frames/rate,sample_rate=rate,
                      channels=channels,peak_dbfs=20*math.log10(peak/32768),
                      rms_dbfs=20*math.log10(rms/32768),
                      sha256=hashlib.sha256(audio).hexdigest(),
                      text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      ssml_sha256=hashlib.sha256(ssml.encode()).hexdigest(),
                      generated_at=datetime.now().astimezone().isoformat(),
                      alignment='none; measured utterance timing required',
                      review_status='candidate_not_listened_by_user')
        temporary.replace(out)
        sidecar.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        return metadata
    finally:
        if temporary.exists(): temporary.unlink()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    ap.add_argument('--allow-cloud',action='store_true',help='Only pass after actual user authorization')
    ap.add_argument('--voices',action='store_true')
    ap.add_argument('--text-file',type=Path)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--request-timeout',type=int,default=90,help='10-600 seconds; does not enable retries')
    args=ap.parse_args()
    if not args.allow_cloud: ap.error('Cloud authorization flag required')
    try:
        cfg=read_config(args.config)
        if not 10 <= args.request_timeout <= 600:
            raise ValueError('Request timeout must be between 10 and 600 seconds')
        cfg['request_timeout_seconds']=args.request_timeout
        if args.voices: result=voices(cfg)
        else:
            if args.text_file is None or args.out is None: ap.error('--text-file and --out required')
            result=say(cfg,args.text_file.read_text(),args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
