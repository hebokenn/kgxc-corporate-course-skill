"""Executable motion inventory. Styles, easing and colour variants are not actions."""
BASE = {
    'chars-in': ('逐字进入', 'text'), 'text-rise': ('文字遮罩升起', 'text'),
    'blur-in': ('文字由虚到实', 'text'), 'typewriter': ('逐字书写', 'text'),
    'draw-on': ('按真实弧长描线', 'line path'), 'mask-reveal': ('对象遮罩揭示', '*'),
    'marker': ('重点底色标记', '*'), 'underline': ('下划线强调', '*'),
}
TEACHING = {
    'assemble': ('部件构建', 'group', '部件依次进入并组合成可使用的整体'),
    'explode': ('空间拆层', 'group', '整体沿空间轴分解成可对应的信息层'),
    'paper-fold': ('纸艺折页', 'group', '纸层沿折轴展开并带动折角与投影'),
    'scan': ('扫描检视', 'rect', '扫描线经过明确的检视范围'),
    'spotlight': ('主体聚光', 'rect', '压暗上下文并将视线聚焦到指定区域'),
    'magnify': ('局部放大', 'image', '保持原图与放大位置对应并显露细节'),
    'path-follow': ('沿业务路径移动', '*', '对象按真实路径与弧长到达目的位置'),
    'handoff': ('物件交接', '*', '物件从持有者移到接收者并停稳'),
    'sort': ('流程归位', 'group', '内容从各自初始位置排入目标顺序'),
    'group-collect': ('信息归组', 'group', '散开的证据移入各自对应类别'),
    'branch-grow': ('知识分枝', 'group', '主干之后依次生长分枝与末端知识'),
    'compare-wipe': ('对照揭示', 'group image', '沿分界显露第二种状态供直接比较'),
    'correct-replace': ('差异纠正', 'text', '旧信息向上退出并由已核实信息替换'),
    'count-up': ('数量累计', 'text', '数值从实际起值累计到可编辑终值'),
    'odometer': ('数位滚动', 'text', '各个数位沿自己的数字滚轮变化'),
    'bar-grow': ('数量条增长', 'rect', '数量长度从共同零点增长到对应值'),
    'ring-progress': ('比例圆环', 'ellipse', '沿圆周累计显示对应比例'),
    'area-fill': ('区域占比填充', 'rect', '从底部填充对应数量的区域'),
    'record-filter': ('记录筛选', 'group', '无关记录退出并重新排列保留记录'),
    'dot-aggregate': ('个体聚合', 'group', '独立记录按稳定身份聚合成结果'),
    'timeline-reflow': ('时段编排', 'group', '时间区间移动并改变实际覆盖位置'),
    'route-progress': ('步骤路径推进', 'path line', '业务路径依次贯通并保留完成轨迹'),
    'dialogue': ('分镜对话', 'group', '气泡出现并随说话方转移解释焦点'),
    'quiz-feedback': ('选择与反馈', 'group', '先选择再显露答案与解释'),
    'callout': ('引线标注', 'group', '引线抵达对象后显露对应标注'),
    'flow-token': ('关系流转', 'path line', '信息沿关系线传递而保留关系本身'),
    'presenter-gesture': ('品牌人物手势', 'image', '原品牌人物连续网格抬手与知识点协同'),
    'pixel-walk': ('任务闯关移动', '*', '对象按像素步进经过任务站并到达终点'),
    'split-merge': ('拆分再合并', 'group', '整体分开检视后重新合并并保持身份'),
    'balance': ('共同基线比较', 'group', '同尺度柱体从共同基线呈现差异'),
    'rotate-inspect': ('转面检查', 'group', '对象围绕中心转面以暴露另一侧信息'),
    'gauge-sweep': ('仪表指针', 'line', '指针沿量表角度移动到对应读数'),
    'threshold-cross': ('阈值判断', 'rect', '数量越过阈值后改变状态并保留阈值线'),
    'venn-intersect': ('范围交集', 'group', '两个范围相交并显示共同部分'),
    'swimlane-transfer': ('泳道职责交接', '*', '对象先跨职责边界再进入下一任务'),
    'parallel-sync': ('并行汇合', 'group', '独立任务完成后同步汇入共同节点'),
    'evidence-attach': ('证据归因', 'group', '证据依次连接到对应结论并保留来源关系'),
}
SYMBOLS = {
    'check-draw': ('完成勾选', 'path'), 'cross-draw': ('异常划除', 'path'),
    'brace-draw': ('范围括注', 'path'),
}
CATALOG = {
    **{k: dict(title=v[0], nodes=v[1].split(), category='text-or-emphasis', purpose=v[0]) for k,v in BASE.items()},
    **{k: dict(title=v[0], nodes=v[1].split(), category='teaching-action', purpose=v[2]) for k,v in TEACHING.items()},
    **{k: dict(title=v[0], nodes=v[1].split(), category='symbol', purpose=v[0]) for k,v in SYMBOLS.items()},
}

from motion_extensions import EXTENSIONS
CATALOG.update(EXTENSIONS)
# These before-stage transforms also support shape nodes with the same bounds.
CATALOG['paper-fold']['nodes'].append('rect')
CATALOG['dialogue']['nodes'].append('rect')
CATALOG['orbit-revolve']['nodes'].append('ellipse')


def inventory():
    from motion_demos import CASES
    return dict(schema='course-motion-catalog/1', count=len(CATALOG),
                teaching_actions=len(TEACHING)+len(EXTENSIONS), counted_as_variants=False,
                effects=[dict(id=k, **v,businessExample=dict(task=CASES[k][0],observe=CASES[k][1],objectFamily=CASES[k][2],scope='fictional teaching example; replace with the confirmed course objects and narration')) for k,v in CATALOG.items()])
