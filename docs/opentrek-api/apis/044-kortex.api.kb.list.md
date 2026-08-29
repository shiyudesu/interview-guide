# 知识库列表查询

- 文档序号：044
- 分类：平台功能类 / 知识库管理 / 知识库列表查询
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.list
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/list
- 文档版本：1787280870349

## 接口概述

查询知识库列表

获取知识库列表，支持根据知识库唯一编码，或知识库名称，或知识库类型进行筛选，支持分页参数。知识库类型包括：100(自定义知识库)、201(文档知识库)、202(BI知识库)、203(图文知识库)、204(问答知识库)、205(术语知识库)。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| pageIndex | Integer | 是 | Body | 当前请求页 | 1 |
| pageSize | Integer | 是 | Body | 每页请求条数 | 60 |
| kbCode | String | 否 | Body | 知识库唯一编码 | qdqsajkhjn6x |
| kbName | String | 否 | Body | 知识库名称 | 高柴测试图文知识库 |
| kbType | Integer | 否 | Body | 知识库类型 | 100,"自定义知识库",<br>    201,"文档知识库",<br>    202,"BI知识库",<br>   203,"图文知识库",<br>    204,"问答知识库",<br>   205,"术语知识库" |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的知识库总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的知识库列表 |  |
| data.list.code | String | 是 | Body | 知识库唯一编码 | qdqsajkhjn6x |
| data.list.name | String | 是 | Body | 知识库名称 | 高柴测试图文知识库 |
| data.list.kbType | Integer | 是 | Body | 知识库类型 | 100,"自定义知识库",<br>    201,"文档知识库",<br>    202,"BI知识库",<br>   203,"图文知识库",<br>    204,"问答知识库",<br>   205,"术语知识库" |
| data.list.description | String | 是 | Body | 知识库描述 | 高柴测试 |
| data.list.projectCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.list.createTime | String | 是 | Body | 创建时间 | 2025-07-04T21:28:45.03314 |
| data.list.createUser | String | 是 | Body | 创建者 | gaochai |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/list \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
      "pageIndex":1,
     "pageSize":10
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"total":1,"list":[{"id":363,"code":"z7pn9wbtkpy0","name":"自定义知识库","kbType":100,"description":"测试自定义知识库创建","sysProperties":null,"kbProperties":null,"refRes":null,"state":null,"deleteFlag":null,"disableFlag":0,"projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T22:59:48.073965","createUser":"gaochai","updateTime":"2025-07-22T22:59:48.073969","updateUser":"gaochai"}],"pageSize":60,"current":1},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.list
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
