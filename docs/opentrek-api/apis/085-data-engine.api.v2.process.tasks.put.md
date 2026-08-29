# 更新加工任务

- 文档序号：085
- 分类：平台功能类 / 数据中心 / 数据加工 / 更新加工任务
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.process.tasks.put
- 请求方法：PUT
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks
- 文档版本：1787280870604

## 接口概述

更新加工任务[UpdateProcessTask]

更新加工任务，支持修改任务名称、描述、类型、模版信息及配置。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| id | Integer | 是 | body | 任务ID | 123 |
| name | String | 是 | body | 任务名称 | 自定义清洗任务 |
| description | String | 否 | body | 任务描述 | 自定义清洗任务 |
| type | String | 是 | body | 任务类型 | pipeline |
| tplId | Integer | 是 | body | 模版ID | 12 |
| tplName | String | 是 | body | 模版名称 | 数据清洗 |
| tplCode | String | 是 | body | 模版Code | text_clean |
| tplVersion | String | 是 | body | 模版版本 | v1.0.0 |
| config | Object | 是 | body | 任务配置 |  |
| config.datasetImport | String | 是 | body | 输入数据集 | sfm://dataset_code/subset |
| config.datasetExport | String | 是 | body | 输出数据集 | sfm://dataset_code/subset |
| config.np | Integer | 否 | body | 计算并行度 | 1 |
| config.process | List<Object> | 否 | body | pipeline配置，算子执行列表 | [{"word_parser_offline_mapper": {"image_ocr": false, "save_file": false, "deep_parse": true, "table_parse": false, "equation_parse": false, "image_filter_size": [3,3]}}, {"parser_format_offline_mapper": {"persistent": true, "input_feature_key": "word_parser", "input_feature_type": "word_parser"}}] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean | 是 | body | 是否成功 | true |


## 请求示例

#### curl命令示例

```bash
curl -X 'PUT' http://10.128.203.200:30226/gatectl/data-engine/api/v2/process/tasks \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-d '{
  "id": 123,
  "name": "自定义清洗任务",
  "description": "自定义清洗任务",
  "type": "pipeline",
  "tplId": 12,
  "tplName": "数据清洗",
  "tplCode": "text_clean",
  "tplVersion": "v1.0.0",
  "config": {}
}'
```


## 响应示例

#### 返回数据

```bash
true
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

- apiCode：data-engine.api.v2.process.tasks.put
- groupCode：DATAPROCESS
- catalogCode：OPERATORS
- serviceRegion：ctl
