import React, { useRef, useState, useEffect, useCallback } from 'react';

const VideoPlayer = ({
  src,
  onFrameChange,
  onVideoLoad,
  width = 800,
  height = 600,
  showControls = true
}) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [frameRate, setFrameRate] = useState(25);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      const estimatedFPS = 25;
      setFrameRate(estimatedFPS);
      setTotalFrames(Math.floor(video.duration * estimatedFPS));
      
      if (onVideoLoad) {
        onVideoLoad({
          duration: video.duration,
          videoWidth: video.videoWidth,
          videoHeight: video.videoHeight,
          frameRate: estimatedFPS
        });
      }
    };

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      const frame = Math.floor(video.currentTime * frameRate);
      setCurrentFrame(frame);
      
      if (onFrameChange) {
        onFrameChange({
          time: video.currentTime,
          frame: frame
        });
      }
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('timeupdate', handleTimeUpdate);

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [frameRate, onFrameChange, onVideoLoad]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    if (!video) return;

    const rect = e.target.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    video.currentTime = percentage * duration;
  };

  const seekToFrame = (frame) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = frame / frameRate;
  };

  const stepForward = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.min(video.currentTime + 1 / frameRate, duration);
  };

  const stepBackward = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(video.currentTime - 1 / frameRate, 0);
  };

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video) return null;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    return canvas.toDataURL('image/png');
  }, []);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  return (
    <div className="video-player-container">
      <div className="video-wrapper" style={{ width, height }}>
        <video
          ref={videoRef}
          src={src}
          className="video-element"
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          preload="metadata"
        />
      </div>
      
      {showControls && (
        <div className="video-controls">
          <button onClick={stepBackward} title="后退一帧">
            ⏮
          </button>
          <button onClick={togglePlay} title={isPlaying ? '暂停' : '播放'}>
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button onClick={stepForward} title="前进一帧">
            ⏭
          </button>
          
          <div className="slider-container">
            <input
              type="range"
              min="0"
              max={duration || 100}
              step="0.01"
              value={currentTime}
              onChange={(e) => {
                const video = videoRef.current;
                if (video) {
                  video.currentTime = parseFloat(e.target.value);
                }
              }}
              style={{ width: '100%' }}
            />
          </div>
          
          <span className="time-display">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          
          <span className="time-display">
            帧: {currentFrame} / {totalFrames}
          </span>
        </div>
      )}
    </div>
  );
};

export { VideoPlayer };
export default VideoPlayer;
