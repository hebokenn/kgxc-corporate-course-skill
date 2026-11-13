"""Named device geometry. References describe a model; course state stays separate.

These are editable educational drawings, not Apple artwork or OS screenshots.
Measurements constrain the chassis ratio. Lens coordinates are traced by eye
from the linked official views and remain an illustration, not CAD dimensions.
"""

IPHONE_18_PRO = {
    'id': 'iphone-18-pro', 'label': 'iPhone 18 Pro',
    'widthMm': 71.9, 'heightMm': 150.0, 'depthMm': 8.75,
    'displayPixels': [1206, 2622], 'os': 'iOS 27',
    'checkedOn': '2026-10-21',
    'references': [
        'https://www.apple.com.cn/iphone-18-pro/specs/',
        'https://www.apple.com.cn/v/iphone-18-pro/c/images/overview/product-viewer/3d_viewer__hgotqf9hvvee_large.jpg',
        'https://www.apple.com.cn/v/iphone-18-pro/c/images/overview/product-viewer/color_glacier__fkxlpbz0ruy6_large.jpg',
    ],
    'finishes': {
        'glacier-blue': {'label': '冰川蓝色', 'edge': '#b3c4dd', 'plate': '#9faec4', 'glass': '#afbed4', 'dark': '#7e8fa8'},
        'silver': {'label': '银色', 'edge': '#e2e3e7', 'plate': '#c9cdd3', 'glass': '#e4e7eb', 'dark': '#9da4af'},
        'black': {'label': '黑色', 'edge': '#505257', 'plate': '#34383e', 'glass': '#2b2e34', 'dark': '#1d2228'},
        'burgundy': {'label': '勃艮第酒红色', 'edge': '#845961', 'plate': '#64424a', 'glass': '#5d3a43', 'dark': '#3e2831'},
    },
}


def profile(model, finish='glacier-blue'):
    if model != IPHONE_18_PRO['id']:
        raise ValueError('未知的具名手机型号：'+str(model))
    if finish not in IPHONE_18_PRO['finishes']:
        raise ValueError('该机型没有已实现的配色：'+str(finish))
    w = 274
    h = w * IPHONE_18_PRO['heightMm'] / IPHONE_18_PRO['widthMm']
    sw = 254
    sh = sw * IPHONE_18_PRO['displayPixels'][1] / IPHONE_18_PRO['displayPixels'][0]
    return dict(width=w, height=h, screenWidth=sw, screenHeight=sh,
                screenX=(w-sw)/2, screenY=(h-sh)/2,
                finish=IPHONE_18_PRO['finishes'][finish], metadata=IPHONE_18_PRO)


def shell(b, view, p, gradient):
    w,h=p['width'],p['height'];f=p['finish']
    if view=='side':
        x=w*.45;depth=w*IPHONE_18_PRO['depthMm']/IPHONE_18_PRO['widthMm']
        return [b.rect('side-frame',x,0,depth,h,gradient(f['edge'],f['dark'],depth,0),radius=9),
                b.rect('side-display',x+depth-3,5,3,h-10,'#11151c',radius=2),
                b.rect('side-power',x+depth-1,147,3,60,f['dark'],radius=2),
                b.rect('side-camera-control',x+depth-1,365,3,59,f['dark'],radius=2),
                b.rect('side-camera-plate',x-9,18,10,158,f['plate'],radius=5),
                b.rect('side-camera-lens',x-16,42,8,102,f['dark'],radius=3)]
    n=[b.rect('shadow',7,10,w,h,'#2335451a',radius=41),
       b.rect('rim',0,0,w,h,gradient(f['edge'],f['dark'],w,h),radius=41),
       b.rect('rim-highlight',2,2,w-4,h-4,None,stroke=f['edge'],lineWidth=1.5,radius=39),
       b.rect('body',4,4,w-8,h-8,'#0d1118' if view=='front' else f['plate'],radius=37),
       b.rect('action-button',-2,81,3,23,f['dark'],radius=2),
       b.rect('volume-up',-2,124,3,44,f['dark'],radius=2),
       b.rect('volume-down',-2,181,3,44,f['dark'],radius=2),
       b.rect('power',w-1,151,3,61,f['dark'],radius=2),
       b.rect('camera-control',w-1,365,3,58,f['dark'],radius=2)]
    if view=='back':
        n.extend([b.rect('back-glass',16,184,w-32,h-200,gradient(f['glass'],f['plate'],w,h),radius=28),
                  b.rect('camera-plate-shadow',9,14,w-18,166,f['dark'],radius=31),
                  b.rect('camera-island',7,9,w-14,165,gradient(f['edge'],f['plate'],w,165),radius=31)])
        for i,(x,y) in enumerate([(57,55),(57,127),(132,91)]):
            n.extend([b.ellipse('lens-rim-'+str(i),x,y,63,63,f['dark']),
                      b.ellipse('lens-metal-'+str(i),x,y,59,59,f['edge']),
                      b.ellipse('lens-glass-'+str(i),x,y,52,52,gradient('#04080e','#202634',52,52)),
                      b.ellipse('lens-optic-'+str(i),x,y,29,29,'#0b1020'),
                      b.ellipse('lens-coating-'+str(i),x-3,y-3,16,16,'#222946'),
                      b.ellipse('lens-reflection-'+str(i),x-6,y-7,6,4,'#a0a7c477')])
        n.extend([b.ellipse('flash-rim',w-44,48,24,24,f['dark']),
                  b.ellipse('flash',w-44,48,21,21,'#e9e9df'),
                  b.ellipse('flash-inner',w-44,48,12,12,'#d6d9d3'),
                  b.ellipse('microphone',w-42,92,3,3,'#1d252e'),
                  b.ellipse('lidar',w-44,133,23,23,'#080c12'),
                  b.path('apple-mark','M 140 300 C 146 289 151 288 154 288 C 154 296 149 301 140 302 Z M 139 306 C 151 299 165 309 166 315 C 155 320 155 333 166 338 C 161 349 154 358 147 355 C 139 351 136 351 128 355 C 118 359 108 341 107 329 C 104 312 118 300 130 306 C 134 308 136 308 139 306 Z',f['dark'],None),
                  b.path('antenna-left','M 1 69 L 8 69 M 1 466 L 15 466',None,f['edge'],2),
                  b.path('antenna-right',f'M {w-8} 69 L {w-1} 69 M {w-15} 466 L {w-1} 466',None,f['edge'],2)])
    return n


def front_overlay(b,p):
    w=p['width'];sx,sy=p['screenX'],p['screenY']
    return [b.rect('dynamic-island',w/2-28.5,sy+10,57,16,'#06090d',radius=8),
            b.ellipse('front-lens',w/2+18,sy+18,6,6,'#11182b'),
            b.ellipse('front-lens-glint',w/2+17,sy+17,2,2,'#42517c'),
            b.path('earpiece',f'M {w/2-24} 5 L {w/2+24} 5',None,'#080b11',1)]
