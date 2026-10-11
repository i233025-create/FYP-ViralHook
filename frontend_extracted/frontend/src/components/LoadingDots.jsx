export default function LoadingDots({ label }) {
  return (
    <div className="flex flex-col items-center gap-4 py-10 animate-fade-in">
      <div className="flex gap-2">
        <span className="loading-dot" />
        <span className="loading-dot" />
        <span className="loading-dot" />
      </div>
      {label && <p className="text-discord-muted text-sm">{label}</p>}
    </div>
  )
}
