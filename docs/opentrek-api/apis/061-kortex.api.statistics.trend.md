# 文档知识库资源用量-图表趋势接口

- 文档序号：061
- 分类：平台功能类 / 知识库管理 / 文档知识库资源用量-图表趋势接口
- 唯一编码：sfm.api.ctl-kortex.kortex.api.statistics.trend
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/kortex/api/statistics/trend
- 文档版本：1787280870449

## 接口概述

获取趋势图所需的时间序列数据。[图表趋势接口]

获取趋势图所需的时间序列数据，采用维度与指标分离的通用格式。根据指定的筛选条件和指标，返回每日的趋势数据。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| startTime | String | 否 | Query | 筛选的开始时间，格式：YYYY-MM-DD。 | 2025-08-30 |
| endTime | String | 否 | Query | 筛选的结束时间，格式：YYYY-MM-DD。默认是最近七天 | 2025-01-26 |
| dataType | String | 否 | Query | 201 目前仅支持 文档知识库 可不传 | 201 |
| timeRange | String | 否 | Query | 预设时间范围。可选值: last_7_days, last_30_days, last_90_days, last_180_days。提供此参数时会忽略startTime和endTime。 | last_7_days |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| errorCode | Integer | 是 | body | 错误码 | 200 |
| errorMsg | String | 是 | body | 错误信息 | success |
| success | Boolean | 是 | body | 是否成功 | true |
| data | Object | 是 | body | 趋势数据 | {"dimensions": [{...},{...}], "source": [[...], ...]} |
| data.dimensions | List<Object> | 是 | body | 固定结构返回;维度和指标的名称列表，定义了source数组中每一列的含义。 | [{"key":"date","label":"时间"},{"key":"fileCount","label":"文件总数"},{"key":"fileSize","label":"文件大小"},{"key":"tokenCount","label":"token总数"}] |
| data.source | List<Object> | 是 | body | 数据矩阵。每一行代表一个时间点，每一列的值与dimensions数组中的名称一一对应。 | [["2025-08-30", 18000, 1572864, 23943], ["2025-01-21", 22000, 2097152, 134667]] |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/kortex/api/statistics/trend?startTime=${startTime}&endTime=${endTime}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "dimensions": [
      {
        "key": "date",
        "label": "时间"
      },
      {
        "key": "fileCount",
        "label": "文件总数"
      },
      {
        "key": "fileSize",
        "label": "文件大小"
      },
      {
        "key": "tokenCount",
        "label": "token总数"
      }
    ],
    "source": [
      [
        "2025-08-29",
        1,
        3532962,
        121036
      ],
      [
        "2025-08-30",
        1,
        3532962,
        121036
      ],
      [
        "2025-08-31",
        1,
        3532962,
        121036
      ],
      [
        "2025-09-01",
        1,
        3532962,
        121036
      ]
    ]
  },
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

- apiCode：kortex.api.statistics.trend
- groupCode：CTL-KORTEX
- catalogCode：DEFAULT
- serviceRegion：ctl
