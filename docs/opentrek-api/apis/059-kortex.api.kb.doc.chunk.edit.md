# 文档知识库chunk内容修正

- 文档序号：059
- 分类：平台功能类 / 知识库管理 / 文档知识库chunk内容修正
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.doc.chunk.edit
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/edit
- 文档版本：1787280870438

## 接口概述

文档知识库chunk内容修正

文档知识库chunk内容修正,将数据写入知识库。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| data | Object | 是 | Body | 需要变更的数据集 | {} |
| data.chunk_content | String | 是 | Body | chunk内容 |  |
| data.sys_data_id | String | 是 | Body | 数据唯一ID,文档知识库场景为分段code |  |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/doc/chunk/edit \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
     "kbCode":"l0a0grkcvvpp",
     "data":{
     "sys_data_id":"4c318d34-8a4d-41f6-8c77-1ea48ad168bf",
     "chunk_content":"序言1\n适合谁来看\n这本书肯定是适合教育行业的创业者的。因为教育行业的创业者一 定会遇到很多跟新东方同样的问题。但是,我觉得这本书的读者远远不 止教育行业的创业者。\n因为创业和管理企业都是相通的,不管你是在教育领域还是在其他 领域,去看一个人、一个组织从零发展到行业巨头的过程,一定对你有 某种启示。所以总体来说,本书适合所有想创新、创业的人。\n此外,我觉得这是一本非常好的讲成长的书。很多大学生都希望自 己进大学的时候,就能够了解社会、了解创业、了解发展。所以讲述新 东方的成长历程,是让大学生提前知道他们想知道的,让他们知道创 业、企业到底是怎么一回事,以便更好地在上大学期间确定自己未来是 否可以创业。因为你会知道创业的过程原来是这样的,并判断创业是否 可以跟自己的个性相匹配。所以你可以思考:我能不能成为下一个俞敏 洪,或者下一个马云?\n还有一点,是一以贯之的,就是希望能够激励一些挣扎在困境中的 朋友。很多人可能都知道新东方的校训和励志文化,但并不知道校训中 的那句“在绝望中寻找希望”是我在什么情境下写在笔记本上的。也许 很多人可能会想“我曾走在崩溃的边缘”太危言耸听,但我想说,这就 是真实的创业历程,成功并不能掩盖我们曾经遇见的困难与困惑——现 实总是比电影更精彩。这就好似我曾在北大做分享时提及的一个例子, 蜗牛虽然不能像雄鹰一样一下飞到金字塔顶,但是它的坚韧,照样可以 带它看到更高的风景。\n总而言之,希望我的这些感悟和思考,能够对所有成长中的年轻 人,但也不仅限于年轻人,有所帮助,哪怕一点点。\n人生是一场漫长的马拉松,加油。\n\n\n"
     }
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

- apiCode：kortex.api.kb.doc.chunk.edit
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
