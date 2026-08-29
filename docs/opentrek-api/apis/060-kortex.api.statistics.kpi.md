# 文档知识库资源用量-汇总KPI接口

- 文档序号：060
- 分类：平台功能类 / 知识库管理 / 文档知识库资源用量-汇总KPI接口
- 唯一编码：sfm.api.ctl-kortex.kortex.api.statistics.kpi
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/statistics/kpi
- 文档版本：1787280870444

## 接口概述

获取三个核心指标数据

获取三个核心指标数据。根据指定的筛选条件，计算并返回指定时间范围内的核心指标总览。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| dataType | String | 否 | Query | 数据类型  | 201 目前仅支持 文档知识库 可不传 |
| startTime | String | 否 | Query | 统计时间点，格式：YYYY-MM-DD。该场景与 endTime 保持一致 | 2025-01-20 |
| endTime | String | 否 | Query | 统计时间点，格式：YYYY-MM-DD。该场景与 startTime 保持一致, 结束时间未传则默认是今天 | 2025-01-26 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| errorCode | Integer | 是 | body | 错误码 | 0 |
| errorMsg | String | 是 | body | 错误信息 | success |
| success | Boolean | 是 | body | 是否成功 | true |
| data | List<Object> | 是 | body | 核心指标数据列表 | [{"key": "fileCount", "label": "文件总数", "value": 1262}, ...] |
| data.key | String | 是 | body | 指标Key | fileCount\|fileSize\|tokenCount |
| data.label | String | 是 | body | 指标名称 | 原始文件总数 |
| data.value | Integer | 是 | body | 指标值 | 1262 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/kortex/api/statistics/kpi \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": [
    {
      "key": "fileCount",
      "label": "文件总数",
      "value": 1
    },
    {
      "key": "fileSize",
      "label": "文件大小",
      "value": 3532962
    },
    {
      "key": "tokenCount",
      "label": "Token总数(仅统计文档类型)",
      "value": "121036"
    }
  ],
  "errorCode": null,
  "errorMsg": null
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

- apiCode：kortex.api.statistics.kpi
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
