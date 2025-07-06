import React from "react";

interface BlessingAudioProps {
  src: string;
}

const BlessingAudio: React.FC<BlessingAudioProps> = ({ src }) => (
  <div className="my-4 text-center">
    <audio controls src={src} className="mx-auto" />
  </div>
);

export default BlessingAudio;
