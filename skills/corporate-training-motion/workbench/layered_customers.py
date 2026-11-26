"""Extensible 3.3-head cute customer presets for CourseActorsCute (actors_v3_cute.js)."""
import copy
import hashlib

PRESETS = {
    'C_M01': dict(
        label='便装男顾客（圆框眼镜）',
        description='短发、圆框眼镜、灰蓝外套 + 浅雾蓝内搭（不顺色）',
        appearance=dict(
            identity='C_M01', characterRole='customer', role='cust_jacket',
            hairStyle='casual_short', hairColor='#4D3B35', hairLight='#745B53',
            skin='#FCDAC2', glasses=True, shirtColor='#8392A6', innerColor='#D5E1EE',
            pantsColor='#3A4354', shoeColor='#FFFFFF', showKG=False
        )
    ),
    'C_F01': dict(
        label='便装女顾客（微卷短发）',
        description='微卷短发、耳环、橘棕针织衫（无员工标）',
        appearance=dict(
            identity='C_F01', characterRole='customer', role='cust_knit',
            hairStyle='fluffy_bob', hairColor='#5E3D36', hairLight='#875B52',
            skin='#FFE3D1', glasses=False, accessory='earring', shirtColor='#D48063',
            pantsColor='#454B5C', shoeColor='#FAF5EC', showKG=False
        )
    ),
}


def catalog():
    return [
        dict(
            id=key, label=item['label'], description=item['description'],
            representation='course-actors-cute/3', design=copy.deepcopy(item['appearance'])
        )
        for key, item in PRESETS.items()
    ]


def design_for_course(course_id, identity, appearance=None):
    """A reproducible starting design for CourseActorsCute; extend hairstyles/outfits as needed."""
    if not isinstance(course_id, str) or not course_id or not isinstance(identity, str) or not identity:
        raise ValueError('人物设计需要当前课程ID和独立人物ID')
    seed = hashlib.sha256((course_id + '\0' + identity).encode()).digest()
    hair_opts = [
        ('casual_short', '#4D3B35', '#745B53'),
        ('fluffy_bob', '#5E3D36', '#875B52'),
        ('manager_short', '#2B2A2F', '#514F58'),
        ('bun_pony', '#3A2E31', '#614E52'),
    ]
    hairStyle, hairColor, hairLight = hair_opts[seed[0] % len(hair_opts)]
    clothes = [
        ('cust_jacket', '#8392A6', '#D5E1EE'),
        ('cust_knit', '#D48063', '#D5E1EE'),
        ('cust_jacket', '#6E857B', '#DCE6DF'),
        ('cust_knit', '#7D74A8', '#E2DEF0'),
    ][seed[1] % 4]
    result = dict(
        identity=identity, characterRole='customer', role=clothes[0],
        hairStyle=hairStyle, hairColor=hairColor, hairLight=hairLight,
        skin=['#FCDAC2', '#FFE0CC', '#FFE3D1'][seed[2] % 3],
        glasses=bool(seed[3] % 2), shirtColor=clothes[1], innerColor=clothes[2],
        pantsColor=['#3A4354', '#454B5C', '#343C4C'][seed[4] % 3],
        shoeColor='#FFFFFF', showKG=False
    )
    for key, value in (appearance or {}).items():
        if key in ['hairStyle', 'hairColor', 'hairLight', 'skin', 'glasses', 'accessory',
                   'role', 'shirtColor', 'innerColor', 'pantsColor', 'shoeColor']:
            result[key] = value
    result['showKG'] = False
    return result
