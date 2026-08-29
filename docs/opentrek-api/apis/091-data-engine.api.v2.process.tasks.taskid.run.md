# 运行加工任务

- 文档序号：091
- 分类：平台功能类 / 数据中心 / 数据加工 / 运行加工任务
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.process.tasks.Taskid.run
- 请求方法：POST
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/{taskId}/run
- 文档版本：1787280870635

## 接口概述

运行加工任务[RunProcessTask]

根据任务ID运行指定的加工任务，并返回任务运行所需的资源信息。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| xlmGroupCode | String | 是 | body | 资源池Code | xxxx |
| specs | Object | 是 | body | 规格配置 | {"name": "CPU", "data": {"vCPU": 1, "Mem": "1GB"}} |
| specs.vCPU | Integer | 是 | body | vCPU数量 | 1 |
| specs.Mem | String | 是 | body | 内存大小 | 1GB |
| specs.np | Integer | 是 | body | 并行度 | 1 |
| specs.GPU | Object | 是 | body | GPU规格 | {"NVIDIA-A100-SXM80GB": 1} |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | body | 是否成功 | true |
| data | Object |  | body | 返回数据 |  |
| data.id | Integer | 是 | body | 任务运行ID | 2357 |


## 请求示例

#### curl命令示例

```bash
curl -X 'POST' http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks/${taskId}/run \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {"id": 2357}
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

- apiCode：data-engine.api.v2.process.tasks.Taskid.run
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
