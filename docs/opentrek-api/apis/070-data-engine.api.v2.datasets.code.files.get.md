# 获取数据集文件列表

- 文档序号：070
- 分类：平台功能类 / 数据中心 / 数据管理 / 获取数据集文件列表
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.files.get
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/files
- 文档版本：1787280870512

## 接口概述

分页查询数据集文件列表[ListDatasetFiles]

获取指定路径下的数据集文件列表，支持分页查询。可以通过查看请求示例，点击curl命令示例右侧的调试按钮验证业务接口调用效果。

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
| code | String | 是 | Url | 数据集Code | COCO_2017 |

### Body传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| filePath | String | 否 | Body | 文件路径 | val |
| relative | Boolean | 否 | Body | 是否为相对路径 | true |
| pageNumber | Integer | 否 | Body | 页码 | 1 |
| pageSize | Integer | 否 | Body | 每页数量 | 10 |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.datasetFileInfos | List<Object> |  | Body | 文件信息列表 |  |
| data.datasetFileInfos.name | String | 是 | Body | 文件名 | 000000000139.jpg |
| data.datasetFileInfos.filepath | String | 是 | Body | 文件路径 | sfm/dataset/baseline/opentrek/COCO_2017/main/val/000000000139.jpg |
| data.datasetFileInfos.suffix | String | 是 | Body | 文件后缀 | jpg |
| data.datasetFileInfos.size | Integer | 是 | Body | 文件大小 | 161811 |
| data.datasetFileInfos.lastModified | Integer | 是 | Body | 最后修改时间戳 | 1737106513 |
| data.pageSize | Integer | 是 | Body | 每页数量 | 10 |
| data.totalCount | Integer | 是 | Body | 总数 | 5000 |
| data.pageNumber | Integer | 是 | Body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${code}/files' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx' \
-d '{
  "filePath": "val",
  "relative": true,
  "pageNumber": 1,
  "pageSize": 10
}'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "datasetFileInfos": [
      {
        "name": "000000000139.jpg",
        "filepath": "sfm/dataset/baseline/opentrek/COCO_2017/main/val/000000000139.jpg",
        "suffix": "jpg",
        "size": 161811,
        "lastModified": 1737106513
      },
      {
        "name": "000000000285.jpg",
        "filepath": "sfm/dataset/baseline/opentrek/COCO_2017/main/val/000000000285.jpg",
        "suffix": "jpg",
        "size": 335861,
        "lastModified": 1737106513
      }
    ],
    "pageSize": 10,
    "totalCount": 5000,
    "pageNumber": 1
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

- apiCode：data-engine.api.v2.datasets.Code.files.get
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
