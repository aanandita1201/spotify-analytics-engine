import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL;

function UploadPage() {
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | error
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
      setErrorMessage(
        "Couldn't reach the server. Is the backend running?"
      );
    }
  }

  return (
    <div>
      <h1>Spotify Analytics Engine</h1>
      <p>Upload your Spotify Extended Streaming History export.</p>

      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".json"
          multiple
          onChange={handleFileChange}
        />

        {files.length > 0 && (
          <p>{files.length} file(s) selected</p>
        )}

        <button type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Analyzing..." : "Upload"}
        </button>
      </form>

      {status === "error" && <p style={{ color: "red" }}>{errorMessage}</p>}
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