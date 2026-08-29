# 扫描Skill ZIP包

- 文档序号：030
- 分类：平台功能类 / 智能体管理 / SKILL HUB / 扫描Skill ZIP包
- 唯一编码：sfm.api.openapi-agent.agent.api.skill.scanzip
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/api/skill/scanZip
- 文档版本：1787280870236

## 接口概述

扫描上传的Skill ZIP包，解析包内容

扫描上传的Skill ZIP包，解析包内容并返回扫描报告。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| zipUrl | String | 是 | Body | ZIP文件可访问的URL | /path/to/skill.zip |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 扫描报告 | {} |
| errorCode | String | 是 | Body | 错误码 |  |
| errorMsg | String | 是 | Body | 错误描述 |  |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/api/skill/scanZip' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"zipUrl": "http://xxx.com/xxx.zip"}'
```


## 响应示例

#### 返回数据

```json
{"errorMessages":[],"success":true,"data":{"filePath":"http://sfm-lite-0518.oss-cn-hangzhou.aliyuncs.com/agent/skill-files/14ccb74d-c0a0-4959-b7e2-72d8bc3df83e/skill-vetter.zip?REDACTED_PRESIGNED_QUERY","securityStatus":true,"insecurityReasons":[]},"errorCode":null,"errorMsg":null,"extraData":null,"traceId":null,"env":null,"other":null,"errorMessage":null,"firstErrorMessage":null,"failure":false}
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

- apiCode：agent.api.skill.scanzip
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-SKILL
- serviceRegion：ctl
