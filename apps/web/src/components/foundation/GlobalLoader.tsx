type GlobalLoaderProps = {
  label: string;
  detail?: string;
  tone?: "default" | "ai";
  size?: "compact" | "screen";
};

export function GlobalLoader({
  label,
  detail,
  tone = "default",
  size = "screen",
}: GlobalLoaderProps) {
  return (
    <div className={`global-loader ${size} ${tone}`} role="status" aria-live="polite">
      <div className="global-loader-orbit" aria-hidden="true">
        <span className="global-loader-core" />
        <span className="global-loader-ring one" />
        <span className="global-loader-ring two" />
        <span className="global-loader-node alpha" />
        <span className="global-loader-node beta" />
        <span className="global-loader-node gamma" />
      </div>
      <div className="global-loader-copy">
        <strong>{label}</strong>
        {detail ? <span>{detail}</span> : null}
      </div>
    </div>
  );
}
