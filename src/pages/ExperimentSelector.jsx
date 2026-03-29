import React from 'react';

const EXPERIMENT_TYPES = [
  {
    id: 'openfield',
    name: '旷场实验',
    nameEn: 'Open Field',
    icon: '🔲',
    description: '评估小鼠自主活动能力和探索行为',
    color: '#667eea',
    preset: {
      defaultROIs: ['center', 'corner'],
      metrics: ['totalDistance', 'centerTime', 'speed']
    }
  },
  {
    id: 'ymaze',
    name: 'Y迷宫',
    nameEn: 'Y-Maze',
    icon: '🔀',
    description: '测试空间记忆和自发交替行为',
    color: '#f093fb',
    preset: {
      defaultROIs: ['armA', 'armB', 'armC', 'center'],
      metrics: ['alternation', 'armEntries', 'timePerArm']
    }
  },
  {
    id: 'fstm',
    name: '强迫游泳',
    nameEn: 'Forced Swim',
    icon: '🌊',
    description: '评估抑郁样行为和绝望状态',
    color: '#4facfe',
    preset: {
      defaultROIs: ['pool'],
      metrics: ['immobilityTime', 'latency', 'climbingTime']
    }
  },
  {
    id: 'elevated',
    name: '高架十字',
    nameEn: 'Elevated Plus Maze',
    icon: '✚',
    description: '评估焦虑样行为',
    color: '#fa709a',
    preset: {
      defaultROIs: ['openArm1', 'openArm2', 'closedArm1', 'closedArm2', 'center'],
      metrics: ['openArmTime', 'closedArmTime', 'openArmEntries']
    }
  },
  {
    id: 'watermaze',
    name: '水迷宫',
    nameEn: 'Water Maze',
    icon: '💧',
    description: '测试空间学习和记忆能力',
    color: '#00c6fb',
    preset: {
      defaultROIs: ['pool', 'platform', 'quadrants'],
      metrics: ['latency', 'pathLength', 'swimSpeed']
    }
  },
  {
    id: 'novelobject',
    name: '新物体识别',
    nameEn: 'Novel Object',
    icon: '📦',
    description: '评估物体识别记忆能力',
    color: '#a8edea',
    preset: {
      defaultROIs: ['object1', 'object2'],
      metrics: ['explorationTime', 'discriminationIndex']
    }
  },
  {
    id: 'social',
    name: '社交交互',
    nameEn: 'Social Interaction',
    icon: '👥',
    description: '评估社交行为和社交偏好',
    color: '#ffecd2',
    preset: {
      defaultROIs: ['socialZone', 'emptyZone'],
      metrics: ['socialTime', 'interactionCount']
    }
  },
  {
    id: 'rotarod',
    name: '转棒实验',
    nameEn: 'Rotarod',
    icon: '⚙️',
    description: '测试运动协调和平衡能力',
    color: '#d299c2',
    preset: {
      defaultROIs: ['rod'],
      metrics: ['latencyToFall', 'rpm']
    }
  }
];

const ExperimentSelector = ({ onSelect }) => {
  return (
    <div className="experiment-selector">
      <div className="selector-header">
        <h1 className="selector-title">ETHO</h1>
        <p className="selector-subtitle">小鼠行为学智能分析平台</p>
      </div>
      
      <div className="experiment-grid">
        {EXPERIMENT_TYPES.map((exp) => (
          <div
            key={exp.id}
            className="experiment-card"
            onClick={() => onSelect(exp)}
            style={{ '--card-color': exp.color }}
          >
            <span className="card-icon">{exp.icon}</span>
            <h3 className="card-name">{exp.name}</h3>
            <span className="card-name-en">{exp.nameEn}</span>
            <p className="card-description">{exp.description}</p>
          </div>
        ))}
      </div>
      
      <div className="selector-footer">
        <p>版本 1.0.0 | 支持 8 种行为学实验范式</p>
      </div>
    </div>
  );
};

export { ExperimentSelector, EXPERIMENT_TYPES };
export default ExperimentSelector;
