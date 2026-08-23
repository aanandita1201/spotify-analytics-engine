import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL;

function ResultsPage() {
  const { id } = useParams();
  const [status, setStatus] = useState("loading"); // loading | error | success
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
    return <p>Loading your results...</p>;
  }

  if (status === "error") {
    return <p style={{ color: "red" }}>{errorMessage}</p>;
  }

  return (
    <div>
      <h1>Your Spotify Story</h1>
      <p><em>{results.disclaimer}</em></p>

      {results.shareable_cards.map((card) => (
        <pre key={card.id}>{JSON.stringify(card, null, 2)}</pre>
      ))}
    </div>
  );
}

export default ResultsPage;