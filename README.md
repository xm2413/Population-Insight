# 人口趋势与分析管理系统

这是一个基于 Python、Flask、SQLite 和 Matplotlib 的课程设计项目，用于完成人口趋势与分析管理系统。项目参考了 `FanTuani/Population-Insight` 的功能方向，但代码结构、页面实现、数据处理和预测逻辑均为重新设计。

## 功能模块

- 用户登录：管理员和查看者两种角色
- 人口数据管理：年度人口指标新增、编辑、删除、筛选、导出
- 统计分析：按指标查看最新年度排名和地区历史变化
- 全球人口统计：按国家和洲维度统计全球人口样本数据
- 地区对比：多地区同年份横向对比
- 趋势预测：使用简单线性回归预测后续年度趋势
- 数据可视化：使用 Matplotlib 生成折线图、柱状图、饼图
- 风险预警：自动识别老龄化率、自然增长率、出生率风险
- 数据导入：支持 CSV 文本批量导入或覆盖更新
- 地区档案：维护地区基础信息
- 操作日志：记录登录、导入、导出和数据维护行为

## 默认账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123` |
| 查看者 | `viewer` | `viewer123` |

## 运行方式

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器访问：

```text
http://127.0.0.1:5000
```

首次启动会自动创建 `data/population_trend.db`，并写入北京、上海、广东、四川、河南的样例人口数据，以及中国、印度、美国、印度尼西亚、巴西、尼日利亚等国家维度的全球人口样例数据。

## CSV 导入字段

导入页面支持以下英文表头：

```text
region,year,total_population,male_population,female_population,birth_rate,death_rate,natural_growth_rate,aging_rate,urbanization_rate,source,note
```

其中人口单位为万人，率类字段单位为 `%`。

## 项目结构

```text
.
├── app.py
├── population_trend/
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── record_service.py
│   ├── analysis_service.py
│   ├── visualization_service.py
│   └── validators.py
├── requirements.txt
├── README.md
├── data/
│   └── population_trend.db
└── static/
    ├── charts/
    └── app.css
```

## 模块化说明

项目没有把所有逻辑堆在主程序中：

- `database.py`：数据库连接、建表、初始化样例数据
- `auth.py`：登录认证、权限装饰器、操作日志
- `record_service.py`：人口数据增删改查、筛选、导入导出
- `analysis_service.py`：统计摘要、全球人口统计、地区对比、风险预警、趋势预测
- `visualization_service.py`：Matplotlib 图表生成
- `validators.py`：表单数据校验函数
