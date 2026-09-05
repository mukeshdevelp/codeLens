/** Badge showing whether text came from AI (Groq, etc.) or rule-based fallback. */
export default function AiSourceBadge({ source, provider, className = "" }) {
  if (source === "ai") {
    const label = provider ? `AI · ${provider}` : "AI summary";
    return <span className={`summary-badge summary-badge-ai ${className}`.trim()}>{label}</span>;
  }
  return <span className={`summary-badge summary-badge-rules ${className}`.trim()}>Auto</span>;
}

export function PanelHeading({ title, source, provider }) {
  return (
    <div className="panel-heading">
      <h3>{title}</h3>
      <AiSourceBadge source={source} provider={provider} />
    </div>
  );
}
