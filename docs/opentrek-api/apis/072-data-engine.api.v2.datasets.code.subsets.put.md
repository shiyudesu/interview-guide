# 更新数据子集

- 文档序号：072
- 分类：平台功能类 / 数据中心 / 数据管理 / 更新数据子集
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.subsets.put
- 请求方法：PUT
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets
- 文档版本：1787280870523

## 接口概述

更新数据子集[UpdateSubset]

更新数据子集。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| subset | String | 是 | Body | 数据子集code | default |
| dataFiles | List<String> | 是 | Body | 关联数据文件列表 | ["pdfs/*.pdf"] |
| autoUpdate | Boolean | 是 | Body | 是否自动更新视图 | true |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.id | Integer | 是 | Body | 数据集ID | 278 |
| data.code | String | 是 | Body | 数据集Code | new_yaml_test |
| data.createdAt | String | 是 | Body | 创建时间 | 2025-03-06T11:41:33.271Z |
| data.updatedAt | String | 是 | Body | 更新时间 | 2025-03-06T11:41:33.271Z |
| data.workspaceCode | String | 是 | Body | 工作组Code | opentrek |
| data.tenantCode | String | 是 | Body | 租户Code | baseline |
| data.name | String | 是 | Body | 数据集名称 | 子集配置测试 |
| data.description | String | 是 | Body | 数据集描述 | 子集配置测试 |
| data.originalFilesSize | Integer | 是 | Body | 原始资源文件大小 | 0 |
| data.parquetFilesSize | Integer | 是 | Body | 数据集大小 | 0 |
| data.rowCount | Integer | 是 | Body | 数据行数 | 0 |
| data.downloadCount | Integer | 是 | Body | 下载次数 | 0 |
| data.ownerId | String | 是 | Body | 所有者ID | 20240813 |
| data.ownerName | String | 是 | Body | 所有者用户名 | admin |
| data.tags | List<Object> | 是 | Body | 标签列表 | [] |


## 请求示例

#### curl命令示例

```bash
curl -X 'PUT' http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${code}/subsets \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-d '{
  "subset": "default",
  "dataFiles": ["pdfs/*.pdf"],
  "autoUpdate": true
}'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "id": 278,
    "code": "new_yaml_test",
    "createdAt": "2025-03-06T11:41:33.271Z",
    "updatedAt": "2025-03-06T11:41:33.271Z",
    "workspaceCode": "opentrek",
    "tenantCode": "baseline",
    "name": "子集配置测试",
    "description": "子集配置测试",
    "originalFilesSize": 0,
    "parquetFilesSize": 0,
    "rowCount": 0,
    "downloadCount": 0,
    "ownerId": "20240813",
    "ownerName": "admin",
    "tags": []
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

- apiCode：data-engine.api.v2.datasets.Code.subsets.put
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
