export default function RiskBadge({ level, score }) {
  return (
    <div className={`risk-banner risk-${level}`}>
      <span>{level.toUpperCase()} RISK</span>
      <strong>{score}/100</strong>
    </div>
  );
}
