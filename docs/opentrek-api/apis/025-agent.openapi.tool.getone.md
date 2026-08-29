# 查询工具详情

- 文档序号：025
- 分类：平台功能类 / 智能体管理 / 工具 / 查询工具详情
- 唯一编码：sfm.api.openapi-agent.agent.openapi.tool.getone
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/tool/getOne
- 文档版本：1787280870188

## 接口概述

查询工具详情

查询工具详情。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| uniqueCode | String | 是 | Body | 工具编码 | a9c81580-8e93-42e1-b331-5cc6506c0093 |
| version | String | 是 | Body | 工具版本 | 1759118429269 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.code | String | 是 | Body | 工具编码 | a9c81580-8e93-42e1-b331-5cc6506c0093 |
| data.name | String | 是 | Body | 工具名称 | 测试工具 |
| data.desc | String | 是 | Body | 工具描述 | 测试工具 |
| data.version | String | 是 | Body | 工具版本 | 1759118429269 |
| data.serviceConfig | Object | 是 | Body | 工具配置 | {} |
| data.workspaceCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.gmtCreate | String | 是 | Body | 创建时间 | 2025-08-29T11:43:54.722+00:00 |
| data.gmtModified | String | 是 | Body | 修改时间 | 2025-08-29T11:43:54.722+00:00 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/tool/getOne' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: xxx' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{"uniqueCode": "a9c81580-8e93-42e1-b331-5cc6506c0093","version": "1759118429269"}'
```


## 响应示例

#### 返回数据

```json
{
  "errorMessages": [],
  "success": true,
  "data": {
    "id": 141,
    "gmtCreate": "2025-09-18T02:35:40.599+00:00",
    "gmtModified": "2025-09-18T02:35:40.599+00:00",
    "tenant": "fmthktsjdb",
    "code": "3c31d315-43a1-47f7-81ab-12b0d75fd2ab",
    "workspaceCode": "fmthktsjdb",
    "name": "fangyu测试-百度",
    "version": "1757382560369",
    "desc": "fangyu测试",
    "toolType": "api",
    "toolSubType": null,
    "owner": {
      "id": null,
      "gmtCreate": null,
      "gmtModified": null,
      "tenant": null,
      "uniqueCode": "33ad2daf266d454a9cd1a9469a75c53d",
      "source": null,
      "outerId": null,
      "name": "test"
    },
    "serviceConfig": {
      "executorName": "openPlatformSpiToolExecutor",
      "result2PromptName": null,
      "serviceInvocationConfig": null,
      "toolCommonConfig": null,
      "llmConfig": null,
      "toolApiConfig": {
        "apiUrl": "http://www.baidu.com",
        "toolTags": null,
        "apiProtocol": "get",
        "platformTool": null,
        "limitQps": 50,
        "apiHeaderList": [
          {
            "fieldCode": "Content-Type",
            "fieldType": "CONSTANT",
            "fieldValue": "application/json",
            "fieldDesc": "",
            "flowEditable": false,
            "encrypt": false
          }
        ],
        "requestToolApiFieldList": [
          {
            "fieldCode": "a",
            "fieldType": "STRING",
            "parentFieldCode": null,
            "required": false,
            "leaf": null,
            "flowEditable": true,
            "fieldDemo": null,
            "fieldDesc": "",
            "extend": null,
            "refType": null,
            "refValue": "",
            "propertyValue": null,
            "children": null
          }
        ],
        "responseToolApiFieldList": [
          {
            "fieldCode": "b",
            "fieldType": "STRING",
            "parentFieldCode": null,
            "required": false,
            "leaf": null,
            "flowEditable": true,
            "fieldDemo": null,
            "fieldDesc": "",
            "extend": null,
            "refType": null,
            "refValue": "",
            "propertyValue": null,
            "children": null
          }
        ],
        "asyncExecutorFlag": false,
        "mockResponse": null,
        "preHandle": null,
        "reasoningModel": null,
        "promptTemplate": null,
        "preHandlerScript": null,
        "httpMethod": "GET",
        "responseParserName": null,
        "returnByStream": false,
        "toolApiMetaConfigDTO": null,
        "browserExecution": null
      },
      "toolScriptConfig": null,
      "searchChunkConfig": null,
      "toolUseDetail": null,
      "mcpConfig": null
    },
    "shareWorkspaces": null,
    "allFlag": null
  },
  "errorCode": null,
  "errorMsg": null,
  "extraData": null,
  "traceId": null,
  "env": null,
  "other": null,
  "firstErrorMessage": null,
  "failure": false
}
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

- apiCode：agent.openapi.tool.getone
- groupCode：OPENAPI-AGENT
- catalogCode：AGENT-TOOL
- serviceRegion：ctl
