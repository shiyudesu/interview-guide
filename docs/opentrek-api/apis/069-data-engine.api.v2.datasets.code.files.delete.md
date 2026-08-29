# 通知数据集文件删除

- 文档序号：069
- 分类：平台功能类 / 数据中心 / 数据管理 / 通知数据集文件删除
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.files.delete
- 请求方法：DELETE
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/files
- 文档版本：1787280870506

## 接口概述

通知数据集文件删除[NotifyDeleteFilesFromDataset]

通知数据集中文件删除，触发与文件相关的视图自动刷新(若视图自动更新已打开)。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Path传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| code | String | 是 | Url | 数据集Code | mmlu_no_train |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| filePaths | List<String> | 是 | Body | 文件相对路径数组 | ["pdfs/1902.10909v1.pdf", "Ray -分布式计算框架架构设计详解 v2.pdf", "pdfs/2406.02543v1.pdf"] |
| relative | Boolean | 是 | Body | 是否为相对路径 | true |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.id | String | 是 | Body | 任务ID | 510FF634FCE407EEA1763854519FD3CE |
| data.completed | Boolean | 是 | Body | 是否执行完成 | true |
| data.createTime | String | 是 | Body | 任务创建时间 | 2024-10-08T11:53:23.000Z |
| data.status | String | 是 | Body | 任务状态 | Success |
| data.response | Object | 否 | Body | 任务生成的资源信息 | {} |
| data.error | String | 否 | Body | 错误信息 |  |
| data.progress | Integer | 是 | Body | 执行进度 | 100 |


## 请求示例

#### curl命令示例

```bash
curl -X 'DELETE' http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${code}/files \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-d '{
  "filePaths": [
    "pdfs/1902.10909v1.pdf",
    "Ray -分布式计算框架架构设计详解 v2.pdf",
    "pdfs/2406.02543v1.pdf"
  ],
  "relative": true
}'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "id": "510FF634FCE407EEA1763854519FD3CE",
    "completed": true,
    "createTime": "2024-10-08T11:53:23.000Z",
    "status": "Success",
    "response": {},
    "error": "",
    "progress": 100
  }
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

- apiCode：data-engine.api.v2.datasets.Code.files.delete
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
