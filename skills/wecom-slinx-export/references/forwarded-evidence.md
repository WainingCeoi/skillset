# 转发内部消息与 RAG 追溯

适用于采集或补齐企业微信转发聊天记录、从已有归档重新打包，以及准备 RAG 来源数据。参考 WhatsApp 导出的 `message_id`、`sent_at`、发送人、`reply_to`、附件路径及缺失状态；不照搬 WhatsApp 本地行号、数字消息类型或身份值，不假定企业微信 UI 提供原生消息 ID。

## 采集与完整性

1. 先保存外层群消息的发送人、时间、原卡片标题和可见摘要，分配可复用的记录编号。展开后核对标题与外层卡片，逐屏读到顶部和底部，记录每屏首末锚点及重叠记录；嵌套转发按相同方法处理。预览有四行不等于内部只有四条。
2. 每条内部消息独立保存原作者、原时间标签、原文、类型、内部顺序、引用和附件。外层群成员、转发者、内部作者分别记录；没有原作者 ID 时保留显示名和空 ID，不根据相同姓名合并身份。对旧 ZIP 只有摘要的卡片，不能把摘要行直接当成已完整核实的子消息。
3. 分别核实内部时间标签、日期上下文和悬停提示。只有日期、秒数和时区都已确认时才填写 ISO `sent_at`；分钟或日期精度使用 `original_time` 与 `time_precision`，`sent_at` 为 null。时区未核实写 null；不把外层时间、附件文件时间、采集时间当成内部发送时间。
4. 打开对应内部消息的附件，匹配原件及内部位置。多个附件可属于同一消息；不凭卡片预览顺序或文件名猜测所属作者。已有文件只确认属于外层卡片时保留 `card_only`，待展开核实后更新为内部消息的 `verified` 关联。
5. `forward_status` 对转发节点使用 `complete`、`partial`、`not_opened`、`unavailable` 或 `unknown`；普通消息为 null。只有首尾、分页衔接和嵌套内容均已核实才可为 `complete`，并记录核实依据。作者、时间和附件缺失另计，遍历完整不代表所有字段或原件完整。已确定的内部条数和界面声称的总数分开保存；未知总数为 null。
6. 无法展开或媒体过期仍保存现有摘要、已核实条目及失败原因。报告整个范围的缺口；不把缺失内容补造成事实，也不把尚未复查标记为已过期。仅更新 skill 或检查格式不授权启动采集、上传或 RAG 处理。

## 证据文件

输出以类似 WhatsApp 的 `messages.jsonl + media/` 为主体，保留 Slinx 兼容 ZIP 及必要的原件、报告；不生成 HTML：

```text
<export>/
  messages.jsonl               # 首行群信息，其后每行一条顶层或内部消息
  slinx-import.zip              # 只有 manifest.json、messages.jsonl、media/
  media/                       # 原件或通过核对的导入副本
  originals/                   # 有压缩副本时另存原件，不重复存相同字节
  captures/                    # 仅在需要保留 UI 核实证据时存在
  export-report.json           # 版本、校验、缺失情况、采集进度
```

所有证据路径相对于 `<export>/`，限制在本目录内；文件采用安全路径，原名另存。采集证据与待导入 RAG 的材料分开，不默认把整个输出目录全部索引。

根目录 JSONL 首行群头使用 `record_type: chat` 和 `schema_version: wecom-evidence-v2`，包含 `source_namespace`、`chat_id`、`chat_name`、已核实的 `source_chat_id`（否则 null）、`export_id`、`exported_at`、采集范围和时区。区分采集时间与重新打包时间。来源归档信息、完整度、数量、原始消息文件与最终 ZIP 的 SHA-256/大小、各类附件校验、续采位置统一保存在 `export-report.json`，不要再生成独立 `evidence/manifest.json`、`slinx-map.jsonl` 或默认续采交接 Markdown。

### 消息记录

根目录 `messages.jsonl` 首行是群头，其后每行是 `record_type: message` 的独立 JSON 对象。顶层及内部消息使用同一组字段；源数据在暂存阶段命名为 `source-messages.jsonl`，防止与待打包的 Slinx 消息混淆：

