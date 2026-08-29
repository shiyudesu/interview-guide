# 知识库文件上传

- 文档序号：054
- 分类：平台功能类 / 知识库管理 / 知识库文件上传
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.file.data.sync
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/file/data/sync
- 文档版本：1787280870406

## 接口概述

针对文档知识库、图文知识库、问答知识库和术语知识库可以通过该接口实现知识库源文件的写入

支持将外部文件写入知识库,接口调用成功后会返回数据库写入成功并与知识库绑定,之后触发异步上传,文件会启动转存,转存成功后会触发后续解析向量化过程。支持的知识库类型：201(文档知识库)、203(图文知识库)、204(问答知识库)、205(术语知识库)。问答知识库和术语知识库支持.csv、.json、.jsonl、.xlsx、.xls格式文件。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| kbType | Integer | 是 | Body | 知识库类型 | 仅支持 201,"文档知识库",<br>   203,"图文知识库",<br>   204,"问答知识库",<br>   205,"术语知识库" |
| referer | String | 否 | Body | 文件地址存在防盗链场景可以传递应用来源验证 | https://example.com |
| fileInfo | List<Object> | 是 | Body | 批量数据投递 |  |
| fileInfo.fileOriginalUrl | String | 是 | Body | 原始文件全路径URL地址; 平台支持白名单限制能力,受限地址访问会反馈响应"The current file address has been rejected" | https://****/tmp/pic/8f1af9cbaa9d9aee17a0c0bd944ef662.jpeg |
| fileInfo.fileOriginalName | String | 否 | Body | 文件名称, 默认截取最后一个/之后的文本 | 风景.jpeg |
| fileInfo.fileOuterCode | String | 否 | Body | 文件外部唯一标识符,建议传递,用于返回内部fileCode映射以及预处理异常信息 | 111111111 |
| fileInfo.fileOriginalContent | String | 否 | Body | 文件描述(图文知识库场景可传) | 风景 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.insert | Integer | 是 | Body | 异步待转存数量 | 0 |
| data.update | Integer | 是 | Body | 更新数量 | 0 |
| data.insertMap | JSONObject | 否 | Body | 文件编码映射, key: fileOuterCode, value: fileCode | {} |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例[文档知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/file/data/sync \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"sx60450nlt1x",
    "kbType":"201",
    "fileInfo":[{
    "fileOriginalUrl":"https://ibp-deliver.oss-cn-hangzhou.aliyuncs.com/%E3%80%8A%E6%88%91%E6%9B%BE%E8%B5%B0%E5%9C%A8%E5%B4%A9%E6%BA%83%E7%9A%84%E8%BE%B9%E7%BC%98%E3%80%8B_full.pdf",
    "fileOriginalName":"《我曾走在崩溃的边缘》_full.pdf"
    }]
}'
```

#### curl命令示例[问答知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/file/data/sync \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"YOUR_QA_KB_CODE",
    "kbType":"204",
    "fileInfo":[{
    "fileOriginalUrl":"https://example.com/qa_data.xlsx",
    "fileOriginalName":"qa_data.xlsx"
    }]
}'
```

#### curl命令示例[术语知识库]

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/file/data/sync \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "kbCode":"YOUR_TERM_KB_CODE",
    "kbType":"205",
    "fileInfo":[{
    "fileOriginalUrl":"https://example.com/term_data.csv",
    "fileOriginalName":"term_data.csv"
    }]
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"insert":1},"errorCode":null,"errorMsg":null,"traceId":null,"env":null,"ext":null}
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

- apiCode：kortex.api.kb.file.data.sync
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
