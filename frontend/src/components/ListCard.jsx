function ListCard({ card }) {
  return (
    <div className="bg-neutral-800 rounded-xl p-6 mb-4">
      <h3 className="text-sm uppercase tracking-wide text-neutral-400 mb-2">
        {card.title}
      </h3>

      <ol className="space-y-2">
        {card.items.map((item, index) => (
          <li key={index} className="flex justify-between text-white">
            <span>{Object.values(item)[0]}</span>
            <span className="text-neutral-400 text-sm">
              {Object.values(item).slice(1).join(" · ")}
            </span>
          </li>
        ))}
      </ol>

      {card.subtitle && (
        <p className="text-sm text-neutral-400 mt-3">{card.subtitle}</p>
      )}
    </div>
  );
}

export default ListCard;