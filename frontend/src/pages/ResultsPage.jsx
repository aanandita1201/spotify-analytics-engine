import { useParams } from "react-router-dom";

function ResultsPage() {
  const { id } = useParams();
  return <h1>Results for {id}</h1>;
}

export default ResultsPage;