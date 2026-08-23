function StatCard({ card }) {
  return (
    <div className="bg-neutral-800 rounded-xl p-6 mb-4">
      <h3 className="text-sm uppercase tracking-wide text-neutral-400 mb-2">
        {card.title}
      </h3>
      <p className="text-3xl font-bold text-white mb-2">{card.value}</p>
      {card.subtitle && (
        <p className="text-sm text-neutral-400">{card.subtitle}</p>
      )}
    </div>
  );
}

export default StatCard;