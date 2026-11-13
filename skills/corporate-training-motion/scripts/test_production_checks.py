#!/usr/bin/env python3
"""Exercise approval expiry and real media fixtures; no course content generated."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from media_check import check as media_check
from review_gate import check as review_check

def run():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        artifact = folder / 'script.md'
        artifact.write_text('Approved script fixture')
        assert review_check(folder, 'script')
        entry = dict(status='approved', reviewer='test fixture',
                     confirmed_at='2026-10-14T10:00:00+08:00',
                     user_confirmation='Fixture only, not real approval',
                     artifacts={'script.md': hashlib.sha256(artifact.read_bytes()).hexdigest()})
        records = {'source': entry, 'content': entry}
        (folder / 'approval_records.json').write_text(json.dumps(records))
        assert not review_check(folder, 'visual')
        assert any('visual' in e for e in review_check(folder, 'pilot'))
        artifact.write_text('Changed script fixture')
        assert any('APPROVAL_STALE' in e for e in review_check(folder, 'visual'))
        entry['artifacts'] = {'../outside.md': '0' * 64}
        (folder / 'approval_records.json').write_text(json.dumps(records))
        assert any('APPROVAL_PATH' in e for e in review_check(folder, 'visual'))

        silent, narrated = folder/'silent.mp4', folder/'audio.mp4'
        # Small technical fixture with test grid/sine. Never a narrated lesson.
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=320x180:rate=30:duration=0.5',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(silent)], check=True)
        assert any('MEDIA_AUDIO' in e for e in media_check(silent, 320, 180, 30))
        assert not media_check(silent, 320, 180, 30, False)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(silent), '-f', 'lavfi',
                        '-i', 'sine=frequency=440:duration=0.5', '-map', '0:v',
                        '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', str(narrated)], check=True)
        assert not media_check(narrated, 320, 180, 30)
        assert any('MEDIA_FPS' in e for e in media_check(narrated, 320, 180, 25))
        assert any('MEDIA_SIZE' in e for e in media_check(narrated))
        broken = folder/'broken.mp4'
        broken.write_text('not a media file')
        assert any('MEDIA_PROBE' in e for e in media_check(broken))
    print('PASS: 11 checks for missing approvals, expiry, paths, audio, FPS, size and corrupt media')

if __name__ == '__main__':
    run()
