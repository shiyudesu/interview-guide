# 查询Skill列表

- 文档序号：027
- 分类：平台功能类 / 智能体管理 / SKILL HUB / 查询Skill列表
- 唯一编码：sfm.api.openapi-agent.agent.api.skill.querypage
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/api/skill/queryPage
- 文档版本：1787280870217

## 接口概述

分页查询空间Skill列表

分页查询空间Skill列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| current | Integer | 是 | Body | 当前页数 | 1 |
| pageSize | Integer | 是 | Body | 每页条数 | 10 |
| skillCategory | String | 否 | Body | Skill分类，workspace=空间级，platform=平台级，share=共享 | workspace |
| skillType | String | 否 | Body | Skill类型，FILE/TOOL/WORKFLOW | FILE |
| keyword | String | 否 | Body | 搜索关键词，匹配名称或别名 |  |
| skillCode | String | 否 | Body | Skill唯一标识 |  |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的Skill总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的Skill列表 |  |
| data.list.skillCode | String | 是 | Body | Skill唯一标识 | sk-abc123 |
| data.list.name | String | 是 | Body | Skill名称 | 数据分析Skill |
| data.list.skillAlias | String | 是 | Body | Skill别名 | data-analysis |
| data.list.skillType | String | 是 | Body | Skill类型 | FILE |
| data.list.skillCategory | String | 是 | Body | Skill分类 | workspace |
| data.list.version | String | 是 | Body | Skill版本 | 1716800000000 |
| data.list.workspaceCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.list.gmtCreate | String | 是 | Body | 创建时间 | 2025-08-29T11:43:54.722+00:00 |
| data.list.gmtModified | String | 是 | Body | 修改时间 | 2025-08-29T11:43:54.722+00:00 |
| data.pageSize | Integer | 是 | Body | 每页大小 | 10 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 |  |
| errorMsg | String | 是 | Body | 错误描述 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/api/skill/queryPage' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"current": 1,"pageSize": 10,"skillCategory": "workspace","skillType": "FILE"}'
```


## 响应示例

#### 返回数据

```json
{"errorMessages":[],"success":true,"data":{"extInfos":{},"total":1,"list":[{"id":105,"skillCode":"c32e0b39-dfbe-45d7-89b2-23226465a12a","skillVersion":"1780888817410","skillAlias":"asdf","name":"amap","description":"使用高德地图Web服务API进行地点搜索、天气查询和路线规划。","skillType":"FILE","zipUrl":null,"skillRefs":null,"skillMd":"---\nname: amap\ndescription: 使用高德地图Web服务API进行地点搜索、天气查询和路线规划。\nhomepage: https://lbs.amap.com/\nmetadata: {\"clawdbot\":{\"emoji\":\"\uD83D\uDDFA️\",\"requires\":{\"bins\":[\"curl\"]},\"primaryEnv\":\"AMAP_KEY\"}}\n---\n\n# 高德地图 (Amap)\n\n本技能使用高德地图 Web 服务 API 提供丰富的地理位置服务。\n\n**重要：** 使用本技能前，你必须在高德开放平台申请一个 Web 服务 API Key，并将其设置为环境变量 `AMAP_KEY`。\n\n```bash\nexport AMAP_KEY=\"你的Web服务API Key\"\n```\n\nClawdbot 会自动读取这个环境变量来调用 API。\n\n## 何时使用 (触发条件)\n\n当用户提出以下类型的请求时，应优先使用本技能：\n- \"帮我查一下[城市]的天气\"\n- \"搜索[地点]附近的[东西]\"\n- \"查找[关键词]的位置\"\n- \"从[A]到[B]怎么走？\"\n- \"查询[地址]的经纬度\"\n- \"这个坐标[经度,纬度]是哪里？\"\n\n## 核心功能与用法\n\n### 1. 天气查询\n\n用于查询指定城市的实时天气或天气预报。\n\n**注意：** API 需要城市的 `adcode`。如果不知道 adcode，可以先通过 **行政区划查询** 功能获取。\n\n#### 查询实时天气\n```bash\n# 将 [城市adcode] 替换为实际的行政区编码, 例如北京是 110000\ncurl \"https://restapi.amap.com/v3/weather/weatherInfo?key=$AMAP_KEY&city=[城市adcode]&extensions=base\"\n```\n\n#### 查询天气预报\n```bash\n# 将 [城市adcode] 替换为实际的行政区编码\ncurl \"https://restapi.amap.com/v3/weather/weatherInfo?key=$AMAP_KEY&city=[城市adcode]&extensions=all\"\n```\n\n### 2. 地点搜索 (POI)\n\n用于根据关键字在指定城市搜索地点信息。\n\n```bash\n# 将 [关键词] 和 [城市] 替换为用户提供的内容\ncurl \"https://restapi.amap.com/v3/place/text?key=$AMAP_KEY&keywords=[关键词]&city=[城市]\"\n```\n\n### 3. 驾车路径规划\n\n用于规划两个地点之间的驾车路线。\n\n**注意：** API 需要起终点的经纬度坐标。如果用户提供的是地址，需要先通过 **地理编码** 功能将地址转换为坐标。\n\n```bash\n# 将 [起点经纬度] 和 [终点经纬度] 替换为实际坐标，格式为 \"经度,纬度\"\ncurl \"https://restapi.amap.com/v3/direction/driving?key=$AMAP_KEY&origin=[起点经纬度]&destination=[终点经纬度]\"\n```\n\n### 4. 地理编码 (地址 → 坐标)\n\n将结构化的地址信息转换为经纬度坐标。\n\n```bash\n# 将 [地址] 替换为用户提供的地址\ncurl \"https://restapi.amap.com/v3/geocode/geo?key=$AMAP_KEY&address=[地址]\"\n```\n\n### 5. 逆地理编码 (坐标 → 地址)\n\n将经纬度坐标转换为结构化的地址信息。\n\n```bash\n# 将 [经纬度] 替换为实际坐标，格式为 \"经度,纬度\"\ncurl \"https://restapi.amap.com/v3/geocode/regeo?key=$AMAP_KEY&location=[经纬度]\"\n```\n\n### 6. 行政区划查询 (获取 adcode)\n\n用于查询省、市、区、街道的行政区划信息，包括 `adcode` 和边界。\n\n```bash\n# 将 [关键词] 替换为城市或区域名称，例如 \"北京市\"\ncurl \"https://restapi.amap.com/v3/config/district?key=$AMAP_KEY&keywords=[关键词]&subdistrict=0\"\n```\n","scanReport":{"filePath":"agent/skill-files/8efb8fba-bb3b-4631-ae95-d89000ca0a8d/amap.zip","securityStatus":true,"insecurityReasons":[]},"status":"PUBLISHED","masterFlag":true,"labels":null,"feature":{"exampleQuestions":["如何查询商务出差目的地的实时天气？","怎样快速搜索公司周边的商务接待餐厅？","如何规划办公地到供应商工厂的最优路线？"]},"shareWorkspaces":["84e47d28-0570-4469-b729-de76d89362f0"],"workspaceCode":"7a92789c-3882-43f5-be70-87c84b7fbede","tenant":"baseline","gmtCreate":"2026-06-08T03:20:17.410+00:00","gmtModified":"2026-06-08T03:20:17.410+00:00","creator":{"id":null,"gmtCreate":null,"gmtModified":null,"tenant":null,"uniqueCode":"7551a976815b413bb859074c9b0677d7","source":null,"outerId":null,"name":"opentrek"},"modifier":{"id":null,"gmtCreate":null,"gmtModified":null,"tenant":null,"uniqueCode":"4e01afc2494d40d7aff9145504a36a14","source":null,"outerId":null,"name":"长堤"},"skillCategory":"workspace","installStatus":null,"exampleQuestions":["如何查询商务出差目的地的实时天气？","怎样快速搜索公司周边的商务接待餐厅？","如何规划办公地到供应商工厂的最优路线？"],"newVersionFlag":null}],"pageSize":10,"current":1,"totalPages":1},"errorCode":null,"errorMsg":null,"extraData":null,"traceId":null,"env":null,"other":null,"errorMessage":null,"firstErrorMessage":null,"failure":false}
```


## 状态码说明

#### 网关异常状态码说明

| HTTP 状态码 | 错误描述 | 错误释义 |
| --- | --- | --- |
| 401 | GATEWAY APP_KEY MISSING! | 网关必填参数缺失 |
| 401 | GATEWAY APP_KEY WRONG! | 鉴权失败,无效 APP_KEY |
| 401 | GATEWAY APP_KEY ALREADY EXPIRED! | 鉴权失败,APP_KEY 已过期 |
| 401 | GATEWAY ROLE NOT MATCH! | 鉴权失败,当前 APP_KEY 归属用户对应的角色不匹配 |
| 401 | GATEWAY ROLE HAS EXPIRED! | 鉴权失败,当前 APP_KEY 归属用户对应的角色已过期 |
| 403 | GATEWAY APP_PATH NOT FOUND! | 无效的服务调用路径 |
| 403 | GATEWAY APP_PATH NOT REGISTER! | 当前服务调用路径未注册 |
| 429 | GATEWAY LIMIT ! | 服务触发限流,请稍后再试 |
| 429 | GATEWAY LIMIT CURRENT CALL TYPE ! | 服务触发限流,请稍后再试 |
| 403 | GATEWAY HEADER PARAMETER MISSING! | 业务所需必填参数缺失 |
| 403 | GATEWAY PARAMETER WORKSPACE NO MATCH! | 传递的工作空间编码与APP_KEY归属用户关联的工作空间编码不匹配 |
| 401 | GATEWAY AUTH_TYPE WRONG! | 鉴权失败,不支持的鉴权方式 |
| 401 | GATEWAY AUTH_USER NOT MATCH WRONG! | 鉴权失败,AK用户信息不匹配 |
| 401 | GATEWAY AUTH_USER_ROLE WRONG! | 鉴权失败,用户角色不匹配 |



## 原始文档标识

- apiCode：agent.api.skill.querypage
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-SKILL
- serviceRegion：ctl
