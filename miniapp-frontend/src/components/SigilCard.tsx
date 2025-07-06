import React from "react";

interface SigilCardProps {
  title: string;
  date: string;
  image: string;
}

const SigilCard: React.FC<SigilCardProps> = ({ title, date, image }) => (
  <div className="border rounded-lg p-2 m-2">
    <img src={image} alt={title} className="w-full h-auto" />
    <h2 className="text-lg font-semibold mt-2">{title}</h2>
    <p className="text-sm text-gray-600">{date}</p>
  </div>
);

export default SigilCard;
