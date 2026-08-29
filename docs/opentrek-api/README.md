# OpenTrek API 文档（本地快照）

来源：http://10.128.203.200:30226/agent/index.html#/arrange/apiDoc

抓取时间：2026-08-28T13:26:23.646Z

本快照通过学校 OpenTrek 平台登录后，从文档页实际使用的目录和详情接口拉取。
账号密码、登录 Cookie、Session、OpenTrek应用密钥 均未写入本目录。

## 实际部署差异

2026-08-29 在当前学校实例进行受保护验收时发现以下行为，运行代码以真实响应为准：

- Agent 名称最大 20 个字符，因此比赛资源使用 `ig-comp-` 前缀。
- Agent 模型配置的 `modelCode` 必须使用模型列表记录中的服务 UUID `code`，不能使用展示用
  `modelCode`/模型名，否则运行时返回“模型配置缺失”。
- 文档知识库即使使用基础解析，也必须在 `kbProperties.visualModel` 提供可用 VLM；只传公开文档
  列出的文本 Embedding 会返回 `vlm model info miss`。
- Skill 文件管理的实际 Cookie 管理路径为 `/agent/api/skill/*`；对应 `/gatectl/agent/api/skill/*`
  在当前部署返回 Nginx 404。
- Skill 保存请求中的静态 Agent 关联未落盘。实际对话 UI 使用
  `message.metadata.skillList: [skill.name, ...]`，比赛运行时按该协议绑定 Skill。
- 已发布 Agent 版本不能原地重新上线；模型配置变化需创建并发布新的版本。

## 内容

- manifest.json：接口索引、分类、方法、地址、版本及本地文件映射。
- category.json：平台返回的原始 API 分类树。
- details.json：全部接口详情接口的原始响应。
- apis/：每个接口一份可直接阅读的 Markdown 文档。

## 抓取结果

- 平台目录接口数：127
- 成功保存：127
- 失败：0

## 接口索引

