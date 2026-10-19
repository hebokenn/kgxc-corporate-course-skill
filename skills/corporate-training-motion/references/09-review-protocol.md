# 逐步确认、版本和失效

默认先制度范围→逐字稿→重点画面→声音→一小节试看→全片候选；用户可明确合并确认点。每次展示可查看的实体文件和具体需确认项，然后停止依赖该确认的制作。用户要求“每一步确认”不等于每条命令询问。

审批记录写 `approval_records.json`，键为 `source/content/visual/voice/pilot/final`。每项形如：

```json
{
  "content": {
    "status": "approved",
    "reviewer": "用户",
    "confirmed_at": "2026-10-14T10:00:00+08:00",
    "user_confirmation": "这里记录实际收到的确认原话，示例不是批准",
    "artifacts": {"script_segments.json": "实际文件的SHA256"}
  }
}
```

确认时间使用用户时区。复制模板不表示批准；只有收到真人确认后才能写 approved。记录不包含凭证或公司敏感人员数据。`project.json.approvals` 可保留给旧工具兼容，但布尔值不能替代记录。

每项绑定用户看到的全部关键产物：source=原件+规则+疑问答复；content=逐字稿+分段JSON；visual=视觉规范+关键帧+分镜JSON；voice=音频+来源选择；pilot=试看MP4+QA；final=全片+SRT+QA+工程输入清单。旧工程artifact路径相对其工程目录；规范工程相对project/，可指向../inputs或../delivery，但解析后必须仍在所属课程内。approved 必须至少绑定一个真实文件；工具核验一致性，不能验证原话确实来自用户，执行代理必须保证来源。

`review_gate.py COURSE --next script|visual|pilot|full|release` 只读检查批准链与绑定文件哈希。它不会启动渲染。实际制作前按本 Skill 检查该阶段应绑定的关键文件都列出，不能用一个无关文件来蒙混。

修改源规则/逐字稿：content、visual、voice、pilot、final 失效；只改视觉：visual、pilot、final 失效；只改声音/时间轴：voice、pilot、final 失效；只修编码：重跑技术QA并重新确认受影响候选。文件哈希变化自动被检查发现；另外明确把相关下游状态改为 pending，不能靠哈希替代依赖判断。

已认可的音色、画风可复用，修改无需重新问无关偏好；重新确认针对变更及影响范围。批准过样片只允许制作全片候选，不代表批准发布。

品牌固定片头片尾及角标规则在visual确认项中审阅；欢迎语音频在voice项中确认，素材路径与哈希一并登记。换Logo/片头/片尾时visual、pilot、final失效；换欢迎语音轨时voice、pilot、final失效。已批准的品牌素材可以跨课程引用，保存其实际文件及来源确认，后续不重复询问已确认的内容。
