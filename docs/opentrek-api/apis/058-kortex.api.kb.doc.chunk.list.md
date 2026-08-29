# 文档知识库chunk明细列表查询

- 文档序号：058
- 分类：平台功能类 / 知识库管理 / 文档知识库chunk明细列表查询
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.doc.chunk.list
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/list
- 文档版本：1787280870428

## 接口概述

文档知识库chunk明细列表查询

查询文档知识库中的chunk明细。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| pageIndex | Integer | 是 | Body | 当前页码 | 1 |
| pageSize | Integer | 是 | Body | 每页大小 | 10 |
| kbCode | String | 是 | Body | 知识库唯一编码 | h8qp21tb85pf |
| keyword | String | 是 | Body | 关键字查询 | 1 |
| code | String | 是 | Body | 分段唯一编码 | 1 |
| fileCode | String | 是 | Body | 文件编码 | 1c1363763d8a44e1a4bf27b516f269c9 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.total | Integer | 是 | Body | 查询到的列表总数 | 39 |
| data.list | List<Object> | 是 | Body | 查询到的列表 |  |
| data.list.file_code | String | 是 | Body | 文件code | 139ace527fad49d1b60642d927cf0734 |
| data.list.file_name | String | 是 | Body | 文档名 | 汇丰香港使用指南2022.5(1).pdf |
| data.list.file_path | String | 是 | Body | 文档路径 | apsara/kortex/kb/doc/file/frfINcOUgYp21rtbw3vsaXobOlFspojA/汇丰香港使用指南2022.5(1).pdf |
| data.list.create_user | String | 是 | Body | 创建者 | gaochai |
| data.list.sys_data_id | String | 是 | Body | 数据唯一id | 180eeed6-58a1-43da-980a-21d50e65615e |
| data.list.sys_create_time | String | 是 | Body | 创建时间 | 2025-07-11T20:08:40.140449 |
| data.list.chunk_upload_type | Integer | 是 | Body | 上传类型 | 1 |
| data.list.chunk_content | String | 是 | Body | chunk内容 - 召回后送入LLM的prompt文本 |  |
| data.list.chunk_representation | String | 是 | Body | chunk内容 - 用于向量化的文本, 在retrieve阶段使用 |  |
| data.list.show_content | String | 是 | Body | chunk内容 - 带有bbox和objects占位符的文本形式 |  |
| data.list.chunk_bboxs | List<Object> | 是 | Body | bbox坐标信息 |  |
| data.list.chunk_bboxs.text_bbox | List<Double> | 是 | Body | 坐标 | [<br>					0.3115,<br>					0.0683,<br>					0.0285,<br>					0.372<br>				] |
| data.list.chunk_bboxs.text_type | String | 是 | Body | 文本类型 | docTitle |
| data.list.chunk_bboxs.text_content | String | 是 | Body | 文本内容 | 汇丰香港账户使用指南\n |
| data.list.chunk_bboxs.page | Integer | 是 | Body | 页数 | 1 |
| data.list.objects | List<Object> | 是 | Body | 对象信息 - 表格,图片等 |  |
| data.list.start_page | Integer | 是 | Body | chunk序号 | 1 |
| data.list.chunk_sort_number | Integer | 是 | Body | 页码 | 0 |
| data.list.title | String | 是 | Body | 标题 |  |
| data.list.chapter_title | String | 是 | Body | 章节标题 |  |
| data.pageSize | Integer | 是 | Body | 每页大小 | 60 |
| data.current | Integer | 是 | Body | 目前所在页数 | 1 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/list \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "pageIndex":1,
    "pageSize":10,
    "kbCode":"z7pn9wbtkpy0"
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"total":1,"list":[{"file_code":"7a3f64a3f22a4f12b2fe2557d3139595","file_name":"《我曾走在崩溃的边缘》_full.pdf","file_path":"kortex/kb/doc/file/kk062kg1t4hd/7a3f64a3f22a4f12b2fe2557d3139595/《我曾走在崩溃的边缘》_full.pdf","create_user":"gaochai","sys_data_id":"88b3affd-5b56-4819-9ebd-a12e8ce46db1","sys_create_time":"2025-07-22T23:51:58.250412","chunk_upload_type":1,"chunk_content":"我曾走在;崩溃的;边缘;柳传志;徐小平;王强;鼎力推荐;中信出版集团
我曾走在崩溃的边缘
——俞敏洪亲述新东方创业发展之路
俞敏洪 著
中信出版集团","chunk_representation":"我曾走在;崩溃的;边缘;柳传志;徐小平;王强;鼎力推荐;中信出版集团
我曾走在崩溃的边缘
——俞敏洪亲述新东方创业发展之路
俞敏洪 著
中信出版集团","show_content":"{object_1_figure_0}
我曾走在崩溃的边缘
——俞敏洪亲述新东方创业发展之路
俞敏洪 著
中信出版集团","chunk_bboxs":[{"text_bbox":[0.2206,0.2898,0.0909,0.5547],"text_type":"docTitle","text_content":"我曾走在崩溃的边缘
——俞敏洪亲述新东方创业发展之路
","page":2},{"text_bbox":[0.2819,0.2923,0.0372,0.4387],"text_type":"line","text_content":"我曾走在崩溃的边缘","page":2},{"text_bbox":[0.2247,0.3542,0.0259,0.549],"text_type":"line","text_content":"——俞敏洪亲述新东方创业发展之路","page":2},{"text_bbox":[0.4567,0.404,0.0158,0.0858],"text_type":"paraText","text_content":"俞敏洪 著
","page":2},{"text_bbox":[0.4592,0.4059,0.0139,0.0817],"text_type":"line","text_content":"俞敏洪 著","page":2},{"text_bbox":[0.442,0.5114,0.0177,0.1152],"text_type":"paraText","text_content":"中信出版集团
","page":2},{"text_bbox":[0.4453,0.5133,0.0152,0.1095],"text_type":"line","text_content":"中信出版集团","page":2}],"objects":[{"object_id":"object_1_figure_0","object_type":"figure","object_sub_type":"other","object_content":"我曾走在;崩溃的;边缘;柳传志;徐小平;王强;鼎力推荐;中信出版集团","object_caption":"","object_bbox":"[0.0335,0.0019,0.9924,0.9346]","object_representation":"","object_path":"kortex/kb/doc/file/7a3f64a3f22a4f12b2fe2557d3139595/output/chunk/objects/0_0_figure.jpg","page":1}],"start_page":1,"chunk_sort_number":0,"title":null,"chapter_title":null}],"pageSize":10,"current":1},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.doc.chunk.list
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
