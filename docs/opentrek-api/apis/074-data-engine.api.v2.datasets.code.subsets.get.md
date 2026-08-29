# 数据集子集列表

- 文档序号：074
- 分类：平台功能类 / 数据中心 / 数据管理 / 数据集子集列表
- 唯一编码：sfm.api.dataprocess.data-engine.api.v2.datasets.Code.subsets.get
- 请求方法：GET
- 调用地址：http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/{code}/subsets
- 文档版本：1787280870533

## 接口概述

数据集子集列表[ListSubsets]

获取数据集子集列表。可以通过查看请求示例，点击 curl 命令示例右侧的调试按钮验证业务接口调用效果。

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
| datasetCode | String | 是 | Url | 数据集Code | mmlu_no_train |

### Query传参

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| built | Boolean | 否 | Query | 是否只获取已构建好的子集 | true |
| subsets | List<String> | 否 | Query | 子集列表 | ["default"] |

## 响应参数

| 字段 | 类型 | 必填 | 位置 | 描述 | 示例 |
| --- | --- | --- | --- | --- | --- |
| success | Boolean |  | Body | 是否成功 | true |
| data | Object |  | Body | 返回数据 |  |
| data.subsets | List<Object> | 是 | Body | 子集列表 |  |
| data.subsets.code | String | 是 | Body | 子集Code | image_subset |
| data.subsets.name | String | 是 | Body | 子集名称 | image_subset |
| data.subsets.parquetFilesSize | Integer | 是 | Body | 子集数据大小，单位bytes | 275025 |
| data.subsets.rowCount | Integer | 是 | Body | 子集数据行数 | 5000 |
| data.subsets.features | List<Object> | 是 | Body | 字段列表 |  |
| data.subsets.features.columnName | String | 是 | Body | 字段名称 | __idx |
| data.subsets.features.columnType | String | 是 | Body | 字段类型 | string |
| data.subsets.features.columnPhysicalType | String | 是 | Body | 字段物理类型 | varchar |
| data.subsets.features.columnComment | String | 是 | Body | 字段描述 |  |
| data.subsets.splits | List<Object> | 是 | Body | 切片列表 |  |
| data.subsets.splits.code | String | 是 | Body | 切片Code | train |
| data.subsets.splits.subset | String | 是 | Body | 所属子集 | image_subset |
| data.subsets.splits.name | String | 是 | Body | 切片名称 | train |
| data.subsets.splits.parquetFilesSize | Integer | 是 | Body | 切片数据大小，单位bytes | 275025 |
| data.subsets.splits.rowCount | Integer | 是 | Body | 切片数据行数 | 5000 |
| data.subsets.splits.sourceFiles | List<String> | 是 | Body | 源文件列表 | ["sfm/dataset/baseline/opentrek/COCO_2017/main/**/*.jpg"] |
| data.subsets.lastModified | Integer | 是 | Body | 最后修改时间 | 1737107658 |
| data.pageSize | Integer | 是 | Body | 每页数量 | 2 |
| data.totalCount | Integer | 是 | Body | 总数 | 2 |
| data.pageNumber | Integer | 是 | Body | 当前页码 | 1 |


## 请求示例

#### curl命令示例

```bash
curl -X 'GET' 'http://10.128.203.200:30226/gatectl/data-engine/api/v2/datasets/${datasetCode}/subsets?built=${built}&subsets=${subsets}' \
-H 'Authorization: Bearer YOUR_APP_KEY' \
-H 'x-sfm-workspacecode: xxx'
```


## 响应示例

#### 返回数据

```json
{
  "success": true,
  "data": {
    "subsets": [
      {
        "code": "image_subset",
        "name": "image_subset",
        "parquetFilesSize": 275025,
        "rowCount": 5000,
        "features": [
          {
            "columnName": "__idx",
            "columnType": "string",
            "columnPhysicalType": "varchar",
            "columnComment": ""
          },
          {
            "columnName": "image",
            "columnType": "Image",
            "columnPhysicalType": "struct(bytes blob, path varchar)",
            "columnComment": ""
          }
        ],
        "splits": [
          {
            "code": "train",
            "subset": "image_subset",
            "name": "train",
            "parquetFilesSize": 275025,
            "rowCount": 5000,
            "sourceFiles": [
              "sfm/dataset/baseline/opentrek/COCO_2017/main/**/*.jpg"
            ]
          }
        ],
        "lastModified": 1737107658
      },
      {
        "code": "image_subset_annotation_dd52841...9d1e7925c5",
        "name": "image_subset_annotation_dd52841...9d1e7925c5",
        "parquetFilesSize": 8898,
        "rowCount": 14,
        "features": [
          {
            "columnName": "image",
            "columnType": "Image",
            "columnPhysicalType": "struct(bytes blob, path varchar)",
            "columnComment": ""
          },
          {
            "columnName": "label",
            "columnType": "string",
            "columnPhysicalType": "varchar",
            "columnComment": ""
          }
        ],
        "splits": [
          {
            "code": "train",
            "subset": "image_subset_annotation_dd52841...9d1e7925c5",
            "name": "train",
            "parquetFilesSize": 8898,
            "rowCount": 14,
            "sourceFiles": [
              "sfm/dataset/baseline/opentrek/COCO_2017/parquet/image_subset_annotation_dd528417ad82405f835e969d1e7925c5/train/0000.parquet"
            ]
          }
        ],
        "lastModified": 1737107659
      }
    ],
    "pageSize": 2,
    "totalCount": 2,
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

- apiCode：data-engine.api.v2.datasets.Code.subsets.get
- groupCode：DATAPROCESS
- catalogCode：DATASET
- serviceRegion：ctl
