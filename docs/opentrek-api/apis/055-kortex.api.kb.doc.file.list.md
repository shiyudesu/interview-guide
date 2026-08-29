# 文档知识库文件列表查询

- 文档序号：055
- 分类：平台功能类 / 知识库管理 / 文档知识库文件列表查询
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.doc.file.list
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/file/list
- 文档版本：1787280870411

## 接口概述

文档知识库文件列表查询

查询文档 知识库文件信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| current | Integer | 是 | Body | 当前页码 | 1 |
| pageSize | Integer | 是 | Body | 每页大小 | 10 |
| kbCode | String | 是 | Body | 知识库唯一编码 | h8qp21tb85pf |
| fileCode | String | 否 | Body | 文件代码 | 1866347c49824f62ab061576b8891806 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的文档总数 | 1 |
| data.list | List<Object> | 是 | Body | 查询到的文档列表 |  |
| data.list.kbCode | String | 是 | Body | 知识库code | h8qp21tb85pf |
| data.list.fileCode | String | 是 | Body | 文档code | 1866347c49824f62ab061576b8891806 |
| data.list.fileOriginalName | String | 是 | Body | 文档原名 | 【情报附件】101330100230176-漏洞验证.docx |
| data.list.filePath | String | 是 | Body | 文档路径 | apsara/kortex/kb/doc/file/aopf27k2rZieth5u7ce8fhTN2p6j1DRn/【情报附件】101330100230176-漏洞验证.docx |
| data.list.fileType | String | 是 | Body | 文档类型 | docx |
| data.list.fileSize | String | 是 | Body | 文档大小 |  |
| data.list.fileChecksum | String | 是 | Body | fileChecksum |  |
| data.list.ownerId | String | 是 | Body | 拥有者id | 48381f1dbff84ad890605177585ea7ff |
| data.list.fileOutputChunkPath | String | 是 | Body | 文档解析出的chunk的路径 | kortex/kb/doc/file/1866347c49824f62ab061576b8891806/output/chunk/chunk.jsonl |
| data.list.state | Integer | 是 | Body | 状态  103 待转存;102 转存失败;0 待调度\|转存成功;100 进行中;200 成功;500 失败 | 200 |
| data.list.uploadType | Integer | 是 | Body | 上传类型 1 - 手动上传, 2 - API上传 | API |
| data.list.refRes | String | 否 | Body | 关联资源 |  |
| data.list.metadata | String | 否 | Body | 元数据 |  |
| data.list.projectCode | String | 是 | Body | 所属工作空间编码 | baseline |
| data.list.createTime | String | 是 | Body | 创建时间 | 2025-07-09T19:28:46.289265 |
| data.list.createUser | String | 是 | Body | 创建者 | dke |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/file/list \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "current":1,
    "pageSize":10,
    "kbCode":"kk062kg1t4hd"
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"total":1,"list":[{"kbCode":"kk062kg1t4hd","fileCode":"7a3f64a3f22a4f12b2fe2557d3139595","fileOriginalUrl":"https://ibp-deliver.oss-cn-hangzhou.aliyuncs.com/%E3%80%8A%E6%88%91%E6%9B%BE%E8%B5%B0%E5%9C%A8%E5%B4%A9%E6%BA%83%E7%9A%84%E8%BE%B9%E7%BC%98%E3%80%8B_full.pdf","fileOriginalName":"《我曾走在崩溃的边缘》_full.pdf","filePath":"kortex/kb/doc/file/kk062kg1t4hd/7a3f64a3f22a4f12b2fe2557d3139595/《我曾走在崩溃的边缘》_full.pdf","fileType":"pdf","fileSize":null,"fileChecksum":null,"ownerId":"2b6b6d96279a4c7eaf3357dca86a4844","fileOriginalOutputChunkUrl":null,"fileOutputChunkPath":null,"state":100,"uploadType":2,"refRes":null,"metadata":null,"projectCode":"17ac7ce4-23ad-413b-95f4-55732b15a4b7","createTime":"2025-07-22T23:49:44.740747","createUser":"gaochai","updateTime":"2025-07-22T23:49:51.550727","updateUser":null,"createUserId":"2b6b6d96279a4c7eaf3357dca86a4844","updateUserId":"2b6b6d96279a4c7eaf3357dca86a4844"}],"pageSize":10,"current":1},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.doc.file.list
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
