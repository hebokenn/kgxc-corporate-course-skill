"""Decode exact numbered frames. Input seek times are not frame observations."""
from fractions import Fraction
from pathlib import Path
import json
import subprocess

def main_video(path):
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)],timeout=30))
    streams=[s for s in result['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
    if len(streams)!=1:raise ValueError('Exactly one main video stream required')
    return streams[0]

def extract(path,index,output,width=960):
    if type(index) is not int or index<0:raise ValueError('Actual nonnegative decoded frame index required')
    stream=main_video(path)
    filters=f'select=eq(n\\,{index})'+(f',scale={width}:-2' if width else '')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(path),'-map',f'0:{stream["index"]}',
                    '-vf',filters,'-fps_mode','passthrough','-frames:v','1','-y',str(output)],check=True,capture_output=True,timeout=120)
    if not Path(output).is_file() or not Path(output).stat().st_size:raise ValueError('Requested decoded frame is absent')
    return dict(decoded_frame=index,stream_index=stream['index'],time=float(Fraction(index)/Fraction(stream['avg_frame_rate'])),method='exact-decoded-frame-select')
