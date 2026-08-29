# 知识库数据查询

- 文档序号：053
- 分类：平台功能类 / 知识库管理 / 知识库数据查询
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.submodel.data.list
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/submodel/data/list
- 文档版本：1787280870400

## 接口概述

知识库数据查询,例如自定义知识库场景下定义的数据模型录入的业务数据,也适用于问答知识库(kbType=204)和术语知识库(kbType=205)的数据查询

按照知识库的kbSubmodels[0].kbSubmodelCode 字段用户可实现针对特定数据模型下的业务数据查询。问答知识库(kbType=204)数据字段为question/answer；术语知识库(kbType=205)数据字段为term/definition。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| kbSubmodelCode | String | 是 | Body | 知识库数据模型编码,见知识库详情返回结构 kbSubmodels[0].kbSubmodelCode  | tttbnz21diense89 |
| kbCode | String | 是 | Body | 知识库编码 |  |
| current | Integer | 是 | Body | 分页页数 | 10 |
| pageSize | Integer | 是 | Body | 每页条数 | 10 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的知识库总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的知识库列表 |  |
| data.list.sys_data_id | String | 是 | Body | 数据唯一ID; | true |
| data.list.sys_create_time | String | 是 | Body | 创建时间 | true |
| data.list.sys_source_ids | String | 是 | Body | 数据附加信息 | true |
| data.list.**** | String | 是 | Body | 自定义的数据字段;例如我创建了一个自定义知识库,定义了一个‘标准知识库’,包含两个字段 matter_code,matter_name; | 自定义的数据字段对应的值 |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/submodel/data/list \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"z7pn9wbtkpy0",
     "kbSubmodelCode":"z7pn9wbtkpy0x6l8",
       "current":1,
     "pageSize":10
}'
```


## 响应示例

#### 返回数据

```json
{"total":3,"list":[{"matter_name":"井盖缺损1","sys_source_ids":"{\"kb_submodel\": \"true\", \"kb_submodel.sys_data_id\": \"b724ba0f-a836-4f5e-88d8-c90dda96e3e6\"}","sys_data_id":"b724ba0f-a836-4f5e-88d8-c90dda96e3e6","matter_code":"CODE0003","sys_create_time":"2025-07-22T15:44:14.592+00:00"},{"matter_name":"噪音扰民","sys_source_ids":"{\"kb_submodel\": \"true\", \"kb_submodel.sys_data_id\": \"d42ba34b-553c-4d7f-adc6-ef81ce65255f\"}","sys_data_id":"d42ba34b-553c-4d7f-adc6-ef81ce65255f","matter_code":"CODE0003","sys_create_time":"2025-07-22T15:43:05.304+00:00"},{"matter_name":"私搭乱建","sys_source_ids":"{\"kb_submodel\": \"true\", \"source_builtin_smod\": \"true\", \"kb_submodel.sys_data_id\": \"d3a2163b-68de-400f-a2b3-dd312247207d\", \"source_builtin_smod.sys_id\": \"1\"}","sys_data_id":"d3a2163b-68de-400f-a2b3-dd312247207d","matter_code":"CODE0002","sys_create_time":"2025-07-22T15:17:58.050+00:00"}],"pageSize":10,"current":1}
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

- apiCode：kortex.api.kb.submodel.data.list
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
