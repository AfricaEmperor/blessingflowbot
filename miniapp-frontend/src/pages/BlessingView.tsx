import React, { useEffect } from "react";

declare global {
  interface Window { Telegram: any }
}
const tg = window.Telegram.WebApp;

interface BlessingViewProps {
  blessing?: string;
}

const BlessingView: React.FC<BlessingViewProps> = ({ blessing = "flow" }) => {
  useEffect(() => {
    tg.ready();
  }, []);
  const qr = `/assets/${blessing}/${blessing}_qr.png`;
  const audio = `/assets/${blessing}/${blessing}_whisper.mp3`;
  return (
    <div className="p-4 text-center">
      <h1 className="text-xl font-bold">Your {blessing} Blessing</h1>
      <img src={qr} alt={`${blessing} QR`} className="w-40 mx-auto my-4" />
      <audio controls src={audio} className="mx-auto" />
      <button onClick={() => tg.sendData(`${blessing}-complete`)} className="bg-indigo-600 text-white rounded-xl p-2 mt-4">
        Received
      </button>
    </div>
);

export default BlessingView;
