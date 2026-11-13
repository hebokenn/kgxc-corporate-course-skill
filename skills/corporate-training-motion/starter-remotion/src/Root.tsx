import React from 'react';
import {Composition} from 'remotion';
import {CorporateTraining} from './Video';

export const Root: React.FC = () => {
  return <Composition
    id="CorporateTraining"
    component={CorporateTraining}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={240} // 8秒可选静音原型
    defaultProps={{}}
  />;
};
