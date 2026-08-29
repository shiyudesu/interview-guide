# 查询提示词分类

- 文档序号：040
- 分类：平台功能类 / 智能体管理 / 提示词模版 / 查询提示词分类
- 唯一编码：sfm.api.openapi-agent.agent.openapi.prompt.queryprompttypes
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/agent/openapi/prompt/queryPromptTypes
- 文档版本：1787280870315

## 接口概述

查询提示词分类

查询提示词分类。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | Object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的提示词分类总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的提示词分类列表 |  |
| data.list.code | String | 是 | Body | 提示词分类唯一编码 | ZCXL |
| data.list.name | String | 是 | Body | 提示词分类名称 | 职场效率 |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' 'http://10.128.203.200:30226/gatectl/agent/openapi/prompt/queryPromptTypes' \
-H 'Content-Type: application/json'  \
-H 'x-sfm-workspacecode: baseline'  \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-d '{
    "current":1,
    "pageSize":10
}'
```


## 响应示例

#### 返回数据

```json
{
    "success": true,
    "data": {
        "total": 10,
        "list": [
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:49.621+00:00",
                "gmtModified": "2025-06-17T07:20:49.621+00:00",
                "code": "ZCXL",
                "name": "职场效率",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:43.370+00:00",
                "gmtModified": "2025-06-17T07:20:43.370+00:00",
                "code": "YXWA",
                "name": "营销文案",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:37.434+00:00",
                "gmtModified": "2025-06-17T07:20:37.434+00:00",
                "code": "WBCL",
                "name": "文本处理",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:31.831+00:00",
                "gmtModified": "2025-06-17T07:20:31.831+00:00",
                "code": "SJFX",
                "name": "数据分析",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:24.433+00:00",
                "gmtModified": "2025-06-17T07:20:24.433+00:00",
                "code": "SHZS",
                "name": "生活助手",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:19.418+00:00",
                "gmtModified": "2025-06-17T07:20:19.418+00:00",
                "code": "RWDH",
                "name": "人物对话",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:13.111+00:00",
                "gmtModified": "2025-06-17T07:20:13.111+00:00",
                "code": "JYPX",
                "name": "教育培训",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:08.109+00:00",
                "gmtModified": "2025-06-17T07:20:08.109+00:00",
                "code": "FYZL",
                "name": "翻译助理",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            },
            {
                "id": null,
                "gmtCreate": "2025-06-17T07:20:01.812+00:00",
                "gmtModified": "2025-06-17T07:20:01.812+00:00",
                "code": "DMBC",
                "name": "代码编程",
                "marketType": "promptTemplate",
                "desc": null,
                "owner": {
                    "userId": "503",
                    "userName": "huanxiang"
                },
                "modifiyUser": null,
                "recommendItems": null,
                "feature": null,
                "managers": null
            }
        ],
        "pageSize": 10,
        "current": 1,
        "totalPages": 1
    },
    "errorCode": null,
    "errorMsg": null
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

- apiCode：agent.openapi.prompt.queryprompttypes
- groupCode：OPENAPI-AGENT
- catalogCode：PROMPT
- serviceRegion：ctl