| # | 分类 | 接口 | 方法 | 调用地址 | 本地文档 |
| --- | --- | --- | --- | --- | --- |
| 1 | 平台功能类 / 系统管理 / 账号管理 / 账号存在判断 | 账号存在判断 | GET | http://10.128.203.200:30226/gatectl/system/api/v1/account/checkExist | [apis/001-system.api.v1.account.checkexist.md](apis/001-system.api.v1.account.checkexist.md) |
| 2 | 平台功能类 / 系统管理 / 账号管理 / 创建账号 | 创建账号 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/account/create | [apis/002-system.api.v1.account.create.md](apis/002-system.api.v1.account.create.md) |
| 3 | 平台功能类 / 系统管理 / 账号管理 / 获取账号信息 | 获取账号信息 | GET | http://10.128.203.200:30226/gatectl/system/api/v1/account/getByAccount | [apis/003-system.api.v1.account.getbyaccount.md](apis/003-system.api.v1.account.getbyaccount.md) |
| 4 | 平台功能类 / 系统管理 / 用户授权 / 新增用户授权 | 新增用户授权 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/permUserAuth/addUserAuth | [apis/004-system.api.v1.permuserauth.adduserauth.md](apis/004-system.api.v1.permuserauth.adduserauth.md) |
| 5 | 平台功能类 / 系统管理 / 用户授权 / 删除用户授权 | 删除用户授权 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/permUserAuth/removeUserAuth | [apis/005-system.api.v1.permuserauth.removeuserauth.md](apis/005-system.api.v1.permuserauth.removeuserauth.md) |
| 6 | 平台功能类 / 系统管理 / 用户授权 / 查询账号授权信息 | 查询账号授权信息 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/permUserAuth/pageUserAuthDetail | [apis/006-system.api.v1.permuserauth.pageuserauthdetail.md](apis/006-system.api.v1.permuserauth.pageuserauthdetail.md) |
| 7 | 平台功能类 / 系统管理 / 空间管理 / 创建工作空间 | 创建工作空间 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/create | [apis/007-system.api.v1.workspace.create.md](apis/007-system.api.v1.workspace.create.md) |
| 8 | 平台功能类 / 系统管理 / 空间管理 / 修改工作空间 | 修改工作空间 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/update | [apis/008-system.api.v1.workspace.update.md](apis/008-system.api.v1.workspace.update.md) |
| 9 | 平台功能类 / 系统管理 / 空间管理 / 工作空间添加用户 | 工作空间添加用户 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/authorizeUser | [apis/009-system.api.v1.workspace.authorizeuser.md](apis/009-system.api.v1.workspace.authorizeuser.md) |
| 10 | 平台功能类 / 系统管理 / 空间管理 / 更改空间授权 | 更改空间授权 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/updateUser | [apis/010-system.api.v1.workspace.updateuser.md](apis/010-system.api.v1.workspace.updateuser.md) |
| 11 | 平台功能类 / 系统管理 / 空间管理 / 查询空间中的用户 | 查询空间中的用户 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/pageQueryUser | [apis/011-system.api.v1.workspace.pagequeryuser.md](apis/011-system.api.v1.workspace.pagequeryuser.md) |
| 12 | 平台功能类 / 系统管理 / 空间管理 / 移除空间用户 | 移除空间用户 | POST | http://10.128.203.200:30226/gatectl/system/api/v1/workspace/removeUser | [apis/012-system.api.v1.workspace.removeuser.md](apis/012-system.api.v1.workspace.removeuser.md) |
| 13 | 平台功能类 / 智能体管理 / 智能体 / 查询智能体列表 | 查询智能体列表 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/pageQuery | [apis/013-agent.openapi.agent.pagequery.md](apis/013-agent.openapi.agent.pagequery.md) |
| 14 | 平台功能类 / 智能体管理 / 智能体 / 创建智能体 | 创建智能体 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/create | [apis/014-agent.openapi.agent.create.md](apis/014-agent.openapi.agent.create.md) |
| 15 | 平台功能类 / 智能体管理 / 智能体 / 编辑智能体 | 编辑智能体 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/update | [apis/015-agent.openapi.agent.update.md](apis/015-agent.openapi.agent.update.md) |
| 16 | 平台功能类 / 智能体管理 / 智能体 / 删除智能体 | 删除智能体 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/delete | [apis/016-agent.openapi.agent.delete.md](apis/016-agent.openapi.agent.delete.md) |
| 17 | 平台功能类 / 智能体管理 / 智能体 / 查询智能体版本列表 | 查询智能体版本列表 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/version/pageQuery | [apis/017-agent.openapi.agent.version.pagequery.md](apis/017-agent.openapi.agent.version.pagequery.md) |
| 18 | 平台功能类 / 智能体管理 / 智能体 / 创建智能体版本 | 创建智能体版本 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/version/create | [apis/018-agent.openapi.agent.version.create.md](apis/018-agent.openapi.agent.version.create.md) |
| 19 | 平台功能类 / 智能体管理 / 智能体 / 编辑智能体版本 | 编辑智能体版本 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/version/update | [apis/019-agent.openapi.agent.version.update.md](apis/019-agent.openapi.agent.version.update.md) |
| 20 | 平台功能类 / 智能体管理 / 智能体 / 删除智能体版本 | 删除智能体版本 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/agent/version/delete | [apis/020-agent.openapi.agent.version.delete.md](apis/020-agent.openapi.agent.version.delete.md) |
| 21 | 平台功能类 / 智能体管理 / 智能体 / 写入记忆分区内容 | 写入记忆分区内容 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/memory/longTerm/partition/add | [apis/021-agent.openapi.memory.longterm.partition.add.md](apis/021-agent.openapi.memory.longterm.partition.add.md) |
| 22 | 平台功能类 / 智能体管理 / 工具 / 查询工具列表 | 查询工具列表 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/tool/pageQuery | [apis/022-agent.openapi.tool.pagequery.md](apis/022-agent.openapi.tool.pagequery.md) |
| 23 | 平台功能类 / 智能体管理 / 工具 / 创建工具 | 创建工具 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/tool/create | [apis/023-agent.openapi.tool.create.md](apis/023-agent.openapi.tool.create.md) |
| 24 | 平台功能类 / 智能体管理 / 工具 / 编辑工具 | 编辑工具 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/tool/update | [apis/024-agent.openapi.tool.update.md](apis/024-agent.openapi.tool.update.md) |
| 25 | 平台功能类 / 智能体管理 / 工具 / 查询工具详情 | 查询工具详情 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/tool/getOne | [apis/025-agent.openapi.tool.getone.md](apis/025-agent.openapi.tool.getone.md) |
| 26 | 平台功能类 / 智能体管理 / 工具 / 删除工具 | 删除工具 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/tool/delete | [apis/026-agent.openapi.tool.delete.md](apis/026-agent.openapi.tool.delete.md) |
| 27 | 平台功能类 / 智能体管理 / SKILL HUB / 查询Skill列表 | 查询Skill列表 | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/queryPage | [apis/027-agent.api.skill.querypage.md](apis/027-agent.api.skill.querypage.md) |
| 28 | 平台功能类 / 智能体管理 / SKILL HUB / 查询Skill详情 | 查询Skill详情 | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/getOne | [apis/028-agent.api.skill.getone.md](apis/028-agent.api.skill.getone.md) |
| 29 | 平台功能类 / 智能体管理 / SKILL HUB / 查询Skill版本列表 | 查询Skill版本列表 | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/listVersions | [apis/029-agent.api.skill.listversions.md](apis/029-agent.api.skill.listversions.md) |
| 30 | 平台功能类 / 智能体管理 / SKILL HUB / 扫描Skill ZIP包 | 扫描Skill ZIP包 | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/scanZip | [apis/030-agent.api.skill.scanzip.md](apis/030-agent.api.skill.scanzip.md) |
| 31 | 平台功能类 / 智能体管理 / SKILL HUB / 创建Skill | 创建Skill | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/create | [apis/031-agent.api.skill.create.md](apis/031-agent.api.skill.create.md) |
| 32 | 平台功能类 / 智能体管理 / SKILL HUB / 更新Skill | 更新Skill | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/update | [apis/032-agent.api.skill.update.md](apis/032-agent.api.skill.update.md) |
| 33 | 平台功能类 / 智能体管理 / SKILL HUB / 删除Skill | 删除Skill | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/delete | [apis/033-agent.api.skill.delete.md](apis/033-agent.api.skill.delete.md) |
| 34 | 平台功能类 / 智能体管理 / SKILL HUB / 分享Skill | 分享Skill | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/share | [apis/034-agent.api.skill.share.md](apis/034-agent.api.skill.share.md) |
| 35 | 平台功能类 / 智能体管理 / SKILL HUB / 安装已分享的Skill | 安装已分享的Skill | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/installShared | [apis/035-agent.api.skill.installshared.md](apis/035-agent.api.skill.installshared.md) |
| 36 | 平台功能类 / 智能体管理 / SKILL HUB / 生成Skill MD | 生成Skill MD | POST | http://10.128.203.200:30226/gatectl/agent/api/skill/generateSkillMD | [apis/036-agent.api.skill.generateskillmd.md](apis/036-agent.api.skill.generateskillmd.md) |
| 37 | 平台功能类 / 智能体管理 / 智能体模版 / 查询智能体模版列表 | 查询智能体模版列表 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/template/pageQuery | [apis/037-agent.openapi.template.pagequery.md](apis/037-agent.openapi.template.pagequery.md) |
| 38 | 平台功能类 / 智能体管理 / 智能体模版 / 查询智能体模版详情 | 查询智能体模版详情 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/template/getOne | [apis/038-agent.openapi.template.getone.md](apis/038-agent.openapi.template.getone.md) |
| 39 | 平台功能类 / 智能体管理 / 提示词模版 / 查询提示词模版列表 | 查询提示词模版列表 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/prompt/pageQuery | [apis/039-agent.openapi.prompt.pagequery.md](apis/039-agent.openapi.prompt.pagequery.md) |
| 40 | 平台功能类 / 智能体管理 / 提示词模版 / 查询提示词分类 | 查询提示词分类 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/prompt/queryPromptTypes | [apis/040-agent.openapi.prompt.queryprompttypes.md](apis/040-agent.openapi.prompt.queryprompttypes.md) |
| 41 | 平台功能类 / 智能体管理 / 提示词模版 / 创建/更新提示词模版 | 创建/更新提示词模版 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/prompt/save | [apis/041-agent.openapi.prompt.save.md](apis/041-agent.openapi.prompt.save.md) |
| 42 | 平台功能类 / 智能体管理 / 提示词模版 / 发布提示词模版 | 发布提示词模版 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/prompt/deploy | [apis/042-agent.openapi.prompt.deploy.md](apis/042-agent.openapi.prompt.deploy.md) |
| 43 | 平台功能类 / 智能体管理 / 提示词模版 / 删除提示词模版 | 删除提示词模版 | POST | http://10.128.203.200:30226/gatectl/agent/openapi/prompt/delete | [apis/043-agent.openapi.prompt.delete.md](apis/043-agent.openapi.prompt.delete.md) |
| 44 | 平台功能类 / 知识库管理 / 知识库列表查询 | 知识库列表查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/list | [apis/044-kortex.api.kb.list.md](apis/044-kortex.api.kb.list.md) |
| 45 | 平台功能类 / 知识库管理 / 共享知识库列表查询 | 共享知识库列表查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/share/sharedlist | [apis/045-kortex.api.kb.share.sharedlist.md](apis/045-kortex.api.kb.share.sharedlist.md) |
| 46 | 平台功能类 / 知识库管理 / 知识库创建 | 知识库创建 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/create | [apis/046-kortex.api.kb.create.md](apis/046-kortex.api.kb.create.md) |
| 47 | 平台功能类 / 知识库管理 / 知识库元数据更新 | 知识库元数据更新 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/updateMateData | [apis/047-kortex.api.kb.updatematedata.md](apis/047-kortex.api.kb.updatematedata.md) |
| 48 | 平台功能类 / 知识库管理 / 知识库停用 | 知识库停用 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/disable | [apis/048-kortex.api.kb.disable.md](apis/048-kortex.api.kb.disable.md) |
| 49 | 平台功能类 / 知识库管理 / 知识库启用 | 知识库启用 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/enable | [apis/049-kortex.api.kb.enable.md](apis/049-kortex.api.kb.enable.md) |
| 50 | 平台功能类 / 知识库管理 / 知识库删除 | 知识库删除 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/delete | [apis/050-kortex.api.kb.delete.md](apis/050-kortex.api.kb.delete.md) |
| 51 | 平台功能类 / 知识库管理 / 知识库详情查询 | 知识库详情查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/mono/detail | [apis/051-kortex.api.kb.mono.detail.md](apis/051-kortex.api.kb.mono.detail.md) |
| 52 | 平台功能类 / 知识库管理 / 知识库数据变更 | 知识库数据变更 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk | [apis/052-kortex.api.kb.data.consumebulk.md](apis/052-kortex.api.kb.data.consumebulk.md) |
| 53 | 平台功能类 / 知识库管理 / 知识库数据查询 | 知识库数据查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/submodel/data/list | [apis/053-kortex.api.kb.submodel.data.list.md](apis/053-kortex.api.kb.submodel.data.list.md) |
| 54 | 平台功能类 / 知识库管理 / 知识库文件上传 | 知识库文件上传 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/file/data/sync | [apis/054-kortex.api.kb.file.data.sync.md](apis/054-kortex.api.kb.file.data.sync.md) |
| 55 | 平台功能类 / 知识库管理 / 文档知识库文件列表查询 | 文档知识库文件列表查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/file/list | [apis/055-kortex.api.kb.doc.file.list.md](apis/055-kortex.api.kb.doc.file.list.md) |
| 56 | 平台功能类 / 知识库管理 / 文件重新解析 | 文件重新解析 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/file/reprocess | [apis/056-kortex.api.kb.doc.file.reprocess.md](apis/056-kortex.api.kb.doc.file.reprocess.md) |
| 57 | 平台功能类 / 知识库管理 / 文档知识库删除文件 | 文档知识库删除文件 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/file/delete | [apis/057-kortex.api.kb.doc.file.delete.md](apis/057-kortex.api.kb.doc.file.delete.md) |
| 58 | 平台功能类 / 知识库管理 / 文档知识库chunk明细列表查询 | 文档知识库chunk明细列表查询 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/list | [apis/058-kortex.api.kb.doc.chunk.list.md](apis/058-kortex.api.kb.doc.chunk.list.md) |
| 59 | 平台功能类 / 知识库管理 / 文档知识库chunk内容修正 | 文档知识库chunk内容修正 | POST | http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/edit | [apis/059-kortex.api.kb.doc.chunk.edit.md](apis/059-kortex.api.kb.doc.chunk.edit.md) |
| 60 | 平台功能类 / 知识库管理 / 文档知识库资源用量-汇总KPI接口 | 文档知识库资源用量-汇总KPI接口 | GET | http://10.128.203.200:30226/gatectl/kortex/api/statistics/kpi | [apis/060-kortex.api.statistics.kpi.md](apis/060-kortex.api.statistics.kpi.md) |
| 61 | 平台功能类 / 知识库管理 / 文档知识库资源用量-图表趋势接口 | 文档知识库资源用量-图表趋势接口 | GET | http://10.128.203.200:30226/gatectl/kortex/api/statistics/trend | [apis/061-kortex.api.statistics.trend.md](apis/061-kortex.api.statistics.trend.md) |
| 62 | 平台功能类 / 知识库管理 / 文档知识库资源用量-明细数据接口 | 文档知识库资源用量-明细数据接口 | GET | http://10.128.203.200:30226/gatectl/kortex/api/statistics/details | [apis/062-kortex.api.statistics.details.md](apis/062-kortex.api.statistics.details.md) |
| 63 | 平台功能类 / 数据中心 / 数据管理 / 获取数据集列表 | 获取数据集列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets | [apis/063-data-engine.api.v2.datasets.get.md](apis/063-data-engine.api.v2.datasets.get.md) |
| 64 | 平台功能类 / 数据中心 / 数据管理 / 新建数据集 | 新建数据集 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets | [apis/064-data-engine.api.v2.datasets.code.post.md](apis/064-data-engine.api.v2.datasets.code.post.md) |
| 65 | 平台功能类 / 数据中心 / 数据管理 / 更新数据集 | 更新数据集 | PUT | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets | [apis/065-data-engine.api.v2.datasets.code.put.md](apis/065-data-engine.api.v2.datasets.code.put.md) |
| 66 | 平台功能类 / 数据中心 / 数据管理 / 删除数据集 | 删除数据集 | DELETE | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code} | [apis/066-data-engine.api.v2.datasets.code.delete.md](apis/066-data-engine.api.v2.datasets.code.delete.md) |
| 67 | 平台功能类 / 数据中心 / 数据管理 / 获取数据集详情 | 获取数据集详情 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code} | [apis/067-data-engine.api.v2.datasets.code.get.md](apis/067-data-engine.api.v2.datasets.code.get.md) |
| 68 | 平台功能类 / 数据中心 / 数据管理 / 通知数据集文件增加 | 通知数据集文件增加 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/files | [apis/068-data-engine.api.v2.datasets.code.files.post.md](apis/068-data-engine.api.v2.datasets.code.files.post.md) |
| 69 | 平台功能类 / 数据中心 / 数据管理 / 通知数据集文件删除 | 通知数据集文件删除 | DELETE | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/files | [apis/069-data-engine.api.v2.datasets.code.files.delete.md](apis/069-data-engine.api.v2.datasets.code.files.delete.md) |
| 70 | 平台功能类 / 数据中心 / 数据管理 / 获取数据集文件列表 | 获取数据集文件列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/files | [apis/070-data-engine.api.v2.datasets.code.files.get.md](apis/070-data-engine.api.v2.datasets.code.files.get.md) |
| 71 | 平台功能类 / 数据中心 / 数据管理 / 新建数据子集 | 新建数据子集 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets | [apis/071-data-engine.api.v2.datasets.code.subsets.post.md](apis/071-data-engine.api.v2.datasets.code.subsets.post.md) |
| 72 | 平台功能类 / 数据中心 / 数据管理 / 更新数据子集 | 更新数据子集 | PUT | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets | [apis/072-data-engine.api.v2.datasets.code.subsets.put.md](apis/072-data-engine.api.v2.datasets.code.subsets.put.md) |
| 73 | 平台功能类 / 数据中心 / 数据管理 / 删除数据集子集 | 删除数据集子集 | DELETE | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets/{subsetCode} | [apis/073-data-engine.api.v2.datasets.code.subsets.subsetcode.delete.md](apis/073-data-engine.api.v2.datasets.code.subsets.subsetcode.delete.md) |
| 74 | 平台功能类 / 数据中心 / 数据管理 / 数据集子集列表 | 数据集子集列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets | [apis/074-data-engine.api.v2.datasets.code.subsets.get.md](apis/074-data-engine.api.v2.datasets.code.subsets.get.md) |
| 75 | 平台功能类 / 数据中心 / 数据管理 / 获取数据集预览数据 | 获取数据集预览数据 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/viewer | [apis/075-data-engine.api.v2.datasets.code.viewer.md](apis/075-data-engine.api.v2.datasets.code.viewer.md) |
| 76 | 平台功能类 / 数据中心 / 数据管理 / 获取文件下载地址 | 获取文件下载地址 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/presigned/url | [apis/076-data-engine.api.v2.files.url.get.md](apis/076-data-engine.api.v2.files.url.get.md) |
| 77 | 平台功能类 / 数据中心 / 数据管理 / 获取图片下载地址 | 获取图片下载地址 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/image/presigned/url | [apis/077-data-engine.api.v2.files.image.presigned.url.md](apis/077-data-engine.api.v2.files.image.presigned.url.md) |
| 78 | 平台功能类 / 数据中心 / 数据管理 / 删除文件 | 删除文件 | DELETE | http://10.128.203.200:30226/gatectl/data-engine/api/v2/files | [apis/078-data-engine.api.v2.files.delete.md](apis/078-data-engine.api.v2.files.delete.md) |
| 79 | 平台功能类 / 数据中心 / 数据管理 / 获取文件上传授权凭证 | 获取文件上传授权凭证 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/upload/credential | [apis/079-data-engine.api.v2.files.upload.credential.md](apis/079-data-engine.api.v2.files.upload.credential.md) |
| 80 | 平台功能类 / 数据中心 / 数据管理 / 获取文件下载授权凭证 | 获取文件下载授权凭证 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/files/download/credential | [apis/080-data-engine.api.v2.files.download.credential.md](apis/080-data-engine.api.v2.files.download.credential.md) |
| 81 | 平台功能类 / 数据中心 / 数据加工 / 获取算子列表 | 获取算子列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/operators | [apis/081-data-engine.api.v2.operators.md](apis/081-data-engine.api.v2.operators.md) |
| 82 | 平台功能类 / 数据中心 / 数据加工 / 获取加工模版列表 | 获取加工模版列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/templates | [apis/082-data-engine.api.v2.process.templates.md](apis/082-data-engine.api.v2.process.templates.md) |
| 83 | 平台功能类 / 数据中心 / 数据加工 / 获取加工模版详情 | 获取加工模版详情 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/templates/{code} | [apis/083-data-engine.api.v2.process.templates.bycode.md](apis/083-data-engine.api.v2.process.templates.bycode.md) |
| 84 | 平台功能类 / 数据中心 / 数据加工 / 新建加工任务 | 新建加工任务 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks | [apis/084-data-engine.api.v2.process.tasks.md](apis/084-data-engine.api.v2.process.tasks.md) |
| 85 | 平台功能类 / 数据中心 / 数据加工 / 更新加工任务 | 更新加工任务 | PUT | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks | [apis/085-data-engine.api.v2.process.tasks.put.md](apis/085-data-engine.api.v2.process.tasks.put.md) |
| 86 | 平台功能类 / 数据中心 / 数据加工 / 删除加工任务 | 删除加工任务 | DELETE | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId} | [apis/086-data-engine.api.v2.process.tasks.taskid.md](apis/086-data-engine.api.v2.process.tasks.taskid.md) |
| 87 | 平台功能类 / 数据中心 / 数据加工 / 发布任务 | 发布任务 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/publish | [apis/087-data-engine.api.v2.process.tasks.taskid.publish.md](apis/087-data-engine.api.v2.process.tasks.taskid.publish.md) |
| 88 | 平台功能类 / 数据中心 / 数据加工 / 下线任务 | 下线任务 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/unpublish | [apis/088-data-engine.api.v2.process.tasks.taskid.unpublish.md](apis/088-data-engine.api.v2.process.tasks.taskid.unpublish.md) |
| 89 | 平台功能类 / 数据中心 / 数据加工 / 获取加工任务列表 | 获取加工任务列表 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks | [apis/089-data-engine.api.v2.process.tasks.get.md](apis/089-data-engine.api.v2.process.tasks.get.md) |
| 90 | 平台功能类 / 数据中心 / 数据加工 / 获取加工任务详情 | 获取加工任务详情 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId} | [apis/090-data-engine.api.v2.process.tasks.taskid.get.md](apis/090-data-engine.api.v2.process.tasks.taskid.get.md) |
| 91 | 平台功能类 / 数据中心 / 数据加工 / 运行加工任务 | 运行加工任务 | POST | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/run | [apis/091-data-engine.api.v2.process.tasks.taskid.run.md](apis/091-data-engine.api.v2.process.tasks.taskid.run.md) |
| 92 | 平台功能类 / 数据中心 / 数据加工 / 获取任务运行实例信息 | 获取任务运行实例信息 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/instances | [apis/092-data-engine.api.v2.process.tasks.taskid.instances.md](apis/092-data-engine.api.v2.process.tasks.taskid.instances.md) |
| 93 | 平台功能类 / 数据中心 / 数据加工 / 获取任务实例日志 | 获取任务实例日志 | GET | http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/instances/{instanceCode}/log | [apis/093-data-engine.api.v2.process.tasks.instances.instancecode.log.md](apis/093-data-engine.api.v2.process.tasks.instances.instancecode.log.md) |
| 94 | 应用集成类 / 智能体 / 创建session | 创建session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/createSession | [apis/094-agent.api.createsession.md](apis/094-agent.api.createsession.md) |
| 95 | 应用集成类 / 智能体 / 发起agent调用 | 发起agent调用 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/run | [apis/095-agent.api.run.md](apis/095-agent.api.run.md) |
| 96 | 应用集成类 / 智能体 / 终止session | 终止session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/clearSession | [apis/096-agent.api.clearsession.md](apis/096-agent.api.clearsession.md) |
| 97 | 应用集成类 / 智能体 / 删除session | 删除session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/deleteSession | [apis/097-agent.api.deletesession.md](apis/097-agent.api.deletesession.md) |
| 98 | 应用集成类 / 智能体 / 工具异步回调 | 工具异步回调 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/taskFinishNotice | [apis/098-agent.api.taskfinishnotice.md](apis/098-agent.api.taskfinishnotice.md) |
| 99 | 应用集成类 / 智能体 / 调用结果反馈 | 调用结果反馈 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/api/feedback | [apis/099-agent.api.feedback.md](apis/099-agent.api.feedback.md) |
| 100 | 应用集成类 / TrekAgent / 创建session | 创建session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/session/create | [apis/100-agent.auto.new.open.session.create.md](apis/100-agent.auto.new.open.session.create.md) |
| 101 | 应用集成类 / TrekAgent / 创建连接 | 创建连接 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/createNewChannel | [apis/101-agent.auto.new.open.createnewchannel.md](apis/101-agent.auto.new.open.createnewchannel.md) |
| 102 | 应用集成类 / TrekAgent / 刷新channel心跳 | 刷新channel心跳 | GET | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/channelRefresh | [apis/102-agent.auto.new.open.channelrefresh.md](apis/102-agent.auto.new.open.channelrefresh.md) |
| 103 | 应用集成类 / TrekAgent / 切换至指定session | 切换至指定session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/changeTask | [apis/103-agent.auto.new.open.changetask.md](apis/103-agent.auto.new.open.changetask.md) |
| 104 | 应用集成类 / TrekAgent / 发起一次对话 | 发起一次对话 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/run | [apis/104-agent.auto.new.open.run.md](apis/104-agent.auto.new.open.run.md) |
| 105 | 应用集成类 / TrekAgent / 停止当前对话 | 停止当前对话 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/stop | [apis/105-agent.auto.new.open.stop.md](apis/105-agent.auto.new.open.stop.md) |
| 106 | 应用集成类 / TrekAgent / 获取会话列表 | 获取会话列表 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/list | [apis/106-agent.auto.new.open.task.list.md](apis/106-agent.auto.new.open.task.list.md) |
| 107 | 应用集成类 / TrekAgent / 查询单个任务详情 | 查询单个任务详情 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/desc | [apis/107-agent.auto.new.open.task.desc.md](apis/107-agent.auto.new.open.task.desc.md) |
| 108 | 应用集成类 / TrekAgent / 删除任务 | 删除任务 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/delete | [apis/108-agent.auto.new.open.task.delete.md](apis/108-agent.auto.new.open.task.delete.md) |
| 109 | 应用集成类 / TrekAgent / 更新任务信息 | 更新任务信息 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/update | [apis/109-agent.auto.new.open.task.update.md](apis/109-agent.auto.new.open.task.update.md) |
| 110 | 应用集成类 / TrekAgent / 统计任务状态 | 统计任务状态 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/task/statistic | [apis/110-agent.auto.new.open.task.statistic.md](apis/110-agent.auto.new.open.task.statistic.md) |
| 111 | 应用集成类 / TrekAgent / 分页查询历史消息 | 分页查询历史消息 | GET | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/pageListLatestMsg | [apis/111-agent.auto.new.open.pagelistlatestmsg.md](apis/111-agent.auto.new.open.pagelistlatestmsg.md) |
| 112 | 应用集成类 / TrekAgent / 获取会话文件树 | 获取会话文件树 | GET | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/files/tree | [apis/112-agent.auto.new.open.files.tree.md](apis/112-agent.auto.new.open.files.tree.md) |
| 113 | 应用集成类 / TrekAgent / 获取文件下载链接 | 获取文件下载链接 | GET | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/auto/new/open/files/download | [apis/113-agent.auto.new.open.files.download.md](apis/113-agent.auto.new.open.files.download.md) |
| 114 | 应用集成类 / 高码智能体 / 创建session | 创建session | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/createSession | [apis/114-agent.highcode.createsession.md](apis/114-agent.highcode.createsession.md) |
| 115 | 应用集成类 / 高码智能体 / 发起agent调用 | 发起agent调用 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/process | [apis/115-agent.highcode.process.md](apis/115-agent.highcode.process.md) |
| 116 | 应用集成类 / 高码智能体 / 终止会话 | 终止会话 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/abortSession | [apis/116-agent.highcode.abortsession.md](apis/116-agent.highcode.abortsession.md) |
| 117 | 应用集成类 / 高码智能体 / 清除会话 | 清除会话 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/agent/highcode/clearSession | [apis/117-agent.highcode.clearsession.md](apis/117-agent.highcode.clearsession.md) |
| 118 | 应用集成类 / 知识库检索 / 文件元数据批量标注 | 文件元数据批量标注 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/annotateFileMetadata | [apis/118-kortex.api.kb.metadata.annotatefilemetadata.md](apis/118-kortex.api.kb.metadata.annotatefilemetadata.md) |
| 119 | 应用集成类 / 知识库检索 / 文件元数据过滤查询 | 文件元数据过滤查询 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/metadata/filterFileCodes | [apis/119-kortex.api.kb.metadata.filterfilecodes.md](apis/119-kortex.api.kb.metadata.filterfilecodes.md) |
| 120 | 应用集成类 / 知识库检索 / 知识库检索 | 知识库检索 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/retrieve | [apis/120-kortex.api.kb.mono.retrieve.md](apis/120-kortex.api.kb.mono.retrieve.md) |
| 121 | 应用集成类 / 知识库检索 / 知识库批量检索 | 知识库批量检索 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/mono/combination/retrieve | [apis/121-kortex.api.kb.mono.combination.retrieve.md](apis/121-kortex.api.kb.mono.combination.retrieve.md) |
| 122 | 应用集成类 / 知识库检索 / 文档知识库检索 | 文档知识库检索 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/doc/retrieve | [apis/122-kortex.api.kb.doc.retrieve.md](apis/122-kortex.api.kb.doc.retrieve.md) |
| 123 | 应用集成类 / 知识库检索 / 文档知识库批量检索 | 文档知识库批量检索 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/kortex/api/kb/doc/combination/retrieve | [apis/123-kortex.api.kb.doc.combination.retrieve.md](apis/123-kortex.api.kb.doc.combination.retrieve.md) |
| 124 | 应用集成类 / 知识库检索 / 数据表知识库检索服务 | 数据表知识库检索服务 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/retrieve/v1/search | [apis/124-dext.api.retrieve.v1.search.md](apis/124-dext.api.retrieve.v1.search.md) |
| 125 | 应用集成类 / 知识库检索 / 数据表知识库资源查询-表 | 数据表知识库资源查询-表 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listTablesWithRelatedInfo | [apis/125-dext.api.dp.refres.schema.listtableswithrelatedinfo.md](apis/125-dext.api.dp.refres.schema.listtableswithrelatedinfo.md) |
| 126 | 应用集成类 / 知识库检索 / 数据表知识库资源查询-字段 | 数据表知识库资源查询-字段 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/schema/listColumnsWithRelatedInfo | [apis/126-dext.api.dp.refres.schema.listcolumnswithrelatedinfo.md](apis/126-dext.api.dp.refres.schema.listcolumnswithrelatedinfo.md) |
| 127 | 应用集成类 / 知识库检索 / 数据表知识库资源查询-专家知识 | 数据表知识库资源查询-专家知识 | POST | http://10.128.203.200:80/sfm-agent-studio/sfm-api-gateway/gateway/dext/api/dp/refRes/flexExt/list | [apis/127-dext.api.dp.refres.flexext.list.md](apis/127-dext.api.dp.refres.flexext.list.md) |
