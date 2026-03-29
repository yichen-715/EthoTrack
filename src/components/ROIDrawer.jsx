import React, { useState, useRef, useEffect } from 'react';
import { Stage, Layer, Line, Circle, Rect, RegularPolygon } from 'react-konva';

const SHAPE_TYPES = {
  POLYGON: 'polygon',
  RECTANGLE: 'rectangle',
  CIRCLE: 'circle'
};

const COLORS = [
  { name: '绿色', value: '#00ff00', fill: 'rgba(0, 255, 0, 0.3)' },
  { name: '蓝色', value: '#0088ff', fill: 'rgba(0, 136, 255, 0.3)' },
  { name: '红色', value: '#ff4444', fill: 'rgba(255, 68, 68, 0.3)' },
  { name: '黄色', value: '#ffcc00', fill: 'rgba(255, 204, 0, 0.3)' },
  { name: '紫色', value: '#aa44ff', fill: 'rgba(170, 68, 255, 0.3)' },
  { name: '青色', value: '#00cccc', fill: 'rgba(0, 204, 204, 0.3)' }
];

const ROIDrawer = ({
  width = 800,
  height = 600,
  shapeType = SHAPE_TYPES.POLYGON,
  colorIndex = 0,
  onROIComplete,
  onROIUpdate,
  isDrawing = true,
  existingROIs = []
}) => {
  const [points, setPoints] = useState([]);
  const [isFinished, setIsFinished] = useState(false);
  const [rectStart, setRectStart] = useState(null);
  const [rectEnd, setRectEnd] = useState(null);
  const [circleCenter, setCircleCenter] = useState(null);
  const [circleRadius, setCircleRadius] = useState(0);
  const [isDrawingCircle, setIsDrawingCircle] = useState(false);
  
  const stageRef = useRef(null);

  useEffect(() => {
    setPoints([]);
    setIsFinished(false);
    setRectStart(null);
    setRectEnd(null);
    setCircleCenter(null);
    setCircleRadius(0);
  }, [shapeType]);

  const currentColor = COLORS[colorIndex % COLORS.length];

  const getPointerPosition = (e) => {
    const stage = e.target.getStage();
    return stage.getPointerPosition();
  };

  const handleStageClick = (e) => {
    if (!isDrawing) return;
    
    const pos = getPointerPosition(e);
    
    if (shapeType === SHAPE_TYPES.POLYGON) {
      if (isFinished) return;
      setPoints([...points, pos.x, pos.y]);
    } else if (shapeType === SHAPE_TYPES.RECTANGLE) {
      if (!rectStart) {
        setRectStart(pos);
      } else if (!rectEnd) {
        setRectEnd(pos);
        const roi = {
          type: SHAPE_TYPES.RECTANGLE,
          x: Math.min(rectStart.x, pos.x),
          y: Math.min(rectStart.y, pos.y),
          width: Math.abs(pos.x - rectStart.x),
          height: Math.abs(pos.y - rectStart.y),
          color: currentColor
        };
        onROIComplete && onROIComplete(roi);
      }
    } else if (shapeType === SHAPE_TYPES.CIRCLE) {
      if (!circleCenter) {
        setCircleCenter(pos);
        setIsDrawingCircle(true);
      }
    }
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    
    const pos = getPointerPosition(e);
    
    if (shapeType === SHAPE_TYPES.CIRCLE && circleCenter && isDrawingCircle) {
      const dx = pos.x - circleCenter.x;
      const dy = pos.y - circleCenter.y;
      const radius = Math.sqrt(dx * dx + dy * dy);
      setCircleRadius(radius);
    }
  };

  const handleStageDblClick = (e) => {
    if (shapeType === SHAPE_TYPES.CIRCLE && circleCenter) {
      const roi = {
        type: SHAPE_TYPES.CIRCLE,
        x: circleCenter.x,
        y: circleCenter.y,
        radius: circleRadius,
        color: currentColor
      };
      onROIComplete && onROIComplete(roi);
      setCircleCenter(null);
      setCircleRadius(0);
      setIsDrawingCircle(false);
    }
  };

  const handleContextMenu = (e) => {
    e.evt.preventDefault();
    
    if (shapeType === SHAPE_TYPES.POLYGON && points.length >= 6) {
      setIsFinished(true);
      const roi = {
        type: SHAPE_TYPES.POLYGON,
        points: points,
        color: currentColor
      };
      onROIComplete && onROIComplete(roi);
    }
  };

  const resetDrawing = () => {
    setPoints([]);
    setIsFinished(false);
    setRectStart(null);
    setRectEnd(null);
    setCircleCenter(null);
    setCircleRadius(0);
    setIsDrawingCircle(false);
  };

  useEffect(() => {
    if (onROIUpdate) {
      onROIUpdate({
        type: shapeType,
        points: points,
        isFinished: isFinished,
        rectStart: rectStart,
        rectEnd: rectEnd,
        circleCenter: circleCenter,
        circleRadius: circleRadius
      });
    }
  }, [points, isFinished, rectStart, rectEnd, circleCenter, circleRadius]);

  const renderPolygonPoints = () => {
    if (shapeType !== SHAPE_TYPES.POLYGON || isFinished) return null;
    
    const circles = [];
    for (let i = 0; i < points.length; i += 2) {
      circles.push(
        <Circle
          key={i}
          x={points[i]}
          y={points[i + 1]}
          radius={6}
          fill={currentColor.value}
          stroke="white"
          strokeWidth={2}
        />
      );
    }
    return circles;
  };

  const renderExistingROIs = () => {
    return existingROIs.map((roi, index) => {
      if (roi.type === SHAPE_TYPES.POLYGON) {
        return (
          <Line
            key={index}
            points={roi.points}
            stroke={roi.color.value}
            strokeWidth={2}
            closed={true}
            fill={roi.color.fill}
          />
        );
      } else if (roi.type === SHAPE_TYPES.RECTANGLE) {
        return (
          <Rect
            key={index}
            x={roi.x}
            y={roi.y}
            width={roi.width}
            height={roi.height}
            stroke={roi.color.value}
            strokeWidth={2}
            fill={roi.color.fill}
          />
        );
      } else if (roi.type === SHAPE_TYPES.CIRCLE) {
        return (
          <RegularPolygon
            key={index}
            x={roi.x}
            y={roi.y}
            radius={roi.radius}
            sides={32}
            stroke={roi.color.value}
            strokeWidth={2}
            fill={roi.color.fill}
          />
        );
      }
      return null;
    });
  };

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      onClick={handleStageClick}
      onDblClick={handleStageDblClick}
      onMouseMove={handleMouseMove}
      onContextMenu={handleContextMenu}
      style={{ cursor: isDrawing ? 'crosshair' : 'default' }}
    >
      <Layer>
        {renderExistingROIs()}
        
        {shapeType === SHAPE_TYPES.POLYGON && points.length > 0 && (
          <Line
            points={points}
            stroke={currentColor.value}
            strokeWidth={3}
            closed={isFinished}
            fill={isFinished ? currentColor.fill : 'transparent'}
          />
        )}
        
        {renderPolygonPoints()}
        
        {shapeType === SHAPE_TYPES.RECTANGLE && rectStart && !rectEnd && (
          <Rect
            x={rectStart.x}
            y={rectStart.y}
            width={1}
            height={1}
            stroke={currentColor.value}
            strokeWidth={2}
            dash={[5, 5]}
          />
        )}
        
        {shapeType === SHAPE_TYPES.CIRCLE && circleCenter && (
          <RegularPolygon
            x={circleCenter.x}
            y={circleCenter.y}
            radius={circleRadius}
            sides={32}
            stroke={currentColor.value}
            strokeWidth={2}
            fill={isDrawingCircle ? 'transparent' : currentColor.fill}
          />
        )}
        
        {circleCenter && (
          <Circle
            x={circleCenter.x}
            y={circleCenter.y}
            radius={6}
            fill={currentColor.value}
            stroke="white"
            strokeWidth={2}
          />
        )}
      </Layer>
    </Stage>
  );
};

export { ROIDrawer, SHAPE_TYPES, COLORS };
export default ROIDrawer;
