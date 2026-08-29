# 知识库数据变更

- 文档序号：052
- 分类：平台功能类 / 知识库管理 / 知识库数据变更
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.data.consumebulk
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk
- 文档版本：1787280870395

## 接口概述

按照知识库数据模型定义将数据写入知识库,支持增、删、改

按照知识库数据模型定义将数据写入知识库。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| kbCode | String | 是 | Body | 知识库唯一编码 | cozhklqn3omz |
| kbSubmodelCode | String | 是 | Body | 知识库内容结构唯一编码, 通过知识库详情获取 |  |
| datasourceNodeId | String | 是 | Body | 数据加工来源 知识库文档由DKE加工chunk的场景传递 source_builtin_dke; 其他场景传递 source_builtin_smod; 删除场景传递 kb_submodel | source_builtin_smod |
| forceReplace | Boolean | 是 | Body | 强制走replace语义 | false |
| data | List<Object> | 是 | Body | 需要变更的数据集合 | [{}] |
| data.key | List<Object> | 是 | Body | 数据key标识 |  |
| data.key.kb_submodel | Object | 是 | Body | operation=Delete场景独有 | {} |
| data.key.kb_submodel.sys_data_id | String | 是 | Body | 数据唯一ID;  检索接口会返回,文档知识库场景chunk列表会返回 |  |
| data.key.sys_data_id | String | 是 | Body | 数据唯一ID; 检索接口会返回,文档知识库场景chunk列表会返回 |  |
| data.operation | String | 是 | Body | 操作 | Insert\|Delete\|Update，注意在一个消息里面, operation需要相同 |
| data.after | Object | 是 | Body | 具体数据内容, 按照知识库不同组装的结构也不同, 当Insert\|Update 需要将数据传在after节点, 注意Update不支持增量更新,每次更新需要传递全量数据模型字段定义; 当Delete 可不传, 但要保障key节点有值 |  |
| data.after.*** | String | 是 | Body | 自定义的数据内容列, 通过知识库详情可以获取明细 | chunk_content |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例[新增]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"z7pn9wbtkpy0",
    "kbSubmodelCode":"z7pn9wbtkpy0x6l8",
    "datasourceNodeId":"source_builtin_smod",
    "forceReplace":true,
    "data":[{
        "key":{},
        "operation":"Insert",
        "after":{"matter_code":"CODE0001","matter_name":"噪音扰民"}
    }]
}'
```

#### curl命令示例[删除]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"z7pn9wbtkpy0",
    "kbSubmodelCode":"z7pn9wbtkpy0x6l8",
    "datasourceNodeId":"kb_submodel",
    "forceReplace":false,
    "data":[{
        "key":{"kb_submodel":{"sys_data_id":"9d980c00-75ae-43e2-adbf-d98183df304a"}},
    "operation":"Delete",
        "after":{}}]
}'
```

#### curl命令示例[更新]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"z7pn9wbtkpy0",
    "kbSubmodelCode":"z7pn9wbtkpy0x6l8",
    "datasourceNodeId":"source_builtin_smod",
    "forceReplace":false,
    "data":[{
        "key":{},
    "operation":"Update",
        "after":{"matter_code":"CODE0003","matter_name":"井盖缺损1","sys_data_id":"b724ba0f-a836-4f5e-88d8-c90dda96e3e6"}}]
}'
```

#### curl命令示例[问答知识库新增]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"YOUR_QA_KB_CODE",
    "kbSubmodelCode":"YOUR_QA_SUBMODEL_CODE",
    "datasourceNodeId":"source_builtin_smod",
    "forceReplace":true,
    "data":[{
        "key":{},
        "operation":"Insert",
        "after":{"question":"什么是人工智能？","answer":"人工智能是模拟人类智能的技术。"}
    }]
}'
```

#### curl命令示例[术语知识库新增]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/data/consumeBulk \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"YOUR_TERM_KB_CODE",
    "kbSubmodelCode":"YOUR_TERM_SUBMODEL_CODE",
    "datasourceNodeId":"source_builtin_smod",
    "forceReplace":true,
    "data":[{
        "key":{},
        "operation":"Insert",
        "after":{"term":"机器学习","definition":"一种通过数据训练模型来实现预测和决策的人工智能方法。"}
    }]
}'
```


## 响应示例

#### 返回数据

```json
{"success": true, "data": null, "errorCode": null, "errorMsg": null }
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

- apiCode：kortex.api.kb.data.consumebulk
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
