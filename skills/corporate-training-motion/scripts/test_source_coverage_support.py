"""Explicit source-accounting receipts for temporary, synthetic legacy tests only."""
from pathlib import Path
import tempfile


def confirm_fixture_coverage(course):
    # A test convenience must never become an approval path for a real course.
    if not Path(course.root).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('覆盖确认测试助手只适用于系统临时目录中的合成夹具')
    from source_coverage import SourceCoverage
    coverage=SourceCoverage(course);view=coverage.view()
    if not view['required'] or view['confirmed']:return view
    text,_=coverage._script();sources=view['sources'];originals=coverage._source_texts(sources)
    inventory=[];points=[]
    for index,source in enumerate(sources):
        original=originals.get(source['source_id']);readable=isinstance(original,str) and bool(original.strip())
        quote=original[:2000] if readable else '合成非文字来源：正文未提取，保留未验证范围'
        inventory.append(dict(source_id=source['source_id'],sha256=source['sha256'],read_scope='合成回归夹具当前完整文字' if readable else '合成回归夹具：仅核文件身份，正文未提取',
                              fully_read=readable,unreadable=[] if readable else ['本测试未验证非文字原件内容']))
        retained=bool(readable and quote in text)
        points.append(dict(id='FIXTURE-P'+str(index+1),source_id=source['source_id'],locator='合成原件全文' if readable else '未验证正文范围',source_quote=quote,
                           critical=False,disposition='retained' if retained else 'omitted',script_quotes=[quote] if retained else [],
                           reason='合成旧功能回归；原件对应内容保留' if retained else '合成旧功能回归；此原件与本测试稿差异明确记录，不代表正式课程内容质量验收'))
    additions=[dict(id='FIXTURE-ADDITION',script_quote=text,location='当前合成稿全文',reason='测试其他工作台功能所需的合成内容',basis_kind='example',basis='由测试夹具构造的虚构内容，不冒充原件结论')] if text.strip() else []
    report=dict(schema='source-coverage/1',source_inventory=inventory,points=points,additions=additions,
                notes='仅在临时合成课程中模拟测试操作员明确查看并确认覆盖说明；不用于真实业务资料或真实用户验收。')
    coverage.save(report,view['script_sha256'])
    return coverage.confirm(coverage.view()['report_sha256'],'合成测试操作员明确确认当前测试来源、舍弃及虚构新增范围',actor='dsh-user-click',source='synthetic-test-explicit-click')
