import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL;

function UploadPage() {
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const navigate = useNavigate();

  function handleFileChange(e) {
    setFiles(Array.from(e.target.files));
    setErrorMessage("");
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (files.length === 0) {
      setErrorMessage("Please select at least one file.");
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    formData.append("user_timezone", userTimezone);

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        setStatus("error");
        setErrorMessage(getFriendlyErrorMessage(data.detail));
        return;
      }

      navigate(`/results/${data.id}`);
    } catch (err) {
      setStatus("error");
      setErrorMessage("Couldn't reach the server. Is the backend running?");
    }
  }

  return (
    <div className="min-h-screen bg-neutral-900 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <h1 className="text-3xl font-bold text-white mb-2">
          Spotify Analytics Engine
        </h1>
        <p className="text-neutral-400 mb-8">
          Upload your Spotify Extended Streaming History export to see your
          listening story.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block w-full border-2 border-dashed border-neutral-700 rounded-xl p-6 text-center cursor-pointer hover:border-neutral-500 transition-colors">
            <input
              type="file"
              accept=".json"
              multiple
              onChange={handleFileChange}
              className="hidden"
            />
            <span className="text-neutral-300">
              {files.length > 0
                ? `${files.length} file(s) selected`
                : "Click to select your Spotify JSON export files"}
            </span>
          </label>

          <button
            type="submit"
            disabled={status === "loading"}
            className="w-full bg-green-500 hover:bg-green-400 disabled:bg-neutral-700 disabled:cursor-not-allowed text-neutral-900 font-semibold rounded-xl py-3 transition-colors"
          >
            {status === "loading" ? "Analyzing..." : "Upload"}
          </button>
        </form>

        {status === "error" && (
          <p className="text-red-400 text-sm mt-4">{errorMessage}</p>
        )}
      </div>
    </div>
  );
}

function getFriendlyErrorMessage(detail) {
  if (!detail) return "Something went wrong. Please try again.";

  if (detail.includes("No files uploaded")) {
    return "Please select at least one file to upload.";
  }
  if (detail.includes("Could not parse")) {
    return "One of your files doesn't look like valid JSON. Try re-exporting from Spotify.";
  }
  if (detail.includes("don't look like Spotify")) {
    return "These files don't look like a Spotify Extended Streaming History export. Make sure you're uploading the right files.";
  }
  if (detail.includes("Not enough listening data")) {
    return "Not enough listening history to generate stats yet — you need at least 50 plays of 30 seconds or longer.";
  }
  return detail;
}

export default UploadPage;