# ETHO 数据库设计文档

## 数据库概述

**数据库名称**: etho_database.db  
**数据库类型**: SQLite  
**版本**: 1.0  
**创建日期**: 2024

## 数据表设计

### 1. experiments (实验表)

存储实验元数据和配置信息。

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| experiment_id | TEXT | PRIMARY KEY | 实验唯一标识符 (UUID) |
| subject_id | TEXT | NOT NULL | 小鼠编号 |
| group_name | TEXT | - | 实验组别 (WT, 5xFAD, APP/PS1等) |
| experiment_type | TEXT | - | 实验类型 (Open Field, Y-Maze等) |
| video_path | TEXT | - | 视频文件路径 |
| created_at | TEXT | - | 创建时间 (ISO 8601格式) |
| config_json | TEXT | - | 配置信息 (JSON格式) |
| metrics_json | TEXT | - | 分析指标 (JSON格式) |

**索引**:
- PRIMARY KEY: experiment_id
- INDEX: subject_id
- INDEX: group_name
- INDEX: created_at

**示例数据**:
```json
{
  "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
  "subject_id": "M001",
  "group_name": "WT",
  "experiment_type": "Open Field",
  "video_path": "/uploads/video_001.mp4",
  "created_at": "2024-01-15T10:30:00",
  "config_json": {
    "threshold": 50,
    "min_area": 100,
    "max_area": 10000,
    "fps": 30
  },
  "metrics_json": {
    "total_distance_cm": 1250.5,
    "avg_speed_cm_s": 8.3,
    "max_speed_cm_s": 25.6,
    "immobility_time_s": 45.2
  }
}
```

### 2. trajectories (轨迹表)

存储逐帧轨迹数据。

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| experiment_id | TEXT | FOREIGN KEY | 关联实验ID |
| frame | INTEGER | - | 帧编号 |
| timestamp | REAL | - | 时间戳 (秒) |
| x | REAL | - | X坐标 (像素) |
| y | REAL | - | Y坐标 (像素) |
| detected | INTEGER | - | 是否检测到目标 (0/1) |
| velocity | REAL | - | 瞬时速度 (像素/秒) |
| zone | TEXT | - | 所在区域名称 |

**索引**:
- PRIMARY KEY: id
- FOREIGN KEY: experiment_id REFERENCES experiments(experiment_id)
- INDEX: (experiment_id, frame)

**示例数据**:
```json
{
  "id": 1,
  "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
  "frame": 0,
  "timestamp": 0.0,
  "x": 320.5,
  "y": 240.3,
  "detected": 1,
  "velocity": 0.0,
  "zone": "center"
}
```

### 3. roi_configs (ROI配置表)

存储感兴趣区域配置。

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|----------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| experiment_id | TEXT | FOREIGN KEY | 关联实验ID |
| roi_name | TEXT | - | ROI名称 |
| roi_type | TEXT | - | ROI类型 (rectangle/circle/polygon) |
| roi_data | TEXT | - | ROI几何数据 (JSON格式) |

**索引**:
- PRIMARY KEY: id
- FOREIGN KEY: experiment_id REFERENCES experiments(experiment_id)

**示例数据**:
```json
{
  "id": 1,
  "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
  "roi_name": "Center Zone",
  "roi_type": "rectangle",
  "roi_data": {
    "x": 160,
    "y": 120,
    "width": 320,
    "height": 240
  }
}
```

## 数据关系图

```
experiments (1) ----< (N) trajectories
    |
    +----< (N) roi_configs
```

## 数据完整性约束

### 外键约束
- trajectories.experiment_id → experiments.experiment_id (CASCADE DELETE)
- roi_configs.experiment_id → experiments.experiment_id (CASCADE DELETE)

### 数据验证规则
1. **subject_id**: 不能为空，建议格式 "M001", "M002"...
2. **group_name**: 允许值为 "WT", "5xFAD", "APP/PS1", "other"
3. **experiment_type**: 允许值为 "Open Field", "Y-Maze", "Forced Swim"等
4. **x, y**: 必须为非负数
5. **frame**: 必须为非负整数
6. **detected**: 必须为 0 或 1

## 查询性能优化

### 常用查询索引
```sql
-- 按实验ID查询轨迹
CREATE INDEX idx_trajectory_exp ON trajectories(experiment_id, frame);

-- 按小鼠编号查询实验
CREATE INDEX idx_experiment_subject ON experiments(subject_id);

-- 按组别查询实验
CREATE INDEX idx_experiment_group ON experiments(group_name);

-- 按时间查询实验
CREATE INDEX idx_experiment_time ON experiments(created_at);
```

### 查询示例

**查询特定实验的所有轨迹**:
```sql
SELECT frame, x, y, velocity, zone
FROM trajectories
WHERE experiment_id = ?
ORDER BY frame;
```

**查询特定小鼠的所有实验**:
```sql
SELECT * FROM experiments
WHERE subject_id = ?
ORDER BY created_at DESC;
```

**统计各区域停留时间**:
```sql
SELECT zone, COUNT(*) as frames, 
       COUNT(*) * 1.0 / (SELECT COUNT(*) FROM trajectories WHERE experiment_id = ?) as percentage
FROM trajectories
WHERE experiment_id = ? AND detected = 1
GROUP BY zone;
```

## 数据备份策略

### 自动备份
- 每日自动备份数据库文件到 `backups/` 目录
- 保留最近30天的备份文件

### 手动备份
```bash
# 备份数据库
cp data/etho_database.db backups/etho_database_$(date +%Y%m%d).db

# 导出为SQL
sqlite3 data/etho_database.db .dump > backups/dump_$(date +%Y%m%d).sql
```

## 数据迁移

### 初始化数据库
```python
from modules.data_reporting import DatabaseManager

db_manager = DatabaseManager('data/etho_database.db')
```

### 数据导入导出
```python
# 导出实验数据
experiment = db_manager.get_experiment(experiment_id)
trajectory = db_manager.get_trajectory(experiment_id)

# 导入实验数据
db_manager.save_experiment(
    experiment_id=experiment_id,
    subject_id='M001',
    group='WT',
    experiment_type='Open Field',
    video_path='/uploads/video.mp4',
    config=config_dict,
    metrics=metrics_dict
)
```

## 性能指标

### 数据容量
- 单个实验: ~10MB (30分钟视频, 30fps)
- 数据库最大容量: 140TB (SQLite限制)
- 建议单数据库: <1000个实验

### 查询性能
- 单实验轨迹查询: <10ms
- 实验列表查询: <50ms
- 复杂统计查询: <100ms

## 安全考虑

### 数据访问控制
- 数据库文件权限: 600 (仅所有者读写)
- 备份文件加密存储
- 敏感数据(小鼠编号)脱敏处理

### 数据完整性
- 定期执行 `PRAGMA integrity_check`
- 使用事务保证数据一致性
- 实现软删除机制

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2024-01-01 | 初始版本，创建核心表结构 |
