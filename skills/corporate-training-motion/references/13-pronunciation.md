# 多音字与班次数字断句

用户指出具体发音错误后，生成短样验证供应商对发音控制的支持，再制作整段正式旁白；保留原带，不拼接不同声线的局部补丁。当前025 `zh-CN-Yunxiao:DragonHDFlashLatestNeural`已实测接受单voice的phoneme与break SSML请求。

- 店长：`<phoneme alphabet="sapi" ph="dian 4 zhang 3">店长</phoneme>`。包括副店长、代班店长、储备店长中的该词；不要将所有“长”字统一改音。
- 班次名与时段分成两个完整语句。如“周四，中班二。上班时间为十三点到二十点。”，在两句间加入已验证的250ms break。不能把“B2 13点”直接紧邻输入。B1、B2、C1、C2等均检查。
- 制度事实、建议与例外保持原样。只有朗读连接词需要改变时，保存原文、修订文、用户授权与原因；字幕和锚点随后按真实新音轨重建，不能用旧声音的时间。
- 同一voice请求贯穿片头、正文、片尾，不在SSML里切换voice或加入另一个人的发音片段。保存文本、SSML、WAV各自哈希。
- 自动转写无法证明声调正确；检查实际控制标注和短样，保留听感验收边界。数字转写如“中班23点”属于必须复核的歧义，不能只按整课匹配率接受。

官方参考（2026-10-16核验）：[中文SAPI音素](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-ssml-phonetic-sets)及[HD的SSML支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/high-definition-voices)。本地Azure适配器只允许一个已选voice及白名单发音标签，禁止外部音频。

## 用户报告读音错误时

SSML phoneme和ASR汉字正确都不证明声学发音正确。提取本次交付音轨的对应完整词句复听，区分发音设置、声学听核和用户确认。不能听核就明确写未核实并交出可复听的本地片段，不写已纠正；不默认忽略用户反馈。只有在确认需要新云配音且获得该次文本传输/费用授权后才生成，旧授权不扩大。
