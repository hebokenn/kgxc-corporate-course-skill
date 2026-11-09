#!/usr/bin/env python3
"""Package our small, named-export browser modules into one DSH lazy chunk.

No eval, network dependency, or alternative UI: the original workbench is mounted.
Unsupported module syntax fails the build rather than silently producing drift.
"""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'skills/corporate-training-motion/workbench'
NAMES=['script-editor-model','timeline','activity','production-progress','production-preferences','source-coverage','review-panel','studio']

def build():
    chunks=[];available=set()
    for name in NAMES:
        source=(APP/(name+'.js')).read_text()
        def imported(match):
            dependency=match[2].removeprefix('/').removesuffix('.js')
            if dependency not in available:raise ValueError('Unresolved native module: '+dependency)
            return 'const {'+match[1]+'}=modules['+json.dumps(dependency)+'];'
        source=re.sub(r'^import\s*\{([^}]+)\}\s*from\s*[\'\"]([^\'\"]+)[\'\"];?',imported,source,flags=re.M)
        exports=re.findall(r'\bexport\s+(?:(?:async\s+)?function|const)\s+(\w+)',source)
        source=re.sub(r'\bexport\s+(?=(?:(?:async\s+)?function|const)\s)', '',source)
        if re.search(r'^\s*(?:import|export)\s',source,re.M):raise ValueError('Unsupported native module syntax: '+name)
        chunks.append('modules['+json.dumps(name)+']=(()=>{\n'+source+'\nreturn {'+','.join(exports)+'};})();')
        available.add(name)
    html=(APP/'studio.html').read_text().split('<body>',1)[1].rsplit('</body>',1)[0]
    html=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',html,flags=re.I)
    constants='const STUDIO_HTML='+json.dumps(html,ensure_ascii=False)+';\nconst STUDIO_CSS='+json.dumps((APP/'studio.css').read_text(),ensure_ascii=False)+';\n'
    entry=(ROOT/'plugin/studio-native-entry.js').read_text().replace('export function mountNative','function mountNative')
    content='// Generated from the shared workbench; run scripts/build_native_client.py.\nwindow.__ModuleLoader__.load({id:"kgxc-course-plugin",chunk:"client.studio-native.js",factory:()=>{\nconst modules={};\n'+constants+'\n'.join(chunks)+'\nconst {mountStudio}=modules.studio;\n'+entry+'\nreturn {mountNative};\n}});\n'
    target=ROOT/'plugin/client.studio-native.js';target.write_text(content)
    print('native workbench chunk:',target.name,len(content.encode()),'bytes')

if __name__=='__main__':build()
