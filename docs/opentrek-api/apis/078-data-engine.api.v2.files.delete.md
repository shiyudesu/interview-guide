# 删除文件

- 文档序号：078
- 分类：平台功能类 / 数据中心 / 数据管理 / 删除文件
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.files.delete
- 请求方法：DELETE
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/files
- 文档版本：1787280870555

## 接口概述

批量删除数据集下的文件[DeleteFiles]

批量删除数据集下的文件，仅平台运维管理员/平台安全管理员/空间管理员/数据集创建者可操作。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

## 请求参数

### Header传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| Authorization | String | 是 | header | APP_KEY | Bearer YOUR_APP_KEY |
| x-sfm-workspacecode | String | 是 | header | 目标工作空间 | your_workspace_code |
| Content-Type | String | 是 | header | Content-Type | application/json |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| datasetCode | String | 是 | Query | 数据集Code | mmlu |
| filePaths | List<String> | 是 | Query | 文件路径列表 | ["train/乌龟谭.jpeg"] |
| relative | Boolean | 否 | Query | 是否使用相对路径 | true |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 | {<br>  "cnt": 1,<br>  "deletedFiles": ["train/乌龟谭.jpeg"]<br>} |
| data.cnt | Integer | 是 | Body | 删除文件数量 | 1 |
| data.deletedFiles | List<String> | 是 | Body | 已删除文件列表 | ["train/乌龟谭.jpeg"] |


## 请求示例

#### curl命令示例

```bash
curl -X 'DELETE' http://10.128.203.200:30226/gatectl/data-engine/api/v2/files?datasetCode=mmlu&filePaths=乌龟谭.jpeg,乌龟谭.jpeg&relative=true \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "cnt": 1,
    "deletedFiles": ["train/乌龟谭.jpeg"]
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

- apiCode：data-engine.api.v2.files.delete
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