| 字段 | 约定 |
| --- | --- |
| `message_id`、`id_kind`、`source_message_id` | `message_id` 是本证据集内稳定的出现记录 ID；`id_kind` 为 `source` 或 `generated`。没有已核实的平台 ID 时 `source_message_id` 为 null、标 `generated`，不能把生成 ID 说成企业微信原生 ID。 |
| `chat_id`、`parent_message_id`、`order` | `chat_id` 继承外层归档的群范围，不表示内部消息原本就在这个群发送。顶层父 ID 为 null；内部指向直接父卡片。`order` 在同一父节点下严格递增，不按日期把内部旧消息挪到群时间线。 |
| `sender_id`、`sender_name`、`from_me` | 均来自这一条消息的界面证据，未知为 null；内部作者不能继承外层转发者。`from_me` 无法核实时为 null。 |
| `sent_at`、`original_time`、`time_precision`、`timezone` | 保留实际精度；`time_precision` 为 `second`、`minute`、`date` 或 `unknown`。不能补零秒，不能用 outer 的时间或时区填 inner 的未知字段。 |
| `message_type`、`text` | 使用明确的字符串类型；`text` 原样保留正文或卡片摘要，未取得为 null。导出标签、内部全文拼接和 AI 识别结果不写入此原文字段。 |
| `reply_to` | 没有观察到引用时为 null；有引用时按下述引用对象记录。`parent_message_id` 与 `reply_to` 是不同关系。 |
| `media` | 附件对象数组，按该条消息内已核实的顺序保存，具体规则见下节。 |
| `forward_status`、`provenance` | 前者记录展开状态。后者记录采集方法、时间、定位描述、`evidence_paths` 相对证据路径数组及未核实原因，足以回到相同卡片和内部条目复核。 |
| `slinx_ref` | 只含 `batch_id` 和 `message_id`，指向本 ZIP 的顶层消息。内部消息指向所属最外层卡片；其自身独立 ID、父卡片和内部顺序仍用于精确定位。 |

记录引用对象至少包含 `message_id`（目标证据 ID 或 null）、`source_message_id`（核实到的平台目标 ID 或 null）、`quoted_author_id`、`quoted_author_name`、`quoted_original_time`、`quoted_text` 和 `status`。状态为 `matched`、`excerpt_only`、`missing_in_export` 或 `unverified`。`matched` 必须指向实际存在且唯一核实的目标；其余状态保留可见引文，不能根据文本相似度强连。同名、同文、同分钟或同一附件哈希都不足以认定为同一次消息。

可定位的来源键由 `source_namespace + chat_id + message_id` 组成；同一来源续采或重新打包沿用命名空间和群标识，每次导出另有 `export_id` 和文件哈希标识内容版本。本地行号只作定位辅助，不能用作跨导出的原生群或消息 ID。续采沿用已核实记录的 ID，并记录旧新映射；无法证明同一出现记录时不合并。重复转发相同内容仍保存各次出现和各自父卡片。

### 附件记录

每个 `media` 项包含 `attachment_id`、`attachment_name`、`attachment_status`、`ownership_status` 和原件的 `attachment_path`、`content_type`、`sha256`、`size_bytes`。另用 `slinx_path` 指向对应 ZIP 附件路径（包含缺失占位项）；不在 ZIP 中的采集证据为 null。原件缺失时原件路径和校验值为 null；名称未知为 null。一个消息可以有多个附件，不沿用 WhatsApp 示例的一条消息只有一个附件字段的限制。

