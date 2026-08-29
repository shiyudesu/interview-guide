# 知识库删除

- 文档序号：050
- 分类：平台功能类 / 知识库管理 / 知识库删除
- 唯一编码：sfm.api.ctl-kortex.kortex.api.kb.delete
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/kb/delete
- 文档版本：1787280870384

## 接口概述

删除知识库

删除知识库,一并删除相关物理资源。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| code | String | 是 | Body | 知识库唯一编码 | rkiviej5rkm2 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | Body | 是否成功 | true |
| data | object | 是 | Body | 返回数据 | {} |
| data.kb | Object | 是 | Body | (自定义\|BI)知识库维度统计 |  |
| data.kb.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.kbSubmodel | Object | 是 | Body | (自定义\|BI)知识库数据模型维度统计 |  |
| data.kbSubmodel.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.kbSubmodelField | Object | 是 | Body | (自定义\|BI)知识库数据模型字段维度统计 |  |
| data.kbSubmodelField.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.kbIndex | Object | 是 | Body | (自定义\|BI)知识库索引维度统计 |  |
| data.kbIndex.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.kbIndexField | Object | 是 | Body | (自定义\|BI)知识库索引字段维度统计 |  |
| data.kbIndexField.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.monoDeletes | Object | 否 | Body | (文档知识库\|图文知识库)删除操作统计对象 |  |
| data.monoDeletes.kb | Object | 是 | Body | 知识库 |  |
| data.monoDeletes.kb.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.monoDeletes.kbSubmodel | Object | 是 | Body | 知识库数据模型 |  |
| data.monoDeletes.kbSubmodel.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.monoDeletes.kbSubmodelField | Object | 是 | Body | 知识库数据模型字段 |  |
| data.monoDeletes.kbSubmodelField.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.monoDeletes.kbIndex | Object | 是 | Body | 知识库索引 |  |
| data.monoDeletes.kbIndex.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.monoDeletes.kbIndexField | Object | 是 | Body | 知识库索引字段 |  |
| data.monoDeletes.kbIndexField.deletes | Integer | 是 | Body | 删除数量 | 1 |
| data.kbdocFileDeletes | Integer | 否 | Body | (文档知识库)删除的文件总数 | 0 |
| data.kbVisualFileDeletes | Integer | 否 | Body | (图文知识库)删除的图片总数 | 0 |
| errorCode | String | 是 | Body | 错误码 | true |
| errorMsg | String | 是 | Body | 错误描述 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/kortex/api/kb/delete \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'Content-Type: application/json' \
-H 'x-sfm-workspacecode: baseline' \
-d '{
    "code":"rkiviej5rkm2"
}'
```


## 响应示例

#### 返回数据

```json
{"success":true,"data":{"monoDeletes":{"kbIndex":{"deletes":2},"kb":{"deletes":1},"kbSubmodelField":{"deletes":9},"kbSubmodel":{"deletes":1},"kbIndexField":{"deletes":6}},"kbdocFileDeletes":0},"errorCode":null,"errorMsg":null}
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

- apiCode：kortex.api.kb.delete
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
