import React, { useState } from 'react';
import { ExperimentSelector } from './pages/ExperimentSelector';
import Workspace from './pages/Workspace';
import './index.css';

const App = () => {
  const [selectedExperiment, setSelectedExperiment] = useState(null);

  const handleExperimentSelect = (experiment) => {
    setSelectedExperiment(experiment);
  };

  const handleBack = () => {
    setSelectedExperiment(null);
  };

  return (
    <div className="app-container">
      {selectedExperiment ? (
        <Workspace 
          experimentType={selectedExperiment} 
          onBack={handleBack} 
        />
      ) : (
        <ExperimentSelector onSelect={handleExperimentSelect} />
      )}
    </div>
  );
};

export default App;