- `attachment_status` 为 `exported`、`missing_local`、`expired` 或 `unverified`；`exported` 只用于已取得且核实对应关系的原件。
- `ownership_status` 为 `verified`（确切消息）、`card_only`（只到卡片）或 `unverified`。卡片所有附件的汇总不是“全部由转发人原创”的证据。
- 压缩副本另存 `import_copy`，缩略图/封面/截图另存 `preview`；各自含 `path`、`sha256`、`size_bytes`、`content_type`，预览还标明具体种类。所有已有文件按安全相对路径保存在 `media/`、`originals/` 或 `captures/`，不跨导出目录引用。压缩转换来源和质量检查沿用 [完整归档](complete-archive.md#压缩顺序与质量边界)。旧 ZIP 仅有压缩副本时不能冒充原件；未转码且原件与导入文件相同可共同引用 `media/` 内一份字节。
- 视频保留完整文件与可核实的时长。OCR、转录、视觉描述和关键帧若另有用户授权生成，作为派生证据，记录所属消息、附件哈希、页码或视频时间区间、方法及核实状态，不覆盖聊天原文。
- 相同字节可复用文件，消息与附件的关联分别保留。映射更新后所有副本都与同一确切消息对应；不能因为两张图看起来相似而串图。

## Slinx 兼容呈现

结构化证据是原始事实层，导入 ZIP 是既有 v1 格式下的展示版本；两者可追溯但不承诺字段或消息计数相同。

1. ZIP 不加入群头、`parent_message_id`、`forward_status`、`slinx_ref` 或额外引用字段。只输出当前 `dev_chat_contract.py` 允许的字段，保持 `manifest.json`、`messages.jsonl`、`media/` 的现有布局。根目录 JSONL 与 ZIP 中 JSONL 不互相覆盖；不要改 Slinx 源码或调整校验器上限。
2. 普通顶层消息保持原文、发送人、时间与现有引用规则。顶层转发卡片仍只占一条群消息，头部是外层转发人和转发时间；其 `text` 生成明确标记的内部记录全文，按内部顺序显示每条的原作者、原时间、原文、引用及附件路径/编号。新增说明标签用英文，原文不翻译、不改写。原卡片摘要原样留在证据文件；已经逐条呈现的内容不再重复附一遍摘要。尚未展开的部分保留摘要并标 `Forwarded content incomplete`。
3. 内部全文以 `Forwarded messages` 开始。每条显示证据 ID、内部位置、原作者及原时间；未知显示 `Unknown sender`、`Time unknown`。用 `Attachment` 标明附件路径和类型，用 `Quoted message` 标明实际可见的引文，回复原文紧随其后且只出现一次。嵌套边界以父卡片/内部位置标明，不能让读者误以为内部作者在外层时间向本群直接发言。
4. 外层 `media` 汇总该卡片实际关联且已取得的全部附件副本，缺失项仍按原契约保留缺失清单及引用。保持核实的内部顺序；同一实际路径可去重，内部消息归属仍保留在证据和全文中。未核实到内部条目的媒体明确标 `card_only`。缩略图不充当原件；Slinx 的 `screenshot_preview` 仅在满足现有缺失原件和 PNG 预览契约时使用，不新增媒体角色。
5. 原生 `reply_to` 只链接唯一核实且实际存在于本 ZIP 的顶层消息。目标是内部子消息时，将准确引文及原作者/原时间呈现一次，并在证据中保留真实子消息关系；不能为了有原生引用框把目标改成外层卡片。需要完整同包引用时纳入原顶层来源并说明范围；无法纳入时保留已核实引文和范围外状态。
6. 将原先独立映射文件的信息合并进每条原始消息的 `slinx_ref` 及每项附件的 `slinx_path`。精确追溯使用来源键、群头导出版本、内部父子关系和原始 JSONL 行号辅助定位，不依赖 HTML。内部消息共用外层 Slinx 消息 ID，但保留独立来源键；不能伪称 Slinx 已有内部消息跳转入口。
7. 在 Slinx 消息 `provenance` 的既有字段中简要注明这是转发全文的兼容呈现及外层来源 ID。修改了呈现内容的重打包使用新 `batch_id`，独立包 `base_batch_id: null`。导出报告列出正文拼接和批次映射这类预期变化；证据中的原文字节保持不变。超出消息长度、单消息附件数量或其他契约限制时报告具体障碍，保留完整 JSONL 和附件，不截断、不伪造顶层消息或声称不兼容的 ZIP 已通过。

## 生成与验收

`finish.py` 接收暂存目录中的 Slinx `manifest.json`、兼容 `messages.jsonl`、所需媒体，以及必需的 `source-messages.jsonl`（v2 群头＋原始消息）。可另提供含采集缺口、压缩依据和续采位置的 `export-report.json`。引用的原件和采集证据也放在暂存目录对应安全路径。它不会自行采集或从摘要生成内层消息，没有自动压缩或 RAG 入库参数。

1. 保存统一证据记录、原件和映射所需 ID；从证据生成普通消息与转发全文的 Slinx 暂存数据。不要把原始 JSONL 直接改名塞进 Slinx ZIP。
2. 小包调用 `finish.py`：校验 ZIP、来源 ID/父子关系/已匹配引用、Slinx 对应关系和附件校验值，再将原始 JSONL 原样保存为输出根目录 `messages.jsonl`，复制被引用的媒体、原件和证据，写出带校验结果的报告。缺少原始 JSONL 时明确停止，不能只导出展示消息冒充逐条证据。此脚本不生成 HTML、独立映射文件或交接 Markdown。
3. 大包走 [流式完整归档](complete-archive.md#大型归档或超过限制时)，生成相同最终布局。校验失败时区分结构错误、来源错误、文件损坏和容量超限，不关闭校验来宣称兼容。
4. 逐条核对证据数量、ID、正文、发送人、时间精度及父子顺序；父引用无环，所有已匹配引用存在。分别统计顶层与内部条目，不能把子消息计入群原始消息数。摘要、完整内文和派生识别文本不能重复冒充三次原始发言。
5. 验证每个 `exported` 原件和已采用副本的大小/哈希、消息归属、相对路径及 ZIP 路径。原始消息均可通过 `slinx_ref` 定位到正确外层消息；缺原件、仅预览、仅卡片归属、未知时间和未展开内容分别报告。
6. 记录文件哈希和版本，完成根目录原始消息与导入 ZIP 的交叉核对。分别报告：证据完整度、结构/媒体完整性、Slinx 格式校验、接收端容量、RAG 解析及入库状态；未执行的检查明确写未执行。此次布局变更不自动删除或改写旧归档，需要时先转换为新目录并核对。

## RAG 使用边界

- 这套证据格式提供逐条定位所需字段，不代表当前 RAG 已实现按字段过滤、内部消息跳转或正确的附件关系抽取。应检查实际接收端解析器，并验证检索片段保留来源键、导出版本及涉及的消息 ID 列表。
- 按用户请求生成 RAG 输入时，每段包含群范围、父卡片来源、内部原作者/原时间、原文和附件对应路径；引用原文与回复分开，未知信息显式标记。不能只索引生成的摘要或只给模型无上下文图片。
- 根目录原始 JSONL 与 ZIP 中的 Slinx 转发全文是同一证据的不同呈现，避免同时当成独立事实重复入库。保留完整归档；测试输入只选择一套有映射的呈现，评测标准答案放在知识库之外。
- 图片、PDF 可解析不代表视频、特殊附件和缩略图均被正确理解。检查接收端支持的格式、ZIP 条目/展开大小上限和跳过记录；原件已保存与内容已被 RAG 读取是两个结果。未授权时不进行 OCR、转录、视觉调用或索引。
