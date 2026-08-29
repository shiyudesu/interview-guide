# 更新数据集

- 文档序号：065
- 分类：平台功能类 / 数据中心 / 数据管理 / 更新数据集
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.put
- 请求方法：PUT
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets
- 文档版本：1787280870484

## 接口概述

更新数据集[UpdateDataset]

更新数据集。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| code | String | 是 | Body | 数据集code | mmlu_no_train |
| name | String | 否 | Body | 数据集名称 | 张三测试数据集 |
| description | String | 否 | Body | 数据集描述 |  |
| tags | List<Object> | 否 | Body | 标签列表 | [{"id":123, "value":"1w-10w"}] |
| tags.id | Integer | 是 | Body | 标签ID | 123 |
| tags.value | String | 是 | Body | 标签值 | 1w-10w |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Boolean |  | Body | 返回数据 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'PUT' http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-d '{
  "code": "mmlu_no_train",
  "name": "张三测试数据集",
  "description": "",
  "tags": [
    {
      "id": 123,
      "value": "1w-10w"
    }
  ]
}'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": true
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

- apiCode：data-engine.api.v2.datasets.Code.put
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
