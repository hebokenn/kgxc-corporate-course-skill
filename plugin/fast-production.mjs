const parallel='逐字稿真实确认后，如当前授权允许生成且音色已确认，让配音与分镜/素材两线并行；两线不同时写同一文件，配音未完成时不得锁定假时间轴。音色或生成尚未授权时只做可以独立推进的分镜与素材，不绕过原有边界。';
const preflight='小样阶段先走实际导出路线，用真实片头、正文和片尾验证两个接缝、声音和时间轴。默认工作台导出会先做自动接缝短试，无需另开审阅或用户确认；使用独立拼接路线时按 Skill 调用 scripts/export_preflight.py，并以实际成片命令完成接缝试拼，不能用模拟试片替代。';
const incremental='返工前按 58-fast-production.md 用 scripts/incremental_production.py 核对实际产物与依赖；未变的配音和画面素材优先复用，只重做受影响的独立片段。整体依赖变化或无法证明复用时保守重算，不能省略成品检查。整课先锁画面与配音主体，再独立加入并检查花字和音效。最终完整解码、核对接缝、时间轴和关键段落；仅当存在具体异常或要求无损一致时才额外逐帧比对。';
export function fastProductionPrompt(stage){
  return stage==='storyboard'?parallel:stage==='pilot'?preflight+incremental:stage==='final'?preflight+incremental:'';
}
