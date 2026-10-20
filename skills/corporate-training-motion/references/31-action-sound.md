# 动作音效的默认选择与混音

“继续制作”包含按动作选择音效，不需要用户逐个挑技术参数。新音效默认使用本包`soft-tactile-v1`：柔和落位、轻空气位移、纸面展开、轻触聚焦、低柔双触、空气过渡、低沉止步，共7类、每类3个实际WAV。按教学动作选择角色，同类事件自动轮换变体，固定课程和事件ID以保证恢复后可重现。

不再把同一个蜂鸣、电子“叮”或统一whoosh铺在所有出现动作上。不每字一响，也不用随机换音制造噪声；不为达到数量或运动指标加音效。对象交接、局部揭示、核对落位、条件冲突和确认完成可以各有合适声音；没有表达价值的动作可以留静音。已有专门选定的音色/资产优先。之前技术验证片反复使用的660Hz提示声不是正式制作默认。

```sh
python3 SKILL_DIR/scripts/course_tools.py sfx-catalog
python3 SKILL_DIR/scripts/course_tools.py sfx-plan COURSE --events COURSE/project/source/sfx-events.json
python3 SKILL_DIR/scripts/course_tools.py sfx-mix COURSE --plan COURSE/project/audio/sfx-plan.json --narration audio/narration.wav --out audio/course-mix.wav
```

事件文件以课程**源时间轴的绝对整数帧**对齐动作接触或完成点。音效按素材实际峰值对齐该frame，音效和旁白混成源音轨后由工作台统一处理裁剪和停留。

新课尚未configure时，先在source/course-composition.json保存与实际配音一致的sourceDurationFrames；sfx-plan会使用这条真实时间轴，不使用空画布的1帧占位。其他文件名可加`--spec COURSE/project/source/实际构图.json`。混音完成后把实际输出写入spec的media.audio，再configure；不会为准备音效伪造画布或确认。

```json
{"palette":"soft-tactile-v1","events":[
  {"id":"receipt-reveal","frame":45,"role":"reveal","gainDb":-1},
  {"id":"handoff","frame":96,"role":"move","gainDb":0},
  {"id":"check-complete","frame":140,"role":"confirm","gainDb":-2}
]}
```

role为enter/move/reveal/focus/confirm/transition/warning；none表示明确静音。gainDb可在-18至6调整。模型根据真实动作写事件，不把每个文字入场自动转成声音事件。计划保存所选素材、哈希、时间点和音量；同类相邻选择不会重复同一文件。素材原始代码合成，无外部服务或下载依赖。

混音命令将原旁白作为不可覆盖输入，输出独立音效分轨、实际混音与来源记录。输入应是原旁白或保留的干净分轨；已经混入旧蜂鸣的成品不能再叠一层新音效假装替换，应回到原分轨。原始录音不变速、不重配。混音轻度避让有声段，削波时拒绝输出并调整相关事件，不统一压低整段人声。

新课在构图spec的media.audio中登记实际混音，再configure。已制作工程在本次授权的音效修改中可给sfx-mix添加`--bind`：先检查当前工程未变化，保存旧文档并增加revision，替换实际工作台音轨绑定；旧源音轨与交付保留。输出必须与源时间轴等长，不能改变字幕、场景、裁剪和停留。新混音会让受影响的旧运行证据与小样批准需要重新核对，不伪造确认。

选音及混音完成后，在正常速度有声小样中核对音色是否刺耳、重复是否疲劳、动作是否对位、是否抢词以及是否实际听得见。峰值、RMS、文件存在、全量解码均不能代替试听；用户听感优先。提供当前小样供试听，不声称技术检查等于用户认可。既有批准旁白、品牌片头片尾及冻结成片不因新默认而自动替换。
