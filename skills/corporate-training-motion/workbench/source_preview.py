"""Bounded, cached PDF page previews using the already installed Poppler tools."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import subprocess
import threading

_cache={}
_lock=threading.Lock()


def pdf_info(path):
    path=Path(path);stat=path.stat();key=(str(path),stat.st_size,stat.st_mtime_ns)
    if key in _cache:return dict(_cache[key])
    info={'pdf_preview_available':False}
    executable=shutil.which('pdfinfo');renderer=shutil.which('pdftoppm')
    if executable and renderer:
        try:
            result=subprocess.run([executable,str(path)],capture_output=True,text=True,timeout=8,env={**os.environ,'LC_ALL':'C'})
            match=re.search(r'^Pages:\s+(\d+)',result.stdout,re.M)
            if result.returncode==0 and match:info=dict(pdf_preview_available=True,pages=int(match[1]))
        except (OSError,subprocess.TimeoutExpired):pass
    if len(_cache)>=24:_cache.clear()
    _cache[key]=info
    return dict(info)


def render_pdf(space,source_id,page):
    from workflow import Course,read
    course=Course(space.root);source=next((s for s in read(course.plan_file)['sources'] if s['id']==source_id),None)
    if not source:raise ValueError('原件不存在')
    path=course.relative(source['location'])
    if path.suffix.lower()!='.pdf' or not path.is_file():raise ValueError('当前原件不是可预览的 PDF')
    info=pdf_info(path)
    if not info['pdf_preview_available']:raise ValueError('本机未提供 PDF 页预览，可使用“查看原件文件”打开原件')
    if not 1<=page<=min(info['pages'],2000):raise ValueError('PDF 页码超出范围')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    folder=space.project/'work/source-previews';target=folder/(digest[:24]+'-'+str(page)+'.png')
    with _lock:
        if not target.is_file():
            folder.mkdir(parents=True,exist_ok=True)
            result=subprocess.run([shutil.which('pdftoppm'),'-f',str(page),'-singlefile','-scale-to','1600','-png',str(path),str(target.with_suffix(''))],capture_output=True,timeout=30)
            if result.returncode or not target.is_file():raise ValueError('此页预览未能生成，可直接打开原件')
    return target
