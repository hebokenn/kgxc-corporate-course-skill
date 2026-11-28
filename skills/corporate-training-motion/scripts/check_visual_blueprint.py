#!/usr/bin/env python3
"""v9.0.0 Episode Visual Diversity Blueprint validator & Markdown table generator.

Prevents AI minimal-path template recycling before any rendering code is written by checking:
1. Single L1 headline per non-store scene (no stacked double titles).
2. Zero same-screen data duplication between primary visual and secondary/insight zone.
3. Single-use cap (<= 1 per episode) for built-in chart primitives (encouraging custom business visuals).
4. No adjacent non-store scene cloning of identical (layout_skeleton + primary_visual).
5. Capsule/floating-tag restraint (discouraging floating pill walls).
"""
import argparse
import json
import re
from pathlib import Path

BUILTIN_SINGLE_USE_CHARTS = {
    'sculpture_bar', 'vertical_bar', 'horizontal_bars', 'horizontal_spotlight_bars',
    'pictogram_grid', 'journey_funnel', 'kpi_rail', 'pie_chart', 'donut_chart',
}

REDUNDANT_ROLE_PATTERNS = re.compile(
    r'(duplicate|repeat_chart|mirror_kpi|same_data|copy_left|重复|复述|镜像指标)',
    re.IGNORECASE,
)


def _norm(val) -> str:
    return str(val or '').strip().lower()


def validate_blueprint(data) -> dict:
    scenes = data.get('scenes') if isinstance(data, dict) else data
    episode = data.get('episode', '') if isinstance(data, dict) else ''
    errors = []
    warnings = []

    if not isinstance(scenes, list) or not scenes:
        return {
            'ok': False,
            'episode': episode,
            'scene_count': 0,
            'errors': ['视觉多样性蓝图缺少有效的 scenes 列表'],
            'warnings': [],
            'pattern_counts': {},
            'custom_visual_count': 0,
        }

    pattern_scenes = {}
    custom_visual_count = 0
    non_store_count = 0
    prev_non_store = None
    seen_ids = set()

    for idx, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            errors.append(f'第 {idx + 1} 项场景格式无效（必须为对象）')
            continue
        sid = str(sc.get('scene_id') or '').strip()
        if not sid:
            errors.append(f'第 {idx + 1} 项缺少 scene_id')
            continue
        if sid in seen_ids:
            errors.append(f'场景 ID 重复: {sid}')
        seen_ids.add(sid)

        lk = _norm(sc.get('layout_kind') or 'kinetic_metaphor')
        skeleton = _norm(sc.get('layout_skeleton'))
        primary = _norm(sc.get('primary_visual'))
        secondary = str(sc.get('secondary_role') or '').strip()
        l1 = str(sc.get('l1_headline') or '').strip()
        callout = _norm(sc.get('callout_style'))

        if not skeleton:
            errors.append(f'{sid}: 缺少 12 栏版式骨架 layout_skeleton（如 grid_7_5 / grid_5_7 / full_journey / store_wide）')
        if not primary:
            errors.append(f'{sid}: 缺少唯一主视觉形态 primary_visual')

        if lk != 'cinematic_store':
            non_store_count += 1
            if not l1:
                errors.append(f'{sid}: 非实景场景必须声明唯一 L1 观点标题 l1_headline')
            if isinstance(sc.get('headline_count'), int) and sc['headline_count'] > 1:
                errors.append(f'{sid}: 声明了 {sc["headline_count"]} 套主标题（上限 1 套），禁止双标题叠罗汉')

        if sc.get('duplicates_primary_data') is True or (secondary and REDUNDANT_ROLE_PATTERNS.search(secondary)):
            errors.append(
                f'{sid}: 辅助区 secondary_role ("{secondary}") 与主视觉重复展示同一组数据，请改为留白或更高一维的洞察/归因'
            )

        if callout == 'floating_pill_wall' or (isinstance(sc.get('capsule_count'), int) and sc['capsule_count'] > 2):
            errors.append(
                f'{sid}: 漂浮圆角胶囊过多（callout_style={callout or "default"}, capsule_count={sc.get("capsule_count")}），请改用无框排版 + 细引导线 Callout'
            )

        is_custom = primary.startswith('custom:') or primary.startswith('custom_') or _norm(secondary).startswith('custom:')
        if is_custom:
            custom_visual_count += 1

        if not (primary.startswith('custom:') or primary.startswith('custom_')) and primary in BUILTIN_SINGLE_USE_CHARTS:
            pattern_scenes.setdefault(primary, []).append(sid)

        if lk != 'cinematic_store':
            if (
                prev_non_store is not None
                and skeleton
                and primary
                and prev_non_store['skeleton'] == skeleton
                and prev_non_store['primary'] == primary
            ):
                errors.append(
                    f'{sid}: 与前一非实景场景 {prev_non_store["scene_id"]} 复用了相同的版式骨架 ({skeleton}) 与主视觉形态 ({primary})，请切换构图或图形语言'
                )
            prev_non_store = {'scene_id': sid, 'skeleton': skeleton, 'primary': primary}

    for pat, sids in sorted(pattern_scenes.items()):
        if len(sids) > 1:
            errors.append(
                f'同一集内内置图表原语 "{pat}" 重复出现 {len(sids)} 次（上限 1 次）：{", ".join(sids)}；请替换为其他图形或业务定制原生图形 (custom:*)'
            )

    if non_store_count >= 4 and custom_visual_count == 0:
        errors.append(
            f'本集有 {non_store_count} 个非实景信息场景，但未规划任何业务现场定制图形 (custom:*)；严禁整集纯套内置组件排列组合'
        )

    return {
        'ok': not errors,
        'episode': episode,
        'scene_count': len(scenes),
        'non_store_scene_count': non_store_count,
        'custom_visual_count': custom_visual_count,
        'pattern_counts': {k: len(v) for k, v in pattern_scenes.items()},
        'errors': errors,
        'warnings': warnings,
    }


def render_markdown_table(data) -> str:
    scenes = data.get('scenes') if isinstance(data, dict) else data
    episode = data.get('episode', '未命名剧集') if isinstance(data, dict) else '未命名剧集'
    lines = [
        f'# 全集视觉多样性蓝图 · {episode}',
        '',
        '| 场景 | 类型 | 12 栏骨架 | L1 唯一标题 | 主视觉形态 | 辅助/洞察区（零数据复述） | 标注方式 |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for sc in scenes or []:
        if not isinstance(sc, dict):
            continue
        lines.append(
            f'| {sc.get("scene_id", "")} | {sc.get("layout_kind", "")} | {sc.get("layout_skeleton", "")} '
            f'| {sc.get("l1_headline", "—")} | {sc.get("primary_visual", "")} '
            f'| {sc.get("secondary_role", "none")} | {sc.get("callout_style", "leader_line")} |'
        )
    lines.append('')
    return '\n'.join(lines)


def check_blueprint_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    return validate_blueprint(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('blueprint', type=Path, help='Path to visual-blueprint.json')
    p.add_argument('--markdown-out', type=Path, help='Optional path to write human-readable Markdown schedule')
    args = p.parse_args()
    data = json.loads(args.blueprint.read_text(encoding='utf-8'))
    res = validate_blueprint(data)
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown_table(data), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
