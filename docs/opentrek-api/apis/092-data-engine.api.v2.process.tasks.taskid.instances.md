# 获取任务运行实例信息

- 文档序号：092
- 分类：平台功能类 / 数据中心 / 数据加工 / 获取任务运行实例信息
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.process.tasks.Taskid.instances
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/instances
- 文档版本：1787280870640

## 接口概述

获取任务运行实例信息[ListTaskInstances]

获取任务运行实例信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| taskId | Integer | 是 | url | 任务ID | 100 |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| runId | Integer | 是 | Query | 任务运行ID | 1001 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| data | List<Object> |  | body | 返回数据列表 | [{"id":667,"tenantCode":"baseline","flowId":555,"taskId":556,"taskCode":"job_25204e0c233c11f0aac656db6f3d4393","taskName":"【待验证】文本-数据解析-CHUNK 切分","instanceCode":"556.250427.15:50.W6hwdGl7j.250427","instanceType":2,"duration":"3s","taskVersion":"1745740172030","execType":"KN_PROC","parents":null,"children":null,"status":4,"substatus":-1,"retry":0,"revision":0,"bizdate":"2025-04-26 15:50:00","plandate":"2025-04-27 15:50:00","execdate":null,"gmtCreate":"2025-04-27 15:50:42","gmtStart":"2025-04-27 15:50:43","gmtEnd":"2025-04-27 15:50:46","gmtHeartbeat":"2025-04-27 15:50:48","createdBy":"qingfu.zmq","rerun":false,"retryStrategy":null,"priority":10,"importDataset":null,"exportDataset":null}] |
| data.id | Integer | 是 | body | 实例ID | 667 |
| data.tenantCode | String | 是 | body | 租户Code | baseline |
| data.flowId | Integer | 是 | body | 流程ID | 555 |
| data.taskId | Integer | 是 | body | 任务ID | 556 |
| data.taskCode | String | 是 | body | 任务Code | job_25204e0c233c11f0aac656db6f3d4393 |
| data.taskName | String | 是 | body | 任务名称 | 【待验证】文本-数据解析-CHUNK 切分 |
| data.instanceCode | String | 是 | body | 实例Code | 556.250427.15:50.W6hwdGl7j.250427 |
| data.instanceType | Integer | 是 | body | 实例类型 | 2 |
| data.duration | String | 是 | body | 执行时长 | 3s |
| data.taskVersion | String | 是 | body | 任务版本 | 1745740172030 |
| data.execType | String | 是 | body | 执行类型 | KN_PROC |
| data.parents | Object | 否 | body | 父实例 | null |
| data.children | Object | 否 | body | 子实例 | null |
| data.status | Integer | 是 | body | 实例状态（1:待执行,2:执行中,3:成功,4:失败,5:超时,6:排队中,7:异常） | 4 |
| data.substatus | Integer | 是 | body | 子状态 | -1 |
| data.retry | Integer | 是 | body | 重试次数 | 0 |
| data.revision | Integer | 是 | body | 修订版本 | 0 |
| data.bizdate | String | 是 | body | 业务日期 | 2025-04-26 15:50:00 |
| data.plandate | String | 是 | body | 计划日期 | 2025-04-27 15:50:00 |
| data.execdate | String | 否 | body | 执行日期 | null |
| data.gmtCreate | String | 是 | body | 创建时间 | 2025-04-27 15:50:42 |
| data.gmtStart | String | 是 | body | 开始时间 | 2025-04-27 15:50:43 |
| data.gmtEnd | String | 是 | body | 结束时间 | 2025-04-27 15:50:46 |
| data.gmtHeartbeat | String | 是 | body | 心跳时间 | 2025-04-27 15:50:48 |
| data.createdBy | String | 是 | body | 创建人 | qingfu.zmq |
| data.rerun | Boolean | 是 | body | 是否重跑 | false |
| data.retryStrategy | Object | 否 | body | 重试策略 | null |
| data.priority | Integer | 是 | body | 优先级 | 10 |
| data.importDataset | Object | 否 | body | 导入数据集 | null |
| data.exportDataset | Object | 否 | body | 导出数据集 | null |
| pageSize | Integer | 是 | body | 分页大小 | 20 |
| totalCount | Integer | 是 | body | 总条数 | 79 |
| pageNumber | Integer | 是 | body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/${taskId}/instances?runId=${runId} \
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
      "id": 667,
      "tenantCode": "baseline",
      "flowId": 555,
      "taskId": 556,
      "taskCode": "job_25204e0c233c11f0aac656db6f3d4393",
      "taskName": "【待验证】文本-数据解析-CHUNK 切分",
      "instanceCode": "556.250427.15:50.W6hwdGl7j.250427",
      "instanceType": 2,
      "duration": "3s",
      "taskVersion": "1745740172030",
      "execType": "KN_PROC",
      "parents": null,
      "children": null,
      "status": 4,
      "substatus": -1,
      "retry": 0,
      "revision": 0,
      "bizdate": "2025-04-26 15:50:00",
      "plandate": "2025-04-27 15:50:00",
      "execdate": null,
      "gmtCreate": "2025-04-27 15:50:42",
      "gmtStart": "2025-04-27 15:50:43",
      "gmtEnd": "2025-04-27 15:50:46",
      "gmtHeartbeat": "2025-04-27 15:50:48",
      "createdBy": "qingfu.zmq",
      "rerun": false,
      "retryStrategy": null,
      "priority": 10,
      "importDataset": null,
      "exportDataset": null
    }
  ]
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

- apiCode：data-engine.api.v2.process.tasks.Taskid.instances
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
