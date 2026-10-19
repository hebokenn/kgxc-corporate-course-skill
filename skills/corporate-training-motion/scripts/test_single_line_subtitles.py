#!/usr/bin/env python3
import unittest
from single_line_subtitles import clean,prepare,validate,identity

class SingleLine(unittest.TestCase):
    def test_numeric_meaning(self):
        self.assertEqual(clean('10:00—22:00，40–44小时，3.5小时，5%。'),'10点至22点 40至44小时 3点5小时 百分之5')
        self.assertEqual(clean('-3度'),'负3度')
        with self.assertRaises(ValueError):clean('3/4')
    def test_semantic_split_and_time(self):
        source=[dict(id='A',start=0,end=6,text='先检查对象身份，再交给接收人员，最后确认接收状态。')]
        cues=prepare(source,max_em=12)
        self.assertEqual(len(cues),3);self.assertFalse(validate(cues))
        self.assertEqual(identity(''.join(c['text'] for c in cues)),identity(source[0]['text']))
        self.assertEqual((cues[0]['start'],cues[-1]['end']),(0,6))
        self.assertTrue(all(a['end']==b['start'] for a,b in zip(cues,cues[1:])))
    def test_rejects_text_loss_and_mechanical_chop(self):
        c=[dict(id='A',start=0,end=4,text='完整课程名称不能机械切开')]
        with self.assertRaises(ValueError):prepare(c,max_em=5)
        with self.assertRaises(ValueError):prepare(c,{'A':['缺字']})
    def test_actual_wrap_and_unsafe_glyph_are_rejected(self):
        c=prepare([dict(id='A',start=0,end=2,text='单行字幕')])
        m=[dict(id=c[0]['id'],text=c[0]['text'],bounds=[112,942,500,1010],line_count=1)]
        self.assertFalse(validate(c,m,[112,942,1808,1028]))
        m[0]['line_count']=2;self.assertTrue(validate(c,m,[112,942,1808,1028]))
        m[0]['line_count']=1;m[0]['bounds'][2]=1809;self.assertTrue(validate(c,m,[112,942,1808,1028]))
        c[0]['text']='单行\n字幕';self.assertTrue(validate(c))

if __name__=='__main__':unittest.main()
