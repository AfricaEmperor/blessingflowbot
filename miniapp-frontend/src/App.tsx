import React, { useEffect } from "react";

declare global {
  interface Window { Telegram: any }
}
const tg = window.Telegram.WebApp;

function App() {
  useEffect(() => {
    tg.ready();
  }, []);

  return (
    <div className="p-4 text-center">
      <h1 className="text-xl font-bold">🌊 Your Blessing Awaits</h1>
      <img src="/assets/flow/flow_qr.png" alt="QR Code" className="w-40 mx-auto my-4" />
      <audio controls src="/assets/flow/flow_whisper.mp3" className="mx-auto" />
      <button
        onClick={() => tg.sendData("flow-blessing-complete")}
        className="bg-indigo-600 text-white rounded-xl p-2 mt-4"
      >
        I have received it 🙏
      </button>
    </div>
);

export default App;
