import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import StatCard from "../components/StatCard";
import ListCard from "../components/ListCard";

const API_URL = import.meta.env.VITE_API_URL;

function ResultsPage() {
  const { id } = useParams();
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [results, setResults] = useState(null);

  useEffect(() => {
    async function fetchResults() {
      try {
        const response = await fetch(`${API_URL}/results/${id}`);
        const data = await response.json();

        if (!response.ok) {
          setStatus("error");
          setErrorMessage(
            response.status === 404
              ? "We couldn't find these results. The link might be wrong."
              : "Something went wrong loading your results."
          );
          return;
        }

        setResults(data);
        setStatus("success");
      } catch (err) {
        setStatus("error");
        setErrorMessage("Couldn't reach the server. Is the backend running?");
      }
    }

    fetchResults();
  }, [id]);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-neutral-900 flex items-center justify-center">
        <p className="text-white">Loading your results...</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen bg-neutral-900 flex items-center justify-center">
        <p className="text-red-400">{errorMessage}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-900 px-4 py-10">
      <div className="max-w-xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-2">
          Your Spotify Story
        </h1>
        <p className="text-sm text-neutral-400 mb-8 italic">
          {results.disclaimer}
        </p>

        {results.shareable_cards.map((card) =>
          card.type === "stat" ? (
            <StatCard key={card.id} card={card} />
          ) : (
            <ListCard key={card.id} card={card} />
          )
        )}
      </div>
    </div>
  );
}

export default ResultsPage;